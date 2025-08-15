#!/usr/bin/env python3
"""
Vector Operations Manager - Unified vector operations and similarity calculations

This module consolidates all vector operations from:
- data/repositories.py (VectorOperations class)
- ml/embeddings.py (EmbeddingManager class) 
- ml/similarity.py (SimilarityCalculator class)

Provides single authoritative implementation for:
- Vector embedding operations
- Multimodal similarity calculations
- Cluster-based recommendations
- Batch similarity computations
"""

import numpy as np
from typing import List, Dict, Optional, Tuple, Any
from psycopg2.extras import RealDictCursor
import logging

logger = logging.getLogger(__name__)


class VectorOperationsManager:
    """Unified manager for all vector operations and similarity calculations"""

    def __init__(self, db_manager, cache_service=None):
        self.db = db_manager
        self.cache = cache_service
        logger.info("Initialized VectorOperationsManager with caching support")

    # ==========================================
    # EMBEDDING OPERATIONS
    # ==========================================

    def get_embeddings(self, question_id: str) -> Optional[Dict[str, Any]]:
        """Get all embeddings for a specific question with caching support"""
        try:
            # Try cache first if available
            if self.cache:
                cached_embeddings = self.cache.get_or_compute(
                    cache_key=f"embeddings:{question_id}",
                    compute_function=self._fetch_embeddings_from_db,
                    ttl=3600,  # 1 hour
                    question_id=question_id
                )
                return cached_embeddings

            # Fallback to direct DB query
            return self._fetch_embeddings_from_db(question_id)

        except Exception as e:
            logger.error(f"Error getting embeddings for {question_id}: {e}")
            return None

    def _fetch_embeddings_from_db(self, question_id: str) -> Optional[Dict[str, Any]]:
        """Fetch embeddings directly from database"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)

                query = """
                SELECT internal_question_id, question_id,
                       openai_embedding, umap_embedding, soft_cluster,
                       text_length, embedding_model
                FROM questions
                WHERE question_id = %s
                """

                cursor.execute(query, (question_id,))
                result = cursor.fetchone()

                if result:
                    return dict(result)
                return None

        except Exception as e:
            logger.error(f"Database error fetching embeddings for {question_id}: {e}")
            return None

    def update_question_embeddings(self, question_id: str,
                                 openai_embedding: Optional[List[float]] = None,
                                 umap_embedding: Optional[List[float]] = None,
                                 soft_cluster: Optional[List[float]] = None) -> bool:
        """Update embeddings for a specific question"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()

                updates = []
                params = []

                if openai_embedding is not None:
                    updates.append("openai_embedding = %s")
                    params.append(openai_embedding)

                if umap_embedding is not None:
                    updates.append("umap_embedding = %s")
                    params.append(umap_embedding)

                if soft_cluster is not None:
                    updates.append("soft_cluster = %s")
                    params.append(soft_cluster)

                if not updates:
                    return False

                updates.append("updated_at = CURRENT_TIMESTAMP")
                params.append(question_id)

                query = f"""
                UPDATE questions
                SET {', '.join(updates)}
                WHERE question_id = %s
                """

                cursor.execute(query, params)
                conn.commit()

                # Invalidate cache if available
                if self.cache and cursor.rowcount > 0:
                    self.cache.intelligent_cache_invalidation(
                        question_id, action='embedding_update'
                    )

                return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Error updating embeddings for {question_id}: {e}")
            return False

    # ==========================================
    # MULTIMODAL SIMILARITY OPERATIONS
    # ==========================================

    def calculate_multimodal_similarity(self, embeddings1: Dict, embeddings2: Dict,
                                      weights: Tuple[float, float, float] = (0.6, 0.2, 0.2)) -> float:
        """
        Calculate multimodal similarity between two questions
        
        Uses weighted combination of:
        - OpenAI embedding similarity (default weight: 0.6)
        - UMAP embedding similarity (default weight: 0.2) 
        - Cluster similarity (default weight: 0.2)
        """
        try:
            similarities = []
            similarity_weights = []

            # OpenAI embedding similarity (normalized euclidean distance)
            if embeddings1.get('openai_embedding') and embeddings2.get('openai_embedding'):
                emb1 = np.array(embeddings1['openai_embedding'])
                emb2 = np.array(embeddings2['openai_embedding'])
                sim = self._calculate_euclidean_similarity(emb1, emb2)
                similarities.append(sim)
                similarity_weights.append(weights[0])

            # UMAP embedding similarity (normalized euclidean distance)
            if embeddings1.get('umap_embedding') and embeddings2.get('umap_embedding'):
                emb1 = np.array(embeddings1['umap_embedding'])
                emb2 = np.array(embeddings2['umap_embedding'])
                sim = self._calculate_euclidean_similarity(emb1, emb2)
                similarities.append(sim)
                similarity_weights.append(weights[1])

            # Cluster similarity (cosine similarity)
            if embeddings1.get('soft_cluster') and embeddings2.get('soft_cluster'):
                cluster1 = np.array(embeddings1['soft_cluster'])
                cluster2 = np.array(embeddings2['soft_cluster'])
                sim = self._calculate_cosine_similarity(cluster1, cluster2)
                similarities.append(sim)
                similarity_weights.append(weights[2])

            if similarities:
                return np.average(similarities, weights=similarity_weights)
            return 0.0

        except Exception as e:
            logger.error(f"Error calculating multimodal similarity: {e}")
            return 0.0

    def find_similar_questions(self, target_embedding: Optional[List[float]] = None,
                             openai_embedding: Optional[List[float]] = None,
                             umap_embedding: Optional[List[float]] = None,
                             cluster_vector: Optional[List[float]] = None,
                             weights: Tuple[float, float, float] = (0.6, 0.2, 0.2),
                             similarity_threshold: float = 0.6,
                             top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Find similar questions using multimodal embeddings
        
        Supports both individual embeddings and target_embedding parameter
        for backward compatibility
        """
        try:
            # Handle backward compatibility
            if target_embedding is not None and openai_embedding is None:
                openai_embedding = target_embedding

            # Use PostgreSQL function for efficiency
            cache_key = None
            if self.cache:
                cache_params = {
                    'weights': weights,
                    'threshold': similarity_threshold,
                    'top_k': top_k
                }
                cache_key = self.cache.create_cache_key(
                    'similarities',
                    str(hash(str(openai_embedding))),
                    **cache_params
                )
                
                cached_result = self.cache.get_or_compute(
                    cache_key=cache_key,
                    compute_function=self._compute_similar_questions,
                    ttl=1800,  # 30 minutes
                    openai_embedding=openai_embedding,
                    umap_embedding=umap_embedding,
                    cluster_vector=cluster_vector,
                    weights=weights,
                    similarity_threshold=similarity_threshold,
                    top_k=top_k
                )
                return cached_result

            return self._compute_similar_questions(
                openai_embedding, umap_embedding, cluster_vector,
                weights, similarity_threshold, top_k
            )

        except Exception as e:
            logger.error(f"Error finding similar questions: {e}")
            return []

    def _compute_similar_questions(self, openai_embedding: Optional[List[float]],
                                 umap_embedding: Optional[List[float]],
                                 cluster_vector: Optional[List[float]],
                                 weights: Tuple[float, float, float],
                                 similarity_threshold: float,
                                 top_k: int) -> List[Dict[str, Any]]:
        """Compute similar questions using PostgreSQL function"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)

                # Use the PostgreSQL function for multimodal similarity
                cursor.execute("""
                    SELECT * FROM find_similar_questions_multimodal(
                        %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    openai_embedding, umap_embedding, cluster_vector,
                    weights[0], weights[1], weights[2], 
                    similarity_threshold, top_k
                ))

                return cursor.fetchall()

        except Exception as e:
            logger.error(f"Error computing similar questions: {e}")
            return []

    def batch_similarity_computation(self, question_ids: List[int], 
                                   target_embedding: List[float]) -> List[Dict[str, Any]]:
        """Batch similarity computation for efficiency"""
        try:
            # Use caching for large batch operations
            if self.cache and len(question_ids) > 10:
                cache_key = self.cache.create_cache_key(
                    'batch_similarity',
                    str(hash(str(target_embedding))),
                    str(hash(str(sorted(question_ids))))
                )
                
                cached_result = self.cache.get_or_compute(
                    cache_key=cache_key,
                    compute_function=self._compute_batch_similarity,
                    ttl=1800,  # 30 minutes
                    question_ids=question_ids,
                    target_embedding=target_embedding
                )
                return cached_result

            return self._compute_batch_similarity(question_ids, target_embedding)

        except Exception as e:
            logger.error(f"Error in batch similarity computation: {e}")
            return []

    def _compute_batch_similarity(self, question_ids: List[int], 
                                target_embedding: List[float]) -> List[Dict[str, Any]]:
        """Compute batch similarities directly from database"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)

                query = """
                SELECT internal_question_id, question_id,
                       1 - (openai_embedding <=> %s) as similarity
                FROM questions
                WHERE internal_question_id = ANY(%s)
                  AND openai_embedding IS NOT NULL
                ORDER BY similarity DESC
                """

                cursor.execute(query, (target_embedding, question_ids))
                return cursor.fetchall()

        except Exception as e:
            logger.error(f"Error computing batch similarities: {e}")
            return []

    # ==========================================
    # CLUSTER-BASED OPERATIONS
    # ==========================================

    def find_cluster_based_questions(self, cluster_priorities: np.ndarray,
                                   exclude_question_ids: List[int],
                                   top_k: int = 10) -> List[Dict[str, Any]]:
        """Find questions based on cluster priorities"""
        try:
            # Cache cluster-based results
            if self.cache:
                cache_key = self.cache.create_cache_key(
                    'cluster_questions',
                    str(hash(cluster_priorities.tobytes())),
                    str(hash(str(sorted(exclude_question_ids)))),
                    top_k=top_k
                )
                
                cached_result = self.cache.get_or_compute(
                    cache_key=cache_key,
                    compute_function=self._compute_cluster_questions,
                    ttl=1800,  # 30 minutes
                    cluster_priorities=cluster_priorities,
                    exclude_question_ids=exclude_question_ids,
                    top_k=top_k
                )
                return cached_result

            return self._compute_cluster_questions(
                cluster_priorities, exclude_question_ids, top_k
            )

        except Exception as e:
            logger.error(f"Error in cluster-based question search: {e}")
            return []

    def _compute_cluster_questions(self, cluster_priorities: np.ndarray,
                                 exclude_question_ids: List[int],
                                 top_k: int) -> List[Dict[str, Any]]:
        """Compute cluster-based questions from database"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)

                query = """
                WITH cluster_scores AS (
                    SELECT
                        q.internal_question_id,
                        q.question_id,
                        q.paper_id,
                        -- Calculate weighted score based on cluster priorities
                        (SELECT SUM(val * priority)
                         FROM unnest(q.soft_cluster) WITH ORDINALITY arr(val, i)
                         JOIN unnest(%s::float[]) WITH ORDINALITY pri(priority, j) ON i = j
                        ) as weighted_score,
                        -- Get dominant cluster
                        (SELECT i-1 FROM unnest(q.soft_cluster) WITH ORDINALITY arr(val,i)
                         ORDER BY val DESC LIMIT 1) as dominant_cluster
                    FROM questions q
                    WHERE q.internal_question_id NOT IN (
                        SELECT unnest(%s::int[])
                    )
                    AND q.soft_cluster IS NOT NULL
                )
                SELECT *
                FROM cluster_scores
                ORDER BY weighted_score DESC
                LIMIT %s
                """

                cursor.execute(query, (
                    cluster_priorities.tolist(),
                    exclude_question_ids if exclude_question_ids else [0],
                    top_k
                ))

                return cursor.fetchall()

        except Exception as e:
            logger.error(f"Error computing cluster-based questions: {e}")
            return []

    # ==========================================
    # RANKING AND DIVERSITY OPERATIONS
    # ==========================================

    def rank_questions_by_similarity(self, target_question_id: str,
                                   candidate_questions: List[Dict[str, Any]],
                                   similarity_threshold: float = 0.7) -> List[Dict[str, Any]]:
        """Rank questions by similarity to target question"""
        try:
            # Get target question embeddings
            target_embeddings = self.get_embeddings(target_question_id)
            if not target_embeddings:
                logger.warning(f"No embeddings found for target question {target_question_id}")
                return candidate_questions

            ranked_questions = []

            for question in candidate_questions:
                question_embeddings = self.get_embeddings(question['question_id'])
                if question_embeddings:
                    similarity = self.calculate_multimodal_similarity(
                        target_embeddings, question_embeddings
                    )

                    if similarity >= similarity_threshold:
                        question_copy = question.copy()
                        question_copy['similarity_score'] = similarity
                        ranked_questions.append(question_copy)

            # Sort by similarity score descending
            ranked_questions.sort(key=lambda x: x['similarity_score'], reverse=True)
            return ranked_questions

        except Exception as e:
            logger.error(f"Error ranking questions by similarity: {e}")
            return candidate_questions

    def find_diverse_recommendations(self, recommendations: List[Dict[str, Any]],
                                   diversity_threshold: float = 0.8) -> List[Dict[str, Any]]:
        """Filter recommendations to ensure diversity"""
        try:
            if not recommendations:
                return recommendations

            diverse_recs = [recommendations[0]]  # Always include top recommendation

            for candidate in recommendations[1:]:
                is_diverse = True
                candidate_embeddings = self.get_embeddings(candidate['question_id'])

                if candidate_embeddings:
                    for selected in diverse_recs:
                        selected_embeddings = self.get_embeddings(selected['question_id'])
                        if selected_embeddings:
                            similarity = self.calculate_multimodal_similarity(
                                candidate_embeddings, selected_embeddings
                            )

                            if similarity > diversity_threshold:
                                is_diverse = False
                                break

                if is_diverse:
                    diverse_recs.append(candidate)

            return diverse_recs

        except Exception as e:
            logger.error(f"Error filtering for diversity: {e}")
            return recommendations

    # ==========================================
    # UTILITY METHODS
    # ==========================================

    def _calculate_cosine_similarity(self, vector1: np.ndarray, vector2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors"""
        try:
            dot_product = np.dot(vector1, vector2)
            norm1 = np.linalg.norm(vector1)
            norm2 = np.linalg.norm(vector2)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            return dot_product / (norm1 * norm2)

        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {e}")
            return 0.0

    def _calculate_euclidean_similarity(self, vector1: np.ndarray, vector2: np.ndarray) -> float:
        """Calculate normalized euclidean similarity (1 - normalized distance)"""
        try:
            distance = np.linalg.norm(vector1 - vector2)
            max_distance = np.linalg.norm(vector1) + np.linalg.norm(vector2)

            if max_distance == 0:
                return 1.0 if np.array_equal(vector1, vector2) else 0.0

            return 1 - (distance / max_distance)

        except Exception as e:
            logger.error(f"Error calculating euclidean similarity: {e}")
            return 0.0

    # ==========================================
    # PERFORMANCE AND ANALYTICS
    # ==========================================

    def get_vector_statistics(self) -> Dict[str, Any]:
        """Get statistics about vector operations and embeddings"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)

                # Get embedding statistics
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_questions,
                        COUNT(openai_embedding) as with_openai_embeddings,
                        COUNT(umap_embedding) as with_umap_embeddings,
                        COUNT(soft_cluster) as with_cluster_info,
                        AVG(text_length) as avg_text_length
                    FROM questions
                """)
                
                stats = dict(cursor.fetchone())
                
                # Add cache statistics if available
                if self.cache:
                    cache_stats = self.cache.get_cache_statistics()
                    stats['cache_performance'] = cache_stats
                
                return stats

        except Exception as e:
            logger.error(f"Error getting vector statistics: {e}")
            return {'error': str(e)}

    def validate_vector_consistency(self) -> Dict[str, Any]:
        """Validate consistency across vector operations"""
        validation_results = {
            'timestamp': np.datetime64('now'),
            'consistency_checks': [],
            'warnings': [],
            'errors': []
        }

        try:
            # Test with a sample question
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                
                cursor.execute("""
                    SELECT question_id, openai_embedding, umap_embedding, soft_cluster
                    FROM questions 
                    WHERE openai_embedding IS NOT NULL 
                      AND umap_embedding IS NOT NULL 
                      AND soft_cluster IS NOT NULL
                    LIMIT 1
                """)
                
                test_question = cursor.fetchone()
                
                if test_question:
                    # Test embedding retrieval consistency
                    embeddings1 = self.get_embeddings(test_question['question_id'])
                    embeddings2 = self._fetch_embeddings_from_db(test_question['question_id'])
                    
                    if embeddings1 and embeddings2:
                        if embeddings1 == embeddings2:
                            validation_results['consistency_checks'].append(
                                "✅ Embedding retrieval consistent between cached and direct methods"
                            )
                        else:
                            validation_results['errors'].append(
                                "❌ Embedding retrieval inconsistent between methods"
                            )
                    
                    # Test similarity calculation consistency
                    self_similarity = self.calculate_multimodal_similarity(embeddings1, embeddings1)
                    if abs(self_similarity - 1.0) < 0.001:
                        validation_results['consistency_checks'].append(
                            "✅ Self-similarity calculation is correct (≈1.0)"
                        )
                    else:
                        validation_results['warnings'].append(
                            f"⚠️ Self-similarity is {self_similarity}, expected ≈1.0"
                        )

            validation_results['status'] = 'completed'
            return validation_results

        except Exception as e:
            validation_results['errors'].append(f"❌ Validation failed: {str(e)}")
            validation_results['status'] = 'failed'
            return validation_results