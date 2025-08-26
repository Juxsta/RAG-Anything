"""
Comprehensive health check system for RAG-Anything.

This module provides health monitoring for all system components
including backends, services, external dependencies, and system resources.
"""

import asyncio
import time
import psutil
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import redis.asyncio as aioredis
import httpx
import logging

# Configure logger
logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health check status levels"""
    HEALTHY = "healthy"
    WARNING = "warning"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class CheckType(Enum):
    """Types of health checks"""
    DEPENDENCY = "dependency"
    RESOURCE = "resource"
    FUNCTIONAL = "functional"
    INTEGRATION = "integration"
    CUSTOM = "custom"


@dataclass
class HealthCheck:
    """Individual health check configuration"""
    name: str
    check_func: Callable
    check_type: CheckType
    timeout: float = 30.0
    interval: float = 60.0  # seconds
    retries: int = 3
    retry_delay: float = 1.0
    critical: bool = False
    labels: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ComponentHealth:
    """Health status of a system component"""
    name: str
    status: HealthStatus
    message: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    response_time: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    checks_passed: int = 0
    checks_failed: int = 0
    last_error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            'name': self.name,
            'status': self.status.value,
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
            'response_time': self.response_time,
            'details': self.details,
            'checks_passed': self.checks_passed,
            'checks_failed': self.checks_failed,
            'last_error': self.last_error
        }


class SystemHealthCheck:
    """System-level health checks for resources and dependencies"""
    
    @staticmethod
    async def check_memory_usage(warning_threshold: float = 80.0, critical_threshold: float = 95.0) -> ComponentHealth:
        """Check system memory usage"""
        try:
            memory = psutil.virtual_memory()
            usage_percent = memory.percent
            
            if usage_percent >= critical_threshold:
                status = HealthStatus.UNHEALTHY
                message = f"Critical memory usage: {usage_percent:.1f}%"
            elif usage_percent >= warning_threshold:
                status = HealthStatus.WARNING
                message = f"High memory usage: {usage_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"Memory usage normal: {usage_percent:.1f}%"
            
            return ComponentHealth(
                name="memory",
                status=status,
                message=message,
                details={
                    'usage_percent': usage_percent,
                    'total_bytes': memory.total,
                    'available_bytes': memory.available,
                    'used_bytes': memory.used,
                    'warning_threshold': warning_threshold,
                    'critical_threshold': critical_threshold
                }
            )
        except Exception as e:
            return ComponentHealth(
                name="memory",
                status=HealthStatus.UNKNOWN,
                message=f"Memory check failed: {str(e)}",
                last_error=str(e)
            )
    
    @staticmethod
    async def check_cpu_usage(warning_threshold: float = 80.0, critical_threshold: float = 95.0, interval: float = 1.0) -> ComponentHealth:
        """Check CPU usage"""
        try:
            cpu_percent = psutil.cpu_percent(interval=interval)
            
            if cpu_percent >= critical_threshold:
                status = HealthStatus.UNHEALTHY
                message = f"Critical CPU usage: {cpu_percent:.1f}%"
            elif cpu_percent >= warning_threshold:
                status = HealthStatus.WARNING
                message = f"High CPU usage: {cpu_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"CPU usage normal: {cpu_percent:.1f}%"
            
            return ComponentHealth(
                name="cpu",
                status=status,
                message=message,
                details={
                    'usage_percent': cpu_percent,
                    'cpu_count': psutil.cpu_count(),
                    'cpu_count_logical': psutil.cpu_count(logical=True),
                    'warning_threshold': warning_threshold,
                    'critical_threshold': critical_threshold
                }
            )
        except Exception as e:
            return ComponentHealth(
                name="cpu",
                status=HealthStatus.UNKNOWN,
                message=f"CPU check failed: {str(e)}",
                last_error=str(e)
            )
    
    @staticmethod
    async def check_disk_usage(path: str = "/", warning_threshold: float = 80.0, critical_threshold: float = 95.0) -> ComponentHealth:
        """Check disk usage"""
        try:
            disk = psutil.disk_usage(path)
            usage_percent = (disk.used / disk.total) * 100
            
            if usage_percent >= critical_threshold:
                status = HealthStatus.UNHEALTHY
                message = f"Critical disk usage: {usage_percent:.1f}%"
            elif usage_percent >= warning_threshold:
                status = HealthStatus.WARNING
                message = f"High disk usage: {usage_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"Disk usage normal: {usage_percent:.1f}%"
            
            return ComponentHealth(
                name="disk",
                status=status,
                message=message,
                details={
                    'path': path,
                    'usage_percent': usage_percent,
                    'total_bytes': disk.total,
                    'used_bytes': disk.used,
                    'free_bytes': disk.free,
                    'warning_threshold': warning_threshold,
                    'critical_threshold': critical_threshold
                }
            )
        except Exception as e:
            return ComponentHealth(
                name="disk",
                status=HealthStatus.UNKNOWN,
                message=f"Disk check failed: {str(e)}",
                last_error=str(e)
            )
    
    @staticmethod
    async def check_redis_connection(redis_client: aioredis.Redis, timeout: float = 5.0) -> ComponentHealth:
        """Check Redis connection"""
        start_time = time.time()
        
        try:
            await asyncio.wait_for(redis_client.ping(), timeout=timeout)
            response_time = time.time() - start_time
            
            # Get additional Redis info
            info = await redis_client.info()
            
            return ComponentHealth(
                name="redis",
                status=HealthStatus.HEALTHY,
                message="Redis connection healthy",
                response_time=response_time,
                details={
                    'connected_clients': info.get('connected_clients', 0),
                    'used_memory': info.get('used_memory', 0),
                    'used_memory_human': info.get('used_memory_human', '0B'),
                    'redis_version': info.get('redis_version', 'unknown'),
                    'uptime_in_seconds': info.get('uptime_in_seconds', 0)
                }
            )
        
        except asyncio.TimeoutError:
            return ComponentHealth(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                message=f"Redis connection timeout (>{timeout}s)",
                response_time=time.time() - start_time,
                last_error="Connection timeout"
            )
        except Exception as e:
            return ComponentHealth(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                message=f"Redis connection failed: {str(e)}",
                response_time=time.time() - start_time,
                last_error=str(e)
            )
    
    @staticmethod
    async def check_http_endpoint(url: str, method: str = "GET", timeout: float = 10.0, expected_status: int = 200) -> ComponentHealth:
        """Check HTTP endpoint availability"""
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(method, url, timeout=timeout)
                response_time = time.time() - start_time
                
                if response.status_code == expected_status:
                    status = HealthStatus.HEALTHY
                    message = f"Endpoint responding correctly ({response.status_code})"
                else:
                    status = HealthStatus.WARNING
                    message = f"Unexpected status code: {response.status_code} (expected {expected_status})"
                
                return ComponentHealth(
                    name=f"http_{url}",
                    status=status,
                    message=message,
                    response_time=response_time,
                    details={
                        'url': url,
                        'method': method,
                        'status_code': response.status_code,
                        'expected_status': expected_status,
                        'response_headers': dict(response.headers),
                        'response_size': len(response.content)
                    }
                )
        
        except httpx.TimeoutException:
            return ComponentHealth(
                name=f"http_{url}",
                status=HealthStatus.UNHEALTHY,
                message=f"HTTP endpoint timeout (>{timeout}s)",
                response_time=time.time() - start_time,
                last_error="Request timeout"
            )
        except Exception as e:
            return ComponentHealth(
                name=f"http_{url}",
                status=HealthStatus.UNHEALTHY,
                message=f"HTTP endpoint error: {str(e)}",
                response_time=time.time() - start_time,
                last_error=str(e)
            )
    
    @staticmethod
    async def check_process_health() -> ComponentHealth:
        """Check current process health"""
        try:
            process = psutil.Process()
            
            # Get process information
            memory_info = process.memory_info()
            cpu_percent = process.cpu_percent()
            num_threads = process.num_threads()
            
            # Check for potential issues
            issues = []
            if memory_info.rss > 2 * 1024 * 1024 * 1024:  # 2GB
                issues.append("High memory usage")
            if cpu_percent > 90:
                issues.append("High CPU usage")
            if num_threads > 100:
                issues.append("High thread count")
            
            if issues:
                status = HealthStatus.WARNING
                message = f"Process health issues: {', '.join(issues)}"
            else:
                status = HealthStatus.HEALTHY
                message = "Process health normal"
            
            return ComponentHealth(
                name="process",
                status=status,
                message=message,
                details={
                    'pid': process.pid,
                    'memory_rss': memory_info.rss,
                    'memory_vms': memory_info.vms,
                    'cpu_percent': cpu_percent,
                    'num_threads': num_threads,
                    'create_time': process.create_time(),
                    'status': process.status()
                }
            )
        
        except Exception as e:
            return ComponentHealth(
                name="process",
                status=HealthStatus.UNKNOWN,
                message=f"Process check failed: {str(e)}",
                last_error=str(e)
            )


class HealthCheckManager:
    """
    Manages health checks for all system components.
    
    Orchestrates periodic health checks, maintains health history,
    and provides comprehensive system health reporting.
    """
    
    def __init__(self, redis_client: Optional[aioredis.Redis] = None):
        self.redis_client = redis_client
        self.registered_checks = {}
        self.component_health = {}
        self.health_history = {}
        self.running = False
        self.check_tasks = {}
        
        # Register default system checks
        self._register_default_checks()
    
    def _register_default_checks(self):
        """Register default system health checks"""
        # System resource checks
        self.register_check(HealthCheck(
            name="memory",
            check_func=SystemHealthCheck.check_memory_usage,
            check_type=CheckType.RESOURCE,
            interval=30.0,
            critical=True
        ))
        
        self.register_check(HealthCheck(
            name="cpu",
            check_func=SystemHealthCheck.check_cpu_usage,
            check_type=CheckType.RESOURCE,
            interval=30.0,
            critical=True
        ))
        
        self.register_check(HealthCheck(
            name="disk",
            check_func=SystemHealthCheck.check_disk_usage,
            check_type=CheckType.RESOURCE,
            interval=60.0,
            critical=True
        ))
        
        self.register_check(HealthCheck(
            name="process",
            check_func=SystemHealthCheck.check_process_health,
            check_type=CheckType.RESOURCE,
            interval=30.0,
            critical=False
        ))
        
        # Redis check (if available)
        if self.redis_client:
            self.register_check(HealthCheck(
                name="redis",
                check_func=lambda: SystemHealthCheck.check_redis_connection(self.redis_client),
                check_type=CheckType.DEPENDENCY,
                interval=30.0,
                critical=True
            ))
    
    def register_check(self, health_check: HealthCheck):
        """Register a health check"""
        self.registered_checks[health_check.name] = health_check
        logger.info(f"Registered health check: {health_check.name}")
    
    def unregister_check(self, check_name: str) -> bool:
        """Unregister a health check"""
        if check_name in self.registered_checks:
            del self.registered_checks[check_name]
            
            # Stop the task if running
            if check_name in self.check_tasks:
                self.check_tasks[check_name].cancel()
                del self.check_tasks[check_name]
            
            # Remove from health status
            if check_name in self.component_health:
                del self.component_health[check_name]
            
            logger.info(f"Unregistered health check: {check_name}")
            return True
        
        return False
    
    async def start_monitoring(self):
        """Start health monitoring"""
        if self.running:
            return
        
        self.running = True
        
        # Start check tasks for each registered check
        for check_name, check in self.registered_checks.items():
            self.check_tasks[check_name] = asyncio.create_task(
                self._check_loop(check_name, check)
            )
        
        logger.info(f"Started health monitoring with {len(self.registered_checks)} checks")
    
    async def stop_monitoring(self):
        """Stop health monitoring"""
        if not self.running:
            return
        
        self.running = False
        
        # Cancel all check tasks
        for task in self.check_tasks.values():
            task.cancel()
        
        # Wait for tasks to complete
        if self.check_tasks:
            await asyncio.gather(*self.check_tasks.values(), return_exceptions=True)
        
        self.check_tasks.clear()
        logger.info("Stopped health monitoring")
    
    async def _check_loop(self, check_name: str, health_check: HealthCheck):
        """Main loop for individual health check"""
        while self.running:
            try:
                await self._perform_check(check_name, health_check)
                await asyncio.sleep(health_check.interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check loop for {check_name}: {e}")
                await asyncio.sleep(health_check.interval)
    
    async def _perform_check(self, check_name: str, health_check: HealthCheck):
        """Perform a single health check with retries"""
        start_time = time.time()
        last_error = None
        
        for attempt in range(health_check.retries + 1):
            try:
                # Execute the health check
                if asyncio.iscoroutinefunction(health_check.check_func):
                    result = await asyncio.wait_for(
                        health_check.check_func(),
                        timeout=health_check.timeout
                    )
                else:
                    result = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(
                            None, health_check.check_func
                        ),
                        timeout=health_check.timeout
                    )
                
                # Update health status
                if isinstance(result, ComponentHealth):
                    result.response_time = time.time() - start_time
                    self.component_health[check_name] = result
                    
                    # Update statistics
                    if result.status == HealthStatus.HEALTHY:
                        result.checks_passed += 1
                    else:
                        result.checks_failed += 1
                    
                    # Store in history
                    self._store_health_history(check_name, result)
                    
                    # Log issues
                    if result.status != HealthStatus.HEALTHY:
                        logger.warning(f"Health check {check_name} status: {result.status.value} - {result.message}")
                else:
                    logger.error(f"Health check {check_name} returned invalid result type: {type(result)}")
                
                return  # Success, exit retry loop
                
            except asyncio.TimeoutError:
                last_error = f"Timeout after {health_check.timeout}s"
                if attempt < health_check.retries:
                    await asyncio.sleep(health_check.retry_delay)
                    continue
            except Exception as e:
                last_error = str(e)
                if attempt < health_check.retries:
                    await asyncio.sleep(health_check.retry_delay)
                    continue
        
        # All retries failed
        failed_result = ComponentHealth(
            name=check_name,
            status=HealthStatus.UNHEALTHY,
            message=f"Health check failed after {health_check.retries + 1} attempts: {last_error}",
            response_time=time.time() - start_time,
            last_error=last_error,
            checks_failed=1
        )
        
        self.component_health[check_name] = failed_result
        self._store_health_history(check_name, failed_result)
        
        logger.error(f"Health check {check_name} failed: {last_error}")
    
    def _store_health_history(self, check_name: str, health: ComponentHealth):
        """Store health check result in history"""
        if check_name not in self.health_history:
            self.health_history[check_name] = []
        
        # Keep last 100 results
        history = self.health_history[check_name]
        history.append({
            'timestamp': health.timestamp,
            'status': health.status.value,
            'response_time': health.response_time,
            'message': health.message
        })
        
        if len(history) > 100:
            history.pop(0)
    
    async def check_single(self, check_name: str) -> Optional[ComponentHealth]:
        """Perform a single health check immediately"""
        if check_name not in self.registered_checks:
            return None
        
        health_check = self.registered_checks[check_name]
        await self._perform_check(check_name, health_check)
        return self.component_health.get(check_name)
    
    async def check_all(self) -> Dict[str, ComponentHealth]:
        """Perform all health checks immediately"""
        tasks = []
        for check_name in self.registered_checks:
            tasks.append(self.check_single(check_name))
        
        await asyncio.gather(*tasks, return_exceptions=True)
        return self.component_health.copy()
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get comprehensive system health status"""
        if not self.component_health:
            return {
                'overall_status': HealthStatus.UNKNOWN.value,
                'message': 'No health checks have been performed yet',
                'timestamp': datetime.now().isoformat(),
                'components': {}
            }
        
        # Calculate overall status
        statuses = [health.status for health in self.component_health.values()]
        critical_checks = [
            name for name, check in self.registered_checks.items()
            if check.critical and name in self.component_health
        ]
        
        # Overall status logic
        if any(self.component_health[name].status == HealthStatus.UNHEALTHY for name in critical_checks):
            overall_status = HealthStatus.UNHEALTHY
            message = "One or more critical components are unhealthy"
        elif any(health.status == HealthStatus.UNHEALTHY for health in self.component_health.values()):
            overall_status = HealthStatus.WARNING
            message = "One or more non-critical components are unhealthy"
        elif any(health.status == HealthStatus.WARNING for health in self.component_health.values()):
            overall_status = HealthStatus.WARNING
            message = "One or more components have warnings"
        elif all(health.status == HealthStatus.HEALTHY for health in self.component_health.values()):
            overall_status = HealthStatus.HEALTHY
            message = "All components are healthy"
        else:
            overall_status = HealthStatus.UNKNOWN
            message = "Unable to determine overall health status"
        
        # Component summary
        component_summary = {}
        for name, health in self.component_health.items():
            component_summary[name] = {
                'status': health.status.value,
                'message': health.message,
                'response_time': health.response_time,
                'last_check': health.timestamp.isoformat(),
                'is_critical': self.registered_checks[name].critical if name in self.registered_checks else False
            }
        
        return {
            'overall_status': overall_status.value,
            'message': message,
            'timestamp': datetime.now().isoformat(),
            'components': component_summary,
            'summary': {
                'total_checks': len(self.component_health),
                'healthy': sum(1 for h in self.component_health.values() if h.status == HealthStatus.HEALTHY),
                'warning': sum(1 for h in self.component_health.values() if h.status == HealthStatus.WARNING),
                'unhealthy': sum(1 for h in self.component_health.values() if h.status == HealthStatus.UNHEALTHY),
                'unknown': sum(1 for h in self.component_health.values() if h.status == HealthStatus.UNKNOWN),
                'critical_checks': len(critical_checks),
                'monitoring_active': self.running
            }
        }
    
    def get_component_health(self, component_name: str) -> Optional[Dict[str, Any]]:
        """Get health status for a specific component"""
        if component_name not in self.component_health:
            return None
        
        health = self.component_health[component_name]
        history = self.health_history.get(component_name, [])
        
        return {
            'current': health.to_dict(),
            'history': history[-10:],  # Last 10 entries
            'check_config': {
                'interval': self.registered_checks[component_name].interval,
                'critical': self.registered_checks[component_name].critical,
                'check_type': self.registered_checks[component_name].check_type.value
            } if component_name in self.registered_checks else None
        }
    
    def get_health_trends(self, hours: int = 24) -> Dict[str, Any]:
        """Get health trends over time"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        trends = {}
        
        for component, history in self.health_history.items():
            recent_history = [
                entry for entry in history
                if entry['timestamp'] > cutoff_time
            ]
            
            if not recent_history:
                continue
            
            # Calculate trend metrics
            status_counts = {}
            response_times = []
            
            for entry in recent_history:
                status = entry['status']
                status_counts[status] = status_counts.get(status, 0) + 1
                if entry['response_time'] > 0:
                    response_times.append(entry['response_time'])
            
            trends[component] = {
                'total_checks': len(recent_history),
                'status_distribution': status_counts,
                'avg_response_time': sum(response_times) / len(response_times) if response_times else 0,
                'max_response_time': max(response_times) if response_times else 0,
                'availability_percent': (status_counts.get('healthy', 0) / len(recent_history)) * 100
            }
        
        return trends
    
    def get_manager_info(self) -> Dict[str, Any]:
        """Get information about the health check manager"""
        return {
            'running': self.running,
            'registered_checks': len(self.registered_checks),
            'active_tasks': len(self.check_tasks),
            'monitored_components': len(self.component_health),
            'checks_by_type': {
                check_type.value: sum(
                    1 for check in self.registered_checks.values()
                    if check.check_type == check_type
                ) for check_type in CheckType
            },
            'critical_checks': sum(
                1 for check in self.registered_checks.values()
                if check.critical
            )
        }