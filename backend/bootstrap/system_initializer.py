#!/usr/bin/env python3
"""
System Initializer - Bootstrap logic for the Human Capital Development System

This module handles the complete system initialization process including:
- Configuration validation
- Database connections
- ML component loading
- System health checks
"""

import os
import time
import sys
from typing import Dict, Any, Optional
from dataclasses import dataclass

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("📄 .env file loaded successfully")
except ImportError:
    print("⚠️  python-dotenv not installed, using system environment variables only")
except Exception as e:
    print(f"⚠️  Error loading .env file: {e}")

# Import existing components
from data.database_manager import DatabaseManager
from services.cache_service import CacheService
from services.performance_service import PerformanceMonitor
from config.config import SystemConfig


class SystemInitializer:
    """
    Main system bootstrap orchestrator that integrates all components
    """

    def __init__(self, config: SystemConfig):
        self.config = config
        self.start_time = time.time()

        print("🚀 Initializing Human Capital Development System...")
        print("=" * 60)

        # Debug environment variables
        self._debug_environment_variables()

        # Initialize components in order
        self._initialize_database_layer()
        self._initialize_monitoring()

        print(f"✅ System initialized successfully in {time.time() - self.start_time:.2f}s")
        print("=" * 60)

    def _debug_environment_variables(self):
        """Debug environment variables for troubleshooting"""
        print("🔍 Environment Variables Debug:")

        # Database variables
        db_vars = ['DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD']
        for var in db_vars:
            value = os.getenv(var, 'NOT_SET')
            if var == 'DB_PASSWORD':
                # Mask password but show if it's set
                display_value = '***MASKED***' if value != 'NOT_SET' and value else 'NOT_SET'
            else:
                display_value = value
            print(f"  {var}: {display_value}")

        # Other important variables
        other_vars = ['ENVIRONMENT', 'DEBUG', 'JWT_SECRET_KEY', 'REDIS_HOST', 'REDIS_PASSWORD']
        for var in other_vars:
            value = os.getenv(var, 'NOT_SET')
            if 'SECRET' in var or 'PASSWORD' in var:
                display_value = '***MASKED***' if value != 'NOT_SET' and value else 'NOT_SET'
            else:
                display_value = value
            print(f"  {var}: {display_value}")

        print()

    def _initialize_database_layer(self):
        """Initialize database and caching layer"""
        print("📊 Initializing database layer...")

        try:
            # Database manager
            self.db_manager = DatabaseManager(
                db_config=self.config.database.to_dict(),
                redis_config=self.config.redis.to_dict()
            )

            # Cache manager
            self.cache_manager = CacheService(self.db_manager.redis_client, self.db_manager)

            # Test connections
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                assert cursor.fetchone()[0] == 1

            # Test Redis
            self.db_manager.redis_client.ping()

            print("✅ Database layer initialized successfully")

        except Exception as e:
            print(f"❌ Failed to initialize database layer: {e}")
            raise



    def _initialize_monitoring(self):
        """Initialize performance monitoring"""
        print("📈 Initializing performance monitoring...")

        if self.config.performance.enable_monitoring:
            self.performance_monitor = PerformanceMonitor(self.db_manager.redis_client)
            print("✅ Performance monitoring enabled")
        else:
            self.performance_monitor = None
            print("⚠️  Performance monitoring disabled")

    def get_system_instance(self):
        """Return initialized system components"""
        return {
            'db_manager': self.db_manager,
            'cache_manager': self.cache_manager,
            'performance_monitor': self.performance_monitor,
            'config': self.config
        }

    def shutdown(self):
        """Graceful system shutdown"""
        print("🛑 Shutting down system components...")

        try:
            # Close database pools
            if hasattr(self, 'db_manager') and self.db_manager:
                self.db_manager.close_pools()

            # Close Redis connections
            if hasattr(self, 'db_manager') and self.db_manager.redis_client:
                self.db_manager.redis_client.close()

            print("✅ System shutdown completed")

        except Exception as e:
            print(f"⚠️  Error during shutdown: {e}")
