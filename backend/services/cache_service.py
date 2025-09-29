#!/usr/bin/env python3
"""
Cache Service - Advanced caching strategies and cache management

This module handles:
- Intelligent caching strategies with optimized serialization
- Cache invalidation patterns
- Cache warming and precomputation
- Cache analytics and monitoring
- Efficient serialization with automatic compression
"""

import time
from typing import Dict, List, Any, Optional, Type, TypeVar
from datetime import datetime
from psycopg2.extras import RealDictCursor
from data.models import create_service_logger, handle_cache_error, Recommendation
from data.serialization import (
    CacheSerializer, SerializationMethod, create_cache_key,
    serialize_for_cache, deserialize_from_cache
)

T = TypeVar('T')


class CacheService:
    """Advanced caching service with intelligent strategies and optimized serialization"""

    def __init__(self, redis_client, db_manager):
        self.redis = redis_client
        self.db_manager = db_manager
        self.logger = create_service_logger('CacheService')
        self.serializer = CacheSerializer(SerializationMethod.JSON_COMPRESSED)
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'serialization_time': 0,
            'deserialization_time': 0,
            'compression_ratio': []
        }

    def get_cached_recommendations(self, student_id: str, objective: str) -> Optional[List[Recommendation]]:
        """Get cached recommendations for a student and objective with optimized deserialization"""
        try:
            # Use simple key format for consistency
            cache_key = f"recommendations:{student_id}:{objective}"
            cached_data = self.redis.get(cache_key)

            if cached_data:
                start_time = time.time()
                recommendations = deserialize_from_cache(cached_data, List[Recommendation])
                self.cache_stats['deserialization_time'] += time.time() - start_time
                self.cache_stats['hits'] += 1
                return recommendations

            self.cache_stats['misses'] += 1
            return None
        except Exception as e:
            handle_cache_error(self.logger, f"get_cached_recommendations for {student_id}/{objective}", e)
            return None

    def cache_recommendations(self, student_id: str, objective: str, recommendations: List[Recommendation], ttl: int = 1800) -> bool:
        """Cache recommendations with optimized serialization and compression"""
        try:
            # Use simple key format for consistency
            cache_key = f"recommendations:{student_id}:{objective}"

            start_time = time.time()
            serialized_data = serialize_for_cache(recommendations, compress_large=True)
            serialization_time = time.time() - start_time

            # Track compression efficiency
            original_size = len(str(recommendations))
            compressed_size = len(serialized_data)
            compression_ratio = compressed_size / original_size if original_size > 0 else 1.0

            self.cache_stats['serialization_time'] += serialization_time
            self.cache_stats['compression_ratio'].append(compression_ratio)

            # Keep only last 100 compression ratios for memory efficiency
            if len(self.cache_stats['compression_ratio']) > 100:
                self.cache_stats['compression_ratio'] = self.cache_stats['compression_ratio'][-100:]

            self.redis.setex(cache_key, ttl, serialized_data)
            self.cache_stats['sets'] += 1

            self.logger.debug(f"Cached recommendations for {student_id}/{objective}: "
                            f"compression {compression_ratio:.2%}, time {serialization_time:.3f}s")

            return True
        except Exception as e:
            return handle_cache_error(self.logger, f"cache_recommendations for {student_id}/{objective}", e)

    def get_cached_student_history(self, student_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached student history with optimized deserialization"""
        try:
            # Use simple key format for consistency
            cache_key = f"student_history:{student_id}"
            cached_data = self.redis.get(cache_key)

            if cached_data:
                start_time = time.time()
                history = deserialize_from_cache(cached_data)
                self.cache_stats['deserialization_time'] += time.time() - start_time
                self.cache_stats['hits'] += 1
                return history

            self.cache_stats['misses'] += 1
            return None
        except Exception as e:
            handle_cache_error(self.logger, f"get_cached_student_history for {student_id}", e)
            return None

    def cache_student_history(self, student_id: str, history: List[Dict[str, Any]], ttl: int = 3600) -> bool:
        """Cache student history with optimized serialization"""
        try:
            # Use simple key format for consistency
            cache_key = f"student_history:{student_id}"

            start_time = time.time()
            serialized_data = serialize_for_cache(history, compress_large=True)
            self.cache_stats['serialization_time'] += time.time() - start_time

            self.redis.setex(cache_key, ttl, serialized_data)
            self.cache_stats['sets'] += 1
            return True
        except Exception as e:
            handle_cache_error(self.logger, f"cache_student_history for {student_id}", e)
            return False

    def get_cached_enriched_vector(self, student_id: str, objective: str) -> Optional[Any]:
        """Get cached enriched vector with optimized numpy array handling"""
        try:
            # Use simple key format for consistency
            cache_key = f"enriched_vector:{student_id}:{objective}"
            cached_data = self.redis.get(cache_key)

            if cached_data:
                start_time = time.time()
                vector = deserialize_from_cache(cached_data)
                self.cache_stats['deserialization_time'] += time.time() - start_time
                self.cache_stats['hits'] += 1
                return vector

            self.cache_stats['misses'] += 1
            return None
        except Exception as e:
            handle_cache_error(self.logger, f"get_cached_enriched_vector for {student_id}/{objective}", e)
            return None

    def cache_enriched_vector(self, student_id: str, objective: str, vector: Any, ttl: int = 1800) -> bool:
        """Cache enriched vector with optimized numpy array serialization"""
        try:
            # Use simple key format for consistency
            cache_key = f"enriched_vector:{student_id}:{objective}"

            start_time = time.time()
            serialized_data = serialize_for_cache(vector, compress_large=True)
            self.cache_stats['serialization_time'] += time.time() - start_time

            self.redis.setex(cache_key, ttl, serialized_data)
            self.cache_stats['sets'] += 1
            return True
        except Exception as e:
            handle_cache_error(self.logger, f"cache_enriched_vector for {student_id}/{objective}", e)
            return False

    def invalidate_student_cache(self, student_id: str) -> bool:
        """Invalidate all cached data for a student when their history changes"""
        try:
            student_str = str(student_id)
            keys_to_delete = []

            # Find all keys related to this student
            pattern_prefixes = [
                f"student_history:{student_str}",
                f"enriched_vector:{student_str}:*",
                f"recommendations:{student_str}:*"
            ]

            for prefix in pattern_prefixes:
                if "*" in prefix:
                    # Use SCAN to find matching keys
                    for key in self.redis.scan_iter(match=prefix):
                        keys_to_delete.append(key)
                else:
                    # Direct key
                    keys_to_delete.append(prefix)

            # Delete all found keys
            if keys_to_delete:
                deleted = self.redis.delete(*keys_to_delete)
                print(f"🗑️ Invalidated {deleted} cache entries for student {student_id}")
                self.cache_stats['deletes'] += deleted
                return deleted

            return 0
        except Exception as e:
            print(f"Error invalidating student cache: {e}")
            return False

    def get_student_cache_version(self, student_id: str) -> Optional[str]:
        """Get the current cache version for a student (based on last activity)"""
        try:
            cache_key = f"student_version:{student_id}"
            version = self.redis.get(cache_key)
            if version:
                # Handle both string and bytes responses
                if isinstance(version, bytes):
                    return version.decode()
                elif isinstance(version, str):
                    return version
                else:
                    return str(version)
            return None
        except Exception as e:
            print(f"Error getting student cache version: {e}")
            return None

    def set_student_cache_version(self, student_id: str, version: str = None) -> bool:
        """Set a new cache version for a student (auto-generates timestamp if not provided)"""
        try:
            if version is None:
                version = str(time.time())

            cache_key = f"student_version:{student_id}"
            self.redis.set(cache_key, version)
            return True
        except Exception as e:
            print(f"Error setting student cache version: {e}")
            return False

    def is_cache_valid(self, student_id: str, cached_version: str = None) -> bool:
        """Check if cached data is still valid by comparing versions"""
        try:
            current_version = self.get_student_cache_version(student_id)
            if not current_version:
                return False

            if cached_version and cached_version != current_version:
                print(f"🔄 Cache version mismatch for student {student_id}: {cached_version} vs {current_version}")
                return False

            return True
        except Exception as e:
            print(f"Error checking cache validity: {e}")
            return False

    def get_or_compute(self, cache_key: str, compute_function, ttl: int = 3600,
                      target_type: Optional[Type[T]] = None, *args, **kwargs) -> T:
        """Get from cache or compute and cache the result with optimized serialization"""
        try:
            # Try to get from cache
            cached_data = self.redis.get(cache_key)
            if cached_data:
                start_time = time.time()
                result = deserialize_from_cache(cached_data, target_type)
                self.cache_stats['deserialization_time'] += time.time() - start_time
                self.cache_stats['hits'] += 1
                return result

            # Cache miss - compute value
            self.cache_stats['misses'] += 1
            computed_value = compute_function(*args, **kwargs)

            # Cache the computed value
            if computed_value is not None:
                start_time = time.time()
                serialized_data = serialize_for_cache(computed_value, compress_large=True)
                self.cache_stats['serialization_time'] += time.time() - start_time

                self.redis.setex(cache_key, ttl, serialized_data)
                self.cache_stats['sets'] += 1

            return computed_value

        except Exception as e:
            handle_cache_error(self.logger, f"get_or_compute for key {cache_key}", e)
            # Fallback to computing without caching
            return compute_function(*args, **kwargs)

    def warm_recommendation_cache(self, student_ids: List[str] = None, objectives: List[str] = None) -> Dict[str, Any]:
        """Enhanced cache warming with intelligent student selection"""
        if objectives is None:
            objectives = ['balanced', 'coverage', 'efficiency']

        warming_stats = {
            'started_at': time.time(),
            'students_processed': 0,
            'recommendations_cached': 0,
            'errors': [],
            'cache_strategy': 'intelligent'
        }

        try:
            # If no student IDs provided, get active students intelligently
            if student_ids is None:
                student_ids = self._get_active_students_for_warming()
                warming_stats['students_selected'] = len(student_ids)
                print(f"🔥 Selected {len(student_ids)} active students for cache warming")

            from services.recommendation_service import OptimizedRecommendationEngine

            # Initialize recommendation engine with cache service
            rec_engine = OptimizedRecommendationEngine(self.db_manager, cache_service=self, lazy_load=True)

            for student_id in student_ids:
                try:
                    for objective in objectives:
                        # Generate and cache recommendations
                        recommendations = rec_engine.recommend_questions_optimized(
                            student_id=student_id,
                            objective=objective,
                            top_k=10,
                            use_cache=False  # Don't use cache when warming
                        )

                        if recommendations:
                            # Cache with longer TTL for warmed data
                            self.cache_recommendations(student_id, objective, recommendations, ttl=2700)  # 45 minutes
                            warming_stats['recommendations_cached'] += 1

                    warming_stats['students_processed'] += 1

                    # Log progress every 10 students
                    if warming_stats['students_processed'] % 10 == 0:
                        print(f"⏱️ Cache warming progress: {warming_stats['students_processed']}/{len(student_ids)} students")

                except Exception as e:
                    warming_stats['errors'].append(f"Error for student {student_id}: {str(e)}")
                    continue

            warming_stats['duration'] = time.time() - warming_stats['started_at']
            print(f"✨ Cache warming completed: {warming_stats}")
            return warming_stats

        except Exception as e:
            warming_stats['fatal_error'] = str(e)
            return warming_stats

    def precompute_similarities(self, question_ids: List[str], batch_size: int = 100) -> Dict[str, Any]:
        """Precompute and cache similarity matrices for questions"""
        computation_stats = {
            'started_at': time.time(),
            'questions_processed': 0,
            'similarities_cached': 0,
            'errors': []
        }

        try:
            from ml.vector_operations_manager import VectorOperationsManager

            embedding_manager = VectorOperationsManager(self.db_manager, self)

            # Process in batches
            for i in range(0, len(question_ids), batch_size):
                batch = question_ids[i:i + batch_size]

                for question_id in batch:
                    try:
                        # Get question embeddings
                        embeddings = embedding_manager.get_question_embeddings(question_id)
                        if not embeddings:
                            continue

                        # Find similar questions
                        similar_questions = embedding_manager.find_similar_questions_multimodal(
                            openai_embedding=embeddings.get('openai_embedding'),
                            umap_embedding=embeddings.get('umap_embedding'),
                            cluster_vector=embeddings.get('soft_cluster'),
                            top_k=20
                        )

                        # Cache the results with optimized serialization
                        cache_key = f"similarities:{question_id}"
                        serialized_data = serialize_for_cache(similar_questions, compress_large=True)
                        self.redis.setex(cache_key, 3600, serialized_data)  # 1 hour

                        computation_stats['similarities_cached'] += 1
                        computation_stats['questions_processed'] += 1

                    except Exception as e:
                        computation_stats['errors'].append(f"Error for question {question_id}: {str(e)}")
                        continue

            computation_stats['duration'] = time.time() - computation_stats['started_at']
            return computation_stats

        except Exception as e:
            computation_stats['fatal_error'] = str(e)
            return computation_stats

    async def delete_pattern(self, pattern: str) -> int:
        """Delete cache keys matching a pattern"""
        try:
            keys = []
            cursor = 0

            # Use SCAN to find keys matching the pattern
            while True:
                cursor, partial_keys = self.redis.scan(cursor, match=pattern, count=100)
                keys.extend(partial_keys)
                if cursor == 0:
                    break

            # Delete the keys if any were found
            if keys:
                deleted_count = self.redis.delete(*keys)
                self.cache_stats['deletes'] += deleted_count
                return deleted_count

            return 0

        except Exception as e:
            print(f"Error deleting cache pattern {pattern}: {e}")
            return 0

    def intelligent_cache_invalidation(self, student_id: str, action: str = 'question_attempt') -> int:
        """Intelligently invalidate related caches based on user action"""
        invalidated_count = 0

        try:
            patterns_to_invalidate = []

            if action == 'question_attempt':
                # Invalidate recommendation caches for this student
                patterns_to_invalidate.extend([
                    f"recommendations:{student_id}:*",
                    f"profile:{student_id}",
                    f"student_history:{student_id}:*"
                ])

            elif action == 'profile_update':
                # Invalidate profile and related caches
                patterns_to_invalidate.extend([
                    f"profile:{student_id}",
                    f"recommendations:{student_id}:*"
                ])

            elif action == 'system_update':
                # Broader invalidation for system-wide updates
                patterns_to_invalidate.extend([
                    "recommendations:*",
                    "similarities:*"
                ])

            # Execute invalidations
            for pattern in patterns_to_invalidate:
                if '*' in pattern:
                    # Use SCAN for pattern matching
                    keys = []
                    cursor = 0
                    while True:
                        cursor, partial_keys = self.redis.scan(cursor, match=pattern, count=100)
                        keys.extend(partial_keys)
                        if cursor == 0:
                            break

                    if keys:
                        deleted = self.redis.delete(*keys)
                        invalidated_count += deleted
                else:
                    # Direct key deletion
                    if self.redis.delete(pattern):
                        invalidated_count += 1

            self.cache_stats['deletes'] += invalidated_count
            return invalidated_count

        except Exception as e:
            print(f"Error in intelligent cache invalidation: {e}")
            return 0

    def cache_analytics(self) -> Dict[str, Any]:
        """Get cache performance analytics"""
        try:
            analytics = {
                'stats': self.cache_stats.copy(),
                'redis_info': {},
                'key_analysis': {},
                'timestamp': datetime.now().isoformat()
            }

            # Calculate hit rate
            total_operations = self.cache_stats['hits'] + self.cache_stats['misses']
            if total_operations > 0:
                analytics['hit_rate'] = self.cache_stats['hits'] / total_operations
            else:
                analytics['hit_rate'] = 0

            # Redis memory info
            redis_info = self.redis.info('memory')
            analytics['redis_info'] = {
                'used_memory': redis_info.get('used_memory'),
                'used_memory_human': redis_info.get('used_memory_human'),
                'maxmemory': redis_info.get('maxmemory'),
                'memory_usage_ratio': redis_info.get('used_memory') / redis_info.get('maxmemory') if redis_info.get('maxmemory') else 0
            }

            # Key count analysis
            analytics['key_analysis'] = self._analyze_cache_keys()

            return analytics

        except Exception as e:
            print(f"Error getting cache analytics: {e}")
            return {'error': str(e)}

    def optimize_cache_memory(self, target_memory_usage: float = 0.8) -> Dict[str, Any]:
        """Optimize cache memory usage by cleaning up old/unused keys"""
        optimization_stats = {
            'started_at': time.time(),
            'keys_before': 0,
            'keys_after': 0,
            'memory_freed': 0,
            'actions_taken': []
        }

        try:
            # Get current memory usage
            redis_info = self.redis.info('memory')
            current_usage = redis_info.get('used_memory', 0)
            max_memory = redis_info.get('maxmemory', 0)

            if max_memory == 0:
                return {'error': 'Cannot determine max memory'}

            current_ratio = current_usage / max_memory
            optimization_stats['memory_before'] = current_usage
            optimization_stats['usage_ratio_before'] = current_ratio

            if current_ratio <= target_memory_usage:
                optimization_stats['no_action_needed'] = True
                return optimization_stats

            # Get all keys for analysis
            all_keys = []
            cursor = 0
            while True:
                cursor, keys = self.redis.scan(cursor, count=1000)
                all_keys.extend(keys)
                if cursor == 0:
                    break

            optimization_stats['keys_before'] = len(all_keys)

            # Analyze and prioritize keys for deletion
            keys_to_delete = self._prioritize_keys_for_deletion(all_keys)

            # Delete keys until we reach target memory usage
            deleted_count = 0
            for key in keys_to_delete:
                if self.redis.delete(key):
                    deleted_count += 1

                # Check if we've reached target
                if deleted_count % 100 == 0:  # Check every 100 deletions
                    current_info = self.redis.info('memory')
                    current_ratio = current_info.get('used_memory', 0) / max_memory
                    if current_ratio <= target_memory_usage:
                        break

            # Final stats
            final_info = self.redis.info('memory')
            optimization_stats['keys_after'] = optimization_stats['keys_before'] - deleted_count
            optimization_stats['memory_after'] = final_info.get('used_memory', 0)
            optimization_stats['memory_freed'] = optimization_stats['memory_before'] - optimization_stats['memory_after']
            optimization_stats['usage_ratio_after'] = final_info.get('used_memory', 0) / max_memory
            optimization_stats['keys_deleted'] = deleted_count
            optimization_stats['duration'] = time.time() - optimization_stats['started_at']

            return optimization_stats

        except Exception as e:
            optimization_stats['error'] = str(e)
            return optimization_stats

    def _analyze_cache_keys(self) -> Dict[str, Any]:
        """Analyze cache keys by type and usage patterns"""
        try:
            key_types = {}
            cursor = 0
            total_keys = 0

            while True:
                cursor, keys = self.redis.scan(cursor, count=1000)

                for key in keys:
                    total_keys += 1
                    key_type = key.split(':')[0] if ':' in key else 'unknown'

                    if key_type not in key_types:
                        key_types[key_type] = {'count': 0, 'total_memory': 0}

                    key_types[key_type]['count'] += 1

                    # Get memory usage for this key (approximate)
                    try:
                        memory_usage = self.redis.memory_usage(key)
                        if memory_usage:
                            key_types[key_type]['total_memory'] += memory_usage
                    except Exception:
                        pass  # memory_usage command might not be available

                if cursor == 0:
                    break

            return {
                'total_keys': total_keys,
                'by_type': key_types
            }

        except Exception as e:
            print(f"Error analyzing cache keys: {e}")
            return {}

    def _prioritize_keys_for_deletion(self, keys: List[str]) -> List[str]:
        """Prioritize keys for deletion based on various factors"""
        key_priorities = []

        for key in keys:
            priority_score = 0

            try:
                # Check TTL
                ttl = self.redis.ttl(key)
                if ttl > 0:
                    # Keys with shorter TTL get higher priority for deletion
                    priority_score += (3600 - ttl) / 3600  # Normalize to 0-1
                elif ttl == -1:
                    # Keys without TTL get lower priority
                    priority_score -= 0.5

                # Key type priority
                key_type = key.split(':')[0] if ':' in key else 'unknown'
                if key_type in ['temp', 'session']:
                    priority_score += 0.8
                elif key_type in ['similarities', 'embeddings']:
                    priority_score += 0.3
                elif key_type in ['recommendations', 'profile']:
                    priority_score += 0.1

                # Key size (if available)
                try:
                    memory_usage = self.redis.memory_usage(key)
                    if memory_usage and memory_usage > 10000:  # Larger than 10KB
                        priority_score += 0.2
                except Exception:
                    pass

                key_priorities.append((key, priority_score))

            except Exception:
                # If we can't analyze the key, give it medium priority
                key_priorities.append((key, 0.5))

        # Sort by priority score (highest first)
        key_priorities.sort(key=lambda x: x[1], reverse=True)

        return [key for key, _ in key_priorities]

    def create_cache_key(self, key_type: str, *identifiers, **params) -> str:
        """Create a standardized cache key"""
        base_key = f"{key_type}:{':'.join(str(id) for id in identifiers)}"

        if params:
            # Create deterministic hash of parameters
            # Use optimized serialization for parameter hashing
            import hashlib
            param_bytes = serialize_for_cache(params, compress_large=False)
            param_hash = hashlib.md5(param_bytes).hexdigest()[:8]
            base_key += f":{param_hash}"

        return base_key

    def _get_active_students_for_warming(self, limit: int = 50) -> List[str]:
        """Get list of active students for intelligent cache warming"""
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)

                # Get students with recent activity (last 24-48 hours)
                query = """
                SELECT DISTINCT spe.student_id, COUNT(*) as recent_activity
                FROM student_question_history sqh
                JOIN student_paper_enrollments spe ON sqh.enrollment_id = spe.enrollment_id
                WHERE sqh.timestamp >= NOW() - INTERVAL '48 hours'
                GROUP BY spe.student_id
                HAVING COUNT(*) >= 2  -- At least 2 attempts
                ORDER BY recent_activity DESC, RANDOM()
                LIMIT %s
                """

                cursor.execute(query, (limit,))
                results = cursor.fetchall()

                active_students = [str(row['student_id']) for row in results]

                # If we don't have enough active students, get some random ones
                if len(active_students) < limit // 2:
                    cursor.execute("""
                        SELECT DISTINCT spe.student_id
                        FROM student_paper_enrollments spe
                        ORDER BY RANDOM()
                        LIMIT %s
                    """, (limit - len(active_students),))

                    additional_students = [str(row['student_id']) for row in cursor.fetchall()]
                    active_students.extend(additional_students)

                return active_students[:limit]

        except Exception as e:
            print(f"⚠️ Error getting active students: {e}")
            # Fallback to a few default student IDs
            return ['1', '2', '3', '4', '5']

    def get_cache_statistics(self) -> Dict[str, Any]:
        """Get current cache statistics including serialization performance"""
        stats = self.cache_stats.copy()

        # Calculate averages for better insights
        if len(stats['compression_ratio']) > 0:
            stats['avg_compression_ratio'] = sum(stats['compression_ratio']) / len(stats['compression_ratio'])
            stats['best_compression_ratio'] = min(stats['compression_ratio'])
        else:
            stats['avg_compression_ratio'] = 1.0
            stats['best_compression_ratio'] = 1.0

        # Calculate serialization efficiency
        total_operations = stats['hits'] + stats['misses']
        if total_operations > 0:
            stats['avg_serialization_time'] = stats['serialization_time'] / stats['sets'] if stats['sets'] > 0 else 0
            stats['avg_deserialization_time'] = stats['deserialization_time'] / stats['hits'] if stats['hits'] > 0 else 0

        return {
            'local_stats': stats,
            'redis_stats': self.redis.info('stats'),
            'memory_info': self.redis.info('memory'),
            'keyspace_info': self.redis.info('keyspace'),
            'serialization_performance': {
                'total_serialization_time': stats['serialization_time'],
                'total_deserialization_time': stats['deserialization_time'],
                'avg_serialization_time': stats.get('avg_serialization_time', 0),
                'avg_deserialization_time': stats.get('avg_deserialization_time', 0),
                'compression_efficiency': {
                    'avg_ratio': stats['avg_compression_ratio'],
                    'best_ratio': stats['best_compression_ratio'],
                    'total_samples': len(stats['compression_ratio'])
                }
            }
        }
