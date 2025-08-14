#!/usr/bin/env python3
"""
API Schemas - Request/response models for the REST API

This module handles:
- Pydantic models for API validation
- Request/response schemas
- API data transformation
"""

from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class ObjectiveType(str, Enum):
    """Valid learning objectives"""
    BALANCED = "balanced"
    COVERAGE = "coverage"
    EFFICIENCY = "efficiency"
    SUCCESS_RATE = "success_rate"


class RecommendationRequest(BaseModel):
    """Request schema for getting recommendations"""
    student_id: str = Field(..., description="Student identifier")
    objective: ObjectiveType = Field(default=ObjectiveType.BALANCED, description="Learning objective")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of recommendations to return")
    use_cache: bool = Field(default=True, description="Whether to use cached results")
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Minimum similarity threshold")
    diversity_filter: bool = Field(default=True, description="Apply diversity filtering to recommendations")

    @validator('student_id')
    def validate_student_id(cls, v):
        if not v or not v.strip():
            raise ValueError('Student ID cannot be empty')
        return v.strip()


class QuestionRecommendation(BaseModel):
    """Individual question recommendation"""
    question_id: str = Field(..., description="Question identifier")
    internal_question_id: int = Field(..., description="Internal question ID")
    paper_id: int = Field(..., description="Paper ID")
    paper_name: Optional[str] = Field(None, description="Paper name")
    paper_code: Optional[str] = Field(None, description="Paper code")
    weighted_score: float = Field(..., description="Cluster-based weighted score")
    dominant_cluster: int = Field(..., description="Primary cluster for this question")
    similarity_score: Optional[float] = Field(None, description="Similarity score to current question")
    combined_score: Optional[float] = Field(None, description="Combined weighted and similarity score")
    reasoning: Optional[str] = Field(None, description="Explanation for recommendation")


class RecommendationResponse(BaseModel):
    """Response schema for recommendations"""
    student_id: str
    objective: ObjectiveType
    recommendations: List[QuestionRecommendation]
    generated_at: float = Field(..., description="Unix timestamp when generated")
    cache_hit: bool = Field(default=False, description="Whether result came from cache")
    response_time_ms: float = Field(default=0.0, description="Response time in milliseconds")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class StudentHistoryRequest(BaseModel):
    """Request schema for student history"""
    limit: int = Field(default=100, ge=1, le=1000, description="Maximum number of records")
    include_embeddings: bool = Field(default=False, description="Include question embeddings")
    start_date: Optional[datetime] = Field(None, description="Start date filter")
    end_date: Optional[datetime] = Field(None, description="End date filter")


class StudentHistoryRecord(BaseModel):
    """Individual student history record"""
    history_id: int
    question_id: str
    paper_name: str
    paper_code: str
    status: str
    is_correct: bool
    is_skipped: bool
    time_spent_sec: int
    confidence_level: int
    device_type: str
    timestamp: datetime
    openai_embedding: Optional[List[float]] = None
    soft_cluster: Optional[List[float]] = None


class StudentHistoryResponse(BaseModel):
    """Response schema for student history"""
    student_id: str
    history_count: int
    total_attempts: int
    success_rate: float
    history: List[StudentHistoryRecord]


# Student Workflow Schemas
class QuestionAttemptRequest(BaseModel):
    """Request to start attempting a question"""
    student_id: str
    question_id: str
    started_at: Optional[float] = None  # Unix timestamp

class QuestionAttemptResponse(BaseModel):
    """Response when starting a question attempt"""
    attempt_id: str
    student_id: str
    question_id: str
    question_data: Dict[str, Any]
    started_at: float
    status: str = "in_progress"

class AnswerSubmissionRequest(BaseModel):
    """Request to submit an answer"""
    attempt_id: str
    student_id: str
    question_id: str
    answer_text: Optional[str] = None
    selected_option: Optional[str] = None
    is_correct: Optional[bool] = None
    confidence_level: Optional[float] = None  # 0.0 to 1.0
    time_spent_seconds: Optional[float] = None
    submission_method: Optional[str] = "manual"  # manual, auto_submit, timeout
    metadata: Optional[Dict[str, Any]] = {}

class AnswerSubmissionResponse(BaseModel):
    """Response after submitting an answer"""
    submission_id: str
    student_id: str
    question_id: str
    is_correct: bool
    time_spent_seconds: float
    submitted_at: float
    feedback: Optional[str] = None
    cache_invalidated: bool = True
    next_recommendations_available: bool = True

class StudentSessionRequest(BaseModel):
    """Request to start a learning session"""
    student_id: str
    objective: str = "balanced"
    session_type: str = "practice"  # practice, assessment, review
    target_questions: Optional[int] = 10

class StudentSessionResponse(BaseModel):
    """Response when starting a learning session"""
    session_id: str
    student_id: str
    objective: str
    session_type: str
    recommendations: List[Dict[str, Any]]
    session_started_at: float
    estimated_duration_minutes: Optional[int] = None


class ClusterPerformance(BaseModel):
    """Performance metrics for a topic cluster"""
    cluster_id: int
    success_rate: float = Field(..., ge=0.0, le=1.0)
    avg_time: float = Field(..., ge=0.0)
    avg_confidence: float = Field(..., ge=1.0, le=5.0)
    total_attempts: int = Field(..., ge=0)


class PerformanceAnalysisResponse(BaseModel):
    """Response schema for student performance analysis"""
    student_id: str
    total_attempts: int
    overall_success_rate: float = Field(..., ge=0.0, le=1.0)
    cluster_performance: Dict[str, ClusterPerformance]
    recent_activity: List[StudentHistoryRecord]
    analysis_timestamp: float
    time_patterns: Optional[Dict[str, Any]] = None
    learning_progression: Optional[Dict[str, Any]] = None
    strengths: Optional[List[str]] = None
    weaknesses: Optional[List[str]] = None


class QuestionDetails(BaseModel):
    """Detailed question information"""
    internal_question_id: int
    question_id: str
    paper_id: int
    paper_name: Optional[str] = None
    paper_code: Optional[str] = None
    question_text: Optional[str] = None
    text_length: Optional[int] = None
    embedding_model: Optional[str] = None
    dominant_cluster: Optional[int] = None
    cluster_distribution: Optional[List[float]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SimilarQuestionRequest(BaseModel):
    """Request schema for finding similar questions"""
    top_k: int = Field(default=10, ge=1, le=50, description="Number of similar questions to return")
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Minimum similarity score")
    include_embeddings: bool = Field(default=False, description="Include embedding vectors")
    cluster_weight: float = Field(default=0.2, ge=0.0, le=1.0, description="Weight for cluster similarity")
    embedding_weight: float = Field(default=0.8, ge=0.0, le=1.0, description="Weight for embedding similarity")

    @validator('cluster_weight', 'embedding_weight')
    def validate_weights(cls, v, values):
        if 'cluster_weight' in values:
            if abs(v + values['cluster_weight'] - 1.0) > 0.01:
                raise ValueError('Cluster weight and embedding weight must sum to 1.0')
        return v


class SimilarQuestion(BaseModel):
    """Similar question with similarity score"""
    question_id: str
    internal_question_id: int
    paper_name: Optional[str] = None
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    embedding_similarity: Optional[float] = None
    cluster_similarity: Optional[float] = None
    dominant_cluster: Optional[int] = None


class SimilarQuestionsResponse(BaseModel):
    """Response schema for similar questions"""
    question_id: str
    similar_questions: List[SimilarQuestion]
    similarity_threshold: float
    total_found: int
    computation_time_ms: float


class HealthStatus(str, Enum):
    """System health status values"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ComponentStatus(BaseModel):
    """Individual component status"""
    status: str
    details: Optional[str] = None
    last_check: datetime
    response_time_ms: Optional[float] = None


class HealthResponse(BaseModel):
    """System health check response"""
    status: HealthStatus
    timestamp: float
    uptime_seconds: float
    components: Dict[str, ComponentStatus]
    system_metrics: Optional[Dict[str, Any]] = None
    total_questions: Optional[int] = None
    total_students: Optional[int] = None


class CacheInvalidationRequest(BaseModel):
    """Request schema for cache invalidation"""
    student_id: Optional[str] = Field(None, description="Specific student ID to invalidate")
    cache_types: Optional[List[str]] = Field(None, description="Specific cache types to invalidate")
    pattern: Optional[str] = Field(None, description="Redis key pattern to match")
    confirm_all: bool = Field(default=False, description="Confirm invalidating all caches")


class CacheInvalidationResponse(BaseModel):
    """Response schema for cache invalidation"""
    message: str
    keys_invalidated: int
    cache_types_affected: List[str]
    operation_time_ms: float


class SystemAnalyticsResponse(BaseModel):
    """Response schema for system analytics"""
    timestamp: float
    health: HealthResponse
    performance_metrics: Optional[Dict[str, Any]] = None
    database_stats: Dict[str, Any]
    cache_stats: Dict[str, Any]
    recent_activity: List[Dict[str, Any]]
    user_metrics: Optional[Dict[str, Any]] = None


class MigrationRequest(BaseModel):
    """Request schema for data migration"""
    source_type: str = Field(default="parquet", description="Source data type")
    force_rebuild: bool = Field(default=False, description="Force rebuild of existing data")
    batch_size: int = Field(default=1000, ge=100, le=10000, description="Processing batch size")
    validate_data: bool = Field(default=True, description="Validate data integrity")


class MigrationResponse(BaseModel):
    """Response schema for migration status"""
    message: str
    migration_id: Optional[str] = None
    estimated_duration: Optional[str] = None
    status: str


class ErrorResponse(BaseModel):
    """Standard error response schema"""
    error: str
    detail: Optional[str] = None
    error_code: Optional[str] = None
    timestamp: float
    request_id: Optional[str] = None


class ValidationErrorDetail(BaseModel):
    """Detailed validation error information"""
    field: str
    message: str
    invalid_value: Any


class ValidationErrorResponse(ErrorResponse):
    """Validation error response with details"""
    validation_errors: List[ValidationErrorDetail]


# Custom validators and transformers
def transform_db_history_to_schema(db_records: List[Dict[str, Any]]) -> List[StudentHistoryRecord]:
    """Transform database history records to schema models"""
    return [
        StudentHistoryRecord(
            history_id=record['history_id'],
            question_id=record['question_id'],
            paper_name=record.get('paper_name', ''),
            paper_code=record.get('paper_code', ''),
            status=record['status'],
            is_correct=record['is_correct'],
            is_skipped=record['is_skipped'],
            time_spent_sec=record['time_spent_sec'],
            confidence_level=record['confidence_level'],
            device_type=record['device_type'],
            timestamp=record['timestamp'],
            openai_embedding=record.get('openai_embedding'),
            soft_cluster=record.get('soft_cluster')
        )
        for record in db_records
    ]


def transform_db_recommendations_to_schema(db_records: List[Dict[str, Any]]) -> List[QuestionRecommendation]:
    """Transform database recommendation records to schema models"""
    return [
        QuestionRecommendation(
            question_id=record['question_id'],
            internal_question_id=record['internal_question_id'],
            paper_id=record['paper_id'],
            paper_name=record.get('paper_name'),
            paper_code=record.get('paper_code'),
            weighted_score=record.get('weighted_score', 0.0),
            dominant_cluster=record.get('dominant_cluster', 0),
            similarity_score=record.get('similarity_score'),
            combined_score=record.get('combined_score'),
            reasoning=record.get('reasoning')
        )
        for record in db_records
    ]
