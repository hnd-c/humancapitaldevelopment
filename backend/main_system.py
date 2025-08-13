#!/usr/bin/env python3
"""
Human Capital Development - Main System Orchestrator
Integrates all components: ML pipeline, database, caching, and recommendations
"""

import os
import sys
import time
import json
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from contextlib import contextmanager

# Import all system components
from database_manager import DatabaseManager
from redis_cache_manager import RedisCacheManager
from vector_operations import VectorOperations
from performance_monitor import PerformanceMonitor

# Import existing ML components
from enriched_vector import RichVectorEncoder, load_student_history_normalized
from transition_matrix import _build_cooccurrence_transitions, recommend_next_clusters
from recommendation_engine import QuestionRecommendationEngine


@dataclass
class SystemConfig:
    """System configuration"""
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


class HumanCapitalDevelopmentSystem:
    """
    Main system orchestrator that integrates:
    1. Existing ML pipeline (enriched_vector.py, transition_matrix.py, recommendation_engine.py)
    2. Database operations (PostgreSQL + Redis)
    3. Vector operations and caching
    4. Performance monitoring
    """

    def __init__(self, config: SystemConfig):
        self.config = config
        self.start_time = time.time()

        print("🚀 Initializing Human Capital Development System...")
        print("=" * 60)

        # Initialize core components
        self._initialize_database_layer()
        self._initialize_ml_components()
        self._initialize_monitoring()

        print(f"✅ System initialized successfully in {time.time() - self.start_time:.2f}s")
        print("=" * 60)

    def _initialize_database_layer(self):
        """Initialize database and caching layer"""
        print("📊 Initializing database layer...")

        try:
            # Database manager
            self.db_manager = DatabaseManager(
                db_config=self.config.db_config,
                redis_config=self.config.redis_config
            )

            # Cache manager
            self.cache_manager = RedisCacheManager(self.db_manager.redis_client)

            # Vector operations
            self.vector_ops = VectorOperations(self.db_manager)

            # Test connections
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                assert cursor.fetchone()[0] == 1

            # Test Redis
            self.db_manager.redis_client.ping()

            print("✅ Database layer initialized successfully")

        except Exception as e:
            print(f"❌ Failed to initialize database layer: {e}")
            raise

    def _initialize_ml_components(self):
        """Initialize ML pipeline components"""
        print("🧠 Initializing ML components...")

        try:
            # Load question data and clusters
            self.questions_df = pd.read_parquet("combined_questions.parquet")
            self.soft_clusters = np.stack(self.questions_df['soft_cluster'].values)

            # Create question mapping
            self.question_mapping = self._create_question_mapping()

            # Initialize rich vector encoder
            self.vector_encoder = RichVectorEncoder(
                soft_clusters=self.soft_clusters,
                question_mapping=self.question_mapping
            )

            # Build or load transition matrix
            self.transition_matrix = _build_cooccurrence_transitions(alpha=0.1, normalize=True)

            # Initialize recommendation engine (legacy support)
            self.legacy_recommendation_engine = QuestionRecommendationEngine()

            print(f"✅ ML components initialized with {len(self.questions_df)} questions")

        except Exception as e:
            print(f"❌ Failed to initialize ML components: {e}")
            raise

    def _initialize_monitoring(self):
        """Initialize performance monitoring"""
        print("📈 Initializing performance monitoring...")

        if self.config.enable_performance_monitoring:
            self.performance_monitor = PerformanceMonitor(self.db_manager.redis_client)
            print("✅ Performance monitoring enabled")
        else:
            self.performance_monitor = None
            print("⚠️  Performance monitoring disabled")

    def _create_question_mapping(self) -> Dict[str, int]:
        """Create mapping from question_id strings to integer indices"""
        questions_indexed = self.questions_df.reset_index(drop=True)
        questions_indexed["question_id"] = (
            questions_indexed["paper_number"].astype(str) + "_" +
            questions_indexed["question_number"].astype(str)
        )

        question_mapping = {}
        for idx, row in questions_indexed.iterrows():
            question_mapping[row["question_id"]] = idx

        return question_mapping

    @contextmanager
    def performance_tracking(self, operation_name: str, student_id: Optional[str] = None):
        """Context manager for performance tracking"""
        start_time = time.time()
        try:
            yield
        finally:
            if self.performance_monitor and student_id:
                response_time = time.time() - start_time
                self.performance_monitor.track_recommendation_performance(
                    student_id=student_id,
                    recommendations=[],  # Would contain actual recommendations
                    response_time=response_time
                )

    def get_recommendations_optimized(self, student_id: str, objective: str = 'balanced',
                                    top_k: int = 5, use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        Main recommendation function that integrates all components
        """
        start_time = time.time()

        # Check cache first
        if use_cache:
            cached_recommendations = self.cache_manager.get_cached_recommendations(student_id, objective)
            if cached_recommendations:
                if self.config.debug_mode:
                    print(f"🎯 Cache hit for {student_id} ({objective})")
                return cached_recommendations

        with self.performance_tracking("get_recommendations", student_id):
            try:
                # 1. Get student history from database (with caching)
                student_history = self.db_manager.get_student_history_optimized(
                    student_id=int(student_id) if student_id.isdigit() else self._extract_student_number(student_id)
                )

                if not student_history:
                    print(f"⚠️  No history found for {student_id}, using default recommendations")
                    return self._get_default_recommendations_db(top_k)

                # 2. Create enriched state vector using ML pipeline
                current_question = student_history[0]['question_id']  # Most recent

                # Convert student history to format expected by ML pipeline
                ml_student_attempts = self._convert_db_history_to_ml_format(student_history)

                current_state = self.vector_encoder.encode_student_context(
                    current_question=current_question,
                    student_attempts=ml_student_attempts,
                    objective=objective
                )

                # 3. Apply transition matrix for next cluster priorities
                next_cluster_priorities = recommend_next_clusters(current_state, self.transition_matrix)

                # 4. Use database vector operations to find recommendations
                attempted_question_ids = [h['internal_question_id'] for h in student_history]

                recommendations = self.vector_ops.find_cluster_based_questions(
                    cluster_priorities=next_cluster_priorities,
                    exclude_question_ids=attempted_question_ids,
                    top_k=top_k
                )

                # 5. Enrich recommendations with similarity scores
                if self.config.use_multimodal_embeddings and recommendations:
                    recommendations = self._enrich_with_similarity_scores(
                        recommendations, current_question
                    )

                # 6. Cache results
                if use_cache:
                    self.cache_manager.cache_recommendation_results(
                        student_id=student_id,
                        objective=objective,
                        recommendations=recommendations,
                        ttl=self.config.cache_ttl_seconds
                    )

                response_time = time.time() - start_time
                if self.config.debug_mode:
                    print(f"🎯 Generated {len(recommendations)} recommendations for {student_id} in {response_time:.3f}s")

                return recommendations

            except Exception as e:
                print(f"❌ Error generating recommendations for {student_id}: {e}")
                return self._get_default_recommendations_db(top_k)

    def _extract_student_number(self, student_id: str) -> int:
        """Extract numeric student ID from full student identifier"""
        if "_STU_" in student_id:
            return int(student_id.split("_STU_")[-1])
        return int(student_id)

    def _convert_db_history_to_ml_format(self, db_history: List[Dict]) -> List[Dict]:
        """Convert database history format to ML pipeline format"""
        ml_attempts = []
        for record in db_history:
            ml_attempts.append({
                'id': record['history_id'],
                'question_id': record['question_id'],
                'status': record['status'],
                'is_correct': record['is_correct'],
                'is_skipped': record['is_skipped'],
                'time_spent_sec': record['time_spent_sec'],
                'timestamp': record['timestamp'],
                'confidence_level': record['confidence_level'],
                'device_type': record['device_type']
            })
        return ml_attempts

    def _enrich_with_similarity_scores(self, recommendations: List[Dict],
                                     current_question: str) -> List[Dict]:
        """Enrich recommendations with multimodal similarity scores"""
        try:
            # Get embeddings for current question
            current_embeddings = self.vector_ops.get_question_embeddings(current_question)
            if not current_embeddings:
                return recommendations

            # Calculate similarity scores for each recommendation
            for rec in recommendations:
                target_embeddings = self.vector_ops.get_question_embeddings(rec['question_id'])
                if target_embeddings:
                    # Calculate multimodal similarity
                    similarity_score = self._calculate_multimodal_similarity(
                        current_embeddings, target_embeddings
                    )
                    rec['similarity_score'] = similarity_score
                else:
                    rec['similarity_score'] = 0.0

            # Re-sort by combined score (weighted cluster + similarity)
            for rec in recommendations:
                rec['combined_score'] = (
                    0.7 * rec.get('weighted_score', 0) +
                    0.3 * rec.get('similarity_score', 0)
                )

            recommendations.sort(key=lambda x: x['combined_score'], reverse=True)

        except Exception as e:
            print(f"⚠️  Error enriching with similarity scores: {e}")

        return recommendations

    def _calculate_multimodal_similarity(self, embeddings1: Dict, embeddings2: Dict) -> float:
        """Calculate multimodal similarity between two questions"""
        try:
            similarities = []
            weights = []

            # OpenAI embedding similarity
            if embeddings1.get('openai_embedding') and embeddings2.get('openai_embedding'):
                emb1 = np.array(embeddings1['openai_embedding'])
                emb2 = np.array(embeddings2['openai_embedding'])
                sim = 1 - np.linalg.norm(emb1 - emb2) / (np.linalg.norm(emb1) + np.linalg.norm(emb2))
                similarities.append(sim)
                weights.append(0.6)

            # UMAP embedding similarity
            if embeddings1.get('umap_embedding') and embeddings2.get('umap_embedding'):
                emb1 = np.array(embeddings1['umap_embedding'])
                emb2 = np.array(embeddings2['umap_embedding'])
                sim = 1 - np.linalg.norm(emb1 - emb2) / (np.linalg.norm(emb1) + np.linalg.norm(emb2))
                similarities.append(sim)
                weights.append(0.2)

            # Cluster similarity
            if embeddings1.get('soft_cluster') and embeddings2.get('soft_cluster'):
                cluster1 = np.array(embeddings1['soft_cluster'])
                cluster2 = np.array(embeddings2['soft_cluster'])
                sim = np.dot(cluster1, cluster2) / (np.linalg.norm(cluster1) * np.linalg.norm(cluster2))
                similarities.append(sim)
                weights.append(0.2)

            if similarities:
                return np.average(similarities, weights=weights)
            return 0.0

        except Exception as e:
            print(f"Error calculating similarity: {e}")
            return 0.0

    def _get_default_recommendations_db(self, top_k: int) -> List[Dict[str, Any]]:
        """Get default recommendations from database"""
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=self.db_manager.RealDictCursor)

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

    def analyze_student_performance(self, student_id: str) -> Dict[str, Any]:
        """Comprehensive student performance analysis using both ML and DB"""
        try:
            # Get student history
            student_history = self.db_manager.get_student_history_optimized(
                student_id=int(student_id) if student_id.isdigit() else self._extract_student_number(student_id)
            )

            if not student_history:
                return {"error": "No student history found"}

            # Convert to ML format for analysis
            ml_attempts = self._convert_db_history_to_ml_format(student_history)

            # Cluster-based performance analysis
            cluster_performance = {}
            for attempt in ml_attempts:
                question_id = attempt['question_id']
                question_idx = self.question_mapping.get(question_id)

                if question_idx is not None:
                    primary_cluster = np.argmax(self.soft_clusters[question_idx])

                    if primary_cluster not in cluster_performance:
                        cluster_performance[primary_cluster] = {
                            'total': 0, 'correct': 0, 'total_time': 0,
                            'confidence_sum': 0
                        }

                    stats = cluster_performance[primary_cluster]
                    stats['total'] += 1
                    stats['total_time'] += attempt['time_spent_sec']
                    stats['confidence_sum'] += attempt['confidence_level']

                    if attempt['is_correct']:
                        stats['correct'] += 1

            # Calculate metrics
            performance_metrics = {}
            for cluster_id, stats in cluster_performance.items():
                if stats['total'] > 0:
                    performance_metrics[cluster_id] = {
                        'success_rate': stats['correct'] / stats['total'],
                        'avg_time': stats['total_time'] / stats['total'],
                        'avg_confidence': stats['confidence_sum'] / stats['total'],
                        'total_attempts': stats['total']
                    }

            # Overall metrics
            total_attempts = len(ml_attempts)
            correct_attempts = sum(1 for a in ml_attempts if a['is_correct'])

            return {
                'student_id': student_id,
                'total_attempts': total_attempts,
                'overall_success_rate': correct_attempts / total_attempts if total_attempts > 0 else 0,
                'cluster_performance': performance_metrics,
                'recent_activity': ml_attempts[:10],  # Last 10 attempts
                'analysis_timestamp': time.time()
            }

        except Exception as e:
            print(f"Error analyzing student performance: {e}")
            return {"error": str(e)}

    def get_system_health(self) -> Dict[str, Any]:
        """Get comprehensive system health metrics"""
        try:
            health = {
                'timestamp': time.time(),
                'uptime_seconds': time.time() - self.start_time,
                'database_status': 'unknown',
                'redis_status': 'unknown',
                'ml_components_status': 'unknown'
            }

            # Test database
            try:
                with self.db_manager.get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM questions")
                    question_count = cursor.fetchone()[0]
                    health['database_status'] = 'healthy'
                    health['total_questions'] = question_count
            except Exception as e:
                health['database_status'] = f'error: {e}'

            # Test Redis
            try:
                self.db_manager.redis_client.ping()
                health['redis_status'] = 'healthy'
                if self.performance_monitor:
                    health.update(self.performance_monitor.get_system_metrics())
            except Exception as e:
                health['redis_status'] = f'error: {e}'

            # Test ML components
            try:
                health['ml_components_status'] = 'healthy'
                health['clusters_loaded'] = self.soft_clusters.shape[1]
                health['transition_matrix_shape'] = self.transition_matrix.shape if self.transition_matrix is not None else None
            except Exception as e:
                health['ml_components_status'] = f'error: {e}'

            return health

        except Exception as e:
            return {'error': f'Health check failed: {e}'}

    def migrate_legacy_data(self, source_type: str = 'parquet') -> Dict[str, Any]:
        """Migrate data from legacy format to optimized database"""
        print("🔄 Starting data migration...")
        migration_stats = {
            'start_time': time.time(),
            'questions_migrated': 0,
            'embeddings_cached': 0,
            'errors': []
        }

        try:
            if source_type == 'parquet':
                # Migrate from existing parquet files
                # This would integrate with the existing create_normalized_schema.py
                from create_normalized_schema import create_normalized_schema
                from data_import_postgresql import PostgreSQLDataImporter

                # Find latest student history file
                import glob
                files = glob.glob("student_history_enhanced_*.csv")
                if files:
                    latest_file = max(files, key=os.path.getctime)
                    print(f"📂 Using latest student history file: {latest_file}")

                    # Create normalized tables
                    normalized_tables = create_normalized_schema(latest_file)

                    # Import to PostgreSQL
                    importer = PostgreSQLDataImporter(
                        f"postgresql://{self.config.db_config['user']}:{self.config.db_config['password']}@{self.config.db_config['host']}:{self.config.db_config['port']}/{self.config.db_config['database']}"
                    )

                    success = importer.run_full_import()
                    if success:
                        migration_stats['status'] = 'completed'
                    else:
                        migration_stats['status'] = 'failed'
                        migration_stats['errors'].append('PostgreSQL import failed')

            migration_stats['duration_seconds'] = time.time() - migration_stats['start_time']
            return migration_stats

        except Exception as e:
            migration_stats['status'] = 'error'
            migration_stats['error'] = str(e)
            migration_stats['duration_seconds'] = time.time() - migration_stats['start_time']
            return migration_stats

    def shutdown(self):
        """Graceful system shutdown"""
        print("🛑 Shutting down Human Capital Development System...")

        try:
            # Close database connections
            # Note: Context managers handle individual connections

            # Close Redis connections
            if hasattr(self, 'db_manager') and self.db_manager.redis_client:
                self.db_manager.redis_client.close()

            print("✅ System shutdown completed")

        except Exception as e:
            print(f"⚠️  Error during shutdown: {e}")


def create_default_config() -> SystemConfig:
    """Create default system configuration"""
    return SystemConfig(
        db_config={
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', 5432)),
            'database': os.getenv('DB_NAME', 'human_capital_dev'),
            'user': os.getenv('DB_USER', 'hcd_user'),
            'password': os.getenv('DB_PASSWORD', 'your_secure_password_here')
        },
        redis_config={
            'host': os.getenv('REDIS_HOST', 'localhost'),
            'port': int(os.getenv('REDIS_PORT', 6379)),
            'db': int(os.getenv('REDIS_DB', 0)),
            'decode_responses': True
        },
        use_multimodal_embeddings=True,
        cache_ttl_seconds=600,
        default_similarity_threshold=0.7,
        max_concurrent_users=1000,
        enable_performance_monitoring=True,
        debug_mode=os.getenv('DEBUG', 'false').lower() == 'true'
    )


def main():
    """Example usage and testing"""
    print("🚀 Human Capital Development System - Demo")
    print("=" * 60)

    try:
        # Initialize system
        config = create_default_config()
        system = HumanCapitalDevelopmentSystem(config)

        # Health check
        health = system.get_system_health()
        print(f"🏥 System Health: {health}")

        # Test recommendations
        test_student_id = "1"
        print(f"\n🎯 Testing recommendations for student {test_student_id}...")

        recommendations = system.get_recommendations_optimized(
            student_id=test_student_id,
            objective='balanced',
            top_k=5
        )

        print(f"📋 Generated {len(recommendations)} recommendations:")
        for i, rec in enumerate(recommendations[:3], 1):
            print(f"   {i}. Question {rec.get('question_id', 'N/A')} "
                  f"(Cluster: {rec.get('dominant_cluster', 'N/A')}, "
                  f"Score: {rec.get('combined_score', rec.get('weighted_score', 0)):.3f})")

        # Performance analysis
        print(f"\n📊 Analyzing student performance...")
        performance = system.analyze_student_performance(test_student_id)
        if 'error' not in performance:
            print(f"   Total attempts: {performance['total_attempts']}")
            print(f"   Overall success rate: {performance['overall_success_rate']:.1%}")
            print(f"   Clusters analyzed: {len(performance['cluster_performance'])}")

        print(f"\n✅ Demo completed successfully!")

        # Graceful shutdown
        system.shutdown()

    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
