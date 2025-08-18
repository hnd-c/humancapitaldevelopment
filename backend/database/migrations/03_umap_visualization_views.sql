-- =====================================================
-- 03_UMAP_VISUALIZATION_VIEWS.SQL
-- Student-specific UMAP visualization system
-- =====================================================

-- Materialized view for student question status with 2D UMAP coordinates
CREATE MATERIALIZED VIEW student_question_status AS
WITH latest_attempts AS (
    SELECT
        sqh.enrollment_id,
        sqh.internal_question_id,
        sqh.status as latest_status,
        sqh.is_correct as latest_is_correct,
        sqh.is_skipped as latest_is_skipped,
        sqh.confidence_level as latest_confidence,
        sqh.time_spent_sec as latest_time_spent,
        sqh.timestamp as latest_attempt_time,
        ROW_NUMBER() OVER (
            PARTITION BY sqh.enrollment_id, sqh.internal_question_id
            ORDER BY sqh.timestamp DESC
        ) as rn
    FROM student_question_history sqh
),
aggregated_attempts AS (
    SELECT
        sqh.enrollment_id,
        sqh.internal_question_id,
        COUNT(*) as total_attempts,
        COUNT(CASE WHEN sqh.is_correct THEN 1 END) as correct_attempts,
        COUNT(CASE WHEN sqh.is_skipped THEN 1 END) as skipped_attempts,
        SUM(sqh.time_spent_sec) as total_time_spent,
        AVG(sqh.confidence_level) as avg_confidence,
        MIN(sqh.timestamp) as first_attempt,
        MAX(sqh.timestamp) as last_attempt
    FROM student_question_history sqh
    GROUP BY sqh.enrollment_id, sqh.internal_question_id
)
SELECT
    spe.student_id,
    q.question_id,
    q.internal_question_id,
    (q.umap_2d_embedding::real[])[1] as x_coord,
    (q.umap_2d_embedding::real[])[2] as y_coord,

    -- Status calculation with proper logic
    CASE
        WHEN aa.total_attempts IS NULL THEN 'not_attempted'
        WHEN la.latest_is_skipped THEN 'skipped'
        WHEN aa.correct_attempts > 0 AND la.latest_is_correct THEN 'mastered'
        WHEN aa.correct_attempts > 0 AND NOT la.latest_is_correct THEN 'mixed'
        WHEN aa.correct_attempts = 0 AND aa.skipped_attempts = aa.total_attempts THEN 'skipped'
        ELSE 'incorrect'
    END as status,

    -- Attempt statistics
    COALESCE(aa.total_attempts, 0) as attempt_count,
    COALESCE(aa.correct_attempts, 0) as correct_count,
    COALESCE(aa.skipped_attempts, 0) as skipped_count,
    aa.total_time_spent,
    ROUND(aa.avg_confidence, 2) as avg_confidence,
    la.latest_attempt_time,
    la.latest_confidence,
    la.latest_time_spent,

    -- Color mapping for frontend
    CASE
        WHEN aa.total_attempts IS NULL THEN '#999999'  -- Gray: Not attempted
        WHEN la.latest_is_skipped THEN '#FF9800'      -- Orange: Skipped
        WHEN aa.correct_attempts > 0 AND la.latest_is_correct THEN '#4CAF50'  -- Green: Mastered
        WHEN aa.correct_attempts > 0 AND NOT la.latest_is_correct THEN '#FFEB3B'  -- Yellow: Mixed
        WHEN aa.correct_attempts = 0 AND aa.skipped_attempts = aa.total_attempts THEN '#FF9800'  -- Orange: All skipped
        ELSE '#F44336'  -- Red: Incorrect
    END as color_code,

    -- Question metadata for optional inclusion
    q.question_number,
    q.text_length,
    p.paper_code,
    p.paper_name,
    SUBSTRING(q.combined_text, 1, 100) as text_preview,

    -- Timestamps
    q.updated_at as question_updated_at,
    CURRENT_TIMESTAMP as view_updated_at
FROM questions q
JOIN papers p ON q.paper_id = p.paper_id
CROSS JOIN student_paper_enrollments spe  -- Get all student-question combinations
LEFT JOIN aggregated_attempts aa ON aa.enrollment_id = spe.enrollment_id
    AND aa.internal_question_id = q.internal_question_id
LEFT JOIN latest_attempts la ON la.enrollment_id = spe.enrollment_id
    AND la.internal_question_id = q.internal_question_id
    AND la.rn = 1
WHERE q.umap_2d_embedding IS NOT NULL
    AND spe.is_active = TRUE;

-- Performance indexes for the materialized view
CREATE INDEX idx_student_status_student ON student_question_status (student_id);
CREATE INDEX idx_student_status_coords ON student_question_status (x_coord, y_coord);
CREATE INDEX idx_student_status_status ON student_question_status (status);
CREATE INDEX idx_student_status_composite ON student_question_status (student_id, status);
CREATE INDEX idx_student_status_paper ON student_question_status (paper_code);
CREATE INDEX idx_student_status_spatial ON student_question_status (x_coord, y_coord, student_id);

-- View for basic 2D UMAP coordinates (non-student specific)
CREATE VIEW question_coordinates_2d AS
SELECT
    q.question_id,
    q.internal_question_id,
    (q.umap_2d_embedding::real[])[1] as x_coord,
    (q.umap_2d_embedding::real[])[2] as y_coord,
    -- Pre-compute cluster instead of calculating each time
    (SELECT i-1 FROM unnest(q.soft_cluster::real[]) WITH ORDINALITY arr(val,i)
     ORDER BY val DESC LIMIT 1) as cluster_id,
    (SELECT MAX(val) FROM unnest(q.soft_cluster::real[]) arr(val)) as cluster_confidence,
    q.question_number,
    q.text_length,
    p.paper_name,
    p.paper_code,
    SUBSTRING(q.combined_text, 1, 100) as text_preview,
    q.updated_at
FROM questions q
JOIN papers p ON q.paper_id = p.paper_id
WHERE q.umap_2d_embedding IS NOT NULL;

-- Note: Cannot create indexes on regular views
-- Indexes would need to be on the underlying questions table if needed

-- Function to refresh student status materialized view
CREATE OR REPLACE FUNCTION refresh_student_status_view()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY student_question_status;
END;
$$ LANGUAGE plpgsql;

-- Function to refresh student status for specific student (for real-time updates)
CREATE OR REPLACE FUNCTION refresh_student_status_for_student(target_student_id VARCHAR)
RETURNS void AS $$
BEGIN
    -- Delete existing data for this student
    DELETE FROM student_question_status WHERE student_id = target_student_id;

    -- Re-insert updated data for this student
    INSERT INTO student_question_status
    SELECT * FROM (
        WITH latest_attempts AS (
            SELECT
                sqh.enrollment_id,
                sqh.internal_question_id,
                sqh.status as latest_status,
                sqh.is_correct as latest_is_correct,
                sqh.is_skipped as latest_is_skipped,
                sqh.confidence_level as latest_confidence,
                sqh.time_spent_sec as latest_time_spent,
                sqh.timestamp as latest_attempt_time,
                ROW_NUMBER() OVER (
                    PARTITION BY sqh.enrollment_id, sqh.internal_question_id
                    ORDER BY sqh.timestamp DESC
                ) as rn
            FROM student_question_history sqh
            JOIN student_paper_enrollments spe ON sqh.enrollment_id = spe.enrollment_id
            WHERE spe.student_id = target_student_id
        ),
        aggregated_attempts AS (
            SELECT
                sqh.enrollment_id,
                sqh.internal_question_id,
                COUNT(*) as total_attempts,
                COUNT(CASE WHEN sqh.is_correct THEN 1 END) as correct_attempts,
                COUNT(CASE WHEN sqh.is_skipped THEN 1 END) as skipped_attempts,
                SUM(sqh.time_spent_sec) as total_time_spent,
                AVG(sqh.confidence_level) as avg_confidence,
                MIN(sqh.timestamp) as first_attempt,
                MAX(sqh.timestamp) as last_attempt
            FROM student_question_history sqh
            JOIN student_paper_enrollments spe ON sqh.enrollment_id = spe.enrollment_id
            WHERE spe.student_id = target_student_id
            GROUP BY sqh.enrollment_id, sqh.internal_question_id
        )
        SELECT
            spe.student_id,
            q.question_id,
            q.internal_question_id,
            (q.umap_2d_embedding::real[])[1] as x_coord,
            (q.umap_2d_embedding::real[])[2] as y_coord,

            CASE
                WHEN aa.total_attempts IS NULL THEN 'not_attempted'
                WHEN la.latest_is_skipped THEN 'skipped'
                WHEN aa.correct_attempts > 0 AND la.latest_is_correct THEN 'mastered'
                WHEN aa.correct_attempts > 0 AND NOT la.latest_is_correct THEN 'mixed'
                WHEN aa.correct_attempts = 0 AND aa.skipped_attempts = aa.total_attempts THEN 'skipped'
                ELSE 'incorrect'
            END as status,

            COALESCE(aa.total_attempts, 0) as attempt_count,
            COALESCE(aa.correct_attempts, 0) as correct_count,
            COALESCE(aa.skipped_attempts, 0) as skipped_count,
            aa.total_time_spent,
            ROUND(aa.avg_confidence, 2) as avg_confidence,
            la.latest_attempt_time,
            la.latest_confidence,
            la.latest_time_spent,

            CASE
                WHEN aa.total_attempts IS NULL THEN '#999999'
                WHEN la.latest_is_skipped THEN '#FF9800'
                WHEN aa.correct_attempts > 0 AND la.latest_is_correct THEN '#4CAF50'
                WHEN aa.correct_attempts > 0 AND NOT la.latest_is_correct THEN '#FFEB3B'
                WHEN aa.correct_attempts = 0 AND aa.skipped_attempts = aa.total_attempts THEN '#FF9800'
                ELSE '#F44336'
            END as color_code,

            q.question_number,
            q.text_length,
            p.paper_code,
            p.paper_name,
            SUBSTRING(q.combined_text, 1, 100) as text_preview,
            q.updated_at as question_updated_at,
            CURRENT_TIMESTAMP as view_updated_at
        FROM questions q
        JOIN papers p ON q.paper_id = p.paper_id
        JOIN student_paper_enrollments spe ON spe.student_id = target_student_id
        LEFT JOIN aggregated_attempts aa ON aa.enrollment_id = spe.enrollment_id
            AND aa.internal_question_id = q.internal_question_id
        LEFT JOIN latest_attempts la ON la.enrollment_id = spe.enrollment_id
            AND la.internal_question_id = q.internal_question_id
            AND la.rn = 1
        WHERE q.umap_2d_embedding IS NOT NULL
            AND spe.is_active = TRUE
    ) AS updated_data;
END;
$$ LANGUAGE plpgsql;

-- Trigger function for real-time updates
CREATE OR REPLACE FUNCTION notify_student_status_change()
RETURNS TRIGGER AS $$
DECLARE
    affected_student_id VARCHAR;
BEGIN
    -- Get the student ID from the enrollment
    SELECT spe.student_id INTO affected_student_id
    FROM student_paper_enrollments spe
    WHERE spe.enrollment_id = NEW.enrollment_id;

    -- Notify the application about the change
    PERFORM pg_notify('student_status_changed', affected_student_id);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for real-time updates
CREATE TRIGGER trigger_student_status_update
    AFTER INSERT OR UPDATE ON student_question_history
    FOR EACH ROW
    EXECUTE FUNCTION notify_student_status_change();

-- Helper function to get UMAP bounds for visualization
CREATE OR REPLACE FUNCTION get_umap_bounds()
RETURNS TABLE(
    x_min FLOAT,
    x_max FLOAT,
    y_min FLOAT,
    y_max FLOAT,
    center_x FLOAT,
    center_y FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        MIN((umap_2d_embedding::real[])[1])::FLOAT as x_min,
        MAX((umap_2d_embedding::real[])[1])::FLOAT as x_max,
        MIN((umap_2d_embedding::real[])[2])::FLOAT as y_min,
        MAX((umap_2d_embedding::real[])[2])::FLOAT as y_max,
        AVG((umap_2d_embedding::real[])[1])::FLOAT as center_x,
        AVG((umap_2d_embedding::real[])[2])::FLOAT as center_y
    FROM questions
    WHERE umap_2d_embedding IS NOT NULL;
END;
$$ LANGUAGE plpgsql;

-- Grant necessary permissions
GRANT SELECT ON student_question_status TO PUBLIC;
GRANT SELECT ON question_coordinates_2d TO PUBLIC;
