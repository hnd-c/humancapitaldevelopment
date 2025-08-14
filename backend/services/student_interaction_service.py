#!/usr/bin/env python3
"""
Student Interaction Service - Handles student learning workflow
Uses existing schema: student_question_history, student_paper_enrollments, students
"""

import time
import uuid
import json
from typing import Dict, List, Any, Optional
from data.database_manager import DatabaseManager
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
            session_data = {
                'session_id': session_id,
                'student_id': student_id,
                'objective': objective,
                'session_type': session_type,
                'recommendations': recommendations,
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

    def submit_answer(self, attempt_id: str, student_id: str, question_id: str,
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
                time_spent_seconds = time.time() - attempt_data['started_at']

            # Auto-validate answer if enabled and is_correct not provided
            validation_result = None
            if auto_validate and is_correct is None:
                from services.answer_validation_service import AnswerValidationService
                validator = AnswerValidationService(self.db_manager)

                # Use the appropriate answer for validation
                student_answer = selected_option or answer_text
                if student_answer:
                    validation_result = validator.submit_with_validation(
                        question_id=question_id,
                        student_answer=student_answer,
                        answer_type="multiple_choice" if selected_option else "short_answer",
                        start_time=attempt_data['started_at']
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

            # Store in existing student_question_history table
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor()

                # Enhanced metadata
                enhanced_metadata = {
                    'submission_method': submission_method,
                    'attempt_id': attempt_id,
                    'session_id': attempt_data.get('session_id'),
                    'answer_text': answer_text,
                    'selected_option': selected_option,
                    **metadata
                }

                insert_query = """
                INSERT INTO student_question_history
                (enrollment_id, internal_question_id, attempt_number, status,
                 is_correct, is_skipped, time_spent_sec, timestamp,
                 confidence_level, device_type)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING history_id
                """

                cursor.execute(insert_query, (
                    enrollment_id, internal_question_id, attempt_number, status,
                    is_correct, is_skipped, time_spent_seconds, submitted_at,
                    confidence_level, metadata.get('device_type', 'desktop')
                ))

                history_id = cursor.fetchone()[0]
                conn.commit()

            # Invalidate student cache since history changed
            self.cache_service.invalidate_student_cache(student_id)
            self.cache_service.set_student_cache_version(student_id)

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
                # Get from database
                with self.db_manager.get_db_connection() as conn:
                    cursor = conn.cursor(cursor_factory=RealDictCursor)
                    cursor.execute("""
                        SELECT * FROM student_learning_sessions
                        WHERE session_id = %s
                    """, (session_id,))
                    session_data = dict(cursor.fetchone() or {})

            if not session_data:
                raise ValueError(f"Session {session_id} not found")

            # Get attempts for this session
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute("""
                    SELECT attempt_id, question_id, status, started_at, completed_at
                    FROM student_question_attempts
                    WHERE session_id = %s
                    ORDER BY started_at
                """, (session_id,))
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
        """Get question data from database"""
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute("""
                    SELECT q.*, p.paper_name, p.paper_code
                    FROM questions q
                    JOIN papers p ON q.paper_id = p.paper_id
                    WHERE q.question_id = %s
                """, (question_id,))
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
                    SELECT * FROM student_question_attempts
                    WHERE attempt_id = %s
                """, (attempt_id,))
                result = cursor.fetchone()
                return dict(result) if result else None
        except Exception as e:
            print(f"Error getting attempt data: {e}")
            return None

    def _get_internal_question_id(self, question_id: str) -> int:
        """Get internal question ID from question_id"""
        with self.db_manager.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT internal_question_id FROM questions
                WHERE question_id = %s
            """, (question_id,))
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
