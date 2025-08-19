#!/usr/bin/env python3
"""
Answer Validation Service - Handles answer checking and timing
Provides automated answer validation and timing mechanisms
"""

import time
import json
from typing import Dict, List, Any, Optional, Tuple
from data.database_manager import DatabaseManager
from psycopg2.extras import RealDictCursor


class AnswerValidationService:
    """Service to validate student answers and manage timing"""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def get_question_answer_key(self, question_id: str) -> Optional[Dict[str, Any]]:
        """Get the correct answer and mark scheme for a question - supports both question ID formats"""
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)

                # Support both question_id (string) and internal_question_id (integer)
                if question_id.isdigit():
                    # Search by internal_question_id
                    cursor.execute("""
                        SELECT q.question_id, q.ms, q.combined_text, p.paper_name
                        FROM questions q
                        JOIN papers p ON q.paper_id = p.paper_id
                        WHERE q.internal_question_id = %s
                    """, (int(question_id),))
                else:
                    # Search by question_id string
                    cursor.execute("""
                        SELECT q.question_id, q.ms, q.combined_text, p.paper_name
                        FROM questions q
                        JOIN papers p ON q.paper_id = p.paper_id
                        WHERE q.question_id = %s
                    """, (question_id,))

                result = cursor.fetchone()
                if not result:
                    return None

                return {
                    'question_id': result['question_id'],
                    'correct_answer': result['ms'],  # This should contain the correct answer
                    'paper_name': result['paper_name'],
                    'question_text': result['combined_text']
                }
        except Exception as e:
            print(f"Error getting answer key: {e}")
            return None

    def validate_answer(self, question_id: str, student_answer: str,
                       answer_type: str = "multiple_choice") -> Dict[str, Any]:
        """
        Validate a student's answer against the correct answer

        Args:
            question_id: The question identifier
            student_answer: Student's submitted answer
            answer_type: Type of question (multiple_choice, short_answer, etc.)

        Returns:
            Dict with validation results
        """
        answer_key = self.get_question_answer_key(question_id)
        if not answer_key:
            return {
                'is_correct': None,
                'error': 'Question not found',
                'validation_method': 'error'
            }

        correct_answer = answer_key['correct_answer']

        # Handle different answer types
        if answer_type == "multiple_choice":
            is_correct = self._validate_multiple_choice(student_answer, correct_answer)
            validation_method = 'exact_match'
        elif answer_type == "numerical":
            is_correct = self._validate_numerical(student_answer, correct_answer)
            validation_method = 'numerical_tolerance'
        elif answer_type == "short_answer":
            is_correct = self._validate_short_answer(student_answer, correct_answer)
            validation_method = 'text_similarity'
        else:
            # Default to string comparison
            is_correct = self._validate_exact_match(student_answer, correct_answer)
            validation_method = 'exact_match'

        return {
            'is_correct': is_correct,
            'correct_answer': correct_answer,
            'student_answer': student_answer,
            'validation_method': validation_method,
            'question_id': question_id
        }

    def _validate_multiple_choice(self, student_answer: str, correct_answer: Any) -> bool:
        """Validate multiple choice answers (A, B, C, D)"""
        if correct_answer is None:
            return False

        # Normalize answers (remove whitespace, convert to uppercase)
        student_clean = str(student_answer).strip().upper()
        correct_clean = str(correct_answer).strip().upper()

        return student_clean == correct_clean

    def _validate_numerical(self, student_answer: str, correct_answer: Any, tolerance: float = 0.01) -> bool:
        """Validate numerical answers with tolerance"""
        try:
            student_num = float(student_answer.strip())
            correct_num = float(str(correct_answer).strip())

            # Check if within tolerance (1% by default)
            diff = abs(student_num - correct_num)
            allowed_error = abs(correct_num * tolerance)

            return diff <= allowed_error
        except (ValueError, TypeError):
            return False

    def _validate_short_answer(self, student_answer: str, correct_answer: Any) -> bool:
        """Validate short text answers with flexibility"""
        if correct_answer is None:
            return False

        student_clean = str(student_answer).strip().lower()
        correct_clean = str(correct_answer).strip().lower()

        # Check exact match first
        if student_clean == correct_clean:
            return True

        # Check if student answer contains the correct answer
        if correct_clean in student_clean or student_clean in correct_clean:
            return True

        # Could add more sophisticated text matching here
        return False

    def _validate_exact_match(self, student_answer: str, correct_answer: Any) -> bool:
        """Exact string match validation"""
        if correct_answer is None:
            return False
        return str(student_answer).strip() == str(correct_answer).strip()

    def calculate_time_metrics(self, start_time: float, end_time: float = None) -> Dict[str, Any]:
        """Calculate timing metrics for an attempt"""
        if end_time is None:
            end_time = time.time()

        time_spent = end_time - start_time

        return {
            'time_spent_seconds': time_spent,
            'time_spent_minutes': time_spent / 60.0,
            'start_time': start_time,
            'end_time': end_time,
            'timing_category': self._categorize_timing(time_spent)
        }

    def _categorize_timing(self, time_spent: float) -> str:
        """Categorize response time"""
        if time_spent < 30:
            return 'very_fast'
        elif time_spent < 60:
            return 'fast'
        elif time_spent < 120:
            return 'normal'
        elif time_spent < 300:
            return 'slow'
        else:
            return 'very_slow'

    def get_question_difficulty_timing(self, question_id: str) -> Dict[str, Any]:
        """Get average timing data for a question to set expectations - supports both question ID formats"""
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)

                # Support both question_id (string) and internal_question_id (integer)
                if question_id.isdigit():
                    # Search by internal_question_id
                    cursor.execute("""
                        SELECT
                            AVG(time_spent_sec) as avg_time,
                            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY time_spent_sec) as median_time,
                            COUNT(*) as attempt_count,
                            AVG(CASE WHEN is_correct THEN 1.0 ELSE 0.0 END) as success_rate
                        FROM student_question_history sqh
                        WHERE sqh.internal_question_id = %s
                    """, (int(question_id),))
                else:
                    # Search by question_id string
                    cursor.execute("""
                        SELECT
                            AVG(time_spent_sec) as avg_time,
                            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY time_spent_sec) as median_time,
                            COUNT(*) as attempt_count,
                            AVG(CASE WHEN is_correct THEN 1.0 ELSE 0.0 END) as success_rate
                        FROM student_question_history sqh
                        JOIN questions q ON sqh.internal_question_id = q.internal_question_id
                        WHERE q.question_id = %s
                    """, (question_id,))

                result = cursor.fetchone()
                if result and result['attempt_count'] > 0:
                    return {
                        'avg_time_seconds': float(result['avg_time'] or 0),
                        'median_time_seconds': float(result['median_time'] or 0),
                        'attempt_count': int(result['attempt_count']),
                        'success_rate': float(result['success_rate'] or 0),
                        'suggested_time_limit': float(result['median_time'] or 120) * 2  # 2x median as suggestion
                    }
                else:
                    return {
                        'avg_time_seconds': 0,
                        'median_time_seconds': 0,
                        'attempt_count': 0,
                        'success_rate': 0,
                        'suggested_time_limit': 120  # Default 2 minutes
                    }
        except Exception as e:
            print(f"Error getting timing data: {e}")
            return {
                'avg_time_seconds': 0,
                'median_time_seconds': 0,
                'attempt_count': 0,
                'success_rate': 0,
                'suggested_time_limit': 120
            }

    def create_timer_session(self, student_id: str, question_id: str,
                           time_limit_seconds: Optional[int] = None) -> Dict[str, Any]:
        """Create a timed session for a question"""
        session_id = f"timer_{student_id}_{question_id}_{int(time.time())}"
        start_time = time.time()

        # Get suggested time if not provided
        if time_limit_seconds is None:
            timing_data = self.get_question_difficulty_timing(question_id)
            time_limit_seconds = int(timing_data['suggested_time_limit'])

        timer_data = {
            'session_id': session_id,
            'student_id': student_id,
            'question_id': question_id,
            'start_time': start_time,
            'time_limit_seconds': time_limit_seconds,
            'end_time': start_time + time_limit_seconds,
            'status': 'active'
        }

        # Cache timer session
        try:
            from services.cache_service import CacheService
            # We'll need to pass cache service from the calling code
            print(f"⏱️ Created timer session: {time_limit_seconds}s limit for {question_id}")
        except Exception as e:
            print(f"Warning: Could not cache timer session: {e}")

        return timer_data

    def check_timer_status(self, session_id: str) -> Dict[str, Any]:
        """Check if a timer session is still active"""
        # This would normally check Redis cache
        # For now, we'll return a basic implementation
        current_time = time.time()

        return {
            'session_id': session_id,
            'status': 'active',  # or 'expired' or 'completed'
            'current_time': current_time,
            'time_remaining': 0,  # Would calculate from cached data
            'is_expired': False
        }

    def submit_with_validation(self, question_id: str, student_answer: str,
                             answer_type: str = "multiple_choice",
                             start_time: float = None) -> Dict[str, Any]:
        """Complete answer submission with validation and timing"""

        # Validate the answer
        validation_result = self.validate_answer(question_id, student_answer, answer_type)

        # Calculate timing if start_time provided
        timing_result = {}
        if start_time:
            timing_result = self.calculate_time_metrics(start_time)

        # Get question difficulty context
        difficulty_data = self.get_question_difficulty_timing(question_id)

        # Generate feedback
        feedback = self._generate_validation_feedback(
            validation_result, timing_result, difficulty_data
        )

        return {
            'validation': validation_result,
            'timing': timing_result,
            'difficulty_context': difficulty_data,
            'feedback': feedback,
            'submission_complete': True
        }

    def _generate_validation_feedback(self, validation: Dict, timing: Dict,
                                    difficulty: Dict) -> str:
        """Generate intelligent feedback based on answer and timing"""
        if validation['is_correct']:
            if timing and timing.get('timing_category') == 'very_fast':
                return "Excellent! Quick and correct."
            elif timing and timing.get('timing_category') in ['slow', 'very_slow']:
                return "Correct! Take your time to build confidence."
            else:
                return "Good work! Correct answer."
        else:
            if validation.get('validation_method') == 'multiple_choice':
                return f"Incorrect. The correct answer is {validation['correct_answer']}. Review the concept and try a similar question."
            else:
                return "Incorrect. Review the material and consider the key concepts before trying again."
