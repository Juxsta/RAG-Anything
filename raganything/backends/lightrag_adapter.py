"""
LightRAG Adapter for Backend Abstraction Layer.

This adapter wraps the existing LightRAG functionality to provide
a standardized interface, maintaining backward compatibility while
enabling seamless integration with the new backend abstraction.
"""

import asyncio
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from lightrag import LightRAG
from lightrag.utils import logger

from .base import BaseRAGBackend, BackendConfig, BackendType, QueryResult, InsertResult


class LightRAGAdapter(BaseRAGBackend):
    """
    Adapter for LightRAG backend that implements the BaseRAGBackend interface.
    
    This class wraps the existing LightRAG functionality to provide backward
    compatibility while enabling the new backend abstraction layer.
    """
    
    def __init__(self, config: BackendConfig, lightrag_instance: Optional[LightRAG] = None):
        """
        Initialize the LightRAG adapter.
        
        Args:
            config: Backend configuration
            lightrag_instance: Optional pre-initialized LightRAG instance
        """
        if config.backend_type != BackendType.LIGHTRAG:
            raise ValueError("Config backend_type must be LIGHTRAG for LightRAGAdapter")
            
        super().__init__(config)
        self.lightrag = lightrag_instance
        self.logger = logger
        
    async def initialize(self) -> None:
        """Initialize the LightRAG backend"""
        try:
            if self.lightrag is None:
                # Validate required functions
                if self.config.llm_model_func is None:
                    raise ValueError("llm_model_func is required when LightRAG is not pre-initialized")
                if self.config.embedding_func is None:
                    raise ValueError("embedding_func is required when LightRAG is not pre-initialized")
                
                # Prepare LightRAG initialization parameters
                lightrag_params = {
                    "working_dir": self.config.working_dir,
                    "llm_model_func": self.config.llm_model_func,
                    "embedding_func": self.config.embedding_func,
                }
                
                # Add any backend-specific kwargs
                lightrag_params.update(self.config.backend_kwargs)
                
                self.logger.info(f"Initializing LightRAG with working_dir: {self.config.working_dir}")
                
                # Create LightRAG instance
                self.lightrag = LightRAG(**lightrag_params)
            
            # Initialize LightRAG storages if not already done
            if (not hasattr(self.lightrag, '_storages_status') 
                or self.lightrag._storages_status.name != "INITIALIZED"):
                self.logger.info("Initializing LightRAG storages")
                await self.lightrag.initialize_storages()
                
                # Initialize pipeline status
                from lightrag.kg.shared_storage import initialize_pipeline_status
                await initialize_pipeline_status()
            
            self._initialized = True
            self.logger.info("LightRAG adapter initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize LightRAG adapter: {e}")
            raise
    
    async def finalize(self) -> None:
        """Clean up LightRAG resources"""
        try:
            if self.lightrag and hasattr(self.lightrag, 'finalize_storages'):
                self.logger.info("Finalizing LightRAG storages")
                await self.lightrag.finalize_storages()
            
            self._initialized = False
            self.logger.info("LightRAG adapter finalized successfully")
            
        except Exception as e:
            self.logger.error(f"Error during LightRAG adapter finalization: {e}")
            raise
    
    async def insert_text(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> InsertResult:
        """Insert text content using LightRAG"""
        if not self._initialized:
            raise RuntimeError("Backend not initialized. Call initialize() first.")
        
        start_time = time.time()
        
        try:
            # Use LightRAG's ainsert method for text insertion
            await self.lightrag.ainsert(text)
            
            processing_time = time.time() - start_time
            
            return InsertResult(
                success=True,
                message="Text content inserted successfully",
                processing_time=processing_time,
                metadata=metadata or {}
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"Error inserting text content: {e}")
            
            return InsertResult(
                success=False,
                message=f"Failed to insert text content: {str(e)}",
                processing_time=processing_time,
                metadata=metadata or {}
            )
    
    async def insert_multimodal_content(
        self,
        content: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> InsertResult:
        """
        Insert multimodal content using LightRAG.
        
        For LightRAG, this converts multimodal content to text format
        and uses the standard text insertion method.
        """
        if not self._initialized:
            raise RuntimeError("Backend not initialized. Call initialize() first.")
        
        try:
            # Convert multimodal content to text representation
            text_content = self._convert_multimodal_to_text(content)
            
            # Use the standard text insertion method
            result = await self.insert_text(text_content, metadata)
            result.metadata.update({
                "original_content_type": "multimodal",
                "converted_to_text": True
            })
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error inserting multimodal content: {e}")
            return InsertResult(
                success=False,
                message=f"Failed to insert multimodal content: {str(e)}",
                metadata=metadata or {}
            )
    
    def _convert_multimodal_to_text(self, content: Dict[str, Any]) -> str:
        """Convert multimodal content dictionary to text representation"""
        text_parts = []
        
        # Handle different content types
        if 'text' in content:
            text_parts.append(content['text'])
        
        if 'title' in content:
            text_parts.append(f"Title: {content['title']}")
        
        if 'description' in content:
            text_parts.append(f"Description: {content['description']}")
        
        if 'image_caption' in content:
            text_parts.append(f"Image: {content['image_caption']}")
        
        if 'table_content' in content:
            text_parts.append(f"Table: {content['table_content']}")
        
        if 'equation' in content:
            text_parts.append(f"Equation: {content['equation']}")
        
        # Handle any additional metadata
        if 'context' in content:
            text_parts.append(f"Context: {content['context']}")
        
        return "\n\n".join(text_parts)
    
    async def query(
        self,
        query: str,
        mode: str = "hybrid",
        top_k: int = 10,
        **kwargs
    ) -> QueryResult:
        """Query using LightRAG"""
        if not self._initialized:
            raise RuntimeError("Backend not initialized. Call initialize() first.")
        
        query_start = datetime.now()
        
        try:
            # Use LightRAG's aquery method
            result = await self.lightrag.aquery(query, param=mode, top_k=top_k, **kwargs)
            
            # Convert LightRAG result to standardized QueryResult
            return QueryResult(
                content=result,
                sources=[],  # LightRAG doesn't return structured sources
                entities=[],  # Would need to extract from graph if needed
                relationships=[],  # Would need to extract from graph if needed
                metadata={
                    "mode": mode,
                    "top_k": top_k,
                    "additional_params": kwargs
                },
                query_time=query_start,
                backend_type=BackendType.LIGHTRAG
            )
            
        except Exception as e:
            self.logger.error(f"Error during LightRAG query: {e}")
            return QueryResult(
                content=f"Query failed: {str(e)}",
                metadata={"error": str(e), "mode": mode},
                query_time=query_start,
                backend_type=BackendType.LIGHTRAG
            )
    
    async def get_entities(
        self,
        limit: int = 100,
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve entities from LightRAG's knowledge graph"""
        if not self._initialized:
            raise RuntimeError("Backend not initialized. Call initialize() first.")
        
        try:
            # Access LightRAG's entity storage
            # Note: This is a simplified implementation
            # In practice, you'd need to access the actual graph storage
            entities = []
            
            # This would require accessing LightRAG's internal graph structure
            # For now, return empty list as LightRAG doesn't expose direct entity access
            self.logger.warning("Entity retrieval not fully implemented for LightRAG adapter")
            
            return entities[offset:offset + limit] if entities else []
            
        except Exception as e:
            self.logger.error(f"Error retrieving entities: {e}")
            return []
    
    async def get_relationships(
        self,
        limit: int = 100,
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve relationships from LightRAG's knowledge graph"""
        if not self._initialized:
            raise RuntimeError("Backend not initialized. Call initialize() first.")
        
        try:
            # Access LightRAG's relationship storage
            # Note: This is a simplified implementation
            relationships = []
            
            # This would require accessing LightRAG's internal graph structure
            # For now, return empty list as LightRAG doesn't expose direct relationship access
            self.logger.warning("Relationship retrieval not fully implemented for LightRAG adapter")
            
            return relationships[offset:offset + limit] if relationships else []
            
        except Exception as e:
            self.logger.error(f"Error retrieving relationships: {e}")
            return []
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get statistics from LightRAG"""
        try:
            base_stats = await super().get_stats()
            
            # Add LightRAG-specific stats
            lightrag_stats = {
                "working_dir": self.config.working_dir,
                "lightrag_initialized": self.lightrag is not None,
            }
            
            # Try to get more detailed stats if possible
            if self.lightrag and hasattr(self.lightrag, 'working_dir'):
                lightrag_stats["actual_working_dir"] = self.lightrag.working_dir
            
            base_stats.update(lightrag_stats)
            return base_stats
            
        except Exception as e:
            return {
                "backend_type": self.backend_type.value,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }