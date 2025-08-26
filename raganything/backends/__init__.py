"""
Backend Abstraction Layer for RAG-Anything

This package provides a unified interface for different RAG backends including
LightRAG and Graphiti, following the Strategy and Adapter patterns for extensibility.
"""

from .base import BaseRAGBackend, BackendConfig, QueryResult, InsertResult
from .lightrag_adapter import LightRAGAdapter
from .graphiti_bridge import GraphitiBridge

__all__ = [
    "BaseRAGBackend",
    "BackendConfig", 
    "QueryResult",
    "InsertResult",
    "LightRAGAdapter",
    "GraphitiBridge",
]