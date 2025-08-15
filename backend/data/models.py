#!/usr/bin/env python3
"""
Data Models - Define data structures and schemas

This module handles:
- Data models for questions, students, recommendations
- Validation schemas
- Database entity definitions
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime


@dataclass
class Question:
    """Question data model"""
    internal_question_id: int
    question_id: str
    paper_id: int
    paper_name: str
    paper_code: str
    question_text: Optional[str] = None
    images: Optional[List[str]] = None
    question_number: Optional[int] = None
    openai_embedding: Optional[List[float]] = None
    umap_embedding: Optional[List[float]] = None
    soft_cluster: Optional[List[float]] = None
    text_length: Optional[int] = None
    embedding_model: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class Student:
    """Student data model"""
    student_id: int
    student_name: str
    student_code: str
    institution_id: int
    department_id: int
    year_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class StudentQuestionHistory:
    """Student question attempt history"""
    history_id: int
    enrollment_id: int
    internal_question_id: int
    status: str
    is_correct: bool
    is_skipped: bool
    time_spent_sec: int
    confidence_level: int
    device_type: str
    timestamp: datetime
    created_at: Optional[datetime] = None


@dataclass
class Recommendation:
    """Recommendation data model"""
    question_id: str
    internal_question_id: int
    paper_id: int
    weighted_score: float
    dominant_cluster: int
    similarity_score: Optional[float] = None
    combined_score: Optional[float] = None
    reasoning: Optional[str] = None


@dataclass
class StudentPerformance:
    """Student performance analysis"""
    student_id: str
    total_attempts: int
    overall_success_rate: float
    cluster_performance: Dict[str, Any]
    recent_activity: List[Dict[str, Any]]
    analysis_timestamp: float
    strengths: Optional[List[str]] = None
    weaknesses: Optional[List[str]] = None


@dataclass
class SystemConfig:
    """System configuration data model"""
    # Database configuration
    db_config: Dict[str, Any]
    redis_config: Dict[str, Any]

    # ML configuration
    use_multimodal_embeddings: bool = True
    cache_ttl_seconds: int = 600
    default_similarity_threshold: float = 0.7

    # Performance configuration
    max_concurrent_users: int = 1000
    enable_performance_monitoring: bool = True
    debug_mode: bool = False


@dataclass
class CacheKey:
    """Cache key structure for Redis"""
    key_type: str  # 'embeddings', 'similarities', 'profile', 'recommendations'
    entity_id: str
    additional_params: Optional[str] = None

    def to_string(self) -> str:
        """Convert to Redis key string"""
        if self.additional_params:
            return f"{self.key_type}:{self.entity_id}:{self.additional_params}"
        return f"{self.key_type}:{self.entity_id}"


@dataclass
class RecommendationRequest:
    """Recommendation request schema"""
    student_id: str
    objective: str = "balanced"
    top_k: int = 5
    use_cache: bool = True
    similarity_threshold: float = 0.7
    diversity_filter: bool = True


@dataclass
class RecommendationResponse:
    """Recommendation response schema"""
    student_id: str
    objective: str
    recommendations: List[Recommendation]
    generated_at: float
    cache_hit: bool = False
    response_time_ms: float = 0.0
    metadata: Optional[Dict[str, Any]] = None


class ValidationError(Exception):
    """Custom validation error"""
    pass


class ModelValidator:
    """Validates data models"""

    @staticmethod
    def validate_question(question: Question) -> bool:
        """Validate question data model"""
        if not question.question_id:
            raise ValidationError("Question ID is required")

        if question.soft_cluster and len(question.soft_cluster) == 0:
            raise ValidationError("Soft cluster cannot be empty if provided")

        if question.openai_embedding and len(question.openai_embedding) == 0:
            raise ValidationError("OpenAI embedding cannot be empty if provided")

        return True

    @staticmethod
    def validate_student(student: Student) -> bool:
        """Validate student data model"""
        if not student.student_code:
            raise ValidationError("Student code is required")

        if student.student_id <= 0:
            raise ValidationError("Student ID must be positive")

        return True

    @staticmethod
    def validate_recommendation_request(request: RecommendationRequest) -> bool:
        """Validate recommendation request"""
        valid_objectives = ['balanced', 'coverage', 'efficiency', 'success_rate']
        if request.objective not in valid_objectives:
            raise ValidationError(f"Objective must be one of: {valid_objectives}")

        if request.top_k <= 0 or request.top_k > 50:
            raise ValidationError("top_k must be between 1 and 50")

        if not (0 <= request.similarity_threshold <= 1):
            raise ValidationError("Similarity threshold must be between 0 and 1")

        return True


def convert_db_row_to_question(row: Dict[str, Any]) -> Question:
    """Convert database row to Question model"""
    return Question(
        internal_question_id=row['internal_question_id'],
        question_id=row['question_id'],
        paper_id=row['paper_id'],
        paper_name=row.get('paper_name', ''),
        paper_code=row.get('paper_code', ''),
        question_text=row.get('question_text'),
        images=row.get('images', []),
        question_number=row.get('question_number'),
        openai_embedding=row.get('openai_embedding'),
        umap_embedding=row.get('umap_embedding'),
        soft_cluster=row.get('soft_cluster'),
        text_length=row.get('text_length'),
        embedding_model=row.get('embedding_model'),
        created_at=row.get('created_at'),
        updated_at=row.get('updated_at')
    )


def convert_db_row_to_recommendation(row: Dict[str, Any]) -> Recommendation:
    """Convert database row to Recommendation model"""
    return Recommendation(
        question_id=row['question_id'],
        internal_question_id=row['internal_question_id'],
        paper_id=row['paper_id'],
        weighted_score=row.get('weighted_score', 0.0),
        dominant_cluster=row.get('dominant_cluster', 0),
        similarity_score=row.get('similarity_score'),
        combined_score=row.get('combined_score'),
        reasoning=row.get('reasoning')
    )
