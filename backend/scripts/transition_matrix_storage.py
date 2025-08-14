#!/usr/bin/env python3
"""
Transition Matrix Storage Manager
Provides hybrid storage strategy: Redis for speed + PostgreSQL for persistence
"""

import numpy as np
import pandas as pd
import json
import redis
import psycopg2
from psycopg2.extras import RealDictCursor
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
import logging

class TransitionMatrixManager:
    """
    Hybrid storage manager for transition matrices:
    - Redis: Fast access (sub-millisecond)
    - PostgreSQL: Persistent storage with versioning
    - Automatic cache invalidation when source data changes
    """

    def __init__(self, redis_client: redis.Redis, db_config: Dict[str, Any]):
        self.redis = redis_client
        self.db_config = db_config
        self.logger = logging.getLogger(__name__)

        # Cache keys
        self.MATRIX_KEY = "transition_matrix:data"
        self.HASH_KEY = "transition_matrix:source_hash"
        self.METADATA_KEY = "transition_matrix:metadata"

    def compute_source_data_hash(self) -> str:
        """Compute hash of source clustering data to detect changes"""
        try:
            df = pd.read_parquet("../combined_questions.parquet")
            # Hash based on clustering data + parameters
            cluster_data = np.stack(df['soft_cluster'].values)
            content = f"{cluster_data.tobytes()}:alpha=0.1:normalized=True"
            return hashlib.sha256(content.encode()).hexdigest()[:16]
        except Exception as e:
            self.logger.error(f"Error computing source hash: {e}")
            return "unknown"

    def load_from_redis(self) -> Optional[np.ndarray]:
        """Load transition matrix from Redis cache"""
        try:
            # Check if matrix exists and is fresh
            matrix_data = self.redis.get(self.MATRIX_KEY)
            metadata = self.redis.get(self.METADATA_KEY)

            if not matrix_data or not metadata:
                return None

            # Parse metadata
            meta = json.loads(metadata)
            cached_hash = meta.get('source_hash')
            current_hash = self.compute_source_data_hash()

            # Check if source data has changed
            if cached_hash != current_hash:
                self.logger.info(f"Source data changed ({cached_hash} → {current_hash}), cache invalid")
                return None

            # Deserialize matrix
            matrix_json = json.loads(matrix_data)
            matrix = np.array(matrix_json['matrix'])

            self.logger.info(f"✅ Loaded transition matrix from Redis cache ({matrix.shape})")
            return matrix

        except Exception as e:
            self.logger.error(f"Error loading from Redis: {e}")
            return None

    def save_to_redis(self, matrix: np.ndarray, ttl_hours: int = 24) -> bool:
        """Save transition matrix to Redis with TTL"""
        try:
            current_hash = self.compute_source_data_hash()

            # Serialize matrix
            matrix_data = {
                'matrix': matrix.tolist(),
                'shape': matrix.shape,
                'dtype': str(matrix.dtype)
            }

            # Metadata
            metadata = {
                'source_hash': current_hash,
                'created_at': datetime.now().isoformat(),
                'shape': matrix.shape,
                'algorithm': 'cooccurrence_transitions',
                'parameters': {'alpha': 0.1, 'normalized': True}
            }

            # Save with TTL
            ttl_seconds = ttl_hours * 3600
            pipeline = self.redis.pipeline()
            pipeline.setex(self.MATRIX_KEY, ttl_seconds, json.dumps(matrix_data))
            pipeline.setex(self.METADATA_KEY, ttl_seconds, json.dumps(metadata))
            pipeline.execute()

            self.logger.info(f"✅ Saved transition matrix to Redis (TTL: {ttl_hours}h)")
            return True

        except Exception as e:
            self.logger.error(f"Error saving to Redis: {e}")
            return False

    def load_from_postgresql(self) -> Optional[np.ndarray]:
        """Load transition matrix from PostgreSQL"""
        try:
            with psycopg2.connect(**self.db_config) as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)

                current_hash = self.compute_source_data_hash()

                # Get latest matrix matching current source data
                cursor.execute("""
                    SELECT matrix_data, metadata, created_at
                    FROM transition_matrices
                    WHERE source_data_hash = %s
                    AND is_active = true
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (current_hash,))

                row = cursor.fetchone()
                if not row:
                    return None

                # Deserialize matrix
                matrix_data = row['matrix_data']
                matrix = np.array(matrix_data['matrix'])

                self.logger.info(f"✅ Loaded transition matrix from PostgreSQL ({matrix.shape})")

                # Also cache in Redis for future access
                self.save_to_redis(matrix, ttl_hours=24)

                return matrix

        except Exception as e:
            self.logger.error(f"Error loading from PostgreSQL: {e}")
            return None

    def save_to_postgresql(self, matrix: np.ndarray) -> bool:
        """Save transition matrix to PostgreSQL with versioning"""
        try:
            with psycopg2.connect(**self.db_config) as conn:
                cursor = conn.cursor()

                current_hash = self.compute_source_data_hash()

                # Check if this version already exists
                cursor.execute("""
                    SELECT matrix_id FROM transition_matrices
                    WHERE source_data_hash = %s AND is_active = true
                """, (current_hash,))

                if cursor.fetchone():
                    self.logger.info("Matrix for current source data already exists in PostgreSQL")
                    return True

                # Prepare data for storage
                matrix_data = {
                    'matrix': matrix.tolist(),
                    'shape': matrix.shape,
                    'dtype': str(matrix.dtype)
                }

                metadata = {
                    'algorithm': 'cooccurrence_transitions',
                    'parameters': {'alpha': 0.1, 'normalized': True},
                    'n_clusters': matrix.shape[0],
                    'sparsity': float((matrix == 0).sum() / matrix.size),
                    'source_file': 'combined_questions.parquet'
                }

                # Insert new matrix
                cursor.execute("""
                    INSERT INTO transition_matrices (
                        source_data_hash, matrix_data, metadata,
                        algorithm_name, algorithm_version, is_active
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    current_hash,
                    json.dumps(matrix_data),
                    json.dumps(metadata),
                    'cooccurrence_transitions',
                    '1.0',
                    True
                ))

                conn.commit()
                self.logger.info(f"✅ Saved transition matrix to PostgreSQL")
                return True

        except Exception as e:
            self.logger.error(f"Error saving to PostgreSQL: {e}")
            return False

    def get_or_compute_matrix(self, force_rebuild: bool = False) -> Optional[np.ndarray]:
        """
        Main method: Get transition matrix using hybrid strategy
        1. Try Redis cache (fastest)
        2. Try PostgreSQL (persistent)
        3. Compute from scratch (slowest)
        """
        if not force_rebuild:
            # Try Redis first
            matrix = self.load_from_redis()
            if matrix is not None:
                return matrix

            # Try PostgreSQL
            matrix = self.load_from_postgresql()
            if matrix is not None:
                return matrix

        # Compute from scratch
        self.logger.info("Computing transition matrix from scratch...")
        matrix = self._build_transition_matrix()

        if matrix is not None:
            # Save to both storage layers
            self.save_to_postgresql(matrix)
            self.save_to_redis(matrix, ttl_hours=24)

        return matrix

    def _build_transition_matrix(self) -> Optional[np.ndarray]:
        """Build transition matrix from source data"""
        try:
            # Import here to avoid circular dependencies
            import sys
            sys.path.append('../ml')
            from transition_matrix import _build_cooccurrence_transitions

            matrix = _build_cooccurrence_transitions(alpha=0.1, normalize=True)
            if matrix is not None:
                self.logger.info(f"✅ Built new transition matrix ({matrix.shape})")

            return matrix

        except Exception as e:
            self.logger.error(f"Error building transition matrix: {e}")
            return None

    def invalidate_cache(self):
        """Manually invalidate Redis cache"""
        try:
            pipeline = self.redis.pipeline()
            pipeline.delete(self.MATRIX_KEY)
            pipeline.delete(self.METADATA_KEY)
            pipeline.execute()
            self.logger.info("✅ Invalidated transition matrix cache")
        except Exception as e:
            self.logger.error(f"Error invalidating cache: {e}")

    def get_cache_info(self) -> Dict[str, Any]:
        """Get information about cached matrices"""
        info = {
            'redis_cached': False,
            'postgresql_versions': 0,
            'current_source_hash': self.compute_source_data_hash()
        }

        try:
            # Check Redis
            if self.redis.exists(self.MATRIX_KEY):
                metadata = self.redis.get(self.METADATA_KEY)
                if metadata:
                    meta = json.loads(metadata)
                    info['redis_cached'] = True
                    info['redis_metadata'] = meta

            # Check PostgreSQL
            with psycopg2.connect(**self.db_config) as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute("SELECT COUNT(*) as count FROM transition_matrices WHERE is_active = true")
                result = cursor.fetchone()
                info['postgresql_versions'] = result['count']

        except Exception as e:
            self.logger.error(f"Error getting cache info: {e}")

        return info


def create_postgresql_table():
    """Create the transition_matrices table in PostgreSQL"""
    return """
    -- Add to your postgresql_migration.sql

    CREATE TABLE IF NOT EXISTS transition_matrices (
        matrix_id SERIAL PRIMARY KEY,
        source_data_hash VARCHAR(32) NOT NULL,
        matrix_data JSONB NOT NULL,
        metadata JSONB NOT NULL,
        algorithm_name VARCHAR(100) NOT NULL DEFAULT 'cooccurrence_transitions',
        algorithm_version VARCHAR(20) NOT NULL DEFAULT '1.0',
        is_active BOOLEAN NOT NULL DEFAULT true,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Indexes for efficient queries
    CREATE INDEX IF NOT EXISTS idx_transition_matrices_hash_active
        ON transition_matrices(source_data_hash, is_active);
    CREATE INDEX IF NOT EXISTS idx_transition_matrices_algorithm
        ON transition_matrices(algorithm_name, algorithm_version);

    -- Trigger for updated_at
    CREATE OR REPLACE FUNCTION update_transition_matrices_updated_at()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = CURRENT_TIMESTAMP;
        RETURN NEW;
    END;
    $$ language 'plpgsql';

    CREATE TRIGGER update_transition_matrices_updated_at
        BEFORE UPDATE ON transition_matrices
        FOR EACH ROW
        EXECUTE FUNCTION update_transition_matrices_updated_at();
    """


# Example usage function
def example_usage():
    """Example of how to use the TransitionMatrixManager"""
    import redis

    # Setup
    redis_client = redis.Redis(host='localhost', port=6379, db=1)  # Use vector Redis
    db_config = {
        'host': 'localhost',
        'port': 5432,
        'database': 'human_capital_dev',
        'user': 'hcd_user',
        'password': 'your_secure_password_here'
    }

    # Initialize manager
    manager = TransitionMatrixManager(redis_client, db_config)

    # Get matrix (will use cache if available, compute if needed)
    matrix = manager.get_or_compute_matrix()

    if matrix is not None:
        print(f"✅ Got transition matrix: {matrix.shape}")

        # Get cache info
        info = manager.get_cache_info()
        print(f"📊 Cache info: {info}")
    else:
        print("❌ Failed to get transition matrix")

    return matrix


if __name__ == "__main__":
    # Print SQL for database setup
    print("📄 PostgreSQL table creation SQL:")
    print(create_postgresql_table())
    print("\n" + "="*60)

    # Run example
    matrix = example_usage()
