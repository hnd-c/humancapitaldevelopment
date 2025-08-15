#!/usr/bin/env python3
"""
Student Service - Handle student management and history operations

This module handles:
- Student profile management
- Learning history tracking
- Performance analytics
- Student progress monitoring
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import numpy as np


class StudentService:
    """Service for managing student operations"""

    def __init__(self, db_manager, cache_manager=None):
        self.db_manager = db_manager
        self.cache_manager = cache_manager

    def get_student_profile(self, student_id: int) -> Optional[Dict[str, Any]]:
        """Get comprehensive student profile"""
        try:
            # Check cache first
            if self.cache_manager:
                cached_profile = self.cache_manager.get_cached_profile(str(student_id))
                if cached_profile:
                    return cached_profile

            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=self.db_manager.RealDictCursor)

                # Get student basic info
                cursor.execute("""
                    SELECT s.*, i.institution_name, d.department_name, y.year_name
                    FROM students s
                    JOIN institutions i ON s.institution_id = i.institution_id
                    JOIN departments d ON s.department_id = d.department_id
                    JOIN academic_years y ON s.year_id = y.year_id
                    WHERE s.student_id = %s
                """, (student_id,))

                student_info = cursor.fetchone()
                if not student_info:
                    return None

                # Get performance statistics
                performance_stats = self._get_student_performance_stats(student_id)

                # Get recent activity
                recent_activity = self._get_recent_activity(student_id, limit=10)

                profile = {
                    'student_info': dict(student_info),
                    'performance_stats': performance_stats,
                    'recent_activity': recent_activity,
                    'last_updated': datetime.now().isoformat()
                }

                # Cache the profile
                if self.cache_manager:
                    self.cache_manager.cache_student_profile(str(student_id), profile)

                return profile

        except Exception as e:
            print(f"Error getting student profile for {student_id}: {e}")
            return None

    def get_student_history_detailed(self, student_id: int, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get detailed student learning history"""
        try:
            # Check cache first
            cache_key = f"student_history:{student_id}:{limit}"
            if self.cache_manager:
                cached_history = self.cache_manager.redis.get(cache_key)
                if cached_history:
                    import json
                    return json.loads(cached_history)

            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=self.db_manager.RealDictCursor)

                query = """
                SELECT sqh.*, q.question_id, q.openai_embedding, q.soft_cluster,
                       p.paper_name, p.paper_code
                FROM student_question_history sqh
                JOIN student_paper_enrollments spe ON sqh.enrollment_id = spe.enrollment_id
                JOIN questions q ON sqh.internal_question_id = q.internal_question_id
                JOIN papers p ON q.paper_id = p.paper_id
                WHERE spe.student_id = %s
                ORDER BY sqh.timestamp DESC
                LIMIT %s
                """

                cursor.execute(query, (student_id, limit))
                results = cursor.fetchall()

                # Cache the results
                if self.cache_manager:
                    import json
                    self.cache_manager.redis.setex(cache_key, 300, json.dumps(results, default=str))

                return results

        except Exception as e:
            print(f"Error getting student history for {student_id}: {e}")
            return []

    def analyze_student_learning_patterns(self, student_id: int) -> Dict[str, Any]:
        """Analyze student learning patterns and behaviors"""
        try:
            history = self.get_student_history_detailed(student_id)
            if not history:
                return {"error": "No history found"}

            # Calculate success rate
            correct_attempts = sum(1 for h in history if h.get('is_correct', False))
            overall_success_rate = correct_attempts / len(history) if history else 0.0

            analysis = {
                'student_id': str(student_id),  # Convert to string for schema
                'total_attempts': len(history),
                'overall_success_rate': overall_success_rate,
                'analysis_timestamp': datetime.now().timestamp(),  # Use timestamp float
                'recent_activity': history[-10:] if history else []  # Last 10 activities
            }

            # Time-based patterns
            analysis['time_patterns'] = self._analyze_time_patterns(history)

            # Cluster performance - fix key types
            cluster_perf = self._analyze_cluster_performance(history)
            analysis['cluster_performance'] = {str(k): v for k, v in cluster_perf.items()}

            # Learning progression
            analysis['learning_progression'] = self._analyze_learning_progression(history)

            # Confidence patterns
            analysis['confidence_patterns'] = self._analyze_confidence_patterns(history)

            # Device usage patterns
            analysis['device_patterns'] = self._analyze_device_patterns(history)

            return analysis

        except Exception as e:
            print(f"Error analyzing learning patterns for {student_id}: {e}")
            return {"error": str(e)}

    def get_student_recommendations_history(self, student_id: int, days: int = 30) -> List[Dict[str, Any]]:
        """Get history of recommendations made to student"""
        try:
            # This would require a recommendations_history table
            # For now, return placeholder
            return []

        except Exception as e:
            print(f"Error getting recommendation history for {student_id}: {e}")
            return []

    def update_student_profile(self, student_id: int, updates: Dict[str, Any]) -> bool:
        """Update student profile information"""
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor()

                # Build dynamic update query
                update_fields = []
                values = []

                for field, value in updates.items():
                    if field in ['student_name', 'student_code', 'institution_id', 'department_id', 'year_id']:
                        update_fields.append(f"{field} = %s")
                        values.append(value)

                if not update_fields:
                    return False

                update_fields.append("updated_at = CURRENT_TIMESTAMP")
                values.append(student_id)

                query = f"""
                UPDATE students
                SET {', '.join(update_fields)}
                WHERE student_id = %s
                """

                cursor.execute(query, values)
                conn.commit()

                # Invalidate cache
                if self.cache_manager:
                    self.cache_manager.invalidate_student_cache(str(student_id))

                return cursor.rowcount > 0

        except Exception as e:
            print(f"Error updating student profile for {student_id}: {e}")
            return False

    def _get_student_performance_stats(self, student_id: int) -> Dict[str, Any]:
        """Get basic performance statistics"""
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor()

                # Overall stats
                cursor.execute("""
                    SELECT
                        COUNT(*) as total_attempts,
                        SUM(CASE WHEN sqh.is_correct THEN 1 ELSE 0 END) as correct_attempts,
                        AVG(sqh.time_spent_sec) as avg_time_spent,
                        AVG(sqh.confidence_level) as avg_confidence
                    FROM student_question_history sqh
                    JOIN student_paper_enrollments spe ON sqh.enrollment_id = spe.enrollment_id
                    WHERE spe.student_id = %s
                """, (student_id,))

                stats = cursor.fetchone()

                if stats and stats[0] > 0:
                    return {
                        'total_attempts': stats[0],
                        'correct_attempts': stats[1],
                        'success_rate': stats[1] / stats[0] if stats[0] > 0 else 0,
                        'avg_time_spent': float(stats[2]) if stats[2] else 0,
                        'avg_confidence': float(stats[3]) if stats[3] else 0
                    }
                else:
                    return {
                        'total_attempts': 0,
                        'correct_attempts': 0,
                        'success_rate': 0,
                        'avg_time_spent': 0,
                        'avg_confidence': 0
                    }

        except Exception as e:
            print(f"Error getting performance stats for {student_id}: {e}")
            return {}

    def _get_recent_activity(self, student_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent student activity"""
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=self.db_manager.RealDictCursor)

                cursor.execute("""
                    SELECT sqh.timestamp, sqh.is_correct, sqh.time_spent_sec,
                           sqh.confidence_level, q.question_id, p.paper_name
                    FROM student_question_history sqh
                    JOIN student_paper_enrollments spe ON sqh.enrollment_id = spe.enrollment_id
                    JOIN questions q ON sqh.internal_question_id = q.internal_question_id
                    JOIN papers p ON q.paper_id = p.paper_id
                    WHERE spe.student_id = %s
                    ORDER BY sqh.timestamp DESC
                    LIMIT %s
                """, (student_id, limit))

                return cursor.fetchall()

        except Exception as e:
            print(f"Error getting recent activity for {student_id}: {e}")
            return []

    def _analyze_time_patterns(self, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze time-based learning patterns"""
        if not history:
            return {}

        # Group by hour of day
        hour_performance = {}
        for record in history:
            # Handle both datetime objects and strings
            timestamp = record['timestamp']

            # If it's already a datetime object, use it directly
            if hasattr(timestamp, 'hour'):
                hour = timestamp.hour
            elif isinstance(timestamp, str):
                try:
                    # Try multiple parsing strategies
                    if 'T' in timestamp:
                        # ISO format
                        timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    elif '+' in timestamp:
                        # PostgreSQL format with timezone: '2025-08-10 13:07:31.143886+00:00'
                        from dateutil.parser import parse
                        timestamp = parse(timestamp)
                    else:
                        # Standard format
                        timestamp = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                    hour = timestamp.hour
                except (ValueError, AttributeError) as e:
                    print(f"Warning: Could not parse timestamp '{timestamp}': {e}")
                    continue  # Skip records with unparseable timestamps
                except ImportError:
                    # Fallback if dateutil not available
                    try:
                        # Try to parse manually by removing microseconds
                        if '.' in timestamp:
                            # Remove microseconds: '2025-08-10 13:07:31.143886+00:00' -> '2025-08-10 13:07:31+00:00'
                            timestamp_clean = timestamp.split('.')[0] + timestamp.split('.')[-1][-6:]
                            timestamp = datetime.fromisoformat(timestamp_clean)
                        else:
                            timestamp = datetime.fromisoformat(timestamp)
                        hour = timestamp.hour
                    except ValueError as e:
                        print(f"Warning: Could not parse timestamp '{timestamp}': {e}")
                        continue
            else:
                print(f"Warning: Unknown timestamp type: {type(timestamp)} - {timestamp}")
                continue

            if hour not in hour_performance:
                hour_performance[hour] = {'total': 0, 'correct': 0}

            hour_performance[hour]['total'] += 1
            if record['is_correct']:
                hour_performance[hour]['correct'] += 1

        # Calculate success rates by hour
        hour_success_rates = {}
        for hour, stats in hour_performance.items():
            hour_success_rates[hour] = stats['correct'] / stats['total'] if stats['total'] > 0 else 0

        return {
            'hour_performance': hour_performance,
            'hour_success_rates': hour_success_rates,
            'most_productive_hour': max(hour_success_rates.items(), key=lambda x: x[1])[0] if hour_success_rates else None
        }

    def _analyze_cluster_performance(self, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze performance by topic clusters"""
        cluster_stats = {}

        for record in history:
            if record.get('soft_cluster'):
                # Get dominant cluster
                soft_cluster = np.array(record['soft_cluster'])
                dominant_cluster = np.argmax(soft_cluster)

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

        # Calculate metrics
        cluster_performance = {}
        for cluster_id, stats in cluster_stats.items():
            cluster_performance[cluster_id] = {
                'success_rate': stats['correct'] / stats['total'] if stats['total'] > 0 else 0,
                'avg_time': stats['time_sum'] / stats['total'] if stats['total'] > 0 else 0,
                'total_attempts': stats['total']
            }

        return cluster_performance

    def _analyze_learning_progression(self, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze learning progression over time"""
        if len(history) < 10:
            return {"insufficient_data": True}

        # Sort by timestamp (oldest first for progression analysis)
        sorted_history = sorted(history, key=lambda x: x['timestamp'])

        # Calculate success rate in windows
        window_size = max(10, len(sorted_history) // 10)
        progression = []

        for i in range(0, len(sorted_history), window_size):
            window = sorted_history[i:i + window_size]
            correct = sum(1 for r in window if r['is_correct'])
            success_rate = correct / len(window)
            progression.append({
                'period': i // window_size,
                'success_rate': success_rate,
                'attempts': len(window)
            })

        # Calculate trend
        if len(progression) >= 2:
            early_rate = np.mean([p['success_rate'] for p in progression[:2]])
            late_rate = np.mean([p['success_rate'] for p in progression[-2:]])
            trend = "improving" if late_rate > early_rate + 0.05 else "declining" if late_rate < early_rate - 0.05 else "stable"
        else:
            trend = "insufficient_data"

        return {
            'progression': progression,
            'trend': trend,
            'improvement_rate': late_rate - early_rate if len(progression) >= 2 else 0
        }

    def _analyze_confidence_patterns(self, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze confidence vs performance patterns"""
        confidence_performance = {}

        for record in history:
            confidence = record['confidence_level']
            if confidence not in confidence_performance:
                confidence_performance[confidence] = {'total': 0, 'correct': 0}

            confidence_performance[confidence]['total'] += 1
            if record['is_correct']:
                confidence_performance[confidence]['correct'] += 1

        # Calculate success rates by confidence level
        confidence_success_rates = {}
        for confidence, stats in confidence_performance.items():
            confidence_success_rates[confidence] = stats['correct'] / stats['total'] if stats['total'] > 0 else 0

        return {
            'confidence_performance': confidence_performance,
            'confidence_success_rates': confidence_success_rates,
            'confidence_accuracy': len([c for c, rate in confidence_success_rates.items() if (c > 3 and rate > 0.7) or (c <= 3 and rate <= 0.7)]) / len(confidence_success_rates) if confidence_success_rates else 0
        }

    def _analyze_device_patterns(self, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze performance by device type"""
        device_performance = {}

        for record in history:
            device = record['device_type']
            if device not in device_performance:
                device_performance[device] = {'total': 0, 'correct': 0, 'time_sum': 0}

            device_performance[device]['total'] += 1
            # Ensure time_spent_sec is numeric
            time_spent = record.get('time_spent_sec', 0)
            try:
                time_spent = float(time_spent) if time_spent is not None else 0.0
            except (ValueError, TypeError):
                time_spent = 0.0
            device_performance[device]['time_sum'] += time_spent
            if record['is_correct']:
                device_performance[device]['correct'] += 1

        # Calculate metrics by device
        device_metrics = {}
        for device, stats in device_performance.items():
            device_metrics[device] = {
                'success_rate': stats['correct'] / stats['total'] if stats['total'] > 0 else 0,
                'avg_time': stats['time_sum'] / stats['total'] if stats['total'] > 0 else 0,
                'total_attempts': stats['total']
            }

        return device_metrics
