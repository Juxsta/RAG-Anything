"""
Base classes and interfaces for RAG backend abstraction.

This module defines the abstract base classes that all RAG backends must implement,
providing a unified interface for different graph-based RAG systems.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, Callable
from enum import Enum
import asyncio


class BackendType(Enum):
    """Supported backend types"""
    LIGHTRAG = "lightrag"
    GRAPHITI = "graphiti"


@dataclass
class BackendConfig:
    """Configuration for RAG backends"""
    backend_type: BackendType
    working_dir: str = "./rag_storage"
    
    # Model configuration
    llm_model_func: Optional[Callable] = None
    embedding_func: Optional[Callable] = None  
    vision_model_func: Optional[Callable] = None
    
    # Backend-specific configuration
    backend_kwargs: Dict[str, Any] = field(default_factory=dict)
    
    # Common settings
    enable_cache: bool = True
    max_concurrent_operations: int = 10


@dataclass
class QueryResult:
    """Standardized query result across backends"""
    content: str
    sources: List[Dict[str, Any]] = field(default_factory=list)
    entities: List[Dict[str, Any]] = field(default_factory=list)
    relationships: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    query_time: Optional[datetime] = None
    backend_type: Optional[BackendType] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary"""
        return {
            "content": self.content,
            "sources": self.sources,
            "entities": self.entities,
            "relationships": self.relationships,
            "metadata": self.metadata,
            "query_time": self.query_time.isoformat() if self.query_time else None,
            "backend_type": self.backend_type.value if self.backend_type else None,
        }


@dataclass
class InsertResult:
    """Result of content insertion operation"""
    success: bool
    message: str = ""
    inserted_entities: int = 0
    inserted_relationships: int = 0
    processing_time: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary"""
        return {
            "success": self.success,
            "message": self.message,
            "inserted_entities": self.inserted_entities,
            "inserted_relationships": self.inserted_relationships,
            "processing_time": self.processing_time,
            "metadata": self.metadata,
        }


class BaseRAGBackend(ABC):
    """
    Abstract base class for RAG backends.
    
    This class defines the interface that all RAG backends must implement,
    providing a unified API for different graph-based RAG systems like LightRAG
    and Graphiti.
    """
    
    def __init__(self, config: BackendConfig):
        """Initialize the backend with configuration"""
        self.config = config
        self.backend_type = config.backend_type
        self._initialized = False
        
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the backend and its dependencies"""
        pass
    
    @abstractmethod
    async def finalize(self) -> None:
        """Clean up resources and finalize the backend"""
        pass
    
    @abstractmethod
    async def insert_text(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> InsertResult:
        """
        Insert plain text content into the knowledge graph.
        
        Args:
            text: The text content to insert
            metadata: Optional metadata for the content
            
        Returns:
            InsertResult with details about the insertion
        """
        pass
    
    @abstractmethod
    async def insert_multimodal_content(
        self,
        content: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> InsertResult:
        """
        Insert multimodal content (text, images, tables, etc.) into the knowledge graph.
        
        Args:
            content: Dictionary containing multimodal content
            metadata: Optional metadata for the content
            
        Returns:
            InsertResult with details about the insertion
        """
        pass
    
    @abstractmethod
    async def query(
        self,
        query: str,
        mode: str = "hybrid",
        top_k: int = 10,
        **kwargs
    ) -> QueryResult:
        """
        Query the knowledge graph.
        
        Args:
            query: The query string
            mode: Query mode (e.g., "local", "global", "hybrid", "naive")
            top_k: Number of top results to return
            **kwargs: Additional backend-specific parameters
            
        Returns:
            QueryResult with the query response and metadata
        """
        pass
    
    @abstractmethod
    async def get_entities(
        self,
        limit: int = 100,
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve entities from the knowledge graph.
        
        Args:
            limit: Maximum number of entities to return
            offset: Offset for pagination
            filters: Optional filters to apply
            
        Returns:
            List of entity dictionaries
        """
        pass
    
    @abstractmethod  
    async def get_relationships(
        self,
        limit: int = 100,
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relationships from the knowledge graph.
        
        Args:
            limit: Maximum number of relationships to return
            offset: Offset for pagination
            filters: Optional filters to apply
            
        Returns:
            List of relationship dictionaries
        """
        pass
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check of the backend.
        
        Returns:
            Dictionary with health status information
        """
        return {
            "backend_type": self.backend_type.value,
            "initialized": self._initialized,
            "status": "healthy" if self._initialized else "not_initialized",
            "timestamp": datetime.now().isoformat(),
        }
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the knowledge graph.
        
        Returns:
            Dictionary with statistics (entity count, relationship count, etc.)
        """
        try:
            entities = await self.get_entities(limit=0)  # Get count only
            relationships = await self.get_relationships(limit=0)  # Get count only
            
            return {
                "backend_type": self.backend_type.value,
                "entity_count": len(entities) if isinstance(entities, list) else 0,
                "relationship_count": len(relationships) if isinstance(relationships, list) else 0,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {
                "backend_type": self.backend_type.value,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(backend_type={self.backend_type.value})"