import psycopg2
import psycopg2.pool
import redis
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager, asynccontextmanager
import json
import asyncpg
from typing import Optional, Dict, Any

class DatabaseManager:
    def __init__(self, db_config, redis_config):
        # Convert config objects to dictionaries if needed
        if hasattr(db_config, 'to_dict'):
            self.db_config = db_config.to_dict()
        else:
            self.db_config = db_config

        if hasattr(redis_config, 'to_dict'):
            redis_dict = redis_config.to_dict()
        else:
            redis_dict = redis_config

        self.redis_client = redis.Redis(**redis_dict)
        # RealDictCursor should be imported directly in each service file for consistency

        # Initialize connection pools
        self._init_connection_pools()

    def _init_connection_pools(self):
        """Initialize both sync and async connection pools"""
        try:
            # Sync connection pool using psycopg2
            pool_size = self.db_config.get('connection_pool_size', 20)
            max_overflow = self.db_config.get('max_overflow', 30)

            self.sync_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=max(1, pool_size // 4),  # Minimum connections
                maxconn=pool_size + max_overflow,  # Maximum connections
                host=self.db_config['host'],
                port=self.db_config['port'],
                database=self.db_config['database'],
                user=self.db_config['user'],
                password=self.db_config['password']
            )

            # Async connection pool (will be initialized lazily)
            self.async_pool: Optional[asyncpg.Pool] = None
            self._async_pool_initialized = False

            print(f"✅ Database connection pools initialized (sync: {pool_size}+{max_overflow})")

        except Exception as e:
            print(f"❌ Failed to initialize connection pools: {e}")
            # Fallback to direct connections
            self.sync_pool = None
            self.async_pool = None

    @contextmanager
    def get_db_connection(self):
        """Get a database connection from the pool (sync)"""
        if self.sync_pool:
            conn = self.sync_pool.getconn()
            try:
                yield conn
            finally:
                self.sync_pool.putconn(conn)
        else:
            # Fallback to direct connection
            conn = psycopg2.connect(**self.db_config)
            try:
                yield conn
            finally:
                conn.close()

    async def get_async_connection(self):
        """Get an async database connection from the pool"""
        if not self._async_pool_initialized:
            await self._init_async_pool()

        if self.async_pool:
            return await self.async_pool.acquire()
        else:
            # Fallback to direct async connection
            return await asyncpg.connect(
                host=self.db_config['host'],
                port=self.db_config['port'],
                database=self.db_config['database'],
                user=self.db_config['user'],
                password=self.db_config['password']
            )

    async def release_async_connection(self, conn):
        """Release an async connection back to the pool"""
        if self.async_pool:
            await self.async_pool.release(conn)
        else:
            await conn.close()

    async def _init_async_pool(self):
        """Initialize the async connection pool lazily"""
        if self._async_pool_initialized:
            return

        try:
            pool_size = self.db_config.get('connection_pool_size', 20)

            self.async_pool = await asyncpg.create_pool(
                host=self.db_config['host'],
                port=self.db_config['port'],
                database=self.db_config['database'],
                user=self.db_config['user'],
                password=self.db_config['password'],
                min_size=max(1, pool_size // 4),
                max_size=pool_size,
                command_timeout=30
            )

            print(f"✅ Async database connection pool initialized (size: {pool_size})")

        except Exception as e:
            print(f"❌ Failed to initialize async connection pool: {e}")
            self.async_pool = None

        self._async_pool_initialized = True

    def get_student_history_optimized(self, student_id, limit=1000):
        """Optimized student history with caching"""
        from data.serialization import create_cache_key
        cache_key = create_cache_key("student_history", student_id, limit=limit)

        # Try Redis cache first
        cached = self.redis_client.get(cache_key)
        if cached:
            return json.loads(cached)

        # Query PostgreSQL with proper indexing
        with self.get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            query = """
            SELECT sqh.*, q.question_id
            FROM student_question_history sqh
            JOIN student_paper_enrollments spe ON sqh.enrollment_id = spe.enrollment_id
            JOIN questions q ON sqh.internal_question_id = q.internal_question_id
            WHERE spe.student_id = %s
            ORDER BY sqh.timestamp DESC
            LIMIT %s
            """
            cursor.execute(query, (student_id, limit))
            results = cursor.fetchall()

        # Cache for 5 minutes using centralized serialization
        from data.serialization import serialize_for_cache
        cached_data = serialize_for_cache(results, compress_large=False)
        self.redis_client.setex(cache_key, 300, cached_data)
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

    async def get_student_history_optimized_async(self, student_id, limit=1000):
        """Async version of optimized student history with caching"""
        from data.serialization import create_cache_key
        cache_key = create_cache_key("student_history", student_id, limit=limit)

        # Try Redis cache first
        cached = self.redis_client.get(cache_key)
        if cached:
            return json.loads(cached)

        # Query PostgreSQL with async connection
        conn = await self.get_async_connection()
        try:
            query = """
            SELECT sqh.*, q.question_id
            FROM student_question_history sqh
            JOIN student_paper_enrollments spe ON sqh.enrollment_id = spe.enrollment_id
            JOIN questions q ON sqh.internal_question_id = q.internal_question_id
            WHERE spe.student_id = $1
            ORDER BY sqh.timestamp DESC
            LIMIT $2
            """
            results = await conn.fetch(query, student_id, limit)

            # Convert asyncpg.Record to dict
            results = [dict(row) for row in results]

            # Cache for 5 minutes using centralized serialization
            from data.serialization import serialize_for_cache
            cached_data = serialize_for_cache(results, compress_large=False)
            self.redis_client.setex(cache_key, 300, cached_data)
            return results

        finally:
            await self.release_async_connection(conn)

    async def find_similar_questions_vector_async(self, query_embedding, similarity_threshold=0.7, limit=10):
        """Async version of PostgreSQL vector similarity search"""
        conn = await self.get_async_connection()
        try:
            query = """
            SELECT internal_question_id, question_id,
                   1 - (openai_embedding <-> $1) as similarity_score
            FROM questions
            WHERE openai_embedding IS NOT NULL
              AND 1 - (openai_embedding <-> $1) >= $2
            ORDER BY openai_embedding <-> $1
            LIMIT $3
            """
            results = await conn.fetch(query, query_embedding, similarity_threshold, limit)
            return [dict(row) for row in results]

        finally:
            await self.release_async_connection(conn)

    async def execute_query_async(self, query: str, params: tuple = None) -> list:
        """Execute an async query and return results"""
        conn = await self.get_async_connection()
        try:
            if params:
                results = await conn.fetch(query, *params)
            else:
                results = await conn.fetch(query)
            return [dict(row) for row in results]
        finally:
            await self.release_async_connection(conn)

    async def execute_query_one_async(self, query: str, params: tuple = None) -> Dict[str, Any]:
        """Execute an async query and return single result"""
        conn = await self.get_async_connection()
        try:
            if params:
                result = await conn.fetchrow(query, *params)
            else:
                result = await conn.fetchrow(query)
            return dict(result) if result else None
        finally:
            await self.release_async_connection(conn)

    def close_pools(self):
        """Close connection pools"""
        if self.sync_pool:
            self.sync_pool.closeall()
            print("✅ Sync connection pool closed")

        if self.async_pool:
            # Note: async pool will be closed by the async context manager
            print("✅ Async connection pool will be closed")

    async def close_async_pool(self):
        """Close async connection pool"""
        if self.async_pool:
            await self.async_pool.close()
            print("✅ Async connection pool closed")

    @asynccontextmanager
    async def async_connection_context(self):
        """Async context manager for database connections"""
        conn = await self.get_async_connection()
        try:
            yield conn
        finally:
            await self.release_async_connection(conn)
