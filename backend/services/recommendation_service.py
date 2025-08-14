"""
Complete Recommendation Engine
Integrates enriched vectors + transition matrix to recommend specific questions
"""

import numpy as np
import pandas as pd
from enriched_vector import RichVectorEncoder, load_student_history_normalized, create_question_mapping_from_normalized
from transition_matrix import _build_cooccurrence_transitions, recommend_next_clusters
from database_manager import DatabaseManager
import json
from psycopg2.extras import RealDictCursor


class OptimizedRecommendationEngine:
    def __init__(self, db_manager):
        """Initialize the complete recommendation system"""
        print("🚀 Initializing Recommendation Engine...")

        self.db = db_manager
        self.transition_matrix = self._load_or_build_transition_matrix()

        # Load question data and clusters from combined_questions.parquet
        try:
            self.questions_df = pd.read_parquet("combined_questions.parquet")
            self.soft_clusters = np.stack(self.questions_df['soft_cluster'].values)
            print(f"✅ Loaded {len(self.questions_df)} questions with {self.soft_clusters.shape[1]} clusters")

            # Create question mapping for string IDs
            self.question_mapping = self._create_question_mapping()

        except FileNotFoundError:
            print("❌ combined_questions.parquet not found!")
            print("💡 Make sure the clustering data is available")
            raise
        except Exception as e:
            print(f"❌ Error loading question data: {e}")
            raise

        # Initialize components
        self.encoder = RichVectorEncoder(self.soft_clusters, self.question_mapping)

        if self.transition_matrix is not None:
            print("✅ Initialized encoder and transition matrix")
        else:
            print("❌ Failed to initialize transition matrix")
            raise ValueError("Cannot proceed without transition matrix")

    def _create_question_mapping(self):
        """Create mapping from question_id strings to integer indices"""
        # Reset index to ensure sequential mapping
        questions_indexed = self.questions_df.reset_index(drop=True)

        # Create question_id from paper_number and question_number
        questions_indexed["question_id"] = (
            questions_indexed["paper_number"].astype(str) + "_" +
            questions_indexed["question_number"].astype(str)
        )

        # Create mapping from question_id string to integer index
        question_mapping = {}
        for idx, row in questions_indexed.iterrows():
            question_mapping[row["question_id"]] = idx

        print(f"📋 Created mapping for {len(question_mapping)} questions")
        return question_mapping

    def _load_or_build_transition_matrix(self):
        """Load transition matrix using hybrid storage strategy"""
        try:
            # Import the storage manager
            from transition_matrix_storage import TransitionMatrixManager

            # Get Redis client for vectors (port 6380)
            import redis
            redis_client = redis.Redis(
                host=self.db.redis_config.get('host', 'localhost'),
                port=6380,  # Use vector Redis instance
                db=0
            )

            # Initialize storage manager
            storage_manager = TransitionMatrixManager(redis_client, self.db.db_config)

            # Get matrix using hybrid strategy
            matrix = storage_manager.get_or_compute_matrix(force_rebuild=False)

            if matrix is not None:
                print(f"✅ Loaded transition matrix from storage ({matrix.shape})")
                return matrix
            else:
                print("❌ Failed to load transition matrix from any source")
                return None

        except Exception as e:
            print(f"❌ Error in transition matrix loading: {e}")
            print("🔄 Falling back to direct computation...")

            # Fallback to direct computation
            try:
                from transition_matrix import _build_cooccurrence_transitions
                matrix = _build_cooccurrence_transitions(alpha=0.1, normalize=True)
                print(f"✅ Built transition matrix directly ({matrix.shape if matrix is not None else 'failed'})")
                return matrix
            except Exception as fallback_error:
                print(f"❌ Fallback computation also failed: {fallback_error}")
                return None

    def recommend_questions_optimized(self, student_id, objective='balanced', top_k=5):
        """Database-optimized recommendations with caching"""
        cache_key = f"recommendations:{student_id}:{objective}:{top_k}"

        # Check Redis cache first
        cached = self.db.redis_client.get(cache_key)
        if cached:
            return json.loads(cached)

        # Get student history (cached)
        student_history = self.db.get_student_history_optimized(student_id)

        if not student_history:
            return self._get_default_recommendations_db(top_k)

        # Get current state using database operations
        current_state = self._encode_student_context_db(student_id, student_history, objective)

        # Use PostgreSQL for similarity search
        recommendations = self._find_recommendations_db(current_state, student_history, top_k)

        # Cache recommendations for 10 minutes
        self.db.redis_client.setex(cache_key, 600, json.dumps(recommendations, default=str))

        return recommendations

    def _find_recommendations_db(self, current_state, student_history, top_k):
        """Use PostgreSQL vector operations for recommendations"""
        attempted_questions = {h['internal_question_id'] for h in student_history}

        with self.db.get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Use PostgreSQL's vector operations
            query = """
            WITH cluster_priorities AS (
                SELECT unnest(%s) as priority,
                       generate_series(0, %s) as cluster_id
            ),
            question_scores AS (
                SELECT q.internal_question_id, q.question_id, q.paper_id,
                       -- Calculate score using PostgreSQL vector operations
                       (q.soft_cluster <#> %s::vector) as cluster_alignment_score,
                       -- Get dominant cluster
                       (SELECT i-1 FROM unnest(q.soft_cluster) WITH ORDINALITY arr(val,i)
                        ORDER BY val DESC LIMIT 1) as dominant_cluster
                FROM questions q
                WHERE q.internal_question_id NOT IN %s
                  AND q.soft_cluster IS NOT NULL
            )
            SELECT qs.*, cp.priority as cluster_priority
            FROM question_scores qs
            JOIN cluster_priorities cp ON qs.dominant_cluster = cp.cluster_id
            ORDER BY qs.cluster_alignment_score ASC, cp.priority DESC
            LIMIT %s
            """

            cursor.execute(query, (
                current_state.tolist(),
                len(current_state) - 1,
                current_state.tolist(),
                tuple(attempted_questions) if attempted_questions else (0,),
                top_k
            ))

            return cursor.fetchall()

    def _get_default_recommendations_db(self, top_k):
        """Fallback recommendations when no student history"""
        print("📋 Using default recommendations...")

        # Recommend questions from different clusters for diversity
        cluster_questions = {}
        for q_idx in range(min(1000, len(self.questions_df))):  # Limit for performance
            primary_cluster = np.argmax(self.soft_clusters[q_idx])
            if primary_cluster not in cluster_questions:
                cluster_questions[primary_cluster] = []

            question_row = self.questions_df.iloc[q_idx]
            question_id = f"{question_row['paper_number']}_{question_row['question_number']}"
            cluster_questions[primary_cluster].append({
                'question_id': question_id,
                'question_index': q_idx,
                'paper_number': question_row['paper_number'],
                'question_number': question_row['question_number']
            })

        # Sample one question from each of the first top_k clusters
        recommendations = []
        for cluster_id in sorted(cluster_questions.keys())[:top_k]:
            if cluster_questions[cluster_id]:
                question_data = np.random.choice(cluster_questions[cluster_id])
                recommendations.append({
                    'question_id': question_data['question_id'],
                    'question_index': question_data['question_index'],
                    'score': 1.0,
                    'primary_cluster': cluster_id,
                    'cluster_strength': 1.0,
                    'paper_number': question_data['paper_number'],
                    'question_number': question_data['question_number']
                })

        return recommendations

    def analyze_recommendations(self, student_id, objectives=['coverage', 'efficiency', 'success_rate', 'balanced']):
        """Compare recommendations across different objectives"""
        print(f"\n🔬 Analyzing recommendations for {student_id} across objectives...")

        all_recommendations = {}
        for objective in objectives:
            try:
                recs = self.recommend_questions(student_id, objective, top_k=3)
                all_recommendations[objective] = [r['question_id'] for r in recs]
                print(f"\n{objective.upper()}: Questions {all_recommendations[objective]}")
            except Exception as e:
                print(f"❌ Error with {objective} objective: {e}")
                all_recommendations[objective] = []

        # Find overlap
        all_questions = set()
        for questions in all_recommendations.values():
            all_questions.update(questions)

        print(f"\n📊 Analysis:")
        print(f"   Total unique questions: {len(all_questions)}")

        # Find questions that appear in multiple objectives
        question_counts = {}
        for questions in all_recommendations.values():
            for q in questions:
                question_counts[q] = question_counts.get(q, 0) + 1

        popular_questions = [q for q, count in question_counts.items() if count > 1]
        if popular_questions:
            print(f"   Questions appearing in multiple objectives: {popular_questions}")
        else:
            print(f"   No questions appear in multiple objectives (high diversity)")

        return all_recommendations

    def get_question_details(self, question_id):
        """Get detailed information about a specific question"""
        try:
            question_idx = self.question_mapping.get(question_id)
            if question_idx is None:
                return None

            question_row = self.questions_df.iloc[question_idx]
            cluster_membership = self.soft_clusters[question_idx]

            # Fix array comparison bug
            def safe_has_data(value):
                """Safely check if data exists, handling arrays/lists"""
                try:
                    # Handle arrays/lists first before pd.isna check
                    if isinstance(value, (list, np.ndarray)):
                        return len(value) > 0
                    elif isinstance(value, str):
                        return len(value.strip()) > 0
                    elif pd.isna(value):
                        return False
                    else:
                        return value is not None
                except:
                    # Fallback for any edge cases
                    return value is not None and value != ""

            return {
                'question_id': question_id,
                'paper_number': question_row['paper_number'],
                'question_number': question_row['question_number'],
                'primary_cluster': np.argmax(cluster_membership),
                'cluster_distribution': cluster_membership,
                'top_3_clusters': np.argsort(cluster_membership)[-3:][::-1],
                'has_text': safe_has_data(question_row.get('combined_text')),
                'has_images': safe_has_data(question_row.get('images'))
            }
        except Exception as e:
            print(f"❌ Error getting question details: {e}")
            return None

    def explain_recommendation(self, student_id, question_id, objective='balanced'):
        """Explain why a specific question was recommended"""
        print(f"\n🔍 Explaining recommendation: {question_id} for {student_id}")

        # Get question details
        question_details = self.get_question_details(question_id)
        if not question_details:
            print(f"❌ Question {question_id} not found")
            return

        print(f"📝 Question Details:")
        print(f"   Paper: {question_details['paper_number']}")
        print(f"   Primary Cluster: {question_details['primary_cluster']}")
        print(f"   Top 3 Clusters: {question_details['top_3_clusters']}")

        # Load student history and create state
        try:
            if isinstance(student_id, str) and "_STU_" in student_id:
                base_number = int(student_id.split("_STU_")[-1])
            else:
                base_number = int(student_id)

            student_attempts = load_student_history_normalized(base_number)

            if student_attempts:
                current_question = student_attempts[-1]['question_id']
                current_state = self.encoder.encode_student_context(
                    current_question=current_question,
                    student_attempts=student_attempts,
                    objective=objective
                )

                print(f"\n🧠 Student State Analysis:")
                print(f"   Last attempted: {current_question}")
                print(f"   Strong clusters: {np.argsort(current_state)[-3:]}")
                print(f"   Objective: {objective}")

                # Show why this question matches
                question_cluster_strength = question_details['cluster_distribution']
                alignment_score = np.sum(current_state * question_cluster_strength)
                print(f"   Alignment score: {alignment_score:.3f}")

        except Exception as e:
            print(f"⚠️  Could not load student analysis: {e}")


def main():
    """Example usage of the complete recommendation system"""
    print("🚀 COMPLETE RECOMMENDATION ENGINE DEMO")
    print("=" * 60)

    try:
        # Initialize the engine
        engine = OptimizedRecommendationEngine()

        # Test with student (use base student number or full ID)
        test_students = [1, "SXC_AL_Y1_B_PHY_P1_STU_001"]

        for student_id in test_students:
            print(f"\n{'='*60}")
            print(f"🎓 Testing with student: {student_id}")

            try:
                # Get recommendations for different objectives
                recommendations = engine.analyze_recommendations(student_id)

                # Deep dive into one objective
                print(f"\n🔍 Detailed recommendation for BALANCED objective:")
                detailed_recs = engine.recommend_questions(student_id, 'balanced', top_k=5)

                # Explain first recommendation
                if detailed_recs:
                    first_rec = detailed_recs[0]
                    engine.explain_recommendation(student_id, first_rec['question_id'], 'balanced')

            except Exception as e:
                print(f"❌ Error testing student {student_id}: {e}")
                continue

        print(f"\n✅ RECOMMENDATION ENGINE DEMO COMPLETED!")
        print("=" * 60)
        print(f"🎯 Integration Ready:")
        print(f"   ✅ Enriched vector encoding")
        print(f"   ✅ Transition matrix pathways")
        print(f"   ✅ Multi-objective optimization")
        print(f"   ✅ Question scoring & ranking")
        print(f"   ✅ Explanation & transparency")

        return engine

    except Exception as e:
        print(f"❌ Failed to initialize recommendation engine: {e}")
        print(f"💡 Check that required files exist:")
        print(f"   • combined_questions.parquet")
        print(f"   • normalized_*_*.parquet files")
        return None


if __name__ == "__main__":
    engine = main()
