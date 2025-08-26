"""
Security headers management for RAG-Anything.

This module provides comprehensive security header management:
- Content Security Policy (CSP)
- HSTS (HTTP Strict Transport Security)
- X-Frame-Options
- X-Content-Type-Options
- X-XSS-Protection
- Referrer Policy
- Permissions Policy
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import logging

# Configure logger
logger = logging.getLogger(__name__)


class CSPDirective(Enum):
    """Content Security Policy directives"""
    DEFAULT_SRC = "default-src"
    SCRIPT_SRC = "script-src"
    STYLE_SRC = "style-src"
    IMG_SRC = "img-src"
    CONNECT_SRC = "connect-src"
    FONT_SRC = "font-src"
    OBJECT_SRC = "object-src"
    MEDIA_SRC = "media-src"
    FRAME_SRC = "frame-src"
    SANDBOX = "sandbox"
    REPORT_URI = "report-uri"
    CHILD_SRC = "child-src"
    FORM_ACTION = "form-action"
    FRAME_ANCESTORS = "frame-ancestors"
    BASE_URI = "base-uri"
    WORKER_SRC = "worker-src"


class SecurityLevel(Enum):
    """Security configuration levels"""
    STRICT = "strict"
    MODERATE = "moderate"
    RELAXED = "relaxed"
    DEVELOPMENT = "development"


@dataclass
class SecurityHeadersConfig:
    """Configuration for security headers"""
    
    # General settings
    security_level: SecurityLevel = SecurityLevel.MODERATE
    enable_hsts: bool = True
    enable_csp: bool = True
    enable_frame_options: bool = True
    
    # HSTS configuration
    hsts_max_age: int = 31536000  # 1 year
    hsts_include_subdomains: bool = True
    hsts_preload: bool = False
    
    # CSP configuration
    csp_directives: Dict[CSPDirective, List[str]] = field(default_factory=dict)
    csp_report_only: bool = False
    csp_report_uri: Optional[str] = None
    
    # Frame options
    frame_options: str = "DENY"  # DENY, SAMEORIGIN, or ALLOW-FROM uri
    
    # Custom headers
    custom_headers: Dict[str, str] = field(default_factory=dict)
    
    # Environment-specific overrides
    development_overrides: bool = True
    
    def __post_init__(self):
        """Set default CSP directives based on security level"""
        if not self.csp_directives:
            self.csp_directives = self._get_default_csp_directives()
    
    def _get_default_csp_directives(self) -> Dict[CSPDirective, List[str]]:
        """Get default CSP directives based on security level"""
        
        if self.security_level == SecurityLevel.STRICT:
            return {
                CSPDirective.DEFAULT_SRC: ["'self'"],
                CSPDirective.SCRIPT_SRC: ["'self'", "'unsafe-inline'"],
                CSPDirective.STYLE_SRC: ["'self'", "'unsafe-inline'"],
                CSPDirective.IMG_SRC: ["'self'", "data:", "https:"],
                CSPDirective.CONNECT_SRC: ["'self'"],
                CSPDirective.FONT_SRC: ["'self'"],
                CSPDirective.OBJECT_SRC: ["'none'"],
                CSPDirective.FRAME_SRC: ["'none'"],
                CSPDirective.FRAME_ANCESTORS: ["'none'"],
                CSPDirective.BASE_URI: ["'self'"],
                CSPDirective.FORM_ACTION: ["'self'"]
            }
        
        elif self.security_level == SecurityLevel.MODERATE:
            return {
                CSPDirective.DEFAULT_SRC: ["'self'"],
                CSPDirective.SCRIPT_SRC: ["'self'", "'unsafe-inline'", "'unsafe-eval'"],
                CSPDirective.STYLE_SRC: ["'self'", "'unsafe-inline'", "https:"],
                CSPDirective.IMG_SRC: ["'self'", "data:", "https:"],
                CSPDirective.CONNECT_SRC: ["'self'", "https:", "wss:"],
                CSPDirective.FONT_SRC: ["'self'", "https:"],
                CSPDirective.OBJECT_SRC: ["'none'"],
                CSPDirective.FRAME_SRC: ["'self'"],
                CSPDirective.BASE_URI: ["'self'"],
                CSPDirective.FORM_ACTION: ["'self'"]
            }
        
        elif self.security_level == SecurityLevel.RELAXED:
            return {
                CSPDirective.DEFAULT_SRC: ["'self'", "https:"],
                CSPDirective.SCRIPT_SRC: ["'self'", "'unsafe-inline'", "'unsafe-eval'", "https:"],
                CSPDirective.STYLE_SRC: ["'self'", "'unsafe-inline'", "https:"],
                CSPDirective.IMG_SRC: ["*", "data:"],
                CSPDirective.CONNECT_SRC: ["*"],
                CSPDirective.FONT_SRC: ["*"],
                CSPDirective.OBJECT_SRC: ["'self'"],
                CSPDirective.FRAME_SRC: ["*"],
                CSPDirective.BASE_URI: ["'self'"],
                CSPDirective.FORM_ACTION: ["*"]
            }
        
        elif self.security_level == SecurityLevel.DEVELOPMENT:
            return {
                CSPDirective.DEFAULT_SRC: ["*", "'unsafe-inline'", "'unsafe-eval'", "data:", "blob:"],
                CSPDirective.SCRIPT_SRC: ["*", "'unsafe-inline'", "'unsafe-eval'"],
                CSPDirective.STYLE_SRC: ["*", "'unsafe-inline'"],
                CSPDirective.IMG_SRC: ["*", "data:", "blob:"],
                CSPDirective.CONNECT_SRC: ["*"],
                CSPDirective.FONT_SRC: ["*"],
                CSPDirective.OBJECT_SRC: ["*"],
                CSPDirective.FRAME_SRC: ["*"],
                CSPDirective.BASE_URI: ["*"],
                CSPDirective.FORM_ACTION: ["*"]
            }
        
        return {}


class SecurityHeadersManager:
    """
    Manages security headers for HTTP responses.
    
    Provides comprehensive security header management with configurable
    security levels and environment-specific overrides.
    """
    
    def __init__(self, config: SecurityHeadersConfig):
        self.config = config
        self._cached_headers = None
        self._csp_violations = []
    
    def get_security_headers(self, request_context: Dict[str, Any] = None) -> Dict[str, str]:
        """
        Get all security headers for HTTP response.
        
        Args:
            request_context: Optional request context for dynamic header generation
            
        Returns:
            Dictionary of header name -> value pairs
        """
        if self._cached_headers is None:
            self._cached_headers = self._build_headers(request_context)
        
        return self._cached_headers.copy()
    
    def _build_headers(self, request_context: Dict[str, Any] = None) -> Dict[str, str]:
        """Build the complete set of security headers"""
        headers = {}
        
        # HSTS header
        if self.config.enable_hsts:
            hsts_value = f"max-age={self.config.hsts_max_age}"
            if self.config.hsts_include_subdomains:
                hsts_value += "; includeSubDomains"
            if self.config.hsts_preload:
                hsts_value += "; preload"
            headers["Strict-Transport-Security"] = hsts_value
        
        # Content Security Policy
        if self.config.enable_csp:
            csp_header = "Content-Security-Policy-Report-Only" if self.config.csp_report_only else "Content-Security-Policy"
            headers[csp_header] = self._build_csp_header()
        
        # Frame Options
        if self.config.enable_frame_options:
            headers["X-Frame-Options"] = self.config.frame_options
        
        # Standard security headers
        headers.update({
            # Prevent MIME type sniffing
            "X-Content-Type-Options": "nosniff",
            
            # XSS Protection (legacy but still useful)
            "X-XSS-Protection": "1; mode=block",
            
            # Referrer Policy
            "Referrer-Policy": "strict-origin-when-cross-origin",
            
            # Permissions Policy (formerly Feature Policy)
            "Permissions-Policy": self._build_permissions_policy(),
            
            # Cross-Origin Policies
            "Cross-Origin-Embedder-Policy": "require-corp",
            "Cross-Origin-Opener-Policy": "same-origin",
            "Cross-Origin-Resource-Policy": "same-site",
            
            # Server identification
            "Server": "RAG-Anything-API",
            
            # Cache control for sensitive responses
            "Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        })
        
        # Custom headers
        headers.update(self.config.custom_headers)
        
        # Development environment overrides
        if self.config.development_overrides and self.config.security_level == SecurityLevel.DEVELOPMENT:
            headers = self._apply_development_overrides(headers)
        
        return headers
    
    def _build_csp_header(self) -> str:
        """Build Content Security Policy header value"""
        csp_parts = []
        
        for directive, values in self.config.csp_directives.items():
            if values:
                directive_str = f"{directive.value} {' '.join(values)}"
                csp_parts.append(directive_str)
        
        # Add report URI if configured
        if self.config.csp_report_uri:
            csp_parts.append(f"report-uri {self.config.csp_report_uri}")
        
        return "; ".join(csp_parts)
    
    def _build_permissions_policy(self) -> str:
        """Build Permissions Policy header value"""
        # Default restrictive permissions policy
        policies = [
            "accelerometer=()",
            "camera=()",
            "geolocation=()",
            "gyroscope=()",
            "magnetometer=()",
            "microphone=()",
            "payment=()",
            "usb=()",
            "interest-cohort=()"  # Disable FLoC
        ]
        
        # Adjust based on security level
        if self.config.security_level in [SecurityLevel.RELAXED, SecurityLevel.DEVELOPMENT]:
            # Allow some features for same origin in relaxed mode
            policies = [
                "accelerometer=(self)",
                "camera=(self)",
                "geolocation=(self)",
                "gyroscope=(self)",
                "magnetometer=(self)",
                "microphone=(self)",
                "payment=(self)",
                "usb=()",
                "interest-cohort=()"
            ]
        
        return ", ".join(policies)
    
    def _apply_development_overrides(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Apply development environment overrides"""
        # Relax some headers for development
        dev_headers = headers.copy()
        
        # Remove or relax certain headers in development
        dev_headers.pop("Strict-Transport-Security", None)
        dev_headers["Cross-Origin-Embedder-Policy"] = "unsafe-none"
        dev_headers["Cross-Origin-Resource-Policy"] = "cross-origin"
        
        # More permissive cache control in development
        dev_headers["Cache-Control"] = "no-cache"
        dev_headers.pop("Pragma", None)
        dev_headers.pop("Expires", None)
        
        return dev_headers
    
    def add_csp_source(self, directive: CSPDirective, source: str) -> None:
        """
        Add a source to a CSP directive.
        
        Args:
            directive: CSP directive to modify
            source: Source to add (e.g., "'self'", "https://cdn.example.com")
        """
        if directive not in self.config.csp_directives:
            self.config.csp_directives[directive] = []
        
        if source not in self.config.csp_directives[directive]:
            self.config.csp_directives[directive].append(source)
            self._cached_headers = None  # Invalidate cache
            logger.info(f"Added CSP source '{source}' to {directive.value}")
    
    def remove_csp_source(self, directive: CSPDirective, source: str) -> bool:
        """
        Remove a source from a CSP directive.
        
        Args:
            directive: CSP directive to modify
            source: Source to remove
            
        Returns:
            True if source was removed, False if not found
        """
        if directive in self.config.csp_directives and source in self.config.csp_directives[directive]:
            self.config.csp_directives[directive].remove(source)
            self._cached_headers = None  # Invalidate cache
            logger.info(f"Removed CSP source '{source}' from {directive.value}")
            return True
        return False
    
    def set_custom_header(self, name: str, value: str) -> None:
        """
        Set a custom security header.
        
        Args:
            name: Header name
            value: Header value
        """
        self.config.custom_headers[name] = value
        self._cached_headers = None  # Invalidate cache
        logger.info(f"Set custom header '{name}': '{value}'")
    
    def remove_custom_header(self, name: str) -> bool:
        """
        Remove a custom security header.
        
        Args:
            name: Header name to remove
            
        Returns:
            True if header was removed, False if not found
        """
        if name in self.config.custom_headers:
            del self.config.custom_headers[name]
            self._cached_headers = None  # Invalidate cache
            logger.info(f"Removed custom header '{name}'")
            return True
        return False
    
    def validate_csp_policy(self) -> List[str]:
        """
        Validate the current CSP policy and return warnings.
        
        Returns:
            List of validation warnings
        """
        warnings = []
        
        # Check for unsafe directives
        unsafe_patterns = ["'unsafe-inline'", "'unsafe-eval'", "*"]
        
        for directive, sources in self.config.csp_directives.items():
            for source in sources:
                if source in unsafe_patterns:
                    if self.config.security_level not in [SecurityLevel.RELAXED, SecurityLevel.DEVELOPMENT]:
                        warnings.append(f"Unsafe CSP source '{source}' in {directive.value}")
        
        # Check for missing important directives
        important_directives = [
            CSPDirective.DEFAULT_SRC,
            CSPDirective.SCRIPT_SRC,
            CSPDirective.OBJECT_SRC,
            CSPDirective.BASE_URI
        ]
        
        for directive in important_directives:
            if directive not in self.config.csp_directives:
                warnings.append(f"Missing important CSP directive: {directive.value}")
        
        # Check object-src
        if CSPDirective.OBJECT_SRC in self.config.csp_directives:
            object_sources = self.config.csp_directives[CSPDirective.OBJECT_SRC]
            if "'none'" not in object_sources and len(object_sources) > 0:
                warnings.append("object-src should typically be set to 'none' for security")
        
        return warnings
    
    def generate_csp_report_handler(self) -> callable:
        """
        Generate a handler for CSP violation reports.
        
        Returns:
            Callable that can handle CSP violation reports
        """
        def handle_csp_report(report_data: Dict[str, Any]) -> None:
            """Handle incoming CSP violation report"""
            try:
                violation = {
                    'timestamp': report_data.get('csp-report', {}).get('timestamp'),
                    'document_uri': report_data.get('csp-report', {}).get('document-uri'),
                    'blocked_uri': report_data.get('csp-report', {}).get('blocked-uri'),
                    'violated_directive': report_data.get('csp-report', {}).get('violated-directive'),
                    'original_policy': report_data.get('csp-report', {}).get('original-policy'),
                    'source_file': report_data.get('csp-report', {}).get('source-file'),
                    'line_number': report_data.get('csp-report', {}).get('line-number')
                }
                
                self._csp_violations.append(violation)
                
                # Keep only last 1000 violations
                if len(self._csp_violations) > 1000:
                    self._csp_violations = self._csp_violations[-1000:]
                
                logger.warning(f"CSP Violation: {violation['violated_directive']} - {violation['blocked_uri']}")
                
            except Exception as e:
                logger.error(f"Error handling CSP report: {e}")
        
        return handle_csp_report
    
    def get_csp_violations_summary(self, limit: int = 50) -> Dict[str, Any]:
        """
        Get summary of recent CSP violations.
        
        Args:
            limit: Maximum number of violations to return
            
        Returns:
            Summary of CSP violations
        """
        recent_violations = self._csp_violations[-limit:]
        
        # Count violations by directive
        by_directive = {}
        by_blocked_uri = {}
        
        for violation in recent_violations:
            directive = violation.get('violated_directive', 'unknown')
            blocked_uri = violation.get('blocked_uri', 'unknown')
            
            by_directive[directive] = by_directive.get(directive, 0) + 1
            by_blocked_uri[blocked_uri] = by_blocked_uri.get(blocked_uri, 0) + 1
        
        return {
            'total_violations': len(self._csp_violations),
            'recent_violations': len(recent_violations),
            'violations_by_directive': dict(sorted(by_directive.items(), key=lambda x: x[1], reverse=True)),
            'violations_by_blocked_uri': dict(sorted(by_blocked_uri.items(), key=lambda x: x[1], reverse=True)[:20]),
            'recent_violations_detail': recent_violations
        }
    
    def update_security_level(self, new_level: SecurityLevel) -> None:
        """
        Update the security level and refresh headers.
        
        Args:
            new_level: New security level to apply
        """
        old_level = self.config.security_level
        self.config.security_level = new_level
        
        # Update CSP directives based on new level
        self.config.csp_directives = self.config._get_default_csp_directives()
        
        # Invalidate cached headers
        self._cached_headers = None
        
        logger.info(f"Updated security level from {old_level.value} to {new_level.value}")
    
    def get_header_analysis(self) -> Dict[str, Any]:
        """
        Analyze current security headers configuration.
        
        Returns:
            Analysis of security headers with recommendations
        """
        headers = self.get_security_headers()
        csp_warnings = self.validate_csp_policy()
        
        analysis = {
            'security_level': self.config.security_level.value,
            'total_headers': len(headers),
            'enabled_features': {
                'hsts': self.config.enable_hsts,
                'csp': self.config.enable_csp,
                'frame_options': self.config.enable_frame_options
            },
            'csp_directives_count': len(self.config.csp_directives),
            'csp_warnings': csp_warnings,
            'custom_headers_count': len(self.config.custom_headers),
            'recommendations': []
        }
        
        # Generate recommendations
        if not self.config.enable_hsts:
            analysis['recommendations'].append("Enable HSTS for better transport security")
        
        if not self.config.enable_csp:
            analysis['recommendations'].append("Enable Content Security Policy to prevent XSS attacks")
        
        if csp_warnings:
            analysis['recommendations'].append("Review and fix CSP policy warnings")
        
        if self.config.security_level == SecurityLevel.DEVELOPMENT:
            analysis['recommendations'].append("Use stricter security level in production")
        
        # Check for missing security headers
        important_headers = [
            "Strict-Transport-Security",
            "Content-Security-Policy",
            "X-Frame-Options",
            "X-Content-Type-Options",
            "Referrer-Policy"
        ]
        
        missing_headers = [h for h in important_headers if h not in headers]
        if missing_headers:
            analysis['recommendations'].append(f"Consider adding missing security headers: {', '.join(missing_headers)}")
        
        return analysis
    
    def export_configuration(self) -> Dict[str, Any]:
        """Export current security headers configuration"""
        return {
            'security_level': self.config.security_level.value,
            'hsts': {
                'enabled': self.config.enable_hsts,
                'max_age': self.config.hsts_max_age,
                'include_subdomains': self.config.hsts_include_subdomains,
                'preload': self.config.hsts_preload
            },
            'csp': {
                'enabled': self.config.enable_csp,
                'report_only': self.config.csp_report_only,
                'report_uri': self.config.csp_report_uri,
                'directives': {
                    directive.value: sources 
                    for directive, sources in self.config.csp_directives.items()
                }
            },
            'frame_options': {
                'enabled': self.config.enable_frame_options,
                'value': self.config.frame_options
            },
            'custom_headers': dict(self.config.custom_headers)
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Health check for security headers system"""
        headers = self.get_security_headers()
        csp_warnings = self.validate_csp_policy()
        
        return {
            'headers_count': len(headers),
            'security_level': self.config.security_level.value,
            'csp_enabled': self.config.enable_csp,
            'csp_warnings_count': len(csp_warnings),
            'csp_violations_count': len(self._csp_violations),
            'hsts_enabled': self.config.enable_hsts,
            'custom_headers_count': len(self.config.custom_headers),
            'status': 'healthy' if len(csp_warnings) == 0 else 'warnings'
        }