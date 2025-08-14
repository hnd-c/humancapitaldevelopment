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

# Import existing components
from data.database_manager import DatabaseManager
from services.cache_service import CacheService
from services.performance_service import PerformanceMonitor
from config.environments import SystemConfig


class SystemInitializer:
    """
    Main system bootstrap orchestrator that integrates all components
    """

    def __init__(self, config: SystemConfig):
        self.config = config
        self.start_time = time.time()

        print("🚀 Initializing Human Capital Development System...")
        print("=" * 60)

        # Initialize components in order
        self._initialize_database_layer()
        self._initialize_monitoring()

        print(f"✅ System initialized successfully in {time.time() - self.start_time:.2f}s")
        print("=" * 60)

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
            self.cache_manager = CacheService(self.db_manager.redis_client)

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
        print("🛑 Shutting down Human Capital Development System...")

        try:
            # Close Redis connections
            if hasattr(self, 'db_manager') and self.db_manager.redis_client:
                self.db_manager.redis_client.close()

            print("✅ System shutdown completed")

        except Exception as e:
            print(f"⚠️  Error during shutdown: {e}")
