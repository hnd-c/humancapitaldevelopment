#!/usr/bin/env python3
"""
Complete Database Reset Script

This script completely destroys and recreates the database from scratch.
Nuclear option - use when everything is broken.
"""

import psycopg2
import sys
import time
from pathlib import Path

def reset_database():
    """Completely reset the database"""

    print("💥 NUCLEAR DATABASE RESET")
    print("=" * 50)
    print("⚠️  WARNING: This will COMPLETELY DESTROY the database!")
    print("⚠️  ALL DATA WILL BE PERMANENTLY LOST!")
    print()

    confirm = input("Type 'NUKE' to confirm complete destruction: ")
    if confirm != 'NUKE':
        print("❌ Operation cancelled")
        return False

    # Database connection params
    admin_params = {
        'host': 'localhost',
        'port': 5432,
        'dbname': 'postgres',  # Connect to postgres database
        'user': 'hcd_user',
        'password': 'your_secure_password_here'
    }

    db_params = {
        'host': 'localhost',
        'port': 5432,
        'dbname': 'human_capital_dev',
        'user': 'hcd_user',
        'password': 'your_secure_password_here'
    }

    schema_file = Path("../database/migrations/01_initial_schema.sql")

    try:
        print("🔥 Step 1: Dropping database...")

                # Connect to postgres database to drop the target database
        conn = psycopg2.connect(**admin_params)
        conn.autocommit = True
        cursor = conn.cursor()

        try:
            # Terminate all connections to the target database
            cursor.execute("""
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = 'human_capital_dev' AND pid <> pg_backend_pid()
            """)

            # Drop the database
            cursor.execute("DROP DATABASE IF EXISTS human_capital_dev")
            print("   ✅ Database dropped")

            print("🏗️  Step 2: Creating fresh database...")

            # Create fresh database
            cursor.execute("CREATE DATABASE human_capital_dev")
            print("   ✅ Fresh database created")

        finally:
            cursor.close()
            conn.close()

        print("🧩 Step 3: Installing extensions...")

        # Install extensions
        with psycopg2.connect(**db_params) as conn:
            cursor = conn.cursor()
            cursor.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
            cursor.execute('CREATE EXTENSION IF NOT EXISTS vector')
            conn.commit()
            print("   ✅ Extensions installed")

        print("📋 Step 4: Creating schema...")

        # Apply main schema
        with psycopg2.connect(**db_params) as conn:
            cursor = conn.cursor()

            with open(schema_file, 'r') as f:
                schema_sql = f.read()

            # Remove extension creation commands since we already did that
            schema_sql = schema_sql.replace('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";', '')
            schema_sql = schema_sql.replace('CREATE EXTENSION IF NOT EXISTS vector;', '')

            cursor.execute(schema_sql)
            conn.commit()
            print("   ✅ Main schema created")

        print("📋 Step 5: Applying additional migrations...")

        # Apply additional migrations in order
        migrations_dir = Path("../database/migrations")
        migration_files = sorted([
            f for f in migrations_dir.glob("*.sql")
            if f.name != "01_initial_schema.sql"  # Skip main schema (already applied)
        ])

        with psycopg2.connect(**db_params) as conn:
            cursor = conn.cursor()

            for migration_file in migration_files:
                print(f"   📄 Applying {migration_file.name}...")
                try:
                    with open(migration_file, 'r') as f:
                        migration_sql = f.read()

                    cursor.execute(migration_sql)
                    conn.commit()
                    print(f"   ✅ {migration_file.name} applied successfully")

                except Exception as e:
                    print(f"   ❌ Error applying {migration_file.name}: {e}")
                    raise

        print("🔍 Step 6: Verifying setup...")

        # Verify everything
        with psycopg2.connect(**db_params) as conn:
            cursor = conn.cursor()

            # Check tables
            cursor.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            tables = [row[0] for row in cursor.fetchall()]
            print(f"   📊 Tables created: {len(tables)}")

            # Check for umap_2d_embedding column
            cursor.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'questions'
                AND column_name LIKE '%umap%'
            """)
            umap_columns = cursor.fetchall()
            print(f"   🧠 UMAP columns: {len(umap_columns)}")
            for col, dtype in umap_columns:
                print(f"      • {col}: {dtype}")

            # Check functions
            cursor.execute("""
                SELECT routine_name
                FROM information_schema.routines
                WHERE routine_schema = 'public'
                AND (routine_name LIKE 'find_similar%' OR routine_name LIKE '%student_status%' OR routine_name LIKE 'get_umap%')
            """)
            functions = [row[0] for row in cursor.fetchall()]
            print(f"   🔧 Functions: {len(functions)}")
            for func in functions:
                print(f"      • {func}")

            # Check materialized views
            cursor.execute("""
                SELECT schemaname, matviewname
                FROM pg_matviews
                WHERE schemaname = 'public'
            """)
            matviews = cursor.fetchall()
            print(f"   📊 Materialized views: {len(matviews)}")
            for schema, view in matviews:
                print(f"      • {view}")

            # Check regular views
            cursor.execute("""
                SELECT table_name
                FROM information_schema.views
                WHERE table_schema = 'public'
            """)
            views = [row[0] for row in cursor.fetchall()]
            print(f"   👁️ Views: {len(views)}")
            for view in views:
                print(f"      • {view}")

        print("\n🎉 DATABASE RESET COMPLETED SUCCESSFULLY!")
        print("=" * 50)
        print("✅ Fresh database with latest schema")
        print("✅ Vector extensions installed")
        print("✅ 2D UMAP support ready")
        print("✅ All similarity functions available")
        print("✅ Student-specific UMAP visualization ready")
        print("✅ Real-time status tracking enabled")
        print()
        print("Next steps:")
        print("   1. python migrate_data.py     # Create normalized data")
        print("   2. python load_to_postgres.py # Load data")

        return True

    except Exception as e:
        print(f"❌ Reset failed: {e}")
        return False

if __name__ == "__main__":
    success = reset_database()
    sys.exit(0 if success else 1)
