#!/usr/bin/env python3
"""
Cache Serialization Performance Demo

This script demonstrates the performance improvements of the new
centralized cache serialization system versus the old manual approach.
"""

import time
import json
import sys
import os
from dataclasses import dataclass, asdict
from typing import List
import numpy as np

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.serialization import CacheSerializer, SerializationMethod
from data.models import Recommendation, Student


@dataclass
class TestData:
    """Sample data structure for testing"""
    id: str
    values: List[float]
    metadata: dict
    timestamp: float


def create_test_recommendations(count: int = 100) -> List[Recommendation]:
    """Create test recommendation data"""
    recommendations = []
    for i in range(count):
        rec = Recommendation(
            question_id=f"test_question_{i}",
            internal_question_id=i,
            paper_id=1001 + (i % 50),
            weighted_score=0.85 + (i % 10) * 0.01,
            dominant_cluster=i % 5,
            similarity_score=0.7 + (i % 20) * 0.01,
            combined_score=0.8 + (i % 15) * 0.01,
            reasoning=f"This question is recommended because it matches cluster {i % 5} patterns"
        )
        recommendations.append(rec)
    return recommendations


def create_test_complex_data(count: int = 50) -> List[TestData]:
    """Create complex test data with numpy arrays"""
    test_data = []
    for i in range(count):
        data = TestData(
            id=f"complex_data_{i}",
            values=np.random.random(100).tolist(),  # Large list of floats
            metadata={
                "type": "embedding",
                "model": "test_model",
                "dimensions": 100,
                "created_at": time.time(),
                "tags": [f"tag_{j}" for j in range(10)]
            },
            timestamp=time.time()
        )
        test_data.append(data)
    return test_data


def benchmark_old_approach(data):
    """Benchmark the old manual JSON serialization approach"""
    start_time = time.time()

    # Simulate old approach - manual dict conversion
    serialized_data = []
    for item in data:
        if hasattr(item, '__dataclass_fields__'):
            item_dict = asdict(item)
        else:
            item_dict = item.__dict__
        serialized_data.append(item_dict)

    # JSON serialization
    json_data = json.dumps(serialized_data, default=str)
    json_bytes = json_data.encode('utf-8')

    serialization_time = time.time() - start_time

    # Deserialization
    start_time = time.time()
    loaded_data = json.loads(json_bytes.decode('utf-8'))
    deserialization_time = time.time() - start_time

    return {
        'serialization_time': serialization_time,
        'deserialization_time': deserialization_time,
        'total_time': serialization_time + deserialization_time,
        'size_bytes': len(json_bytes),
        'method': 'old_manual_json'
    }


def benchmark_new_approach(data, method: SerializationMethod):
    """Benchmark the new optimized serialization approach"""
    serializer = CacheSerializer(method)

    # Serialization
    start_time = time.time()
    serialized_bytes = serializer.serialize(data)
    serialization_time = time.time() - start_time

    # Deserialization
    start_time = time.time()
    loaded_data = serializer.deserialize(serialized_bytes)
    deserialization_time = time.time() - start_time

    return {
        'serialization_time': serialization_time,
        'deserialization_time': deserialization_time,
        'total_time': serialization_time + deserialization_time,
        'size_bytes': len(serialized_bytes),
        'method': method.value
    }


def run_performance_comparison():
    """Run comprehensive performance comparison"""
    print("🚀 Cache Serialization Performance Demo")
    print("=" * 50)

    # Test datasets
    test_cases = [
        ("Small Recommendations", create_test_recommendations(10)),
        ("Medium Recommendations", create_test_recommendations(100)),
        ("Large Recommendations", create_test_recommendations(500)),
        ("Complex Data Small", create_test_complex_data(10)),
        ("Complex Data Medium", create_test_complex_data(50)),
    ]

    methods = [
        SerializationMethod.JSON,
        SerializationMethod.JSON_COMPRESSED,
        SerializationMethod.PICKLE,
        SerializationMethod.PICKLE_COMPRESSED
    ]

    for test_name, test_data in test_cases:
        print(f"\n📊 Testing: {test_name} ({len(test_data)} items)")
        print("-" * 40)

        # Benchmark old approach
        old_result = benchmark_old_approach(test_data)
        print(f"Old Manual JSON:     {old_result['total_time']:.4f}s, {old_result['size_bytes']:,} bytes")

        # Benchmark new approaches
        for method in methods:
            try:
                new_result = benchmark_new_approach(test_data, method)

                # Calculate improvements
                time_improvement = ((old_result['total_time'] - new_result['total_time']) / old_result['total_time']) * 100
                size_improvement = ((old_result['size_bytes'] - new_result['size_bytes']) / old_result['size_bytes']) * 100

                print(f"{method.value:15}: {new_result['total_time']:.4f}s, {new_result['size_bytes']:,} bytes "
                      f"({time_improvement:+.1f}% time, {size_improvement:+.1f}% size)")

            except Exception as e:
                print(f"{method.value:15}: Error - {e}")


def demonstrate_memory_efficiency():
    """Demonstrate memory efficiency improvements"""
    print("\n🧠 Memory Efficiency Demonstration")
    print("=" * 50)

    # Create large dataset
    large_data = create_test_recommendations(1000)

    # Compare different compression methods
    serializer = CacheSerializer()

    methods_to_test = [
        (SerializationMethod.JSON, "JSON (no compression)"),
        (SerializationMethod.JSON_COMPRESSED, "JSON + gzip"),
        (SerializationMethod.PICKLE, "Pickle (no compression)"),
        (SerializationMethod.PICKLE_COMPRESSED, "Pickle + lzma")
    ]

    print(f"Dataset: {len(large_data)} recommendations")
    baseline_size = None

    for method, description in methods_to_test:
        try:
            serialized = serializer.serialize(large_data, method)
            size_kb = len(serialized) / 1024

            if baseline_size is None:
                baseline_size = len(serialized)
                compression_ratio = 1.0
            else:
                compression_ratio = len(serialized) / baseline_size

            print(f"{description:25}: {size_kb:8.1f} KB (ratio: {compression_ratio:.3f})")

        except Exception as e:
            print(f"{description:25}: Error - {e}")


def main():
    """Main demo function"""
    try:
        run_performance_comparison()
        demonstrate_memory_efficiency()

        print("\n✅ Cache Serialization Optimization Complete!")
        print("\nKey Benefits:")
        print("- Automatic dataclass handling")
        print("- Intelligent compression for large objects")
        print("- Type-safe deserialization")
        print("- Consistent performance across services")
        print("- Reduced memory usage")

    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
