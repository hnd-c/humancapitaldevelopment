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
  -d '{"student_id": "2", "objective": "coverage", "top_k": 10}' | jq .

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

echo -e "\n📝 Question Management"
echo "----------------------------"
echo "11. Random questions:"
curl -s "$BASE_URL/questions/random?count=3" | jq .

echo -e "\n12. Search mathematics:"
curl -s "$BASE_URL/questions/search?q=mathematics&limit=5" | jq .

echo -e "\n13. Search algebra:"
curl -s "$BASE_URL/questions/search?q=algebra&limit=3" | jq .

echo -e "\n📋 Paper Management"
echo "----------------------------"
echo "14. All papers (first 3):"
curl -s "$BASE_URL/papers" | jq '.papers[:3]'

echo -e "\n🔧 Cache Management"
echo "----------------------------"
echo "15. Cache invalidation:"
curl -s -X POST "$BASE_URL/cache/invalidate" | jq .

echo -e "\n✅ Testing Complete!"
