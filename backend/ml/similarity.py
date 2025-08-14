#!/usr/bin/env python3
"""
Similarity - Advanced similarity calculations and vector operations

This module handles:
- Cluster-based similarity
- Vector distance calculations
- Similarity ranking and filtering
"""

import numpy as np
from typing import List, Dict, Optional, Any
from psycopg2.extras import RealDictCursor


class SimilarityCalculator:
    """Handles advanced similarity calculations"""

    def __init__(self, db_manager):
        self.db_manager = db_manager

    def find_cluster_based_questions(self, cluster_priorities: np.ndarray,
                                   exclude_question_ids: List[int],
                                   top_k: int = 10) -> List[Dict[str, Any]]:
        """Find questions based on cluster priorities"""
        try:
            with self.db_manager.get_db_connection() as conn:
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
            print(f"Error in cluster-based question search: {e}")
            return []

    def calculate_cosine_similarity(self, vector1: np.ndarray, vector2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors"""
        try:
            dot_product = np.dot(vector1, vector2)
            norm1 = np.linalg.norm(vector1)
            norm2 = np.linalg.norm(vector2)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            return dot_product / (norm1 * norm2)
        except Exception as e:
            print(f"Error calculating cosine similarity: {e}")
            return 0.0

    def calculate_euclidean_similarity(self, vector1: np.ndarray, vector2: np.ndarray) -> float:
        """Calculate normalized euclidean similarity (1 - normalized distance)"""
        try:
            distance = np.linalg.norm(vector1 - vector2)
            max_distance = np.linalg.norm(vector1) + np.linalg.norm(vector2)

            if max_distance == 0:
                return 1.0 if np.array_equal(vector1, vector2) else 0.0

            return 1 - (distance / max_distance)
        except Exception as e:
            print(f"Error calculating euclidean similarity: {e}")
            return 0.0

    def rank_questions_by_similarity(self, target_question_id: str,
                                   candidate_questions: List[Dict[str, Any]],
                                   similarity_threshold: float = 0.7) -> List[Dict[str, Any]]:
        """Rank questions by similarity to target question"""
        try:
            # Get target question embeddings
            target_embeddings = self._get_question_embeddings(target_question_id)
            if not target_embeddings:
                return candidate_questions

            ranked_questions = []

            for question in candidate_questions:
                question_embeddings = self._get_question_embeddings(question['question_id'])
                if question_embeddings:
                    similarity = self._calculate_multimodal_similarity(
                        target_embeddings, question_embeddings
                    )

                    if similarity >= similarity_threshold:
                        question['similarity_score'] = similarity
                        ranked_questions.append(question)

            # Sort by similarity score descending
            ranked_questions.sort(key=lambda x: x['similarity_score'], reverse=True)
            return ranked_questions

        except Exception as e:
            print(f"Error ranking questions by similarity: {e}")
            return candidate_questions

    def find_diverse_recommendations(self, recommendations: List[Dict[str, Any]],
                                   diversity_threshold: float = 0.8) -> List[Dict[str, Any]]:
        """Filter recommendations to ensure diversity"""
        try:
            if not recommendations:
                return recommendations

            diverse_recs = [recommendations[0]]  # Always include the top recommendation

            for candidate in recommendations[1:]:
                is_diverse = True
                candidate_embeddings = self._get_question_embeddings(candidate['question_id'])

                if candidate_embeddings:
                    for selected in diverse_recs:
                        selected_embeddings = self._get_question_embeddings(selected['question_id'])
                        if selected_embeddings:
                            similarity = self._calculate_multimodal_similarity(
                                candidate_embeddings, selected_embeddings
                            )

                            if similarity > diversity_threshold:
                                is_diverse = False
                                break

                if is_diverse:
                    diverse_recs.append(candidate)

            return diverse_recs

        except Exception as e:
            print(f"Error filtering for diversity: {e}")
            return recommendations

    def _get_question_embeddings(self, question_id: str) -> Optional[Dict[str, Any]]:
        """Helper method to get question embeddings"""
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)

                query = """
                SELECT openai_embedding, umap_embedding, soft_cluster
                FROM questions
                WHERE question_id = %s
                """

                cursor.execute(query, (question_id,))
                result = cursor.fetchone()

                if result:
                    return dict(result)
                return None
        except Exception as e:
            print(f"Error getting embeddings for {question_id}: {e}")
            return None

    def _calculate_multimodal_similarity(self, embeddings1: Dict, embeddings2: Dict) -> float:
        """Helper method for multimodal similarity calculation"""
        try:
            similarities = []
            weights = []

            # OpenAI embedding similarity
            if embeddings1.get('openai_embedding') and embeddings2.get('openai_embedding'):
                emb1 = np.array(embeddings1['openai_embedding'])
                emb2 = np.array(embeddings2['openai_embedding'])
                sim = self.calculate_cosine_similarity(emb1, emb2)
                similarities.append(sim)
                weights.append(0.6)

            # UMAP embedding similarity
            if embeddings1.get('umap_embedding') and embeddings2.get('umap_embedding'):
                emb1 = np.array(embeddings1['umap_embedding'])
                emb2 = np.array(embeddings2['umap_embedding'])
                sim = self.calculate_cosine_similarity(emb1, emb2)
                similarities.append(sim)
                weights.append(0.2)

            # Cluster similarity
            if embeddings1.get('soft_cluster') and embeddings2.get('soft_cluster'):
                cluster1 = np.array(embeddings1['soft_cluster'])
                cluster2 = np.array(embeddings2['soft_cluster'])
                sim = self.calculate_cosine_similarity(cluster1, cluster2)
                similarities.append(sim)
                weights.append(0.2)

            if similarities:
                return np.average(similarities, weights=weights)
            return 0.0

        except Exception as e:
            print(f"Error calculating multimodal similarity: {e}")
            return 0.0
