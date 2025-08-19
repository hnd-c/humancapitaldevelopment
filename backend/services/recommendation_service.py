"""
Complete Recommendation Engine
Integrates enriched vectors + transition matrix to recommend specific questions
"""

import numpy as np
import pandas as pd
from ml.vector_encoder import RichVectorEncoder, load_student_history_normalized
import time
from psycopg2.extras import RealDictCursor


class OptimizedRecommendationEngine:
    def __init__(self, db_manager, cache_service=None, lazy_load=False):
        """Initialize the complete recommendation system with caching support"""
        print("🚀 Initializing Recommendation Engine...")

        self.db = db_manager
        self.cache_service = cache_service
        self.lazy_load = lazy_load
        self._initialized = False

        # Initialize basic attributes regardless of lazy loading
        self.questions_df = None
        self.soft_clusters = None
        self.question_mapping = None
        self.transition_matrix = None
        self.encoder = None

        # Initialize cache service if not provided
        if not self.cache_service:
            try:
                from services.cache_service import CacheService
                self.cache_service = CacheService(self.db.redis_client, self.db)
            except Exception as e:
                print(f"⚠️ Could not initialize cache service: {e}")
                self.cache_service = None

        if not lazy_load:
            self._full_initialization()
        else:
            print("⚡ Using lazy loading - components will initialize on first use")

    def _full_initialization(self):
        """Perform full initialization of all components"""
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

        # Initialize components (optional)
        try:
            self.encoder = RichVectorEncoder(self.soft_clusters, self.question_mapping, self.db)
            print("✅ Initialized RichVectorEncoder")
        except Exception as e:
            print(f"⚠️ Could not initialize RichVectorEncoder: {e}")
            self.encoder = None

        if self.transition_matrix is not None:
            print("✅ Initialized transition matrix")
        else:
            print("⚠️ No transition matrix - will use direct cluster-based recommendations")

        self._initialized = True
        print("✅ Recommendation engine ready")

    def _ensure_initialized(self):
        """Ensure components are initialized before use"""
        if not self._initialized:
            self._full_initialization()

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
        # Check cache first - using JSON serialization for better reliability
        cache_key = "questions_data_v2"
        try:
            cached_data = self.db.redis_client.get(cache_key)
            if cached_data:
                import json
                cached_json = json.loads(cached_data)
                # Reconstruct DataFrame from cached JSON
                df = pd.DataFrame(cached_json['data'])

                # Convert vector columns back to numpy arrays
                for col in ['soft_cluster', 'openai_embedding', 'umap_embedding']:
                    if col in df.columns:
                        df[col] = df[col].apply(lambda x: np.array(x, dtype=np.float32) if x is not None else None)

                print(f"✅ Loaded {len(df)} questions from cache (JSON)")
                return df
        except Exception as e:
            print(f"⚠️ Cache miss for questions data: {e}")

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
                        except Exception:
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

                # Cache using JSON serialization (more reliable than pickle)
                try:
                    import json
                    # Convert DataFrame to JSON-serializable format
                    cache_data = {
                        'data': df.copy().to_dict('records'),
                        'cached_at': time.time(),
                        'count': len(df)
                    }

                    # Convert numpy arrays to lists for JSON serialization
                    for record in cache_data['data']:
                        for col in ['soft_cluster', 'openai_embedding', 'umap_embedding']:
                            if col in record and record[col] is not None:
                                if hasattr(record[col], 'tolist'):
                                    record[col] = record[col].tolist()

                    cached_json = json.dumps(cache_data, default=str)
                    self.db.redis_client.setex(cache_key, 1800, cached_json)  # 30 minutes
                    print(f"💾 Cached questions dataframe (JSON) for faster startup")
                except Exception as e:
                    print(f"⚠️ Could not cache questions data: {e}")

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
            # Use the updated transition matrix function with database support
            from ml.transition_matrix import _build_cooccurrence_transitions

            # Get soft clusters from the already loaded questions_df
            if hasattr(self, 'soft_clusters') and self.soft_clusters is not None:
                print(f"🔄 Building transition matrix using loaded soft clusters")
                T = _build_cooccurrence_transitions(
                    alpha=alpha,
                    normalize=normalize,
                    soft_clusters=self.soft_clusters,
                    db_manager=self.db
                )
            else:
                print(f"🔄 Building transition matrix from database")
                T = _build_cooccurrence_transitions(
                    alpha=alpha,
                    normalize=normalize,
                    db_manager=self.db
                )

            if T is not None:
                print(f"✅ Built transition matrix with shape {T.shape}")
            else:
                print(f"❌ Failed to build transition matrix")

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

    def recommend_questions_optimized(self, student_id, objective='balanced', top_k=5, use_cache=True):
        """Database-optimized recommendations with proper model integration and caching"""
        from data.models import RecommendationRequest, ModelValidator

        # Validate request using data model
        request = RecommendationRequest(
            student_id=str(student_id),
            objective=objective,
            top_k=top_k,
            use_cache=use_cache
        )

        try:
            ModelValidator.validate_recommendation_request(request)
        except Exception as e:
            print(f"❌ Validation error: {e}")
            return []

        # Ensure components are initialized
        if self.lazy_load:
            self._ensure_initialized()

        # Check cache if enabled
        if use_cache and self.cache_service:
            cached_recommendations = self.cache_service.get_cached_recommendations(
                request.student_id, request.objective
            )
            if cached_recommendations:
                print(f"✅ Using cached recommendations for student {request.student_id}")
                return cached_recommendations

        # Get student history from database
        student_history = self.db.get_student_history_optimized(request.student_id)

        if not student_history:
            print("📋 No student history found, using default recommendations")
            recommendations = self._get_default_recommendations_db(request.top_k)
        else:
            # Get current state using database operations
            current_state = self._encode_student_context_db(
                request.student_id, student_history, request.objective
            )

            # Use PostgreSQL for similarity search
            recommendations = self._find_recommendations_db(
                current_state, student_history, request.top_k
            )

        # Cache recommendations if caching is enabled
        if use_cache and self.cache_service and recommendations:
            self.cache_service.cache_recommendations(
                request.student_id, request.objective, recommendations
            )
            print(f"💾 Cached {len(recommendations)} recommendations for student {request.student_id}")

        return recommendations

    def _encode_student_context_db(self, student_id, student_history, objective='balanced'):
        """Create enriched vector from student history"""
        # Check if enriched vector is cached first
        if hasattr(self.db, 'redis_client'):
            cache_service = getattr(self, '_cache_service', None)
            if not cache_service:
                from services.cache_service import CacheService
                self._cache_service = CacheService(self.db.redis_client, self.db)
                cache_service = self._cache_service

            cached_vector = cache_service.get_cached_enriched_vector(str(student_id), objective)
            if cached_vector is not None:
                print(f"🧠 Using cached enriched vector for student {student_id}")
                return cached_vector

        try:
            print(f"🧠 Encoding context for student {student_id} with {len(student_history)} attempts")

            # Get the number of clusters from our matrix
            n_clusters = 20  # Default
            if hasattr(self, 'transition_matrix') and self.transition_matrix is not None:
                n_clusters = self.transition_matrix.shape[0]

            # Initialize cluster distribution
            cluster_distribution = np.zeros(n_clusters)

            if not student_history:
                print("📋 No history - using uniform distribution")
                return np.ones(n_clusters) / n_clusters

            # Analyze recent vs older attempts (enriched context)
            total_attempts = len(student_history)
            recent_attempts = student_history[:min(10, total_attempts)]  # Last 10 attempts

            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()

                # Get detailed cluster analysis for recent attempts
                recent_ids = [h['internal_question_id'] for h in recent_attempts]

                query = """
                SELECT q.soft_cluster, COUNT(*) as count,
                       AVG(CASE WHEN sqh.is_correct THEN 1.0 ELSE 0.0 END) as success_rate
                FROM questions q
                JOIN student_question_history sqh ON q.internal_question_id = sqh.internal_question_id
                JOIN student_paper_enrollments spe ON sqh.enrollment_id = spe.enrollment_id
                WHERE q.internal_question_id = ANY(%s) AND spe.student_id = %s
                  AND q.soft_cluster IS NOT NULL
                GROUP BY q.soft_cluster
                """

                cursor.execute(query, (recent_ids, student_id))
                results = cursor.fetchall()

                # Build enriched vector based on recent performance
                for row in results:
                    soft_cluster_str = row[0]
                    attempt_count = row[1]
                    success_rate = float(row[2]) if row[2] is not None else 0.0

                    # Parse soft cluster array
                    try:
                        import ast
                        soft_cluster = ast.literal_eval(soft_cluster_str)

                        # Weight by recency and success rate
                        base_weight = attempt_count * (0.5 + success_rate)

                        # Distribute weight across all clusters based on membership strength
                        for cluster_id, membership in enumerate(soft_cluster):
                            if cluster_id < n_clusters and membership > 0.1:  # Threshold for meaningful membership
                                weight = base_weight * membership
                                cluster_distribution[cluster_id] += weight

                                # Add adjacent cluster influence (transition tendency)
                                if cluster_id > 0:
                                    cluster_distribution[cluster_id - 1] += weight * 0.1
                                if cluster_id < n_clusters - 1:
                                    cluster_distribution[cluster_id + 1] += weight * 0.1
                    except Exception as e:
                        print(f"⚠️ Could not parse soft cluster: {soft_cluster_str}")

                # Normalize
                if cluster_distribution.sum() > 0:
                    cluster_distribution = cluster_distribution / cluster_distribution.sum()
                else:
                    cluster_distribution = np.ones(n_clusters) / n_clusters

                # Objective-based adjustment
                if objective == 'coverage':
                    # Boost underexplored clusters
                    weak_clusters = cluster_distribution < 0.1
                    cluster_distribution[weak_clusters] += 0.1
                elif objective == 'efficiency':
                    # Focus on strong clusters
                    cluster_distribution = cluster_distribution ** 2

                # Final normalization
                cluster_distribution = cluster_distribution / cluster_distribution.sum()

                print(f"✅ Created enriched vector - top clusters: {np.argsort(cluster_distribution)[-3:][::-1]}")

                # Cache the computed enriched vector
                if hasattr(self, '_cache_service'):
                    self._cache_service.cache_enriched_vector(str(student_id), objective, cluster_distribution)

                return cluster_distribution

        except Exception as e:
            print(f"❌ Error encoding student context: {e}")
            # Return uniform distribution as fallback
            return np.ones(20) / 20

    def _find_recommendations_db(self, current_state, student_history, top_k):
        """Find recommendations using student context and transition matrix"""
        attempted_questions = {h['internal_question_id'] for h in student_history}

        try:
            # Step 1: Use transition matrix to find next promising clusters
            if hasattr(self, 'transition_matrix') and self.transition_matrix is not None:
                # Get next cluster probabilities
                next_cluster_probs = np.dot(current_state, self.transition_matrix)
                # Get top 3 cluster indices
                top_clusters = np.argsort(next_cluster_probs)[-3:][::-1]
                print(f"🎯 Recommending from clusters: {top_clusters}")
            else:
                # Fallback: use current strong clusters as probabilities
                next_cluster_probs = current_state
                top_clusters = np.argsort(current_state)[-3:][::-1]
                print(f"🎯 Using current strong clusters: {top_clusters}")

            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)

                # Step 2: Get more questions for better scoring
                query = """
                SELECT q.internal_question_id, q.question_id, q.paper_id,
                       q.soft_cluster, q.combined_text
                FROM questions q
                WHERE q.internal_question_id NOT IN %s
                  AND q.soft_cluster IS NOT NULL
                ORDER BY RANDOM()
                LIMIT %s
                """

                cursor.execute(query, (
                    tuple(attempted_questions) if attempted_questions else (0,),
                    min(100, top_k * 20)  # Get many questions to score
                ))

                results = cursor.fetchall()
                print(f"📊 Retrieved {len(results)} questions for scoring")

                # Step 3: Score questions using cluster priorities (CORE ALGORITHM!)
                scored_questions = []
                for row in results:
                    if row['soft_cluster']:
                        try:
                            import ast
                            question_clusters = np.array(ast.literal_eval(row['soft_cluster']), dtype=float)

                            # Ensure both arrays have the same length
                            min_len = min(len(question_clusters), len(next_cluster_probs))
                            if min_len > 0:
                                q_clusters = question_clusters[:min_len]
                                n_probs = next_cluster_probs[:min_len]

                                # CORE ALGORITHM: Score = weighted sum of cluster priorities
                                score = np.sum(q_clusters * n_probs)

                                primary_cluster = np.argmax(q_clusters)
                                cluster_strength = np.max(q_clusters)

                                # Create proper Recommendation model instance
                                from data.models import Recommendation
                                recommendation = Recommendation(
                                    question_id=row['question_id'],
                                    internal_question_id=row['internal_question_id'],
                                    paper_id=row['paper_id'],
                                    weighted_score=float(score),
                                    dominant_cluster=int(primary_cluster),
                                    similarity_score=float(cluster_strength),
                                    combined_score=float(score),
                                    reasoning=f'ML-scored: {score:.3f} alignment with learning path'
                                )
                                scored_questions.append(recommendation)
                        except Exception as e:
                            print(f"⚠️ Could not score question {row['question_id']}: {e}")

                # Sort by score (highest first) and take top_k
                if scored_questions:
                    scored_questions.sort(key=lambda x: x.weighted_score, reverse=True)
                    recommendations = scored_questions[:top_k]

                    print(f"🎯 Scored {len(scored_questions)} questions, selected top {len(recommendations)}")
                    for i, rec in enumerate(recommendations, 1):
                        print(f"   {i}. Q{rec.question_id}: Score={rec.weighted_score:.3f}, Cluster={rec.dominant_cluster}")

                    return recommendations
                else:
                    print("⚠️ No questions could be scored, using fallback")
                    return self._get_simple_fallback_recommendations(attempted_questions, top_k)

        except Exception as e:
            print(f"❌ Error in _find_recommendations_db: {e}")
            # Fallback to simple random selection
            return self._get_simple_fallback_recommendations(attempted_questions, top_k)

    def _get_simple_fallback_recommendations(self, attempted_questions, top_k):
        """Simple fallback when main recommendation logic fails"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)

                query = """
                SELECT internal_question_id, question_id, paper_id, soft_cluster
                FROM questions
                WHERE internal_question_id NOT IN %s
                  AND soft_cluster IS NOT NULL
                ORDER BY RANDOM()
                LIMIT %s
                """

                cursor.execute(query, (
                    tuple(attempted_questions) if attempted_questions else (0,),
                    top_k
                ))

                results = cursor.fetchall()
                recommendations = []
                for row in results:
                    # Calculate primary cluster from soft_cluster
                    primary_cluster = 0
                    if row['soft_cluster']:
                        try:
                            import ast
                            cluster_array = ast.literal_eval(row['soft_cluster'])
                            primary_cluster = cluster_array.index(max(cluster_array))
                        except:
                            primary_cluster = 0

                    # Create proper Recommendation model instance for fallback
                    from data.models import Recommendation
                    recommendation = Recommendation(
                        question_id=row['question_id'],
                        internal_question_id=row['internal_question_id'],
                        paper_id=row['paper_id'],
                        weighted_score=0.5,
                        dominant_cluster=primary_cluster,
                        similarity_score=0.5,
                        combined_score=0.5,
                        reasoning='Random fallback recommendation'
                    )
                    recommendations.append(recommendation)

                return recommendations

        except Exception as e:
            print(f"❌ Even fallback failed: {e}")
            return []

    def _get_default_recommendations_db(self, top_k):
        """Fallback recommendations when no student history"""
        print(f"📋 Using default recommendations for {top_k} questions...")

        # Use database instead of dataframe
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)

                # Get random questions from different clusters
                query = """
                SELECT internal_question_id, question_id, paper_id, soft_cluster
                FROM questions
                WHERE soft_cluster IS NOT NULL
                ORDER BY RANDOM()
                LIMIT %s
                """

                cursor.execute(query, (top_k,))
                results = cursor.fetchall()

                print(f"📊 Found {len(results)} questions for default recommendations")

                recommendations = []
                for row in results:
                    # Calculate primary cluster
                    primary_cluster = 0
                    if row['soft_cluster']:
                        try:
                            import ast
                            cluster_array = ast.literal_eval(row['soft_cluster'])
                            primary_cluster = cluster_array.index(max(cluster_array))
                        except:
                            primary_cluster = 0

                    # Create proper Recommendation model instance for default
                    from data.models import Recommendation
                    recommendation = Recommendation(
                        question_id=row['question_id'],
                        internal_question_id=row['internal_question_id'],
                        paper_id=row['paper_id'],
                        weighted_score=1.0,
                        dominant_cluster=primary_cluster,
                        similarity_score=1.0,
                        combined_score=1.0,
                        reasoning='Default recommendation for new student'
                    )
                    recommendations.append(recommendation)

                print(f"✅ Generated {len(recommendations)} default recommendations")
                return recommendations

        except Exception as e:
            print(f"❌ Error getting default recommendations: {e}")
            return []

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
