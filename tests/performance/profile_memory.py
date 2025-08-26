"""
Memory profiling script for nightly performance testing.

This script profiles memory usage of key RAG-Anything operations
and generates reports for performance monitoring.
"""

import asyncio
import gc
import time
from typing import List, Dict, Any
import tracemalloc
from memory_profiler import profile
import psutil
import os

from raganything.backends.graphiti_direct import GraphitiDirectBackend
from raganything.episode_converter import EpisodeConverter
from raganything.caching import CacheManager
from tests.factories import DocumentFactory, EpisodeFactory


class MemoryProfiler:
    """Memory profiler for RAG-Anything operations"""
    
    def __init__(self):
        self.process = psutil.Process()
        self.baseline_memory = None
        self.measurements = []
    
    def start_profiling(self):
        """Start memory profiling"""
        tracemalloc.start()
        self.baseline_memory = self.process.memory_info().rss
        print(f"Starting memory profiling. Baseline: {self.baseline_memory / 1024 / 1024:.2f} MB")
    
    def measure(self, operation_name: str):
        """Take a memory measurement"""
        current_memory = self.process.memory_info().rss
        memory_diff = current_memory - self.baseline_memory
        
        # Get tracemalloc snapshot
        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics('lineno')[:10]
        
        measurement = {
            'operation': operation_name,
            'timestamp': time.time(),
            'memory_mb': current_memory / 1024 / 1024,
            'memory_diff_mb': memory_diff / 1024 / 1024,
            'top_allocations': [
                f"{stat.traceback.format()[-1]}: {stat.size / 1024:.1f} KB"
                for stat in top_stats[:5]
            ]
        }
        
        self.measurements.append(measurement)
        print(f"{operation_name}: {current_memory / 1024 / 1024:.2f} MB (+{memory_diff / 1024 / 1024:.2f} MB)")
        
        return measurement
    
    def stop_profiling(self):
        """Stop memory profiling and return results"""
        tracemalloc.stop()
        return self.measurements


@profile
def profile_document_processing():
    """Profile memory usage during document processing"""
    print("\n=== Profiling Document Processing ===")
    
    profiler = MemoryProfiler()
    profiler.start_profiling()
    
    # Create test documents
    profiler.measure("Baseline")
    
    documents = []
    for i in range(50):
        doc = DocumentFactory.create_text_document(size=10000)  # 10KB each
        documents.append(doc)
    
    profiler.measure("Created 50 documents")
    
    # Process documents through episode converter
    converter = EpisodeConverter()
    episodes = []
    
    for doc in documents:
        content = doc.content.decode('utf-8')
        episode = converter.convert_to_episode(content, f"doc_{len(episodes)}")
        episodes.append(episode)
    
    profiler.measure("Converted to episodes")
    
    # Clean up
    del documents
    del episodes
    gc.collect()
    
    profiler.measure("After cleanup")
    
    results = profiler.stop_profiling()
    return results


@profile
def profile_caching_operations():
    """Profile memory usage of caching operations"""
    print("\n=== Profiling Caching Operations ===")
    
    profiler = MemoryProfiler()
    profiler.start_profiling()
    
    # Create cache manager
    cache_manager = CacheManager()
    profiler.measure("Created cache manager")
    
    # Fill caches with data
    for i in range(1000):
        # Document cache
        key = f"doc_{i}"
        value = f"document_content_{i}" * 100  # Make it substantial
        cache_manager.document_cache.set(key, value)
        
        if i % 100 == 0:
            profiler.measure(f"Added {i+1} documents to cache")
    
    # Fill embedding cache
    for i in range(500):
        key = f"embedding_{i}"
        value = [0.1] * 1536  # Typical embedding size
        cache_manager.embedding_cache.set(key, value)
        
        if i % 100 == 0:
            profiler.measure(f"Added {i+1} embeddings to cache")
    
    # Access cached items
    for i in range(100):
        cache_manager.document_cache.get(f"doc_{i}")
        cache_manager.embedding_cache.get(f"embedding_{i}")
    
    profiler.measure("Accessed cached items")
    
    # Clear caches
    cache_manager.clear_all()
    gc.collect()
    
    profiler.measure("Cleared all caches")
    
    results = profiler.stop_profiling()
    return results


@profile
def profile_batch_processing():
    """Profile memory usage during batch processing"""
    print("\n=== Profiling Batch Processing ===")
    
    profiler = MemoryProfiler()
    profiler.start_profiling()
    
    # Create large batch of episodes
    episodes = EpisodeFactory.create_batch_episodes(count=200)
    profiler.measure("Created 200 episodes")
    
    # Process in batches
    batch_size = 20
    processed_batches = []
    
    for i in range(0, len(episodes), batch_size):
        batch = episodes[i:i + batch_size]
        
        # Simulate processing
        processed_batch = []
        for episode in batch:
            # Convert to dict (simulates serialization)
            episode_dict = {
                'name': episode.name,
                'content': episode.content,
                'content_type': episode.content_type,
                'metadata': episode.metadata
            }
            processed_batch.append(episode_dict)
        
        processed_batches.append(processed_batch)
        
        if len(processed_batches) % 5 == 0:
            profiler.measure(f"Processed {len(processed_batches)} batches")
    
    profiler.measure("Completed batch processing")
    
    # Clean up
    del episodes
    del processed_batches
    gc.collect()
    
    profiler.measure("After cleanup")
    
    results = profiler.stop_profiling()
    return results


def profile_memory_leaks():
    """Profile for potential memory leaks"""
    print("\n=== Profiling for Memory Leaks ===")
    
    profiler = MemoryProfiler()
    profiler.start_profiling()
    
    # Simulate repeated operations that might leak memory
    for iteration in range(10):
        print(f"Iteration {iteration + 1}")
        
        # Create and destroy objects repeatedly
        temp_data = []
        
        for i in range(100):
            doc = DocumentFactory.create_text_document()
            episode = EpisodeFactory.create_text_episode()
            temp_data.append((doc, episode))
        
        # Process data
        converter = EpisodeConverter()
        for doc, episode in temp_data:
            converted = converter.convert_to_episode(
                doc.content.decode('utf-8'), 
                f"temp_{i}"
            )
        
        # Clean up
        del temp_data
        del converter
        gc.collect()
        
        profiler.measure(f"Iteration {iteration + 1} cleanup")
    
    results = profiler.stop_profiling()
    
    # Analyze for leaks
    print("\n=== Memory Leak Analysis ===")
    if len(results) >= 2:
        initial_memory = results[1]['memory_mb']  # After first measurement
        final_memory = results[-1]['memory_mb']
        memory_growth = final_memory - initial_memory
        
        print(f"Initial memory: {initial_memory:.2f} MB")
        print(f"Final memory: {final_memory:.2f} MB")
        print(f"Memory growth: {memory_growth:.2f} MB")
        
        if memory_growth > 50:  # More than 50MB growth
            print("WARNING: Potential memory leak detected!")
        else:
            print("No significant memory leak detected.")
    
    return results


def generate_memory_report(all_results: Dict[str, List[Dict]]):
    """Generate a comprehensive memory usage report"""
    print("\n" + "="*60)
    print("MEMORY PROFILING REPORT")
    print("="*60)
    
    for test_name, results in all_results.items():
        print(f"\n{test_name.upper()}:")
        print("-" * 40)
        
        if not results:
            print("No measurements taken")
            continue
        
        max_memory = max(r['memory_mb'] for r in results)
        max_diff = max(r['memory_diff_mb'] for r in results)
        
        print(f"Peak memory usage: {max_memory:.2f} MB")
        print(f"Maximum memory increase: {max_diff:.2f} MB")
        
        print("\nDetailed measurements:")
        for result in results:
            print(f"  {result['operation']}: {result['memory_mb']:.2f} MB "
                  f"(+{result['memory_diff_mb']:.2f} MB)")
        
        if results[-1]['top_allocations']:
            print("\nTop allocations in final measurement:")
            for allocation in results[-1]['top_allocations']:
                print(f"  {allocation}")
    
    print("\n" + "="*60)


def main():
    """Main memory profiling function"""
    print("Starting comprehensive memory profiling...")
    
    all_results = {}
    
    try:
        # Run all profiling tests
        all_results['document_processing'] = profile_document_processing()
        all_results['caching_operations'] = profile_caching_operations()
        all_results['batch_processing'] = profile_batch_processing()
        all_results['memory_leaks'] = profile_memory_leaks()
        
    except Exception as e:
        print(f"Error during profiling: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Generate report
        generate_memory_report(all_results)
        
        # Save results to file
        import json
        with open('memory_profiling_results.json', 'w') as f:
            # Convert results to JSON-serializable format
            serializable_results = {}
            for test_name, results in all_results.items():
                serializable_results[test_name] = [
                    {k: v for k, v in result.items() if k != 'top_allocations'}
                    for result in results
                ]
            json.dump(serializable_results, f, indent=2)
        
        print(f"\nDetailed results saved to memory_profiling_results.json")
        print("Memory profiling completed.")


if __name__ == "__main__":
    main()