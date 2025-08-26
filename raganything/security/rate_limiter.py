"""
Advanced rate limiting implementation for RAG-Anything.

This module provides multiple rate limiting strategies:
- Token Bucket Algorithm
- Sliding Window Counter
- Fixed Window Counter
- Adaptive Rate Limiting

Supports per-user, per-IP, and per-endpoint rate limiting
with Redis-based distributed storage.
"""

import time
import json
import asyncio
import hashlib
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import redis.asyncio as aioredis
import logging

# Configure logger
logger = logging.getLogger(__name__)


class RateLimitStrategy(Enum):
    """Rate limiting strategies"""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"
    ADAPTIVE = "adaptive"


class RateLimitError(Exception):
    """Raised when rate limit is exceeded"""
    
    def __init__(
        self, 
        message: str, 
        retry_after: float = None,
        current_usage: int = None,
        limit: int = None
    ):
        self.message = message
        self.retry_after = retry_after
        self.current_usage = current_usage
        self.limit = limit
        super().__init__(message)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting"""
    
    # Basic rate limiting
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    requests_per_day: int = 10000
    
    # Burst handling
    burst_limit: int = 10
    burst_window: int = 10  # seconds
    
    # Strategy
    strategy: RateLimitStrategy = RateLimitStrategy.TOKEN_BUCKET
    
    # Advanced features
    enable_adaptive: bool = False
    adaptive_factor: float = 0.1
    
    # Blocking behavior
    block_duration: int = 300  # 5 minutes
    progressive_blocking: bool = True
    
    # Redis settings
    redis_prefix: str = "raganything:ratelimit"
    redis_ttl: int = 86400  # 24 hours
    
    # Whitelist/Blacklist
    whitelist: List[str] = field(default_factory=list)
    blacklist: List[str] = field(default_factory=list)


@dataclass 
class RateLimitResult:
    """Result of rate limit check"""
    allowed: bool
    remaining: int
    reset_time: float
    retry_after: Optional[float] = None
    current_usage: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseRateLimiter(ABC):
    """Base class for rate limiters"""
    
    def __init__(self, config: RateLimitConfig, redis_client: Optional[aioredis.Redis] = None):
        self.config = config
        self.redis_client = redis_client
        self._local_cache = {}  # Fallback for when Redis is unavailable
        self._cache_ttl = {}
    
    @abstractmethod
    async def check_rate_limit(self, key: str, cost: int = 1) -> RateLimitResult:
        """Check if request is within rate limits"""
        pass
    
    @abstractmethod
    async def reset_rate_limit(self, key: str) -> bool:
        """Reset rate limit for a key"""
        pass
    
    def _generate_key(self, identifier: str, window: str = "minute") -> str:
        """Generate Redis key for rate limiting"""
        return f"{self.config.redis_prefix}:{identifier}:{window}"
    
    def _is_whitelisted(self, identifier: str) -> bool:
        """Check if identifier is whitelisted"""
        return identifier in self.config.whitelist
    
    def _is_blacklisted(self, identifier: str) -> bool:
        """Check if identifier is blacklisted"""
        return identifier in self.config.blacklist
    
    async def _get_redis_data(self, key: str) -> Optional[Dict[str, Any]]:
        """Get data from Redis with fallback to local cache"""
        try:
            if self.redis_client:
                data = await self.redis_client.get(key)
                if data:
                    return json.loads(data)
            return self._local_cache.get(key)
        except Exception as e:
            logger.warning(f"Redis error, using local cache: {e}")
            return self._local_cache.get(key)
    
    async def _set_redis_data(self, key: str, data: Dict[str, Any], ttl: int = None) -> bool:
        """Set data in Redis with fallback to local cache"""
        try:
            if self.redis_client:
                await self.redis_client.setex(
                    key, 
                    ttl or self.config.redis_ttl, 
                    json.dumps(data)
                )
                return True
        except Exception as e:
            logger.warning(f"Redis error, using local cache: {e}")
        
        # Fallback to local cache
        self._local_cache[key] = data
        self._cache_ttl[key] = time.time() + (ttl or self.config.redis_ttl)
        return False
    
    def _clean_local_cache(self):
        """Clean expired entries from local cache"""
        current_time = time.time()
        expired_keys = [
            key for key, ttl in self._cache_ttl.items()
            if ttl < current_time
        ]
        for key in expired_keys:
            self._local_cache.pop(key, None)
            self._cache_ttl.pop(key, None)


class TokenBucketRateLimiter(BaseRateLimiter):
    """
    Token Bucket rate limiter implementation.
    
    Allows burst traffic up to bucket capacity while maintaining
    average rate over time.
    """
    
    async def check_rate_limit(self, key: str, cost: int = 1) -> RateLimitResult:
        """Check rate limit using token bucket algorithm"""
        
        # Check whitelist/blacklist
        if self._is_whitelisted(key):
            return RateLimitResult(
                allowed=True,
                remaining=self.config.requests_per_minute,
                reset_time=time.time() + 60
            )
        
        if self._is_blacklisted(key):
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=time.time() + self.config.block_duration,
                retry_after=self.config.block_duration
            )
        
        current_time = time.time()
        bucket_key = self._generate_key(key, "bucket")
        
        # Get current bucket state
        bucket_data = await self._get_redis_data(bucket_key)
        
        if not bucket_data:
            # Initialize new bucket
            bucket_data = {
                'tokens': self.config.burst_limit,
                'last_refill': current_time,
                'total_requests': 0
            }
        
        # Calculate tokens to add based on time elapsed
        time_elapsed = current_time - bucket_data['last_refill']
        tokens_to_add = time_elapsed * (self.config.requests_per_minute / 60.0)
        
        # Update bucket
        bucket_data['tokens'] = min(
            self.config.burst_limit,
            bucket_data['tokens'] + tokens_to_add
        )
        bucket_data['last_refill'] = current_time
        
        # Check if enough tokens available
        if bucket_data['tokens'] >= cost:
            # Consume tokens
            bucket_data['tokens'] -= cost
            bucket_data['total_requests'] += cost
            
            # Save updated bucket state
            await self._set_redis_data(bucket_key, bucket_data)
            
            return RateLimitResult(
                allowed=True,
                remaining=int(bucket_data['tokens']),
                reset_time=current_time + (self.config.burst_limit / (self.config.requests_per_minute / 60.0)),
                current_usage=bucket_data['total_requests']
            )
        else:
            # Rate limit exceeded
            retry_after = (cost - bucket_data['tokens']) / (self.config.requests_per_minute / 60.0)
            
            return RateLimitResult(
                allowed=False,
                remaining=int(bucket_data['tokens']),
                reset_time=current_time + retry_after,
                retry_after=retry_after,
                current_usage=bucket_data['total_requests']
            )
    
    async def reset_rate_limit(self, key: str) -> bool:
        """Reset token bucket for a key"""
        try:
            bucket_key = self._generate_key(key, "bucket")
            if self.redis_client:
                await self.redis_client.delete(bucket_key)
            else:
                self._local_cache.pop(bucket_key, None)
                self._cache_ttl.pop(bucket_key, None)
            return True
        except Exception as e:
            logger.error(f"Failed to reset rate limit for {key}: {e}")
            return False


class SlidingWindowRateLimiter(BaseRateLimiter):
    """
    Sliding Window rate limiter implementation.
    
    Maintains accurate rate limiting over a sliding time window
    using sorted sets in Redis.
    """
    
    async def check_rate_limit(self, key: str, cost: int = 1) -> RateLimitResult:
        """Check rate limit using sliding window algorithm"""
        
        # Check whitelist/blacklist
        if self._is_whitelisted(key):
            return RateLimitResult(
                allowed=True,
                remaining=self.config.requests_per_minute,
                reset_time=time.time() + 60
            )
        
        if self._is_blacklisted(key):
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=time.time() + self.config.block_duration,
                retry_after=self.config.block_duration
            )
        
        current_time = time.time()
        window_key = self._generate_key(key, "sliding")
        
        # Window durations in seconds
        windows = {
            'minute': (60, self.config.requests_per_minute),
            'hour': (3600, self.config.requests_per_hour),
            'day': (86400, self.config.requests_per_day)
        }
        
        # Check all windows
        for window_name, (duration, limit) in windows.items():
            window_start = current_time - duration
            window_key_full = f"{window_key}:{window_name}"
            
            try:
                if self.redis_client:
                    # Use Redis sorted sets for accurate sliding window
                    pipe = self.redis_client.pipeline()
                    
                    # Remove old entries
                    pipe.zremrangebyscore(window_key_full, 0, window_start)
                    
                    # Count current entries
                    pipe.zcard(window_key_full)
                    
                    # Execute pipeline
                    results = await pipe.execute()
                    current_count = results[1] if len(results) > 1 else 0
                    
                else:
                    # Fallback to local cache with less precision
                    window_data = self._local_cache.get(window_key_full, [])
                    # Filter out old entries
                    window_data = [
                        timestamp for timestamp in window_data 
                        if timestamp > window_start
                    ]
                    current_count = len(window_data)
                
                # Check if adding this request would exceed limit
                if current_count + cost > limit:
                    # Calculate retry after
                    if self.redis_client:
                        oldest_timestamp = await self.redis_client.zrange(
                            window_key_full, 0, 0, withscores=True
                        )
                        if oldest_timestamp:
                            retry_after = oldest_timestamp[0][1] + duration - current_time
                        else:
                            retry_after = duration
                    else:
                        retry_after = duration if window_data else duration
                    
                    return RateLimitResult(
                        allowed=False,
                        remaining=max(0, limit - current_count),
                        reset_time=current_time + retry_after,
                        retry_after=max(1, retry_after),
                        current_usage=current_count
                    )
            
            except Exception as e:
                logger.error(f"Error checking sliding window for {window_name}: {e}")
                # Conservative fallback - deny request
                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    reset_time=current_time + 60,
                    retry_after=60
                )
        
        # All windows passed, record the request
        try:
            for window_name, (duration, limit) in windows.items():
                window_key_full = f"{window_key}:{window_name}"
                
                if self.redis_client:
                    # Add current timestamp to sorted set
                    pipe = self.redis_client.pipeline()
                    for _ in range(cost):
                        pipe.zadd(
                            window_key_full, 
                            {f"{current_time}:{asyncio.get_event_loop().time()}": current_time}
                        )
                    pipe.expire(window_key_full, duration)
                    await pipe.execute()
                else:
                    # Local cache fallback
                    if window_key_full not in self._local_cache:
                        self._local_cache[window_key_full] = []
                    self._local_cache[window_key_full].extend([current_time] * cost)
                    self._cache_ttl[window_key_full] = current_time + duration
        
        except Exception as e:
            logger.error(f"Error recording request in sliding window: {e}")
        
        return RateLimitResult(
            allowed=True,
            remaining=self.config.requests_per_minute - cost,
            reset_time=current_time + 60,
            current_usage=cost
        )
    
    async def reset_rate_limit(self, key: str) -> bool:
        """Reset sliding window for a key"""
        try:
            window_key = self._generate_key(key, "sliding")
            
            if self.redis_client:
                # Delete all window keys
                pattern = f"{window_key}:*"
                keys = await self.redis_client.keys(pattern)
                if keys:
                    await self.redis_client.delete(*keys)
            else:
                # Clean local cache
                keys_to_remove = [
                    k for k in self._local_cache.keys() 
                    if k.startswith(window_key)
                ]
                for k in keys_to_remove:
                    self._local_cache.pop(k, None)
                    self._cache_ttl.pop(k, None)
            
            return True
        except Exception as e:
            logger.error(f"Failed to reset sliding window for {key}: {e}")
            return False


class AdaptiveRateLimiter(BaseRateLimiter):
    """
    Adaptive rate limiter that adjusts limits based on system load
    and user behavior patterns.
    """
    
    def __init__(self, config: RateLimitConfig, redis_client: Optional[aioredis.Redis] = None):
        super().__init__(config, redis_client)
        self.base_limiter = TokenBucketRateLimiter(config, redis_client)
        self.system_load_threshold = 0.8
        self.user_behavior_cache = {}
    
    async def check_rate_limit(self, key: str, cost: int = 1) -> RateLimitResult:
        """Check rate limit with adaptive behavior"""
        
        # Get base rate limit result
        base_result = await self.base_limiter.check_rate_limit(key, cost)
        
        if not self.config.enable_adaptive:
            return base_result
        
        # Adjust limits based on system metrics and user behavior
        adjustment_factor = await self._calculate_adjustment_factor(key)
        
        if adjustment_factor < 1.0:
            # Reduce limits due to high load or suspicious behavior
            if base_result.allowed:
                # Apply stricter limits
                adjusted_remaining = int(base_result.remaining * adjustment_factor)
                if adjusted_remaining <= 0:
                    return RateLimitResult(
                        allowed=False,
                        remaining=0,
                        reset_time=base_result.reset_time,
                        retry_after=base_result.retry_after or 60,
                        current_usage=base_result.current_usage
                    )
                else:
                    base_result.remaining = adjusted_remaining
        
        elif adjustment_factor > 1.0:
            # Increase limits for trusted users during low load
            base_result.remaining = int(base_result.remaining * adjustment_factor)
        
        return base_result
    
    async def _calculate_adjustment_factor(self, key: str) -> float:
        """Calculate adjustment factor based on various metrics"""
        factor = 1.0
        
        try:
            # System load adjustment
            system_load = await self._get_system_load()
            if system_load > self.system_load_threshold:
                factor *= (2 - system_load / self.system_load_threshold)
            
            # User behavior adjustment
            behavior_score = await self._get_user_behavior_score(key)
            factor *= (0.5 + behavior_score)  # Range: 0.5 to 1.5
            
            # Time-based adjustment (lower limits during peak hours)
            time_factor = self._get_time_adjustment()
            factor *= time_factor
            
        except Exception as e:
            logger.warning(f"Error calculating adjustment factor: {e}")
        
        return max(0.1, min(2.0, factor))  # Clamp between 0.1 and 2.0
    
    async def _get_system_load(self) -> float:
        """Get current system load (mock implementation)"""
        # In real implementation, this would check:
        # - CPU usage
        # - Memory usage  
        # - Active connections
        # - Response times
        # - Queue lengths
        
        # Mock implementation
        return 0.5  # 50% load
    
    async def _get_user_behavior_score(self, key: str) -> float:
        """Get user behavior score (0.0 = suspicious, 1.0 = trusted)"""
        # Check behavior patterns
        behavior_key = f"behavior:{key}"
        behavior_data = await self._get_redis_data(behavior_key)
        
        if not behavior_data:
            return 0.5  # Neutral for new users
        
        # Calculate score based on:
        # - Request patterns (regularity vs bursty)
        # - Error rates
        # - Compliance with rate limits
        # - Account age
        
        score = 0.5
        
        # Good behavior indicators
        if behavior_data.get('compliant_requests', 0) > behavior_data.get('rate_limited_requests', 0):
            score += 0.2
        
        if behavior_data.get('error_rate', 1.0) < 0.1:
            score += 0.2
        
        if behavior_data.get('account_age_days', 0) > 30:
            score += 0.1
        
        return min(1.0, score)
    
    def _get_time_adjustment(self) -> float:
        """Get time-based adjustment factor"""
        import datetime
        
        now = datetime.datetime.now()
        hour = now.hour
        
        # Lower limits during peak hours (9 AM - 5 PM)
        if 9 <= hour <= 17:
            return 0.8
        # Higher limits during off-hours
        elif hour < 6 or hour > 22:
            return 1.2
        else:
            return 1.0
    
    async def reset_rate_limit(self, key: str) -> bool:
        """Reset adaptive rate limit"""
        return await self.base_limiter.reset_rate_limit(key)


class RateLimiter:
    """
    Main rate limiter interface that selects appropriate strategy
    and provides unified API.
    """
    
    def __init__(self, config: RateLimitConfig, redis_client: Optional[aioredis.Redis] = None):
        self.config = config
        self.redis_client = redis_client
        
        # Initialize strategy-specific limiter
        if config.strategy == RateLimitStrategy.TOKEN_BUCKET:
            self.limiter = TokenBucketRateLimiter(config, redis_client)
        elif config.strategy == RateLimitStrategy.SLIDING_WINDOW:
            self.limiter = SlidingWindowRateLimiter(config, redis_client)
        elif config.strategy == RateLimitStrategy.ADAPTIVE:
            self.limiter = AdaptiveRateLimiter(config, redis_client)
        else:
            self.limiter = TokenBucketRateLimiter(config, redis_client)
    
    async def check_rate_limit(
        self, 
        identifier: str, 
        endpoint: str = None, 
        cost: int = 1
    ) -> RateLimitResult:
        """
        Check rate limit for an identifier and endpoint.
        
        Args:
            identifier: User/IP identifier
            endpoint: API endpoint (optional)
            cost: Cost of this request (default: 1)
            
        Returns:
            RateLimitResult indicating if request is allowed
        """
        # Create composite key if endpoint is provided
        if endpoint:
            key = f"{identifier}:{endpoint}"
        else:
            key = identifier
        
        try:
            result = await self.limiter.check_rate_limit(key, cost)
            
            # Log rate limiting events
            if not result.allowed:
                logger.warning(
                    f"Rate limit exceeded for {identifier}"
                    f"{f' on {endpoint}' if endpoint else ''}: "
                    f"{result.current_usage} requests, limit exceeded"
                )
            
            return result
            
        except Exception as e:
            logger.error(f"Rate limiting error for {key}: {e}")
            # Fail open - allow request but log error
            return RateLimitResult(
                allowed=True,
                remaining=self.config.requests_per_minute,
                reset_time=time.time() + 60,
                metadata={'error': str(e)}
            )
    
    async def reset_rate_limit(self, identifier: str, endpoint: str = None) -> bool:
        """Reset rate limit for identifier and optional endpoint"""
        key = f"{identifier}:{endpoint}" if endpoint else identifier
        return await self.limiter.reset_rate_limit(key)
    
    async def get_rate_limit_status(self, identifier: str, endpoint: str = None) -> Dict[str, Any]:
        """Get detailed rate limit status"""
        key = f"{identifier}:{endpoint}" if endpoint else identifier
        
        # Get current status without consuming quota
        result = await self.limiter.check_rate_limit(key, cost=0)
        
        return {
            'identifier': identifier,
            'endpoint': endpoint,
            'allowed': result.allowed,
            'remaining': result.remaining,
            'reset_time': result.reset_time,
            'current_usage': result.current_usage,
            'strategy': self.config.strategy.value,
            'limits': {
                'per_minute': self.config.requests_per_minute,
                'per_hour': self.config.requests_per_hour,
                'per_day': self.config.requests_per_day,
                'burst': self.config.burst_limit
            }
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for rate limiting system"""
        status = {
            'strategy': self.config.strategy.value,
            'redis_connected': False,
            'local_cache_entries': len(self.limiter._local_cache),
            'timestamp': time.time()
        }
        
        try:
            if self.redis_client:
                await self.redis_client.ping()
                status['redis_connected'] = True
        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")
        
        return status