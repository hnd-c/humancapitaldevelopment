"""
Complete Recommendation Engine
Integrates enriched vectors + transition matrix to recommend specific questions
"""

import numpy as np
import pandas as pd
from ml.vector_encoder import RichVectorEncoder, load_student_history_normalized, create_question_mapping_from_normalized
from ml.transition_matrix import _build_cooccurrence_transitions, recommend_next_clusters
from data.database_manager import DatabaseManager
import json
from psycopg2.extras import RealDictCursor


class OptimizedRecommendationEngine:
    def __init__(self, db_manager):
        """Initialize the complete recommendation system"""
        print("🚀 Initializing Recommendation Engine...")

        self.db = db_manager

        # Load question data and clusters from PostgreSQL database first
        try:
            self.questions_df = self._load_questions_from_database()
            if not self.questions_df.empty:
                self.soft_clusters = np.stack(self.questions_df['soft_cluster'].values)
                print(f"✅ Loaded {len(self.questions_df)} questions with {self.soft_clusters.shape[1]} clusters from database")

                # Create question mapping for string IDs
                self.question_mapping = self._create_question_mapping()
            else:
                print("❌ No questions found in database!")
                raise ValueError("No questions available in database")

        except Exception as e:
            print(f"❌ Error loading question data from database: {e}")
            raise

        # Now load or build transition matrix (after questions_df is available)
        self.transition_matrix = self._load_or_build_transition_matrix()

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

    def _load_questions_from_database(self):
        """Load question data with embeddings from PostgreSQL database"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=self.db.RealDictCursor)

                # Query to get questions with all their embeddings and metadata
                query = """
                SELECT
                    internal_question_id,
                    question_id,
                    paper_id,
                    question_number,
                    openai_embedding,
                    umap_embedding,
                    soft_cluster,
                    combined_text,
                    embedding_model,
                    embedding_created_at,
                    created_at
                FROM questions
                WHERE soft_cluster IS NOT NULL
                ORDER BY internal_question_id
                """

                cursor.execute(query)
                results = cursor.fetchall()

                if not results:
                    print("⚠️  No questions with embeddings found in database")
                    return pd.DataFrame()

                # Convert to DataFrame
                df = pd.DataFrame(results)

                # Convert vector strings to numpy arrays
                def parse_vector(vector_str):
                    if isinstance(vector_str, str):
                        # Parse string like '[0,0,0,1,0,...]' to numpy array
                        import ast
                        try:
                            return np.array(ast.literal_eval(vector_str), dtype=np.float32)
                        except:
                            return None
                    return vector_str

                # Apply vector conversion to embedding columns
                if 'soft_cluster' in df.columns:
                    df['soft_cluster'] = df['soft_cluster'].apply(parse_vector)

                if 'openai_embedding' in df.columns:
                    df['openai_embedding'] = df['openai_embedding'].apply(parse_vector)

                if 'umap_embedding' in df.columns:
                    df['umap_embedding'] = df['umap_embedding'].apply(parse_vector)

                # Extract paper_number from question_id
                # Assuming question_id format is like "9702_m16_qp_12_1"
                df['paper_number'] = df['question_id'].str.extract(r'(\d+_[a-z]\d+_qp_\d+)')

                # question_number is already a separate column in the database
                # Ensure it's treated as string for consistency with existing code
                df['question_number'] = df['question_number'].astype(str)

                print(f"✅ Loaded {len(df)} questions from PostgreSQL database")
                return df

        except Exception as e:
            print(f"❌ Error loading questions from database: {e}")
            return pd.DataFrame()

    def _load_or_build_transition_matrix(self):
        """Load transition matrix from PostgreSQL database"""
        try:
            # First try to load from database
            matrix = self._load_transition_matrix_from_database()
            if matrix is not None:
                return matrix

            # If no matrix in database, build one from the question data
            print("🔄 No transition matrix in database, building from data...")
            matrix = self._build_transition_matrix_from_database(alpha=0.1, normalize=True)

            if matrix is not None:
                # Optionally save the built matrix back to database
                self._save_transition_matrix_to_database(matrix)

            return matrix

        except Exception as e:
            print(f"❌ Error in transition matrix loading: {e}")
            return None

    def _load_transition_matrix_from_database(self):
        """Load transition matrix from PostgreSQL database"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=self.db.RealDictCursor)

                # Get the most recent active transition matrix
                cursor.execute("""
                    SELECT matrix_data, metadata
                    FROM transition_matrices
                    WHERE is_active = true
                    ORDER BY created_at DESC
                    LIMIT 1
                """)

                result = cursor.fetchone()

                if result:
                    matrix_data = result['matrix_data']
                    metadata = result['metadata']

                    # Reconstruct the numpy matrix
                    import numpy as np
                    matrix = np.array(matrix_data['matrix'])

                    print(f"✅ Loaded transition matrix from database: {matrix.shape}")
                    print(f"   📊 Algorithm: {metadata['algorithm']}")
                    print(f"   📊 N clusters: {metadata['n_clusters']}")

                    return matrix
                else:
                    print("⚠️  No active transition matrix found in database")
                    return None

        except Exception as e:
            print(f"❌ Error loading transition matrix from database: {e}")
            return None

    def _save_transition_matrix_to_database(self, matrix):
        """Save a transition matrix to the PostgreSQL database"""
        try:
            import json
            import hashlib
            import numpy as np

            # Create matrix data structure
            matrix_data = {
                'shape': list(matrix.shape),
                'dtype': str(matrix.dtype),
                'matrix': matrix.tolist()
            }

            # Create metadata
            metadata = {
                'algorithm': 'cooccurrence_transitions',
                'n_clusters': matrix.shape[0],
                'parameters': {'alpha': 0.1, 'normalized': True},
                'source': 'database_questions'
            }

            # Create hash for the matrix
            matrix_str = json.dumps(matrix_data, sort_keys=True)
            source_hash = hashlib.md5(matrix_str.encode()).hexdigest()

            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()

                # Insert the new matrix
                cursor.execute("""
                    INSERT INTO transition_matrices
                    (source_data_hash, matrix_data, metadata, algorithm_name, algorithm_version, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    source_hash,
                    json.dumps(matrix_data),
                    json.dumps(metadata),
                    'cooccurrence_transitions',
                    '1.0',
                    True
                ))

                conn.commit()
                print("✅ Saved transition matrix to database")

        except Exception as e:
            print(f"❌ Error saving transition matrix to database: {e}")

    def _build_transition_matrix_from_database(self, alpha=0.1, normalize=True):
        """Build transition matrix using soft cluster data from database"""
        try:
            # Get soft clusters from the already loaded questions_df
            if not hasattr(self, 'questions_df') or self.questions_df.empty:
                print("❌ No questions data available for transition matrix building")
                return None

            soft_clusters = np.stack(self.questions_df['soft_cluster'].values)
            n_clusters = soft_clusters.shape[1]
            n_questions = soft_clusters.shape[0]

            print(f"🔄 Building transition matrix from {n_questions} questions with {n_clusters} clusters")

            # Initialize transition matrix
            T = np.zeros((n_clusters, n_clusters))

            # Build co-occurrence transitions
            for question_idx in range(n_questions):
                clusters = soft_clusters[question_idx]

                # Get significant clusters (above threshold)
                significant_clusters = np.where(clusters > 0.1)[0]

                # Add transitions between significant clusters
                for i in significant_clusters:
                    for j in significant_clusters:
                        if i != j:
                            # Weight by product of cluster memberships
                            weight = clusters[i] * clusters[j]
                            T[i, j] += weight

            # Add self-loops with alpha
            for i in range(n_clusters):
                T[i, i] += alpha

            # Normalize if requested
            if normalize:
                T = self._normalize_transition_matrix(T)

            print(f"✅ Built transition matrix with shape {T.shape}")
            return T

        except Exception as e:
            print(f"❌ Error building transition matrix from database: {e}")
            return None

    def _normalize_transition_matrix(self, T):
        """Normalize each row to sum to 1 (valid probability distribution)"""
        T_normalized = T.copy()
        for i in range(T.shape[0]):
            row_sum = T_normalized[i].sum()
            if row_sum > 0:
                T_normalized[i] /= row_sum
            else:
                # If no transitions from cluster i, uniform distribution
                T_normalized[i] = np.ones(T.shape[1]) / T.shape[1]
        return T_normalized

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
