#!/usr/bin/env python3
"""
Student Service - Database operations for student data with model integration

This module handles:
- Student data retrieval and management
- Student performance analysis
- Learning history tracking
- Proper data model usage and validation
"""

from typing import Dict, List, Any, Optional, Tuple
import time

from data.models import (
    Student, StudentPerformance,
    ModelValidator, ValidationError,
    extract_student_number,
    create_service_logger, handle_service_error, handle_database_error
)
from psycopg2.extras import RealDictCursor


class StudentService:
    """Service for student data operations with proper model integration"""

    def __init__(self, db_manager, cache_service=None):
        self.db_manager = db_manager
        self.cache_service = cache_service
        self.logger = create_service_logger('StudentService')

    def get_student_by_id(self, student_id: str) -> Optional[Student]:
        """Get student information by ID, returns Student model"""
        try:
            # Try cache first
            if self.cache_service:
                cache_key = f"student:{student_id}"
                cached_data = self.cache_service.redis.get(cache_key)
                if cached_data:
                    import json
                    student_dict = json.loads(cached_data)
                    # Convert back to Student model
                    return Student(
                        student_id=student_dict['student_id'],
                        student_name=student_dict['student_name'],
                        student_code=student_dict['student_code'],
                        institution_id=student_dict['institution_id'],
                        department_id=student_dict['department_id'],
                        year_id=student_dict['year_id'],
                        created_at=student_dict.get('created_at'),
                        updated_at=student_dict.get('updated_at')
                    )

            # Extract numeric ID if needed
            numeric_id = extract_student_number(student_id)

            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)

                query = """
                SELECT s.student_id, s.student_name, s.student_code,
                       s.institution_id, s.department_id, s.year_id,
                       s.created_at, s.updated_at
                FROM students s
                WHERE s.student_id = %s
                """

                cursor.execute(query, (numeric_id,))
                result = cursor.fetchone()

                if result:
                    # Create Student model from database result
                    student = Student(
                        student_id=result['student_id'],
                        student_name=result['student_name'],
                        student_code=result['student_code'],
                        institution_id=result['institution_id'],
                        department_id=result['department_id'],
                        year_id=result['year_id'],
                        created_at=result.get('created_at'),
                        updated_at=result.get('updated_at')
                    )

                    # Validate the model
                    try:
                        ModelValidator.validate_student(student)
                    except ValidationError as ve:
                        print(f"Student data validation warning: {ve}")

                    # Cache the result as dict for JSON serialization
                    if self.cache_service:
                        import json
                        cache_key = f"student:{student_id}"
                        student_dict = {
                            'student_id': student.student_id,
                            'student_name': student.student_name,
                            'student_code': student.student_code,
                            'institution_id': student.institution_id,
                            'department_id': student.department_id,
                            'year_id': student.year_id,
                            'created_at': str(student.created_at) if student.created_at else None,
                            'updated_at': str(student.updated_at) if student.updated_at else None
                        }
                        self.cache_service.redis.setex(
                            cache_key, 3600, json.dumps(student_dict, default=str)
                        )

                    return student

                return None

        except Exception as e:
            return handle_service_error(self.logger, f"get_student_by_id for {student_id}", e)

    def analyze_student_performance(self, student_id: str) -> Optional[StudentPerformance]:
        """Comprehensive student performance analysis, returns StudentPerformance model"""
        try:
            # Get student history
            history = self.get_student_history(student_id, limit=1000)

            if not history:
                # Return empty performance model
                return StudentPerformance(
                    student_id=student_id,
                    total_attempts=0,
                    overall_success_rate=0.0,
                    cluster_performance={},
                    recent_activity=[],
                    analysis_timestamp=time.time(),
                    strengths=["No data available"],
                    weaknesses=["Insufficient attempts to analyze"]
                )

            # Basic statistics
            total_attempts = len(history)
            correct_attempts = sum(1 for h in history if h.get('is_correct', False))
            overall_success_rate = correct_attempts / total_attempts if total_attempts > 0 else 0

            # Cluster-based performance analysis
            cluster_performance = self._analyze_cluster_performance(history)

            # Recent activity (last 10 attempts)
            recent_activity = history[:10] if len(history) >= 10 else history

            # Time-based analysis
            time_analysis = self._analyze_time_patterns(history)

            # Identify strengths and weaknesses
            strengths, weaknesses = self._identify_strengths_weaknesses(
                cluster_performance, time_analysis, overall_success_rate
            )

            # Create StudentPerformance model
            performance = StudentPerformance(
                student_id=student_id,
                total_attempts=total_attempts,
                overall_success_rate=overall_success_rate,
                cluster_performance=cluster_performance,
                recent_activity=recent_activity,
                analysis_timestamp=time.time(),
                strengths=strengths,
                weaknesses=weaknesses
            )

            # Cache the performance analysis as dict
            if self.cache_service:
                import json
                cache_key = f"performance:{student_id}"
                performance_dict = {
                    "student_id": performance.student_id,
                    "total_attempts": performance.total_attempts,
                    "overall_success_rate": performance.overall_success_rate,
                    "cluster_performance": performance.cluster_performance,
                    "recent_activity": performance.recent_activity,
                    "analysis_timestamp": performance.analysis_timestamp,
                    "strengths": performance.strengths,
                    "weaknesses": performance.weaknesses
                }
                self.cache_service.redis.setex(
                    cache_key, 1800,  # 30 minutes
                    json.dumps(performance_dict, default=str)
                )

            return performance

        except Exception as e:
            self.logger.error(f"analyze_student_performance for {student_id} failed: {str(e)}", exc_info=True)
            # Return error performance model with proper logging
            return StudentPerformance(
                student_id=student_id,
                total_attempts=0,
                overall_success_rate=0.0,
                cluster_performance={"error": str(e)},
                recent_activity=[],
                analysis_timestamp=time.time(),
                strengths=[],
                weaknesses=["Analysis failed"]
            )

    def get_student_history(self, student_id: str, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get student question history"""
        try:
            # Extract numeric ID if needed
            numeric_id = extract_student_number(student_id)

            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)

                query = """
                SELECT sqh.*, q.question_id
                FROM student_question_history sqh
                JOIN student_paper_enrollments spe ON sqh.enrollment_id = spe.enrollment_id
                JOIN questions q ON sqh.internal_question_id = q.internal_question_id
                WHERE spe.student_id = %s
                ORDER BY sqh.timestamp DESC
                LIMIT %s
                """

                cursor.execute(query, (numeric_id, limit))
                results = cursor.fetchall()

                return [dict(row) for row in results]

        except Exception as e:
            return handle_database_error(self.logger, f"get_student_history for {student_id}", e)

# Removed _extract_student_number - now using centralized extract_student_number from data.models

    def _identify_strengths_weaknesses(self, cluster_performance: Dict[str, Any],
                                     time_analysis: Dict[str, Any],
                                     overall_success_rate: float) -> Tuple[List[str], List[str]]:
        """Identify student strengths and weaknesses from performance data"""
        strengths = []
        weaknesses = []

        try:
            # Analyze overall performance
            if overall_success_rate >= 0.8:
                strengths.append("High overall accuracy (80%+)")
            elif overall_success_rate <= 0.5:
                weaknesses.append("Low overall accuracy (50% or below)")

            # Analyze cluster performance
            if cluster_performance:
                strong_clusters = []
                weak_clusters = []

                for cluster_id, perf in cluster_performance.items():
                    if isinstance(perf, dict) and 'success_rate' in perf:
                        success_rate = perf['success_rate']
                        if success_rate >= 0.8 and perf.get('total_attempts', 0) >= 3:
                            strong_clusters.append(f"Cluster {cluster_id}")
                        elif success_rate <= 0.4 and perf.get('total_attempts', 0) >= 3:
                            weak_clusters.append(f"Cluster {cluster_id}")

                if strong_clusters:
                    strengths.append(f"Strong performance in: {', '.join(strong_clusters[:3])}")
                if weak_clusters:
                    weaknesses.append(f"Needs improvement in: {', '.join(weak_clusters[:3])}")

            # Analyze time patterns
            avg_time = time_analysis.get('avg_time_seconds', 0)
            if avg_time > 0:
                if avg_time < 30:  # Fast completion
                    strengths.append("Quick problem solving")
                elif avg_time > 300:  # More than 5 minutes
                    weaknesses.append("Slow problem solving pace")

            # Default messages if no specific patterns found
            if not strengths:
                strengths.append("Consistent learning engagement")
            if not weaknesses and overall_success_rate < 0.7:
                weaknesses.append("Room for improvement in accuracy")

        except Exception as e:
            print(f"Error identifying strengths/weaknesses: {e}")
            strengths = ["Analysis incomplete"]
            weaknesses = ["Unable to determine"]

        return strengths, weaknesses

    def _analyze_time_patterns(self, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze time-based learning patterns"""
        if not history:
            return {}

        try:
            # Calculate average time spent
            times = []
            for record in history:
                time_spent = record.get('time_spent_sec', 0)
                if time_spent and time_spent > 0:
                    times.append(float(time_spent))

            if times:
                avg_time = sum(times) / len(times)
                return {
                    'avg_time_seconds': avg_time,
                    'min_time': min(times),
                    'max_time': max(times),
                    'total_records_with_time': len(times)
                }
            else:
                return {'avg_time_seconds': 0, 'no_time_data': True}

        except Exception as e:
            print(f"Error analyzing time patterns: {e}")
            return {}

    def _analyze_cluster_performance(self, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze performance by topic clusters"""
        if not history:
            return {}

        # Get cluster information for the questions in this history
        question_ids = [record.get('internal_question_id') for record in history if record.get('internal_question_id')]
        if not question_ids:
            return {}

        cluster_stats = {}

        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)

                # Get cluster information for the questions
                placeholders = ','.join(['%s'] * len(question_ids))
                query = f"""
                SELECT internal_question_id, soft_cluster
                FROM questions
                WHERE internal_question_id IN ({placeholders})
                AND soft_cluster IS NOT NULL
                """

                cursor.execute(query, question_ids)
                results = cursor.fetchall()

                # Calculate dominant cluster in Python
                cluster_mapping = {}
                for row in results:
                    question_id = row['internal_question_id']
                    soft_cluster = row['soft_cluster']

                    # Convert vector string to list and find max index
                    try:
                        if isinstance(soft_cluster, str):
                            import ast
                            cluster_probs = ast.literal_eval(soft_cluster)
                        else:
                            cluster_probs = soft_cluster

                        # Find index of maximum probability
                        dominant_cluster = cluster_probs.index(max(cluster_probs))
                        cluster_mapping[question_id] = dominant_cluster

                    except Exception as e:
                        print(f"Warning: Could not parse cluster for question {question_id}: {e}")

        except Exception as e:
            print(f"Error fetching cluster information: {e}")
            return {}

        # Analyze performance by cluster
        for record in history:
            question_id = record.get('internal_question_id')
            if question_id and question_id in cluster_mapping:
                dominant_cluster = cluster_mapping[question_id]

                if dominant_cluster not in cluster_stats:
                    cluster_stats[dominant_cluster] = {'total': 0, 'correct': 0, 'time_sum': 0}

                cluster_stats[dominant_cluster]['total'] += 1
                # Ensure time_spent_sec is numeric
                time_spent = record.get('time_spent_sec', 0)
                try:
                    time_spent = float(time_spent) if time_spent is not None else 0.0
                except (ValueError, TypeError):
                    time_spent = 0.0
                cluster_stats[dominant_cluster]['time_sum'] += time_spent
                if record['is_correct']:
                    cluster_stats[dominant_cluster]['correct'] += 1

        # Calculate metrics - ensure string keys for Pydantic
        cluster_performance = {}
        for cluster_id, stats in cluster_stats.items():
            cluster_performance[str(cluster_id)] = {
                'success_rate': stats['correct'] / stats['total'] if stats['total'] > 0 else 0,
                'avg_time': stats['time_sum'] / stats['total'] if stats['total'] > 0 else 0,
                'total_attempts': stats['total']
            }

        return cluster_performance