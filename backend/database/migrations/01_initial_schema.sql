-- =====================================================
-- POSTGRESQL MIGRATION SCRIPT WITH VECTOR DATABASE SUPPORT
-- Generated from normalized student learning data
-- Includes pgvector extension for embedding storage and similarity search
-- Updated for OpenAI text-embedding-3-large (3072D) and actual data dimensions
-- =====================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- =====================================================
-- 1. INSTITUTIONS TABLE
-- =====================================================
CREATE TABLE institutions (
    institution_id SERIAL PRIMARY KEY,
    institution_key VARCHAR(50) UNIQUE NOT NULL,
    institution_name VARCHAR(255) NOT NULL,
    institution_code VARCHAR(10) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- 2. DEPARTMENTS TABLE
-- =====================================================
CREATE TABLE departments (
    department_id SERIAL PRIMARY KEY,
    institution_id INTEGER NOT NULL REFERENCES institutions(institution_id),
    department_key VARCHAR(50) NOT NULL,
    department_name VARCHAR(255) NOT NULL,
    department_code VARCHAR(10) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(institution_id, department_key)
);

-- =====================================================
-- 3. ACADEMIC_YEARS TABLE
-- =====================================================
CREATE TABLE academic_years (
    year_id SERIAL PRIMARY KEY,
    year_key VARCHAR(50) UNIQUE NOT NULL,
    year_name VARCHAR(100) NOT NULL,
    year_code VARCHAR(10) NOT NULL,
    academic_year VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- 4. SECTIONS TABLE
-- =====================================================
CREATE TABLE sections (
    section_id SERIAL PRIMARY KEY,
    section_key VARCHAR(50) UNIQUE NOT NULL,
    section_name VARCHAR(100) NOT NULL,
    section_code VARCHAR(10) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- 5. SUBJECTS TABLE
-- =====================================================
CREATE TABLE subjects (
    subject_id SERIAL PRIMARY KEY,
    subject_key VARCHAR(50) UNIQUE NOT NULL,
    subject_name VARCHAR(255) NOT NULL,
    subject_code VARCHAR(10) NOT NULL,
    cambridge_subject_code INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- 6. PAPERS TABLE
-- =====================================================
CREATE TABLE papers (
    paper_id SERIAL PRIMARY KEY,
    subject_id INTEGER NOT NULL REFERENCES subjects(subject_id),
    paper_key VARCHAR(50) NOT NULL,
    paper_name VARCHAR(255) NOT NULL,
    paper_code VARCHAR(10) NOT NULL,
    paper_description TEXT,
    paper_duration_minutes INTEGER NOT NULL,
    paper_max_marks INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(subject_id, paper_key)
);

-- =====================================================
-- 7. STUDENTS TABLE
-- =====================================================
CREATE TABLE students (
    student_id SERIAL PRIMARY KEY,
    base_student_number INTEGER NOT NULL,
    institution_id INTEGER NOT NULL REFERENCES institutions(institution_id),
    department_id INTEGER NOT NULL REFERENCES departments(department_id),
    year_id INTEGER NOT NULL REFERENCES academic_years(year_id),
    section_id INTEGER NOT NULL REFERENCES sections(section_id),
    student_ability_level VARCHAR(20) CHECK (student_ability_level IN ('low', 'medium_low', 'medium', 'medium_high', 'high')),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(institution_id, department_id, year_id, section_id, base_student_number)
);

-- =====================================================
-- 8. STUDENT_PAPER_ENROLLMENTS TABLE
-- =====================================================
CREATE TABLE student_paper_enrollments (
    enrollment_id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(student_id),
    paper_id INTEGER NOT NULL REFERENCES papers(paper_id),
    paper_student_id VARCHAR(100) UNIQUE NOT NULL, -- Legacy ID for backward compatibility
    is_active BOOLEAN DEFAULT TRUE,
    enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, paper_id)
);

-- =====================================================
-- 9. QUESTIONS TABLE (ENHANCED WITH VECTOR EMBEDDINGS)
-- =====================================================
CREATE TABLE questions (
    internal_question_id SERIAL PRIMARY KEY,
    question_id VARCHAR(100) UNIQUE NOT NULL, -- External question identifier
    paper_id INTEGER NOT NULL REFERENCES papers(paper_id),
    question_number INTEGER NOT NULL,
    combined_text TEXT,
    images JSONB, -- Store image paths as JSON array

    -- VECTOR EMBEDDINGS (Updated with correct dimensions)
    openai_embedding vector(3072), -- OpenAI text-embedding-3-large (3072 dimensions)
    umap_embedding vector(50), -- UMAP 50D embeddings from your data
    soft_cluster vector(20), -- 20 cluster probabilities (fixed dimension)

    -- EMBEDDING METADATA
    embedding_model VARCHAR(100) DEFAULT 'text-embedding-3-large',
    embedding_created_at TIMESTAMP,
    cluster_model_version VARCHAR(50),
    text_length INTEGER,

    -- ADDITIONAL FIELDS FROM YOUR DATA
    source_file VARCHAR(255), -- Track which source file the question came from
    ms NUMERIC(8,2), -- Milliseconds field from your data

    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(paper_id, question_number)
);

-- =====================================================
-- 10. STUDENT_QUESTION_HISTORY TABLE (Main transaction table)
-- =====================================================
CREATE TABLE student_question_history (
    history_id SERIAL PRIMARY KEY,
    enrollment_id INTEGER NOT NULL REFERENCES student_paper_enrollments(enrollment_id),
    internal_question_id INTEGER NOT NULL REFERENCES questions(internal_question_id),
    attempt_number INTEGER NOT NULL CHECK (attempt_number > 0),
    status VARCHAR(20) NOT NULL CHECK (status IN ('correct', 'wrong', 'skipped')),
    is_correct BOOLEAN NOT NULL,
    is_skipped BOOLEAN NOT NULL,
    time_spent_sec NUMERIC(8,2) NOT NULL CHECK (time_spent_sec >= 0),
    timestamp TIMESTAMPTZ NOT NULL,
    confidence_level INTEGER CHECK (confidence_level BETWEEN 1 AND 5),
    device_type VARCHAR(20) CHECK (device_type IN ('desktop', 'mobile', 'tablet')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(enrollment_id, internal_question_id, attempt_number)
);

-- =====================================================
-- 11. QUESTION_SIMILARITIES TABLE (Precomputed similarities)
-- =====================================================
CREATE TABLE question_similarities (
    similarity_id SERIAL PRIMARY KEY,
    question_a_id INTEGER NOT NULL REFERENCES questions(internal_question_id),
    question_b_id INTEGER NOT NULL REFERENCES questions(internal_question_id),
    similarity_type VARCHAR(20) NOT NULL CHECK (similarity_type IN ('openai', 'umap', 'cluster')),
    similarity_score NUMERIC(5,4) NOT NULL CHECK (similarity_score BETWEEN 0 AND 1),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(question_a_id, question_b_id, similarity_type),
    CHECK (question_a_id != question_b_id)
);

-- =====================================================
-- 12. CLUSTER_ANALYSIS TABLE (Store cluster characteristics)
-- =====================================================
CREATE TABLE cluster_analysis (
    cluster_id INTEGER PRIMARY KEY CHECK (cluster_id BETWEEN 0 AND 19),
    cluster_name VARCHAR(100),
    cluster_description TEXT,
    question_count INTEGER DEFAULT 0,
    avg_difficulty NUMERIC(5,4), -- Based on success rates
    avg_time_spent NUMERIC(8,2),
    dominant_topics JSONB, -- Store topic keywords as JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- INDEXES FOR PERFORMANCE
-- =====================================================

-- Traditional indexes
CREATE INDEX idx_students_base_number ON students(base_student_number);
CREATE INDEX idx_students_institution ON students(institution_id);
CREATE INDEX idx_students_ability ON students(student_ability_level);

CREATE INDEX idx_enrollments_student ON student_paper_enrollments(student_id);
CREATE INDEX idx_enrollments_paper ON student_paper_enrollments(paper_id);
CREATE INDEX idx_enrollments_legacy_id ON student_paper_enrollments(paper_student_id);

CREATE INDEX idx_questions_paper ON questions(paper_id);
CREATE INDEX idx_questions_number ON questions(question_number);
CREATE INDEX idx_questions_external_id ON questions(question_id);
CREATE INDEX idx_questions_text_length ON questions(text_length);
CREATE INDEX idx_questions_source_file ON questions(source_file);

-- VECTOR SIMILARITY INDEXES (Updated for 3072 dimensions)
-- Note: Half-precision indexes for OpenAI embeddings will be created after data loading
-- Run create_halfprecision_indexes.sql after loading your vector data
CREATE INDEX idx_questions_umap_cosine ON questions USING ivfflat (umap_embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_questions_umap_l2 ON questions USING ivfflat (umap_embedding vector_l2_ops) WITH (lists = 100);
CREATE INDEX idx_questions_cluster_cosine ON questions USING ivfflat (soft_cluster vector_cosine_ops) WITH (lists = 50);

-- History queries
CREATE INDEX idx_history_enrollment ON student_question_history(enrollment_id);
CREATE INDEX idx_history_question ON student_question_history(internal_question_id);
CREATE INDEX idx_history_timestamp ON student_question_history(timestamp);
CREATE INDEX idx_history_status ON student_question_history(status);

-- Composite indexes for common query patterns
CREATE INDEX idx_history_student_date ON student_question_history(enrollment_id, timestamp);
CREATE INDEX idx_history_question_attempts ON student_question_history(internal_question_id, attempt_number);
CREATE INDEX idx_history_performance ON student_question_history(enrollment_id, is_correct, timestamp);

-- Similarity table indexes
CREATE INDEX idx_similarities_question_a ON question_similarities(question_a_id, similarity_type);
CREATE INDEX idx_similarities_question_b ON question_similarities(question_b_id, similarity_type);
CREATE INDEX idx_similarities_score ON question_similarities(similarity_score DESC);

-- =====================================================
-- VECTOR SIMILARITY FUNCTIONS (Updated for 3072D embeddings)
-- =====================================================

-- Find similar questions using OpenAI text-embedding-3-large
CREATE OR REPLACE FUNCTION find_similar_questions_openai(
    query_embedding vector(3072),
    similarity_threshold float DEFAULT 0.7,
    limit_count int DEFAULT 10
)
RETURNS TABLE(
    internal_question_id integer,
    question_id varchar(100),
    similarity_score float
) AS $$
BEGIN
    RETURN QUERY
    SELECT q.internal_question_id,
           q.question_id,
           1 - (q.openai_embedding <=> query_embedding) as similarity_score
    FROM questions q
    WHERE q.openai_embedding IS NOT NULL
      AND 1 - (q.openai_embedding <=> query_embedding) >= similarity_threshold
    ORDER BY q.openai_embedding <=> query_embedding
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- Find similar questions using 50D UMAP embeddings
CREATE OR REPLACE FUNCTION find_similar_questions_umap(
    query_umap vector(50),
    similarity_threshold float DEFAULT 0.5,
    limit_count int DEFAULT 10
)
RETURNS TABLE(
    internal_question_id integer,
    question_id varchar(100),
    similarity_score float
) AS $$
BEGIN
    RETURN QUERY
    SELECT q.internal_question_id,
           q.question_id,
           1 - (q.umap_embedding <=> query_umap) as similarity_score
    FROM questions q
    WHERE q.umap_embedding IS NOT NULL
      AND 1 - (q.umap_embedding <=> query_umap) >= similarity_threshold
    ORDER BY q.umap_embedding <=> query_umap
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- Find similar questions using 20-cluster soft clustering
CREATE OR REPLACE FUNCTION find_similar_questions_cluster(
    query_cluster vector(20),
    similarity_threshold float DEFAULT 0.5,
    limit_count int DEFAULT 10
)
RETURNS TABLE(
    internal_question_id integer,
    question_id varchar(100),
    similarity_score float,
    dominant_cluster integer
) AS $$
BEGIN
    RETURN QUERY
    SELECT q.internal_question_id,
           q.question_id,
           1 - (q.soft_cluster <=> query_cluster) as similarity_score,
           -- Get the dominant cluster (index of max probability)
           (SELECT i-1 FROM unnest(q.soft_cluster) WITH ORDINALITY arr(val,i) ORDER BY val DESC LIMIT 1) as dominant_cluster
    FROM questions q
    WHERE q.soft_cluster IS NOT NULL
      AND 1 - (q.soft_cluster <=> query_cluster) >= similarity_threshold
    ORDER BY q.soft_cluster <=> query_cluster
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- Multi-modal similarity search (combines all embedding types)
CREATE OR REPLACE FUNCTION find_similar_questions_multimodal(
    query_openai vector(3072) DEFAULT NULL,
    query_umap vector(50) DEFAULT NULL,
    query_cluster vector(20) DEFAULT NULL,
    openai_weight float DEFAULT 0.5,
    umap_weight float DEFAULT 0.2,
    cluster_weight float DEFAULT 0.3,
    similarity_threshold float DEFAULT 0.6,
    limit_count int DEFAULT 10
)
RETURNS TABLE(
    internal_question_id integer,
    question_id varchar(100),
    combined_similarity_score float,
    openai_score float,
    umap_score float,
    cluster_score float
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        q.internal_question_id,
        q.question_id,
        (
            COALESCE(openai_weight * (1 - (q.openai_embedding <=> query_openai)), 0) +
            COALESCE(umap_weight * (1 - (q.umap_embedding <=> query_umap)), 0) +
            COALESCE(cluster_weight * (1 - (q.soft_cluster <=> query_cluster)), 0)
        ) / (
            CASE WHEN query_openai IS NOT NULL THEN openai_weight ELSE 0 END +
            CASE WHEN query_umap IS NOT NULL THEN umap_weight ELSE 0 END +
            CASE WHEN query_cluster IS NOT NULL THEN cluster_weight ELSE 0 END
        ) as combined_similarity_score,
        CASE WHEN query_openai IS NOT NULL THEN 1 - (q.openai_embedding <=> query_openai) ELSE NULL END as openai_score,
        CASE WHEN query_umap IS NOT NULL THEN 1 - (q.umap_embedding <=> query_umap) ELSE NULL END as umap_score,
        CASE WHEN query_cluster IS NOT NULL THEN 1 - (q.soft_cluster <=> query_cluster) ELSE NULL END as cluster_score
    FROM questions q
    WHERE (query_openai IS NULL OR q.openai_embedding IS NOT NULL)
      AND (query_umap IS NULL OR q.umap_embedding IS NOT NULL)
      AND (query_cluster IS NULL OR q.soft_cluster IS NOT NULL)
    HAVING (
        COALESCE(openai_weight * (1 - (q.openai_embedding <=> query_openai)), 0) +
        COALESCE(umap_weight * (1 - (q.umap_embedding <=> query_umap)), 0) +
        COALESCE(cluster_weight * (1 - (q.soft_cluster <=> query_cluster)), 0)
    ) / (
        CASE WHEN query_openai IS NOT NULL THEN openai_weight ELSE 0 END +
        CASE WHEN query_umap IS NOT NULL THEN umap_weight ELSE 0 END +
        CASE WHEN query_cluster IS NOT NULL THEN cluster_weight ELSE 0 END
    ) >= similarity_threshold
    ORDER BY combined_similarity_score DESC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- Hybrid search combining similarity + student performance (Updated for 3072D)
CREATE OR REPLACE FUNCTION recommend_questions_hybrid(
    student_enrollment_id integer,
    query_embedding vector(3072),
    similarity_threshold float DEFAULT 0.6,
    min_success_rate float DEFAULT 0.3,
    max_success_rate float DEFAULT 0.8,
    limit_count int DEFAULT 5
)
RETURNS TABLE(
    internal_question_id integer,
    question_id varchar(100),
    similarity_score float,
    avg_success_rate float,
    recommendation_score float,
    dominant_cluster integer
) AS $$
BEGIN
    RETURN QUERY
    WITH question_performance AS (
        SELECT
            q.internal_question_id,
            AVG(CASE WHEN sqh.is_correct THEN 1.0 ELSE 0.0 END) as avg_success_rate,
            COUNT(sqh.history_id) as attempt_count
        FROM questions q
        LEFT JOIN student_question_history sqh ON q.internal_question_id = sqh.internal_question_id
        GROUP BY q.internal_question_id
    ),
    similar_questions AS (
        SELECT * FROM find_similar_questions_openai(query_embedding, similarity_threshold, limit_count * 3)
    )
    SELECT
        sq.internal_question_id,
        sq.question_id,
        sq.similarity_score,
        COALESCE(qp.avg_success_rate, 0.5) as avg_success_rate,
        (sq.similarity_score * 0.7 +
         (1 - ABS(COALESCE(qp.avg_success_rate, 0.5) - 0.6)) * 0.3) as recommendation_score,
        -- Get dominant cluster
        (SELECT i-1 FROM unnest(q.soft_cluster) WITH ORDINALITY arr(val,i) ORDER BY val DESC LIMIT 1) as dominant_cluster
    FROM similar_questions sq
    LEFT JOIN question_performance qp ON sq.internal_question_id = qp.internal_question_id
    LEFT JOIN questions q ON sq.internal_question_id = q.internal_question_id
    WHERE COALESCE(qp.avg_success_rate, 0.5) BETWEEN min_success_rate AND max_success_rate
      AND sq.internal_question_id NOT IN (
          SELECT DISTINCT internal_question_id
          FROM student_question_history sqh2
          WHERE sqh2.enrollment_id = student_enrollment_id
      )
    ORDER BY recommendation_score DESC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- CLUSTER ANALYSIS FUNCTIONS
-- =====================================================

-- Analyze cluster characteristics
CREATE OR REPLACE FUNCTION analyze_clusters()
RETURNS void AS $$
BEGIN
    -- Update cluster statistics
    WITH cluster_stats AS (
        SELECT
            (SELECT i-1 FROM unnest(soft_cluster) WITH ORDINALITY arr(val,i) ORDER BY val DESC LIMIT 1) as cluster_id,
            COUNT(*) as question_count,
            AVG(text_length) as avg_text_length,
            ARRAY_AGG(question_id ORDER BY RANDOM() LIMIT 5) as sample_questions
        FROM questions
        WHERE soft_cluster IS NOT NULL
        GROUP BY cluster_id
    )
    INSERT INTO cluster_analysis (cluster_id, question_count, created_at)
    SELECT cluster_id, question_count, CURRENT_TIMESTAMP
    FROM cluster_stats
    ON CONFLICT (cluster_id) DO UPDATE SET
        question_count = EXCLUDED.question_count,
        updated_at = CURRENT_TIMESTAMP;

    RAISE NOTICE 'Cluster analysis updated for % clusters', (SELECT COUNT(*) FROM cluster_analysis);
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- ENHANCED VIEWS FOR VECTOR-ENABLED QUERIES
-- =====================================================

-- Student performance summary view (same as before)
CREATE VIEW student_performance_summary AS
SELECT
    s.student_id,
    s.base_student_number,
    i.institution_name,
    d.department_name,
    y.year_name,
    sec.section_name,
    sub.subject_name,
    p.paper_name,
    s.student_ability_level,
    COUNT(sqh.history_id) as total_attempts,
    COUNT(DISTINCT sqh.internal_question_id) as questions_attempted,
    SUM(CASE WHEN sqh.is_correct THEN 1 ELSE 0 END) as correct_answers,
    SUM(CASE WHEN sqh.is_skipped THEN 1 ELSE 0 END) as skipped_answers,
    ROUND(AVG(sqh.time_spent_sec), 2) as avg_time_per_question,
    ROUND(AVG(CASE WHEN sqh.is_correct THEN 1.0 ELSE 0.0 END) * 100, 2) as success_rate
FROM students s
JOIN institutions i ON s.institution_id = i.institution_id
JOIN departments d ON s.department_id = d.department_id
JOIN academic_years y ON s.year_id = y.year_id
JOIN sections sec ON s.section_id = sec.section_id
JOIN student_paper_enrollments spe ON s.student_id = spe.student_id
JOIN papers p ON spe.paper_id = p.paper_id
JOIN subjects sub ON p.subject_id = sub.subject_id
LEFT JOIN student_question_history sqh ON spe.enrollment_id = sqh.enrollment_id
GROUP BY s.student_id, s.base_student_number, i.institution_name, d.department_name,
         y.year_name, sec.section_name, sub.subject_name, p.paper_name, s.student_ability_level;

-- Enhanced question difficulty analysis with vector metadata and cluster info
CREATE VIEW question_difficulty_analysis AS
SELECT
    q.internal_question_id,
    q.question_id,
    q.question_number,
    p.paper_name,
    sub.subject_name,
    q.text_length,
    q.embedding_model,
    q.source_file,
    -- Get dominant cluster
    (SELECT i-1 FROM unnest(q.soft_cluster) WITH ORDINALITY arr(val,i) ORDER BY val DESC LIMIT 1) as dominant_cluster,
    -- Get cluster confidence (max probability)
    (SELECT MAX(val) FROM unnest(q.soft_cluster) arr(val)) as cluster_confidence,
    COUNT(sqh.history_id) as total_attempts,
    COUNT(DISTINCT sqh.enrollment_id) as students_attempted,
    SUM(CASE WHEN sqh.is_correct THEN 1 ELSE 0 END) as correct_attempts,
    ROUND(AVG(CASE WHEN sqh.is_correct THEN 1.0 ELSE 0.0 END) * 100, 2) as success_rate,
    ROUND(AVG(sqh.time_spent_sec), 2) as avg_time_spent,
    ROUND(AVG(sqh.confidence_level), 2) as avg_confidence,
    (q.openai_embedding IS NOT NULL) as has_openai_embedding,
    (q.umap_embedding IS NOT NULL) as has_umap_embedding,
    (q.soft_cluster IS NOT NULL) as has_cluster_data
FROM questions q
JOIN papers p ON q.paper_id = p.paper_id
JOIN subjects sub ON p.subject_id = sub.subject_id
LEFT JOIN student_question_history sqh ON q.internal_question_id = sqh.internal_question_id
GROUP BY q.internal_question_id, q.question_id, q.question_number, p.paper_name, sub.subject_name,
         q.text_length, q.embedding_model, q.source_file, q.openai_embedding, q.umap_embedding, q.soft_cluster
ORDER BY success_rate ASC, avg_time_spent DESC;

-- Cluster performance analysis view
CREATE VIEW cluster_performance_analysis AS
SELECT
    (SELECT i-1 FROM unnest(q.soft_cluster) WITH ORDINALITY arr(val,i) ORDER BY val DESC LIMIT 1) as cluster_id,
    COUNT(DISTINCT q.internal_question_id) as question_count,
    COUNT(sqh.history_id) as total_attempts,
    COUNT(DISTINCT sqh.enrollment_id) as students_attempted,
    ROUND(AVG(CASE WHEN sqh.is_correct THEN 1.0 ELSE 0.0 END) * 100, 2) as avg_success_rate,
    ROUND(AVG(sqh.time_spent_sec), 2) as avg_time_spent,
    ROUND(AVG(q.text_length), 0) as avg_text_length,
    ROUND(AVG((SELECT MAX(val) FROM unnest(q.soft_cluster) arr(val))), 3) as avg_cluster_confidence
FROM questions q
LEFT JOIN student_question_history sqh ON q.internal_question_id = sqh.internal_question_id
WHERE q.soft_cluster IS NOT NULL
GROUP BY cluster_id
ORDER BY cluster_id;

-- =====================================================
-- TRIGGERS FOR AUDIT TRAIL
-- =====================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Add update triggers to main tables
CREATE TRIGGER update_institutions_updated_at BEFORE UPDATE ON institutions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_departments_updated_at BEFORE UPDATE ON departments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_students_updated_at BEFORE UPDATE ON students
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_questions_updated_at BEFORE UPDATE ON questions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_cluster_analysis_updated_at BEFORE UPDATE ON cluster_analysis
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- POPULATE CLUSTER ANALYSIS DATA
-- =====================================================

-- Initialize cluster analysis table with your 20 clusters
INSERT INTO cluster_analysis (cluster_id, cluster_name, cluster_description) VALUES
(0, 'Cluster 0', 'Cluster 0 analysis pending'),
(1, 'Cluster 1', 'Cluster 1 analysis pending'),
(2, 'Cluster 2', 'Cluster 2 analysis pending'),
(3, 'Cluster 3', 'Cluster 3 analysis pending'),
(4, 'Cluster 4', 'Cluster 4 analysis pending'),
(5, 'Cluster 5', 'Cluster 5 analysis pending'),
(6, 'Cluster 6', 'Cluster 6 analysis pending'),
(7, 'Cluster 7', 'Cluster 7 analysis pending'),
(8, 'Cluster 8', 'Cluster 8 analysis pending'),
(9, 'Cluster 9', 'Cluster 9 analysis pending'),
(10, 'Cluster 10', 'Cluster 10 analysis pending'),
(11, 'Cluster 11', 'Cluster 11 analysis pending'),
(12, 'Cluster 12', 'Cluster 12 analysis pending'),
(13, 'Cluster 13', 'Cluster 13 analysis pending'),
(14, 'Cluster 14', 'Cluster 14 analysis pending'),
(15, 'Cluster 15', 'Cluster 15 analysis pending'),
(16, 'Cluster 16', 'Cluster 16 analysis pending'),
(17, 'Cluster 17', 'Cluster 17 analysis pending'),
(18, 'Cluster 18', 'Cluster 18 analysis pending'),
(19, 'Cluster 19', 'Cluster 19 analysis pending')
ON CONFLICT (cluster_id) DO NOTHING;

-- =====================================================
-- TRANSITION MATRICES TABLE (For ML Learning Pathways)
-- =====================================================

-- Table to store precomputed transition matrices
CREATE TABLE IF NOT EXISTS transition_matrices (
    matrix_id SERIAL PRIMARY KEY,
    source_data_hash VARCHAR(32) NOT NULL,
    matrix_data JSONB NOT NULL,
    metadata JSONB NOT NULL,
    algorithm_name VARCHAR(100) NOT NULL DEFAULT 'cooccurrence_transitions',
    algorithm_version VARCHAR(20) NOT NULL DEFAULT '1.0',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_transition_matrices_hash_active
    ON transition_matrices(source_data_hash, is_active);
CREATE INDEX IF NOT EXISTS idx_transition_matrices_algorithm
    ON transition_matrices(algorithm_name, algorithm_version);
CREATE INDEX IF NOT EXISTS idx_transition_matrices_created
    ON transition_matrices(created_at DESC);

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_transition_matrices_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_transition_matrices_updated_at
    BEFORE UPDATE ON transition_matrices
    FOR EACH ROW
    EXECUTE FUNCTION update_transition_matrices_updated_at();

-- Function to get the latest transition matrix
CREATE OR REPLACE FUNCTION get_latest_transition_matrix(
    p_source_hash VARCHAR(32) DEFAULT NULL
)
RETURNS TABLE (
    matrix_data JSONB,
    metadata JSONB,
    created_at TIMESTAMP
) AS $$
BEGIN
    IF p_source_hash IS NOT NULL THEN
        -- Get matrix for specific source data hash
        RETURN QUERY
        SELECT tm.matrix_data, tm.metadata, tm.created_at
        FROM transition_matrices tm
        WHERE tm.source_data_hash = p_source_hash
        AND tm.is_active = true
        ORDER BY tm.created_at DESC
        LIMIT 1;
    ELSE
        -- Get most recent active matrix
        RETURN QUERY
        SELECT tm.matrix_data, tm.metadata, tm.created_at
        FROM transition_matrices tm
        WHERE tm.is_active = true
        ORDER BY tm.created_at DESC
        LIMIT 1;
    END IF;
END;
$$ language 'plpgsql';

-- Function to invalidate old transition matrices
CREATE OR REPLACE FUNCTION cleanup_old_transition_matrices(
    p_keep_count INTEGER DEFAULT 5
)
RETURNS INTEGER AS $$
DECLARE
    affected_rows INTEGER;
BEGIN
    -- Keep only the latest p_keep_count matrices per algorithm
    WITH ranked_matrices AS (
        SELECT matrix_id,
               ROW_NUMBER() OVER (
                   PARTITION BY algorithm_name, algorithm_version
                   ORDER BY created_at DESC
               ) as rn
        FROM transition_matrices
        WHERE is_active = true
    )
    UPDATE transition_matrices
    SET is_active = false
    WHERE matrix_id IN (
        SELECT matrix_id FROM ranked_matrices WHERE rn > p_keep_count
    );

    GET DIAGNOSTICS affected_rows = ROW_COUNT;
    RETURN affected_rows;
END;
$$ language 'plpgsql';

-- =====================================================
-- EXAMPLE QUERIES FOR YOUR SPECIFIC DATA
-- =====================================================

-- Find similar questions using OpenAI text-embedding-3-large (3072D)
-- SELECT * FROM find_similar_questions_openai('[0.01381706, -0.00438518, ...]'::vector(3072), 0.7, 5);

-- Find similar questions using 50D UMAP embeddings
-- SELECT * FROM find_similar_questions_umap('[1.89422726, 7.15444236, ...]'::vector(50), 0.5, 5);

-- Find questions in the same cluster as cluster 5 (largest cluster with 587 questions)
-- SELECT * FROM find_similar_questions_cluster(
--     (SELECT soft_cluster FROM questions WHERE question_id = 'some_question_id'),
--     0.8, 10
-- );

-- Multi-modal similarity search
-- SELECT * FROM find_similar_questions_multimodal(
--     '[0.01381706, -0.00438518, ...]'::vector(3072),  -- OpenAI embedding
--     '[1.89422726, 7.15444236, ...]'::vector(50),     -- UMAP embedding
--     NULL,                                             -- Cluster (optional)
--     0.6, 0.2, 0.2,                                  -- Weights (openai, umap, cluster)
--     0.6, 10                                          -- Threshold and limit
-- );

-- Get hybrid recommendations for a student
-- SELECT * FROM recommend_questions_hybrid(123, '[0.01381706, ...]'::vector(3072), 0.6, 0.3, 0.8, 5);

-- Analyze cluster performance
-- SELECT * FROM cluster_performance_analysis ORDER BY avg_success_rate;

-- Update cluster statistics
-- SELECT analyze_clusters();

-- Performance analytics by cluster
-- SELECT
--     cluster_id,
--     question_count,
--     avg_success_rate,
--     avg_time_spent,
--     CASE
--         WHEN avg_success_rate > 80 THEN 'Easy'
--         WHEN avg_success_rate > 60 THEN 'Medium'
--         WHEN avg_success_rate > 40 THEN 'Hard'
--         ELSE 'Very Hard'
--     END as difficulty_level
-- FROM cluster_performance_analysis
-- ORDER BY avg_success_rate DESC;
