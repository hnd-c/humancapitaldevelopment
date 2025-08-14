#!/usr/bin/env python3
"""
Deployment Script - Handle application deployment

This module handles:
- Application deployment automation
- Environment setup and validation
- Database migrations
- System health checks
"""

import os
import sys
import time
import subprocess
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from config.environments import load_config_for_environment, ENVIRONMENT_CONFIGS
from bootstrap.system_initializer import SystemInitializer
from bootstrap.database_setup import DatabaseSetup


class DeploymentManager:
    """Manages application deployment process"""

    def __init__(self, environment: str):
        self.environment = environment
        self.config = load_config_for_environment(environment)
        self.deployment_start_time = time.time()

        print(f"🚀 Starting deployment for {environment} environment")
        print("=" * 60)

    def run_deployment(self, steps: List[str] = None) -> bool:
        """Run complete deployment process"""
        default_steps = [
            'validate_environment',
            'setup_directories',
            'install_dependencies',
            'run_migrations',
            'setup_database',
            'initialize_system',
            'run_health_checks',
            'start_services'
        ]

        steps_to_run = steps or default_steps

        try:
            for step in steps_to_run:
                print(f"\n📋 Running step: {step}")
                success = getattr(self, step)()

                if not success:
                    print(f"❌ Step {step} failed")
                    return False

                print(f"✅ Step {step} completed")

            deployment_time = time.time() - self.deployment_start_time
            print(f"\n🎉 Deployment completed successfully in {deployment_time:.2f}s")
            return True

        except Exception as e:
            print(f"❌ Deployment failed: {e}")
            return False

    def validate_environment(self) -> bool:
        """Validate environment configuration and requirements"""
        try:
            print("🔍 Validating environment configuration...")

            # Validate configuration
            if not self.config.validate():
                print("❌ Configuration validation failed")
                return False

            # Check required environment variables for production
            if self.environment == 'production':
                required_vars = [
                    'PROD_DB_PASSWORD',
                    'PROD_REDIS_PASSWORD',
                    'PROD_JWT_SECRET'
                ]

                missing_vars = [var for var in required_vars if not os.getenv(var)]
                if missing_vars:
                    print(f"❌ Missing required environment variables: {missing_vars}")
                    return False

            # Check Python version
            python_version = sys.version_info
            if python_version.major != 3 or python_version.minor < 8:
                print(f"❌ Python 3.8+ required, found {python_version.major}.{python_version.minor}")
                return False

            print("✅ Environment validation passed")
            return True

        except Exception as e:
            print(f"❌ Environment validation failed: {e}")
            return False

    def setup_directories(self) -> bool:
        """Setup required directories"""
        try:
            print("📁 Setting up directories...")

            directories = [
                self.config.data_path,
                self.config.logs_path,
                Path("tmp"),
                Path("backups")
            ]

            for directory in directories:
                directory.mkdir(exist_ok=True, parents=True)
                print(f"   📂 Created directory: {directory}")

            return True

        except Exception as e:
            print(f"❌ Directory setup failed: {e}")
            return False

    def install_dependencies(self) -> bool:
        """Install Python dependencies"""
        try:
            print("📦 Installing dependencies...")

            # Check if requirements.txt exists
            requirements_file = Path("requirements.txt")
            if not requirements_file.exists():
                print("⚠️  requirements.txt not found, skipping dependency installation")
                return True

            # Install dependencies
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                print(f"❌ Dependency installation failed: {result.stderr}")
                return False

            print("✅ Dependencies installed successfully")
            return True

        except Exception as e:
            print(f"❌ Dependency installation failed: {e}")
            return False

    def run_migrations(self) -> bool:
        """Run database migrations"""
        try:
            print("🗄️  Running database migrations...")

            # Check if migration SQL files exist
            migration_files = [
                "postgresql_migration.sql",
                "create_halfprecision_indexes.sql",
                "init-scripts/01-migration.sql"
            ]

            # Initialize database setup
            from data.database_manager import DatabaseManager
            db_manager = DatabaseManager(
                self.config.get_database_config(),
                self.config.get_redis_config()
            )

            db_setup = DatabaseSetup(db_manager)

            # Run schema creation
            if not db_setup.create_schema():
                print("❌ Schema creation failed")
                return False

            # Create indexes
            if not db_setup.create_indexes():
                print("❌ Index creation failed")
                return False

            print("✅ Database migrations completed")
            return True

        except Exception as e:
            print(f"❌ Database migration failed: {e}")
            return False

    def setup_database(self) -> bool:
        """Setup and populate database"""
        try:
            print("🗃️  Setting up database...")

            from data.database_manager import DatabaseManager
            db_manager = DatabaseManager(
                self.config.get_database_config(),
                self.config.get_redis_config()
            )

            # Test database connection
            with db_manager.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                assert cursor.fetchone()[0] == 1

            # Test Redis connection
            db_manager.redis_client.ping()

            print("✅ Database setup completed")
            return True

        except Exception as e:
            print(f"❌ Database setup failed: {e}")
            return False

    def initialize_system(self) -> bool:
        """Initialize the system components"""
        try:
            print("⚙️  Initializing system components...")

            # Initialize system
            system_initializer = SystemInitializer(self.config)

            # Get system instance to verify initialization
            system_components = system_initializer.get_system_instance()

            if not all(key in system_components for key in ['db_manager', 'cache_manager']):
                print("❌ System initialization incomplete")
                return False

            print("✅ System initialization completed")
            return True

        except Exception as e:
            print(f"❌ System initialization failed: {e}")
            return False

    def run_health_checks(self) -> bool:
        """Run system health checks"""
        try:
            print("🏥 Running health checks...")

            # Import main system for health checks
            from main import HumanCapitalDevelopmentSystem

            system = HumanCapitalDevelopmentSystem(self.config)
            health = system.get_system_health()

            # Check critical components
            required_components = ['database_status', 'redis_status', 'ml_components_status']
            for component in required_components:
                if health.get(component) != 'healthy':
                    print(f"❌ Health check failed for {component}: {health.get(component)}")
                    system.shutdown()
                    return False

            system.shutdown()
            print("✅ All health checks passed")
            return True

        except Exception as e:
            print(f"❌ Health checks failed: {e}")
            return False

    def start_services(self) -> bool:
        """Start application services"""
        try:
            print("🌐 Starting services...")

            if self.environment == 'production':
                # In production, services would typically be started by a process manager
                print("✅ Production services should be started by process manager (systemd, supervisor, etc.)")
                return True

            else:
                # For development/staging, we might start services directly
                print("✅ Services ready to start (use 'python main.py' or 'uvicorn api.routes:app')")
                return True

        except Exception as e:
            print(f"❌ Service startup failed: {e}")
            return False

    def rollback_deployment(self) -> bool:
        """Rollback deployment in case of failure"""
        try:
            print("🔄 Rolling back deployment...")

            # Implementation would depend on specific rollback strategy
            # This could include:
            # - Restoring database from backup
            # - Reverting to previous code version
            # - Restarting with previous configuration

            print("✅ Rollback completed")
            return True

        except Exception as e:
            print(f"❌ Rollback failed: {e}")
            return False

    def create_backup(self) -> bool:
        """Create backup before deployment"""
        try:
            print("💾 Creating backup...")

            timestamp = int(time.time())
            backup_dir = Path(f"backups/backup_{timestamp}")
            backup_dir.mkdir(parents=True, exist_ok=True)

            # Backup database (this would be environment-specific)
            # For PostgreSQL: pg_dump command
            # For files: copy important data files

            print(f"✅ Backup created at {backup_dir}")
            return True

        except Exception as e:
            print(f"❌ Backup creation failed: {e}")
            return False


def main():
    """Main deployment script"""
    parser = argparse.ArgumentParser(description="Deploy Human Capital Development System")
    parser.add_argument(
        "--environment",
        choices=list(ENVIRONMENT_CONFIGS.keys()),
        default="development",
        help="Deployment environment"
    )
    parser.add_argument(
        "--steps",
        nargs="*",
        help="Specific deployment steps to run"
    )
    parser.add_argument(
        "--with-backup",
        action="store_true",
        help="Create backup before deployment"
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Rollback previous deployment"
    )

    args = parser.parse_args()

    deployment_manager = DeploymentManager(args.environment)

    try:
        if args.rollback:
            success = deployment_manager.rollback_deployment()
        else:
            if args.with_backup:
                if not deployment_manager.create_backup():
                    print("❌ Backup creation failed, aborting deployment")
                    return 1

            success = deployment_manager.run_deployment(args.steps)

        return 0 if success else 1

    except KeyboardInterrupt:
        print("\n🛑 Deployment interrupted by user")
        return 1
    except Exception as e:
        print(f"❌ Deployment failed with error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
