#!/usr/bin/env python3
"""
UMAP Visualization Service - Student-specific 2D visualization management

This service handles:
- Student-specific UMAP coordinate retrieval
- Real-time status updates
- Spatial filtering and optimization
- Cache management for visualization data
"""

import time
import json
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

from data.database_manager import DatabaseManager
from services.cache_service import CacheService


class QuestionStatus(str, Enum):
    """Question status enumeration for visualization"""
    NOT_ATTEMPTED = "not_attempted"
    SKIPPED = "skipped"
    MASTERED = "mastered"
    MIXED = "mixed"
    INCORRECT = "incorrect"


@dataclass
class UMAPBounds:
    """UMAP coordinate bounds for visualization"""
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    center_x: float
    center_y: float


@dataclass
class QuestionPoint:
    """Individual question point data"""
    question_id: str
    x_coord: float
    y_coord: float
    status: QuestionStatus
    color_code: str
    attempt_count: int
    correct_count: int
    latest_attempt_time: Optional[datetime] = None
    latest_confidence: Optional[int] = None

    # Optional metadata
    question_number: Optional[int] = None
    paper_code: Optional[str] = None
    text_preview: Optional[str] = None
    time_spent_total: Optional[float] = None


class UMAPVisualizationService:
    """Service for UMAP visualization and student progress tracking"""

    # Color constants for consistent mapping
    STATUS_COLORS = {
        QuestionStatus.NOT_ATTEMPTED: "#999999",  # Gray
        QuestionStatus.SKIPPED: "#FF9800",       # Orange
        QuestionStatus.MASTERED: "#4CAF50",      # Green
        QuestionStatus.MIXED: "#FFEB3B",         # Yellow
        QuestionStatus.INCORRECT: "#F44336"      # Red
    }

    STATUS_LABELS = {
        QuestionStatus.NOT_ATTEMPTED: "Not Attempted",
        QuestionStatus.SKIPPED: "Skipped",
        QuestionStatus.MASTERED: "Mastered",
        QuestionStatus.MIXED: "In Progress",
        QuestionStatus.INCORRECT: "Incorrect"
    }

    def __init__(self, db_manager: DatabaseManager, cache_service: CacheService = None):
        self.db_manager = db_manager
        self.cache_service = cache_service

    async def get_student_coordinates(
        self,
        student_id: str,
        status_filter: Optional[List[QuestionStatus]] = None,
        paper_codes: Optional[List[str]] = None,
        spatial_bounds: Optional[Tuple[float, float, float, float]] = None,  # x_min, x_max, y_min, y_max
        offset: int = 0,
        limit: int = 2000,
        include_metadata: bool = False,
        include_attempt_details: bool = False
    ) -> Dict[str, Any]:
        """
        Get student-specific UMAP coordinates with filtering and pagination

        Args:
            student_id: Student identifier
            status_filter: Filter by question statuses
            paper_codes: Filter by specific paper codes
            spatial_bounds: Spatial filtering (x_min, x_max, y_min, y_max)
            offset: Pagination offset
            limit: Number of results to return
            include_metadata: Include question metadata
            include_attempt_details: Include detailed attempt information

        Returns:
            Dictionary with coordinates, pagination info, and statistics
        """

        # Build cache key
        cache_params = [
            student_id, offset, limit,
            str(sorted(status_filter or [])),
            str(sorted(paper_codes or [])),
            str(spatial_bounds),
            str(include_metadata),
            str(include_attempt_details)
        ]
        cache_key = f"student_umap:{':'.join(str(p) for p in cache_params)}"

        # Try cache first
        if self.cache_service:
            try:
                cached_value = self.cache_service.redis.get(cache_key)
                if cached_value:
                    return json.loads(cached_value)
            except Exception as e:
                print(f"Cache lookup failed: {e}")

        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=self.db_manager.RealDictCursor)

                # Build dynamic SELECT fields
                select_fields = [
                    "sqs.question_id", "sqs.x_coord", "sqs.y_coord",
                    "sqs.status", "sqs.color_code", "sqs.attempt_count",
                    "sqs.correct_count", "sqs.latest_attempt_time", "sqs.latest_confidence"
                ]

                if include_metadata:
                    select_fields.extend([
                        "sqs.question_number", "sqs.paper_code", "sqs.paper_name", "sqs.text_preview"
                    ])

                if include_attempt_details:
                    select_fields.extend([
                        "sqs.total_time_spent", "sqs.avg_confidence",
                        "sqs.skipped_count", "sqs.latest_time_spent"
                    ])

                # Build WHERE conditions
                conditions = ["sqs.student_id = %s"]
                params = [student_id]

                # Status filter
                if status_filter:
                    status_placeholders = ','.join(['%s'] * len(status_filter))
                    conditions.append(f"sqs.status IN ({status_placeholders})")
                    params.extend([status.value for status in status_filter])

                # Paper filter
                if paper_codes:
                    paper_placeholders = ','.join(['%s'] * len(paper_codes))
                    conditions.append(f"sqs.paper_code IN ({paper_placeholders})")
                    params.extend(paper_codes)

                # Spatial bounds
                if spatial_bounds:
                    x_min, x_max, y_min, y_max = spatial_bounds
                    if x_min is not None:
                        conditions.append("sqs.x_coord >= %s")
                        params.append(x_min)
                    if x_max is not None:
                        conditions.append("sqs.x_coord <= %s")
                        params.append(x_max)
                    if y_min is not None:
                        conditions.append("sqs.y_coord >= %s")
                        params.append(y_min)
                    if y_max is not None:
                        conditions.append("sqs.y_coord <= %s")
                        params.append(y_max)

                where_clause = "WHERE " + " AND ".join(conditions)

                # Main query
                query = f"""
                    SELECT {', '.join(select_fields)}
                    FROM student_question_status sqs
                    {where_clause}
                    ORDER BY sqs.question_id
                    LIMIT %s OFFSET %s
                """

                params.extend([limit, offset])
                cursor.execute(query, params)
                coordinates = [dict(row) for row in cursor.fetchall()]

                # Get total count
                count_query = f"""
                    SELECT COUNT(*)
                    FROM student_question_status sqs
                    {where_clause}
                """
                cursor.execute(count_query, params[:-2])  # Exclude limit/offset
                count_result = cursor.fetchone()
                total_count = count_result['count'] if count_result else 0

                # Get status distribution for this student
                status_distribution = await self._get_status_distribution(student_id, cursor)

                result = {
                    "student_id": student_id,
                    "coordinates": coordinates,
                    "pagination": {
                        "offset": offset,
                        "limit": limit,
                        "total": total_count,
                        "has_more": offset + limit < total_count
                    },
                    "status_distribution": status_distribution,
                    "status_legend": {
                        status.value: {
                            "color": self.STATUS_COLORS[status],
                            "label": self.STATUS_LABELS[status]
                        }
                        for status in QuestionStatus
                    },
                    "retrieved_at": time.time()
                }

                # Cache for 2 minutes (shorter TTL due to dynamic nature)
                if self.cache_service:
                    try:
                        self.cache_service.redis.setex(cache_key, 120, json.dumps(result, default=str))
                    except Exception as e:
                        print(f"Cache set failed: {e}")

                return result

        except Exception as e:
            raise Exception(f"Failed to get student coordinates: {e}")

    async def get_basic_coordinates(
        self,
        cluster_filter: Optional[List[int]] = None,
        spatial_bounds: Optional[Tuple[float, float, float, float]] = None,
        offset: int = 0,
        limit: int = 2000,
        include_metadata: bool = False
    ) -> Dict[str, Any]:
        """
        Get basic 2D UMAP coordinates (non-student specific) for general visualization

        Args:
            cluster_filter: Filter by cluster IDs
            spatial_bounds: Spatial filtering (x_min, x_max, y_min, y_max)
            offset: Pagination offset
            limit: Number of results to return
            include_metadata: Include question metadata

        Returns:
            Dictionary with coordinates and cluster information
        """

        cache_key = f"basic_umap:{offset}:{limit}:{str(sorted(cluster_filter or []))}:{str(spatial_bounds)}:{include_metadata}"

        # Try cache first
        if self.cache_service:
            try:
                cached_value = self.cache_service.redis.get(cache_key)
                if cached_value:
                    return json.loads(cached_value)
            except Exception as e:
                print(f"Cache lookup failed: {e}")


        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=self.db_manager.RealDictCursor)

                # Build SELECT fields
                select_fields = ["question_id", "x_coord", "y_coord", "cluster_id", "cluster_confidence"]

                if include_metadata:
                    select_fields.extend([
                        "question_number", "paper_code", "paper_name", "text_preview", "text_length"
                    ])

                # Build WHERE conditions
                conditions = []
                params = []

                # Cluster filter
                if cluster_filter:
                    cluster_placeholders = ','.join(['%s'] * len(cluster_filter))
                    conditions.append(f"cluster_id IN ({cluster_placeholders})")
                    params.extend(cluster_filter)

                # Spatial bounds
                if spatial_bounds:
                    x_min, x_max, y_min, y_max = spatial_bounds
                    if x_min is not None:
                        conditions.append("x_coord >= %s")
                        params.append(x_min)
                    if x_max is not None:
                        conditions.append("x_coord <= %s")
                        params.append(x_max)
                    if y_min is not None:
                        conditions.append("y_coord >= %s")
                        params.append(y_min)
                    if y_max is not None:
                        conditions.append("y_coord <= %s")
                        params.append(y_max)

                where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

                # Main query
                query = f"""
                    SELECT {', '.join(select_fields)}
                    FROM question_coordinates_2d
                    {where_clause}
                    ORDER BY question_id
                    LIMIT %s OFFSET %s
                """

                params.extend([limit, offset])
                cursor.execute(query, params)
                coordinates = [dict(row) for row in cursor.fetchall()]

                # Get total count
                count_query = f"""
                    SELECT COUNT(*)
                    FROM question_coordinates_2d
                    {where_clause}
                """
                cursor.execute(count_query, params[:-2])
                count_result = cursor.fetchone()
                total_count = count_result['count'] if count_result else 0

                # Get cluster distribution
                cluster_distribution = {}
                if not cluster_filter:  # Only get all clusters if not filtering
                    cursor.execute("""
                        SELECT cluster_id, COUNT(*) as count
                        FROM question_coordinates_2d
                        GROUP BY cluster_id
                        ORDER BY cluster_id
                    """)
                    cluster_rows = cursor.fetchall()
                    cluster_distribution = {
                        row['cluster_id']: row['count']
                        for row in cluster_rows
                    }

                result = {
                    "coordinates": coordinates,
                    "pagination": {
                        "offset": offset,
                        "limit": limit,
                        "total": total_count,
                        "has_more": offset + limit < total_count
                    },
                    "cluster_distribution": cluster_distribution,
                    "retrieved_at": time.time()
                }

                # Cache for 5 minutes (longer TTL for static data)
                if self.cache_service:
                    try:
                        self.cache_service.redis.setex(cache_key, 300, json.dumps(result, default=str))
                    except Exception as e:
                        print(f"Cache set failed: {e}")

                return result

        except Exception as e:
            raise Exception(f"Failed to get basic coordinates: {e}")

    async def get_question_status(
        self,
        student_id: str,
        question_id: str
    ) -> Dict[str, Any]:
        """Get current status of a specific question for a student"""

        cache_key = f"question_status:{student_id}:{question_id}"

        if self.cache_service:
            try:
                cached_value = self.cache_service.redis.get(cache_key)
                if cached_value:
                    return json.loads(cached_value)
            except Exception as e:
                print(f"Cache lookup failed: {e}")

        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=self.db_manager.RealDictCursor)

                query = """
                    SELECT status, color_code, attempt_count, correct_count,
                           latest_attempt_time, latest_confidence, x_coord, y_coord
                    FROM student_question_status
                    WHERE student_id = %s AND question_id = %s
                """

                cursor.execute(query, [student_id, question_id])
                result = cursor.fetchone()

                if not result:
                    return {
                        "status": QuestionStatus.NOT_ATTEMPTED.value,
                        "color_code": self.STATUS_COLORS[QuestionStatus.NOT_ATTEMPTED]
                    }

                status_data = dict(result)

                # Cache for 1 minute
                if self.cache_service:
                    try:
                        self.cache_service.redis.setex(cache_key, 60, json.dumps(status_data, default=str))
                    except Exception as e:
                        print(f"Cache set failed: {e}")

                return status_data

        except Exception as e:
            raise Exception(f"Failed to get question status: {e}")

    async def get_umap_bounds(self) -> UMAPBounds:
        """Get UMAP coordinate bounds for visualization setup"""

        cache_key = "umap_bounds"

        if self.cache_service:
            try:
                cached_value = self.cache_service.redis.get(cache_key)
                if cached_value:
                    cached_bounds = json.loads(cached_value)
                    return UMAPBounds(**cached_bounds)
            except Exception as e:
                print(f"Cache lookup failed: {e}")

        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("SELECT * FROM get_umap_bounds()")
                bounds_data = cursor.fetchone()

                bounds = UMAPBounds(
                    x_min=bounds_data[0],
                    x_max=bounds_data[1],
                    y_min=bounds_data[2],
                    y_max=bounds_data[3],
                    center_x=bounds_data[4],
                    center_y=bounds_data[5]
                )

                # Cache for 1 hour (bounds don't change often)
                if self.cache_service:
                    bounds_dict = {
                        "x_min": bounds.x_min,
                        "x_max": bounds.x_max,
                        "y_min": bounds.y_min,
                        "y_max": bounds.y_max,
                        "center_x": bounds.center_x,
                        "center_y": bounds.center_y
                    }
                    try:
                        self.cache_service.redis.setex(cache_key, 3600, json.dumps(bounds_dict, default=str))
                    except Exception as e:
                        print(f"Cache set failed: {e}")

                return bounds

        except Exception as e:
            raise Exception(f"Failed to get UMAP bounds: {e}")

    async def refresh_student_status(self, student_id: str):
        """Refresh materialized view data for a specific student"""

        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor()

                # Call the database function to refresh this student's data
                cursor.execute("SELECT refresh_student_status_for_student(%s)", [student_id])
                conn.commit()

                # Invalidate related caches
                if self.cache_service:
                    await self._invalidate_student_caches(student_id)

        except Exception as e:
            raise Exception(f"Failed to refresh student status: {e}")

    async def _get_status_distribution(self, student_id: str, cursor) -> Dict[str, int]:
        """Get status distribution for a student"""

        status_query = """
            SELECT status, COUNT(*) as count
            FROM student_question_status
            WHERE student_id = %s
            GROUP BY status
        """
        cursor.execute(status_query, [student_id])
        return {
            row['status']: row['count']
            for row in cursor.fetchall()
        }

    async def _invalidate_student_caches(self, student_id: str):
        """Invalidate all caches related to a specific student"""

        if not self.cache_service:
            return

        # Invalidate student-specific caches
        cache_patterns = [
            f"student_umap:{student_id}:*",
            f"question_status:{student_id}:*"
        ]

        for pattern in cache_patterns:
            try:
                await self.cache_service.delete_pattern(pattern)
            except Exception as e:
                print(f"Warning: Failed to invalidate cache pattern {pattern}: {e}")
