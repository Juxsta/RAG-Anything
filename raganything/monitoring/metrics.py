"""
Comprehensive metrics collection system for RAG-Anything.

This module provides performance metrics, system monitoring,
and real-time analytics for the RAG system.
"""

import time
import psutil
import asyncio
import threading
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from collections import defaultdict, deque
import redis.asyncio as aioredis
import json
import logging
from contextlib import asynccontextmanager

# Configure logger
logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics that can be collected"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"
    RATE = "rate"


class MetricUnit(Enum):
    """Units for metrics"""
    NONE = ""
    BYTES = "bytes"
    SECONDS = "seconds"
    MILLISECONDS = "ms"
    MICROSECONDS = "us"
    REQUESTS = "requests"
    PERCENT = "percent"
    COUNT = "count"


@dataclass
class Metric:
    """Individual metric data point"""
    name: str
    value: Union[float, int]
    metric_type: MetricType
    unit: MetricUnit = MetricUnit.NONE
    timestamp: datetime = field(default_factory=datetime.now)
    labels: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metric to dictionary"""
        return {
            'name': self.name,
            'value': self.value,
            'type': self.metric_type.value,
            'unit': self.unit.value,
            'timestamp': self.timestamp.isoformat(),
            'labels': self.labels,
            'metadata': self.metadata
        }
    
    def with_labels(self, **labels) -> 'Metric':
        """Create a copy of metric with additional labels"""
        new_labels = {**self.labels, **labels}
        return Metric(
            name=self.name,
            value=self.value,
            metric_type=self.metric_type,
            unit=self.unit,
            timestamp=self.timestamp,
            labels=new_labels,
            metadata=self.metadata
        )


@dataclass
class MetricsConfig:
    """Configuration for metrics collection"""
    
    # Collection settings
    collection_interval: float = 10.0  # seconds
    retention_hours: int = 24
    max_metrics_per_hour: int = 10000
    
    # Storage settings
    redis_prefix: str = "raganything:metrics"
    enable_redis_storage: bool = True
    enable_file_storage: bool = False
    file_storage_path: str = "./metrics"
    
    # System monitoring
    enable_system_metrics: bool = True
    system_metrics_interval: float = 30.0  # seconds
    
    # Performance tracking
    enable_performance_tracking: bool = True
    track_slow_operations: bool = True
    slow_operation_threshold: float = 1.0  # seconds
    
    # Custom metrics
    custom_collectors: List[Callable] = field(default_factory=list)
    
    # Export settings
    prometheus_enabled: bool = False
    prometheus_port: int = 9090
    grafana_enabled: bool = False


class PerformanceTracker:
    """Tracks performance metrics for operations"""
    
    def __init__(self, metrics_collector: 'MetricsCollector' = None):
        self.metrics_collector = metrics_collector
        self.active_timers = {}
        self.operation_stats = defaultdict(lambda: {
            'count': 0,
            'total_time': 0.0,
            'min_time': float('inf'),
            'max_time': 0.0,
            'recent_times': deque(maxlen=100)
        })
    
    @asynccontextmanager
    async def track_operation(self, operation_name: str, labels: Dict[str, str] = None):
        """Context manager to track operation performance"""
        start_time = time.time()
        labels = labels or {}
        
        try:
            yield
        except Exception as e:
            # Track error metrics
            if self.metrics_collector:
                await self.metrics_collector.increment_counter(
                    f"{operation_name}_errors",
                    labels={**labels, "error_type": type(e).__name__}
                )
            raise
        finally:
            end_time = time.time()
            duration = end_time - start_time
            
            # Update statistics
            stats = self.operation_stats[operation_name]
            stats['count'] += 1
            stats['total_time'] += duration
            stats['min_time'] = min(stats['min_time'], duration)
            stats['max_time'] = max(stats['max_time'], duration)
            stats['recent_times'].append(duration)
            
            # Record metrics
            if self.metrics_collector:
                await self.metrics_collector.record_timer(
                    f"{operation_name}_duration",
                    duration,
                    labels=labels
                )
                
                await self.metrics_collector.increment_counter(
                    f"{operation_name}_total",
                    labels=labels
                )
                
                # Track slow operations
                if duration > self.metrics_collector.config.slow_operation_threshold:
                    await self.metrics_collector.increment_counter(
                        f"{operation_name}_slow",
                        labels={**labels, "threshold": str(self.metrics_collector.config.slow_operation_threshold)}
                    )
    
    def get_operation_stats(self, operation_name: str) -> Dict[str, Any]:
        """Get statistics for a specific operation"""
        stats = self.operation_stats.get(operation_name)
        if not stats or stats['count'] == 0:
            return {}
        
        recent_times = list(stats['recent_times'])
        avg_time = stats['total_time'] / stats['count']
        recent_avg = sum(recent_times) / len(recent_times) if recent_times else 0
        
        return {
            'operation': operation_name,
            'total_calls': stats['count'],
            'total_time': stats['total_time'],
            'average_time': avg_time,
            'min_time': stats['min_time'],
            'max_time': stats['max_time'],
            'recent_average': recent_avg,
            'recent_calls': len(recent_times)
        }
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all tracked operations"""
        return {
            name: self.get_operation_stats(name)
            for name in self.operation_stats.keys()
        }


class SystemMonitor:
    """Monitors system resource usage"""
    
    def __init__(self, metrics_collector: 'MetricsCollector' = None):
        self.metrics_collector = metrics_collector
        self.monitoring = False
        self.monitor_task = None
        self.process = psutil.Process()
    
    async def start_monitoring(self, interval: float = 30.0):
        """Start system monitoring"""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_task = asyncio.create_task(self._monitor_loop(interval))
        logger.info("System monitoring started")
    
    async def stop_monitoring(self):
        """Stop system monitoring"""
        self.monitoring = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("System monitoring stopped")
    
    async def _monitor_loop(self, interval: float):
        """Main monitoring loop"""
        while self.monitoring:
            try:
                await self._collect_system_metrics()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in system monitoring: {e}")
                await asyncio.sleep(interval)
    
    async def _collect_system_metrics(self):
        """Collect system metrics"""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            if self.metrics_collector:
                await self.metrics_collector.set_gauge(
                    "system_cpu_percent",
                    cpu_percent,
                    unit=MetricUnit.PERCENT
                )
            
            # Memory metrics
            memory = psutil.virtual_memory()
            if self.metrics_collector:
                await self.metrics_collector.set_gauge(
                    "system_memory_usage",
                    memory.percent,
                    unit=MetricUnit.PERCENT
                )
                
                await self.metrics_collector.set_gauge(
                    "system_memory_available",
                    memory.available,
                    unit=MetricUnit.BYTES
                )
                
                await self.metrics_collector.set_gauge(
                    "system_memory_total",
                    memory.total,
                    unit=MetricUnit.BYTES
                )
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            if self.metrics_collector:
                await self.metrics_collector.set_gauge(
                    "system_disk_usage",
                    (disk.used / disk.total) * 100,
                    unit=MetricUnit.PERCENT
                )
                
                await self.metrics_collector.set_gauge(
                    "system_disk_free",
                    disk.free,
                    unit=MetricUnit.BYTES
                )
            
            # Process-specific metrics
            try:
                process_memory = self.process.memory_info()
                process_cpu = self.process.cpu_percent()
                
                if self.metrics_collector:
                    await self.metrics_collector.set_gauge(
                        "process_memory_rss",
                        process_memory.rss,
                        unit=MetricUnit.BYTES
                    )
                    
                    await self.metrics_collector.set_gauge(
                        "process_memory_vms",
                        process_memory.vms,
                        unit=MetricUnit.BYTES
                    )
                    
                    await self.metrics_collector.set_gauge(
                        "process_cpu_percent",
                        process_cpu,
                        unit=MetricUnit.PERCENT
                    )
                    
                    # File descriptors (Unix only)
                    try:
                        num_fds = self.process.num_fds()
                        await self.metrics_collector.set_gauge(
                            "process_file_descriptors",
                            num_fds,
                            unit=MetricUnit.COUNT
                        )
                    except AttributeError:
                        # Not available on Windows
                        pass
                    
                    # Thread count
                    num_threads = self.process.num_threads()
                    await self.metrics_collector.set_gauge(
                        "process_threads",
                        num_threads,
                        unit=MetricUnit.COUNT
                    )
                    
            except psutil.NoSuchProcess:
                logger.warning("Process no longer exists for monitoring")
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
    
    def get_current_system_info(self) -> Dict[str, Any]:
        """Get current system information"""
        try:
            return {
                'cpu': {
                    'percent': psutil.cpu_percent(interval=1),
                    'count': psutil.cpu_count(),
                    'count_logical': psutil.cpu_count(logical=True)
                },
                'memory': {
                    'total': psutil.virtual_memory().total,
                    'available': psutil.virtual_memory().available,
                    'percent': psutil.virtual_memory().percent,
                    'used': psutil.virtual_memory().used
                },
                'disk': {
                    'total': psutil.disk_usage('/').total,
                    'used': psutil.disk_usage('/').used,
                    'free': psutil.disk_usage('/').free,
                    'percent': (psutil.disk_usage('/').used / psutil.disk_usage('/').total) * 100
                },
                'process': {
                    'pid': self.process.pid,
                    'memory_rss': self.process.memory_info().rss,
                    'memory_vms': self.process.memory_info().vms,
                    'cpu_percent': self.process.cpu_percent(),
                    'num_threads': self.process.num_threads(),
                    'create_time': self.process.create_time()
                }
            }
        except Exception as e:
            logger.error(f"Error getting system info: {e}")
            return {}


class MetricsCollector:
    """
    Main metrics collection and storage system.
    
    Collects, aggregates, and stores metrics from various sources
    including system monitoring, performance tracking, and custom collectors.
    """
    
    def __init__(self, config: MetricsConfig, redis_client: Optional[aioredis.Redis] = None):
        self.config = config
        self.redis_client = redis_client
        
        # Internal storage
        self.metrics_buffer = deque(maxlen=10000)
        self.metric_aggregates = defaultdict(lambda: {
            'count': 0,
            'sum': 0.0,
            'min': float('inf'),
            'max': float('-inf'),
            'recent_values': deque(maxlen=100)
        })
        
        # Components
        self.performance_tracker = PerformanceTracker(self)
        self.system_monitor = SystemMonitor(self)
        
        # Background tasks
        self.collection_task = None
        self.storage_task = None
        self.running = False
        
        # Metrics registry
        self.registered_metrics = {}
        self.custom_collectors = config.custom_collectors or []
    
    async def start(self):
        """Start the metrics collection system"""
        if self.running:
            return
        
        self.running = True
        
        # Start background tasks
        self.collection_task = asyncio.create_task(self._collection_loop())
        self.storage_task = asyncio.create_task(self._storage_loop())
        
        # Start system monitoring if enabled
        if self.config.enable_system_metrics:
            await self.system_monitor.start_monitoring(
                interval=self.config.system_metrics_interval
            )
        
        logger.info("Metrics collection started")
    
    async def stop(self):
        """Stop the metrics collection system"""
        if not self.running:
            return
        
        self.running = False
        
        # Stop background tasks
        if self.collection_task:
            self.collection_task.cancel()
        if self.storage_task:
            self.storage_task.cancel()
        
        # Stop system monitoring
        await self.system_monitor.stop_monitoring()
        
        # Final storage flush
        await self._store_metrics()
        
        logger.info("Metrics collection stopped")
    
    async def _collection_loop(self):
        """Background task for collecting metrics"""
        while self.running:
            try:
                # Run custom collectors
                for collector in self.custom_collectors:
                    try:
                        if asyncio.iscoroutinefunction(collector):
                            await collector(self)
                        else:
                            collector(self)
                    except Exception as e:
                        logger.error(f"Error in custom collector: {e}")
                
                await asyncio.sleep(self.config.collection_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in collection loop: {e}")
                await asyncio.sleep(self.config.collection_interval)
    
    async def _storage_loop(self):
        """Background task for storing metrics"""
        while self.running:
            try:
                await self._store_metrics()
                await asyncio.sleep(60)  # Store every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in storage loop: {e}")
                await asyncio.sleep(60)
    
    async def _store_metrics(self):
        """Store buffered metrics to persistent storage"""
        if not self.metrics_buffer:
            return
        
        try:
            # Convert buffer to list and clear it atomically
            metrics_to_store = list(self.metrics_buffer)
            self.metrics_buffer.clear()
            
            # Store to Redis if enabled
            if self.config.enable_redis_storage and self.redis_client:
                await self._store_to_redis(metrics_to_store)
            
            # Store to file if enabled
            if self.config.enable_file_storage:
                await self._store_to_file(metrics_to_store)
            
            logger.debug(f"Stored {len(metrics_to_store)} metrics")
            
        except Exception as e:
            logger.error(f"Error storing metrics: {e}")
    
    async def _store_to_redis(self, metrics: List[Metric]):
        """Store metrics to Redis"""
        try:
            pipe = self.redis_client.pipeline()
            
            for metric in metrics:
                # Store individual metric
                metric_key = f"{self.config.redis_prefix}:metric:{metric.name}:{int(metric.timestamp.timestamp())}"
                pipe.setex(
                    metric_key,
                    self.config.retention_hours * 3600,
                    json.dumps(metric.to_dict())
                )
                
                # Add to time series
                series_key = f"{self.config.redis_prefix}:series:{metric.name}"
                pipe.zadd(
                    series_key,
                    {metric_key: metric.timestamp.timestamp()}
                )
                pipe.expire(series_key, self.config.retention_hours * 3600)
                
                # Update aggregates
                if metric.metric_type in [MetricType.COUNTER, MetricType.GAUGE, MetricType.TIMER]:
                    agg_key = f"{self.config.redis_prefix}:agg:{metric.name}"
                    pipe.hincrby(agg_key, "count", 1)
                    pipe.hincrbyfloat(agg_key, "sum", float(metric.value))
                    pipe.expire(agg_key, self.config.retention_hours * 3600)
            
            await pipe.execute()
            
        except Exception as e:
            logger.error(f"Error storing metrics to Redis: {e}")
    
    async def _store_to_file(self, metrics: List[Metric]):
        """Store metrics to file"""
        # Implementation for file storage
        pass
    
    # Metric recording methods
    
    async def increment_counter(self, name: str, value: int = 1, labels: Dict[str, str] = None):
        """Increment a counter metric"""
        metric = Metric(
            name=name,
            value=value,
            metric_type=MetricType.COUNTER,
            labels=labels or {}
        )
        await self._record_metric(metric)
    
    async def set_gauge(self, name: str, value: Union[float, int], unit: MetricUnit = MetricUnit.NONE, labels: Dict[str, str] = None):
        """Set a gauge metric value"""
        metric = Metric(
            name=name,
            value=value,
            metric_type=MetricType.GAUGE,
            unit=unit,
            labels=labels or {}
        )
        await self._record_metric(metric)
    
    async def record_histogram(self, name: str, value: Union[float, int], unit: MetricUnit = MetricUnit.NONE, labels: Dict[str, str] = None):
        """Record a histogram value"""
        metric = Metric(
            name=name,
            value=value,
            metric_type=MetricType.HISTOGRAM,
            unit=unit,
            labels=labels or {}
        )
        await self._record_metric(metric)
    
    async def record_timer(self, name: str, duration: float, unit: MetricUnit = MetricUnit.SECONDS, labels: Dict[str, str] = None):
        """Record a timer value"""
        metric = Metric(
            name=name,
            value=duration,
            metric_type=MetricType.TIMER,
            unit=unit,
            labels=labels or {}
        )
        await self._record_metric(metric)
    
    async def record_rate(self, name: str, count: int, duration: float, labels: Dict[str, str] = None):
        """Record a rate metric (count per time unit)"""
        rate = count / duration if duration > 0 else 0
        metric = Metric(
            name=name,
            value=rate,
            metric_type=MetricType.RATE,
            unit=MetricUnit.REQUESTS,
            labels=labels or {},
            metadata={'count': count, 'duration': duration}
        )
        await self._record_metric(metric)
    
    async def _record_metric(self, metric: Metric):
        """Record a metric to the buffer"""
        self.metrics_buffer.append(metric)
        
        # Update aggregates
        agg = self.metric_aggregates[metric.name]
        agg['count'] += 1
        agg['sum'] += float(metric.value)
        agg['min'] = min(agg['min'], float(metric.value))
        agg['max'] = max(agg['max'], float(metric.value))
        agg['recent_values'].append(float(metric.value))
    
    # Query methods
    
    async def get_metric_summary(self, name: str) -> Dict[str, Any]:
        """Get summary statistics for a metric"""
        agg = self.metric_aggregates.get(name)
        if not agg or agg['count'] == 0:
            return {}
        
        recent_values = list(agg['recent_values'])
        
        return {
            'name': name,
            'count': agg['count'],
            'sum': agg['sum'],
            'average': agg['sum'] / agg['count'],
            'min': agg['min'] if agg['min'] != float('inf') else 0,
            'max': agg['max'] if agg['max'] != float('-inf') else 0,
            'recent_count': len(recent_values),
            'recent_average': sum(recent_values) / len(recent_values) if recent_values else 0
        }
    
    async def get_metrics_by_pattern(self, pattern: str) -> List[Dict[str, Any]]:
        """Get metrics matching a pattern"""
        matching_metrics = []
        
        for name in self.metric_aggregates.keys():
            if pattern in name:
                summary = await self.get_metric_summary(name)
                if summary:
                    matching_metrics.append(summary)
        
        return matching_metrics
    
    async def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system metrics"""
        return self.system_monitor.get_current_system_info()
    
    async def get_performance_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get performance tracking metrics"""
        return self.performance_tracker.get_all_stats()
    
    def get_collector_info(self) -> Dict[str, Any]:
        """Get information about the metrics collector"""
        return {
            'running': self.running,
            'buffer_size': len(self.metrics_buffer),
            'tracked_metrics': len(self.metric_aggregates),
            'config': {
                'collection_interval': self.config.collection_interval,
                'retention_hours': self.config.retention_hours,
                'redis_enabled': self.config.enable_redis_storage,
                'system_monitoring': self.config.enable_system_metrics,
                'performance_tracking': self.config.enable_performance_tracking
            },
            'components': {
                'system_monitor': self.system_monitor.monitoring,
                'performance_tracker': len(self.performance_tracker.operation_stats)
            }
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for metrics collection system"""
        health = {
            'status': 'healthy' if self.running else 'stopped',
            'running': self.running,
            'buffer_size': len(self.metrics_buffer),
            'tracked_metrics': len(self.metric_aggregates),
            'redis_connected': False,
            'system_monitor_active': self.system_monitor.monitoring,
            'timestamp': datetime.now().isoformat()
        }
        
        # Check Redis connection
        if self.redis_client:
            try:
                await self.redis_client.ping()
                health['redis_connected'] = True
            except Exception as e:
                health['redis_error'] = str(e)
        
        return health
    
    # Context managers and decorators
    
    def track_operation(self, operation_name: str, labels: Dict[str, str] = None):
        """Context manager to track operation performance"""
        return self.performance_tracker.track_operation(operation_name, labels)
    
    def timer(self, metric_name: str, labels: Dict[str, str] = None):
        """Decorator/context manager for timing operations"""
        return self.track_operation(metric_name, labels)