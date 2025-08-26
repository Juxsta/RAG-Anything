"""
GraphitiRAGAnything Integration Class.

This module provides the main integration class that combines RAG-Anything's
powerful multimodal parsing capabilities with Graphiti's episodic knowledge
graph functionality.
"""

import asyncio
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable, Union
from dataclasses import dataclass, field

from lightrag.utils import logger

from .config import RAGAnythingConfig
from .backends.base import BaseRAGBackend, BackendConfig, BackendType, QueryResult, InsertResult
from .backends.lightrag_adapter import LightRAGAdapter
from .backends.graphiti_bridge import GraphitiBridge
from .episode_converter import EpisodeConverter
from .processor import ProcessorMixin
from .query import QueryMixin
from .batch import BatchMixin


@dataclass
class GraphitiRAGAnythingConfig(RAGAnythingConfig):
    """Extended configuration for Graphiti integration"""
    
    # Backend selection
    backend_type: BackendType = BackendType.GRAPHITI
    """Which backend to use: LIGHTRAG or GRAPHITI"""
    
    # Graphiti-specific configuration
    graphiti_config: Dict[str, Any] = field(default_factory=dict)
    """Graphiti-specific configuration parameters"""
    
    # Episode conversion settings
    preserve_document_structure: bool = True
    """Whether to maintain document hierarchy in episodes"""
    
    default_group_id: str = "default"
    """Default group ID for Graphiti episodes"""
    
    # Backend fallback
    enable_backend_fallback: bool = True
    """Enable fallback to LightRAG if Graphiti fails"""


class GraphitiRAGAnything(QueryMixin, ProcessorMixin, BatchMixin):
    """
    Main integration class combining RAG-Anything with Graphiti.
    
    This class provides a unified interface for multimodal document processing
    and episodic knowledge graph operations, supporting both LightRAG and
    Graphiti backends with seamless switching capabilities.
    """
    
    def __init__(
        self,
        config: Optional[GraphitiRAGAnythingConfig] = None,
        backend: Optional[BaseRAGBackend] = None,
        llm_model_func: Optional[Callable] = None,
        vision_model_func: Optional[Callable] = None,
        embedding_func: Optional[Callable] = None,
        **kwargs
    ):
        """
        Initialize the GraphitiRAGAnything integration.
        
        Args:
            config: Configuration object
            backend: Pre-initialized backend (optional)
            llm_model_func: LLM model function
            vision_model_func: Vision model function  
            embedding_func: Embedding function
            **kwargs: Additional configuration parameters
        """
        # Initialize configuration
        self.config = config or GraphitiRAGAnythingConfig()
        
        # Update config with kwargs
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        
        # Store model functions
        self.llm_model_func = llm_model_func
        self.vision_model_func = vision_model_func
        self.embedding_func = embedding_func
        
        # Initialize components
        self.backend = backend
        self.episode_converter = EpisodeConverter(
            default_group_id=self.config.default_group_id,
            preserve_document_structure=self.config.preserve_document_structure
        )
        
        # Internal state
        self._initialized = False
        self.logger = logger
        
        # Initialize document parser (inherited from RAGAnything)
        from .parser import MineruParser, DoclingParser
        self.doc_parser = (
            DoclingParser() if self.config.parser == "docling" else MineruParser()
        )
        
        # Set working directory
        self.working_dir = self.config.working_dir
        
        # Create working directory if needed
        if not os.path.exists(self.working_dir):
            os.makedirs(self.working_dir)
            self.logger.info(f"Created working directory: {self.working_dir}")
    
    async def initialize(self) -> None:
        """Initialize the integration and its backend"""
        try:
            # Initialize backend if not provided
            if self.backend is None:
                self.backend = await self._create_backend()
            
            # Initialize backend
            if not self.backend._initialized:
                await self.backend.initialize()
            
            self._initialized = True
            self.logger.info(f"GraphitiRAGAnything initialized with {self.backend.backend_type.value} backend")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize GraphitiRAGAnything: {e}")
            
            # Try fallback to LightRAG if enabled
            if (self.config.enable_backend_fallback 
                and self.config.backend_type == BackendType.GRAPHITI):
                self.logger.info("Attempting fallback to LightRAG backend")
                await self._fallback_to_lightrag()
            else:
                raise
    
    async def _create_backend(self) -> BaseRAGBackend:
        """Create the appropriate backend based on configuration"""
        backend_config = BackendConfig(
            backend_type=self.config.backend_type,
            working_dir=self.working_dir,
            llm_model_func=self.llm_model_func,
            embedding_func=self.embedding_func,
            vision_model_func=self.vision_model_func,
            backend_kwargs=self.config.graphiti_config
        )
        
        if self.config.backend_type == BackendType.GRAPHITI:
            return GraphitiBridge(backend_config)
        else:
            return LightRAGAdapter(backend_config)
    
    async def _fallback_to_lightrag(self) -> None:
        """Fallback to LightRAG backend if Graphiti fails"""
        try:
            self.logger.info("Initializing LightRAG fallback backend")
            
            backend_config = BackendConfig(
                backend_type=BackendType.LIGHTRAG,
                working_dir=self.working_dir,
                llm_model_func=self.llm_model_func,
                embedding_func=self.embedding_func,
                vision_model_func=self.vision_model_func
            )
            
            self.backend = LightRAGAdapter(backend_config)
            await self.backend.initialize()
            
            self._initialized = True
            self.logger.info("Successfully initialized LightRAG fallback backend")
            
        except Exception as e:
            self.logger.error(f"Fallback to LightRAG also failed: {e}")
            raise RuntimeError("Both Graphiti and LightRAG backends failed to initialize")
    
    async def finalize(self) -> None:
        """Clean up resources"""
        try:
            if self.backend:
                await self.backend.finalize()
            
            self._initialized = False
            self.logger.info("GraphitiRAGAnything finalized successfully")
            
        except Exception as e:
            self.logger.error(f"Error during finalization: {e}")
            raise
    
    async def process_document(
        self,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> InsertResult:
        """
        Process a document and insert it into the knowledge graph.
        
        Args:
            file_path: Path to the document file
            metadata: Optional metadata for the document
            
        Returns:
            InsertResult with processing details
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            self.logger.info(f"Processing document: {file_path}")
            
            # Parse the document using RAG-Anything's parsers
            parsed_content = await self._parse_document(file_path)
            
            # Create document metadata
            doc_metadata = {
                "filename": os.path.basename(file_path),
                "file_path": file_path,
                "processed_at": datetime.now(),
                **(metadata or {})
            }
            
            # Insert content based on backend type
            if self.config.backend_type == BackendType.GRAPHITI:
                return await self._process_with_graphiti(parsed_content, doc_metadata)
            else:
                return await self._process_with_lightrag(parsed_content, doc_metadata)
            
        except Exception as e:
            self.logger.error(f"Error processing document {file_path}: {e}")
            return InsertResult(
                success=False,
                message=f"Failed to process document: {str(e)}",
                metadata=metadata or {}
            )
    
    async def _parse_document(self, file_path: str) -> Dict[str, Any]:
        """Parse document using RAG-Anything's parsers"""
        # Use the existing parser from RAG-Anything
        if not self.doc_parser.check_installation():
            raise RuntimeError(f"Parser '{self.config.parser}' is not properly installed")
        
        # Parse the document
        result = await self.doc_parser.parse_document(
            file_path,
            output_dir=self.config.parser_output_dir,
            parse_method=self.config.parse_method
        )
        
        return result
    
    async def _process_with_graphiti(
        self,
        content: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> InsertResult:
        """Process content with Graphiti backend using episodes"""
        # Convert content to episodes
        episodes = self.episode_converter.convert_document(content, metadata)
        
        if not episodes:
            return InsertResult(
                success=False,
                message="No episodes generated from content",
                metadata=metadata
            )
        
        # Insert episodes into Graphiti
        total_entities = 0
        total_relationships = 0
        successful_episodes = 0
        
        for episode in episodes:
            try:
                episode_dict = episode.to_dict()
                result = await self.backend.insert_multimodal_content(
                    episode_dict, 
                    episode.original_metadata
                )
                
                if result.success:
                    successful_episodes += 1
                    total_entities += result.inserted_entities
                    total_relationships += result.inserted_relationships
                
            except Exception as e:
                self.logger.error(f"Error inserting episode {episode.name}: {e}")
                continue
        
        return InsertResult(
            success=successful_episodes > 0,
            message=f"Inserted {successful_episodes}/{len(episodes)} episodes",
            inserted_entities=total_entities,
            inserted_relationships=total_relationships,
            metadata={
                **metadata,
                "total_episodes": len(episodes),
                "successful_episodes": successful_episodes,
                "backend": "graphiti"
            }
        )
    
    async def _process_with_lightrag(
        self,
        content: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> InsertResult:
        """Process content with LightRAG backend"""
        # Convert multimodal content to text for LightRAG
        text_content = self._convert_to_text(content)
        
        # Insert into LightRAG
        return await self.backend.insert_text(text_content, metadata)
    
    def _convert_to_text(self, content: Dict[str, Any]) -> str:
        """Convert parsed content to text representation"""
        text_parts = []
        
        # Handle different content structures
        if isinstance(content, dict):
            if 'text' in content:
                text_parts.append(content['text'])
            elif 'content' in content:
                text_parts.append(str(content['content']))
            else:
                # Extract all string values
                for key, value in content.items():
                    if isinstance(value, str) and value.strip():
                        text_parts.append(f"{key}: {value}")
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    item_text = self._convert_to_text(item)
                    if item_text:
                        text_parts.append(item_text)
                elif isinstance(item, str):
                    text_parts.append(item)
        
        return "\n\n".join(text_parts)
    
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
            query: Query string
            mode: Query mode
            top_k: Number of results to return
            **kwargs: Additional parameters
            
        Returns:
            QueryResult with response
        """
        if not self._initialized:
            await self.initialize()
        
        return await self.backend.query(query, mode, top_k, **kwargs)
    
    async def get_backend_stats(self) -> Dict[str, Any]:
        """Get statistics from the current backend"""
        if not self._initialized:
            await self.initialize()
        
        return await self.backend.get_stats()
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform a health check of the integration"""
        status = {
            "integration_initialized": self._initialized,
            "config": {
                "backend_type": self.config.backend_type.value,
                "working_dir": self.working_dir,
                "parser": self.config.parser,
            },
            "timestamp": datetime.now().isoformat()
        }
        
        if self.backend:
            backend_health = await self.backend.health_check()
            status["backend"] = backend_health
        else:
            status["backend"] = {"status": "not_initialized"}
        
        return status
    
    async def switch_backend(self, backend_type: BackendType) -> bool:
        """
        Switch to a different backend.
        
        Args:
            backend_type: Target backend type
            
        Returns:
            True if switch was successful
        """
        if self.config.backend_type == backend_type:
            self.logger.info(f"Already using {backend_type.value} backend")
            return True
        
        try:
            # Finalize current backend
            if self.backend:
                await self.backend.finalize()
            
            # Update configuration
            self.config.backend_type = backend_type
            
            # Create new backend
            self.backend = await self._create_backend()
            await self.backend.initialize()
            
            self.logger.info(f"Successfully switched to {backend_type.value} backend")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to switch to {backend_type.value} backend: {e}")
            return False
    
    def get_config_info(self) -> Dict[str, Any]:
        """Get comprehensive configuration information"""
        base_config = super().get_config_info() if hasattr(super(), 'get_config_info') else {}
        
        graphiti_config = {
            "integration": {
                "backend_type": self.config.backend_type.value,
                "enable_backend_fallback": self.config.enable_backend_fallback,
                "default_group_id": self.config.default_group_id,
                "preserve_document_structure": self.config.preserve_document_structure,
            },
            "graphiti_config": self.config.graphiti_config,
            "status": {
                "initialized": self._initialized,
                "backend_initialized": self.backend._initialized if self.backend else False,
            }
        }
        
        # Merge with base configuration
        base_config.update(graphiti_config)
        return base_config
    
    def __repr__(self) -> str:
        return f"GraphitiRAGAnything(backend={self.config.backend_type.value}, initialized={self._initialized})"