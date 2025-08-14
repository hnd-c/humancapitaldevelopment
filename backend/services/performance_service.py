import time
import json
from typing import Dict, List, Optional

class PerformanceMonitor:
    def __init__(self, redis_client):
        self.redis = redis_client

    def track_recommendation_performance(self, student_id: str, recommendations: List[Dict], response_time: float):
        """Track recommendation system performance"""
        timestamp = int(time.time())

        # Store performance metrics
        self.redis.zadd(f"response_times:{student_id}", {timestamp: response_time})
        self.redis.zadd("global_response_times", {f"{student_id}:{timestamp}": response_time})

        # Keep only last 1000 entries
        self.redis.zremrangebyrank(f"response_times:{student_id}", 0, -1001)

    def get_cache_hit_rate(self) -> float:
        """Monitor cache effectiveness"""
        info = self.redis.info()
        hits = info.get('keyspace_hits', 0)
        misses = info.get('keyspace_misses', 0)
        total = hits + misses
        return hits / total if total > 0 else 0

    def get_avg_response_time(self, student_id: str, last_n: int = 100) -> Optional[float]:
        """Get average response time for a student"""
        times = self.redis.zrevrange(f"response_times:{student_id}", 0, last_n-1, withscores=True)
        if not times:
            return None

        total_time = sum(score for _, score in times)
        return total_time / len(times)

    def get_system_metrics(self) -> Dict:
        """Get comprehensive system metrics"""
        return {
            'cache_hit_rate': self.get_cache_hit_rate(),
            'total_recommendations': self.redis.zcard('global_response_times'),
            'avg_global_response_time': self._get_global_avg_response_time(),
            'active_students': len(self.redis.keys('response_times:*')),
            'redis_memory_usage': self.redis.info().get('used_memory_human', 'Unknown')
        }

    def _get_global_avg_response_time(self) -> Optional[float]:
        """Get global average response time"""
        times = self.redis.zrevrange('global_response_times', 0, 999, withscores=True)
        if not times:
            return None

        total_time = sum(score for _, score in times)
        return total_time / len(times)