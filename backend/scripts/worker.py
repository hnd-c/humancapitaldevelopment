#!/usr/bin/env python3
"""
Background Worker - Process ML tasks and cache warming

This worker handles:
- Cache warming for active students
- Precomputation of similarity matrices
- Background ML model updates
- Performance analytics processing
"""

import os
import sys
import time
import signal
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from config.environments import load_config_for_environment
from bootstrap.system_initializer import SystemInitializer
from services.cache_service import CacheService
from data.database_manager import DatabaseManager


class BackgroundWorker:
    """Background worker for ML and caching tasks"""

    def __init__(self, environment="production"):
        self.environment = environment
        self.config = load_config_for_environment(environment)
        self.running = True

        print(f"🔧 Initializing background worker for {environment}")

        # Initialize system components
        self.system_initializer = SystemInitializer(self.config)
        self.components = self.system_initializer.get_system_instance()

        # Initialize services
        self.db_manager = self.components['db_manager']
        self.cache_service = CacheService(
            self.db_manager.redis_client,
            self.db_manager
        )

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        print("✅ Background worker initialized successfully")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"📨 Received signal {signum}, shutting down gracefully...")
        self.running = False

    def run(self):
        """Main worker loop"""
        print("🔄 Starting background worker loop...")

        cache_warm_interval = 300  # 5 minutes
        similarity_precompute_interval = 1800  # 30 minutes
        last_cache_warm = 0
        last_similarity_precompute = 0

        while self.running:
            try:
                current_time = time.time()

                # Cache warming for active students
                if current_time - last_cache_warm >= cache_warm_interval:
                    self._warm_caches()
                    last_cache_warm = current_time

                # Precompute similarity matrices
                if current_time - last_similarity_precompute >= similarity_precompute_interval:
                    self._precompute_similarities()
                    last_similarity_precompute = current_time

                # Perform cache optimization
                self._optimize_caches()

                # Sleep for 60 seconds before next iteration
                time.sleep(60)

            except Exception as e:
                print(f"❌ Error in worker loop: {e}")
                time.sleep(60)  # Wait before retrying

        print("🛑 Background worker stopped")

    def _warm_caches(self):
        """Warm caches for active students"""
        try:
            print("🔥 Warming caches for active students...")

            # Get active students (last 24 hours)
            active_students = self._get_active_students(hours=24, limit=100)

            if active_students:
                result = self.cache_service.warm_recommendation_cache(
                    student_ids=active_students,
                    objectives=['balanced', 'coverage', 'efficiency']
                )

                print(f"✅ Cache warming completed: {result['recommendations_cached']} recommendations cached")
            else:
                print("ℹ️  No active students found for cache warming")

        except Exception as e:
            print(f"❌ Cache warming failed: {e}")

    def _precompute_similarities(self):
        """Precompute similarity matrices for frequently accessed questions"""
        try:
            print("🧮 Precomputing similarity matrices...")

            # Get frequently accessed questions
            popular_questions = self._get_popular_questions(limit=50)

            if popular_questions:
                result = self.cache_service.precompute_similarities(
                    question_ids=popular_questions,
                    batch_size=10
                )

                print(f"✅ Similarity precomputation completed: {result['similarities_cached']} matrices cached")
            else:
                print("ℹ️  No popular questions found for similarity precomputation")

        except Exception as e:
            print(f"❌ Similarity precomputation failed: {e}")

    def _optimize_caches(self):
        """Optimize cache memory usage"""
        try:
            # Only optimize if memory usage is high
            cache_analytics = self.cache_service.cache_analytics()
            memory_usage = cache_analytics.get('redis_info', {}).get('memory_usage_ratio', 0)

            if memory_usage > 0.8:  # 80% memory usage
                print("🧹 Optimizing cache memory usage...")
                result = self.cache_service.optimize_cache_memory(target_memory_usage=0.7)
                print(f"✅ Cache optimization completed: {result.get('keys_deleted', 0)} keys removed")

        except Exception as e:
            print(f"❌ Cache optimization failed: {e}")

    def _get_active_students(self, hours=24, limit=100):
        """Get list of students active in the last N hours"""
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor()

                query = """
                SELECT DISTINCT spe.student_id::text
                FROM student_question_history sqh
                JOIN student_paper_enrollments spe ON sqh.enrollment_id = spe.enrollment_id
                WHERE sqh.timestamp >= NOW() - INTERVAL '%s hours'
                ORDER BY MAX(sqh.timestamp) DESC
                LIMIT %s
                """

                cursor.execute(query, (hours, limit))
                return [row[0] for row in cursor.fetchall()]

        except Exception as e:
            print(f"Error getting active students: {e}")
            return []

    def _get_popular_questions(self, limit=50):
        """Get list of most frequently accessed questions"""
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor()

                query = """
                SELECT q.question_id
                FROM student_question_history sqh
                JOIN questions q ON sqh.internal_question_id = q.internal_question_id
                WHERE sqh.timestamp >= NOW() - INTERVAL '7 days'
                GROUP BY q.question_id
                ORDER BY COUNT(*) DESC
                LIMIT %s
                """

                cursor.execute(query, (limit,))
                return [row[0] for row in cursor.fetchall()]

        except Exception as e:
            print(f"Error getting popular questions: {e}")
            return []

    def shutdown(self):
        """Graceful shutdown"""
        print("🛑 Shutting down background worker...")
        self.system_initializer.shutdown()


def main():
    """Main entry point"""
    environment = os.getenv('APP_ENV', 'production')

    try:
        worker = BackgroundWorker(environment)
        worker.run()
    except KeyboardInterrupt:
        print("\n🛑 Worker interrupted by user")
    except Exception as e:
        print(f"❌ Worker failed: {e}")
        return 1
    finally:
        if 'worker' in locals():
            worker.shutdown()

    return 0


if __name__ == "__main__":
    exit(main())
