# redis_cache_manager.py
import json
import time
from typing import Dict, List, Any, Optional

class RedisCacheManager:
    def __init__(self, redis_client):
        self.redis = redis_client

    def cache_embeddings(self, question_id: str, embeddings_dict: Dict[str, Any]) -> bool:
        """Cache question embeddings"""
        try:
            cache_key = f"embeddings:{question_id}"
            self.redis.hset(cache_key, mapping=embeddings_dict)
            self.redis.expire(cache_key, 3600)  # 1 hour
            return True
        except Exception as e:
            print(f"Error caching embeddings for {question_id}: {e}")
            return False

    def cache_similarity_matrix(self, question_id: str, similar_questions: List[Dict]) -> bool:
        """Cache precomputed similarities"""
        try:
            cache_key = f"similarities:{question_id}"
            self.redis.setex(cache_key, 1800, json.dumps(similar_questions, default=str))  # 30 minutes
            return True
        except Exception as e:
            print(f"Error caching similarities for {question_id}: {e}")
            return False

    def cache_student_profile(self, student_id: str, profile_data: Dict[str, Any]) -> bool:
        """Cache student learning profile"""
        try:
            cache_key = f"profile:{student_id}"
            self.redis.setex(cache_key, 900, json.dumps(profile_data, default=str))  # 15 minutes
            return True
        except Exception as e:
            print(f"Error caching profile for {student_id}: {e}")
            return False

    def get_cached_profile(self, student_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached student profile"""
        try:
            cache_key = f"profile:{student_id}"
            cached_data = self.redis.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
            return None
        except Exception as e:
            print(f"Error retrieving cached profile for {student_id}: {e}")
            return None

    def get_cached_similarities(self, question_id: str) -> Optional[List[Dict]]:
        """Retrieve cached similarities"""
        try:
            cache_key = f"similarities:{question_id}"
            cached_data = self.redis.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
            return None
        except Exception as e:
            print(f"Error retrieving cached similarities for {question_id}: {e}")
            return None

    def invalidate_student_cache(self, student_id: str) -> int:
        """Invalidate all student-related caches"""
        pattern = f"*{student_id}*"
        deleted_count = 0
        try:
            for key in self.redis.scan_iter(match=pattern):
                self.redis.delete(key)
                deleted_count += 1
            return deleted_count
        except Exception as e:
            print(f"Error invalidating cache for {student_id}: {e}")
            return deleted_count

    def cache_recommendation_results(self, student_id: str, objective: str, recommendations: List[Dict], ttl: int = 600) -> bool:
        """Cache recommendation results with TTL"""
        try:
            cache_key = f"recommendations:{student_id}:{objective}"
            self.redis.setex(cache_key, ttl, json.dumps(recommendations, default=str))
            return True
        except Exception as e:
            print(f"Error caching recommendations for {student_id}: {e}")
            return False

    def get_cached_recommendations(self, student_id: str, objective: str) -> Optional[List[Dict]]:
        """Get cached recommendation results"""
        try:
            cache_key = f"recommendations:{student_id}:{objective}"
            cached_data = self.redis.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
            return None
        except Exception as e:
            print(f"Error retrieving cached recommendations for {student_id}: {e}")
            return None