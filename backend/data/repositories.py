# vector_operations.py
import numpy as np
from typing import List, Dict, Optional, Tuple, Any
from psycopg2.extras import RealDictCursor

class VectorOperations:
    def __init__(self, db_manager):
        self.db = db_manager

    def find_similar_questions_multimodal(self, openai_embedding: Optional[List[float]] = None,
                                         umap_embedding: Optional[List[float]] = None,
                                         cluster_vector: Optional[List[float]] = None,
                                         weights: Tuple[float, float, float] = (0.6, 0.2, 0.2),
                                         similarity_threshold: float = 0.6,
                                         top_k: int = 10) -> List[Dict[str, Any]]:
        """Multi-modal similarity using PostgreSQL functions"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)

                # Use the PostgreSQL function we created in the migration
                cursor.execute("""
                    SELECT * FROM find_similar_questions_multimodal(
                        %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    openai_embedding, umap_embedding, cluster_vector,
                    weights[0], weights[1], weights[2], similarity_threshold, top_k
                ))

                return cursor.fetchall()
        except Exception as e:
            print(f"Error in multimodal similarity search: {e}")
            return []

    def batch_similarity_computation(self, question_ids: List[int], target_embedding: List[float]) -> List[Dict[str, Any]]:
        """Batch similarity computation for efficiency"""
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
            print(f"Error in batch similarity computation: {e}")
            return []

    def find_cluster_based_questions(self, cluster_priorities: np.ndarray,
                                   exclude_question_ids: List[int],
                                   top_k: int = 10) -> List[Dict[str, Any]]:
        """Find questions based on cluster priorities"""
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
            print(f"Error in cluster-based question search: {e}")
            return []

    def get_question_embeddings(self, question_id: str) -> Optional[Dict[str, Any]]:
        """Get all embeddings for a specific question"""
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
            print(f"Error getting embeddings for {question_id}: {e}")
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

                return cursor.rowcount > 0
        except Exception as e:
            print(f"Error updating embeddings for {question_id}: {e}")
            return False