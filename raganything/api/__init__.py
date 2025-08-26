"""
FastAPI REST Service for RAG-Anything with Graphiti Integration.

This package provides comprehensive REST API endpoints for:
- Document processing with multimodal support
- Knowledge graph querying and management  
- Episode and entity management
- Community building and analytics
- Health monitoring and statistics
"""

from .main import create_app, GraphitiRAGApp
from .models import *
from .endpoints import *

__all__ = [
    'create_app',
    'GraphitiRAGApp'
]