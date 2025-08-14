#!/usr/bin/env python3
"""
Maintenance Script - System maintenance and housekeeping tasks

This module handles:
- Database cleanup and optimization
- Cache management and cleanup
- Log file rotation and cleanup
- Performance monitoring and alerts
- Backup management
"""

import os
import sys
import time
import shutil
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from config.environments import load_config_for_environment
from data.database_manager import DatabaseManager
from services.cache_service import CacheService


class MaintenanceManager:
    """Manages system maintenance tasks"""

    def __init__(self, environment: str = "development"):
        self.environment = environment
        self.config = load_config_for_environment(environment)
        self.start_time = time.time()

        # Initialize components
        self.db_manager = DatabaseManager(
            self.config.get_database_config(),
            self.config.get_redis_config()
        )
        self.cache_service = CacheService(self.db_manager.redis_client, self.db_manager)

        print(f"🔧 Starting maintenance for {environment} environment")
        print("=" * 60)

    def run_full_maintenance(self) -> Dict[str, Any]:
        """Run complete maintenance routine"""
        maintenance_report = {
            'started_at': datetime.now().isoformat(),
            'environment': self.environment,
            'tasks_completed': [],
            'tasks_failed': [],
            'summary': {}
        }

        maintenance_tasks = [
            ('database_cleanup', self.cleanup_database),
            ('cache_optimization', self.optimize_cache),
            ('log_rotation', self.rotate_logs),
            ('backup_cleanup', self.cleanup_old_backups),
            ('performance_analysis', self.analyze_performance),
            ('system_health_check', self.system_health_check)
        ]

        for task_name, task_function in maintenance_tasks:
            try:
                print(f"\n🔄 Running {task_name}...")
                result = task_function()
                maintenance_report['tasks_completed'].append(task_name)
                maintenance_report['summary'][task_name] = result
                print(f"✅ {task_name} completed")

            except Exception as e:
                print(f"❌ {task_name} failed: {e}")
                maintenance_report['tasks_failed'].append({
                    'task': task_name,
                    'error': str(e)
                })

        maintenance_report['duration'] = time.time() - self.start_time
        maintenance_report['completed_at'] = datetime.now().isoformat()

        self._generate_maintenance_report(maintenance_report)
        return maintenance_report

    def cleanup_database(self) -> Dict[str, Any]:
        """Clean up database - remove old data, optimize tables"""
        cleanup_stats = {
            'old_records_removed': 0,
            'tables_optimized': 0,
            'space_freed_mb': 0
        }

        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor()

                # Clean up old performance metrics (older than retention period)
                retention_days = self.config.performance.metrics_retention_days
                cutoff_date = datetime.now() - timedelta(days=retention_days)

                # Example cleanup queries (adjust based on your schema)
                cleanup_queries = [
                    # Clean up old API request logs
                    ("DELETE FROM api_request_logs WHERE created_at < %s", cutoff_date),

                    # Clean up old cache entries metadata
                    ("DELETE FROM cache_metadata WHERE created_at < %s", cutoff_date),

                    # Clean up old error logs
                    ("DELETE FROM error_logs WHERE created_at < %s", cutoff_date)
                ]

                for query, param in cleanup_queries:
                    try:
                        cursor.execute(query, (param,))
                        rows_affected = cursor.rowcount
                        cleanup_stats['old_records_removed'] += rows_affected
                        print(f"   📊 Removed {rows_affected} old records")
                    except Exception as e:
                        print(f"   ⚠️  Query failed: {e}")

                conn.commit()

                # Optimize tables (PostgreSQL VACUUM)
                tables_to_optimize = [
                    'student_question_history',
                    'questions',
                    'students',
                    'api_request_logs'
                ]

                for table in tables_to_optimize:
                    try:
                        cursor.execute(f"VACUUM ANALYZE {table}")
                        cleanup_stats['tables_optimized'] += 1
                        print(f"   🔧 Optimized table: {table}")
                    except Exception as e:
                        print(f"   ⚠️  Failed to optimize {table}: {e}")

                # Get database size information
                cursor.execute("""
                    SELECT pg_size_pretty(pg_database_size(current_database())) as db_size,
                           pg_database_size(current_database()) as db_size_bytes
                """)
                size_info = cursor.fetchone()
                cleanup_stats['current_db_size'] = size_info[0]
                cleanup_stats['db_size_bytes'] = size_info[1]

        except Exception as e:
            print(f"❌ Database cleanup failed: {e}")
            cleanup_stats['error'] = str(e)

        return cleanup_stats

    def optimize_cache(self) -> Dict[str, Any]:
        """Optimize cache - remove stale entries, optimize memory usage"""
        optimization_stats = {
            'keys_before': 0,
            'keys_after': 0,
            'memory_freed_mb': 0,
            'optimization_actions': []
        }

        try:
            # Get cache analytics
            cache_analytics = self.cache_service.cache_analytics()
            optimization_stats['cache_analytics'] = cache_analytics

            # Optimize memory usage
            optimization_result = self.cache_service.optimize_cache_memory(
                target_memory_usage=self.config.cache.max_memory_usage_ratio
            )
            optimization_stats.update(optimization_result)

            # Warm up important caches if enabled
            if self.config.cache.enable_cache_warming:
                # Get list of active students for cache warming
                active_students = self._get_active_students(limit=100)

                if active_students:
                    warming_result = self.cache_service.warm_recommendation_cache(
                        student_ids=active_students,
                        objectives=['balanced', 'coverage']
                    )
                    optimization_stats['cache_warming'] = warming_result

            # Calculate memory freed
            if 'memory_before' in optimization_stats and 'memory_after' in optimization_stats:
                memory_freed_bytes = optimization_stats['memory_before'] - optimization_stats['memory_after']
                optimization_stats['memory_freed_mb'] = memory_freed_bytes / (1024 * 1024)

        except Exception as e:
            print(f"❌ Cache optimization failed: {e}")
            optimization_stats['error'] = str(e)

        return optimization_stats

    def rotate_logs(self) -> Dict[str, Any]:
        """Rotate and cleanup log files"""
        rotation_stats = {
            'files_rotated': 0,
            'files_deleted': 0,
            'space_freed_mb': 0
        }

        try:
            logs_path = self.config.logs_path
            if not logs_path.exists():
                logs_path.mkdir(parents=True, exist_ok=True)
                return rotation_stats

            # Find log files
            log_files = list(logs_path.glob("*.log"))

            for log_file in log_files:
                try:
                    # Get file stats
                    file_stats = log_file.stat()
                    file_age_days = (time.time() - file_stats.st_mtime) / 86400
                    file_size_mb = file_stats.st_size / (1024 * 1024)

                    # Rotate if file is large or old
                    if file_size_mb > 100 or file_age_days > 7:
                        # Create rotated filename with timestamp
                        timestamp = datetime.fromtimestamp(file_stats.st_mtime).strftime("%Y%m%d_%H%M%S")
                        rotated_name = f"{log_file.stem}_{timestamp}{log_file.suffix}"
                        rotated_path = logs_path / rotated_name

                        # Rotate the file
                        shutil.move(log_file, rotated_path)
                        rotation_stats['files_rotated'] += 1

                        # Compress rotated file
                        if shutil.which('gzip'):
                            os.system(f"gzip {rotated_path}")
                            rotated_path = Path(str(rotated_path) + '.gz')

                        print(f"   📋 Rotated log file: {log_file.name}")

                    # Delete very old rotated files
                    if file_age_days > 30:
                        rotation_stats['space_freed_mb'] += file_size_mb
                        log_file.unlink()
                        rotation_stats['files_deleted'] += 1
                        print(f"   🗑️  Deleted old log file: {log_file.name}")

                except Exception as e:
                    print(f"   ⚠️  Failed to process {log_file}: {e}")

        except Exception as e:
            print(f"❌ Log rotation failed: {e}")
            rotation_stats['error'] = str(e)

        return rotation_stats

    def cleanup_old_backups(self) -> Dict[str, Any]:
        """Clean up old backup files"""
        cleanup_stats = {
            'backups_deleted': 0,
            'space_freed_mb': 0,
            'backups_remaining': 0
        }

        try:
            backup_path = Path("backups")
            if not backup_path.exists():
                return cleanup_stats

            # Find backup directories/files
            backup_items = list(backup_path.iterdir())

            # Sort by modification time
            backup_items.sort(key=lambda x: x.stat().st_mtime, reverse=True)

            # Keep only the last N backups (e.g., 10)
            max_backups = 10

            for i, backup_item in enumerate(backup_items):
                if i >= max_backups:
                    try:
                        if backup_item.is_dir():
                            # Calculate directory size
                            total_size = sum(f.stat().st_size for f in backup_item.rglob('*') if f.is_file())
                            cleanup_stats['space_freed_mb'] += total_size / (1024 * 1024)

                            shutil.rmtree(backup_item)
                        else:
                            cleanup_stats['space_freed_mb'] += backup_item.stat().st_size / (1024 * 1024)
                            backup_item.unlink()

                        cleanup_stats['backups_deleted'] += 1
                        print(f"   🗑️  Deleted old backup: {backup_item.name}")

                    except Exception as e:
                        print(f"   ⚠️  Failed to delete backup {backup_item}: {e}")
                else:
                    cleanup_stats['backups_remaining'] += 1

        except Exception as e:
            print(f"❌ Backup cleanup failed: {e}")
            cleanup_stats['error'] = str(e)

        return cleanup_stats

    def analyze_performance(self) -> Dict[str, Any]:
        """Analyze system performance and generate recommendations"""
        performance_stats = {
            'database_performance': {},
            'cache_performance': {},
            'recommendations': []
        }

        try:
            # Database performance analysis
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor()

                # Query performance stats
                cursor.execute("""
                    SELECT schemaname, tablename, n_tup_ins, n_tup_upd, n_tup_del,
                           n_live_tup, n_dead_tup, last_vacuum, last_analyze
                    FROM pg_stat_user_tables
                    ORDER BY n_live_tup DESC
                    LIMIT 10
                """)

                table_stats = cursor.fetchall()
                performance_stats['database_performance']['table_stats'] = table_stats

                # Index usage stats
                cursor.execute("""
                    SELECT schemaname, tablename, indexname, idx_tup_read, idx_tup_fetch
                    FROM pg_stat_user_indexes
                    WHERE idx_tup_read > 0
                    ORDER BY idx_tup_read DESC
                    LIMIT 10
                """)

                index_stats = cursor.fetchall()
                performance_stats['database_performance']['index_stats'] = index_stats

            # Cache performance analysis
            cache_analytics = self.cache_service.cache_analytics()
            performance_stats['cache_performance'] = cache_analytics

            # Generate recommendations
            recommendations = []

            # Check cache hit rate
            if cache_analytics.get('hit_rate', 0) < 0.7:
                recommendations.append("Consider increasing cache TTL or warming more caches")

            # Check memory usage
            memory_usage = cache_analytics.get('redis_info', {}).get('memory_usage_ratio', 0)
            if memory_usage > 0.9:
                recommendations.append("Redis memory usage is high, consider optimization")

            # Check database performance
            if table_stats:
                for stat in table_stats[:3]:  # Check top 3 tables
                    if stat[6] and stat[6] > 1000:  # High dead tuples
                        recommendations.append(f"Table {stat[1]} needs vacuum - high dead tuple count")

            performance_stats['recommendations'] = recommendations

        except Exception as e:
            print(f"❌ Performance analysis failed: {e}")
            performance_stats['error'] = str(e)

        return performance_stats

    def system_health_check(self) -> Dict[str, Any]:
        """Perform comprehensive system health check"""
        health_stats = {
            'database_health': 'unknown',
            'redis_health': 'unknown',
            'disk_usage': {},
            'system_load': {}
        }

        try:
            # Database health
            try:
                with self.db_manager.get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
                health_stats['database_health'] = 'healthy'
            except Exception as e:
                health_stats['database_health'] = f'unhealthy: {e}'

            # Redis health
            try:
                self.db_manager.redis_client.ping()
                health_stats['redis_health'] = 'healthy'
            except Exception as e:
                health_stats['redis_health'] = f'unhealthy: {e}'

            # Disk usage
            try:
                disk_usage = shutil.disk_usage('.')
                health_stats['disk_usage'] = {
                    'total_gb': disk_usage.total / (1024**3),
                    'used_gb': disk_usage.used / (1024**3),
                    'free_gb': disk_usage.free / (1024**3),
                    'usage_percent': (disk_usage.used / disk_usage.total) * 100
                }
            except Exception as e:
                health_stats['disk_usage'] = {'error': str(e)}

            # System load (if available)
            try:
                if hasattr(os, 'getloadavg'):
                    load_avg = os.getloadavg()
                    health_stats['system_load'] = {
                        '1min': load_avg[0],
                        '5min': load_avg[1],
                        '15min': load_avg[2]
                    }
            except Exception as e:
                health_stats['system_load'] = {'error': str(e)}

        except Exception as e:
            print(f"❌ Health check failed: {e}")
            health_stats['error'] = str(e)

        return health_stats

    def _get_active_students(self, limit: int = 100) -> List[str]:
        """Get list of recently active students for cache warming"""
        try:
            with self.db_manager.get_db_connection() as conn:
                cursor = conn.cursor()

                # Get students who have been active in the last 7 days
                cursor.execute("""
                    SELECT DISTINCT spe.student_id
                    FROM student_question_history sqh
                    JOIN student_paper_enrollments spe ON sqh.enrollment_id = spe.enrollment_id
                    WHERE sqh.timestamp >= CURRENT_DATE - INTERVAL '7 days'
                    ORDER BY MAX(sqh.timestamp) DESC
                    LIMIT %s
                """, (limit,))

                return [str(row[0]) for row in cursor.fetchall()]

        except Exception as e:
            print(f"Error getting active students: {e}")
            return []

    def _generate_maintenance_report(self, report: Dict[str, Any]):
        """Generate maintenance report file"""
        try:
            reports_dir = Path("maintenance_reports")
            reports_dir.mkdir(exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = reports_dir / f"maintenance_report_{timestamp}.json"

            import json
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2, default=str)

            print(f"📋 Maintenance report saved to: {report_file}")

        except Exception as e:
            print(f"⚠️  Failed to save maintenance report: {e}")


def main():
    """Main maintenance script"""
    parser = argparse.ArgumentParser(description="System Maintenance Manager")
    parser.add_argument(
        "--environment",
        default="development",
        help="Environment to run maintenance for"
    )
    parser.add_argument(
        "--task",
        choices=['database', 'cache', 'logs', 'backups', 'performance', 'health'],
        help="Run specific maintenance task"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )

    args = parser.parse_args()

    try:
        maintenance_manager = MaintenanceManager(args.environment)

        if args.task:
            # Run specific task
            task_methods = {
                'database': maintenance_manager.cleanup_database,
                'cache': maintenance_manager.optimize_cache,
                'logs': maintenance_manager.rotate_logs,
                'backups': maintenance_manager.cleanup_old_backups,
                'performance': maintenance_manager.analyze_performance,
                'health': maintenance_manager.system_health_check
            }

            result = task_methods[args.task]()
            print(f"\n📊 Task '{args.task}' completed:")
            print(json.dumps(result, indent=2, default=str))
        else:
            # Run full maintenance
            report = maintenance_manager.run_full_maintenance()

            if report['tasks_failed']:
                print(f"\n⚠️  Some tasks failed: {report['tasks_failed']}")
                return 1
            else:
                print(f"\n🎉 All maintenance tasks completed successfully!")
                return 0

    except KeyboardInterrupt:
        print("\n🛑 Maintenance interrupted by user")
        return 1
    except Exception as e:
        print(f"❌ Maintenance failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
