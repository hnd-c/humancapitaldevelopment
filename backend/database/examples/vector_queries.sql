-- Vector Query Examples for OpenAI Embeddings (3072 dimensions)
--
-- Since OpenAI embeddings exceed the 2000-dimension index limit,
-- you can still perform vector similarity searches using direct distance functions.
-- These will be slower than indexed searches but still functional.

-- Example 1: Direct cosine similarity search (no index required)
-- Replace [your_query_vector] with your actual 3072-dimension vector
/*
SELECT
    question_id,
    question_text,
    1 - (openai_embedding <=> '[your_query_vector]'::vector) as cosine_similarity
FROM questions
WHERE openai_embedding IS NOT NULL
ORDER BY openai_embedding <=> '[your_query_vector]'::vector
LIMIT 10;
*/

-- Example 2: Direct L2 distance search (no index required)
/*
SELECT
    question_id,
    question_text,
    openai_embedding <-> '[your_query_vector]'::vector as l2_distance
FROM questions
WHERE openai_embedding IS NOT NULL
ORDER BY openai_embedding <-> '[your_query_vector]'::vector
LIMIT 10;
*/

-- Example 3: Using half-precision indexes (after running create_halfprecision_indexes.sql)
/*
SELECT
    question_id,
    question_text,
    vector_to_halfvec(openai_embedding, 3072, false) <=> vector_to_halfvec('[your_query_vector]'::vector, 3072, false) as halfvec_cosine_distance
FROM questions
WHERE openai_embedding IS NOT NULL
ORDER BY vector_to_halfvec(openai_embedding, 3072, false) <=> vector_to_halfvec('[your_query_vector]'::vector, 3072, false)
LIMIT 10;
*/

-- Performance tip: If you need faster queries, consider:
-- 1. Using the half-precision indexes (run create_halfprecision_indexes.sql after loading data)
-- 2. Adding a WHERE clause to filter data before similarity search
-- 3. Using approximate search with higher ef_search values for HNSW indexes

-- Check vector dimensions in your data
SELECT
    vector_dims(openai_embedding) as openai_dims,
    COUNT(*) as count
FROM questions
WHERE openai_embedding IS NOT NULL
GROUP BY vector_dims(openai_embedding);
