-- Half-Precision Vector Indexes for OpenAI Embeddings (3072 dimensions)
-- Run this script AFTER loading your vector data into the questions table
--
-- This script creates indexes using half-precision conversion to handle
-- OpenAI text-embedding-3-large embeddings (3072 dimensions) which exceed
-- the standard pgvector index limit of 2000 dimensions.

-- Check if we have data before creating indexes
DO $$
BEGIN
    IF (SELECT COUNT(*) FROM questions WHERE openai_embedding IS NOT NULL) > 0 THEN
        RAISE NOTICE 'Creating half-precision indexes for OpenAI embeddings...';

        -- Create half-precision HNSW index for cosine similarity
        -- This converts vector(3072) to halfvec on-the-fly for indexing
        CREATE INDEX IF NOT EXISTS idx_questions_openai_cosine_halfvec
        ON questions USING hnsw (vector_to_halfvec(openai_embedding, 3072, false) halfvec_cosine_ops)
        WITH (m = 16, ef_construction = 64);

        -- Create half-precision HNSW index for L2 distance
        CREATE INDEX IF NOT EXISTS idx_questions_openai_l2_halfvec
        ON questions USING hnsw (vector_to_halfvec(openai_embedding, 3072, false) halfvec_l2_ops)
        WITH (m = 16, ef_construction = 64);

        RAISE NOTICE 'Half-precision indexes created successfully!';
        RAISE NOTICE 'Usage examples:';
        RAISE NOTICE '  Cosine similarity: SELECT * FROM questions ORDER BY vector_to_halfvec(openai_embedding, 3072, false) <=> vector_to_halfvec($$[your_query_vector]$$::vector, 3072, false) LIMIT 10;';
        RAISE NOTICE '  L2 distance: SELECT * FROM questions ORDER BY vector_to_halfvec(openai_embedding, 3072, false) <-> vector_to_halfvec($$[your_query_vector]$$::vector, 3072, false) LIMIT 10;';
    ELSE
        RAISE NOTICE 'No vector data found in questions table. Load your data first, then run this script.';
    END IF;
END $$;
