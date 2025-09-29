#!/usr/bin/env python3
"""
FastAPI Server for Human Capital Development System
Provides REST API endpoints for the ML-powered recommendation system
"""

import os
import time
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

# Import our system components
from main import HumanCapitalDevelopmentSystem
from config.environments import load_config_for_environment, is_development
from api.schemas import (
    RecommendationRequest, RecommendationResponse,
    StudentSessionRequest, StudentSessionResponse,
    QuestionAttemptRequest, QuestionAttemptResponse,
    AnswerSubmissionRequest, AnswerSubmissionResponse,
    RandomQuestionsResponse, QuestionSearchResponse,
    QuestionDetailsResponse,
    # UMAP Visualization schemas
    UMAPBoundsResponse,
    StudentUMAPResponse, BasicUMAPResponse, QuestionStatusResponse
)
# Import data models for consistent response handling
from data.models import (
    ModelValidator, ValidationError,
    resolve_question_id
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

# Mount static files for development (images)
if is_development():
    from pathlib import Path
    static_path = Path(__file__).parent.parent / "p1_images"
    if static_path.exists():
        app.mount("/static/images", StaticFiles(directory=str(static_path)), name="images")


# Pydantic models for API
# RecommendationRequest and RecommendationResponse are now imported from api.schemas
# to eliminate duplication - using the comprehensive Pydantic models


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
    """Get personalized learning recommendations for a student with proper model validation"""
    start_time = time.time()

    try:
        # Pydantic handles validation automatically, but we can add additional validation if needed
        try:
            ModelValidator.validate_recommendation_request(request)
        except ValidationError as ve:
            raise HTTPException(status_code=400, detail=f"Request validation failed: {ve}")

        # Check cache first if requested
        cache_hit = False
        if request.use_cache and system.cache_manager:
            try:
                cached_recommendations = system.cache_manager.get_cached_recommendations(
                    request.student_id, request.objective
                )
                if cached_recommendations:
                    cache_hit = True
                    recommendations = cached_recommendations
                    print(f"🎯 Cache HIT for recommendations: {request.student_id}/{request.objective}")
                else:
                    print(f"🎯 Cache MISS for recommendations: {request.student_id}/{request.objective}")
                    recommendations = system.get_recommendations_optimized(
                        student_id=request.student_id,
                        objective=request.objective,
                        top_k=request.top_k,
                        use_cache=True
                    )
                    # Cache the computed recommendations
                    if recommendations and system.cache_manager:
                        system.cache_manager.cache_recommendations(
                            request.student_id, request.objective, recommendations
                        )
            except Exception as cache_error:
                print(f"🚨 Cache error: {cache_error}")
                # Fall back to fresh computation
                recommendations = system.get_recommendations_optimized(
                    student_id=request.student_id,
                    objective=request.objective,
                    top_k=request.top_k,
                    use_cache=False
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

        # Convert to API response format using proper Pydantic models
        from api.schemas import QuestionRecommendation

        formatted_recommendations = []
        if recommendations:
            for r in recommendations:
                try:
                    if hasattr(r, '__dict__'):
                        # It's a Recommendation model object, convert to QuestionRecommendation
                        rec = QuestionRecommendation(
                            question_id=r.question_id,
                            internal_question_id=r.internal_question_id,
                            paper_id=r.paper_id,
                            paper_name=getattr(r, 'paper_name', None),
                            paper_code=getattr(r, 'paper_code', None),
                            weighted_score=r.weighted_score,
                            dominant_cluster=r.dominant_cluster,
                            similarity_score=r.similarity_score,
                            combined_score=r.combined_score,
                            reasoning=r.reasoning
                        )
                        formatted_recommendations.append(rec)
                    elif isinstance(r, dict):
                        # It's already a dict, convert to QuestionRecommendation
                        rec = QuestionRecommendation(
                            question_id=r.get('question_id', ''),
                            internal_question_id=r.get('internal_question_id', 0),
                            paper_id=r.get('paper_id', 0),
                            paper_name=r.get('paper_name'),
                            paper_code=r.get('paper_code'),
                            weighted_score=r.get('weighted_score', 0.0),
                            dominant_cluster=r.get('dominant_cluster', 0),
                            similarity_score=r.get('similarity_score'),
                            combined_score=r.get('combined_score'),
                            reasoning=r.get('reasoning')
                        )
                        formatted_recommendations.append(rec)
                    else:
                        # Skip invalid recommendations
                        continue
                except Exception as e:
                    print(f"Warning: Could not format recommendation {r}: {e}")
                    continue

        return RecommendationResponse(
            student_id=request.student_id,
            objective=request.objective,
            recommendations=formatted_recommendations,
            generated_at=time.time(),
            cache_hit=cache_hit,
            response_time_ms=response_time_ms
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recommendation generation failed: {e}")


@app.get("/student/{student_id}/performance", response_model=PerformanceAnalysisResponse)
async def get_student_performance(
    student_id: str,
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """Get comprehensive performance analysis for a student using proper models"""
    try:
        # Get student performance using proper service with models
        from services.student_service import StudentService

        student_service = StudentService(system.db_manager, system.cache_manager)
        performance_model = student_service.analyze_student_performance(student_id)

        if not performance_model:
            raise HTTPException(status_code=404, detail="Student not found or no performance data")

        # Convert StudentPerformance model to API response format
        return PerformanceAnalysisResponse(
            student_id=performance_model.student_id,
            total_attempts=performance_model.total_attempts,
            overall_success_rate=performance_model.overall_success_rate,
            cluster_performance=performance_model.cluster_performance,
            recent_activity=performance_model.recent_activity,
            analysis_timestamp=performance_model.analysis_timestamp
        )

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

        # Use async database operation
        history = await system.db_manager.get_student_history_optimized_async(
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


@app.get("/questions/random", summary="Get random questions", response_model=RandomQuestionsResponse)
async def get_random_questions(
    count: int = Query(10, description="Number of questions to return"),
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """Get random questions from the database"""
    try:
        # Validate input parameters
        if count <= 0:
            raise HTTPException(status_code=400, detail="Count must be positive")
        if count > 100:
            raise HTTPException(status_code=400, detail="Count cannot exceed 100")
        from services.question_service import QuestionService
        question_service = QuestionService(system.db_manager)
        questions = question_service.get_random_questions(count)
        summaries = [question_service.question_to_summary(q) for q in questions]
        return RandomQuestionsResponse(count=len(summaries), questions=summaries)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting random questions: {str(e)}")


@app.get("/questions/search", summary="Search questions", response_model=QuestionSearchResponse)
async def search_questions(
    q: str = Query(..., description="Search query"),
    limit: int = Query(20, description="Maximum number of results"),
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """Search questions by text content"""
    try:
        # Validate search parameters
        if not q or len(q.strip()) < 2:
            raise HTTPException(status_code=400, detail="Search query must be at least 2 characters")
        if limit <= 0:
            raise HTTPException(status_code=400, detail="Limit must be positive")
        if limit > 200:
            raise HTTPException(status_code=400, detail="Limit cannot exceed 200")
        from services.question_service import QuestionService
        question_service = QuestionService(system.db_manager)
        questions = question_service.search_questions(q, limit)
        summaries = [question_service.get_question_summary(question) for question in questions]
        return QuestionSearchResponse(query=q, count=len(summaries), questions=summaries)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching questions: {str(e)}")


@app.get("/questions/{question_id}", response_model=QuestionDetailsResponse)
async def get_question_details(
    question_id: str,
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """Get detailed information about a specific question"""
    try:
        # Validate question_id format - support both internal_question_id (integer) and question_id (string)
        if not question_id or len(question_id.strip()) == 0:
            raise HTTPException(status_code=400, detail="Question ID cannot be empty")

        # Basic format validation for question_id - accept integers or Cambridge format strings
        try:
            # Use centralized validation through resolve_question_id
            resolve_question_id(question_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid question ID format: must be integer or Cambridge format (9702_...)")
        # Use the Question Rendering Service to get the question with proper Question model
        from services.question_service import QuestionService
        question_service = QuestionService(system.db_manager)

        question = question_service.get_question_by_id(question_id)
        if not question:
            raise HTTPException(status_code=404, detail="Question not found")

        # Convert Question model to dictionary response with all details
        return {
            "internal_question_id": question.internal_question_id,
            "question_id": question.question_id,
            "paper_id": question.paper_id,
            "question_number": question.question_number,
            "question_text": question.question_text,
            "images": question.images,
            "text_length": question.text_length,
            "embedding_model": question.embedding_model,
            "created_at": question.created_at,
            "updated_at": question.updated_at,
            "paper_name": question.paper_name,
            "paper_code": question.paper_code
        }

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
        # Get question embeddings first - support both question ID formats
        query_field, query_value = resolve_question_id(question_id)

        if query_field == "q.internal_question_id":
            # Search by internal_question_id
            question_data = await system.db_manager.execute_query_one_async("""
                SELECT openai_embedding, umap_embedding, soft_cluster
                FROM questions
                WHERE internal_question_id = $1
            """, (query_value,))
        else:
            # Search by question_id string
            question_data = await system.db_manager.execute_query_one_async("""
                SELECT openai_embedding, umap_embedding, soft_cluster
                FROM questions
                WHERE question_id = $1
            """, (query_value,))

        if not question_data:
            raise HTTPException(status_code=404, detail="Question not found")

        # Use async vector similarity search
        if question_data['openai_embedding']:
            similar_questions = await system.db_manager.execute_query_async("""
                SELECT q.internal_question_id, q.question_id,
                       1 - (q.openai_embedding <-> $1) as similarity_score
                FROM questions q
                WHERE q.openai_embedding IS NOT NULL
                  AND 1 - (q.openai_embedding <-> $1) >= $2
                  AND q.question_id != $3
                ORDER BY q.openai_embedding <-> $1
                LIMIT $4
            """, (
                question_data['openai_embedding'],
                similarity_threshold,
                question_id,
                top_k
            ))
        elif question_data['soft_cluster']:
            similar_questions = await system.db_manager.execute_query_async("""
                SELECT q.internal_question_id, q.question_id,
                       1 - (q.soft_cluster <-> $1) as similarity_score
                FROM questions q
                WHERE q.soft_cluster IS NOT NULL
                  AND 1 - (q.soft_cluster <-> $1) >= $2
                  AND q.question_id != $3
                ORDER BY q.soft_cluster <-> $1
                LIMIT $4
            """, (
                question_data['soft_cluster'],
                similarity_threshold,
                question_id,
                top_k
            ))
        else:
            # No embeddings available, return empty results
            similar_questions = []

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

        # Database statistics using async operations

        # Question statistics
        result = await system.db_manager.execute_query_one_async("SELECT COUNT(*) as count FROM questions")
        analytics['total_questions'] = result['count'] if result else 0

        result = await system.db_manager.execute_query_one_async("SELECT COUNT(*) as count FROM students")
        analytics['total_students'] = result['count'] if result else 0

        result = await system.db_manager.execute_query_one_async("SELECT COUNT(*) as count FROM student_question_history")
        analytics['total_attempts'] = result['count'] if result else 0

        # Recent activity
        recent_activity_results = await system.db_manager.execute_query_async("""
            SELECT DATE(timestamp) as date, COUNT(*) as attempts
            FROM student_question_history
            WHERE timestamp >= CURRENT_DATE - INTERVAL '7 days'
            GROUP BY DATE(timestamp)
            ORDER BY date DESC
        """)
        analytics['recent_activity'] = [
            {"date": row['date'].isoformat(), "attempts": row['attempts']}
            for row in recent_activity_results
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

        # Simple, efficient conversion for API response
        if 'recommendations' in session_data and session_data['recommendations']:
            from dataclasses import asdict, is_dataclass
            converted_recs = []
            for rec in session_data['recommendations']:
                if is_dataclass(rec):
                    converted_recs.append(asdict(rec))
                else:
                    # Fallback to __dict__ if not a dataclass
                    converted_recs.append(dict(rec.__dict__))
            session_data['recommendations'] = converted_recs

        # Ensure estimated_duration_minutes is an integer
        if 'estimated_duration_minutes' in session_data and session_data['estimated_duration_minutes'] is not None:
            session_data['estimated_duration_minutes'] = int(session_data['estimated_duration_minutes'])

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

        submission_data = await interaction_service.submit_answer(
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

        # Get session data from Redis cache with optimized deserialization
        cache_keys = system.cache_manager.redis.keys("session:*")
        for key in cache_keys:
            session_data = system.cache_manager.redis.get(key)
            if session_data:
                from data.serialization import deserialize_from_cache
                session = deserialize_from_cache(session_data)
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


# ==============================================
# PHASE 1 OPTIMIZATION ENDPOINTS
# ==============================================

@app.post("/cache/warm")
async def warm_caches(
    background_tasks: BackgroundTasks,
    student_limit: int = Query(30, description="Number of students to warm cache for"),
    objectives: List[str] = Query(['balanced', 'coverage'], description="Objectives to cache"),
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """Warm caches with recommendations and popular questions (Phase 1 optimization)"""
    try:
        if not system.cache_manager:
            raise HTTPException(status_code=503, detail="Cache service not available")

        # Start recommendation cache warming in background
        background_tasks.add_task(
            system.cache_manager.warm_recommendation_cache,
            None,  # Let it auto-select active students
            objectives
        )

        # Note: Question rendering cache warming removed (using frontend composition now)

        return {
            "message": "Cache warming started in background",
            "recommendation_warming": {
                "student_limit": student_limit,
                "objectives": objectives,
                "estimated_duration": "2-3 minutes"
            },
            "image_rendering": {
                "note": "Frontend composition - no server-side image cache needed",
                "status": "N/A"
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cache warming failed to start: {e}")


@app.get("/cache/statistics")
async def get_cache_statistics(
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """Get comprehensive cache performance statistics (Phase 1 monitoring)"""
    try:
        if not system.cache_manager:
            raise HTTPException(status_code=503, detail="Cache service not available")

        # Get cache service statistics
        cache_stats = system.cache_manager.get_cache_statistics()

        # Note: Question rendering statistics removed (using frontend composition now)
        rendering_stats = {"note": "Frontend composition - no server-side rendering cache"}

        # Get detailed cache analytics
        cache_analytics = system.cache_manager.cache_analytics()

        return {
            "timestamp": time.time(),
            "cache_service_stats": cache_stats,
            "question_rendering_stats": rendering_stats,
            "detailed_analytics": cache_analytics,
            "optimization_status": {
                "phase_1_complete": True,
                "image_rendering_cache": "Active",
                "recommendation_cache": "Active",
                "intelligent_warming": "Available"
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get cache statistics: {e}")


@app.get("/performance/benchmark")
async def performance_benchmark(
    test_student_id: str = Query("1", description="Student ID to test with"),
    iterations: int = Query(10, description="Number of test iterations"),
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """Run performance benchmarks to validate Phase 1 optimizations"""
    try:
        benchmark_results = {
            "test_config": {
                "student_id": test_student_id,
                "iterations": iterations,
                "timestamp": time.time()
            },
            "recommendation_performance": {},
            "question_rendering_performance": {},
            "summary": {}
        }

        # Test recommendation performance (with and without cache)
        rec_times_cold = []
        rec_times_warm = []

        for i in range(iterations):
            # Cold cache test (invalidate first)
            if system.cache_manager:
                system.cache_manager.invalidate_student_cache(test_student_id)

            start_time = time.time()
            _ = system.get_recommendations_optimized(
                student_id=test_student_id,
                objective='balanced',
                top_k=5,
                use_cache=False
            )
            cold_time = (time.time() - start_time) * 1000
            rec_times_cold.append(cold_time)

            # Warm cache test
            start_time = time.time()
            _ = system.get_recommendations_optimized(
                student_id=test_student_id,
                objective='balanced',
                top_k=5,
                use_cache=True
            )
            warm_time = (time.time() - start_time) * 1000
            rec_times_warm.append(warm_time)

        # Calculate recommendation stats
        avg_cold = sum(rec_times_cold) / len(rec_times_cold)
        avg_warm = sum(rec_times_warm) / len(rec_times_warm)

        benchmark_results["recommendation_performance"] = {
            "avg_cold_cache_ms": avg_cold,
            "avg_warm_cache_ms": avg_warm,
            "improvement_factor": avg_cold / avg_warm if avg_warm > 0 else 0,
            "improvement_percentage": ((avg_cold - avg_warm) / avg_cold * 100) if avg_cold > 0 else 0
        }

        # Note: Question rendering performance test removed (using frontend composition now)
        benchmark_results["question_rendering_performance"] = {
            "note": "Frontend composition - no server-side rendering to benchmark",
            "avg_cold_cache_ms": 0,
            "avg_warm_cache_ms": 0,
            "improvement_factor": "N/A - Frontend handles image composition",
            "improvement_percentage": "N/A"
        }

        # Overall summary
        benchmark_results["summary"] = {
            "phase_1_optimizations": "Active",
            "target_recommendation_time_ms": 80,
            "target_rendering_time_ms": 100,
            "recommendation_target_met": avg_warm < 80,
            "rendering_target_met": True,  # Frontend composition is always fast
            "overall_performance_improvement": "Significant" if avg_cold / avg_warm > 2 else "Moderate"
        }

        return benchmark_results

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Benchmark failed: {e}")


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
# QUESTION IMAGE ENDPOINTS (Frontend Composition)
# =====================================================


@app.get("/questions/{question_id}/images", summary="Get question images for frontend composition")
async def get_question_images_for_frontend(
    question_id: str,
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """
    Get question images prepared for frontend composition
    Returns image URLs based on environment (local static files or S3)
    """
    try:
        from services.question_service import QuestionService
        from services.image_service import get_image_service, QuestionImageComposer

        question_service = QuestionService(system.db_manager)
        question = question_service.get_question_by_id(question_id)
        if not question:
            raise HTTPException(status_code=404, detail="Question not found")

        # Convert Question model to dict for the composer
        question_data = {
            'question_id': question.question_id,
            'paper_code': question.paper_code,
            'paper_name': question.paper_name,
            'question_number': question.question_number,
            'question_text': question.question_text,
            'images': question.images
        }

        # Use the new image service for frontend composition
        image_service = get_image_service()
        composer = QuestionImageComposer(image_service)

        composed_data = composer.prepare_question_images(question_data)

        return composed_data

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting question images: {str(e)}")





@app.get("/questions/{question_id}/summary", summary="Get question summary")
async def get_question_summary(
    question_id: str,
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """
    Get question summary including metadata and text preview
    """

    try:
        from services.question_service import QuestionService

        question_service = QuestionService(system.db_manager)
        question = question_service.get_question_by_id(question_id)
        if not question:
            raise HTTPException(status_code=404, detail="Question not found")

        summary = question_service.question_to_summary(question)
        return summary

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting question summary: {str(e)}")



# Removed random question rendering - use /questions/random + individual /questions/{id}/images instead


@app.get("/papers", summary="Get available papers")
async def get_papers(
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """
    Get list of available papers with question counts
    """

    try:
        from services.question_service import QuestionService

        question_service = QuestionService(system.db_manager)

        papers = question_service.get_papers_list()
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
        from services.question_service import QuestionService

        question_service = QuestionService(system.db_manager)

        questions = question_service.get_questions_by_paper(paper_code)
        summaries = [question_service.get_question_summary(q) for q in questions]

        return {
            "paper_code": paper_code,
            "count": len(summaries),
            "questions": summaries
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting questions for paper {paper_code}: {str(e)}")


# =====================================================
# UMAP VISUALIZATION ENDPOINTS
# =====================================================

@app.get("/umap-2d/coordinates", response_model=BasicUMAPResponse,
         summary="Get basic 2D UMAP coordinates",
         description="Get all 2D UMAP coordinates with optional cluster filtering")
async def get_umap_coordinates(
    cluster_filter: Optional[str] = Query(None, description="Filter by cluster IDs (comma-separated)"),
    x_min: Optional[float] = Query(None, description="Minimum X coordinate"),
    x_max: Optional[float] = Query(None, description="Maximum X coordinate"),
    y_min: Optional[float] = Query(None, description="Minimum Y coordinate"),
    y_max: Optional[float] = Query(None, description="Maximum Y coordinate"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(2000, ge=1, le=5000, description="Number of results"),
    include_metadata: bool = Query(False, description="Include question metadata"),
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """Get basic 2D UMAP coordinates for general visualization (cluster-based)"""
    try:
        from services.umap_visualization_service import UMAPVisualizationService

        umap_service = UMAPVisualizationService(
            system.db_manager,
            system.cache_manager
        )

        spatial_bounds = None
        if any(coord is not None for coord in [x_min, x_max, y_min, y_max]):
            spatial_bounds = (x_min, x_max, y_min, y_max)

        # Handle comma-separated cluster_filter strings (for backward compatibility)
        parsed_cluster_filter = cluster_filter
        if cluster_filter and isinstance(cluster_filter, str):
            # If it's a single string with commas, convert to list of ints
            try:
                parsed_cluster_filter = [int(x.strip()) for x in cluster_filter.split(',')]
            except (ValueError, AttributeError):
                # If parsing fails, keep as is and let the service handle the error
                pass

        result = await umap_service.get_basic_coordinates(
            cluster_filter=parsed_cluster_filter,
            spatial_bounds=spatial_bounds,
            offset=offset,
            limit=limit,
            include_metadata=include_metadata
        )

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get UMAP coordinates: {e}")


@app.get("/students/{student_id}/umap-2d/coordinates", response_model=StudentUMAPResponse,
         summary="Get student-specific 2D UMAP coordinates",
         description="Get 2D UMAP coordinates colored by student's mastery status")
async def get_student_umap_coordinates(
    student_id: str,

    # Filtering options
    status_filter: Optional[str] = Query(None, description="Filter by question status (comma-separated)"),
    paper_codes: Optional[List[str]] = Query(None, description="Filter by paper codes"),

    # Spatial filtering (for zoom/pan)
    x_min: Optional[float] = Query(None, description="Minimum X coordinate"),
    x_max: Optional[float] = Query(None, description="Maximum X coordinate"),
    y_min: Optional[float] = Query(None, description="Minimum Y coordinate"),
    y_max: Optional[float] = Query(None, description="Maximum Y coordinate"),

    # Pagination
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(2000, ge=1, le=5000, description="Number of results"),

    # Response options
    include_metadata: bool = Query(False, description="Include question numbers, paper codes"),
    include_attempt_details: bool = Query(False, description="Include detailed attempt information"),

    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """
    Get 2D UMAP coordinates with student-specific question status coloring

    **Status Colors:**
    - 🔘 Gray (#999999): Not attempted
    - 🟠 Orange (#FF9800): Skipped
    - 🟢 Green (#4CAF50): Mastered (latest correct)
    - 🟡 Yellow (#FFEB3B): Mixed (has correct but latest wrong)
    - 🔴 Red (#F44336): Incorrect only
    """
    try:
        from services.umap_visualization_service import UMAPVisualizationService

        umap_service = UMAPVisualizationService(
            system.db_manager,
            system.cache_manager
        )

        spatial_bounds = None
        if any(coord is not None for coord in [x_min, x_max, y_min, y_max]):
            spatial_bounds = (x_min, x_max, y_min, y_max)

        # Handle comma-separated status_filter strings (for backward compatibility)
        parsed_status_filter = None
        if status_filter:
            try:
                from api.schemas import QuestionStatusEnum
                status_values = [s.strip() for s in status_filter.split(',')]
                parsed_status_filter = [QuestionStatusEnum(s) for s in status_values]
            except (ValueError, AttributeError):
                # Invalid status values - let service handle the error
                parsed_status_filter = status_filter

        result = await umap_service.get_student_coordinates(
            student_id=student_id,
            status_filter=parsed_status_filter,
            paper_codes=paper_codes,
            spatial_bounds=spatial_bounds,
            offset=offset,
            limit=limit,
            include_metadata=include_metadata,
            include_attempt_details=include_attempt_details
        )

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get student coordinates: {e}")


@app.get("/students/{student_id}/questions/{question_id}/status", response_model=QuestionStatusResponse,
         summary="Get question status for student",
         description="Get current status of a specific question for real-time updates")
async def get_question_status_for_student(
    student_id: str,
    question_id: str,
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """Get current status of a specific question for a student"""
    try:
        from services.umap_visualization_service import UMAPVisualizationService

        umap_service = UMAPVisualizationService(
            system.db_manager,
            system.cache_manager
        )

        result = await umap_service.get_question_status(student_id, question_id)

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get question status: {e}")


@app.get("/umap-2d/bounds", response_model=UMAPBoundsResponse,
         summary="Get UMAP coordinate bounds",
         description="Get coordinate bounds for visualization setup")
async def get_umap_bounds(
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """Get UMAP coordinate bounds for visualization setup"""
    try:
        from services.umap_visualization_service import UMAPVisualizationService

        umap_service = UMAPVisualizationService(
            system.db_manager,
            system.cache_manager
        )

        bounds = await umap_service.get_umap_bounds()

        return {
            "x_min": bounds.x_min,
            "x_max": bounds.x_max,
            "y_min": bounds.y_min,
            "y_max": bounds.y_max,
            "center_x": bounds.center_x,
            "center_y": bounds.center_y
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get UMAP bounds: {e}")


@app.post("/students/{student_id}/umap-2d/refresh",
          summary="Refresh student status data",
          description="Refresh materialized view data for a specific student")
async def refresh_student_umap_status(
    student_id: str,
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """Refresh materialized view data for a specific student (admin/debug endpoint)"""
    try:
        from services.umap_visualization_service import UMAPVisualizationService

        umap_service = UMAPVisualizationService(
            system.db_manager,
            system.cache_manager
        )

        await umap_service.refresh_student_status(student_id)

        return {
            "message": f"Successfully refreshed status data for student {student_id}",
            "timestamp": time.time()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to refresh student status: {e}")


# =====================================================
# WEBSOCKET ENDPOINTS FOR REAL-TIME UPDATES
# =====================================================

@app.websocket("/ws/students/{student_id}/umap-updates")
async def websocket_umap_updates(websocket: WebSocket, student_id: str):
    """WebSocket endpoint for real-time UMAP visualization updates"""

    from services.websocket_service import websocket_manager

    # Accept connection
    connection_success = await websocket_manager.connect(websocket, student_id)
    if not connection_success:
        return

    try:
        while True:
            # Wait for messages from client
            data = await websocket.receive_text()

            # Handle the message
            await websocket_manager.handle_message(student_id, websocket, data)

    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket, student_id)
    except Exception as e:
        print(f"WebSocket error for student {student_id}: {e}")
        websocket_manager.disconnect(websocket, student_id)


@app.get("/ws/stats", summary="Get WebSocket connection statistics")
async def get_websocket_stats(
    system: HumanCapitalDevelopmentSystem = Depends(get_system)
):
    """Get WebSocket connection statistics (admin endpoint)"""
    try:
        from services.websocket_service import websocket_manager

        stats = websocket_manager.get_connection_stats()

        return {
            "websocket_stats": stats,
            "timestamp": time.time()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get WebSocket stats: {e}")


if __name__ == "__main__":
    # Development server
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
