"""
API endpoints for RAG-Anything with Graphiti integration.

This package contains all the FastAPI route handlers organized by functionality:
- Document processing endpoints
- Query and search endpoints  
- Entity and relationship management
- Community and analytics endpoints
- Health monitoring and statistics
- File upload and batch processing
"""

from .processing import router as processing_router
from .querying import router as querying_router
from .entities import router as entities_router
from .communities import router as communities_router
from .health import router as health_router
from .files import router as files_router
from .management import router as management_router

__all__ = [
    'processing_router',
    'querying_router', 
    'entities_router',
    'communities_router',
    'health_router',
    'files_router',
    'management_router'
]