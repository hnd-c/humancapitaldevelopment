#!/usr/bin/env python3
"""
Configuration Settings - Main application configuration

This module handles:
- System configuration management
- Environment variable handling
- Default settings and validation
"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DatabaseConfig:
    """Database configuration settings"""
    host: str = "localhost"
    port: int = 5432
    database: str = "human_capital_dev"
    user: str = "hcd_user"
    password: str = "your_secure_password_here"
    connection_pool_size: int = 20
    max_overflow: int = 30
    pool_timeout: int = 30
    pool_recycle: int = 3600

    @classmethod
    def from_env(cls) -> 'DatabaseConfig':
        """Create database config from environment variables"""
        return cls(
            host=os.getenv('DB_HOST', cls.host),
            port=int(os.getenv('DB_PORT', cls.port)),
            database=os.getenv('DB_NAME', cls.database),
            user=os.getenv('DB_USER', cls.user),
            password=os.getenv('DB_PASSWORD', cls.password),
            connection_pool_size=int(os.getenv('DB_POOL_SIZE', cls.connection_pool_size)),
            max_overflow=int(os.getenv('DB_MAX_OVERFLOW', cls.max_overflow)),
            pool_timeout=int(os.getenv('DB_POOL_TIMEOUT', cls.pool_timeout)),
            pool_recycle=int(os.getenv('DB_POOL_RECYCLE', cls.pool_recycle))
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for psycopg2"""
        return {
            'host': self.host,
            'port': self.port,
            'database': self.database,
            'user': self.user,
            'password': self.password
        }

    def get_connection_string(self) -> str:
        """Get PostgreSQL connection string"""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


@dataclass
class RedisConfig:
    """Redis configuration settings"""
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    decode_responses: bool = True
    socket_timeout: int = 30
    socket_connect_timeout: int = 30
    max_connections: int = 50

    @classmethod
    def from_env(cls) -> 'RedisConfig':
        """Create Redis config from environment variables"""
        return cls(
            host=os.getenv('REDIS_HOST', cls.host),
            port=int(os.getenv('REDIS_PORT', cls.port)),
            db=int(os.getenv('REDIS_DB', cls.db)),
            password=os.getenv('REDIS_PASSWORD'),
            decode_responses=os.getenv('REDIS_DECODE_RESPONSES', 'true').lower() == 'true',
            socket_timeout=int(os.getenv('REDIS_SOCKET_TIMEOUT', cls.socket_timeout)),
            socket_connect_timeout=int(os.getenv('REDIS_CONNECT_TIMEOUT', cls.socket_connect_timeout)),
            max_connections=int(os.getenv('REDIS_MAX_CONNECTIONS', cls.max_connections))
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for redis-py"""
        config = {
            'host': self.host,
            'port': self.port,
            'db': self.db,
            'decode_responses': self.decode_responses,
            'socket_timeout': self.socket_timeout,
            'socket_connect_timeout': self.socket_connect_timeout,
            'max_connections': self.max_connections
        }

        if self.password:
            config['password'] = self.password

        return config


@dataclass
class MLConfig:
    """Machine Learning configuration settings"""
    use_multimodal_embeddings: bool = True
    default_similarity_threshold: float = 0.7
    cluster_transition_alpha: float = 0.1
    embedding_weights: Dict[str, float] = field(default_factory=lambda: {
        'openai': 0.6,
        'umap': 0.2,
        'cluster': 0.2
    })
    recommendation_objectives: Dict[str, Dict[str, float]] = field(default_factory=lambda: {
        'balanced': {'coverage': 0.3, 'efficiency': 0.3, 'success_rate': 0.4},
        'coverage': {'coverage': 0.8, 'efficiency': 0.1, 'success_rate': 0.1},
        'efficiency': {'coverage': 0.1, 'efficiency': 0.8, 'success_rate': 0.1},
        'success_rate': {'coverage': 0.1, 'efficiency': 0.1, 'success_rate': 0.8}
    })
    max_recommendations: int = 50
    diversity_threshold: float = 0.8

    @classmethod
    def from_env(cls) -> 'MLConfig':
        """Create ML config from environment variables"""
        return cls(
            use_multimodal_embeddings=os.getenv('ML_USE_MULTIMODAL', 'true').lower() == 'true',
            default_similarity_threshold=float(os.getenv('ML_SIMILARITY_THRESHOLD', cls.default_similarity_threshold)),
            cluster_transition_alpha=float(os.getenv('ML_TRANSITION_ALPHA', cls.cluster_transition_alpha)),
            max_recommendations=int(os.getenv('ML_MAX_RECOMMENDATIONS', cls.max_recommendations)),
            diversity_threshold=float(os.getenv('ML_DIVERSITY_THRESHOLD', cls.diversity_threshold))
        )


@dataclass
class CacheConfig:
    """Caching configuration settings"""
    default_ttl_seconds: int = 600
    recommendation_ttl_seconds: int = 1800
    student_profile_ttl_seconds: int = 900
    similarity_ttl_seconds: int = 3600
    embeddings_ttl_seconds: int = 7200
    enable_cache_warming: bool = True
    cache_warming_batch_size: int = 100
    max_memory_usage_ratio: float = 0.8

    @classmethod
    def from_env(cls) -> 'CacheConfig':
        """Create cache config from environment variables"""
        return cls(
            default_ttl_seconds=int(os.getenv('CACHE_DEFAULT_TTL', cls.default_ttl_seconds)),
            recommendation_ttl_seconds=int(os.getenv('CACHE_RECOMMENDATION_TTL', cls.recommendation_ttl_seconds)),
            student_profile_ttl_seconds=int(os.getenv('CACHE_PROFILE_TTL', cls.student_profile_ttl_seconds)),
            similarity_ttl_seconds=int(os.getenv('CACHE_SIMILARITY_TTL', cls.similarity_ttl_seconds)),
            embeddings_ttl_seconds=int(os.getenv('CACHE_EMBEDDINGS_TTL', cls.embeddings_ttl_seconds)),
            enable_cache_warming=os.getenv('CACHE_ENABLE_WARMING', 'true').lower() == 'true',
            cache_warming_batch_size=int(os.getenv('CACHE_WARMING_BATCH_SIZE', cls.cache_warming_batch_size)),
            max_memory_usage_ratio=float(os.getenv('CACHE_MAX_MEMORY_RATIO', cls.max_memory_usage_ratio))
        )


@dataclass
class PerformanceConfig:
    """Performance monitoring configuration"""
    enable_monitoring: bool = True
    max_concurrent_users: int = 1000
    request_timeout_seconds: int = 30
    rate_limit_requests_per_minute: int = 60
    enable_detailed_logging: bool = False
    log_level: str = "INFO"
    metrics_retention_days: int = 7

    @classmethod
    def from_env(cls) -> 'PerformanceConfig':
        """Create performance config from environment variables"""
        return cls(
            enable_monitoring=os.getenv('PERF_ENABLE_MONITORING', 'true').lower() == 'true',
            max_concurrent_users=int(os.getenv('PERF_MAX_CONCURRENT_USERS', cls.max_concurrent_users)),
            request_timeout_seconds=int(os.getenv('PERF_REQUEST_TIMEOUT', cls.request_timeout_seconds)),
            rate_limit_requests_per_minute=int(os.getenv('PERF_RATE_LIMIT', cls.rate_limit_requests_per_minute)),
            enable_detailed_logging=os.getenv('PERF_DETAILED_LOGGING', 'false').lower() == 'true',
            log_level=os.getenv('LOG_LEVEL', cls.log_level),
            metrics_retention_days=int(os.getenv('PERF_METRICS_RETENTION', cls.metrics_retention_days))
        )


@dataclass
class SecurityConfig:
    """Security configuration settings"""
    enable_cors: bool = True
    cors_origins: list = field(default_factory=lambda: ["*"])
    enable_rate_limiting: bool = True
    enable_request_logging: bool = True
    api_key_required: bool = False
    jwt_secret_key: Optional[str] = None
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24

    @classmethod
    def from_env(cls) -> 'SecurityConfig':
        """Create security config from environment variables"""
        cors_origins = os.getenv('CORS_ORIGINS', "*").split(',')

        return cls(
            enable_cors=os.getenv('SECURITY_ENABLE_CORS', 'true').lower() == 'true',
            cors_origins=cors_origins,
            enable_rate_limiting=os.getenv('SECURITY_ENABLE_RATE_LIMITING', 'true').lower() == 'true',
            enable_request_logging=os.getenv('SECURITY_ENABLE_REQUEST_LOGGING', 'true').lower() == 'true',
            api_key_required=os.getenv('SECURITY_API_KEY_REQUIRED', 'false').lower() == 'true',
            jwt_secret_key=os.getenv('JWT_SECRET_KEY'),
            jwt_algorithm=os.getenv('JWT_ALGORITHM', cls.jwt_algorithm),
            jwt_expiration_hours=int(os.getenv('JWT_EXPIRATION_HOURS', cls.jwt_expiration_hours))
        )


@dataclass
class SystemConfig:
    """Main system configuration"""
    database: DatabaseConfig
    redis: RedisConfig
    ml: MLConfig
    cache: CacheConfig
    performance: PerformanceConfig
    security: SecurityConfig

    # Application settings
    app_name: str = "Human Capital Development API"
    app_version: str = "1.0.0"
    debug_mode: bool = False
    environment: str = "development"

    # File paths
    data_path: Path = Path(".")
    logs_path: Path = Path("logs")

    @classmethod
    def from_env(cls) -> 'SystemConfig':
        """Create system config from environment variables"""
        return cls(
            database=DatabaseConfig.from_env(),
            redis=RedisConfig.from_env(),
            ml=MLConfig.from_env(),
            cache=CacheConfig.from_env(),
            performance=PerformanceConfig.from_env(),
            security=SecurityConfig.from_env(),
            debug_mode=os.getenv('DEBUG', 'false').lower() == 'true',
            environment=os.getenv('ENVIRONMENT', 'development'),
            data_path=Path(os.getenv('DATA_PATH', '.')),
            logs_path=Path(os.getenv('LOGS_PATH', 'logs'))
        )

    def validate(self) -> bool:
        """Validate configuration settings"""
        try:
            # Check required directories
            self.data_path.mkdir(exist_ok=True)
            self.logs_path.mkdir(exist_ok=True)

            # Validate database connection string
            db_conn_str = self.database.get_connection_string()
            if not db_conn_str or len(db_conn_str) < 20:
                raise ValueError("Invalid database connection string")

            # Validate ML weights sum to 1
            embedding_weights_sum = sum(self.ml.embedding_weights.values())
            if abs(embedding_weights_sum - 1.0) > 0.01:
                raise ValueError("ML embedding weights must sum to 1.0")

            # Validate objectives
            for objective, weights in self.ml.recommendation_objectives.items():
                obj_weights_sum = sum(weights.values())
                if abs(obj_weights_sum - 1.0) > 0.01:
                    raise ValueError(f"Objective '{objective}' weights must sum to 1.0")

            # Validate thresholds
            if not (0 <= self.ml.default_similarity_threshold <= 1):
                raise ValueError("Similarity threshold must be between 0 and 1")

            if not (0 <= self.cache.max_memory_usage_ratio <= 1):
                raise ValueError("Max memory usage ratio must be between 0 and 1")

            return True

        except Exception as e:
            print(f"Configuration validation failed: {e}")
            return False

    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration as dictionary"""
        return self.database.to_dict()

    def get_redis_config(self) -> Dict[str, Any]:
        """Get Redis configuration as dictionary"""
        return self.redis.to_dict()

    def to_dict(self) -> Dict[str, Any]:
        """Convert entire configuration to dictionary"""
        return {
            'database': self.database.to_dict(),
            'redis': self.redis.to_dict(),
            'ml': self.ml.__dict__,
            'cache': self.cache.__dict__,
            'performance': self.performance.__dict__,
            'security': self.security.__dict__,
            'app_name': self.app_name,
            'app_version': self.app_version,
            'debug_mode': self.debug_mode,
            'environment': self.environment
        }


def load_config() -> SystemConfig:
    """Load system configuration from environment variables"""
    return SystemConfig.from_env()


def create_default_config() -> SystemConfig:
    """Create default system configuration"""
    return SystemConfig(
        database=DatabaseConfig(),
        redis=RedisConfig(),
        ml=MLConfig(),
        cache=CacheConfig(),
        performance=PerformanceConfig(),
        security=SecurityConfig()
    )


def generate_pgadmin_config(db_config: DatabaseConfig, output_path: str = "config/pgadmin_servers.json") -> bool:
    """Generate pgAdmin servers.json configuration file"""
    try:
        import json

        pgadmin_config = {
            "Servers": {
                "1": {
                    "Name": "Human Capital Development",
                    "Group": "Servers",
                    "Host": db_config.host,
                    "Port": db_config.port,
                    "MaintenanceDB": db_config.database,
                    "Username": db_config.user,
                    "SSLMode": "prefer",
                    "SSLCert": "<STORAGE_DIR>/.postgresql/postgresql.crt",
                    "SSLKey": "<STORAGE_DIR>/.postgresql/postgresql.key",
                    "SSLCompression": 0,
                    "Timeout": 10,
                    "UseSSHTunnel": 0,
                    "TunnelPort": "22",
                    "TunnelAuthentication": 0
                }
            }
        }

        with open(output_path, 'w') as f:
            json.dump(pgadmin_config, f, indent=2)

        print(f"✅ pgAdmin configuration generated at {output_path}")
        return True

    except Exception as e:
        print(f"❌ Failed to generate pgAdmin config: {e}")
        return False
