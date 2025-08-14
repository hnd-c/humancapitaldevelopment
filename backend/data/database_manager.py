import psycopg2
import redis
import numpy as np
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
import json
import time

class DatabaseManager:
    def __init__(self, db_config, redis_config):
        self.db_config = db_config
        self.redis_client = redis.Redis(**redis_config)
        self.RealDictCursor = RealDictCursor  # Make RealDictCursor accessible

    @contextmanager
    def get_db_connection(self):
        conn = psycopg2.connect(**self.db_config)
        try:
            yield conn
        finally:
            conn.close()

    def get_student_history_optimized(self, student_id, limit=1000):
        """Optimized student history with caching"""
        cache_key = f"student_history:{student_id}:{limit}"

        # Try Redis cache first
        cached = self.redis_client.get(cache_key)
        if cached:
            return json.loads(cached)

        # Query PostgreSQL with proper indexing
        with self.get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            query = """
            SELECT sqh.*, q.question_id, q.openai_embedding, q.soft_cluster
            FROM student_question_history sqh
            JOIN student_paper_enrollments spe ON sqh.enrollment_id = spe.enrollment_id
            JOIN questions q ON sqh.internal_question_id = q.internal_question_id
            WHERE spe.student_id = %s
            ORDER BY sqh.timestamp DESC
            LIMIT %s
            """
            cursor.execute(query, (student_id, limit))
            results = cursor.fetchall()

        # Cache for 5 minutes
        self.redis_client.setex(cache_key, 300, json.dumps(results, default=str))
        return results

    def find_similar_questions_vector(self, query_embedding, similarity_threshold=0.7, limit=10):
        """Use PostgreSQL vector similarity"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            query = """
            SELECT internal_question_id, question_id,
                   1 - (openai_embedding <=> %s) as similarity_score
            FROM questions
            WHERE openai_embedding IS NOT NULL
              AND 1 - (openai_embedding <=> %s) >= %s
            ORDER BY openai_embedding <=> %s
            LIMIT %s
            """
            cursor.execute(query, (query_embedding, query_embedding, similarity_threshold, query_embedding, limit))
            return cursor.fetchall()
