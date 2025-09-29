#!/usr/bin/env python3
"""
Environment Configurations - Environment-specific settings

This module handles:
- Development environment configuration
- Staging environment configuration
- Production environment configuration
- Environment detection and selection
"""

import os
from typing import Dict, Any, Optional
from .settings import SystemConfig, DatabaseConfig, RedisConfig, MLConfig, CacheConfig, PerformanceConfig, SecurityConfig


class DevelopmentConfig(SystemConfig):
    """Development environment configuration"""

    def __init__(self):
        super().__init__(
            database=DatabaseConfig(
                host="localhost",
                port=5432,
                database="human_capital_dev",
                user="hcd_user",
                password=os.getenv("DB_PASSWORD", ""),
                connection_pool_size=5,
                max_overflow=10
            ),
            redis=RedisConfig(
                host="localhost",
                port=6379,
                db=0,
                max_connections=10
            ),
            ml=MLConfig(),
            cache=CacheConfig(),
            performance=PerformanceConfig(
                enable_monitoring=True,
                enable_detailed_logging=True,
                log_level="DEBUG",
                max_concurrent_users=50,
                rate_limit_requests_per_minute=100
            ),
            security=SecurityConfig(
                enable_cors=True,
                cors_origins=["http://localhost:3000", "http://localhost:8000"],
                enable_rate_limiting=False,  # Disabled for development
                enable_request_logging=True,
                api_key_required=False
            ),
            debug_mode=True,
            environment="development"
        )


class StagingConfig(SystemConfig):
    """Staging environment configuration"""

    def __init__(self):
        super().__init__(
            database=DatabaseConfig(
                host=os.getenv("STAGING_DB_HOST", "staging-db.example.com"),
                port=int(os.getenv("STAGING_DB_PORT", 5432)),
                database=os.getenv("STAGING_DB_NAME", "human_capital_staging"),
                user=os.getenv("STAGING_DB_USER", "hcd_staging"),
                password=os.getenv("STAGING_DB_PASSWORD", ""),
                connection_pool_size=10,
                max_overflow=20
            ),
            redis=RedisConfig(
                host=os.getenv("STAGING_REDIS_HOST", "staging-redis.example.com"),
                port=int(os.getenv("STAGING_REDIS_PORT", 6379)),
                db=int(os.getenv("STAGING_REDIS_DB", 0)),
                password=os.getenv("STAGING_REDIS_PASSWORD"),
                max_connections=25
            ),
            ml=MLConfig(),
            cache=CacheConfig(),
            performance=PerformanceConfig(
                enable_monitoring=True,
                enable_detailed_logging=False,
                log_level="INFO",
                max_concurrent_users=200,
                rate_limit_requests_per_minute=120
            ),
            security=SecurityConfig(
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
            debug_mode=False,
            environment="staging"
        )


class ProductionConfig(SystemConfig):
    """Production environment configuration"""

    def __init__(self):
        super().__init__(
            database=DatabaseConfig(
                host=os.getenv("PROD_DB_HOST", "prod-db.example.com"),
                port=int(os.getenv("PROD_DB_PORT", 5432)),
                database=os.getenv("PROD_DB_NAME", "human_capital_prod"),
                user=os.getenv("PROD_DB_USER", "hcd_prod"),
                password=os.getenv("PROD_DB_PASSWORD"),
                connection_pool_size=20,
                max_overflow=30,
                pool_timeout=30,
                pool_recycle=3600
            ),
            redis=RedisConfig(
                host=os.getenv("PROD_REDIS_HOST", "prod-redis.example.com"),
                port=int(os.getenv("PROD_REDIS_PORT", 6379)),
                db=int(os.getenv("PROD_REDIS_DB", 0)),
                password=os.getenv("PROD_REDIS_PASSWORD"),
                max_connections=50,
                socket_timeout=30,
                socket_connect_timeout=30
            ),
            ml=MLConfig(),
            cache=CacheConfig(),
            performance=PerformanceConfig(
                enable_monitoring=True,
                enable_detailed_logging=False,
                log_level="WARNING",
                max_concurrent_users=1000,
                rate_limit_requests_per_minute=60,
                request_timeout_seconds=30,
                metrics_retention_days=30
            ),
            security=SecurityConfig(
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
            debug_mode=False,
            environment="production"
        )

    def validate(self) -> bool:
        """Additional validation for production environment"""
        if not super().validate():
            return False

        # Production-specific validations
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
            print(f"Missing required production environment variables: {missing_vars}")
            return False

        # Validate JWT secret strength
        jwt_secret = os.getenv("PROD_JWT_SECRET")
        if jwt_secret and len(jwt_secret) < 32:
            print("Production JWT secret must be at least 32 characters long")
            return False

        return True


class TestConfig(SystemConfig):
    """Test environment configuration"""

    def __init__(self):
        super().__init__(
            database=DatabaseConfig(
                host="localhost",
                port=5432,
                database="human_capital_test",
                user="hcd_test",
                password=os.getenv("TEST_DB_PASSWORD", ""),
                connection_pool_size=2,
                max_overflow=5
            ),
            redis=RedisConfig(
                host="localhost",
                port=6379,
                db=1,  # Different DB for tests
                max_connections=5
            ),
            ml=MLConfig(),
            cache=CacheConfig(),
            performance=PerformanceConfig(
                enable_monitoring=False,
                enable_detailed_logging=False,
                log_level="ERROR",
                max_concurrent_users=10,
                rate_limit_requests_per_minute=1000  # No rate limiting in tests
            ),
            security=SecurityConfig(
                enable_cors=False,
                enable_rate_limiting=False,
                enable_request_logging=False,
                api_key_required=False
            ),
            debug_mode=True,
            environment="test"
        )


def get_environment() -> str:
    """Get current environment from environment variable"""
    return os.getenv("ENVIRONMENT", "development").lower()


def load_config_for_environment(environment: Optional[str] = None) -> SystemConfig:
    """Load configuration for specific environment"""
    if environment is None:
        environment = get_environment()

    environment = environment.lower()

    if environment == "production":
        config = ProductionConfig()
    elif environment == "staging":
        config = StagingConfig()
    elif environment == "test":
        config = TestConfig()
    else:
        config = DevelopmentConfig()

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


# Environment configuration mapping
ENVIRONMENT_CONFIGS = {
    'development': DevelopmentConfig,
    'staging': StagingConfig,
    'production': ProductionConfig,
    'test': TestConfig
}


def create_config(environment: str) -> SystemConfig:
    """Create configuration instance for given environment"""
    if environment not in ENVIRONMENT_CONFIGS:
        raise ValueError(f"Unknown environment: {environment}. Valid options: {list(ENVIRONMENT_CONFIGS.keys())}")

    return ENVIRONMENT_CONFIGS[environment]()


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


# Load default configuration based on environment
default_config = load_config_for_environment()
