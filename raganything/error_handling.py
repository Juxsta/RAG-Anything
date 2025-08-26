"""
Comprehensive error handling and logging for RAG-Anything.

Provides structured error handling, logging configuration, and recovery mechanisms
for the entire RAG-Anything system including Graphiti integration.
"""

import logging
import logging.handlers
import traceback
import sys
import os
import json
from typing import Any, Dict, Optional, List, Union, Type, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from contextlib import asynccontextmanager, contextmanager
import asyncio
from pathlib import Path


class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for better classification"""
    INITIALIZATION = "initialization"
    PARSING = "parsing"
    PROCESSING = "processing"
    DATABASE = "database"
    API = "api"
    AUTHENTICATION = "authentication"
    VALIDATION = "validation"
    CONFIGURATION = "configuration"
    NETWORK = "network"
    PERMISSION = "permission"
    RESOURCE = "resource"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


@dataclass
class ErrorContext:
    """Context information for errors"""
    operation: str
    component: str
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    session_id: Optional[str] = None
    additional_data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class RAGAnythingError(Exception):
    """Base exception class for RAG-Anything"""
    
    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        context: Optional[ErrorContext] = None,
        original_error: Optional[Exception] = None,
        recoverable: bool = True,
        user_message: Optional[str] = None
    ):
        super().__init__(message)
        self.message = message
        self.category = category
        self.severity = severity
        self.context = context
        self.original_error = original_error
        self.recoverable = recoverable
        self.user_message = user_message or self._generate_user_message()
        self.timestamp = datetime.now()
        
    def _generate_user_message(self) -> str:
        """Generate a user-friendly error message"""
        if self.severity == ErrorSeverity.CRITICAL:
            return "A critical error occurred. Please contact system administrator."
        elif self.category == ErrorCategory.AUTHENTICATION:
            return "Authentication failed. Please check your credentials."
        elif self.category == ErrorCategory.PERMISSION:
            return "Access denied. You don't have permission for this operation."
        elif self.category == ErrorCategory.VALIDATION:
            return "Invalid input provided. Please check your data and try again."
        elif self.category == ErrorCategory.NETWORK:
            return "Network error occurred. Please check your connection and try again."
        elif self.category == ErrorCategory.DATABASE:
            return "Database error occurred. Please try again later."
        elif self.category == ErrorCategory.TIMEOUT:
            return "Operation timed out. Please try again."
        else:
            return "An error occurred while processing your request."
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for logging/serialization"""
        return {
            "message": self.message,
            "user_message": self.user_message,
            "category": self.category.value,
            "severity": self.severity.value,
            "recoverable": self.recoverable,
            "timestamp": self.timestamp.isoformat(),
            "context": {
                "operation": self.context.operation if self.context else None,
                "component": self.context.component if self.context else None,
                "user_id": self.context.user_id if self.context else None,
                "request_id": self.context.request_id if self.context else None,
                "additional_data": self.context.additional_data if self.context else {}
            },
            "original_error": {
                "type": type(self.original_error).__name__ if self.original_error else None,
                "message": str(self.original_error) if self.original_error else None,
                "traceback": traceback.format_exception(
                    type(self.original_error), 
                    self.original_error, 
                    self.original_error.__traceback__
                ) if self.original_error else None
            }
        }


class GraphitiError(RAGAnythingError):
    """Graphiti-specific errors"""
    
    def __init__(self, message: str, **kwargs):
        kwargs.setdefault('category', ErrorCategory.DATABASE)
        super().__init__(message, **kwargs)


class ParsingError(RAGAnythingError):
    """Document parsing errors"""
    
    def __init__(self, message: str, **kwargs):
        kwargs.setdefault('category', ErrorCategory.PARSING)
        super().__init__(message, **kwargs)


class ProcessingError(RAGAnythingError):
    """Content processing errors"""
    
    def __init__(self, message: str, **kwargs):
        kwargs.setdefault('category', ErrorCategory.PROCESSING)
        super().__init__(message, **kwargs)


class APIError(RAGAnythingError):
    """API-related errors"""
    
    def __init__(self, message: str, **kwargs):
        kwargs.setdefault('category', ErrorCategory.API)
        super().__init__(message, **kwargs)


class ValidationError(RAGAnythingError):
    """Input validation errors"""
    
    def __init__(self, message: str, **kwargs):
        kwargs.setdefault('category', ErrorCategory.VALIDATION)
        kwargs.setdefault('severity', ErrorSeverity.LOW)
        super().__init__(message, **kwargs)


class ConfigurationError(RAGAnythingError):
    """Configuration-related errors"""
    
    def __init__(self, message: str, **kwargs):
        kwargs.setdefault('category', ErrorCategory.CONFIGURATION)
        kwargs.setdefault('severity', ErrorSeverity.HIGH)
        super().__init__(message, **kwargs)


class ErrorHandler:
    """Central error handler with logging and recovery mechanisms"""
    
    def __init__(self, log_dir: str = "./logs", max_log_size_mb: int = 100):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Initialize loggers
        self.logger = self._setup_logger()
        self.error_logger = self._setup_error_logger(max_log_size_mb)
        
        # Error statistics
        self.error_counts: Dict[str, int] = {}
        self.last_errors: List[RAGAnythingError] = []
        self.max_recent_errors = 100
        
        # Recovery callbacks
        self.recovery_handlers: Dict[ErrorCategory, List[Callable]] = {}
        
        self.logger.info("Error handler initialized")
    
    def _setup_logger(self) -> logging.Logger:
        """Set up general application logger"""
        logger = logging.getLogger("raganything")
        logger.setLevel(logging.DEBUG)
        
        if not logger.handlers:  # Avoid duplicate handlers
            # Console handler
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            console_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)
            
            # File handler
            file_handler = logging.handlers.RotatingFileHandler(
                self.log_dir / "raganything.log",
                maxBytes=50 * 1024 * 1024,  # 50MB
                backupCount=5
            )
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        
        return logger
    
    def _setup_error_logger(self, max_size_mb: int) -> logging.Logger:
        """Set up dedicated error logger with structured logging"""
        error_logger = logging.getLogger("raganything.errors")
        error_logger.setLevel(logging.ERROR)
        
        if not error_logger.handlers:
            # Structured error log handler
            error_handler = logging.handlers.RotatingFileHandler(
                self.log_dir / "errors.json",
                maxBytes=max_size_mb * 1024 * 1024,
                backupCount=10
            )
            error_handler.setLevel(logging.ERROR)
            
            # Custom formatter for JSON structured logging
            class JSONFormatter(logging.Formatter):
                def format(self, record):
                    log_entry = {
                        "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                        "level": record.levelname,
                        "logger": record.name,
                        "message": record.getMessage(),
                        "module": record.module,
                        "function": record.funcName,
                        "line": record.lineno,
                    }
                    
                    if hasattr(record, 'error_data'):
                        log_entry.update(record.error_data)
                    
                    return json.dumps(log_entry)
            
            error_handler.setFormatter(JSONFormatter())
            error_logger.addHandler(error_handler)
        
        return error_logger
    
    def handle_error(
        self, 
        error: Union[Exception, RAGAnythingError], 
        context: Optional[ErrorContext] = None,
        auto_recover: bool = True
    ) -> RAGAnythingError:
        """Handle an error with logging and optional recovery"""
        
        # Convert to RAGAnythingError if needed
        if not isinstance(error, RAGAnythingError):
            rag_error = self._convert_to_rag_error(error, context)
        else:
            rag_error = error
            if context and not rag_error.context:
                rag_error.context = context
        
        # Update statistics
        category_key = rag_error.category.value
        self.error_counts[category_key] = self.error_counts.get(category_key, 0) + 1
        
        # Store recent error
        self.last_errors.append(rag_error)
        if len(self.last_errors) > self.max_recent_errors:
            self.last_errors.pop(0)
        
        # Log the error
        self._log_error(rag_error)
        
        # Attempt recovery if enabled and error is recoverable
        if auto_recover and rag_error.recoverable:
            self._attempt_recovery(rag_error)
        
        return rag_error
    
    def _convert_to_rag_error(
        self, 
        error: Exception, 
        context: Optional[ErrorContext]
    ) -> RAGAnythingError:
        """Convert standard exception to RAGAnythingError"""
        
        # Determine category based on exception type
        category = ErrorCategory.UNKNOWN
        severity = ErrorSeverity.MEDIUM
        
        if isinstance(error, (ConnectionError, OSError)):
            category = ErrorCategory.NETWORK
        elif isinstance(error, ValueError):
            category = ErrorCategory.VALIDATION
            severity = ErrorSeverity.LOW
        elif isinstance(error, PermissionError):
            category = ErrorCategory.PERMISSION
        elif isinstance(error, FileNotFoundError):
            category = ErrorCategory.RESOURCE
        elif isinstance(error, TimeoutError):
            category = ErrorCategory.TIMEOUT
        elif "database" in str(error).lower() or "sql" in str(error).lower():
            category = ErrorCategory.DATABASE
        elif "config" in str(error).lower():
            category = ErrorCategory.CONFIGURATION
            severity = ErrorSeverity.HIGH
        
        return RAGAnythingError(
            message=str(error),
            category=category,
            severity=severity,
            context=context,
            original_error=error
        )
    
    def _log_error(self, error: RAGAnythingError) -> None:
        """Log error with appropriate level and structured data"""
        
        # Prepare structured error data
        error_data = error.to_dict()
        
        # Log to general logger based on severity
        if error.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(f"CRITICAL ERROR: {error.message}")
        elif error.severity == ErrorSeverity.HIGH:
            self.logger.error(f"HIGH SEVERITY: {error.message}")
        elif error.severity == ErrorSeverity.MEDIUM:
            self.logger.warning(f"MEDIUM SEVERITY: {error.message}")
        else:
            self.logger.info(f"LOW SEVERITY: {error.message}")
        
        # Log to structured error logger
        self.error_logger.error(
            f"Error in {error.context.component if error.context else 'unknown'}: {error.message}",
            extra={"error_data": error_data}
        )
        
        # Log original exception traceback if available
        if error.original_error:
            self.logger.debug(
                "Original exception traceback:",
                exc_info=(
                    type(error.original_error),
                    error.original_error,
                    error.original_error.__traceback__
                )
            )
    
    def _attempt_recovery(self, error: RAGAnythingError) -> bool:
        """Attempt to recover from error using registered handlers"""
        try:
            handlers = self.recovery_handlers.get(error.category, [])
            
            for handler in handlers:
                try:
                    self.logger.info(f"Attempting recovery for {error.category.value} error")
                    success = handler(error)
                    if success:
                        self.logger.info(f"Successfully recovered from {error.category.value} error")
                        return True
                except Exception as recovery_error:
                    self.logger.error(f"Recovery handler failed: {recovery_error}")
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error during recovery attempt: {e}")
            return False
    
    def register_recovery_handler(
        self, 
        category: ErrorCategory, 
        handler: Callable[[RAGAnythingError], bool]
    ) -> None:
        """Register a recovery handler for a specific error category"""
        if category not in self.recovery_handlers:
            self.recovery_handlers[category] = []
        
        self.recovery_handlers[category].append(handler)
        self.logger.info(f"Registered recovery handler for {category.value} errors")
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics and recent errors"""
        return {
            "error_counts_by_category": self.error_counts,
            "total_errors": sum(self.error_counts.values()),
            "recent_errors_count": len(self.last_errors),
            "recent_critical_errors": len([
                e for e in self.last_errors 
                if e.severity == ErrorSeverity.CRITICAL
            ]),
            "categories_with_handlers": list(self.recovery_handlers.keys()),
            "last_24h_errors": len([
                e for e in self.last_errors
                if (datetime.now() - e.timestamp).total_seconds() < 86400
            ])
        }
    
    def clear_error_history(self) -> None:
        """Clear error history (useful for testing)"""
        self.error_counts.clear()
        self.last_errors.clear()
        self.logger.info("Error history cleared")


# Global error handler instance
_global_error_handler: Optional[ErrorHandler] = None


def get_error_handler(log_dir: str = "./logs") -> ErrorHandler:
    """Get or create global error handler"""
    global _global_error_handler
    
    if _global_error_handler is None:
        _global_error_handler = ErrorHandler(log_dir)
    
    return _global_error_handler


def handle_error(
    error: Union[Exception, RAGAnythingError], 
    context: Optional[ErrorContext] = None,
    component: str = "unknown",
    operation: str = "unknown",
    user_id: Optional[str] = None,
    auto_recover: bool = True
) -> RAGAnythingError:
    """Convenience function to handle errors with context"""
    
    if not context:
        context = ErrorContext(
            operation=operation,
            component=component,
            user_id=user_id
        )
    
    error_handler = get_error_handler()
    return error_handler.handle_error(error, context, auto_recover)


@contextmanager
def error_context(component: str, operation: str, user_id: Optional[str] = None):
    """Context manager for handling errors in a block of code"""
    context = ErrorContext(
        component=component,
        operation=operation,
        user_id=user_id
    )
    
    try:
        yield context
    except Exception as e:
        handle_error(e, context)
        raise


@asynccontextmanager
async def async_error_context(component: str, operation: str, user_id: Optional[str] = None):
    """Async context manager for handling errors"""
    context = ErrorContext(
        component=component,
        operation=operation,
        user_id=user_id
    )
    
    try:
        yield context
    except Exception as e:
        handle_error(e, context)
        raise


def error_handler_decorator(component: str, operation: str = None):
    """Decorator for automatic error handling"""
    def decorator(func):
        op_name = operation or func.__name__
        
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    context = ErrorContext(
                        component=component,
                        operation=op_name
                    )
                    handled_error = handle_error(e, context)
                    
                    # Re-raise if not recoverable or critical
                    if not handled_error.recoverable or handled_error.severity == ErrorSeverity.CRITICAL:
                        raise handled_error
                    
                    return None  # or appropriate default value
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    context = ErrorContext(
                        component=component,
                        operation=op_name
                    )
                    handled_error = handle_error(e, context)
                    
                    if not handled_error.recoverable or handled_error.severity == ErrorSeverity.CRITICAL:
                        raise handled_error
                    
                    return None
            return sync_wrapper
    
    return decorator


def setup_default_recovery_handlers():
    """Set up default recovery handlers for common error scenarios"""
    error_handler = get_error_handler()
    
    def database_recovery_handler(error: RAGAnythingError) -> bool:
        """Try to recover from database errors"""
        # Could implement connection retry, failover, etc.
        return False
    
    def network_recovery_handler(error: RAGAnythingError) -> bool:
        """Try to recover from network errors"""
        # Could implement retry with exponential backoff
        return False
    
    def timeout_recovery_handler(error: RAGAnythingError) -> bool:
        """Try to recover from timeout errors"""
        # Could implement operation retry with longer timeout
        return False
    
    error_handler.register_recovery_handler(ErrorCategory.DATABASE, database_recovery_handler)
    error_handler.register_recovery_handler(ErrorCategory.NETWORK, network_recovery_handler)
    error_handler.register_recovery_handler(ErrorCategory.TIMEOUT, timeout_recovery_handler)


# Initialize default recovery handlers
setup_default_recovery_handlers()