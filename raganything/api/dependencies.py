"""
FastAPI dependencies for RAG-Anything API.

Provides dependency injection for services, authentication, and configuration.
"""

import os
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..backends.graphiti_direct import GraphitiDirectBackend, GraphitiDirectConfig
from ..backends.base import BackendConfig, BackendType
from ..config import RAGAnythingConfig

# Security
security = HTTPBearer(auto_error=False)

# Global service instance
_rag_service = None


async def get_rag_service():
    """Get or create the RAG service instance."""
    global _rag_service
    
    if _rag_service is None:
        # Initialize RAG service
        config = RAGAnythingConfig()
        
        # Create backend configuration
        backend_config = BackendConfig(
            backend_type=BackendType.GRAPHITI,
            working_dir=config.working_dir,
            llm_model_func=config.llm_model_func,
            embedding_func=config.embedding_func,
            vision_model_func=config.vision_model_func,
            backend_kwargs={
                'graphiti_config': {
                    'graph_provider': os.getenv('GRAPHITI_GRAPH_PROVIDER', 'falkordb'),
                    'falkordb_host': os.getenv('GRAPHITI_GRAPH_HOST', 'localhost'),
                    'falkordb_port': int(os.getenv('GRAPHITI_GRAPH_PORT', '6379')),
                    'falkordb_database': os.getenv('GRAPHITI_GRAPH_DATABASE', 'rag_graph'),
                    'falkordb_password': os.getenv('GRAPHITI_GRAPH_PASSWORD'),
                    'neo4j_uri': os.getenv('GRAPHITI_NEO4J_URI', 'bolt://localhost:7687'),
                    'neo4j_user': os.getenv('GRAPHITI_NEO4J_USER', 'neo4j'),
                    'neo4j_password': os.getenv('GRAPHITI_NEO4J_PASSWORD', 'password'),
                    'llm_provider': os.getenv('GRAPHITI_LLM_PROVIDER', 'openai'),
                    'llm_model': os.getenv('GRAPHITI_LLM_MODEL', 'gpt-4o-mini'),
                    'llm_api_key': os.getenv('OPENAI_API_KEY'),
                    'embedder_provider': os.getenv('GRAPHITI_EMBEDDER_PROVIDER', 'openai'),
                    'embedder_model': os.getenv('GRAPHITI_EMBEDDER_MODEL', 'text-embedding-3-small'),
                    'default_group_id': os.getenv('GRAPHITI_GROUP_ID', 'default'),
                    'preserve_document_structure': os.getenv('PRESERVE_DOCUMENT_STRUCTURE', 'true').lower() == 'true',
                    'auto_build_communities': os.getenv('AUTO_BUILD_COMMUNITIES', 'false').lower() == 'true',
                    'enable_cache': os.getenv('ENABLE_CACHE', 'true').lower() == 'true'
                }
            }
        )
        
        # Create and initialize backend
        _rag_service = GraphitiDirectBackend(backend_config)
        await _rag_service.initialize()
    
    return _rag_service


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[Dict[str, Any]]:
    """Get current user from authorization token (optional)."""
    if not credentials:
        return None
    
    # In a real implementation, you would validate the token
    # and return user information from your auth system
    try:
        # Placeholder: decode JWT or validate API key
        # For now, return a mock user
        return {
            'user_id': 'user_123',
            'username': 'test_user',
            'roles': ['user']
        }
    except Exception:
        # Invalid token - return None for anonymous access
        return None


async def get_admin_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Dict[str, Any]:
    """Get current user and verify admin privileges."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required for admin operations",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # In a real implementation, validate token and check admin role
    try:
        # Placeholder admin validation
        user = {
            'user_id': 'admin_123',
            'username': 'admin_user',
            'roles': ['admin', 'user']
        }
        
        if 'admin' not in user.get('roles', []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required"
            )
        
        return user
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"}
        )