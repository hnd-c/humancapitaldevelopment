# Database Schema and SQL Files

This directory contains all database-related SQL files for the Human Capital Development System.

## 📁 Directory Structure

```
database/
├── migrations/           # Database schema migrations (run in order)
│   ├── 01_initial_schema.sql         # Main PostgreSQL schema with vector support
│   └── 02_halfprecision_indexes.sql  # Performance indexes for 3072D embeddings
│
├── examples/            # SQL query examples and documentation
│   └── vector_queries.sql            # Vector similarity query examples
│
└── README.md           # This file
```

## 🚀 Quick Start

### 1. Create Database and Extensions

```sql
-- Create database
CREATE DATABASE human_capital_dev;

-- Connect to the database and enable extensions
\c human_capital_dev
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

### 2. Run Migrations in Order

```bash
# Run the main schema
psql -d human_capital_dev -f database/migrations/01_initial_schema.sql

# After loading your data, create performance indexes
psql -d human_capital_dev -f database/migrations/02_halfprecision_indexes.sql
```

### 3. Load Your Data

Use the data import scripts in the `scripts/` directory to populate the database with your question data and embeddings.

## 📊 Database Schema Overview

### Core Tables

- **institutions, departments, academic_years, sections, subjects** - Organizational structure
- **papers** - Exam papers/assessments
- **students** - Student information
- **student_paper_enrollments** - Student-paper relationships
- **questions** - Questions with vector embeddings (OpenAI 3072D, UMAP 50D, clusters 20D)
- **student_question_history** - Student attempt history
- **question_similarities** - Precomputed similarity scores
- **cluster_analysis** - ML cluster characteristics
- **transition_matrices** - ML learning pathway data

### Vector Embeddings

The system supports three types of vector embeddings:

1. **OpenAI Embeddings** (`vector(3072)`) - text-embedding-3-large
2. **UMAP Embeddings** (`vector(50)`) - Dimensionality-reduced embeddings
3. **Soft Clusters** (`vector(20)`) - Cluster probability distributions

### Key Features

- **pgvector Extension** - Native PostgreSQL vector similarity search
- **Half-Precision Indexes** - Optimized indexes for 3072-dimension OpenAI embeddings
- **Multi-modal Similarity** - Combine different embedding types for recommendations
- **Performance Views** - Pre-built analytics views for student and question performance
- **Stored Functions** - Ready-to-use similarity search functions

## 🔍 Vector Similarity Search

### Available Functions

```sql
-- OpenAI embedding similarity (3072D)
SELECT * FROM find_similar_questions_openai(query_vector, threshold, limit);

-- UMAP embedding similarity (50D)
SELECT * FROM find_similar_questions_umap(query_vector, threshold, limit);

-- Cluster similarity (20D)
SELECT * FROM find_similar_questions_cluster(query_vector, threshold, limit);

-- Multi-modal similarity (combines all types)
SELECT * FROM find_similar_questions_multimodal(
    openai_vector, umap_vector, cluster_vector,
    openai_weight, umap_weight, cluster_weight,
    threshold, limit
);

-- Hybrid recommendations (similarity + performance)
SELECT * FROM recommend_questions_hybrid(
    student_enrollment_id, query_vector,
    similarity_threshold, min_success_rate, max_success_rate, limit
);
```

### Performance Optimization

1. **Standard Indexes** - For UMAP (50D) and cluster (20D) embeddings
2. **Half-Precision Indexes** - For OpenAI (3072D) embeddings to exceed the 2000D limit
3. **Composite Indexes** - For common query patterns
4. **Materialized Views** - For frequently accessed analytics

## 📈 Analytics Views

### Pre-built Views

- `student_performance_summary` - Student success rates and metrics
- `question_difficulty_analysis` - Question difficulty and embedding metadata
- `cluster_performance_analysis` - Performance by ML clusters

### Example Queries

```sql
-- Student performance analysis
SELECT * FROM student_performance_summary
WHERE student_id = 123;

-- Question difficulty by cluster
SELECT cluster_id, avg_success_rate, question_count
FROM cluster_performance_analysis
ORDER BY avg_success_rate;

-- Find hardest questions
SELECT * FROM question_difficulty_analysis
WHERE success_rate < 30
ORDER BY success_rate ASC;
```

## 🛠️ Maintenance

### Regular Tasks

```sql
-- Update cluster statistics
SELECT analyze_clusters();

-- Cleanup old transition matrices
SELECT cleanup_old_transition_matrices(5);

-- Refresh materialized views (if any)
-- REFRESH MATERIALIZED VIEW view_name;
```

### Performance Monitoring

```sql
-- Check vector index usage
SELECT schemaname, tablename, indexname, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes
WHERE indexname LIKE '%vector%' OR indexname LIKE '%halfvec%'
ORDER BY idx_tup_read DESC;

-- Monitor table sizes
SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

## 🚨 Important Notes

1. **Load Data First** - Run `02_halfprecision_indexes.sql` AFTER loading your vector data
2. **Vector Dimensions** - Ensure your data matches the expected dimensions (3072, 50, 20)
3. **Memory Requirements** - Vector operations require sufficient RAM, especially for large datasets
4. **Backup Strategy** - Include vector data in your backup procedures

## 🔗 Related Files

- `scripts/migrate_data.py` - Data migration script
- `scripts/vector_data_import.py` - Vector data import utilities
- `data/database_manager.py` - Python database interface
- `ml/embeddings.py` - Vector embedding operations
