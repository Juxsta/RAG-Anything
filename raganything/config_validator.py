"""
Configuration validation and production setup utilities for RAG-Anything.

Provides comprehensive validation, security checks, and deployment assistance
for production environments.
"""

import os
import re
import warnings
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import logging
import json
from enum import Enum

logger = logging.getLogger(__name__)


class ValidationLevel(Enum):
    """Validation severity levels"""
    INFO = "info"
    WARNING = "warning" 
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationResult:
    """Result of a configuration validation check"""
    key: str
    level: ValidationLevel
    message: str
    current_value: Any = None
    expected_value: Any = None
    suggestion: Optional[str] = None


@dataclass
class ValidationReport:
    """Complete validation report"""
    results: List[ValidationResult] = field(default_factory=list)
    passed: int = 0
    warnings: int = 0
    errors: int = 0
    critical: int = 0
    
    def add_result(self, result: ValidationResult) -> None:
        """Add a validation result"""
        self.results.append(result)
        
        if result.level == ValidationLevel.INFO:
            self.passed += 1
        elif result.level == ValidationLevel.WARNING:
            self.warnings += 1
        elif result.level == ValidationLevel.ERROR:
            self.errors += 1
        elif result.level == ValidationLevel.CRITICAL:
            self.critical += 1
    
    def is_production_ready(self) -> bool:
        """Check if configuration is ready for production"""
        return self.critical == 0 and self.errors == 0
    
    def has_warnings(self) -> bool:
        """Check if there are any warnings"""
        return self.warnings > 0


class ConfigValidator:
    """Comprehensive configuration validator for RAG-Anything"""
    
    def __init__(self):
        self.required_vars = {
            'RAG_BACKEND_TYPE',
            'WORKING_DIR',
            'OPENAI_API_KEY',
        }
        
        self.production_required_vars = {
            'GRAPHITI_GRAPH_HOST',
            'GRAPHITI_GRAPH_DATABASE', 
            'GRAPHITI_GROUP_ID',
            'LOG_DIR',
            'JWT_SECRET_KEY',
        }
        
        self.security_sensitive_vars = {
            'OPENAI_API_KEY',
            'GRAPHITI_LLM_API_KEY',
            'GRAPHITI_EMBEDDER_API_KEY',
            'GRAPHITI_GRAPH_PASSWORD',
            'GRAPHITI_NEO4J_PASSWORD',
            'JWT_SECRET_KEY',
            'API_KEYS',
            'SMTP_PASSWORD',
            'WEBHOOK_URL',
            'SLACK_WEBHOOK_URL',
        }
        
        # Default values and validation rules
        self.validation_rules = {
            'RAG_BACKEND_TYPE': {
                'type': str,
                'choices': ['lightrag', 'graphiti'],
                'default': 'graphiti'
            },
            'GRAPHITI_GRAPH_PROVIDER': {
                'type': str,
                'choices': ['falkordb', 'neo4j'],
                'default': 'falkordb'
            },
            'GRAPHITI_LLM_PROVIDER': {
                'type': str,
                'choices': ['openai', 'anthropic', 'custom'],
                'default': 'openai'
            },
            'GRAPHITI_GRAPH_PORT': {
                'type': int,
                'min': 1,
                'max': 65535,
                'default': 6379
            },
            'GRAPHITI_BATCH_SIZE': {
                'type': int,
                'min': 1,
                'max': 1000,
                'default': 50
            },
            'GRAPHITI_CACHE_TTL': {
                'type': int,
                'min': 60,
                'max': 86400,
                'default': 3600
            },
            'MAX_CONCURRENT_FILES': {
                'type': int,
                'min': 1,
                'max': 20,
                'default': 1
            },
            'FASTAPI_PORT': {
                'type': int,
                'min': 1000,
                'max': 65535,
                'default': 8000
            },
            'JWT_EXPIRATION_HOURS': {
                'type': int,
                'min': 1,
                'max': 168,  # 1 week
                'default': 24
            },
            'RATE_LIMIT_PER_MINUTE': {
                'type': int,
                'min': 1,
                'max': 10000,
                'default': 60
            }
        }
    
    def validate_configuration(
        self, 
        env_path: Optional[str] = None,
        production_mode: bool = False
    ) -> ValidationReport:
        """Validate complete configuration"""
        report = ValidationReport()
        
        # Load environment variables
        if env_path:
            self._load_env_file(env_path, report)
        
        # Basic validation
        self._validate_required_variables(report, production_mode)
        self._validate_variable_types_and_ranges(report)
        self._validate_file_paths(report)
        self._validate_security_settings(report, production_mode)
        self._validate_database_settings(report)
        self._validate_api_settings(report)
        
        # Production-specific validation
        if production_mode:
            self._validate_production_settings(report)
        
        return report
    
    def _load_env_file(self, env_path: str, report: ValidationReport) -> None:
        """Load and validate .env file"""
        env_file = Path(env_path)
        
        if not env_file.exists():
            report.add_result(ValidationResult(
                key=".env",
                level=ValidationLevel.ERROR,
                message=f"Environment file not found: {env_path}",
                suggestion="Create .env file from .env.example template"
            ))
            return
        
        try:
            from dotenv import load_dotenv
            load_dotenv(env_path)
            report.add_result(ValidationResult(
                key=".env",
                level=ValidationLevel.INFO,
                message=f"Environment file loaded successfully: {env_path}"
            ))
        except Exception as e:
            report.add_result(ValidationResult(
                key=".env",
                level=ValidationLevel.ERROR,
                message=f"Failed to load environment file: {e}",
                suggestion="Check .env file syntax and permissions"
            ))
    
    def _validate_required_variables(self, report: ValidationReport, production_mode: bool) -> None:
        """Validate required environment variables"""
        required = self.required_vars.copy()
        if production_mode:
            required.update(self.production_required_vars)
        
        for var in required:
            value = os.getenv(var)
            if not value:
                level = ValidationLevel.CRITICAL if production_mode else ValidationLevel.ERROR
                report.add_result(ValidationResult(
                    key=var,
                    level=level,
                    message=f"Required environment variable not set: {var}",
                    suggestion=f"Set {var} in .env file or environment"
                ))
            else:
                report.add_result(ValidationResult(
                    key=var,
                    level=ValidationLevel.INFO,
                    message=f"Required variable is set: {var}"
                ))
    
    def _validate_variable_types_and_ranges(self, report: ValidationReport) -> None:
        """Validate variable types and value ranges"""
        for var, rules in self.validation_rules.items():
            value = os.getenv(var)
            
            if not value:
                continue  # Skip if not set (handled in required validation)
            
            # Type validation
            try:
                if rules['type'] == int:
                    int_value = int(value)
                    
                    # Range validation
                    if 'min' in rules and int_value < rules['min']:
                        report.add_result(ValidationResult(
                            key=var,
                            level=ValidationLevel.ERROR,
                            message=f"{var} value {int_value} is below minimum {rules['min']}",
                            current_value=int_value,
                            expected_value=f">= {rules['min']}"
                        ))
                    elif 'max' in rules and int_value > rules['max']:
                        report.add_result(ValidationResult(
                            key=var,
                            level=ValidationLevel.ERROR,
                            message=f"{var} value {int_value} exceeds maximum {rules['max']}",
                            current_value=int_value,
                            expected_value=f"<= {rules['max']}"
                        ))
                    else:
                        report.add_result(ValidationResult(
                            key=var,
                            level=ValidationLevel.INFO,
                            message=f"{var} has valid value: {int_value}"
                        ))
                
                elif rules['type'] == str and 'choices' in rules:
                    if value not in rules['choices']:
                        report.add_result(ValidationResult(
                            key=var,
                            level=ValidationLevel.ERROR,
                            message=f"{var} value '{value}' is not in allowed choices: {rules['choices']}",
                            current_value=value,
                            expected_value=rules['choices']
                        ))
                    else:
                        report.add_result(ValidationResult(
                            key=var,
                            level=ValidationLevel.INFO,
                            message=f"{var} has valid value: {value}"
                        ))
                
            except ValueError as e:
                report.add_result(ValidationResult(
                    key=var,
                    level=ValidationLevel.ERROR,
                    message=f"{var} has invalid type: {e}",
                    current_value=value,
                    expected_value=rules['type'].__name__
                ))
    
    def _validate_file_paths(self, report: ValidationReport) -> None:
        """Validate file and directory paths"""
        path_vars = {
            'WORKING_DIR': 'directory',
            'OUTPUT_DIR': 'directory', 
            'LOG_DIR': 'directory'
        }
        
        for var, path_type in path_vars.items():
            value = os.getenv(var)
            if not value:
                continue
            
            path = Path(value)
            
            try:
                if path_type == 'directory':
                    path.mkdir(parents=True, exist_ok=True)
                    if not path.is_dir() or not os.access(path, os.W_OK):
                        report.add_result(ValidationResult(
                            key=var,
                            level=ValidationLevel.ERROR,
                            message=f"Directory not writable: {path}",
                            suggestion="Check directory permissions or create directory"
                        ))
                    else:
                        report.add_result(ValidationResult(
                            key=var,
                            level=ValidationLevel.INFO,
                            message=f"Directory is valid and writable: {path}"
                        ))
            except Exception as e:
                report.add_result(ValidationResult(
                    key=var,
                    level=ValidationLevel.ERROR,
                    message=f"Failed to validate path {path}: {e}",
                    suggestion="Check path permissions and parent directories"
                ))
    
    def _validate_security_settings(self, report: ValidationReport, production_mode: bool) -> None:
        """Validate security-related settings"""
        
        # Check for default/weak secrets
        jwt_secret = os.getenv('JWT_SECRET_KEY', '')
        if jwt_secret:
            if len(jwt_secret) < 32:
                report.add_result(ValidationResult(
                    key='JWT_SECRET_KEY',
                    level=ValidationLevel.CRITICAL if production_mode else ValidationLevel.WARNING,
                    message="JWT secret key is too short (minimum 32 characters)",
                    suggestion="Generate a strong random secret key"
                ))
            elif jwt_secret in ['your_jwt_secret_key_here', 'changeme', 'secret']:
                report.add_result(ValidationResult(
                    key='JWT_SECRET_KEY',
                    level=ValidationLevel.CRITICAL,
                    message="JWT secret key is using default/weak value",
                    suggestion="Generate a secure random secret key"
                ))
        
        # Check API key formats
        openai_key = os.getenv('OPENAI_API_KEY', '')
        if openai_key and not openai_key.startswith('sk-'):
            report.add_result(ValidationResult(
                key='OPENAI_API_KEY',
                level=ValidationLevel.WARNING,
                message="OpenAI API key doesn't match expected format",
                suggestion="Verify API key format (should start with 'sk-')"
            ))
        
        # Check for sensitive data in logs
        debug_mode = os.getenv('DEBUG_MODE', 'false').lower() == 'true'
        detailed_errors = os.getenv('DETAILED_ERROR_RESPONSES', 'true').lower() == 'true'
        
        if production_mode and (debug_mode or detailed_errors):
            report.add_result(ValidationResult(
                key='DEBUG_SETTINGS',
                level=ValidationLevel.WARNING,
                message="Debug settings enabled in production mode",
                suggestion="Disable DEBUG_MODE and DETAILED_ERROR_RESPONSES in production"
            ))
    
    def _validate_database_settings(self, report: ValidationReport) -> None:
        """Validate database connection settings"""
        provider = os.getenv('GRAPHITI_GRAPH_PROVIDER', 'falkordb')
        
        if provider == 'falkordb':
            host = os.getenv('GRAPHITI_GRAPH_HOST', 'localhost')
            port = os.getenv('GRAPHITI_GRAPH_PORT', '6379')
            
            if host == 'localhost' or host == '127.0.0.1':
                report.add_result(ValidationResult(
                    key='GRAPHITI_GRAPH_HOST',
                    level=ValidationLevel.WARNING,
                    message="Using localhost for database connection",
                    suggestion="Consider using specific host address for production"
                ))
            
        elif provider == 'neo4j':
            uri = os.getenv('GRAPHITI_NEO4J_URI', '')
            user = os.getenv('GRAPHITI_NEO4J_USER', 'neo4j')
            password = os.getenv('GRAPHITI_NEO4J_PASSWORD', 'password')
            
            if password == 'password':
                report.add_result(ValidationResult(
                    key='GRAPHITI_NEO4J_PASSWORD',
                    level=ValidationLevel.CRITICAL,
                    message="Using default Neo4j password",
                    suggestion="Change Neo4j password from default value"
                ))
    
    def _validate_api_settings(self, report: ValidationReport) -> None:
        """Validate API configuration settings"""
        port = os.getenv('FASTAPI_PORT', '8000')
        try:
            port_int = int(port)
            if port_int < 1024:
                report.add_result(ValidationResult(
                    key='FASTAPI_PORT',
                    level=ValidationLevel.WARNING,
                    message=f"Using privileged port {port_int}",
                    suggestion="Consider using port >= 1024 or ensure proper permissions"
                ))
        except ValueError:
            pass  # Already handled in type validation
        
        # Rate limiting
        rate_limiting = os.getenv('ENABLE_RATE_LIMITING', 'true').lower() == 'true'
        if not rate_limiting:
            report.add_result(ValidationResult(
                key='ENABLE_RATE_LIMITING',
                level=ValidationLevel.WARNING,
                message="Rate limiting is disabled",
                suggestion="Enable rate limiting for production use"
            ))
    
    def _validate_production_settings(self, report: ValidationReport) -> None:
        """Additional validation for production environments"""
        
        # Check logging configuration
        log_level = os.getenv('LOG_LEVEL', 'INFO')
        if log_level == 'DEBUG':
            report.add_result(ValidationResult(
                key='LOG_LEVEL',
                level=ValidationLevel.WARNING,
                message="Debug logging enabled in production",
                suggestion="Use INFO or WARNING log level for production"
            ))
        
        # Check CORS settings
        cors_enabled = os.getenv('ENABLE_CORS', 'true').lower() == 'true'
        if cors_enabled:
            report.add_result(ValidationResult(
                key='ENABLE_CORS',
                level=ValidationLevel.WARNING,
                message="CORS is enabled for all origins",
                suggestion="Configure specific CORS origins for production"
            ))
        
        # Check cache settings
        cache_enabled = os.getenv('ENABLE_GRAPHITI_CACHE', 'true').lower() == 'true'
        if not cache_enabled:
            report.add_result(ValidationResult(
                key='ENABLE_GRAPHITI_CACHE',
                level=ValidationLevel.WARNING,
                message="Caching is disabled",
                suggestion="Enable caching for better performance in production"
            ))


def generate_secure_key(length: int = 64) -> str:
    """Generate a secure random key"""
    import secrets
    import string
    
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def setup_production_env(
    env_path: str = ".env.production",
    template_path: str = ".env.example"
) -> Tuple[bool, List[str]]:
    """Set up production environment file with secure defaults"""
    
    template_file = Path(template_path)
    production_file = Path(env_path)
    
    if not template_file.exists():
        return False, [f"Template file not found: {template_path}"]
    
    messages = []
    
    try:
        # Read template
        with open(template_file, 'r') as f:
            template_content = f.read()
        
        # Generate secure values
        jwt_secret = generate_secure_key(64)
        api_key = generate_secure_key(32)
        
        # Replace placeholders with secure values
        production_content = template_content.replace(
            'your_openai_api_key_here',
            'YOUR_ACTUAL_OPENAI_API_KEY'
        ).replace(
            'your_jwt_secret_key_here',
            jwt_secret
        ).replace(
            'DEBUG_MODE=false',
            'DEBUG_MODE=false'
        ).replace(
            'DETAILED_ERROR_RESPONSES=true',
            'DETAILED_ERROR_RESPONSES=false'
        ).replace(
            'LOG_LEVEL=INFO',
            'LOG_LEVEL=WARNING'
        )
        
        # Write production file
        with open(production_file, 'w') as f:
            f.write(production_content)
        
        messages.append(f"Production environment file created: {env_path}")
        messages.append("Remember to:")
        messages.append("1. Set your actual API keys")
        messages.append("2. Update database connection settings")
        messages.append("3. Review and adjust all configuration values")
        messages.append("4. Keep this file secure and never commit to version control")
        
        return True, messages
        
    except Exception as e:
        return False, [f"Failed to create production environment file: {e}"]


def main():
    """CLI for configuration validation"""
    import argparse
    
    parser = argparse.ArgumentParser(description="RAG-Anything Configuration Validator")
    parser.add_argument(
        "--env-file", 
        default=".env",
        help="Path to environment file (default: .env)"
    )
    parser.add_argument(
        "--production", 
        action="store_true",
        help="Enable production-level validation"
    )
    parser.add_argument(
        "--setup-production",
        action="store_true",
        help="Set up production environment file"
    )
    parser.add_argument(
        "--output-format",
        choices=["text", "json"],
        default="text",
        help="Output format for validation results"
    )
    
    args = parser.parse_args()
    
    if args.setup_production:
        success, messages = setup_production_env()
        for message in messages:
            print(message)
        return 0 if success else 1
    
    # Validate configuration
    validator = ConfigValidator()
    report = validator.validate_configuration(args.env_file, args.production)
    
    if args.output_format == "json":
        # JSON output
        json_report = {
            "summary": {
                "passed": report.passed,
                "warnings": report.warnings,
                "errors": report.errors,
                "critical": report.critical,
                "production_ready": report.is_production_ready()
            },
            "results": [
                {
                    "key": result.key,
                    "level": result.level.value,
                    "message": result.message,
                    "current_value": result.current_value,
                    "expected_value": result.expected_value,
                    "suggestion": result.suggestion
                }
                for result in report.results
            ]
        }
        print(json.dumps(json_report, indent=2))
    else:
        # Text output
        print("RAG-Anything Configuration Validation Report")
        print("=" * 50)
        print(f"✅ Passed: {report.passed}")
        print(f"⚠️  Warnings: {report.warnings}")
        print(f"❌ Errors: {report.errors}")
        print(f"🔥 Critical: {report.critical}")
        print(f"🚀 Production Ready: {'Yes' if report.is_production_ready() else 'No'}")
        print()
        
        # Group results by level
        for level in [ValidationLevel.CRITICAL, ValidationLevel.ERROR, 
                     ValidationLevel.WARNING, ValidationLevel.INFO]:
            level_results = [r for r in report.results if r.level == level]
            if level_results:
                level_icon = {"critical": "🔥", "error": "❌", "warning": "⚠️", "info": "✅"}
                print(f"{level_icon[level.value]} {level.value.upper()}:")
                for result in level_results:
                    print(f"  {result.key}: {result.message}")
                    if result.suggestion:
                        print(f"    💡 {result.suggestion}")
                print()
    
    # Return exit code based on validation results
    if report.critical > 0:
        return 2  # Critical issues
    elif report.errors > 0:
        return 1  # Error issues
    else:
        return 0  # Success


if __name__ == "__main__":
    exit(main())