"""
Comprehensive input validation and sanitization module.

This module provides robust input validation for RAG-Anything,
protecting against injection attacks, malformed data, and 
ensuring data integrity throughout the processing pipeline.
"""

import re
import html
import json
import bleach
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse
import magic
import hashlib
import logging

# Configure logger
logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when input validation fails"""
    
    def __init__(self, field: str, message: str, value: Any = None):
        self.field = field
        self.message = message
        self.value = value
        super().__init__(f"Validation failed for {field}: {message}")


@dataclass
class ValidationResult:
    """Result of input validation"""
    is_valid: bool
    sanitized_data: Dict[str, Any] = field(default_factory=dict)
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_error(self, field: str, message: str, value: Any = None):
        """Add validation error"""
        error = ValidationError(field, message, value)
        self.errors.append(error)
        self.is_valid = False
    
    def add_warning(self, message: str):
        """Add validation warning"""
        self.warnings.append(message)


class InputValidator:
    """
    Comprehensive input validator for RAG-Anything integration.
    
    Provides multiple layers of validation:
    - Data type validation
    - Size and length limits
    - Content sanitization
    - File validation
    - Injection attack prevention
    - Business logic validation
    """
    
    # Allowed HTML tags for sanitization
    ALLOWED_HTML_TAGS = [
        'p', 'br', 'strong', 'em', 'u', 'i', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'ul', 'ol', 'li', 'blockquote', 'code', 'pre'
    ]
    
    # Allowed HTML attributes
    ALLOWED_HTML_ATTRIBUTES = {
        'a': ['href', 'title'],
        'img': ['src', 'alt', 'title'],
    }
    
    # Common injection patterns
    INJECTION_PATTERNS = [
        # SQL injection
        r'(\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b)',
        # XSS patterns
        r'(<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>)',
        r'(javascript:|vbscript:|onload=|onerror=)',
        # Command injection
        r'(&&|\|\||\;|\`)',
        # Path traversal
        r'(\.\./|\.\.\\|%2e%2e%2f)',
    ]
    
    # File type mappings
    ALLOWED_MIME_TYPES = {
        'text': ['text/plain', 'text/html', 'text/markdown'],
        'document': [
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.ms-powerpoint',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation'
        ],
        'image': [
            'image/jpeg', 'image/png', 'image/gif', 'image/bmp', 
            'image/tiff', 'image/webp', 'image/svg+xml'
        ]
    }
    
    def __init__(self, max_text_length: int = 1000000, max_file_size: int = 50 * 1024 * 1024):
        """
        Initialize validator with configuration.
        
        Args:
            max_text_length: Maximum allowed text length (default: 1MB)
            max_file_size: Maximum file size in bytes (default: 50MB)
        """
        self.max_text_length = max_text_length
        self.max_file_size = max_file_size
        
        # Compile injection patterns for performance
        self.injection_regex = re.compile(
            '|'.join(self.INJECTION_PATTERNS), 
            re.IGNORECASE | re.MULTILINE
        )
    
    def validate_and_sanitize(self, data: Dict[str, Any]) -> ValidationResult:
        """
        Main validation and sanitization method.
        
        Args:
            data: Input data to validate and sanitize
            
        Returns:
            ValidationResult with sanitized data or errors
        """
        result = ValidationResult(is_valid=True)
        
        try:
            # Deep copy to avoid modifying original
            sanitized = self._deep_copy_dict(data)
            
            # Validate each field
            for field, value in data.items():
                try:
                    sanitized_value = self._validate_field(field, value)
                    sanitized[field] = sanitized_value
                except ValidationError as e:
                    result.add_error(e.field, e.message, e.value)
                except Exception as e:
                    result.add_error(field, f"Unexpected validation error: {str(e)}", value)
            
            # Additional business logic validation
            self._validate_business_logic(sanitized, result)
            
            # Set sanitized data if validation passed
            if result.is_valid:
                result.sanitized_data = sanitized
                result.metadata['validation_passed'] = True
                logger.info("Input validation successful")
            else:
                logger.warning(f"Input validation failed with {len(result.errors)} errors")
                
        except Exception as e:
            result.add_error("validation", f"Critical validation failure: {str(e)}")
            logger.error(f"Critical validation failure: {e}", exc_info=True)
        
        return result
    
    def _validate_field(self, field: str, value: Any) -> Any:
        """
        Validate individual field based on its type and name.
        
        Args:
            field: Field name
            value: Field value
            
        Returns:
            Sanitized field value
            
        Raises:
            ValidationError: If validation fails
        """
        # Handle None values
        if value is None:
            return None
        
        # Field-specific validation
        if field in ['query', 'text', 'content', 'message']:
            return self._validate_text(field, value)
        elif field in ['file_path', 'filename', 'path']:
            return self._validate_file_path(field, value)
        elif field in ['email']:
            return self._validate_email(field, value)
        elif field in ['url', 'endpoint']:
            return self._validate_url(field, value)
        elif field in ['metadata', 'config', 'params']:
            return self._validate_dict(field, value)
        elif field in ['items', 'files', 'documents']:
            return self._validate_list(field, value)
        elif field in ['api_key', 'token', 'password']:
            return self._validate_secret(field, value)
        elif field in ['limit', 'offset', 'top_k', 'chunk_size']:
            return self._validate_integer(field, value)
        elif field in ['threshold', 'temperature', 'confidence']:
            return self._validate_float(field, value)
        else:
            # Generic validation
            return self._validate_generic(field, value)
    
    def _validate_text(self, field: str, value: Any) -> str:
        """Validate and sanitize text fields"""
        if not isinstance(value, (str, bytes)):
            raise ValidationError(field, f"Expected string, got {type(value).__name__}")
        
        # Convert bytes to string
        if isinstance(value, bytes):
            try:
                value = value.decode('utf-8')
            except UnicodeDecodeError:
                raise ValidationError(field, "Invalid UTF-8 encoding in bytes")
        
        # Check length
        if len(value) > self.max_text_length:
            raise ValidationError(
                field, 
                f"Text too long: {len(value)} > {self.max_text_length} characters"
            )
        
        # Check for injection patterns
        if self.injection_regex.search(value):
            raise ValidationError(field, "Potentially malicious content detected")
        
        # Sanitize HTML
        sanitized = self._sanitize_html(value)
        
        # Additional XSS protection
        sanitized = self._prevent_xss(sanitized)
        
        return sanitized.strip()
    
    def _validate_file_path(self, field: str, value: Any) -> str:
        """Validate file paths to prevent directory traversal"""
        if not isinstance(value, str):
            raise ValidationError(field, f"Expected string, got {type(value).__name__}")
        
        # Check for path traversal attempts
        if '..' in value or value.startswith('/') or '\\' in value:
            raise ValidationError(field, "Invalid file path: potential directory traversal")
        
        # Validate path components
        path_obj = Path(value)
        if not path_obj.name:
            raise ValidationError(field, "Empty filename not allowed")
        
        # Check for valid filename characters
        if not re.match(r'^[a-zA-Z0-9._-]+$', path_obj.name):
            raise ValidationError(field, "Invalid characters in filename")
        
        return str(path_obj)
    
    def _validate_email(self, field: str, value: Any) -> str:
        """Validate email addresses"""
        if not isinstance(value, str):
            raise ValidationError(field, f"Expected string, got {type(value).__name__}")
        
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, value):
            raise ValidationError(field, "Invalid email format")
        
        return value.lower().strip()
    
    def _validate_url(self, field: str, value: Any) -> str:
        """Validate URLs"""
        if not isinstance(value, str):
            raise ValidationError(field, f"Expected string, got {type(value).__name__}")
        
        try:
            parsed = urlparse(value)
            if not parsed.scheme or not parsed.netloc:
                raise ValidationError(field, "Invalid URL format")
            
            # Only allow safe protocols
            if parsed.scheme not in ['http', 'https']:
                raise ValidationError(field, f"Unsupported URL scheme: {parsed.scheme}")
            
        except Exception:
            raise ValidationError(field, "Malformed URL")
        
        return value
    
    def _validate_dict(self, field: str, value: Any) -> Dict[str, Any]:
        """Validate dictionary fields"""
        if not isinstance(value, dict):
            raise ValidationError(field, f"Expected dict, got {type(value).__name__}")
        
        # Recursively validate nested dictionaries
        sanitized = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise ValidationError(field, f"Dictionary keys must be strings, got {type(k).__name__}")
            
            # Validate key
            sanitized_key = self._validate_text(f"{field}.{k}", k)
            
            # Recursively validate value
            if isinstance(v, dict):
                sanitized[sanitized_key] = self._validate_dict(f"{field}.{k}", v)
            elif isinstance(v, list):
                sanitized[sanitized_key] = self._validate_list(f"{field}.{k}", v)
            else:
                sanitized[sanitized_key] = self._validate_generic(f"{field}.{k}", v)
        
        return sanitized
    
    def _validate_list(self, field: str, value: Any) -> List[Any]:
        """Validate list fields"""
        if not isinstance(value, list):
            raise ValidationError(field, f"Expected list, got {type(value).__name__}")
        
        # Check list size
        if len(value) > 1000:  # Prevent DoS through large lists
            raise ValidationError(field, f"List too large: {len(value)} > 1000 items")
        
        # Validate each item
        sanitized = []
        for i, item in enumerate(value):
            item_field = f"{field}[{i}]"
            if isinstance(item, dict):
                sanitized.append(self._validate_dict(item_field, item))
            elif isinstance(item, list):
                sanitized.append(self._validate_list(item_field, item))
            else:
                sanitized.append(self._validate_generic(item_field, item))
        
        return sanitized
    
    def _validate_secret(self, field: str, value: Any) -> str:
        """Validate secret fields (API keys, passwords, tokens)"""
        if not isinstance(value, str):
            raise ValidationError(field, f"Expected string, got {type(value).__name__}")
        
        # Check minimum length for security
        if len(value) < 8:
            raise ValidationError(field, "Secret too short (minimum 8 characters)")
        
        # Check for obvious test/placeholder values
        test_values = ['test', 'placeholder', 'example', '12345678', 'password']
        if value.lower() in test_values:
            raise ValidationError(field, "Invalid secret value")
        
        return value
    
    def _validate_integer(self, field: str, value: Any) -> int:
        """Validate integer fields"""
        if isinstance(value, bool):
            raise ValidationError(field, "Expected integer, got boolean")
        
        if not isinstance(value, int):
            if isinstance(value, str) and value.isdigit():
                value = int(value)
            else:
                raise ValidationError(field, f"Expected integer, got {type(value).__name__}")
        
        # Common sense bounds
        if field in ['limit', 'top_k'] and (value < 1 or value > 10000):
            raise ValidationError(field, f"Value out of range: 1-10000, got {value}")
        elif field in ['offset'] and (value < 0 or value > 1000000):
            raise ValidationError(field, f"Value out of range: 0-1000000, got {value}")
        elif field in ['chunk_size'] and (value < 100 or value > 100000):
            raise ValidationError(field, f"Value out of range: 100-100000, got {value}")
        
        return value
    
    def _validate_float(self, field: str, value: Any) -> float:
        """Validate float fields"""
        if not isinstance(value, (int, float)):
            if isinstance(value, str):
                try:
                    value = float(value)
                except ValueError:
                    raise ValidationError(field, f"Expected float, got invalid string: {value}")
            else:
                raise ValidationError(field, f"Expected float, got {type(value).__name__}")
        
        # Range validation
        if field in ['threshold', 'confidence'] and not (0.0 <= value <= 1.0):
            raise ValidationError(field, f"Value must be between 0.0 and 1.0, got {value}")
        elif field in ['temperature'] and not (0.0 <= value <= 2.0):
            raise ValidationError(field, f"Temperature must be between 0.0 and 2.0, got {value}")
        
        return float(value)
    
    def _validate_generic(self, field: str, value: Any) -> Any:
        """Generic validation for other types"""
        # Check for basic data types
        if isinstance(value, (str, int, float, bool)):
            if isinstance(value, str):
                return self._validate_text(field, value)
            return value
        elif value is None:
            return None
        else:
            # Convert complex objects to string representation
            try:
                return str(value)
            except Exception:
                raise ValidationError(field, f"Cannot serialize value of type {type(value).__name__}")
    
    def _sanitize_html(self, text: str) -> str:
        """Sanitize HTML content"""
        return bleach.clean(
            text,
            tags=self.ALLOWED_HTML_TAGS,
            attributes=self.ALLOWED_HTML_ATTRIBUTES,
            strip=True
        )
    
    def _prevent_xss(self, text: str) -> str:
        """Additional XSS prevention"""
        # HTML entity encoding
        text = html.escape(text, quote=False)
        
        # Remove null bytes
        text = text.replace('\x00', '')
        
        # Remove control characters except newlines and tabs
        text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t\r')
        
        return text
    
    def _validate_business_logic(self, data: Dict[str, Any], result: ValidationResult):
        """Validate business logic constraints"""
        # Example: Check that query is provided for search operations
        if 'operation' in data and data['operation'] == 'query':
            if not data.get('query'):
                result.add_error('query', 'Query text required for query operations')
        
        # Example: Check file format consistency
        if 'filename' in data and 'mime_type' in data:
            expected_mime = self._get_expected_mime_type(data['filename'])
            if expected_mime and data['mime_type'] not in expected_mime:
                result.add_warning(
                    f"MIME type {data['mime_type']} may not match filename {data['filename']}"
                )
    
    def _get_expected_mime_type(self, filename: str) -> Optional[List[str]]:
        """Get expected MIME types for a filename"""
        ext = Path(filename).suffix.lower()
        
        mime_map = {
            '.txt': ['text/plain'],
            '.html': ['text/html'],
            '.pdf': ['application/pdf'],
            '.docx': ['application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
            '.jpg': ['image/jpeg'],
            '.png': ['image/png'],
        }
        
        return mime_map.get(ext)
    
    def _deep_copy_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a deep copy of dictionary data"""
        try:
            # Use JSON serialization for deep copy (handles most cases)
            return json.loads(json.dumps(data, default=str))
        except (TypeError, ValueError):
            # Fallback for non-serializable objects
            result = {}
            for k, v in data.items():
                if isinstance(v, dict):
                    result[k] = self._deep_copy_dict(v)
                elif isinstance(v, list):
                    result[k] = [
                        self._deep_copy_dict(item) if isinstance(item, dict) else item 
                        for item in v
                    ]
                else:
                    result[k] = v
            return result
    
    def validate_file_content(self, file_path: str, expected_type: str = None) -> ValidationResult:
        """
        Validate file content and metadata.
        
        Args:
            file_path: Path to file
            expected_type: Expected file type category
            
        Returns:
            ValidationResult with file validation details
        """
        result = ValidationResult(is_valid=True)
        
        try:
            path_obj = Path(file_path)
            
            # Check if file exists
            if not path_obj.exists():
                result.add_error('file_path', f"File does not exist: {file_path}")
                return result
            
            # Check file size
            file_size = path_obj.stat().st_size
            if file_size > self.max_file_size:
                result.add_error(
                    'file_size', 
                    f"File too large: {file_size} > {self.max_file_size} bytes"
                )
                return result
            
            # Detect MIME type
            try:
                mime_type = magic.from_file(str(path_obj), mime=True)
            except Exception:
                result.add_warning("Could not detect MIME type")
                mime_type = None
            
            # Validate MIME type
            if expected_type and mime_type:
                allowed_types = self.ALLOWED_MIME_TYPES.get(expected_type, [])
                if mime_type not in allowed_types:
                    result.add_error(
                        'mime_type',
                        f"Invalid MIME type {mime_type} for expected type {expected_type}"
                    )
            
            # Calculate file hash for integrity
            file_hash = self._calculate_file_hash(path_obj)
            
            # Store metadata
            result.metadata.update({
                'file_size': file_size,
                'mime_type': mime_type,
                'file_hash': file_hash,
                'filename': path_obj.name,
                'extension': path_obj.suffix.lower()
            })
            
            result.sanitized_data = {
                'file_path': str(path_obj.resolve()),
                'metadata': result.metadata
            }
            
        except Exception as e:
            result.add_error('file_validation', f"File validation failed: {str(e)}")
            logger.error(f"File validation error for {file_path}: {e}", exc_info=True)
        
        return result
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of file content"""
        hash_sha256 = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception:
            return ""
    
    def get_validation_summary(self, result: ValidationResult) -> Dict[str, Any]:
        """Get a summary of validation results"""
        return {
            'is_valid': result.is_valid,
            'error_count': len(result.errors),
            'warning_count': len(result.warnings),
            'errors': [
                {'field': e.field, 'message': e.message} 
                for e in result.errors
            ],
            'warnings': result.warnings,
            'metadata_keys': list(result.metadata.keys()) if result.metadata else [],
            'sanitized_keys': list(result.sanitized_data.keys()) if result.sanitized_data else []
        }