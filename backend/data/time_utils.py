#!/usr/bin/env python3
"""
Time Utilities - Centralized time calculation and categorization functions

This module provides:
- Consistent time calculation methods
- Standardized timing categorization
- Timezone handling utilities
- Performance feedback generation
"""

import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Union
from enum import Enum


class TimingCategory(str, Enum):
    """Standard timing categories for response times"""
    VERY_FAST = "very_fast"
    FAST = "fast"
    NORMAL = "normal"
    SLOW = "slow"
    VERY_SLOW = "very_slow"


class FeedbackLevel(str, Enum):
    """Feedback levels for performance"""
    EXCELLENT = "excellent"
    GOOD = "good"
    AVERAGE = "average"
    NEEDS_IMPROVEMENT = "needs_improvement"


class TimeCalculator:
    """Centralized time calculation utilities"""

    # Standard timing thresholds (in seconds)
    TIMING_THRESHOLDS = {
        TimingCategory.VERY_FAST: 30,
        TimingCategory.FAST: 60,
        TimingCategory.NORMAL: 120,
        TimingCategory.SLOW: 300,
        # VERY_SLOW is anything above 300 seconds
    }

    # Default session duration estimates (in minutes)
    DEFAULT_QUESTION_DURATION = 3
    DEFAULT_SESSION_MULTIPLIER = 1.2  # Add 20% buffer

    @staticmethod
    def calculate_time_spent(start_time: Union[float, datetime],
                           end_time: Optional[Union[float, datetime]] = None) -> float:
        """
        Calculate time spent between start and end times

        Args:
            start_time: Start time (Unix timestamp or datetime)
            end_time: End time (Unix timestamp or datetime, defaults to now)

        Returns:
            Time spent in seconds (float)
        """
        if end_time is None:
            end_time = time.time()

        # Convert datetime objects to timestamps
        if isinstance(start_time, datetime):
            start_time = start_time.timestamp()
        if isinstance(end_time, datetime):
            end_time = end_time.timestamp()

        return max(0, end_time - start_time)

    @classmethod
    def calculate_time_metrics(cls, start_time: Union[float, datetime],
                              end_time: Optional[Union[float, datetime]] = None) -> Dict[str, Any]:
        """
        Calculate comprehensive timing metrics for an attempt

        Args:
            start_time: Start time (Unix timestamp or datetime)
            end_time: End time (Unix timestamp or datetime, defaults to now)

        Returns:
            Dictionary with timing metrics
        """
        if end_time is None:
            end_time = time.time()

        # Convert to timestamps for consistency
        start_timestamp = start_time.timestamp() if isinstance(start_time, datetime) else start_time
        end_timestamp = end_time.timestamp() if isinstance(end_time, datetime) else end_time

        time_spent = cls.calculate_time_spent(start_timestamp, end_timestamp)

        return {
            'time_spent_seconds': time_spent,
            'time_spent_minutes': time_spent / 60.0,
            'start_time': start_timestamp,
            'end_time': end_timestamp,
            'timing_category': cls.categorize_timing(time_spent),
            'is_within_normal_range': cls.is_normal_timing(time_spent)
        }

    @classmethod
    def categorize_timing(cls, time_spent: float) -> TimingCategory:
        """
        Categorize response time into standard categories

        Args:
            time_spent: Time spent in seconds

        Returns:
            TimingCategory enum value
        """
        if time_spent < cls.TIMING_THRESHOLDS[TimingCategory.VERY_FAST]:
            return TimingCategory.VERY_FAST
        elif time_spent < cls.TIMING_THRESHOLDS[TimingCategory.FAST]:
            return TimingCategory.FAST
        elif time_spent < cls.TIMING_THRESHOLDS[TimingCategory.NORMAL]:
            return TimingCategory.NORMAL
        elif time_spent < cls.TIMING_THRESHOLDS[TimingCategory.SLOW]:
            return TimingCategory.SLOW
        else:
            return TimingCategory.VERY_SLOW

    @classmethod
    def is_normal_timing(cls, time_spent: float) -> bool:
        """Check if timing falls within normal range (fast to normal)"""
        return (cls.TIMING_THRESHOLDS[TimingCategory.VERY_FAST] <=
                time_spent <= cls.TIMING_THRESHOLDS[TimingCategory.NORMAL])

    @classmethod
    def estimate_session_duration(cls, question_count: int,
                                 question_duration_minutes: Optional[float] = None) -> float:
        """
        Estimate total session duration with buffer

        Args:
            question_count: Number of questions in session
            question_duration_minutes: Average duration per question (defaults to 3 minutes)

        Returns:
            Estimated duration in minutes
        """
        if question_duration_minutes is None:
            question_duration_minutes = cls.DEFAULT_QUESTION_DURATION

        base_duration = question_count * question_duration_minutes
        return base_duration * cls.DEFAULT_SESSION_MULTIPLIER

    @staticmethod
    def get_current_timestamp() -> float:
        """Get current Unix timestamp"""
        return time.time()

    @staticmethod
    def get_current_datetime(with_timezone: bool = True) -> datetime:
        """
        Get current datetime

        Args:
            with_timezone: Whether to include timezone info (UTC)

        Returns:
            Current datetime object
        """
        if with_timezone:
            return datetime.now(timezone.utc)
        return datetime.now()

    @staticmethod
    def format_duration(seconds: float) -> str:
        """
        Format duration in a human-readable way

        Args:
            seconds: Duration in seconds

        Returns:
            Formatted duration string (e.g., "2m 30s", "45s", "1h 15m")
        """
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            remaining_seconds = seconds % 60
            if remaining_seconds < 1:
                return f"{minutes}m"
            return f"{minutes}m {remaining_seconds:.0f}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            if minutes == 0:
                return f"{hours}h"
            return f"{hours}h {minutes}m"


class FeedbackGenerator:
    """Generate standardized feedback based on performance and timing"""

    @staticmethod
    def generate_timing_feedback(is_correct: bool, time_spent: float,
                               confidence: Optional[float] = None) -> str:
        """
        Generate feedback based on correctness, timing, and confidence

        Args:
            is_correct: Whether the answer was correct
            time_spent: Time spent in seconds
            confidence: Confidence level (0.0 to 1.0)

        Returns:
            Feedback message string
        """
        timing_category = TimeCalculator.categorize_timing(time_spent)

        if is_correct:
            if timing_category == TimingCategory.VERY_FAST:
                return "Excellent! Quick and correct."
            elif timing_category in [TimingCategory.FAST, TimingCategory.NORMAL]:
                return "Good work! Correct answer."
            else:  # SLOW or VERY_SLOW
                return "Correct! Consider reviewing the topic for faster recall."
        else:
            if confidence and confidence > 0.7:
                return "Incorrect, but you seemed confident. Review the concept carefully."
            elif timing_category == TimingCategory.VERY_SLOW:
                return "Take your time to understand the concept before answering."
            else:
                return "Incorrect. Take time to understand the underlying concept."

    @staticmethod
    def generate_performance_summary(total_time: float, correct_count: int,
                                   total_count: int) -> Dict[str, Any]:
        """
        Generate performance summary with timing and accuracy metrics

        Args:
            total_time: Total time spent in seconds
            correct_count: Number of correct answers
            total_count: Total number of questions

        Returns:
            Dictionary with performance summary
        """
        accuracy = correct_count / total_count if total_count > 0 else 0
        avg_time_per_question = total_time / total_count if total_count > 0 else 0

        # Determine overall performance level
        if accuracy >= 0.9 and TimeCalculator.is_normal_timing(avg_time_per_question):
            level = FeedbackLevel.EXCELLENT
        elif accuracy >= 0.7 and avg_time_per_question < 300:
            level = FeedbackLevel.GOOD
        elif accuracy >= 0.5:
            level = FeedbackLevel.AVERAGE
        else:
            level = FeedbackLevel.NEEDS_IMPROVEMENT

        return {
            'accuracy': accuracy,
            'total_time_formatted': TimeCalculator.format_duration(total_time),
            'avg_time_per_question': avg_time_per_question,
            'avg_time_formatted': TimeCalculator.format_duration(avg_time_per_question),
            'performance_level': level,
            'timing_category': TimeCalculator.categorize_timing(avg_time_per_question),
            'recommendations': FeedbackGenerator._get_recommendations(accuracy, avg_time_per_question)
        }

    @staticmethod
    def _get_recommendations(accuracy: float, avg_time: float) -> list:
        """Generate recommendations based on performance metrics"""
        recommendations = []

        if accuracy < 0.6:
            recommendations.append("Focus on understanding core concepts before speed")
        elif accuracy < 0.8:
            recommendations.append("Review incorrect answers to identify knowledge gaps")

        timing_category = TimeCalculator.categorize_timing(avg_time)
        if timing_category in [TimingCategory.SLOW, TimingCategory.VERY_SLOW]:
            recommendations.append("Practice similar questions to improve response time")
        elif timing_category == TimingCategory.VERY_FAST and accuracy < 0.9:
            recommendations.append("Take more time to carefully read questions")

        if not recommendations:
            recommendations.append("Great work! Continue practicing to maintain performance")

        return recommendations


# Convenience functions for backward compatibility and ease of use
def calculate_time_metrics(start_time: Union[float, datetime],
                         end_time: Optional[Union[float, datetime]] = None) -> Dict[str, Any]:
    """Convenience function for time metric calculation"""
    return TimeCalculator.calculate_time_metrics(start_time, end_time)


def categorize_timing(time_spent: float) -> TimingCategory:
    """Convenience function for timing categorization"""
    return TimeCalculator.categorize_timing(time_spent)


def generate_timing_feedback(is_correct: bool, time_spent: float,
                           confidence: Optional[float] = None) -> str:
    """Convenience function for feedback generation"""
    return FeedbackGenerator.generate_timing_feedback(is_correct, time_spent, confidence)


def format_duration(seconds: float) -> str:
    """Convenience function for duration formatting"""
    return TimeCalculator.format_duration(seconds)
