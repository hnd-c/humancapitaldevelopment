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
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

# Import our system components
from main_system import HumanCapitalDevelopmentSystem, create_default_config, SystemConfig


# Global system instance
system: Optional[HumanCapitalDevelopmentSystem] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan"""
    global system

    print("🚀 Starting Human Capital Development API Server...")

    # Initialize system
    config = create_default_config()
    system = HumanCapitalDevelopmentSystem(config)

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


if __name__ == "__main__":
    # Development server
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
