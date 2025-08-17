#!/usr/bin/env python3
"""
PostgreSQL Data Loader - Load normalized PARQUET data into PostgreSQL

Pure parquet approach - no CSV, no truncation, full vector support.
"""

import os
import sys
import glob
import pandas as pd
import psycopg2
import json
import numpy as np
from datetime import datetime
from typing import Dict, List, Any
import time

class PostgreSQLDataLoader:
    """Load normalized data from PARQUET files into PostgreSQL database"""

    def __init__(self):
        """Initialize with database connection"""
        self.db_params = {
            'host': 'localhost',
            'port': 5432,
            'dbname': 'human_capital_dev',
            'user': 'hcd_user',
            'password': 'your_secure_password_here'
        }

        # Load order ensuring foreign key dependencies
        self.load_order = [
            'institutions', 'departments', 'academic_years', 'sections', 'subjects',
            'papers', 'students', 'student_paper_enrollments', 'questions',
            'student_question_history'
        ]

    def setup_database_schema(self):
        """Ensure database schema exists"""
        print("🔨 Ensuring database schema...")

        try:
            with psycopg2.connect(**self.db_params) as conn:
                cursor = conn.cursor()

                # Check if tables exist
                cursor.execute("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                """)

                existing_tables = [row[0] for row in cursor.fetchall()]
                print(f"✅ Database schema exists ({len(existing_tables)} tables found)")

        except Exception as e:
            print(f"❌ Schema check failed: {e}")
            raise

    def clear_existing_data(self):
        """Clear existing data in dependency order"""
        print("🧹 Clearing existing data...")

        try:
            with psycopg2.connect(**self.db_params) as conn:
                cursor = conn.cursor()

                # Clear in reverse dependency order
                clear_order = list(reversed(self.load_order))

                for table in clear_order:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    if count > 0:
                        cursor.execute(f"DELETE FROM {table}")
                        print(f"   🗑️  Cleared {count} rows from {table}")

                # Reset sequences
                cursor.execute("SELECT setval('student_question_history_history_id_seq', 1, false)")

                conn.commit()
                print("✅ Existing data cleared")

        except Exception as e:
            print(f"❌ Error clearing data: {e}")
            raise

    def load_table_from_parquet(self, table_name: str, parquet_file: str) -> int:
        """Load data from PARQUET file into PostgreSQL table"""
        print(f"📦 Loading {table_name}...")

        try:
            with psycopg2.connect(**self.db_params) as conn:
                cursor = conn.cursor()

                # Read parquet data (preserves all data types)
                df = pd.read_parquet(parquet_file)

                if len(df) == 0:
                    print(f"⚠️  {table_name}: No data to load")
                    return 0

                # Get table columns
                columns = list(df.columns)

                # Special handling for questions table with vectors
                if table_name == 'questions':
                    return self._load_questions_with_vectors(df, cursor)

                # For student_question_history, skip the history_id column (auto-generated)
                if table_name == 'student_question_history' and 'history_id' in columns:
                    columns = [col for col in columns if col != 'history_id']
                    df_insert = df.drop(columns=['history_id'])
                else:
                    df_insert = df

                # Prepare insert statement
                placeholders = ','.join(['%s'] * len(columns))
                column_names = ','.join(columns)
                insert_sql = f"INSERT INTO {table_name} ({column_names}) VALUES ({placeholders})"

                # Insert data row by row (handles all data types properly)
                inserted = 0
                for _, row in df_insert.iterrows():
                    values = []
                    for val in row:
                        if pd.isna(val) or str(val) == 'NaT':
                            values.append(None)
                        else:
                            values.append(val)

                    cursor.execute(insert_sql, tuple(values))
                    inserted += 1

                conn.commit()
                print(f"   ✅ Loaded {inserted} records into {table_name}")
                return inserted

        except Exception as e:
            print(f"❌ Error loading {table_name}: {e}")
            raise

    def _load_questions_with_vectors(self, df: pd.DataFrame, cursor) -> int:
        """Special loader for questions table with vector embeddings"""
        print("🧠 Loading questions with vector embeddings...")

        inserted = 0
        for _, row in df.iterrows():
            if inserted % 500 == 0:
                print(f"   Progress: {inserted}/{len(df)} questions")

            # Convert vectors to lists for PostgreSQL
            openai_embedding = None
            umap_embedding = None
            soft_cluster = None
            umap_2d_embedding = None

            # Handle OpenAI embedding
            openai_val = row.get('openai_embedding')
            if openai_val is not None and not (isinstance(openai_val, float) and np.isnan(openai_val)):
                if hasattr(openai_val, 'tolist'):
                    openai_embedding = self._clean_vector(openai_val.tolist())
                elif isinstance(openai_val, (list, tuple)):
                    openai_embedding = self._clean_vector(list(openai_val))

            # Handle UMAP embedding
            umap_val = row.get('umap_embedding')
            if umap_val is not None and not (isinstance(umap_val, float) and np.isnan(umap_val)):
                if hasattr(umap_val, 'tolist'):
                    umap_embedding = self._clean_vector(umap_val.tolist())
                elif isinstance(umap_val, (list, tuple)):
                    umap_embedding = self._clean_vector(list(umap_val))

            # Handle soft cluster
            cluster_val = row.get('soft_cluster')
            if cluster_val is not None and not (isinstance(cluster_val, float) and np.isnan(cluster_val)):
                if hasattr(cluster_val, 'tolist'):
                    soft_cluster = self._clean_vector(cluster_val.tolist())
                elif isinstance(cluster_val, (list, tuple)):
                    soft_cluster = self._clean_vector(list(cluster_val))

            # Handle 2D UMAP embedding
            umap_2d_val = row.get('umap_2d')
            if umap_2d_val is not None and not (isinstance(umap_2d_val, float) and np.isnan(umap_2d_val)):
                if hasattr(umap_2d_val, 'tolist'):
                    umap_2d_embedding = self._clean_vector(umap_2d_val.tolist())
                elif isinstance(umap_2d_val, (list, tuple)):
                    umap_2d_embedding = self._clean_vector(list(umap_2d_val))

            # Convert images array to JSONB
            images_json = None
            images_val = row.get('images')
            if images_val is not None and not (isinstance(images_val, float) and np.isnan(images_val)):
                if hasattr(images_val, 'tolist'):
                    images_json = json.dumps(images_val.tolist())
                elif isinstance(images_val, (list, tuple)):
                    images_json = json.dumps(list(images_val))
                else:
                    images_json = json.dumps([str(images_val)])

            # Insert question with all data
            cursor.execute("""
                INSERT INTO questions (
                    internal_question_id, question_id, paper_id, question_number, combined_text,
                    images, openai_embedding, umap_embedding, soft_cluster, umap_2d_embedding, embedding_model,
                    embedding_created_at, cluster_model_version, text_length, source_file,
                    ms, is_active, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                int(row['internal_question_id']),
                row['question_id'],
                int(row['paper_id']),
                int(row['question_number']),
                row.get('combined_text', ''),
                images_json,
                openai_embedding,
                umap_embedding,
                soft_cluster,
                umap_2d_embedding,
                row.get('embedding_model', 'text-embedding-3-large'),
                row.get('embedding_created_at'),
                row.get('cluster_model_version'),
                int(row.get('text_length', 0)) if pd.notna(row.get('text_length')) else None,
                row.get('source_file', ''),
                row.get('ms', ''),
                bool(row.get('is_active', True)),
                row.get('created_at', datetime.now()),
                row.get('updated_at', datetime.now())
            ))
            inserted += 1

        print(f"   ✅ Loaded {inserted} questions with full vector embeddings")
        return inserted

    def _clean_vector(self, vector_list):
        """Clean vector by handling extreme values that PostgreSQL can't handle"""
        if not vector_list:
            return vector_list

        cleaned = []
        for val in vector_list:
            if val is None or np.isnan(val) or np.isinf(val):
                cleaned.append(0.0)
            elif abs(val) < 1e-30:   # Extremely small values (more aggressive)
                cleaned.append(0.0)
            elif abs(val) > 1e20:    # Extremely large values
                cleaned.append(1e20 if val > 0 else -1e20)
            else:
                cleaned.append(float(val))

        return cleaned

    def load_questions_from_original_parquet(self, parquet_file: str = '../combined_questions_2d.parquet') -> int:
        """Load questions directly from original parquet file (bypasses normalization issues)"""
        try:
            with psycopg2.connect(**self.db_params) as conn:
                cursor = conn.cursor()

                # Load original parquet data
                df = pd.read_parquet(parquet_file)
                print(f"✅ Loaded {len(df)} questions from original parquet")

                # Create question_id and get paper mappings
                df['question_id'] = df['paper_number'].astype(str) + '_' + df['question_number'].astype(str)

                cursor.execute("SELECT paper_number, paper_id FROM papers")
                paper_mapping = {row[0]: row[1] for row in cursor.fetchall()}

                inserted = 0
                for _, row in df.iterrows():
                    if inserted % 500 == 0:
                        print(f"   Progress: {inserted}/{len(df)} questions")

                    # Get paper_id
                    paper_id = paper_mapping.get(row['paper_number'])
                    if not paper_id:
                        continue

                    # Clean and prepare vectors
                    openai_embedding = self._clean_vector(row['openai_embedding'].tolist()) if hasattr(row['openai_embedding'], 'tolist') else None
                    umap_embedding = self._clean_vector(row['umap_embedding'].tolist()) if hasattr(row['umap_embedding'], 'tolist') else None
                    soft_cluster = self._clean_vector(row['soft_cluster'].tolist()) if hasattr(row['soft_cluster'], 'tolist') else None
                    umap_2d_embedding = self._clean_vector(row['umap_2d'].tolist()) if hasattr(row.get('umap_2d'), 'tolist') else None

                    # Convert images (simple approach)
                    images_json = None
                    try:
                        images = row.get('images')
                        if images is not None:
                            if hasattr(images, 'tolist'):
                                images_json = json.dumps(images.tolist())
                            else:
                                images_json = json.dumps([str(images)])
                    except:
                        images_json = None

                    # Insert question
                    cursor.execute("""
                        INSERT INTO questions (
                            internal_question_id, question_id, paper_id, question_number, combined_text, images,
                            openai_embedding, umap_embedding, soft_cluster, umap_2d_embedding, embedding_model,
                            text_length, source_file, ms, is_active, created_at, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        inserted + 1,  # Use sequential ID
                        row['question_id'],
                        paper_id,
                        int(row['question_number']),
                        row.get('combined_text', ''),
                        images_json,
                        openai_embedding,
                        umap_embedding,
                        soft_cluster,
                        umap_2d_embedding,
                        'text-embedding-3-large',
                        int(row.get('text_length', 0)) if pd.notna(row.get('text_length')) else None,
                        row.get('source_file', ''),
                        row.get('ms', ''),
                        True,
                        datetime.now(),
                        datetime.now()
                    ))
                    inserted += 1

                conn.commit()
                return inserted

        except Exception as e:
            print(f"❌ Error loading from original parquet: {e}")
            return 0

    def verify_data_integrity(self) -> Dict[str, Any]:
        """Verify data was loaded correctly"""
        print("🔍 Verifying data integrity...")

        verification = {
            'total_records': 0,
            'table_counts': {},
            'vector_stats': {},
            'valid_relationships': 0
        }

        try:
            with psycopg2.connect(**self.db_params) as conn:
                cursor = conn.cursor()

                # Count records in each table
                for table in self.load_order:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    verification['table_counts'][table] = count
                    verification['total_records'] += count
                    print(f"   📊 {table}: {count:,} records")

                # Check vector embeddings
                cursor.execute("""
                    SELECT
                        COUNT(*) as total_questions,
                        COUNT(openai_embedding) as openai_count,
                        COUNT(umap_embedding) as umap_count,
                        COUNT(soft_cluster) as cluster_count,
                        COUNT(umap_2d_embedding) as umap_2d_count
                    FROM questions
                """)

                vector_stats = cursor.fetchone()
                verification['vector_stats'] = {
                    'total_questions': vector_stats[0],
                    'openai_embeddings': vector_stats[1],
                    'umap_embeddings': vector_stats[2],
                    'soft_clusters': vector_stats[3],
                    'umap_2d_embeddings': vector_stats[4]
                }
                print(f"   🧠 Vector embeddings: {vector_stats[1]}/{vector_stats[0]} complete")

                # Check relationships
                cursor.execute("""
                    SELECT COUNT(DISTINCT sqh.internal_question_id)
                    FROM student_question_history sqh
                    JOIN questions q ON sqh.internal_question_id = q.internal_question_id
                """)
                verification['valid_relationships'] = cursor.fetchone()[0]
                print(f"   🔗 Valid student-question relationships: {verification['valid_relationships']}")

        except Exception as e:
            print(f"❌ Error in verification: {e}")
            verification['error'] = str(e)

        return verification

    def run_full_load(self, clear_existing: bool = True) -> Dict[str, Any]:
        """Run complete data loading process using PARQUET files only"""
        start_time = time.time()

        print("🚀 STARTING POSTGRESQL DATA LOAD (PARQUET)")
        print("=" * 60)

        load_stats = {
            'status': 'success',
            'tables_loaded': 0,
            'total_records': 0,
            'duration': 0,
            'errors': []
        }

        try:
            # Find PARQUET files (fixed filenames)
            parquet_files = {}
            for table in self.load_order:
                parquet_file = f"normalized_{table}.parquet"
                if os.path.exists(parquet_file):
                    parquet_files[table] = parquet_file
                    print(f"📁 {table}: {parquet_file}")
                else:
                    print(f"⚠️  {table}: {parquet_file} not found")

            self.setup_database_schema()

            if clear_existing:
                self.clear_existing_data()

            # Load core tables first (except questions and student_question_history)
            for table in self.load_order:
                if table in ['questions', 'student_question_history']:
                    continue  # Handle these separately

                if table in parquet_files:
                    try:
                        records_loaded = self.load_table_from_parquet(table, parquet_files[table])
                        load_stats['tables_loaded'] += 1
                        load_stats['total_records'] += records_loaded
                    except Exception as e:
                        error_msg = f"Error loading {table}: {str(e)}"
                        print(f"❌ {error_msg}")
                        load_stats['errors'].append(error_msg)

            # Load questions directly from original parquet
            print("\n📦 Loading questions from original parquet file...")
            try:
                questions_loaded = self.load_questions_from_original_parquet()
                if questions_loaded > 0:
                    load_stats['tables_loaded'] += 1
                    load_stats['total_records'] += questions_loaded
                    print(f"✅ Successfully loaded {questions_loaded} questions with vectors")

                    # Now load student history (after questions exist)
                    if 'student_question_history' in parquet_files:
                        print("\n📦 Loading student question history...")
                        try:
                            history_loaded = self.load_table_from_parquet('student_question_history', parquet_files['student_question_history'])
                            load_stats['tables_loaded'] += 1
                            load_stats['total_records'] += history_loaded
                        except Exception as e:
                            error_msg = f"Error loading student_question_history: {str(e)}"
                            print(f"❌ {error_msg}")
                            load_stats['errors'].append(error_msg)
                else:
                    load_stats['errors'].append("Failed to load questions from original parquet")
            except Exception as e:
                error_msg = f"Error loading questions from original parquet: {str(e)}"
                print(f"❌ {error_msg}")
                load_stats['errors'].append(error_msg)

            # Verify data integrity
            verification = self.verify_data_integrity()
            load_stats.update(verification)

            load_stats['duration'] = time.time() - start_time
            rate = load_stats['total_records'] / load_stats['duration'] if load_stats['duration'] > 0 else 0

            print(f"\n🎉 PARQUET DATA LOAD COMPLETED!")
            print("=" * 60)
            print(f"📊 Statistics:")
            print(f"   • Tables loaded: {load_stats['tables_loaded']}")
            print(f"   • Total records: {load_stats['total_records']:,}")
            print(f"   • Duration: {load_stats['duration']:.2f} seconds")
            print(f"   • Rate: {rate:,.0f} records/second")

            if load_stats.get('vector_stats'):
                vs = load_stats['vector_stats']
                print(f"\n🧠 Vector Data:")
                print(f"   • Questions: {vs['total_questions']:,}")
                print(f"   • OpenAI embeddings: {vs['openai_embeddings']:,}")
                print(f"   • UMAP embeddings: {vs['umap_embeddings']:,}")
                print(f"   • Soft clusters: {vs['soft_clusters']:,}")
                print(f"   • 2D UMAP embeddings: {vs['umap_2d_embeddings']:,}")

            if load_stats['errors']:
                print(f"\n⚠️  Errors encountered:")
                for error in load_stats['errors']:
                    print(f"   • {error}")

            # Build transition matrix if questions were loaded successfully
            if load_stats.get('vector_stats', {}).get('total_questions', 0) > 0:
                print(f"\n🔄 Building transition matrix for ML recommendations...")
                try:
                    matrix_success = self._build_transition_matrix()
                    if matrix_success:
                        print(f"✅ Transition matrix ready for instant recommendations")
                    else:
                        print(f"⚠️  Transition matrix will build on first API request")
                except Exception as e:
                    print(f"⚠️  Transition matrix build failed: {e}")
                    print(f"💡 Will build on first API request instead")

            print(f"\n✅ Ready for ML pipeline and API server!")
            print("Next steps:")
            print("   • python ../main.py --mode api    # Start API server")
            print("   • python ../main.py --mode demo   # Run system demo")

        except Exception as e:
            load_stats['status'] = 'error'
            load_stats['error'] = str(e)
            load_stats['duration'] = time.time() - start_time
            print(f"❌ Load failed: {e}")

        return load_stats

    def _build_transition_matrix(self) -> bool:
        """Build and store transition matrix as part of data pipeline"""
        try:
            # Import and setup transition matrix manager
            from transition_matrix_storage import TransitionMatrixManager
            import redis

            # Setup Redis connection (use same as vector cache)
            try:
                redis_client = redis.Redis(host='localhost', port=6379, db=1)
                redis_client.ping()
            except:
                redis_client = None  # Redis optional for building

            # Initialize manager
            manager = TransitionMatrixManager(redis_client, self.db_params)

            # Build matrix (force rebuild to ensure fresh data)
            matrix = manager.get_or_compute_matrix(force_rebuild=True)

            if matrix is not None:
                print(f"   📊 Matrix built: {matrix.shape} ({(matrix == 0).sum() / matrix.size:.1%} sparse)")
                return True
            else:
                return False

        except Exception as e:
            print(f"   ❌ Matrix build error: {e}")
            return False


if __name__ == "__main__":
    loader = PostgreSQLDataLoader()
    success = loader.run_full_load(clear_existing=True)

    if success.get('status') == 'success':
        print("\n🎯 SUCCESS: Parquet data loaded with full vector embeddings!")
    else:
        print(f"\n❌ FAILED: {success.get('error', 'Unknown error')}")
        sys.exit(1)