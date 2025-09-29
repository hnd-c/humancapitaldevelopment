#!/usr/bin/env python3
"""
Student Interaction Service - Handles student learning workflow
Uses existing schema: student_question_history, student_paper_enrollments, students
"""

import time
import uuid
import json
from typing import Dict, Any, Optional
from data.database_manager import DatabaseManager
from data.models import build_question_query, resolve_question_id
from services.cache_service import CacheService
from psycopg2.extras import RealDictCursor
from datetime import datetime


class StudentInteractionService:
    """Service to handle student learning interactions using existing schema"""

    def __init__(self, db_manager: DatabaseManager, cache_service: CacheService):
        self.db_manager = db_manager
        self.cache_service = cache_service

    def start_learning_session(self, student_id: str, objective: str = "balanced",
                             session_type: str = "practice", target_questions: int = 10) -> Dict[str, Any]:
        """Start a new learning session for a student - uses in-memory session tracking"""
        session_id = str(uuid.uuid4())
        session_start = time.time()

        try:
            # Get recommendations for the session
            from services.recommendation_service import OptimizedRecommendationEngine
            engine = OptimizedRecommendationEngine(self.db_manager, lazy_load=True)
            recommendations = engine.recommend_questions_optimized(
                student_id=student_id,
                objective=objective,
                top_k=target_questions
            )

            # Cache session data (no database needed - just Redis)
            # Convert Recommendation objects to dicts for JSON serialization
            recommendations_dicts = []
            for rec in recommendations:
                try:
                    # Import dataclasses for conversion
                    import dataclasses

                                        # Try different ways to convert Recommendation objects to dicts
                    if hasattr(rec, '__dataclass_fields__'):
                        # It's a dataclass - use dataclasses.asdict
                        rec_dict = dataclasses.asdict(rec)
                        recommendations_dicts.append(rec_dict)
                    elif hasattr(rec, '__dict__'):
                        # Regular object with __dict__
                        rec_dict = {}
                        for key, value in rec.__dict__.items():
                            # Handle special types that might not serialize
                            if isinstance(value, (str, int, float, bool, type(None))):
                                rec_dict[key] = value
                            else:
                                rec_dict[key] = str(value)
                        recommendations_dicts.append(rec_dict)
                    elif isinstance(rec, dict):
                        recommendations_dicts.append(rec)
                    else:
                        # Manual field extraction for Recommendation objects
                        rec_dict = {
                            'question_id': getattr(rec, 'question_id', 'unknown'),
                            'internal_question_id': getattr(rec, 'internal_question_id', 0),
                            'paper_id': getattr(rec, 'paper_id', 0),
                            'weighted_score': getattr(rec, 'weighted_score', 0.0),
                            'dominant_cluster': getattr(rec, 'dominant_cluster', 0),
                            'similarity_score': getattr(rec, 'similarity_score', None),
                            'combined_score': getattr(rec, 'combined_score', None),
                            'reasoning': getattr(rec, 'reasoning', None)
                        }
                        recommendations_dicts.append(rec_dict)
                except Exception as e:
                    # Last resort fallback
                    print(f"⚠️ Error converting recommendation: {e}")
                    recommendations_dicts.append({"error": "Conversion failed", "raw": str(rec)})

            session_data = {
                'session_id': session_id,
                'student_id': student_id,
                'objective': objective,
                'session_type': session_type,
                'recommendations': recommendations_dicts,
                'session_started_at': session_start,
                'estimated_duration_minutes': target_questions * 3  # 3 minutes per question estimate
            }

            self.cache_service.redis.setex(
                f"session:{session_id}",
                3600,  # 1 hour TTL
                json.dumps(session_data, default=str)
            )

            print(f"🎓 Started learning session {session_id[:8]}... for student {student_id}")
            return session_data

        except Exception as e:
            print(f"❌ Error starting learning session: {e}")
            raise

    def start_question_attempt(self, student_id: str, question_id: str,
                              session_id: Optional[str] = None) -> Dict[str, Any]:
        """Start a question attempt - returns question data for student to work on"""
        attempt_id = str(uuid.uuid4())
        started_at = time.time()

        try:
            # Get question data
            question_data = self._get_question_data(question_id)
            if not question_data:
                raise ValueError(f"Question {question_id} not found")

            # Cache attempt data for submission tracking (no database insert needed yet)
            attempt_data = {
                'attempt_id': attempt_id,
                'student_id': student_id,
                'question_id': question_id,
                'session_id': session_id,
                'question_data': question_data,
                'started_at': started_at,
                'status': 'in_progress'
            }

            self.cache_service.redis.setex(
                f"attempt:{attempt_id}",
                1800,  # 30 minutes TTL
                json.dumps(attempt_data, default=str)
            )

            print(f"📝 Started question attempt {attempt_id[:8]}... for student {student_id}")
            return attempt_data

        except Exception as e:
            print(f"❌ Error starting question attempt: {e}")
            raise

    async def submit_answer(self, attempt_id: str, student_id: str, question_id: str,
                     answer_text: Optional[str] = None, selected_option: Optional[str] = None,
                     is_correct: Optional[bool] = None, confidence_level: Optional[float] = None,
                     time_spent_seconds: Optional[float] = None, submission_method: str = "manual",
                     metadata: Optional[Dict[str, Any]] = None,
                     auto_validate: bool = True) -> Dict[str, Any]:
        """Submit an answer using existing student_question_history table"""
        submission_id = str(uuid.uuid4())
        submitted_at = datetime.now()

        if metadata is None:
            metadata = {}

        try:
            # Get attempt data
            attempt_data = self._get_attempt_data(attempt_id)
            if not attempt_data:
                raise ValueError(f"Attempt {attempt_id} not found")

            # Calculate time spent if not provided
            if time_spent_seconds is None:
                # Use started_at if available, otherwise use a default time
                started_at = attempt_data.get('started_at', time.time() - 120)  # Default 2 minutes ago
                time_spent_seconds = time.time() - started_at

            # Auto-validate answer if enabled and is_correct not provided
            validation_result = None
            if auto_validate and is_correct is None:
                from services.answer_validation_service import AnswerValidationService
                validator = AnswerValidationService(self.db_manager)

                # Get the proper question data to ensure we have the Cambridge format question_id
                question_data = self._get_question_data(question_id)
                if not question_data:
                    raise ValueError(f"Question {question_id} not found")

                # Use the Cambridge format question_id for validation
                cambridge_question_id = question_data['question_id']

                # Use the appropriate answer for validation
                student_answer = selected_option or answer_text
                if student_answer:
                    # Use calculated started_at safely
                    start_time = attempt_data.get('started_at', time.time() - 120)
                    validation_result = validator.submit_with_validation(
                        question_id=cambridge_question_id,  # Use Cambridge format
                        student_answer=student_answer,
                        answer_type="multiple_choice" if selected_option else "short_answer",
                        start_time=start_time
                    )
                    is_correct = validation_result['validation']['is_correct']
                    print(f"🤖 Auto-validated answer: {'✓ Correct' if is_correct else '✗ Incorrect'}")
                else:
                    print("⚠️ No answer provided for validation")
                    is_correct = False

            # Get internal question ID and enrollment
            internal_question_id = self._get_internal_question_id(question_id)
            enrollment_id = self._get_or_create_enrollment(student_id)

            # Get next attempt number for this student-question pair
            attempt_number = self._get_next_attempt_number(enrollment_id, internal_question_id)

            # Determine status based on is_correct
            status = 'correct' if is_correct else 'wrong'
            is_skipped = False

            # Store in existing student_question_history table using async
            conn = await self.db_manager.get_async_connection()
            try:
                # Enhanced metadata for logging/debugging
                enhanced_metadata = {
                    'submission_method': submission_method,
                    'attempt_id': attempt_id,
                    'session_id': attempt_data.get('session_id'),
                    'answer_text': answer_text,
                    'selected_option': selected_option,
                    **metadata
                }
                print(f"📊 Submission metadata: {enhanced_metadata}")  # Use the metadata

                insert_query = """
                INSERT INTO student_question_history
                (enrollment_id, internal_question_id, attempt_number, status,
                 is_correct, is_skipped, time_spent_sec, timestamp,
                 confidence_level, device_type)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING history_id
                """

                # Ensure confidence_level meets database constraints (must be between 1 and 5)
                if confidence_level is None:
                    safe_confidence_level = 3  # Default to medium confidence
                else:
                    # Convert float confidence (0.0-1.0) to integer scale (1-5)
                    if 0 <= confidence_level <= 1:
                        safe_confidence_level = max(1, min(5, int(confidence_level * 4) + 1))
                    else:
                        safe_confidence_level = max(1, min(5, int(confidence_level)))

                history_id = await conn.fetchval(insert_query,
                    enrollment_id, internal_question_id, attempt_number, status,
                    is_correct, is_skipped, time_spent_seconds, submitted_at,
                    safe_confidence_level, metadata.get('device_type', 'desktop')
                )
            finally:
                await self.db_manager.release_async_connection(conn)

            # Invalidate student cache since history changed
            self.cache_service.invalidate_student_cache(student_id)
            self.cache_service.set_student_cache_version(student_id)

            # Trigger real-time UMAP status updates (non-blocking)
            import asyncio
            asyncio.create_task(
                self._notify_umap_status_change(student_id, question_id, status, is_correct, metadata)
            )

            # Generate feedback
            feedback = self._generate_feedback(is_correct, confidence_level, time_spent_seconds)

            submission_data = {
                'submission_id': submission_id,
                'history_id': history_id,
                'student_id': student_id,
                'question_id': question_id,
                'is_correct': is_correct,
                'time_spent_seconds': time_spent_seconds,
                'submitted_at': time.time(),
                'feedback': feedback,
                'cache_invalidated': True,
                'next_recommendations_available': True
            }

            print(f"✅ Submitted answer for student {student_id}, question {question_id}")
            print(f"   Result: {'✓ Correct' if is_correct else '✗ Incorrect'}")
            print(f"   Time: {time_spent_seconds:.1f}s")
            print(f"   History ID: {history_id}")

            return submission_data

        except Exception as e:
            print(f"❌ Error submitting answer: {e}")
            raise

    def get_student_session_progress(self, session_id: str) -> Dict[str, Any]:
        """Get progress for a learning session"""
        try:
            # Try cache first
            cached_session = self.cache_service.redis.get(f"session:{session_id}")
            if cached_session:
                session_data = json.loads(cached_session)
            else:
                # Get from database - use student history to reconstruct session
                with self.db_manager.get_db_connection() as conn:
                    cursor = conn.cursor(cursor_factory=RealDictCursor)
                    # Extract student_id from session_id pattern if possible
                    try:
                        # Session data stored in cache with student_id
                        session_data = {
                            'session_id': session_id,
                            'status': 'not_found',
                            'message': 'Session data only available in cache'
                        }
                    except Exception:
                        session_data = {}

            if not session_data:
                raise ValueError(f"Session {session_id} not found")

            # Get attempts for this session
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                # Since sessions are memory-only for now, we can't get attempts from DB based on session_id
                # Instead, get recent attempts from the student (derived from session data)
                student_number = session_data.get('student_id', '1')  # fallback to student 1

                cursor.execute("""
                    SELECT sqh.history_id as attempt_id, q.question_id,
                           CASE
                               WHEN sqh.status = 'correct' THEN 'completed'
                               WHEN sqh.status = 'wrong' THEN 'completed'
                               WHEN sqh.status = 'skipped' THEN 'completed'
                               ELSE 'completed'
                           END as status,
                           sqh.timestamp as started_at,
                           sqh.timestamp as completed_at
                    FROM student_question_history sqh
                    JOIN questions q ON sqh.internal_question_id = q.internal_question_id
                    JOIN student_paper_enrollments spe ON sqh.enrollment_id = spe.enrollment_id
                    JOIN students s ON spe.student_id = s.student_id
                    WHERE s.base_student_number = %s
                    ORDER BY sqh.timestamp DESC
                    LIMIT 20
                """, (student_number,))
                attempts = [dict(row) for row in cursor.fetchall()]

            progress = {
                'session_data': session_data,
                'attempts': attempts,
                'total_questions': len(session_data.get('recommendations', [])),
                'completed_questions': len([a for a in attempts if a['status'] == 'completed']),
                'in_progress_questions': len([a for a in attempts if a['status'] == 'in_progress'])
            }

            return progress

        except Exception as e:
            print(f"❌ Error getting session progress: {e}")
            raise

    def _get_question_data(self, question_id: str) -> Optional[Dict[str, Any]]:
        """Get question data from database - supports both question_id (string) and internal_question_id (integer)"""
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)

                # Use centralized question ID resolution
                base_query = """
                    SELECT q.internal_question_id, q.question_id, q.paper_id, q.question_number,
                           q.images, q.text_length, q.source_file, q.ms,
                           q.is_active, q.created_at, q.updated_at,
                           p.paper_name, p.paper_code
                    FROM questions q
                    JOIN papers p ON q.paper_id = p.paper_id
                    {where_clause}
                """
                query, params = build_question_query(base_query, question_id)
                cursor.execute(query, params)
                result = cursor.fetchone()
                return dict(result) if result else None
        except Exception as e:
            print(f"Error getting question data: {e}")
            return None

    def _get_attempt_data(self, attempt_id: str) -> Optional[Dict[str, Any]]:
        """Get attempt data from cache or database"""
        try:
            # Try cache first
            cached_attempt = self.cache_service.redis.get(f"attempt:{attempt_id}")
            if cached_attempt:
                return json.loads(cached_attempt)

            # Get from database
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute("""
                    SELECT history_id as attempt_id, enrollment_id, internal_question_id,
                           attempt_number, status, is_correct, is_skipped,
                           time_spent_sec, timestamp, confidence_level, device_type
                    FROM student_question_history
                    WHERE history_id = %s
                """, (attempt_id,))
                result = cursor.fetchone()
                return dict(result) if result else None
        except Exception as e:
            print(f"Error getting attempt data: {e}")
            return None

    def _get_internal_question_id(self, question_id: str) -> int:
        """Get internal question ID from question_id - supports both integer and Cambridge format"""
        # Use centralized question ID resolution
        query_field, query_value = resolve_question_id(question_id)

        if query_field == "q.internal_question_id":
            # Already an integer, return it directly
            return query_value
        else:
            # Need to look up the internal_question_id
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT internal_question_id FROM questions
                    WHERE question_id = %s
                """, (query_value,))
                result = cursor.fetchone()
                if not result:
                    raise ValueError(f"Question {question_id} not found")
                return result[0]

    def _get_or_create_enrollment(self, student_id: str) -> int:
        """Get or create enrollment ID for student"""
        with self.db_manager.get_db_connection() as conn:
            cursor = conn.cursor()

            # Try to find existing enrollment
            cursor.execute("""
                SELECT enrollment_id FROM student_paper_enrollments
                WHERE student_id = %s
                LIMIT 1
            """, (student_id,))
            result = cursor.fetchone()

            if result:
                return result[0]

            # Create new enrollment (using paper_id = 1 for default)
            cursor.execute("""
                INSERT INTO student_paper_enrollments
                (student_id, paper_id, paper_student_id, enrolled_at)
                VALUES (%s, %s, %s, %s)
                RETURNING enrollment_id
            """, (student_id, 1, f"STUDENT_{student_id}_PAPER_1", datetime.now()))

            enrollment_id = cursor.fetchone()[0]
            conn.commit()
            return enrollment_id

    def _get_next_attempt_number(self, enrollment_id: int, internal_question_id: int) -> int:
        """Get the next attempt number for this student-question pair"""
        with self.db_manager.get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT COALESCE(MAX(attempt_number), 0) + 1
                FROM student_question_history
                WHERE enrollment_id = %s AND internal_question_id = %s
            """, (enrollment_id, internal_question_id))

            return cursor.fetchone()[0]

    def _generate_feedback(self, is_correct: bool, confidence: Optional[float],
                          time_spent: float) -> str:
        """Generate feedback based on performance"""
        if is_correct:
            if time_spent < 30:
                return "Excellent! Quick and correct."
            elif time_spent < 120:
                return "Good work! Correct answer."
            else:
                return "Correct! Consider reviewing the topic for faster recall."
        else:
            if confidence and confidence > 0.7:
                return "Incorrect, but you seemed confident. Review the concept carefully."
            else:
                return "Incorrect. Take time to understand the underlying concept."

    async def _notify_umap_status_change(
        self,
        student_id: str,
        question_id: str,
        status: str,
        is_correct: bool,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Notify WebSocket connections about UMAP status changes"""
        try:
            from services.websocket_service import umap_notification_service

            # Determine the visual status for UMAP
            if status == 'skipped':
                umap_status = 'skipped'
            elif is_correct:
                umap_status = 'mastered'  # Latest attempt is correct
            else:
                # Need to check if student has any previous correct attempts
                umap_status = await self._determine_mixed_status(student_id, question_id)

            additional_data = {
                "confidence_level": metadata.get('confidence_level') if metadata else None,
                "time_spent": metadata.get('time_spent_seconds') if metadata else None,
                "device_type": metadata.get('device_type') if metadata else None
            }

            await umap_notification_service.notify_question_answered(
                student_id=student_id,
                question_id=question_id,
                is_correct=is_correct,
                status=umap_status,
                additional_data=additional_data
            )

        except Exception as e:
            # Don't fail the main operation if notification fails
            print(f"Warning: Failed to send UMAP notification for student {student_id}, question {question_id}: {e}")

    async def _determine_mixed_status(self, student_id: str, question_id: str) -> str:
        """Determine if question status should be 'mixed' or 'incorrect'"""
        try:
            # Get enrollment_id for this student
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT enrollment_id FROM student_paper_enrollments
                    WHERE student_id = %s AND is_active = TRUE
                    LIMIT 1
                """, [student_id])

                result = cursor.fetchone()
                if not result:
                    return 'incorrect'

                enrollment_id = result[0]

                # Get internal_question_id
                cursor.execute("""
                    SELECT internal_question_id FROM questions
                    WHERE question_id = %s
                """, [question_id])

                result = cursor.fetchone()
                if not result:
                    return 'incorrect'

                internal_question_id = result[0]

                # Check if student has any previous correct attempts
                cursor.execute("""
                    SELECT COUNT(*) FROM student_question_history
                    WHERE enrollment_id = %s AND internal_question_id = %s AND is_correct = TRUE
                """, [enrollment_id, internal_question_id])

                correct_count = cursor.fetchone()[0]
                return 'mixed' if correct_count > 0 else 'incorrect'

        except Exception as e:
            print(f"Error determining mixed status: {e}")
            return 'incorrect'
