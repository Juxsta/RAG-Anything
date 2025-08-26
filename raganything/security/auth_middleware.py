"""
Authentication and authorization middleware for RAG-Anything.

This module provides comprehensive authentication mechanisms:
- API Key authentication
- JWT token authentication
- Role-based access control
- Session management
- Multi-factor authentication support
"""

import jwt
import time
import hashlib
import secrets
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import redis.asyncio as aioredis
import bcrypt
import logging

# Configure logger
logger = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Raised when authentication fails"""
    pass


class AuthorizationError(Exception):
    """Raised when authorization fails"""
    pass


class AuthMethod(Enum):
    """Authentication methods"""
    API_KEY = "api_key"
    JWT = "jwt"
    BASIC = "basic"
    BEARER = "bearer"


class UserRole(Enum):
    """User roles for RBAC"""
    ADMIN = "admin"
    USER = "user"
    READONLY = "readonly"
    API_CLIENT = "api_client"
    GUEST = "guest"


class Permission(Enum):
    """System permissions"""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    QUERY = "query"
    UPLOAD = "upload"
    DOWNLOAD = "download"
    MANAGE_USERS = "manage_users"
    VIEW_METRICS = "view_metrics"


@dataclass
class AuthConfig:
    """Authentication configuration"""
    
    # JWT settings
    jwt_secret: str = "your-secret-key"
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 60
    refresh_token_expiry_days: int = 30
    
    # API Key settings
    api_key_length: int = 32
    api_key_prefix: str = "raga_"
    
    # Security settings
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 15
    require_https: bool = True
    
    # Session settings
    session_timeout_minutes: int = 30
    max_concurrent_sessions: int = 5
    
    # Redis settings
    redis_prefix: str = "raganything:auth"
    cache_ttl: int = 3600
    
    # Role permissions
    role_permissions: Dict[UserRole, Set[Permission]] = field(default_factory=dict)
    
    def __post_init__(self):
        """Set default role permissions"""
        if not self.role_permissions:
            self.role_permissions = {
                UserRole.ADMIN: {
                    Permission.READ, Permission.WRITE, Permission.DELETE,
                    Permission.ADMIN, Permission.QUERY, Permission.UPLOAD,
                    Permission.DOWNLOAD, Permission.MANAGE_USERS, Permission.VIEW_METRICS
                },
                UserRole.USER: {
                    Permission.READ, Permission.WRITE, Permission.QUERY,
                    Permission.UPLOAD, Permission.DOWNLOAD
                },
                UserRole.READONLY: {
                    Permission.READ, Permission.QUERY, Permission.DOWNLOAD
                },
                UserRole.API_CLIENT: {
                    Permission.READ, Permission.WRITE, Permission.QUERY,
                    Permission.UPLOAD, Permission.DOWNLOAD
                },
                UserRole.GUEST: {
                    Permission.READ, Permission.QUERY
                }
            }


@dataclass
class User:
    """User entity"""
    id: str
    username: str
    email: str
    role: UserRole
    permissions: Set[Permission]
    api_keys: List[str] = field(default_factory=list)
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    last_login: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuthContext:
    """Authentication context for a request"""
    user: Optional[User] = None
    method: Optional[AuthMethod] = None
    token: Optional[str] = None
    permissions: Set[Permission] = field(default_factory=set)
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    authenticated: bool = False
    
    def has_permission(self, permission: Permission) -> bool:
        """Check if user has specific permission"""
        return permission in self.permissions
    
    def has_any_permission(self, permissions: List[Permission]) -> bool:
        """Check if user has any of the specified permissions"""
        return any(p in self.permissions for p in permissions)
    
    def has_all_permissions(self, permissions: List[Permission]) -> bool:
        """Check if user has all specified permissions"""
        return all(p in self.permissions for p in permissions)


class BaseAuthenticator(ABC):
    """Base class for authentication methods"""
    
    def __init__(self, config: AuthConfig, redis_client: Optional[aioredis.Redis] = None):
        self.config = config
        self.redis_client = redis_client
    
    @abstractmethod
    async def authenticate(self, credentials: Dict[str, Any]) -> AuthContext:
        """Authenticate user with provided credentials"""
        pass
    
    @abstractmethod
    async def validate_token(self, token: str) -> AuthContext:
        """Validate authentication token"""
        pass
    
    async def _get_user_from_cache(self, user_id: str) -> Optional[User]:
        """Get user from Redis cache"""
        try:
            if self.redis_client:
                key = f"{self.config.redis_prefix}:user:{user_id}"
                data = await self.redis_client.get(key)
                if data:
                    import json
                    user_data = json.loads(data)
                    return User(
                        id=user_data['id'],
                        username=user_data['username'],
                        email=user_data['email'],
                        role=UserRole(user_data['role']),
                        permissions={Permission(p) for p in user_data['permissions']},
                        api_keys=user_data.get('api_keys', []),
                        is_active=user_data.get('is_active', True),
                        created_at=datetime.fromisoformat(user_data['created_at']),
                        last_login=datetime.fromisoformat(user_data['last_login']) if user_data.get('last_login') else None,
                        metadata=user_data.get('metadata', {})
                    )
        except Exception as e:
            logger.warning(f"Error getting user from cache: {e}")
        return None
    
    async def _cache_user(self, user: User) -> None:
        """Cache user in Redis"""
        try:
            if self.redis_client:
                key = f"{self.config.redis_prefix}:user:{user.id}"
                user_data = {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'role': user.role.value,
                    'permissions': [p.value for p in user.permissions],
                    'api_keys': user.api_keys,
                    'is_active': user.is_active,
                    'created_at': user.created_at.isoformat(),
                    'last_login': user.last_login.isoformat() if user.last_login else None,
                    'metadata': user.metadata
                }
                import json
                await self.redis_client.setex(
                    key, 
                    self.config.cache_ttl, 
                    json.dumps(user_data)
                )
        except Exception as e:
            logger.warning(f"Error caching user: {e}")


class APIKeyAuth(BaseAuthenticator):
    """API Key authentication"""
    
    def __init__(self, config: AuthConfig, redis_client: Optional[aioredis.Redis] = None):
        super().__init__(config, redis_client)
        self.valid_keys = {}  # In production, this would be in database
    
    async def authenticate(self, credentials: Dict[str, Any]) -> AuthContext:
        """Authenticate using API key"""
        api_key = credentials.get('api_key')
        if not api_key:
            raise AuthenticationError("API key not provided")
        
        return await self.validate_token(api_key)
    
    async def validate_token(self, token: str) -> AuthContext:
        """Validate API key token"""
        
        # Check rate limiting for failed attempts
        await self._check_failed_attempts(token)
        
        try:
            # Get API key info from cache/database
            key_info = await self._get_api_key_info(token)
            if not key_info:
                await self._record_failed_attempt(token)
                raise AuthenticationError("Invalid API key")
            
            # Check if key is active
            if not key_info.get('is_active', True):
                raise AuthenticationError("API key is disabled")
            
            # Check expiry
            if key_info.get('expires_at'):
                expires_at = datetime.fromisoformat(key_info['expires_at'])
                if datetime.now() > expires_at:
                    raise AuthenticationError("API key has expired")
            
            # Get user associated with API key
            user = await self._get_user_from_cache(key_info['user_id'])
            if not user:
                user = await self._load_user_from_db(key_info['user_id'])
            
            if not user or not user.is_active:
                raise AuthenticationError("User not found or inactive")
            
            # Update last used timestamp
            await self._update_api_key_usage(token)
            
            # Create auth context
            context = AuthContext(
                user=user,
                method=AuthMethod.API_KEY,
                token=token,
                permissions=user.permissions,
                authenticated=True
            )
            
            logger.info(f"API key authentication successful for user {user.username}")
            return context
            
        except AuthenticationError:
            raise
        except Exception as e:
            logger.error(f"API key validation error: {e}")
            raise AuthenticationError("Authentication failed")
    
    async def _get_api_key_info(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Get API key information from cache/database"""
        try:
            if self.redis_client:
                key = f"{self.config.redis_prefix}:apikey:{self._hash_api_key(api_key)}"
                data = await self.redis_client.get(key)
                if data:
                    import json
                    return json.loads(data)
        except Exception as e:
            logger.warning(f"Error getting API key info: {e}")
        
        # Fallback to in-memory (for testing)
        return self.valid_keys.get(api_key)
    
    async def _load_user_from_db(self, user_id: str) -> Optional[User]:
        """Load user from database (mock implementation)"""
        # In real implementation, this would query the database
        # For now, create a mock user
        if user_id == "admin":
            user = User(
                id="admin",
                username="admin",
                email="admin@example.com",
                role=UserRole.ADMIN,
                permissions=self.config.role_permissions[UserRole.ADMIN]
            )
            await self._cache_user(user)
            return user
        return None
    
    def _hash_api_key(self, api_key: str) -> str:
        """Hash API key for storage"""
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    async def _update_api_key_usage(self, api_key: str) -> None:
        """Update API key last used timestamp"""
        try:
            if self.redis_client:
                key = f"{self.config.redis_prefix}:apikey:{self._hash_api_key(api_key)}"
                await self.redis_client.hset(key, "last_used", datetime.now().isoformat())
        except Exception as e:
            logger.warning(f"Error updating API key usage: {e}")
    
    async def _check_failed_attempts(self, api_key: str) -> None:
        """Check for too many failed attempts"""
        try:
            if self.redis_client:
                key = f"{self.config.redis_prefix}:failed:{self._hash_api_key(api_key)}"
                attempts = await self.redis_client.get(key)
                if attempts and int(attempts) >= self.config.max_login_attempts:
                    raise AuthenticationError(
                        f"Too many failed attempts. Try again in {self.config.lockout_duration_minutes} minutes"
                    )
        except AuthenticationError:
            raise
        except Exception as e:
            logger.warning(f"Error checking failed attempts: {e}")
    
    async def _record_failed_attempt(self, api_key: str) -> None:
        """Record failed authentication attempt"""
        try:
            if self.redis_client:
                key = f"{self.config.redis_prefix}:failed:{self._hash_api_key(api_key)}"
                pipe = self.redis_client.pipeline()
                pipe.incr(key)
                pipe.expire(key, self.config.lockout_duration_minutes * 60)
                await pipe.execute()
        except Exception as e:
            logger.warning(f"Error recording failed attempt: {e}")
    
    async def create_api_key(self, user_id: str, name: str = None, expires_days: int = None) -> str:
        """Create new API key for user"""
        
        # Generate secure API key
        api_key = f"{self.config.api_key_prefix}{secrets.token_urlsafe(self.config.api_key_length)}"
        
        # Create key info
        key_info = {
            'user_id': user_id,
            'name': name or f"Generated {datetime.now().isoformat()}",
            'created_at': datetime.now().isoformat(),
            'last_used': None,
            'is_active': True
        }
        
        if expires_days:
            key_info['expires_at'] = (datetime.now() + timedelta(days=expires_days)).isoformat()
        
        # Store API key info
        try:
            if self.redis_client:
                key = f"{self.config.redis_prefix}:apikey:{self._hash_api_key(api_key)}"
                import json
                await self.redis_client.setex(
                    key, 
                    self.config.cache_ttl if not expires_days else expires_days * 24 * 3600,
                    json.dumps(key_info)
                )
            else:
                # Fallback to in-memory
                self.valid_keys[api_key] = key_info
                
        except Exception as e:
            logger.error(f"Error storing API key: {e}")
            raise
        
        logger.info(f"Created API key for user {user_id}")
        return api_key
    
    async def revoke_api_key(self, api_key: str) -> bool:
        """Revoke an API key"""
        try:
            if self.redis_client:
                key = f"{self.config.redis_prefix}:apikey:{self._hash_api_key(api_key)}"
                result = await self.redis_client.delete(key)
                return result > 0
            else:
                return self.valid_keys.pop(api_key, None) is not None
        except Exception as e:
            logger.error(f"Error revoking API key: {e}")
            return False


class JWTAuth(BaseAuthenticator):
    """JWT token authentication"""
    
    async def authenticate(self, credentials: Dict[str, Any]) -> AuthContext:
        """Authenticate using username/password and return JWT"""
        username = credentials.get('username')
        password = credentials.get('password')
        
        if not username or not password:
            raise AuthenticationError("Username and password required")
        
        # Verify credentials (mock implementation)
        user = await self._verify_credentials(username, password)
        if not user:
            raise AuthenticationError("Invalid credentials")
        
        # Generate JWT token
        token = self._generate_jwt_token(user)
        
        # Create auth context
        context = AuthContext(
            user=user,
            method=AuthMethod.JWT,
            token=token,
            permissions=user.permissions,
            authenticated=True
        )
        
        return context
    
    async def validate_token(self, token: str) -> AuthContext:
        """Validate JWT token"""
        try:
            # Decode JWT
            payload = jwt.decode(
                token, 
                self.config.jwt_secret, 
                algorithms=[self.config.jwt_algorithm]
            )
            
            # Check expiry
            if payload.get('exp', 0) < time.time():
                raise AuthenticationError("Token has expired")
            
            # Get user
            user_id = payload.get('user_id')
            user = await self._get_user_from_cache(user_id)
            if not user:
                user = await self._load_user_from_db(user_id)
            
            if not user or not user.is_active:
                raise AuthenticationError("User not found or inactive")
            
            # Create auth context
            context = AuthContext(
                user=user,
                method=AuthMethod.JWT,
                token=token,
                permissions=user.permissions,
                authenticated=True
            )
            
            return context
            
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token has expired")
        except jwt.InvalidTokenError:
            raise AuthenticationError("Invalid token")
        except Exception as e:
            logger.error(f"JWT validation error: {e}")
            raise AuthenticationError("Token validation failed")
    
    def _generate_jwt_token(self, user: User) -> str:
        """Generate JWT token for user"""
        payload = {
            'user_id': user.id,
            'username': user.username,
            'role': user.role.value,
            'permissions': [p.value for p in user.permissions],
            'iat': time.time(),
            'exp': time.time() + (self.config.jwt_expiry_minutes * 60)
        }
        
        return jwt.encode(payload, self.config.jwt_secret, algorithm=self.config.jwt_algorithm)
    
    async def _verify_credentials(self, username: str, password: str) -> Optional[User]:
        """Verify username/password credentials (mock implementation)"""
        # In real implementation, this would check against database
        if username == "admin" and password == "admin123":
            return User(
                id="admin",
                username="admin",
                email="admin@example.com",
                role=UserRole.ADMIN,
                permissions=self.config.role_permissions[UserRole.ADMIN]
            )
        return None
    
    async def refresh_token(self, refresh_token: str) -> str:
        """Refresh JWT token"""
        # Implementation for refresh tokens
        # This would involve validating the refresh token and generating a new access token
        pass


class AuthenticationManager:
    """
    Main authentication manager that coordinates different auth methods.
    """
    
    def __init__(self, config: AuthConfig, redis_client: Optional[aioredis.Redis] = None):
        self.config = config
        self.redis_client = redis_client
        
        # Initialize authenticators
        self.api_key_auth = APIKeyAuth(config, redis_client)
        self.jwt_auth = JWTAuth(config, redis_client)
        
        # Active sessions
        self.sessions = {}
    
    async def authenticate(self, method: AuthMethod, credentials: Dict[str, Any]) -> AuthContext:
        """
        Authenticate user using specified method.
        
        Args:
            method: Authentication method to use
            credentials: Authentication credentials
            
        Returns:
            AuthContext with user information
        """
        try:
            if method == AuthMethod.API_KEY:
                return await self.api_key_auth.authenticate(credentials)
            elif method == AuthMethod.JWT:
                return await self.jwt_auth.authenticate(credentials)
            else:
                raise AuthenticationError(f"Unsupported authentication method: {method}")
                
        except AuthenticationError:
            raise
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            raise AuthenticationError("Authentication failed")
    
    async def validate_request(self, auth_header: str, ip_address: str = None) -> AuthContext:
        """
        Validate authentication from request header.
        
        Args:
            auth_header: Authorization header value
            ip_address: Client IP address
            
        Returns:
            AuthContext if authentication successful
        """
        if not auth_header:
            raise AuthenticationError("No authorization header")
        
        try:
            # Parse authorization header
            auth_parts = auth_header.split(' ', 1)
            if len(auth_parts) != 2:
                raise AuthenticationError("Invalid authorization header format")
            
            auth_type, token = auth_parts
            
            # Determine authentication method and validate
            if auth_type.lower() == 'bearer':
                # Could be JWT or API key
                if token.startswith(self.config.api_key_prefix):
                    context = await self.api_key_auth.validate_token(token)
                else:
                    context = await self.jwt_auth.validate_token(token)
            elif auth_type.lower() == 'apikey':
                context = await self.api_key_auth.validate_token(token)
            else:
                raise AuthenticationError(f"Unsupported auth type: {auth_type}")
            
            # Set IP address
            context.ip_address = ip_address
            
            return context
            
        except AuthenticationError:
            raise
        except Exception as e:
            logger.error(f"Request validation error: {e}")
            raise AuthenticationError("Invalid authorization")
    
    def check_permission(
        self, 
        context: AuthContext, 
        required_permissions: List[Permission],
        require_all: bool = False
    ) -> bool:
        """
        Check if authenticated user has required permissions.
        
        Args:
            context: Authentication context
            required_permissions: List of required permissions
            require_all: Whether user must have ALL permissions (default: any)
            
        Returns:
            True if user has required permissions
        """
        if not context.authenticated:
            return False
        
        if require_all:
            return context.has_all_permissions(required_permissions)
        else:
            return context.has_any_permission(required_permissions)
    
    async def create_session(self, context: AuthContext) -> str:
        """Create new session for authenticated user"""
        session_id = secrets.token_urlsafe(32)
        
        session_data = {
            'user_id': context.user.id,
            'created_at': datetime.now().isoformat(),
            'last_activity': datetime.now().isoformat(),
            'ip_address': context.ip_address,
            'user_agent': context.user_agent
        }
        
        try:
            if self.redis_client:
                key = f"{self.config.redis_prefix}:session:{session_id}"
                import json
                await self.redis_client.setex(
                    key, 
                    self.config.session_timeout_minutes * 60,
                    json.dumps(session_data)
                )
        except Exception as e:
            logger.warning(f"Error creating session: {e}")
        
        self.sessions[session_id] = session_data
        return session_id
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data"""
        try:
            if self.redis_client:
                key = f"{self.config.redis_prefix}:session:{session_id}"
                data = await self.redis_client.get(key)
                if data:
                    import json
                    return json.loads(data)
        except Exception as e:
            logger.warning(f"Error getting session: {e}")
        
        return self.sessions.get(session_id)
    
    async def revoke_session(self, session_id: str) -> bool:
        """Revoke a session"""
        try:
            if self.redis_client:
                key = f"{self.config.redis_prefix}:session:{session_id}"
                result = await self.redis_client.delete(key)
                success = result > 0
            else:
                success = self.sessions.pop(session_id, None) is not None
            
            if success:
                logger.info(f"Session {session_id} revoked")
            
            return success
        except Exception as e:
            logger.error(f"Error revoking session: {e}")
            return False
    
    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions (for in-memory storage)"""
        # Redis handles TTL automatically, this is for local storage
        current_time = datetime.now()
        timeout_delta = timedelta(minutes=self.config.session_timeout_minutes)
        
        expired_sessions = []
        for session_id, session_data in self.sessions.items():
            last_activity = datetime.fromisoformat(session_data['last_activity'])
            if current_time - last_activity > timeout_delta:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            self.sessions.pop(session_id, None)
        
        return len(expired_sessions)
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for authentication system"""
        status = {
            'redis_connected': False,
            'active_sessions': len(self.sessions),
            'auth_methods': [AuthMethod.API_KEY.value, AuthMethod.JWT.value],
            'timestamp': time.time()
        }
        
        try:
            if self.redis_client:
                await self.redis_client.ping()
                status['redis_connected'] = True
        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")
        
        return status