"""
Security framework for RAG-Anything integration.

This module provides comprehensive security features including:
- Input validation and sanitization
- Rate limiting with multiple strategies
- Authentication and authorization
- Security auditing and logging
- Request monitoring and anomaly detection
"""

from .input_validator import InputValidator, ValidationError, ValidationResult
from .rate_limiter import (
    RateLimiter, 
    TokenBucketRateLimiter,
    SlidingWindowRateLimiter,
    RateLimitError,
    RateLimitConfig
)
from .auth_middleware import (
    AuthenticationManager,
    APIKeyAuth,
    JWTAuth,
    AuthenticationError,
    AuthorizationError
)
from .security_audit import SecurityAuditor, SecurityEvent, AuditLogger
from .security_headers import SecurityHeadersManager
from .anomaly_detector import AnomalyDetector, SecurityAnomaly

__all__ = [
    # Input validation
    "InputValidator",
    "ValidationError", 
    "ValidationResult",
    
    # Rate limiting
    "RateLimiter",
    "TokenBucketRateLimiter",
    "SlidingWindowRateLimiter",
    "RateLimitError",
    "RateLimitConfig",
    
    # Authentication
    "AuthenticationManager",
    "APIKeyAuth",
    "JWTAuth", 
    "AuthenticationError",
    "AuthorizationError",
    
    # Security auditing
    "SecurityAuditor",
    "SecurityEvent",
    "AuditLogger",
    
    # Security headers
    "SecurityHeadersManager",
    
    # Anomaly detection
    "AnomalyDetector",
    "SecurityAnomaly",
]