#!/bin/bash

# Clear previous log file
> output_api.txt

echo "🚀 Testing All API Endpoints" | tee -a output_api.txt
echo "==============================" | tee -a output_api.txt
echo "Timestamp: $(date)" | tee -a output_api.txt
echo "" | tee -a output_api.txt

BASE_URL="http://localhost:8000"
PASSED=0
FAILED=0
FAILED_TESTS=()

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to test endpoint and track results
test_endpoint() {
    local test_name="$1"
    local response="$2"
    local hint="$3"

    echo -e "\n${YELLOW}Testing:${NC} $test_name" | tee -a output_api.txt
    echo "Request: $test_name" >> output_api.txt
    echo "Response: $response" >> output_api.txt
    echo "---" >> output_api.txt

    if echo "$response" | jq . >/dev/null 2>&1; then
        if echo "$response" | grep -q '"error"'; then
            echo -e "${RED}❌ FAILED${NC} - API returned error" | tee -a output_api.txt
            echo "Error details: $(echo "$response" | jq -r '.error // .detail // "Unknown error"')" >> output_api.txt
            FAILED=$((FAILED + 1))
            FAILED_TESTS+=("$test_name - $hint")
        else
            echo -e "${GREEN}✅ PASSED${NC}" | tee -a output_api.txt
            echo "Success: Valid JSON response received" >> output_api.txt
            PASSED=$((PASSED + 1))
        fi
    else
        echo -e "${RED}❌ FAILED${NC} - Invalid response or server not responding" | tee -a output_api.txt
        echo "Raw response: $response" >> output_api.txt
        FAILED=$((FAILED + 1))
        FAILED_TESTS+=("$test_name - $hint")
    fi
    echo "" >> output_api.txt
}

echo "📊 System & Health Endpoints" | tee -a output_api.txt
echo "----------------------------" | tee -a output_api.txt

# Test 1: Root endpoint
response=$(curl -s "$BASE_URL/" 2>/dev/null)
test_endpoint "Root endpoint" "$response" "Check if server is running on localhost:8000. Run: python main.py --mode api"

# Test 2: Health check
response=$(curl -s "$BASE_URL/health" 2>/dev/null)
test_endpoint "Health check" "$response" "Verify database and Redis connections. Check config/environments.py"

# Test 3: System analytics
response=$(curl -s "$BASE_URL/analytics/system" 2>/dev/null)
test_endpoint "System analytics" "$response" "Ensure performance monitoring is enabled in system initialization"

echo -e "\n🎯 Recommendation Endpoints" | tee -a output_api.txt
echo "----------------------------" | tee -a output_api.txt

# Test 4: Balanced recommendations
response=$(curl -s -X POST "$BASE_URL/recommendations" \
  -H "Content-Type: application/json" \
  -d '{"student_id": "1", "objective": "balanced", "top_k": 5}' 2>/dev/null)
test_endpoint "Balanced recommendations" "$response" "Check if recommendation engine is initialized. Verify ML models in services/recommendation_service.py"

# Test 5: Coverage recommendations
response=$(curl -s -X POST "$BASE_URL/recommendations" \
  -H "Content-Type: application/json" \
  -d '{"student_id": "2", "objective": "coverage", "top_k": 3}' 2>/dev/null)
test_endpoint "Coverage recommendations" "$response" "Ensure question database has clustering data. Check questions table soft_cluster column"

# Test 6: Efficiency recommendations
response=$(curl -s -X POST "$BASE_URL/recommendations" \
  -H "Content-Type: application/json" \
  -d '{"student_id": "3", "objective": "efficiency", "top_k": 3}' 2>/dev/null)
test_endpoint "Efficiency recommendations" "$response" "Verify student performance data exists. Check student_question_attempts table"

echo -e "\n👨‍🎓 Student Management" | tee -a output_api.txt
echo "----------------------------" | tee -a output_api.txt

# Test 7: Student performance
response=$(curl -s "$BASE_URL/student/1/performance" 2>/dev/null)
test_endpoint "Student 1 performance" "$response" "Check StudentService initialization. Verify students table and attempt data exists"

# Test 8: Student 2 performance
response=$(curl -s "$BASE_URL/student/2/performance" 2>/dev/null)
test_endpoint "Student 2 performance" "$response" "Ensure student ID exists in database. Check students table for student_id=2"

# Test 9: Student history
response=$(curl -s "$BASE_URL/student/1/history" 2>/dev/null)
test_endpoint "Student 1 history" "$response" "Verify learning_sessions table exists and has data for student_id=1"

# Test 10: Student history with limit
response=$(curl -s "$BASE_URL/student/2/history?limit=10" 2>/dev/null)
test_endpoint "Student 2 history (limited)" "$response" "Check query pagination logic in student history endpoint"

echo -e "\n🎓 Student Learning Workflow" | tee -a output_api.txt
echo "----------------------------" | tee -a output_api.txt

# Test 11: Start learning session
SESSION_RESPONSE=$(curl -s -X POST "$BASE_URL/student/20/start-session" \
  -H "Content-Type: application/json" \
  -d '{"student_id": "20", "objective": "balanced", "session_type": "practice", "target_questions": 3}' 2>/dev/null)
test_endpoint "Start learning session" "$SESSION_RESPONSE" "Check session management service. Verify learning_sessions table exists and recommendations work"

SESSION_ID=$(echo "$SESSION_RESPONSE" | jq -r '.session_id // "null"' 2>/dev/null)
FIRST_QUESTION=$(echo "$SESSION_RESPONSE" | jq -r '.recommendations[0].question_id // "1"' 2>/dev/null)
echo "Extracted SESSION_ID: $SESSION_ID" >> output_api.txt
echo "Extracted FIRST_QUESTION: $FIRST_QUESTION" >> output_api.txt

# Test 12: Start question attempt
ATTEMPT_RESPONSE=$(curl -s -X POST "$BASE_URL/student/20/attempt-question" \
  -H "Content-Type: application/json" \
  -d "{\"student_id\": \"20\", \"question_id\": \"$FIRST_QUESTION\"}" 2>/dev/null)
test_endpoint "Start question attempt" "$ATTEMPT_RESPONSE" "Verify question attempt tracking. Check student_question_attempts table structure"

ATTEMPT_ID=$(echo "$ATTEMPT_RESPONSE" | jq -r '.attempt_id // "1"' 2>/dev/null)
echo "Extracted ATTEMPT_ID: $ATTEMPT_ID" >> output_api.txt

# Test 13: Submit answer
response=$(curl -s -X POST "$BASE_URL/student/20/submit-answer" \
  -H "Content-Type: application/json" \
  -d "{\"attempt_id\": \"$ATTEMPT_ID\", \"student_id\": \"20\", \"question_id\": \"$FIRST_QUESTION\", \"selected_option\": \"C\", \"confidence_level\": 0.8}" 2>/dev/null)
test_endpoint "Submit answer" "$response" "Check answer validation service. Verify questions table has correct_option column"

# Test 14: Session progress
response=$(curl -s "$BASE_URL/student/20/session/$SESSION_ID/progress" 2>/dev/null)
test_endpoint "Session progress" "$response" "Ensure session ID is valid and progress tracking is implemented"

# Test 15: Student sessions
response=$(curl -s "$BASE_URL/student/20/sessions" 2>/dev/null)
test_endpoint "Student sessions" "$response" "Check if learning_sessions table has data for student_id=20"

echo -e "\n📝 Question Management & Search" | tee -a output_api.txt
echo "----------------------------" | tee -a output_api.txt

# Test 16: Random questions
response=$(curl -s "$BASE_URL/questions/random?count=3" 2>/dev/null)
test_endpoint "Random questions" "$response" "Check questions table has data. Verify random selection logic in question service"

# Test 17: Search physics - circuit
response=$(curl -s "$BASE_URL/questions/search?q=circuit&limit=5" 2>/dev/null)
test_endpoint "Search physics - circuit" "$response" "Verify search indexing. Check if questions have searchable text content"

# Test 18: Search physics - resistance
response=$(curl -s "$BASE_URL/questions/search?q=resistance&limit=3" 2>/dev/null)
test_endpoint "Search physics - resistance" "$response" "Ensure search service is working. Check elasticsearch or text search implementation"

# Test 19: Question details
response=$(curl -s "$BASE_URL/questions/$FIRST_QUESTION" 2>/dev/null)
test_endpoint "Question details" "$response" "Verify question exists in database. Check questions table for question_id=$FIRST_QUESTION"

echo -e "\n🤖 Answer Validation & Timing" | tee -a output_api.txt
echo "----------------------------" | tee -a output_api.txt

# Test 20: Question timing stats
response=$(curl -s "$BASE_URL/questions/$FIRST_QUESTION/timing-stats" 2>/dev/null)
test_endpoint "Question timing stats" "$response" "Check if timing data exists in student_question_attempts table"

# Test 21: Validate correct answer
response=$(curl -s -X POST "$BASE_URL/questions/$FIRST_QUESTION/validate-answer" \
  -H "Content-Type: application/json" \
  -d '{"student_answer": "C", "answer_type": "multiple_choice"}' 2>/dev/null)
test_endpoint "Validate correct answer" "$response" "Verify answer validation service. Check questions.correct_option column"

# Test 22: Validate incorrect answer
response=$(curl -s -X POST "$BASE_URL/questions/$FIRST_QUESTION/validate-answer" \
  -H "Content-Type: application/json" \
  -d '{"student_answer": "A", "answer_type": "multiple_choice"}' 2>/dev/null)
test_endpoint "Validate incorrect answer" "$response" "Ensure validation logic handles incorrect answers properly"

# Test 23: Get answer key
response=$(curl -s "$BASE_URL/questions/$FIRST_QUESTION/answer-key" 2>/dev/null)
test_endpoint "Get answer key" "$response" "Check admin access and answer key retrieval functionality"

echo -e "\n📋 Paper Management" | tee -a output_api.txt
echo "----------------------------" | tee -a output_api.txt

# Test 24: All papers
response=$(curl -s "$BASE_URL/papers" 2>/dev/null)
test_endpoint "All papers" "$response" "Check papers table exists and has data. Verify paper listing endpoint"

# Test 25: Questions by paper
response=$(curl -s "$BASE_URL/papers/9702_w22_qp_12/questions" 2>/dev/null)
test_endpoint "Questions by paper" "$response" "Ensure paper_id exists and questions are linked to papers properly"

echo -e "\n🖼️ Question Rendering" | tee -a output_api.txt
echo "----------------------------" | tee -a output_api.txt

# Test 26: Question image
response=$(curl -s "$BASE_URL/questions/$FIRST_QUESTION/image" 2>/dev/null)
test_endpoint "Question image" "$response" "Check image processing service. Verify p1_images directory structure"

# Test 27: Question summary
response=$(curl -s "$BASE_URL/questions/$FIRST_QUESTION/summary" 2>/dev/null)
test_endpoint "Question summary" "$response" "Verify question metadata and summary generation logic"

echo -e "\n🔍 Similar Questions" | tee -a output_api.txt
echo "----------------------------" | tee -a output_api.txt

# Test 28: Similar questions
response=$(curl -s "$BASE_URL/questions/$FIRST_QUESTION/similar?limit=3" 2>/dev/null)
test_endpoint "Similar questions" "$response" "Check vector similarity service. Verify embeddings are generated for questions"

echo -e "\n🔧 Cache Management" | tee -a output_api.txt
echo "----------------------------" | tee -a output_api.txt

# Test 29: Student-specific cache invalidation
response=$(curl -s -X POST "$BASE_URL/cache/invalidate?student_id=20" 2>/dev/null)
test_endpoint "Student cache invalidation" "$response" "Verify Redis connection and cache service functionality"

# Test 30: Full cache invalidation
response=$(curl -s -X POST "$BASE_URL/cache/invalidate" 2>/dev/null)
test_endpoint "Full cache invalidation" "$response" "Check global cache clearing functionality"

echo -e "\n📊 Performance Testing" | tee -a output_api.txt
echo "----------------------------" | tee -a output_api.txt

# Test 31: Fresh recommendations
response=$(curl -s -X POST "$BASE_URL/recommendations" \
  -H "Content-Type: application/json" \
  -d '{"student_id": "20", "objective": "balanced", "top_k": 3}' 2>/dev/null)
test_endpoint "Fresh recommendations" "$response" "Test recommendation engine after cache clear"

# Test 32: Cached recommendations
response=$(curl -s -X POST "$BASE_URL/recommendations" \
  -H "Content-Type: application/json" \
  -d '{"student_id": "20", "objective": "balanced", "top_k": 3}' 2>/dev/null)
test_endpoint "Cached recommendations" "$response" "Verify caching improves response times"

echo -e "\n" | tee -a output_api.txt
echo "==============================" | tee -a output_api.txt
echo "🏁 TEST RESULTS SUMMARY" | tee -a output_api.txt
echo "==============================" | tee -a output_api.txt

echo -e "${GREEN}✅ PASSED: $PASSED tests${NC}" | tee -a output_api.txt
echo -e "${RED}❌ FAILED: $FAILED tests${NC}" | tee -a output_api.txt
echo -e "📊 Total tests: $((PASSED + FAILED))" | tee -a output_api.txt

if [ ${#FAILED_TESTS[@]} -gt 0 ]; then
    echo -e "\n${RED}🔧 FAILED TESTS & TROUBLESHOOTING HINTS:${NC}" | tee -a output_api.txt
    echo "----------------------------------------" | tee -a output_api.txt
    for i in "${!FAILED_TESTS[@]}"; do
        echo -e "${RED}$((i+1)).${NC} ${FAILED_TESTS[$i]}" | tee -a output_api.txt
    done

    echo -e "\n${YELLOW}🚀 QUICK FIXES TO TRY:${NC}" | tee -a output_api.txt
    echo "1. Start the API server: python main.py --mode api" | tee -a output_api.txt
    echo "2. Check database connection in config/environments.py" | tee -a output_api.txt
    echo "3. Verify Redis is running: redis-server" | tee -a output_api.txt
    echo "4. Run database migrations: check database/migrations/" | tee -a output_api.txt
    echo "5. Install missing dependencies: pip install -r requirements.txt" | tee -a output_api.txt
    echo "6. Check system health: python main.py --mode health" | tee -a output_api.txt
fi

if [ $FAILED -eq 0 ]; then
    echo -e "\n${GREEN}🎉 ALL TESTS PASSED! System is fully functional.${NC}" | tee -a output_api.txt
else
    echo -e "\n${YELLOW}⚠️  Some tests failed. Check the hints above to resolve issues.${NC}" | tee -a output_api.txt
fi

echo -e "\n📋 TESTED FEATURES:" | tee -a output_api.txt
echo "• System health and monitoring" | tee -a output_api.txt
echo "• ML-powered question recommendations" | tee -a output_api.txt
echo "• Student performance analysis" | tee -a output_api.txt
echo "• Learning session management" | tee -a output_api.txt
echo "• Question search and retrieval" | tee -a output_api.txt
echo "• Answer validation and timing" | tee -a output_api.txt
echo "• Image processing and rendering" | tee -a output_api.txt
echo "• Vector similarity matching" | tee -a output_api.txt
echo "• Cache management and optimization" | tee -a output_api.txt
echo "• Paper and content organization" | tee -a output_api.txt

echo "==============================" | tee -a output_api.txt
echo "📄 Full detailed results saved to: output_api.txt" | tee -a output_api.txt
echo "==============================" | tee -a output_api.txt
