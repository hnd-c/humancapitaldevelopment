#!/usr/bin/env python3
"""
Database Setup - Handle database schema creation and migration

This module handles:
- Database schema creation
- Data migration from CSV/Parquet to PostgreSQL
- Database optimization and indexing
"""

import os
import glob
import time
from typing import Dict, Any, Optional
from data.database_manager import DatabaseManager


class DatabaseSetup:
    """Handles database schema creation and data migration"""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def create_schema(self) -> bool:
        """Create the complete database schema"""
        try:
            print("🔨 Creating database schema...")

            # This would integrate with existing create_normalized_schema.py
            from create_normalized_schema import create_normalized_schema

            # Find latest student history file
            files = glob.glob("student_history_enhanced_*.csv")
            if not files:
                print("❌ No student history files found for schema creation")
                return False

            latest_file = max(files, key=os.path.getctime)
            print(f"📂 Using {latest_file} for schema creation")

            # Create normalized tables
            normalized_tables = create_normalized_schema(latest_file)

            print("✅ Database schema created successfully")
            return True

        except Exception as e:
            print(f"❌ Failed to create database schema: {e}")
            return False

    def migrate_data(self, source_type: str = 'csv') -> Dict[str, Any]:
        """Migrate data from legacy format to optimized database"""
        print("🔄 Starting data migration...")

        try:
            # Import our PostgreSQL loader
            import sys
            import os
            sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scripts'))
            from load_to_postgres import PostgreSQLDataLoader

            # Run migration
            loader = PostgreSQLDataLoader()
            migration_stats = loader.run_full_load(clear_existing=True)

            return migration_stats

        except Exception as e:
            migration_stats = {
                'status': 'error',
                'error': str(e),
                'duration_seconds': 0
            }
            return migration_stats

    def create_indexes(self) -> bool:
        """Create optimized indexes for performance"""
        try:
            print("📊 Creating database indexes...")

            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor()

                # Read and execute index creation script from new location
                index_file = 'database/migrations/02_halfprecision_indexes.sql'
                with open(index_file, 'r') as f:
                    index_script = f.read()

                cursor.execute(index_script)
                conn.commit()

            print("✅ Database indexes created successfully")
            return True

        except Exception as e:
            print(f"❌ Failed to create indexes: {e}")
            return False

    def validate_migration(self) -> Dict[str, Any]:
        """Validate that migration was successful"""
        try:
            validation_results = {}

            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor()

                # Check table counts
                tables = ['questions', 'students', 'student_question_history', 'papers']
                for table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    validation_results[f'{table}_count'] = count
                    print(f"📊 {table}: {count:,} records")

                # Check for required columns
                cursor.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'questions'
                    AND column_name IN ('openai_embedding', 'soft_cluster')
                """)
                embedding_columns = [row[0] for row in cursor.fetchall()]
                validation_results['embedding_columns'] = embedding_columns

            validation_results['status'] = 'valid'
            print("✅ Migration validation completed")
            return validation_results

        except Exception as e:
            print(f"❌ Migration validation failed: {e}")
            return {'status': 'error', 'error': str(e)}
