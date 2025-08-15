#!/usr/bin/env python3
"""
FastAPI Server for Human Capital Development System
Provides REST API endpoints for the ML-powered recommendation system
"""

import os
import time
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
import uvicorn

# Import our system components
from main import HumanCapitalDevelopmentSystem
from config.environments import load_config_for_environment
from api.schemas import (
    StudentSessionRequest, StudentSessionResponse,
    QuestionAttemptRequest, QuestionAttemptResponse,
    AnswerSubmissionRequest, AnswerSubmissionResponse
)
# Import middleware components
from api.middleware import (
    RequestLoggingMiddleware,
    ErrorHandlingMiddleware,
    PerformanceMonitoringMiddleware,
    RateLimitingMiddleware,
    SecurityHeadersMiddleware
)


# Global system instance
system: Optional[HumanCapitalDevelopmentSystem] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan"""
    global system

    print("🚀 Starting Human Capital Development API Server...")

    # Initialize system
    config = load_config_for_environment('development')
    system = HumanCapitalDevelopmentSystem(config, 'development')

    print("✅ API Server ready to serve requests")

    yield

    # Cleanup
    if system:
        system.shutdown()
    print("🛑 API Server shut down")


# FastAPI app with lifespan management
app = FastAPI(
    title="Human Capital Development API",
    description="ML-powered learning recommendation system with vector database",
    version="1.0.0",
    lifespan=lifespan
)

# Add middleware stack (order matters - first added = outermost layer)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitingMiddleware, redis_client=None, requests_per_minute=60)
app.add_middleware(PerformanceMonitoringMiddleware, redis_client=None)
app.add_middleware(ErrorHandlingMiddleware, debug_mode=os.getenv("DEBUG", "false").lower() == "true")
app.add_middleware(RequestLoggingMiddleware, enable_detailed_logging=True)

# CORS middleware (keep as innermost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models for API
class RecommendationRequest(BaseModel):
    student_id: str = Field(..., description="Student identifier")
    objective: str = Field(default="balanced", description="Learning objective: coverage, efficiency, success_rate, balanced")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of recommendations to return")
    use_cache: bool = Field(default=True, description="Whether to use cached results")


class RecommendationResponse(BaseModel):
    student_id: str
    objective: str
    recommendations: List[Dict[str, Any]]
    generated_at: float
    cache_hit: bool = False
    response_time_ms: float


class PerformanceAnalysisResponse(BaseModel):
    student_id: str
    total_attempts: int
    overall_success_rate: float
    cluster_performance: Dict[str, Any]
    recent_activity: List[Dict[str, Any]]
    analysis_timestamp: float


class HealthResponse(BaseModel):
    status: str
    timestamp: float
    uptime_seconds: float
    database_status: str
    redis_status: str
    ml_components_status: str
    total_questions: Optional[int] = None


def get_system() -> HumanCapitalDevelopmentSystem:
    """Dependency to get system instance"""
    if system is None:
        raise HTTPException(status_code=503, detail="System not initialized")
    return system


@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint"""
    return {
        "message": "Human Capital Development API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check(system: HumanCapitalDevelopmentSystem = Depends(get_system)):
    """System health check endpoint"""
    try:
        health_data = system.get_system_health()

        # Determine overall status
        if (health_data.get('database_status') == 'healthy' and
            health_data.get('redis_status') == 'healthy' and
            health_data.get('ml_components_status') == 'healthy'):
            status = "healthy"
        else:
            status = "degraded"

        return HealthResponse(
            status=status,
            **health_data
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {e}")


@app.post("/recommendations", response_model=RecommendationResponse)
async def get_recommendations(
    request: RecommendationRequest,
    background_tasks: BackgroundTasks,
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """Get personalized learning recommendations for a student"""
    start_time = time.time()

    try:
        # Check cache first if requested
        cache_hit = False
        if request.use_cache:
            cached_recommendations = system.cache_manager.get_cached_recommendations(
                request.student_id, request.objective
            )
            if cached_recommendations:
                cache_hit = True
                recommendations = cached_recommendations
            else:
                recommendations = system.get_recommendations_optimized(
                    student_id=request.student_id,
                    objective=request.objective,
                    top_k=request.top_k,
                    use_cache=True
                )
                # Cache the computed recommendations
                if recommendations:
                    system.cache_manager.cache_recommendations(
                        request.student_id, request.objective, recommendations
                    )
        else:
            recommendations = system.get_recommendations_optimized(
                student_id=request.student_id,
                objective=request.objective,
                top_k=request.top_k,
                use_cache=False
            )

        response_time_ms = (time.time() - start_time) * 1000

        # Log performance in background
        if system.performance_monitor:
            background_tasks.add_task(
                system.performance_monitor.track_recommendation_performance,
                request.student_id,
                recommendations,
                response_time_ms / 1000
            )

        return RecommendationResponse(
            student_id=request.student_id,
            objective=request.objective,
            recommendations=recommendations,
            generated_at=time.time(),
            cache_hit=cache_hit,
            response_time_ms=response_time_ms
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recommendation generation failed: {e}")


@app.get("/student/{student_id}/performance", response_model=PerformanceAnalysisResponse)
async def get_student_performance(
    student_id: str,
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """Get comprehensive performance analysis for a student"""
    try:
        performance_data = system.analyze_student_performance(student_id)

        if "error" in performance_data:
            raise HTTPException(status_code=404, detail=performance_data["error"])

        return PerformanceAnalysisResponse(**performance_data)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Performance analysis failed: {e}")


@app.get("/student/{student_id}/history")
async def get_student_history(
    student_id: str,
    limit: int = Query(default=100, ge=1, le=1000),
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """Get student learning history"""
    try:
        # Extract numeric student ID
        numeric_id = system._extract_student_number(student_id)

        history = system.db_manager.get_student_history_optimized(
            student_id=numeric_id,
            limit=limit
        )

        return {
            "student_id": student_id,
            "history_count": len(history),
            "history": history
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get student history: {e}")


@app.get("/questions/random", summary="Get random questions")
async def get_random_questions(
    count: int = Query(10, description="Number of questions to return"),
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """Get random questions from the database"""
    try:
        from services.question_rendering_service import QuestionRenderingService
        renderer = QuestionRenderingService(system.db_manager, system.cache_manager)
        questions = renderer.get_random_questions(count)
        summaries = [renderer.get_question_summary(q) for q in questions]
        return {"count": len(summaries), "questions": summaries}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting random questions: {str(e)}")


@app.get("/questions/search", summary="Search questions")
async def search_questions(
    q: str = Query(..., description="Search query"),
    limit: int = Query(20, description="Maximum number of results"),
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """Search questions by text content"""
    try:
        from services.question_rendering_service import QuestionRenderingService
        renderer = QuestionRenderingService(system.db_manager, system.cache_manager)
        questions = renderer.search_questions(q, limit)
        summaries = [renderer.get_question_summary(question) for question in questions]
        return {"query": q, "count": len(summaries), "questions": summaries}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching questions: {str(e)}")


@app.get("/questions/{question_id}")
async def get_question_details(
    question_id: str,
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """Get detailed information about a specific question"""
    try:
        with system.db_manager.get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=system.db_manager.RealDictCursor)

            cursor.execute("""
                SELECT q.*, p.paper_name, p.paper_code, sub.subject_name
                FROM questions q
                JOIN papers p ON q.paper_id = p.paper_id
                JOIN subjects sub ON p.subject_id = sub.subject_id
                WHERE q.question_id = %s
            """, (question_id,))

            question = cursor.fetchone()
            if not question:
                raise HTTPException(status_code=404, detail="Question not found")

            return dict(question)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get question details: {e}")


@app.get("/questions/{question_id}/similar")
async def get_similar_questions(
    question_id: str,
    top_k: int = Query(default=10, ge=1, le=50),
    similarity_threshold: float = Query(default=0.7, ge=0.0, le=1.0),
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """Find similar questions using vector similarity"""
    try:
        with system.db_manager.get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=system.db_manager.RealDictCursor)

            # Get question embeddings first
            cursor.execute("""
                SELECT openai_embedding, umap_embedding, soft_cluster
                FROM questions
                WHERE question_id = %s
            """, (question_id,))

            question_data = cursor.fetchone()
            if not question_data:
                raise HTTPException(status_code=404, detail="Question not found")

            # Use the database function for multimodal similarity
            cursor.execute("""
                SELECT * FROM find_similar_questions_multimodal(
                    %s::vector(3072),
                    %s::vector(50),
                    %s::vector(20),
                    0.5, 0.2, 0.3,
                    %s, %s
                )
            """, (
                question_data['openai_embedding'],
                question_data['umap_embedding'],
                question_data['soft_cluster'],
                similarity_threshold,
                top_k
            ))

            similar_questions = [dict(row) for row in cursor.fetchall()]

        return {
            "question_id": question_id,
            "similar_questions": similar_questions,
            "similarity_threshold": similarity_threshold
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Similar questions search failed: {e}")


@app.get("/analytics/system")
async def get_system_analytics(
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """Get system-wide analytics and metrics"""
    try:
        analytics = {}

        # System health
        analytics['health'] = system.get_system_health()

        # Performance metrics
        if system.performance_monitor:
            analytics['performance'] = system.performance_monitor.get_system_metrics()

        # Database statistics
        with system.db_manager.get_db_connection() as conn:
            cursor = conn.cursor()

            # Question statistics
            cursor.execute("SELECT COUNT(*) FROM questions")
            analytics['total_questions'] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM students")
            analytics['total_students'] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM student_question_history")
            analytics['total_attempts'] = cursor.fetchone()[0]

            # Recent activity
            cursor.execute("""
                SELECT DATE(timestamp) as date, COUNT(*) as attempts
                FROM student_question_history
                WHERE timestamp >= CURRENT_DATE - INTERVAL '7 days'
                GROUP BY DATE(timestamp)
                ORDER BY date DESC
            """)
            analytics['recent_activity'] = [
                {"date": row[0].isoformat(), "attempts": row[1]}
                for row in cursor.fetchall()
            ]

        return analytics

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analytics generation failed: {e}")


# Student Learning Workflow Endpoints

@app.post("/student/{student_id}/start-session", response_model=StudentSessionResponse)
async def start_learning_session(
    student_id: str,
    request: StudentSessionRequest,
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """Start a new learning session for a student"""
    try:
        from services.student_interaction_service import StudentInteractionService
        from services.cache_service import CacheService

        cache_service = CacheService(system.db_manager.redis_client, system.db_manager)
        interaction_service = StudentInteractionService(system.db_manager, cache_service)

        session_data = interaction_service.start_learning_session(
            student_id=student_id,
            objective=request.objective,
            session_type=request.session_type,
            target_questions=request.target_questions or 10
        )

        return StudentSessionResponse(**session_data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start session: {str(e)}")

@app.post("/student/{student_id}/attempt-question", response_model=QuestionAttemptResponse)
async def start_question_attempt(
    student_id: str,
    request: QuestionAttemptRequest,
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """Start attempting a question"""
    try:
        from services.student_interaction_service import StudentInteractionService
        from services.cache_service import CacheService

        cache_service = CacheService(system.db_manager.redis_client, system.db_manager)
        interaction_service = StudentInteractionService(system.db_manager, cache_service)

        attempt_data = interaction_service.start_question_attempt(
            student_id=student_id,
            question_id=request.question_id,
            session_id=getattr(request, 'session_id', None)
        )

        return QuestionAttemptResponse(**attempt_data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start question attempt: {str(e)}")

@app.post("/student/{student_id}/submit-answer", response_model=AnswerSubmissionResponse)
async def submit_student_answer(
    student_id: str,
    request: AnswerSubmissionRequest,
    auto_validate: bool = True,  # New parameter for auto-validation
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """Submit an answer for a question with automatic validation"""
    try:
        from services.student_interaction_service import StudentInteractionService
        from services.cache_service import CacheService

        cache_service = CacheService(system.db_manager.redis_client, system.db_manager)
        interaction_service = StudentInteractionService(system.db_manager, cache_service)

        submission_data = interaction_service.submit_answer(
            attempt_id=request.attempt_id,
            student_id=student_id,
            question_id=request.question_id,
            answer_text=request.answer_text,
            selected_option=request.selected_option,
            is_correct=request.is_correct,
            confidence_level=request.confidence_level,
            time_spent_seconds=request.time_spent_seconds,
            submission_method=request.submission_method,
            metadata=request.metadata or {},
            auto_validate=auto_validate  # Enable auto-validation
        )

        return AnswerSubmissionResponse(**submission_data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit answer: {str(e)}")

@app.get("/student/{student_id}/session/{session_id}/progress")
async def get_session_progress(
    student_id: str,
    session_id: str,
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """Get progress for a learning session"""
    try:
        from services.student_interaction_service import StudentInteractionService
        from services.cache_service import CacheService

        cache_service = CacheService(system.db_manager.redis_client, system.db_manager)
        interaction_service = StudentInteractionService(system.db_manager, cache_service)

        progress = interaction_service.get_student_session_progress(session_id)

        return {
            "student_id": student_id,
            "session_id": session_id,
            "progress": progress,
            "retrieved_at": time.time()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get session progress: {str(e)}")

@app.get("/student/{student_id}/sessions")
async def get_student_sessions(
    student_id: str,
    limit: int = 10,
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """Get recent learning sessions for a student - from cache only since we use in-memory sessions"""
    try:
        sessions = []

        # Get session data from Redis cache
        cache_keys = system.cache_manager.redis.keys("session:*")
        for key in cache_keys:
            session_data = system.cache_manager.redis.get(key)
            if session_data:
                import json
                session = json.loads(session_data)
                if str(session.get('student_id')) == str(student_id):
                    sessions.append({
                        'session_id': session.get('session_id'),
                        'objective': session.get('objective'),
                        'session_type': session.get('session_type', 'practice'),
                        'started_at': session.get('session_started_at'),
                        'status': 'active',
                        'target_questions': len(session.get('recommendations', []))
                    })

        # Sort by started_at and limit
        sessions.sort(key=lambda x: x.get('started_at', 0), reverse=True)
        sessions = sessions[:limit]

        return {
            "student_id": student_id,
            "sessions": sessions,
            "total_sessions": len(sessions)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get student sessions: {str(e)}")

# Answer Validation and Timing Endpoints

@app.get("/questions/{question_id}/answer-key")
async def get_question_answer_key(
    question_id: str,
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """Get answer key and timing data for a question (for admin/teacher use)"""
    try:
        from services.answer_validation_service import AnswerValidationService

        validator = AnswerValidationService(system.db_manager)

        answer_key = validator.get_question_answer_key(question_id)
        timing_data = validator.get_question_difficulty_timing(question_id)

        if not answer_key:
            raise HTTPException(status_code=404, detail="Question not found")

        return {
            "question_id": question_id,
            "answer_key": answer_key,
            "timing_stats": timing_data,
            "retrieved_at": time.time()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get answer key: {str(e)}")

@app.post("/questions/{question_id}/validate-answer")
async def validate_answer(
    question_id: str,
    answer_data: dict,  # {"student_answer": "C", "answer_type": "multiple_choice"}
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """Validate an answer without submitting to student history"""
    try:
        from services.answer_validation_service import AnswerValidationService

        validator = AnswerValidationService(system.db_manager)

        student_answer = answer_data.get('student_answer')
        answer_type = answer_data.get('answer_type', 'multiple_choice')

        if not student_answer:
            raise HTTPException(status_code=400, detail="student_answer is required")

        result = validator.validate_answer(question_id, student_answer, answer_type)

        return {
            "question_id": question_id,
            "validation_result": result,
            "validated_at": time.time()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to validate answer: {str(e)}")

@app.get("/questions/{question_id}/timing-stats")
async def get_question_timing_stats(
    question_id: str,
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """Get timing statistics for a question"""
    try:
        from services.answer_validation_service import AnswerValidationService

        validator = AnswerValidationService(system.db_manager)
        timing_data = validator.get_question_difficulty_timing(question_id)

        return {
            "question_id": question_id,
            "timing_statistics": timing_data,
            "retrieved_at": time.time()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get timing stats: {str(e)}")

@app.post("/cache/invalidate")
async def invalidate_cache(
    student_id: Optional[str] = None,
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """Invalidate cache for a specific student or all caches"""
    try:
        if student_id:
            deleted_count = system.cache_manager.invalidate_student_cache(student_id)
            return {"message": f"Invalidated {deleted_count} cache entries for student {student_id}"}
        else:
            # Invalidate all caches (use with caution)
            system.db_manager.redis_client.flushdb()
            return {"message": "All caches invalidated"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cache invalidation failed: {e}")


@app.post("/system/migrate")
async def migrate_data(
    background_tasks: BackgroundTasks,
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """Trigger data migration from legacy format"""
    try:
        # Run migration in background
        background_tasks.add_task(system.migrate_legacy_data, "parquet")

        return {"message": "Data migration started in background"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Migration failed to start: {e}")


# Error handlers
@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions"""
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if os.getenv("DEBUG", "false").lower() == "true" else "An error occurred"
        }
    )


def create_app() -> FastAPI:
    """Create and configure the FastAPI application"""
    return app


# =====================================================
# QUESTION RENDERING ENDPOINTS
# =====================================================

@app.get("/questions/{question_id}/render", summary="Render question with images")
async def render_question_image(
    question_id: str,
    width: int = Query(12, description="Image width"),
    height: int = Query(16, description="Image height"),
    format: str = Query("PNG", description="Image format (PNG/JPEG)"),
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """
    Render a question with its images as a visual layout
    Returns the rendered image as bytes
    """

    try:
        # Import here to avoid circular imports
        from services.question_rendering_service import QuestionRenderingService

        # Initialize rendering service
        renderer = QuestionRenderingService(
            system.db_manager,
            system.cache_manager
        )

        # Get question data
        question_data = renderer.get_question_by_id(question_id)
        if not question_data:
            raise HTTPException(status_code=404, detail="Question not found")

        # Render question to bytes
        img_bytes = renderer.render_question_to_bytes(
            question_data,
            figsize=(width, height),
            format=format.upper()
        )

        if not img_bytes:
            raise HTTPException(status_code=500, detail="Failed to render question")

        # Return image
        media_type = f"image/{format.lower()}"
        return Response(content=img_bytes, media_type=media_type)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error rendering question: {str(e)}")


@app.get("/questions/{question_id}/render/base64", summary="Render question as base64")
async def render_question_base64(
    question_id: str,
    width: int = Query(12, description="Image width"),
    height: int = Query(16, description="Image height"),
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """
    Render a question and return as base64 encoded image
    Useful for embedding in web pages
    """

    try:
        from services.question_rendering_service import QuestionRenderingService

        renderer = QuestionRenderingService(
            system.db_manager,
            system.cache_manager
        )

        question_data = renderer.get_question_by_id(question_id)
        if not question_data:
            raise HTTPException(status_code=404, detail="Question not found")

        base64_image = renderer.render_question_to_base64(
            question_data,
            figsize=(width, height)
        )

        if not base64_image:
            raise HTTPException(status_code=500, detail="Failed to render question")

        return {
            "question_id": question_id,
            "image_base64": base64_image,
            "format": "PNG",
            "size": {"width": width, "height": height}
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error rendering question: {str(e)}")


@app.get("/questions/{question_id}/image")
async def get_question_image(
    question_id: str,
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """Get question image URL or data (legacy endpoint)"""
    try:
        from services.question_rendering_service import QuestionRenderingService

        renderer = QuestionRenderingService(
            system.db_manager,
            system.cache_manager
        )

        question_data = renderer.get_question_by_id(question_id)
        if not question_data:
            raise HTTPException(status_code=404, detail="Question not found")

        # Check if question has images
        images = question_data.get('images')
        if not images:
            raise HTTPException(status_code=404, detail="No images found for this question")

        return {
            "question_id": question_id,
            "images": images,
            "has_images": bool(images),
            "render_url": f"/questions/{question_id}/render"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting question image: {str(e)}")


@app.get("/questions/{question_id}/summary", summary="Get question summary")
async def get_question_summary(
    question_id: str,
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """
    Get question summary including metadata and text preview
    """

    try:
        from services.question_rendering_service import QuestionRenderingService

        renderer = QuestionRenderingService(
            system.db_manager,
            system.cache_manager
        )

        question_data = renderer.get_question_by_id(question_id)
        if not question_data:
            raise HTTPException(status_code=404, detail="Question not found")

        summary = renderer.get_question_summary(question_data)
        return summary

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting question summary: {str(e)}")



@app.get("/questions/random/render", summary="Render random questions")
async def render_random_questions(
    count: int = Query(5, description="Number of questions to render"),
    width: int = Query(12, description="Image width"),
    height: int = Query(16, description="Image height"),
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """
    Get random questions and return their rendered images as base64
    """

    try:
        from services.question_rendering_service import QuestionRenderingService

        renderer = QuestionRenderingService(
            system.db_manager,
            system.cache_manager
        )

        questions = renderer.get_random_questions(count)

        rendered_questions = []
        for question_data in questions:
            summary = renderer.get_question_summary(question_data)
            base64_image = renderer.render_question_to_base64(
                question_data,
                figsize=(width, height)
            )

            rendered_questions.append({
                "summary": summary,
                "image_base64": base64_image
            })

        return {
            "count": len(rendered_questions),
            "questions": rendered_questions
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error rendering random questions: {str(e)}")


@app.get("/papers", summary="Get available papers")
async def get_papers(
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """
    Get list of available papers with question counts
    """

    try:
        from services.question_rendering_service import QuestionRenderingService

        renderer = QuestionRenderingService(
            system.db_manager,
            system.cache_manager
        )

        papers = renderer.get_papers_list()
        return {
            "count": len(papers),
            "papers": papers
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting papers: {str(e)}")


@app.get("/papers/{paper_code}/questions", summary="Get questions by paper")
async def get_questions_by_paper(
    paper_code: str,
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """
    Get all questions for a specific paper
    """

    try:
        from services.question_rendering_service import QuestionRenderingService

        renderer = QuestionRenderingService(
            system.db_manager,
            system.cache_manager
        )

        questions = renderer.get_questions_by_paper(paper_code)
        summaries = [renderer.get_question_summary(q) for q in questions]

        return {
            "paper_code": paper_code,
            "count": len(summaries),
            "questions": summaries
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting questions for paper {paper_code}: {str(e)}")




if __name__ == "__main__":
    # Development server
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
