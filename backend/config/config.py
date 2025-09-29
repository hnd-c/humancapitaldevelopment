#!/usr/bin/env python3
"""
Consolidated Configuration System - Human Capital Development API

This module provides a unified configuration system that consolidates all
application settings into a single, maintainable structure with environment-specific
overrides and comprehensive validation.

Features:
- Environment-agnostic base configuration
- Environment-specific profiles with minimal duplication
- Comprehensive validation and error handling
- Type-safe dataclass-based configuration
- Easy deployment and maintenance
"""

import os
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DatabaseProfile:
    """Database configuration profile"""
    host: str = "localhost"
    port: int = 5432
    database: str = "human_capital_dev"
    user: str = "hcd_user"
    password: str = ""  # Must be set via environment variables
    connection_pool_size: int = 20
    max_overflow: int = 30
    pool_timeout: int = 30
    pool_recycle: int = 3600

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
class RedisProfile:
    """Redis configuration profile"""
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    decode_responses: bool = False  # Must be False for binary cache data (gzip compressed)
    socket_timeout: int = 30
    socket_connect_timeout: int = 30
    max_connections: int = 50

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
class MLProfile:
    """Machine Learning configuration profile"""
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


@dataclass
class CacheProfile:
    """Caching configuration profile"""
    default_ttl_seconds: int = 600
    recommendation_ttl_seconds: int = 1800
    student_profile_ttl_seconds: int = 900
    similarity_ttl_seconds: int = 3600
    embeddings_ttl_seconds: int = 7200
    enable_cache_warming: bool = True
    cache_warming_batch_size: int = 100
    max_memory_usage_ratio: float = 0.8


@dataclass
class PerformanceProfile:
    """Performance monitoring configuration profile"""
    enable_monitoring: bool = True
    max_concurrent_users: int = 1000
    request_timeout_seconds: int = 30
    rate_limit_requests_per_minute: int = 60
    enable_detailed_logging: bool = False
    log_level: str = "INFO"
    metrics_retention_days: int = 7


@dataclass
class SecurityProfile:
    """Security configuration profile"""
    enable_cors: bool = True
    cors_origins: List[str] = field(default_factory=lambda: ["*"])
    enable_rate_limiting: bool = True
    enable_request_logging: bool = True
    api_key_required: bool = False
    jwt_secret_key: Optional[str] = None
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24


@dataclass
class SystemConfig:
    """Main system configuration with environment-specific profiles"""
    # Core profiles
    database: DatabaseProfile
    redis: RedisProfile
    ml: MLProfile
    cache: CacheProfile
    performance: PerformanceProfile
    security: SecurityProfile

    # Application settings
    app_name: str = "Human Capital Development API"
    app_version: str = "1.0.0"
    debug_mode: bool = False
    environment: str = "development"

    # File paths
    data_path: Path = Path(".")
    logs_path: Path = Path("logs")

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


# Environment-specific configuration profiles with minimal duplication
ENVIRONMENT_PROFILES = {
    'development': {
        'database': DatabaseProfile(
            connection_pool_size=5,
            max_overflow=10
        ),
        'redis': RedisProfile(
            max_connections=10
        ),
        'performance': PerformanceProfile(
            enable_monitoring=True,
            enable_detailed_logging=True,
            log_level="DEBUG",
            max_concurrent_users=50,
            rate_limit_requests_per_minute=100
        ),
        'security': SecurityProfile(
            enable_cors=True,
            cors_origins=["http://localhost:3000", "http://localhost:8000"],
            enable_rate_limiting=False,  # Disabled for development
            enable_request_logging=True,
            api_key_required=False,
            jwt_secret_key=os.getenv('JWT_SECRET_KEY')
        ),
        'debug_mode': True,
        'environment': 'development'
    },

    'staging': {
        'database': DatabaseProfile(
            host="staging-db.example.com",
            database="human_capital_staging",
            user="hcd_staging",
            connection_pool_size=10,
            max_overflow=20
        ),
        'redis': RedisProfile(
            host=os.getenv("STAGING_REDIS_HOST", "staging-redis.example.com"),
            port=int(os.getenv("STAGING_REDIS_PORT", 6379)),
            db=int(os.getenv("STAGING_REDIS_DB", 0)),
            password=os.getenv("STAGING_REDIS_PASSWORD"),
            max_connections=25
        ),
        'performance': PerformanceProfile(
            enable_monitoring=True,
            enable_detailed_logging=False,
            log_level="INFO",
            max_concurrent_users=200,
            rate_limit_requests_per_minute=120
        ),
        'security': SecurityProfile(
            enable_cors=True,
            cors_origins=[
                "https://staging.humancapital.example.com",
                "https://staging-admin.humancapital.example.com"
            ],
            enable_rate_limiting=True,
            enable_request_logging=True,
            api_key_required=True,
            jwt_secret_key=os.getenv("STAGING_JWT_SECRET")
        ),
        'debug_mode': False,
        'environment': 'staging'
    },

    'production': {
        'database': DatabaseProfile(
            host="prod-db.example.com",
            database="human_capital_prod",
            user="hcd_prod",
            connection_pool_size=20,
            max_overflow=30,
            pool_timeout=30,
            pool_recycle=3600
        ),
        'redis': RedisProfile(
            host=os.getenv("PROD_REDIS_HOST", "prod-redis.example.com"),
            port=int(os.getenv("PROD_REDIS_PORT", 6379)),
            db=int(os.getenv("PROD_REDIS_DB", 0)),
            password=os.getenv("PROD_REDIS_PASSWORD"),
            max_connections=50,
            socket_timeout=30,
            socket_connect_timeout=30
        ),
        'performance': PerformanceProfile(
            enable_monitoring=True,
            enable_detailed_logging=False,
            log_level="WARNING",
            max_concurrent_users=1000,
            rate_limit_requests_per_minute=60,
            request_timeout_seconds=30,
            metrics_retention_days=30
        ),
        'security': SecurityProfile(
            enable_cors=True,
            cors_origins=[
                "https://humancapital.example.com",
                "https://admin.humancapital.example.com",
                "https://api.humancapital.example.com"
            ],
            enable_rate_limiting=True,
            enable_request_logging=True,
            api_key_required=True,
            jwt_secret_key=os.getenv("PROD_JWT_SECRET"),
            jwt_expiration_hours=12
        ),
        'debug_mode': False,
        'environment': 'production'
    },

    'test': {
        'database': DatabaseProfile(
            database="human_capital_test",
            user="hcd_test",
            connection_pool_size=2,
            max_overflow=5
        ),
        'redis': RedisProfile(
            db=1,  # Different DB for tests
            max_connections=5
        ),
        'performance': PerformanceProfile(
            enable_monitoring=False,
            enable_detailed_logging=False,
            log_level="ERROR",
            max_concurrent_users=10,
            rate_limit_requests_per_minute=1000  # No rate limiting in tests
        ),
        'security': SecurityProfile(
            enable_cors=False,
            enable_rate_limiting=False,
            enable_request_logging=False,
            api_key_required=False,
            jwt_secret_key=os.getenv('JWT_SECRET_KEY')
        ),
        'debug_mode': True,
        'environment': 'test'
    }
}


def get_environment() -> str:
    """Get current environment from environment variable"""
    return os.getenv("ENVIRONMENT", "development").lower()


def load_config_for_environment(environment: Optional[str] = None) -> SystemConfig:
    """Load configuration for specific environment"""
    if environment is None:
        environment = get_environment()

    environment = environment.lower()

    if environment not in ENVIRONMENT_PROFILES:
        raise ValueError(f"Unknown environment: {environment}. Valid options: {list(ENVIRONMENT_PROFILES.keys())}")

    profile = ENVIRONMENT_PROFILES[environment]

    # Get database profile and apply environment variables
    db_profile = profile.get('database', DatabaseProfile())
    # Apply environment-specific password
    if environment == 'development':
        db_profile.password = os.getenv('DB_PASSWORD', '')
    elif environment == 'staging':
        db_profile.password = os.getenv('STAGING_DB_PASSWORD', '')
    elif environment == 'production':
        db_profile.password = os.getenv('PROD_DB_PASSWORD', '')
    elif environment == 'test':
        db_profile.password = os.getenv('TEST_DB_PASSWORD', '')

    # Apply environment variables to ML config
    ml_config = MLProfile(
        use_multimodal_embeddings=os.getenv('ML_USE_MULTIMODAL', 'true').lower() == 'true',
        default_similarity_threshold=float(os.getenv('ML_SIMILARITY_THRESHOLD', 0.7)),
        cluster_transition_alpha=float(os.getenv('ML_TRANSITION_ALPHA', 0.1)),
        max_recommendations=int(os.getenv('ML_MAX_RECOMMENDATIONS', 50)),
        diversity_threshold=float(os.getenv('ML_DIVERSITY_THRESHOLD', 0.8))
    )

    # Apply environment variables to cache config
    cache_config = CacheProfile(
        default_ttl_seconds=int(os.getenv('CACHE_DEFAULT_TTL', 600)),
        recommendation_ttl_seconds=int(os.getenv('CACHE_RECOMMENDATION_TTL', 1800)),
        student_profile_ttl_seconds=int(os.getenv('CACHE_PROFILE_TTL', 900)),
        similarity_ttl_seconds=int(os.getenv('CACHE_SIMILARITY_TTL', 3600)),
        embeddings_ttl_seconds=int(os.getenv('CACHE_EMBEDDINGS_TTL', 7200)),
        enable_cache_warming=os.getenv('CACHE_ENABLE_WARMING', 'true').lower() == 'true',
        cache_warming_batch_size=int(os.getenv('CACHE_WARMING_BATCH_SIZE', 100)),
        max_memory_usage_ratio=float(os.getenv('CACHE_MAX_MEMORY_RATIO', 0.8))
    )

    # Create system config with profile overrides
    config = SystemConfig(
        database=db_profile,
        redis=profile.get('redis', RedisProfile()),
        ml=ml_config,
        cache=cache_config,
        performance=profile.get('performance', PerformanceProfile()),
        security=profile.get('security', SecurityProfile()),
        debug_mode=profile.get('debug_mode', False),
        environment=profile.get('environment', environment),
        data_path=Path(os.getenv('DATA_PATH', '.')),
        logs_path=Path(os.getenv('LOGS_PATH', 'logs'))
    )

    # Production-specific validation
    if environment == 'production':
        required_env_vars = [
            "PROD_DB_PASSWORD",
            "PROD_REDIS_PASSWORD",
            "PROD_JWT_SECRET",
            "S3_BUCKET_NAME",
            "S3_REGION"
        ]

        missing_vars = []
        for var in required_env_vars:
            if not os.getenv(var):
                missing_vars.append(var)

        if missing_vars:
            raise ValueError(f"Missing required production environment variables: {missing_vars}")

        # Validate JWT secret strength
        jwt_secret = os.getenv("PROD_JWT_SECRET")
        if jwt_secret and len(jwt_secret) < 32:
            raise ValueError("Production JWT secret must be at least 32 characters long")

    # Validate configuration
    if not config.validate():
        raise ValueError(f"Invalid configuration for environment: {environment}")

    return config


def get_database_url(environment: Optional[str] = None) -> str:
    """Get database URL for specific environment"""
    config = load_config_for_environment(environment)
    return config.database.get_connection_string()


def get_redis_config(environment: Optional[str] = None) -> Dict[str, Any]:
    """Get Redis configuration for specific environment"""
    config = load_config_for_environment(environment)
    return config.redis.to_dict()


def is_development() -> bool:
    """Check if running in development environment"""
    return get_environment() == "development"


def is_production() -> bool:
    """Check if running in production environment"""
    return get_environment() == "production"


def is_staging() -> bool:
    """Check if running in staging environment"""
    return get_environment() == "staging"


def is_test() -> bool:
    """Check if running in test environment"""
    return get_environment() == "test"


def generate_pgadmin_config(db_profile: DatabaseProfile, output_path: str = "config/pgadmin_servers.json") -> bool:
    """Generate pgAdmin servers.json configuration file with actual environment variable substitution"""
    try:
        pgadmin_config = {
            "Servers": {
                "1": {
                    "Name": "Human Capital Development",
                    "Group": "Servers",
                    "Host": db_profile.host,
                    "Port": db_profile.port,
                    "MaintenanceDB": db_profile.database,
                    "Username": db_profile.user,
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


def print_environment_info():
    """Print current environment information"""
    env = get_environment()
    config = load_config_for_environment(env)

    print(f"Environment: {env}")
    print(f"Debug Mode: {config.debug_mode}")
    print(f"Database: {config.database.host}:{config.database.port}/{config.database.database}")
    print(f"Redis: {config.redis.host}:{config.redis.port}/{config.redis.db}")
    print(f"Performance Monitoring: {config.performance.enable_monitoring}")
    print(f"Rate Limiting: {config.security.enable_rate_limiting}")
    print(f"CORS Enabled: {config.security.enable_cors}")


# Legacy compatibility functions (for backward compatibility during transition)
def load_config() -> SystemConfig:
    """Load system configuration from environment variables (legacy compatibility)"""
    return load_config_for_environment()


def create_default_config() -> SystemConfig:
    """Create default system configuration (legacy compatibility)"""
    return load_config_for_environment('development')


# Backward compatibility aliases
DatabaseConfig = DatabaseProfile
RedisConfig = RedisProfile
MLConfig = MLProfile
CacheConfig = CacheProfile
PerformanceConfig = PerformanceProfile
SecurityConfig = SecurityProfile

# Default configuration will be loaded on-demand when needed
# This prevents loading config before .env file is loaded
default_config = None
