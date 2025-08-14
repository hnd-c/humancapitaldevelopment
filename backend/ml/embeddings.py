#!/usr/bin/env python3
"""
Embeddings - Handle vector embeddings and similarity operations

This module handles:
- Vector embedding operations
- Multimodal similarity calculations
- Embedding caching and optimization
"""

import numpy as np
from typing import List, Dict, Optional, Tuple, Any


class EmbeddingManager:
    """Manages vector embeddings and similarity operations"""

    def __init__(self, db_manager):
        self.db_manager = db_manager

    def get_question_embeddings(self, question_id: str) -> Optional[Dict[str, Any]]:
        """Get all embeddings for a specific question"""
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=self.db_manager.RealDictCursor)

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
            print(f"Error getting embeddings for {question_id}: {e}")
            return None

    def calculate_multimodal_similarity(self, embeddings1: Dict, embeddings2: Dict) -> float:
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

    def find_similar_questions_multimodal(self, openai_embedding: Optional[List[float]] = None,
                                        umap_embedding: Optional[List[float]] = None,
                                        cluster_vector: Optional[List[float]] = None,
                                        weights: Tuple[float, float, float] = (0.6, 0.2, 0.2),
                                        top_k: int = 10) -> List[Dict[str, Any]]:
        """Multi-modal similarity using PostgreSQL functions"""
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=self.db_manager.RealDictCursor)

                # Use the PostgreSQL function for multimodal similarity
                cursor.execute("""
                    SELECT * FROM find_similar_questions_multimodal(
                        %s, %s, %s, %s, %s, %s, 0.6, %s
                    )
                """, (
                    openai_embedding, umap_embedding, cluster_vector,
                    weights[0], weights[1], weights[2], top_k
                ))

                return cursor.fetchall()
        except Exception as e:
            print(f"Error in multimodal similarity search: {e}")
            return []

    def batch_similarity_computation(self, question_ids: List[int], target_embedding: List[float]) -> List[Dict[str, Any]]:
        """Batch similarity computation for efficiency"""
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=self.db_manager.RealDictCursor)

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
            print(f"Error in batch similarity computation: {e}")
            return []

    def update_question_embeddings(self, question_id: str,
                                 openai_embedding: Optional[List[float]] = None,
                                 umap_embedding: Optional[List[float]] = None,
                                 soft_cluster: Optional[List[float]] = None) -> bool:
        """Update embeddings for a specific question"""
        try:
            with self.db_manager.get_db_connection() as conn:
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

                return cursor.rowcount > 0
        except Exception as e:
            print(f"Error updating embeddings for {question_id}: {e}")
            return False
