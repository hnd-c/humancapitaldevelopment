#!/usr/bin/env python3
"""
Vector Data Import Script
Imports embeddings from combined_questions.parquet into PostgreSQL
This is the critical bridge between your ML pipeline and the database system
"""

import pandas as pd
import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import sys
import json
from typing import List, Dict, Any
import time

class VectorDataImporter:
    def __init__(self, db_config: Dict[str, Any]):
        self.db_config = db_config
        self.connection = None

    def connect(self):
        """Connect to PostgreSQL database"""
        try:
            self.connection = psycopg2.connect(**self.db_config)
            print("✅ Connected to PostgreSQL database")
            return True
        except Exception as e:
            print(f"❌ Failed to connect to database: {e}")
            return False

    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()

    def verify_questions_table(self):
        """Verify questions table exists and has proper vector columns"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)

            # Check if questions table exists with vector columns
            cursor.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'questions'
                AND column_name IN ('openai_embedding', 'umap_embedding', 'soft_cluster')
            """)

            vector_columns = cursor.fetchall()
            cursor.close()

            if len(vector_columns) == 3:
                print("✅ Questions table has all required vector columns")
                return True
            else:
                print(f"❌ Questions table missing vector columns. Found: {[col['column_name'] for col in vector_columns]}")
                return False

        except Exception as e:
            print(f"❌ Error verifying questions table: {e}")
            return False

    def load_parquet_data(self, parquet_file: str = "combined_questions.parquet"):
        """Load data from combined_questions.parquet"""
        try:
            print(f"📊 Loading data from {parquet_file}...")
            df = pd.read_parquet(parquet_file)

            print(f"✅ Loaded {len(df)} questions with columns: {list(df.columns)}")
            print(f"📊 Data overview:")
            print(f"   • OpenAI embeddings: {df['openai_embedding'].notna().sum()}/{len(df)}")
            print(f"   • UMAP embeddings: {df['umap_embedding'].notna().sum()}/{len(df)}")
            print(f"   • Soft clusters: {df['soft_cluster'].notna().sum()}/{len(df)}")

            # Verify embedding dimensions
            if len(df) > 0:
                sample_openai = df['openai_embedding'].dropna().iloc[0]
                sample_umap = df['umap_embedding'].dropna().iloc[0]
                sample_cluster = df['soft_cluster'].dropna().iloc[0]

                print(f"📏 Embedding dimensions:")
                print(f"   • OpenAI: {len(sample_openai)}D")
                print(f"   • UMAP: {len(sample_umap)}D")
                print(f"   • Clusters: {len(sample_cluster)}D")

            return df

        except FileNotFoundError:
            print(f"❌ File {parquet_file} not found!")
            print("💡 Make sure combined_questions.parquet is in the current directory")
            return None
        except Exception as e:
            print(f"❌ Error loading parquet file: {e}")
            return None

    def create_question_records(self, df: pd.DataFrame):
        """Create or update question records with basic info"""
        cursor = self.connection.cursor()

        try:
            print("📝 Creating/updating question records...")

            # First, ensure we have a paper mapping
            cursor.execute("SELECT paper_id, paper_key FROM papers")
            paper_mapping = {row[1]: row[0] for row in cursor.fetchall()}

            if not paper_mapping:
                print("⚠️  No papers found in database. Creating default paper entries...")
                self._create_default_papers(df, cursor)
                cursor.execute("SELECT paper_id, paper_key FROM papers")
                paper_mapping = {row[1]: row[0] for row in cursor.fetchall()}

            created_count = 0
            updated_count = 0

            for idx, row in df.iterrows():
                if idx % 500 == 0:
                    print(f"   Progress: {idx}/{len(df)} questions processed")

                question_id = f"{row['paper_number']}_{row['question_number']}"
                paper_key = str(row['paper_number'])

                # Get paper_id
                paper_id = paper_mapping.get(paper_key)
                if not paper_id:
                    print(f"⚠️  No paper found for {paper_key}, skipping question {question_id}")
                    continue

                # Check if question exists
                cursor.execute("SELECT internal_question_id FROM questions WHERE question_id = %s", (question_id,))
                existing = cursor.fetchone()

                if existing:
                    # Update existing question
                    cursor.execute("""
                        UPDATE questions
                        SET combined_text = %s,
                            images = %s,
                            text_length = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE question_id = %s
                    """, (
                        row.get('combined_text', ''),
                        json.dumps(row.get('images', [])) if pd.notna(row.get('images')) else None,
                        int(row.get('text_length', 0)) if pd.notna(row.get('text_length')) else None,
                        question_id
                    ))
                    updated_count += 1
                else:
                    # Insert new question
                    cursor.execute("""
                        INSERT INTO questions (
                            question_id, paper_id, question_number, combined_text,
                            images, text_length, embedding_model, is_active
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        question_id,
                        paper_id,
                        int(row['question_number']),
                        row.get('combined_text', ''),
                        json.dumps(row.get('images', [])) if pd.notna(row.get('images')) else None,
                        int(row.get('text_length', 0)) if pd.notna(row.get('text_length')) else None,
                        'text-embedding-3-large',
                        True
                    ))
                    created_count += 1

            self.connection.commit()
            print(f"✅ Question records: {created_count} created, {updated_count} updated")

        except Exception as e:
            print(f"❌ Error creating question records: {e}")
            self.connection.rollback()
            raise
        finally:
            cursor.close()

    def _create_default_papers(self, df: pd.DataFrame, cursor):
        """Create default paper entries if none exist"""
        print("📄 Creating default paper entries...")

        # Get unique paper numbers
        unique_papers = df['paper_number'].unique()

        # First ensure we have a default subject
        cursor.execute("SELECT subject_id FROM subjects LIMIT 1")
        subject_row = cursor.fetchone()

        if not subject_row:
            # Create default subject
            cursor.execute("""
                INSERT INTO subjects (subject_key, subject_name, subject_code, cambridge_subject_code)
                VALUES ('physics', 'Physics', 'PHY', 9702)
                RETURNING subject_id
            """)
            subject_id = cursor.fetchone()[0]
        else:
            subject_id = subject_row[0]

        # Create papers
        for paper_number in unique_papers:
            paper_key = str(paper_number)
            cursor.execute("""
                INSERT INTO papers (
                    subject_id, paper_key, paper_name, paper_code,
                    paper_description, paper_duration_minutes, paper_max_marks
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                subject_id,
                paper_key,
                f"Paper {paper_number}",
                paper_key.split('_')[-1] if '_' in paper_key else 'P1',
                f"Questions for paper {paper_number}",
                75,  # Default duration
                40   # Default max marks
            ))

        self.connection.commit()
        print(f"✅ Created default entries for {len(unique_papers)} papers")

    def import_vector_embeddings(self, df: pd.DataFrame):
        """Import vector embeddings into PostgreSQL"""
        cursor = self.connection.cursor()

        try:
            print("🧮 Importing vector embeddings...")

            success_count = 0
            error_count = 0

            for idx, row in df.iterrows():
                if idx % 100 == 0:
                    print(f"   Progress: {idx}/{len(df)} embeddings processed")

                question_id = f"{row['paper_number']}_{row['question_number']}"

                try:
                    # Prepare embeddings
                    openai_embedding = row['openai_embedding'] if pd.notna(row['openai_embedding']) else None
                    umap_embedding = row['umap_embedding'] if pd.notna(row['umap_embedding']) else None
                    soft_cluster = row['soft_cluster'] if pd.notna(row['soft_cluster']) else None

                    # Convert numpy arrays to lists for PostgreSQL
                    if openai_embedding is not None:
                        openai_embedding = openai_embedding.tolist() if isinstance(openai_embedding, np.ndarray) else openai_embedding

                    if umap_embedding is not None:
                        umap_embedding = umap_embedding.tolist() if isinstance(umap_embedding, np.ndarray) else umap_embedding

                    if soft_cluster is not None:
                        soft_cluster = soft_cluster.tolist() if isinstance(soft_cluster, np.ndarray) else soft_cluster

                    # Update question with embeddings
                    cursor.execute("""
                        UPDATE questions
                        SET openai_embedding = %s,
                            umap_embedding = %s,
                            soft_cluster = %s,
                            embedding_created_at = CURRENT_TIMESTAMP,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE question_id = %s
                    """, (
                        openai_embedding,
                        umap_embedding,
                        soft_cluster,
                        question_id
                    ))

                    if cursor.rowcount > 0:
                        success_count += 1
                    else:
                        error_count += 1
                        if error_count < 10:  # Only show first 10 errors
                            print(f"⚠️  Question {question_id} not found in database")

                except Exception as e:
                    error_count += 1
                    if error_count < 10:
                        print(f"❌ Error importing embeddings for {question_id}: {e}")

            self.connection.commit()
            print(f"✅ Vector embeddings imported: {success_count} successful, {error_count} errors")

            if error_count > 0:
                print(f"⚠️  {error_count} embeddings failed to import")
                print("💡 Make sure all questions exist in the database before importing embeddings")

        except Exception as e:
            print(f"❌ Critical error importing embeddings: {e}")
            self.connection.rollback()
            raise
        finally:
            cursor.close()

    def verify_import(self):
        """Verify that the import was successful"""
        cursor = self.connection.cursor(cursor_factory=RealDictCursor)

        try:
            print("🔍 Verifying import results...")

            # Count questions with embeddings
            cursor.execute("""
                SELECT
                    COUNT(*) as total_questions,
                    COUNT(openai_embedding) as openai_count,
                    COUNT(umap_embedding) as umap_count,
                    COUNT(soft_cluster) as cluster_count
                FROM questions
            """)

            stats = cursor.fetchone()

            print(f"📊 Import verification:")
            print(f"   • Total questions: {stats['total_questions']}")
            print(f"   • OpenAI embeddings: {stats['openai_count']}")
            print(f"   • UMAP embeddings: {stats['umap_count']}")
            print(f"   • Soft clusters: {stats['cluster_count']}")

            # Test vector operations
            cursor.execute("""
                SELECT question_id,
                       array_length(openai_embedding, 1) as openai_dim,
                       array_length(umap_embedding, 1) as umap_dim,
                       array_length(soft_cluster, 1) as cluster_dim
                FROM questions
                WHERE openai_embedding IS NOT NULL
                LIMIT 3
            """)

            samples = cursor.fetchall()
            print(f"📏 Sample embedding dimensions:")
            for sample in samples:
                print(f"   • {sample['question_id']}: OpenAI={sample['openai_dim']}D, UMAP={sample['umap_dim']}D, Clusters={sample['cluster_dim']}D")

            return stats['openai_count'] > 0

        except Exception as e:
            print(f"❌ Error verifying import: {e}")
            return False
        finally:
            cursor.close()

    def run_full_import(self, parquet_file: str = "combined_questions.parquet"):
        """Run the complete import process"""
        print("🚀 Starting vector data import process...")
        print("=" * 60)

        start_time = time.time()

        try:
            # 1. Connect to database
            if not self.connect():
                return False

            # 2. Verify database schema
            if not self.verify_questions_table():
                print("💡 Make sure the PostgreSQL migration has been run first")
                return False

            # 3. Load parquet data
            df = self.load_parquet_data(parquet_file)
            if df is None:
                return False

            # 4. Create/update question records
            self.create_question_records(df)

            # 5. Import vector embeddings
            self.import_vector_embeddings(df)

            # 6. Verify import
            success = self.verify_import()

            duration = time.time() - start_time

            if success:
                print(f"\n🎉 Vector data import completed successfully in {duration:.2f}s!")
                print("💡 Your ML pipeline is now fully integrated with the database")
                return True
            else:
                print(f"\n❌ Import completed with errors in {duration:.2f}s")
                return False

        except Exception as e:
            print(f"❌ Import failed: {e}")
            return False
        finally:
            self.close()


def main():
    """Main function"""
    print("🚀 Vector Data Import Tool")
    print("Bridges ML pipeline (parquet) with PostgreSQL database")
    print("=" * 60)

    # Database configuration
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', 5432)),
        'database': os.getenv('DB_NAME', 'human_capital_dev'),
        'user': os.getenv('DB_USER', 'hcd_user'),
        'password': os.getenv('DB_PASSWORD', 'your_secure_password_here')
    }

    print(f"📊 Database: {db_config['host']}:{db_config['port']}/{db_config['database']}")

    # Run import
    importer = VectorDataImporter(db_config)
    success = importer.run_full_import()

    if success:
        print("\n🎯 Next steps:")
        print("   1. Test the API: python api_server.py")
        print("   2. Get recommendations: curl -X POST http://localhost:8000/recommendations -H 'Content-Type: application/json' -d '{\"student_id\": \"1\"}'")
        print("   3. Monitor performance: docker-compose --profile monitoring up -d")
    else:
        print("\n💡 Troubleshooting:")
        print("   1. Ensure PostgreSQL is running: docker-compose up -d postgres")
        print("   2. Check migration was run: docker-compose logs postgres")
        print("   3. Verify parquet file exists: ls -la combined_questions.parquet")
        print("   4. Check database credentials in environment variables")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
