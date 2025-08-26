"""
Security auditing and logging system for RAG-Anything.

This module provides comprehensive security event tracking:
- Authentication events
- Authorization failures  
- Suspicious activity detection
- Compliance logging
- Incident reporting
"""

import json
import time
import hashlib
import asyncio
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import redis.asyncio as aioredis
import logging
from pathlib import Path

# Configure logger
logger = logging.getLogger(__name__)


class SecurityEventType(Enum):
    """Types of security events"""
    AUTHENTICATION_SUCCESS = "auth_success"
    AUTHENTICATION_FAILURE = "auth_failure"
    AUTHORIZATION_FAILURE = "authz_failure"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    ADMIN_ACTION = "admin_action"
    API_KEY_CREATED = "api_key_created"
    API_KEY_REVOKED = "api_key_revoked"
    SESSION_CREATED = "session_created"
    SESSION_EXPIRED = "session_expired"
    SECURITY_VIOLATION = "security_violation"
    SYSTEM_EVENT = "system_event"


class SeverityLevel(Enum):
    """Security event severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityEventSource(Enum):
    """Source of security events"""
    API = "api"
    WEB_UI = "web_ui"
    SYSTEM = "system"
    CRON = "cron"
    EXTERNAL = "external"


@dataclass
class SecurityEvent:
    """Security event data structure"""
    
    # Basic event information
    event_type: SecurityEventType
    severity: SeverityLevel
    source: SecurityEventSource
    timestamp: datetime = field(default_factory=datetime.now)
    
    # User and session context
    user_id: Optional[str] = None
    username: Optional[str] = None
    session_id: Optional[str] = None
    
    # Request context
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    endpoint: Optional[str] = None
    method: Optional[str] = None
    
    # Event details
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    request_id: Optional[str] = None
    correlation_id: Optional[str] = None
    tags: Set[str] = field(default_factory=set)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for storage/transmission"""
        return {
            'event_id': self.generate_event_id(),
            'event_type': self.event_type.value,
            'severity': self.severity.value,
            'source': self.source.value,
            'timestamp': self.timestamp.isoformat(),
            'user_id': self.user_id,
            'username': self.username,
            'session_id': self.session_id,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'endpoint': self.endpoint,
            'method': self.method,
            'message': self.message,
            'details': self.details,
            'request_id': self.request_id,
            'correlation_id': self.correlation_id,
            'tags': list(self.tags)
        }
    
    def generate_event_id(self) -> str:
        """Generate unique event ID"""
        content = f"{self.timestamp.isoformat()}{self.event_type.value}{self.user_id or ''}{self.ip_address or ''}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def add_tag(self, tag: str) -> None:
        """Add tag to event"""
        self.tags.add(tag)
    
    def add_detail(self, key: str, value: Any) -> None:
        """Add detail to event"""
        self.details[key] = value


@dataclass
class AuditConfig:
    """Configuration for security auditing"""
    
    # Storage configuration
    redis_prefix: str = "raganything:audit"
    log_retention_days: int = 90
    max_events_per_day: int = 100000
    
    # File logging
    enable_file_logging: bool = True
    log_file_path: str = "./logs/security_audit.log"
    log_file_rotation_mb: int = 100
    log_file_backup_count: int = 10
    
    # Event filtering
    log_levels: Set[SeverityLevel] = field(default_factory=lambda: {
        SeverityLevel.MEDIUM, SeverityLevel.HIGH, SeverityLevel.CRITICAL
    })
    log_event_types: Set[SecurityEventType] = field(default_factory=lambda: set(SecurityEventType))
    
    # Real-time alerting
    enable_real_time_alerts: bool = True
    alert_threshold_critical: int = 1  # Alert immediately for critical events
    alert_threshold_high: int = 5  # Alert after 5 high severity events
    alert_window_minutes: int = 10
    
    # Compliance settings
    enable_compliance_logging: bool = True
    compliance_standards: List[str] = field(default_factory=lambda: ["SOC2", "GDPR", "HIPAA"])


class AuditLogger:
    """File-based audit logger with rotation"""
    
    def __init__(self, config: AuditConfig):
        self.config = config
        self.logger = self._setup_logger()
    
    def _setup_logger(self) -> logging.Logger:
        """Setup rotating file logger for security events"""
        audit_logger = logging.getLogger("security_audit")
        audit_logger.setLevel(logging.INFO)
        
        if not audit_logger.handlers:
            # Create log directory if it doesn't exist
            log_path = Path(self.config.log_file_path)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Setup rotating file handler
            from logging.handlers import RotatingFileHandler
            handler = RotatingFileHandler(
                self.config.log_file_path,
                maxBytes=self.config.log_file_rotation_mb * 1024 * 1024,
                backupCount=self.config.log_file_backup_count
            )
            
            # JSON formatter for structured logging
            formatter = logging.Formatter('%(message)s')
            handler.setFormatter(formatter)
            
            audit_logger.addHandler(handler)
        
        return audit_logger
    
    def log_event(self, event: SecurityEvent) -> None:
        """Log security event to file"""
        try:
            if event.severity in self.config.log_levels:
                event_json = json.dumps(event.to_dict(), ensure_ascii=False)
                self.logger.info(event_json)
        except Exception as e:
            logger.error(f"Failed to log security event: {e}")


class SecurityAuditor:
    """
    Main security auditing system.
    
    Handles collection, storage, analysis, and reporting of security events.
    """
    
    def __init__(self, config: AuditConfig, redis_client: Optional[aioredis.Redis] = None):
        self.config = config
        self.redis_client = redis_client
        self.audit_logger = AuditLogger(config) if config.enable_file_logging else None
        
        # Event buffers for real-time analysis
        self._event_buffer = []
        self._alert_counts = {}
        
        # Metrics tracking
        self._metrics = {
            'total_events': 0,
            'events_by_type': {},
            'events_by_severity': {},
            'events_by_user': {},
            'events_by_ip': {}
        }
        
        # Start background tasks
        self._cleanup_task = None
        self._alert_task = None
        
    async def initialize(self) -> None:
        """Initialize auditing system"""
        # Start background tasks
        self._cleanup_task = asyncio.create_task(self._cleanup_old_events())
        self._alert_task = asyncio.create_task(self._process_alerts())
        
        logger.info("Security auditor initialized")
    
    async def finalize(self) -> None:
        """Cleanup auditing system"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
        if self._alert_task:
            self._alert_task.cancel()
        
        logger.info("Security auditor finalized")
    
    async def log_event(self, event: SecurityEvent) -> None:
        """
        Log a security event.
        
        Args:
            event: SecurityEvent to log
        """
        try:
            # Add to buffer for real-time processing
            self._event_buffer.append(event)
            
            # Update metrics
            self._update_metrics(event)
            
            # Store in Redis if available
            await self._store_event_redis(event)
            
            # Log to file if enabled
            if self.audit_logger:
                self.audit_logger.log_event(event)
            
            # Process for real-time alerts
            await self._process_event_for_alerts(event)
            
            logger.debug(f"Logged security event: {event.event_type.value}")
            
        except Exception as e:
            logger.error(f"Failed to log security event: {e}")
    
    async def log_authentication_success(
        self, 
        user_id: str, 
        username: str, 
        method: str,
        ip_address: str = None,
        session_id: str = None,
        **kwargs
    ) -> None:
        """Log successful authentication"""
        event = SecurityEvent(
            event_type=SecurityEventType.AUTHENTICATION_SUCCESS,
            severity=SeverityLevel.LOW,
            source=SecurityEventSource.API,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            session_id=session_id,
            message=f"User {username} authenticated successfully using {method}",
            details={'auth_method': method, **kwargs}
        )
        event.add_tag('authentication')
        await self.log_event(event)
    
    async def log_authentication_failure(
        self,
        username: str = None,
        ip_address: str = None,
        reason: str = "Invalid credentials",
        **kwargs
    ) -> None:
        """Log failed authentication"""
        event = SecurityEvent(
            event_type=SecurityEventType.AUTHENTICATION_FAILURE,
            severity=SeverityLevel.MEDIUM,
            source=SecurityEventSource.API,
            username=username,
            ip_address=ip_address,
            message=f"Authentication failed for {username or 'unknown'}: {reason}",
            details={'failure_reason': reason, **kwargs}
        )
        event.add_tag('authentication')
        event.add_tag('failure')
        await self.log_event(event)
    
    async def log_authorization_failure(
        self,
        user_id: str,
        username: str,
        resource: str,
        action: str,
        ip_address: str = None,
        **kwargs
    ) -> None:
        """Log authorization failure"""
        event = SecurityEvent(
            event_type=SecurityEventType.AUTHORIZATION_FAILURE,
            severity=SeverityLevel.HIGH,
            source=SecurityEventSource.API,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            message=f"Access denied: {username} attempted {action} on {resource}",
            details={'resource': resource, 'action': action, **kwargs}
        )
        event.add_tag('authorization')
        event.add_tag('access_denied')
        await self.log_event(event)
    
    async def log_rate_limit_exceeded(
        self,
        identifier: str,
        endpoint: str = None,
        limit: int = None,
        current_usage: int = None,
        ip_address: str = None,
        **kwargs
    ) -> None:
        """Log rate limit exceeded"""
        event = SecurityEvent(
            event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
            severity=SeverityLevel.MEDIUM,
            source=SecurityEventSource.API,
            ip_address=ip_address,
            endpoint=endpoint,
            message=f"Rate limit exceeded for {identifier}",
            details={
                'identifier': identifier,
                'limit': limit,
                'current_usage': current_usage,
                **kwargs
            }
        )
        event.add_tag('rate_limiting')
        await self.log_event(event)
    
    async def log_suspicious_activity(
        self,
        user_id: str = None,
        ip_address: str = None,
        activity_type: str = "unknown",
        description: str = "",
        **kwargs
    ) -> None:
        """Log suspicious activity"""
        event = SecurityEvent(
            event_type=SecurityEventType.SUSPICIOUS_ACTIVITY,
            severity=SeverityLevel.HIGH,
            source=SecurityEventSource.SYSTEM,
            user_id=user_id,
            ip_address=ip_address,
            message=f"Suspicious activity detected: {activity_type}",
            details={
                'activity_type': activity_type,
                'description': description,
                **kwargs
            }
        )
        event.add_tag('suspicious')
        event.add_tag('security_violation')
        await self.log_event(event)
    
    async def log_data_access(
        self,
        user_id: str,
        username: str,
        resource: str,
        action: str = "read",
        ip_address: str = None,
        **kwargs
    ) -> None:
        """Log data access events"""
        event = SecurityEvent(
            event_type=SecurityEventType.DATA_ACCESS,
            severity=SeverityLevel.LOW,
            source=SecurityEventSource.API,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            message=f"{username} accessed {resource}",
            details={'resource': resource, 'action': action, **kwargs}
        )
        event.add_tag('data_access')
        await self.log_event(event)
    
    async def _store_event_redis(self, event: SecurityEvent) -> None:
        """Store event in Redis for querying"""
        if not self.redis_client:
            return
        
        try:
            # Store event with time-based key for efficient querying
            event_key = f"{self.config.redis_prefix}:event:{event.timestamp.strftime('%Y%m%d')}:{event.generate_event_id()}"
            
            # Store event data
            await self.redis_client.setex(
                event_key,
                self.config.log_retention_days * 24 * 3600,
                json.dumps(event.to_dict())
            )
            
            # Add to time-based index
            date_key = f"{self.config.redis_prefix}:index:date:{event.timestamp.strftime('%Y%m%d')}"
            await self.redis_client.zadd(
                date_key, 
                {event.generate_event_id(): event.timestamp.timestamp()}
            )
            await self.redis_client.expire(date_key, self.config.log_retention_days * 24 * 3600)
            
            # Add to user index if applicable
            if event.user_id:
                user_key = f"{self.config.redis_prefix}:index:user:{event.user_id}"
                await self.redis_client.zadd(
                    user_key,
                    {event.generate_event_id(): event.timestamp.timestamp()}
                )
                await self.redis_client.expire(user_key, self.config.log_retention_days * 24 * 3600)
            
            # Add to IP index if applicable
            if event.ip_address:
                ip_key = f"{self.config.redis_prefix}:index:ip:{event.ip_address}"
                await self.redis_client.zadd(
                    ip_key,
                    {event.generate_event_id(): event.timestamp.timestamp()}
                )
                await self.redis_client.expire(ip_key, self.config.log_retention_days * 24 * 3600)
                
        except Exception as e:
            logger.error(f"Failed to store event in Redis: {e}")
    
    def _update_metrics(self, event: SecurityEvent) -> None:
        """Update internal metrics"""
        self._metrics['total_events'] += 1
        
        # Update by type
        event_type = event.event_type.value
        self._metrics['events_by_type'][event_type] = self._metrics['events_by_type'].get(event_type, 0) + 1
        
        # Update by severity
        severity = event.severity.value
        self._metrics['events_by_severity'][severity] = self._metrics['events_by_severity'].get(severity, 0) + 1
        
        # Update by user
        if event.user_id:
            self._metrics['events_by_user'][event.user_id] = self._metrics['events_by_user'].get(event.user_id, 0) + 1
        
        # Update by IP
        if event.ip_address:
            self._metrics['events_by_ip'][event.ip_address] = self._metrics['events_by_ip'].get(event.ip_address, 0) + 1
    
    async def _process_event_for_alerts(self, event: SecurityEvent) -> None:
        """Process event for real-time alerting"""
        if not self.config.enable_real_time_alerts:
            return
        
        try:
            # Check for immediate critical alerts
            if event.severity == SeverityLevel.CRITICAL:
                await self._trigger_alert(event, "Critical security event detected")
            
            # Count high severity events
            elif event.severity == SeverityLevel.HIGH:
                alert_key = f"high_severity_{event.timestamp.strftime('%Y%m%d_%H%M')}"
                self._alert_counts[alert_key] = self._alert_counts.get(alert_key, 0) + 1
                
                if self._alert_counts[alert_key] >= self.config.alert_threshold_high:
                    await self._trigger_alert(event, f"Multiple high severity events: {self._alert_counts[alert_key]}")
                    
        except Exception as e:
            logger.error(f"Error processing event for alerts: {e}")
    
    async def _trigger_alert(self, event: SecurityEvent, alert_message: str) -> None:
        """Trigger security alert"""
        logger.critical(f"SECURITY ALERT: {alert_message} - Event: {event.to_dict()}")
        
        # In production, this would integrate with:
        # - Email notifications
        # - Slack/Teams alerts
        # - PagerDuty/OpsGenie
        # - SIEM systems
    
    async def query_events(
        self,
        start_date: datetime = None,
        end_date: datetime = None,
        user_id: str = None,
        ip_address: str = None,
        event_types: List[SecurityEventType] = None,
        severity_levels: List[SeverityLevel] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Query security events with various filters.
        
        Args:
            start_date: Start date for query
            end_date: End date for query
            user_id: Filter by user ID
            ip_address: Filter by IP address
            event_types: Filter by event types
            severity_levels: Filter by severity levels
            limit: Maximum number of events to return
            
        Returns:
            List of matching events
        """
        if not self.redis_client:
            return []
        
        try:
            events = []
            
            # Default date range if not provided
            if not end_date:
                end_date = datetime.now()
            if not start_date:
                start_date = end_date - timedelta(days=7)
            
            # Query by date range
            current_date = start_date.date()
            while current_date <= end_date.date():
                date_key = f"{self.config.redis_prefix}:index:date:{current_date.strftime('%Y%m%d')}"
                
                # Get event IDs for the date
                event_ids = await self.redis_client.zrangebyscore(
                    date_key,
                    start_date.timestamp(),
                    end_date.timestamp()
                )
                
                # Fetch event details
                for event_id in event_ids:
                    event_key = f"{self.config.redis_prefix}:event:{current_date.strftime('%Y%m%d')}:{event_id}"
                    event_data = await self.redis_client.get(event_key)
                    
                    if event_data:
                        event = json.loads(event_data)
                        
                        # Apply filters
                        if self._matches_filters(event, user_id, ip_address, event_types, severity_levels):
                            events.append(event)
                            
                            if len(events) >= limit:
                                break
                
                if len(events) >= limit:
                    break
                
                current_date += timedelta(days=1)
            
            # Sort by timestamp descending
            events.sort(key=lambda x: x['timestamp'], reverse=True)
            
            return events[:limit]
            
        except Exception as e:
            logger.error(f"Error querying events: {e}")
            return []
    
    def _matches_filters(
        self,
        event: Dict[str, Any],
        user_id: str = None,
        ip_address: str = None,
        event_types: List[SecurityEventType] = None,
        severity_levels: List[SeverityLevel] = None
    ) -> bool:
        """Check if event matches query filters"""
        
        if user_id and event.get('user_id') != user_id:
            return False
        
        if ip_address and event.get('ip_address') != ip_address:
            return False
        
        if event_types and SecurityEventType(event['event_type']) not in event_types:
            return False
        
        if severity_levels and SeverityLevel(event['severity']) not in severity_levels:
            return False
        
        return True
    
    async def generate_security_report(
        self,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> Dict[str, Any]:
        """
        Generate security report for a time period.
        
        Args:
            start_date: Start date for report
            end_date: End date for report
            
        Returns:
            Security report with metrics and insights
        """
        if not end_date:
            end_date = datetime.now()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        # Query all events in the period
        events = await self.query_events(
            start_date=start_date,
            end_date=end_date,
            limit=10000  # Get more events for analysis
        )
        
        # Analyze events
        report = {
            'report_period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'duration_days': (end_date - start_date).days
            },
            'summary': {
                'total_events': len(events),
                'events_by_type': {},
                'events_by_severity': {},
                'unique_users': set(),
                'unique_ips': set()
            },
            'security_insights': [],
            'recommendations': []
        }
        
        # Analyze events
        for event in events:
            # Count by type
            event_type = event['event_type']
            report['summary']['events_by_type'][event_type] = report['summary']['events_by_type'].get(event_type, 0) + 1
            
            # Count by severity
            severity = event['severity']
            report['summary']['events_by_severity'][severity] = report['summary']['events_by_severity'].get(severity, 0) + 1
            
            # Track unique users and IPs
            if event.get('user_id'):
                report['summary']['unique_users'].add(event['user_id'])
            if event.get('ip_address'):
                report['summary']['unique_ips'].add(event['ip_address'])
        
        # Convert sets to counts
        report['summary']['unique_users'] = len(report['summary']['unique_users'])
        report['summary']['unique_ips'] = len(report['summary']['unique_ips'])
        
        # Generate insights
        self._generate_security_insights(report, events)
        
        return report
    
    def _generate_security_insights(self, report: Dict[str, Any], events: List[Dict[str, Any]]) -> None:
        """Generate security insights from events"""
        insights = report['security_insights']
        recommendations = report['recommendations']
        
        # Check for high failure rates
        auth_failures = report['summary']['events_by_type'].get('auth_failure', 0)
        auth_successes = report['summary']['events_by_type'].get('auth_success', 0)
        
        if auth_failures > 0 and auth_successes > 0:
            failure_rate = auth_failures / (auth_failures + auth_successes)
            if failure_rate > 0.1:  # More than 10% failure rate
                insights.append(f"High authentication failure rate: {failure_rate:.1%}")
                recommendations.append("Review authentication logs and consider implementing account lockout policies")
        
        # Check for suspicious activity
        suspicious_events = report['summary']['events_by_type'].get('suspicious_activity', 0)
        if suspicious_events > 0:
            insights.append(f"Detected {suspicious_events} suspicious activity events")
            recommendations.append("Investigate suspicious activities and consider tightening security controls")
        
        # Check for rate limiting issues
        rate_limit_events = report['summary']['events_by_type'].get('rate_limit_exceeded', 0)
        if rate_limit_events > 10:
            insights.append(f"High number of rate limiting events: {rate_limit_events}")
            recommendations.append("Review rate limiting policies and client behavior patterns")
    
    async def _cleanup_old_events(self) -> None:
        """Background task to cleanup old events"""
        while True:
            try:
                await asyncio.sleep(24 * 3600)  # Run daily
                
                if self.redis_client:
                    # Calculate cutoff date
                    cutoff_date = datetime.now() - timedelta(days=self.config.log_retention_days)
                    
                    # Clean up old date indexes
                    current_date = cutoff_date.date()
                    for _ in range(7):  # Clean up a week's worth at a time
                        date_key = f"{self.config.redis_prefix}:index:date:{current_date.strftime('%Y%m%d')}"
                        await self.redis_client.delete(date_key)
                        current_date -= timedelta(days=1)
                    
                    logger.info("Cleaned up old security events")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error cleaning up old events: {e}")
    
    async def _process_alerts(self) -> None:
        """Background task to process alerts"""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                # Clean up old alert counts
                current_time = datetime.now()
                expired_keys = [
                    key for key in self._alert_counts.keys()
                    if key.endswith(
                        (current_time - timedelta(minutes=self.config.alert_window_minutes))
                        .strftime('%Y%m%d_%H%M')
                    )
                ]
                
                for key in expired_keys:
                    del self._alert_counts[key]
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing alerts: {e}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current security metrics"""
        return {
            'total_events': self._metrics['total_events'],
            'events_by_type': dict(self._metrics['events_by_type']),
            'events_by_severity': dict(self._metrics['events_by_severity']),
            'top_users': dict(sorted(
                self._metrics['events_by_user'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]),
            'top_ips': dict(sorted(
                self._metrics['events_by_ip'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]),
            'buffer_size': len(self._event_buffer),
            'alert_counts': dict(self._alert_counts)
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for security auditing system"""
        status = {
            'redis_connected': False,
            'file_logging': self.config.enable_file_logging,
            'total_events': self._metrics['total_events'],
            'buffer_size': len(self._event_buffer),
            'timestamp': time.time()
        }
        
        try:
            if self.redis_client:
                await self.redis_client.ping()
                status['redis_connected'] = True
        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")
        
        return status