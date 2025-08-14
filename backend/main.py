#!/usr/bin/env python3
"""
Main Application Entry Point - Human Capital Development System

This is the main entry point that integrates all system components:
- Bootstrap and initialization
- ML pipeline and recommendations
- Database operations and caching
- API server
"""

import os
import sys
import time
import argparse
from pathlib import Path

# Add current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from config.environments import load_config_for_environment
from bootstrap.system_initializer import SystemInitializer
from services.recommendation_service import OptimizedRecommendationEngine
from api.routes import create_app


class HumanCapitalDevelopmentSystem:
    """
    Main system orchestrator that integrates all components
    """

    def __init__(self, config=None, environment="development"):
        self.environment = environment
        self.config = config or load_config_for_environment(environment)
        self.start_time = time.time()

        print("🚀 Initializing Human Capital Development System...")
        print("=" * 60)

        # Initialize system using bootstrap
        self.system_initializer = SystemInitializer(self.config)
        self.components = self.system_initializer.get_system_instance()

        # Initialize recommendation engine
        self._initialize_recommendation_engine()

        print(f"✅ System initialized successfully in {time.time() - self.start_time:.2f}s")
        print("=" * 60)

    def _initialize_recommendation_engine(self):
        """Initialize the recommendation engine"""
        try:
            self.recommendation_engine = OptimizedRecommendationEngine(
                self.components['db_manager']
            )
            print("✅ Recommendation engine initialized")
        except Exception as e:
            print(f"⚠️  Recommendation engine initialization failed: {e}")
            self.recommendation_engine = None

    def get_recommendations_optimized(self, student_id: str, objective: str = 'balanced',
                                    top_k: int = 5, use_cache: bool = True):
        """
        Main recommendation function that integrates all components
        """
        if not self.recommendation_engine:
            return self._get_default_recommendations(top_k)

        try:
            return self.recommendation_engine.get_recommendations_for_student(
                student_id=student_id,
                objective=objective,
                top_k=top_k,
                use_cache=use_cache
            )
        except Exception as e:
            print(f"❌ Error generating recommendations for {student_id}: {e}")
            return self._get_default_recommendations(top_k)

    def analyze_student_performance(self, student_id: str):
        """Comprehensive student performance analysis"""
        try:
            from services.student_service import StudentService

            student_service = StudentService(
                self.components['db_manager'],
                self.components['cache_manager']
            )

            return student_service.analyze_student_learning_patterns(int(student_id))

        except Exception as e:
            print(f"Error analyzing student performance: {e}")
            return {"error": str(e)}

    def get_system_health(self):
        """Get comprehensive system health metrics"""
        try:
            health = {
                'timestamp': time.time(),
                'uptime_seconds': time.time() - self.start_time,
                'environment': self.environment,
                'database_status': 'unknown',
                'redis_status': 'unknown',
                'ml_components_status': 'unknown'
            }

            # Test database
            try:
                with self.components['db_manager'].get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM questions")
                    question_count = cursor.fetchone()[0]
                    health['database_status'] = 'healthy'
                    health['total_questions'] = question_count
            except Exception as e:
                health['database_status'] = f'error: {e}'

            # Test Redis
            try:
                self.components['db_manager'].redis_client.ping()
                health['redis_status'] = 'healthy'
                if self.components['performance_monitor']:
                    health.update(self.components['performance_monitor'].get_system_metrics())
            except Exception as e:
                health['redis_status'] = f'error: {e}'

            # Test ML components
            try:
                if self.recommendation_engine:
                    health['ml_components_status'] = 'healthy'
                    health['recommendation_engine_available'] = True
                else:
                    health['ml_components_status'] = 'degraded'
                    health['recommendation_engine_available'] = False
            except Exception as e:
                health['ml_components_status'] = f'error: {e}'

            return health

        except Exception as e:
            return {'error': f'Health check failed: {e}'}

    def _get_default_recommendations(self, top_k: int):
        """Get default recommendations when ML engine is unavailable"""
        try:
            with self.components['db_manager'].get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=self.components['db_manager'].RealDictCursor)

                query = """
                SELECT q.internal_question_id, q.question_id, q.paper_id,
                       p.paper_name, p.paper_code,
                       (SELECT i-1 FROM unnest(q.soft_cluster) WITH ORDINALITY arr(val,i)
                        ORDER BY val DESC LIMIT 1) as dominant_cluster
                FROM questions q
                JOIN papers p ON q.paper_id = p.paper_id
                WHERE q.soft_cluster IS NOT NULL
                ORDER BY RANDOM()
                LIMIT %s
                """

                cursor.execute(query, (top_k,))
                return cursor.fetchall()

        except Exception as e:
            print(f"Error getting default recommendations: {e}")
            return []

    def start_api_server(self, host="0.0.0.0", port=8000, reload=False):
        """Start the FastAPI server"""
        try:
            import uvicorn
            from api.routes import app

            print(f"🌐 Starting API server on {host}:{port}")

            # Set system instance for the API
            app.state.system = self

            uvicorn.run(
                app,
                host=host,
                port=port,
                reload=reload,
                log_level="info" if self.config.debug_mode else "warning"
            )

        except ImportError:
            print("❌ uvicorn not installed. Install with: pip install uvicorn")
        except Exception as e:
            print(f"❌ Failed to start API server: {e}")

    def run_demo(self):
        """Run system demonstration"""
        print("🚀 Human Capital Development System - Demo")
        print("=" * 60)

        # Health check
        health = self.get_system_health()
        print(f"🏥 System Health:")
        print(f"   Database: {health.get('database_status')}")
        print(f"   Redis: {health.get('redis_status')}")
        print(f"   ML Components: {health.get('ml_components_status')}")

        if health.get('total_questions'):
            print(f"   Total Questions: {health['total_questions']:,}")

        # Test recommendations
        test_student_id = "1"
        print(f"\n🎯 Testing recommendations for student {test_student_id}...")

        recommendations = self.get_recommendations_optimized(
            student_id=test_student_id,
            objective='balanced',
            top_k=5
        )

        print(f"📋 Generated {len(recommendations)} recommendations:")
        for i, rec in enumerate(recommendations[:3], 1):
            print(f"   {i}. Question {rec.get('question_id', 'N/A')} "
                  f"(Score: {rec.get('combined_score', rec.get('weighted_score', 0)):.3f})")

        # Performance analysis
        print(f"\n📊 Analyzing student performance...")
        performance = self.analyze_student_performance(test_student_id)
        if 'error' not in performance:
            print(f"   Total attempts: {performance.get('total_attempts', 0)}")
            print(f"   Success rate: {performance.get('overall_success_rate', 0):.1%}")

        print(f"\n✅ Demo completed successfully!")

    def shutdown(self):
        """Graceful system shutdown"""
        print("🛑 Shutting down Human Capital Development System...")

        try:
            self.system_initializer.shutdown()
            print("✅ System shutdown completed")
        except Exception as e:
            print(f"⚠️  Error during shutdown: {e}")


def main():
    """Main entry point with command line interface"""
    parser = argparse.ArgumentParser(description="Human Capital Development System")
    parser.add_argument(
        "--environment",
        default="development",
        help="Environment to run in (development, staging, production)"
    )
    parser.add_argument(
        "--mode",
        choices=["demo", "api", "health"],
        default="demo",
        help="Mode to run the system in"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="API server host (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="API server port (default: 8000)"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development"
    )

    args = parser.parse_args()

    try:
        # Initialize system
        config = load_config_for_environment(args.environment)
        system = HumanCapitalDevelopmentSystem(config, args.environment)

        if args.mode == "demo":
            system.run_demo()

        elif args.mode == "api":
            system.start_api_server(
                host=args.host,
                port=args.port,
                reload=args.reload
            )

        elif args.mode == "health":
            health = system.get_system_health()
            print(f"System Health: {health}")

            # Exit with error code if unhealthy
            if any('error' in str(v) for v in health.values()):
                return 1

        # Graceful shutdown
        system.shutdown()
        return 0

    except KeyboardInterrupt:
        print("\n🛑 System interrupted by user")
        return 1
    except Exception as e:
        print(f"❌ System failed: {e}")
        import traceback
        if args.environment == "development":
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
