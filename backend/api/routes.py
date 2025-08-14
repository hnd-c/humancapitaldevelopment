#!/usr/bin/env python3
"""
FastAPI Server for Human Capital Development System
Provides REST API endpoints for the ML-powered recommendation system
"""

import os
import time
import asyncio
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
import uvicorn
import base64

# Import our system components
from main import HumanCapitalDevelopmentSystem
from config.environments import load_config_for_environment


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

# CORS middleware
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
        question_details = system.vector_ops.get_question_embeddings(question_id)

        if not question_details:
            raise HTTPException(status_code=404, detail="Question not found")

        return question_details

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
        # Get question embeddings
        question_embeddings = system.vector_ops.get_question_embeddings(question_id)
        if not question_embeddings:
            raise HTTPException(status_code=404, detail="Question not found")

        # Find similar questions using multimodal similarity
        similar_questions = system.vector_ops.find_similar_questions_multimodal(
            openai_embedding=question_embeddings.get('openai_embedding'),
            umap_embedding=question_embeddings.get('umap_embedding'),
            cluster_vector=question_embeddings.get('soft_cluster'),
            top_k=top_k
        )

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
