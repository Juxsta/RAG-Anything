"""
Caching and performance optimization module for RAG-Anything.

Provides intelligent caching for various operations including:
- Document parsing results
- Embedding computations
- Query results
- Entity/relationship lookups
- Episode processing results
"""

import hashlib
import json
import time
import asyncio
from typing import Any, Dict, List, Optional, Union, Callable, TypeVar
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass 
class CacheEntry:
    """Represents a cached entry with metadata"""
    data: Any
    created_at: datetime
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.now)
    ttl_seconds: Optional[int] = None
    size_bytes: Optional[int] = None
    cache_key: str = ""
    
    def is_expired(self) -> bool:
        """Check if the cache entry has expired"""
        if not self.ttl_seconds:
            return False
        return datetime.now() > self.created_at + timedelta(seconds=self.ttl_seconds)
    
    def touch(self) -> None:
        """Update access statistics"""
        self.access_count += 1
        self.last_accessed = datetime.now()


class InMemoryCache:
    """High-performance in-memory cache with LRU eviction"""
    
    def __init__(self, max_size: int = 1000, max_memory_mb: int = 512):
        self.max_size = max_size
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self._cache: Dict[str, CacheEntry] = {}
        self._access_order: List[str] = []
        self._current_memory_usage = 0
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'size_evictions': 0,
            'memory_evictions': 0,
            'expired_evictions': 0
        }
    
    def get(self, key: str) -> Optional[Any]:
        """Get item from cache"""
        if key not in self._cache:
            self._stats['misses'] += 1
            return None
        
        entry = self._cache[key]
        
        # Check expiration
        if entry.is_expired():
            self._evict(key)
            self._stats['misses'] += 1
            self._stats['expired_evictions'] += 1
            return None
        
        # Update access statistics
        entry.touch()
        
        # Move to end of access order (most recently used)
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)
        
        self._stats['hits'] += 1
        return entry.data
    
    def put(self, key: str, data: Any, ttl_seconds: Optional[int] = None) -> None:
        """Store item in cache"""
        # Calculate data size
        try:
            size_bytes = len(json.dumps(data, default=str).encode())
        except (TypeError, ValueError):
            size_bytes = len(str(data).encode())
        
        # Create cache entry
        entry = CacheEntry(
            data=data,
            created_at=datetime.now(),
            ttl_seconds=ttl_seconds,
            size_bytes=size_bytes,
            cache_key=key
        )
        
        # Check if item already exists
        if key in self._cache:
            old_entry = self._cache[key]
            self._current_memory_usage -= old_entry.size_bytes or 0
        
        # Store the entry
        self._cache[key] = entry
        self._current_memory_usage += size_bytes
        
        # Update access order
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)
        
        # Enforce size and memory limits
        self._enforce_limits()
    
    def _enforce_limits(self) -> None:
        """Enforce cache size and memory limits"""
        # Evict expired entries first
        self._evict_expired()
        
        # Evict based on size limit
        while len(self._cache) > self.max_size:
            if not self._access_order:
                break
            lru_key = self._access_order.pop(0)
            self._evict(lru_key)
            self._stats['evictions'] += 1
            self._stats['size_evictions'] += 1
        
        # Evict based on memory limit
        while self._current_memory_usage > self.max_memory_bytes:
            if not self._access_order:
                break
            lru_key = self._access_order.pop(0)
            self._evict(lru_key)
            self._stats['evictions'] += 1
            self._stats['memory_evictions'] += 1
    
    def _evict_expired(self) -> None:
        """Remove all expired entries"""
        expired_keys = [
            key for key, entry in self._cache.items() 
            if entry.is_expired()
        ]
        
        for key in expired_keys:
            self._evict(key)
            self._stats['expired_evictions'] += 1
    
    def _evict(self, key: str) -> None:
        """Remove a specific key from cache"""
        if key in self._cache:
            entry = self._cache.pop(key)
            self._current_memory_usage -= entry.size_bytes or 0
        
        if key in self._access_order:
            self._access_order.remove(key)
    
    def clear(self) -> None:
        """Clear all cache entries"""
        self._cache.clear()
        self._access_order.clear()
        self._current_memory_usage = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self._stats['hits'] + self._stats['misses']
        hit_rate = self._stats['hits'] / total_requests if total_requests > 0 else 0
        
        return {
            **self._stats,
            'size': len(self._cache),
            'max_size': self.max_size,
            'memory_usage_mb': self._current_memory_usage / (1024 * 1024),
            'max_memory_mb': self.max_memory_bytes / (1024 * 1024),
            'hit_rate': hit_rate,
            'memory_usage_percent': (self._current_memory_usage / self.max_memory_bytes) * 100
        }


class CacheManager:
    """Manages multiple specialized caches with different policies"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # Initialize different cache types
        self.document_cache = InMemoryCache(
            max_size=self.config.get('document_cache_size', 100),
            max_memory_mb=self.config.get('document_cache_memory_mb', 256)
        )
        
        self.embedding_cache = InMemoryCache(
            max_size=self.config.get('embedding_cache_size', 1000),
            max_memory_mb=self.config.get('embedding_cache_memory_mb', 128)
        )
        
        self.query_cache = InMemoryCache(
            max_size=self.config.get('query_cache_size', 500),
            max_memory_mb=self.config.get('query_cache_memory_mb', 64)
        )
        
        self.entity_cache = InMemoryCache(
            max_size=self.config.get('entity_cache_size', 2000),
            max_memory_mb=self.config.get('entity_cache_memory_mb', 32)
        )
        
        self.episode_cache = InMemoryCache(
            max_size=self.config.get('episode_cache_size', 500),
            max_memory_mb=self.config.get('episode_cache_memory_mb', 128)
        )
        
        # Cache-specific TTLs (in seconds)
        self.cache_ttls = {
            'document': self.config.get('document_ttl', 3600),  # 1 hour
            'embedding': self.config.get('embedding_ttl', 86400),  # 24 hours
            'query': self.config.get('query_ttl', 300),  # 5 minutes
            'entity': self.config.get('entity_ttl', 1800),  # 30 minutes
            'episode': self.config.get('episode_ttl', 7200),  # 2 hours
        }
        
        # Thread pool for async operations
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        logger.info("Cache manager initialized with multiple specialized caches")
    
    def _generate_key(self, *args, prefix: str = "") -> str:
        """Generate a consistent cache key from arguments"""
        key_data = json.dumps(args, sort_keys=True, default=str)
        key_hash = hashlib.md5(key_data.encode()).hexdigest()
        return f"{prefix}:{key_hash}" if prefix else key_hash
    
    async def get_or_compute_document(
        self, 
        key: str, 
        compute_fn: Callable[[], Any],
        ttl_seconds: Optional[int] = None
    ) -> Any:
        """Get document from cache or compute and store"""
        cache_key = self._generate_key(key, prefix="doc")
        
        # Try cache first
        result = self.document_cache.get(cache_key)
        if result is not None:
            logger.debug(f"Document cache hit for key: {cache_key}")
            return result
        
        # Compute the result
        logger.debug(f"Document cache miss for key: {cache_key}, computing...")
        
        if asyncio.iscoroutinefunction(compute_fn):
            result = await compute_fn()
        else:
            result = await asyncio.get_event_loop().run_in_executor(
                self.executor, compute_fn
            )
        
        # Store in cache
        ttl = ttl_seconds or self.cache_ttls['document']
        self.document_cache.put(cache_key, result, ttl)
        
        return result
    
    async def get_or_compute_embedding(
        self,
        text: str,
        model: str,
        compute_fn: Callable[[str], Any],
        ttl_seconds: Optional[int] = None
    ) -> Any:
        """Get embedding from cache or compute and store"""
        cache_key = self._generate_key(text, model, prefix="emb")
        
        # Try cache first
        result = self.embedding_cache.get(cache_key)
        if result is not None:
            logger.debug(f"Embedding cache hit for: {text[:50]}...")
            return result
        
        # Compute embedding
        logger.debug(f"Embedding cache miss, computing for: {text[:50]}...")
        
        if asyncio.iscoroutinefunction(compute_fn):
            result = await compute_fn(text)
        else:
            result = await asyncio.get_event_loop().run_in_executor(
                self.executor, lambda: compute_fn(text)
            )
        
        # Store in cache
        ttl = ttl_seconds or self.cache_ttls['embedding']
        self.embedding_cache.put(cache_key, result, ttl)
        
        return result
    
    async def get_or_compute_query(
        self,
        query: str,
        mode: str,
        params: Dict[str, Any],
        compute_fn: Callable[[], Any],
        ttl_seconds: Optional[int] = None
    ) -> Any:
        """Get query result from cache or compute and store"""
        cache_key = self._generate_key(query, mode, params, prefix="query")
        
        # Try cache first
        result = self.query_cache.get(cache_key)
        if result is not None:
            logger.debug(f"Query cache hit for: {query[:50]}...")
            return result
        
        # Compute query
        logger.debug(f"Query cache miss, computing for: {query[:50]}...")
        
        if asyncio.iscoroutinefunction(compute_fn):
            result = await compute_fn()
        else:
            result = await asyncio.get_event_loop().run_in_executor(
                self.executor, compute_fn
            )
        
        # Store in cache
        ttl = ttl_seconds or self.cache_ttls['query']
        self.query_cache.put(cache_key, result, ttl)
        
        return result
    
    def cache_entity(self, entity_uuid: str, entity_data: Any, ttl_seconds: Optional[int] = None) -> None:
        """Cache entity data"""
        cache_key = self._generate_key(entity_uuid, prefix="entity")
        ttl = ttl_seconds or self.cache_ttls['entity']
        self.entity_cache.put(cache_key, entity_data, ttl)
    
    def get_entity(self, entity_uuid: str) -> Optional[Any]:
        """Get entity from cache"""
        cache_key = self._generate_key(entity_uuid, prefix="entity")
        return self.entity_cache.get(cache_key)
    
    def cache_episode(self, episode_uuid: str, episode_data: Any, ttl_seconds: Optional[int] = None) -> None:
        """Cache episode data"""
        cache_key = self._generate_key(episode_uuid, prefix="episode")
        ttl = ttl_seconds or self.cache_ttls['episode']
        self.episode_cache.put(cache_key, episode_data, ttl)
    
    def get_episode(self, episode_uuid: str) -> Optional[Any]:
        """Get episode from cache"""
        cache_key = self._generate_key(episode_uuid, prefix="episode")
        return self.episode_cache.get(cache_key)
    
    def invalidate_cache(self, cache_type: str = "all") -> None:
        """Invalidate specific cache or all caches"""
        if cache_type == "all":
            self.document_cache.clear()
            self.embedding_cache.clear()
            self.query_cache.clear()
            self.entity_cache.clear()
            self.episode_cache.clear()
            logger.info("All caches cleared")
        elif cache_type == "document":
            self.document_cache.clear()
            logger.info("Document cache cleared")
        elif cache_type == "embedding":
            self.embedding_cache.clear()
            logger.info("Embedding cache cleared")
        elif cache_type == "query":
            self.query_cache.clear()
            logger.info("Query cache cleared")
        elif cache_type == "entity":
            self.entity_cache.clear()
            logger.info("Entity cache cleared")
        elif cache_type == "episode":
            self.episode_cache.clear()
            logger.info("Episode cache cleared")
    
    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics for all caches"""
        return {
            'document_cache': self.document_cache.get_stats(),
            'embedding_cache': self.embedding_cache.get_stats(),
            'query_cache': self.query_cache.get_stats(),
            'entity_cache': self.entity_cache.get_stats(),
            'episode_cache': self.episode_cache.get_stats(),
            'config': self.config,
            'cache_ttls': self.cache_ttls,
            'total_memory_usage_mb': sum([
                self.document_cache._current_memory_usage,
                self.embedding_cache._current_memory_usage,
                self.query_cache._current_memory_usage,
                self.entity_cache._current_memory_usage,
                self.episode_cache._current_memory_usage
            ]) / (1024 * 1024)
        }
    
    async def cleanup_expired(self) -> Dict[str, int]:
        """Clean up expired entries from all caches"""
        cleanup_stats = {}
        
        for cache_name, cache in [
            ('document', self.document_cache),
            ('embedding', self.embedding_cache),
            ('query', self.query_cache),
            ('entity', self.entity_cache),
            ('episode', self.episode_cache),
        ]:
            initial_size = len(cache._cache)
            cache._evict_expired()
            final_size = len(cache._cache)
            cleanup_stats[cache_name] = initial_size - final_size
        
        total_cleaned = sum(cleanup_stats.values())
        logger.info(f"Cleanup complete: removed {total_cleaned} expired entries")
        
        return cleanup_stats
    
    async def periodic_maintenance(self, interval_seconds: int = 300) -> None:
        """Run periodic maintenance tasks"""
        while True:
            try:
                await asyncio.sleep(interval_seconds)
                cleanup_stats = await self.cleanup_expired()
                
                # Log cache statistics periodically
                if sum(cleanup_stats.values()) > 0:
                    stats = self.get_comprehensive_stats()
                    logger.info(f"Cache maintenance: {cleanup_stats}, total memory: {stats['total_memory_usage_mb']:.1f}MB")
                
            except Exception as e:
                logger.error(f"Error during cache maintenance: {e}")
    
    def shutdown(self) -> None:
        """Shutdown cache manager and cleanup resources"""
        self.executor.shutdown(wait=True)
        logger.info("Cache manager shutdown complete")


# Global cache manager instance
_global_cache_manager: Optional[CacheManager] = None


def get_cache_manager(config: Optional[Dict[str, Any]] = None) -> CacheManager:
    """Get or create global cache manager instance"""
    global _global_cache_manager
    
    if _global_cache_manager is None:
        _global_cache_manager = CacheManager(config)
    
    return _global_cache_manager


def invalidate_global_cache(cache_type: str = "all") -> None:
    """Invalidate global cache"""
    global _global_cache_manager
    
    if _global_cache_manager:
        _global_cache_manager.invalidate_cache(cache_type)


def get_global_cache_stats() -> Dict[str, Any]:
    """Get global cache statistics"""
    global _global_cache_manager
    
    if _global_cache_manager:
        return _global_cache_manager.get_comprehensive_stats()
    
    return {"error": "Cache manager not initialized"}


# Decorators for easy caching
def cache_result(cache_type: str = "document", ttl_seconds: Optional[int] = None):
    """Decorator to cache function results"""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            cache_manager = get_cache_manager()
            
            # Generate cache key
            key = cache_manager._generate_key(*args, **kwargs, prefix=cache_type)
            
            # Get appropriate cache
            if cache_type == "document":
                cache = cache_manager.document_cache
                default_ttl = cache_manager.cache_ttls['document']
            elif cache_type == "embedding":
                cache = cache_manager.embedding_cache
                default_ttl = cache_manager.cache_ttls['embedding']
            elif cache_type == "query":
                cache = cache_manager.query_cache
                default_ttl = cache_manager.cache_ttls['query']
            else:
                cache = cache_manager.document_cache
                default_ttl = cache_manager.cache_ttls['document']
            
            # Try cache first
            result = cache.get(key)
            if result is not None:
                return result
            
            # Compute result
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Store in cache
            ttl = ttl_seconds or default_ttl
            cache.put(key, result, ttl)
            
            return result
        
        def sync_wrapper(*args, **kwargs):
            # For synchronous functions, we can't use async cache operations
            return func(*args, **kwargs)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator