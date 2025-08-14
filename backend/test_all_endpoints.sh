#!/bin/bash

echo "🚀 Testing All API Endpoints"
echo "=============================="

BASE_URL="http://localhost:8000"

echo "📊 System & Health Endpoints"
echo "----------------------------"
echo "1. Root endpoint:"
curl -s "$BASE_URL/" | jq .

echo -e "\n2. Health check:"
curl -s "$BASE_URL/health" | jq .

echo -e "\n3. System analytics:"
curl -s "$BASE_URL/analytics/system" | jq .

echo -e "\n🎯 Recommendation Endpoints"
echo "----------------------------"
echo "4. Balanced recommendations:"
curl -s -X POST "$BASE_URL/recommendations" \
  -H "Content-Type: application/json" \
  -d '{"student_id": "1", "objective": "balanced", "top_k": 5}' | jq .

echo -e "\n5. Coverage recommendations:"
curl -s -X POST "$BASE_URL/recommendations" \
  -H "Content-Type: application/json" \
  -d '{"student_id": "2", "objective": "coverage", "top_k": 3}' | jq .

echo -e "\n6. Efficiency recommendations:"
curl -s -X POST "$BASE_URL/recommendations" \
  -H "Content-Type: application/json" \
  -d '{"student_id": "3", "objective": "efficiency", "top_k": 3}' | jq .

echo -e "\n👨‍🎓 Student Management"
echo "----------------------------"
echo "7. Student 1 performance:"
curl -s "$BASE_URL/student/1/performance" | jq .

echo -e "\n8. Student 2 performance:"
curl -s "$BASE_URL/student/2/performance" | jq .

echo -e "\n9. Student 1 history:"
curl -s "$BASE_URL/student/1/history" | jq .

echo -e "\n10. Student 2 history (limited):"
curl -s "$BASE_URL/student/2/history?limit=10" | jq .

echo -e "\n🎓 Student Learning Workflow"
echo "----------------------------"
echo "11. Start learning session for student 20:"
SESSION_RESPONSE=$(curl -s -X POST "$BASE_URL/student/20/start-session" \
  -H "Content-Type: application/json" \
  -d '{"student_id": "20", "objective": "balanced", "session_type": "practice", "target_questions": 3}')
echo "$SESSION_RESPONSE" | jq .
SESSION_ID=$(echo "$SESSION_RESPONSE" | jq -r '.session_id')
FIRST_QUESTION=$(echo "$SESSION_RESPONSE" | jq -r '.recommendations[0].question_id')

echo -e "\n12. Start question attempt for $FIRST_QUESTION:"
ATTEMPT_RESPONSE=$(curl -s -X POST "$BASE_URL/student/20/attempt-question" \
  -H "Content-Type: application/json" \
  -d "{\"student_id\": \"20\", \"question_id\": \"$FIRST_QUESTION\"}")
echo "$ATTEMPT_RESPONSE" | jq .
ATTEMPT_ID=$(echo "$ATTEMPT_RESPONSE" | jq -r '.attempt_id')

echo -e "\n13. Submit answer with auto-validation:"
curl -s -X POST "$BASE_URL/student/20/submit-answer" \
  -H "Content-Type: application/json" \
  -d "{\"attempt_id\": \"$ATTEMPT_ID\", \"student_id\": \"20\", \"question_id\": \"$FIRST_QUESTION\", \"selected_option\": \"C\", \"confidence_level\": 0.8}" | jq .

echo -e "\n14. Get session progress:"
curl -s "$BASE_URL/student/20/session/$SESSION_ID/progress" | jq .

echo -e "\n15. Get student sessions:"
curl -s "$BASE_URL/student/20/sessions" | jq .

echo -e "\n📝 Question Management"
echo "----------------------------"
echo "16. Random questions:"
curl -s "$BASE_URL/questions/random?count=3" | jq .

echo -e "\n17. Search mathematics:"
curl -s "$BASE_URL/questions/search?q=mathematics&limit=5" | jq .

echo -e "\n18. Search algebra:"
curl -s "$BASE_URL/questions/search?q=algebra&limit=3" | jq .

echo -e "\n19. Question details:"
curl -s "$BASE_URL/questions/$FIRST_QUESTION" | jq .

echo -e "\n🤖 Answer Validation & Timing"
echo "----------------------------"
echo "20. Question timing stats:"
curl -s "$BASE_URL/questions/$FIRST_QUESTION/timing-stats" | jq .

echo -e "\n21. Validate correct answer:"
curl -s -X POST "$BASE_URL/questions/$FIRST_QUESTION/validate-answer" \
  -H "Content-Type: application/json" \
  -d '{"student_answer": "C", "answer_type": "multiple_choice"}' | jq .

echo -e "\n22. Validate incorrect answer:"
curl -s -X POST "$BASE_URL/questions/$FIRST_QUESTION/validate-answer" \
  -H "Content-Type: application/json" \
  -d '{"student_answer": "A", "answer_type": "multiple_choice"}' | jq .

echo -e "\n23. Get answer key (admin endpoint):"
curl -s "$BASE_URL/questions/$FIRST_QUESTION/answer-key" | jq .

echo -e "\n📋 Paper Management"
echo "----------------------------"
echo "24. All papers (first 3):"
curl -s "$BASE_URL/papers" | jq '.papers[:3]'

echo -e "\n25. Questions by paper:"
curl -s "$BASE_URL/papers/9702_w22_qp_12/questions" | jq .

echo -e "\n🖼️ Question Rendering"
echo "----------------------------"
echo "26. Question image base64:"
curl -s "$BASE_URL/questions/$FIRST_QUESTION/image" | jq '.has_image'

echo -e "\n27. Question summary:"
curl -s "$BASE_URL/questions/$FIRST_QUESTION/summary" | jq .

echo -e "\n🔍 Similar Questions"
echo "----------------------------"
echo "28. Similar questions:"
curl -s "$BASE_URL/questions/$FIRST_QUESTION/similar?limit=3" | jq .

echo -e "\n🔧 Cache Management"
echo "----------------------------"
echo "29. Student-specific cache invalidation:"
curl -s -X POST "$BASE_URL/cache/invalidate?student_id=20" | jq .

echo -e "\n30. Full cache invalidation:"
curl -s -X POST "$BASE_URL/cache/invalidate" | jq .

echo -e "\n📊 Performance Testing"
echo "----------------------------"
echo "31. Fresh recommendations after cache invalidation:"
curl -s -X POST "$BASE_URL/recommendations" \
  -H "Content-Type: application/json" \
  -d '{"student_id": "20", "objective": "balanced", "top_k": 3}' | jq '.cache_hit, .response_time_ms'

echo -e "\n32. Cached recommendations (should be faster):"
curl -s -X POST "$BASE_URL/recommendations" \
  -H "Content-Type: application/json" \
  -d '{"student_id": "20", "objective": "balanced", "top_k": 3}' | jq '.cache_hit, .response_time_ms'

echo -e "\n✅ Testing Complete!"
echo "=============================="
echo "📈 Summary:"
echo "• Tested 32 endpoints covering all features"
echo "• Student workflow: Session → Attempt → Submit → Validate"
echo "• ML recommendations with caching"
echo "• Answer validation and timing"
echo "• Performance monitoring"
echo "=============================="
