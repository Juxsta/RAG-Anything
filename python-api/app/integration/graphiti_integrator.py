"""
Graphiti Integrator for FastAPI Backend.

This module provides the REST API integration layer for GraphitiRAGAnything,
handling API requests and coordinating with the backend services.
"""

import asyncio
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from pydantic import BaseModel

from app.config import get_settings
from app.models.common import OperationResult
from app.models.documents import DocumentProcessingResult
from app.models.queries import QueryRequest, QueryResponse
from .exceptions import RAGIntegrationError

# Import GraphitiRAGAnything (with fallback handling)
try:
    from raganything.graphiti_integration import GraphitiRAGAnything, GraphitiRAGAnythingConfig
    from raganything.backends.base import BackendType, QueryResult, InsertResult
    GRAPHITI_INTEGRATION_AVAILABLE = True
except ImportError as e:
    GRAPHITI_INTEGRATION_AVAILABLE = False
    GraphitiRAGAnything = None
    GraphitiRAGAnythingConfig = None
    BackendType = None
    QueryResult = None
    InsertResult = None


class GraphitiIntegrationConfig(BaseModel):
    """Configuration for Graphiti integration"""
    backend_type: str = "graphiti"
    enable_fallback: bool = True
    default_group_id: str = "default"
    preserve_document_structure: bool = True
    
    # Graphiti-specific settings
    graph_provider: str = "falkordb"
    graph_host: str = "localhost"
    graph_port: int = 6379
    graph_database: str = "rag_graph" 
    graph_password: Optional[str] = None
    
    # LLM settings
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None


class GraphitiIntegrator:
    """
    Integration layer for GraphitiRAGAnything with FastAPI.
    
    This class provides a REST API-friendly interface to the GraphitiRAGAnything
    system, handling document processing, querying, and backend management.
    """
    
    def __init__(self):
        """Initialize the Graphiti integrator"""
        if not GRAPHITI_INTEGRATION_AVAILABLE:
            raise ImportError(
                "GraphitiRAGAnything is not available. "
                "Please ensure the integration modules are properly installed."
            )
        
        self.settings = get_settings()
        self.rag_instance: Optional[GraphitiRAGAnything] = None
        self.config: Optional[GraphitiIntegrationConfig] = None
        self._initialized = False
    
    async def initialize(
        self,
        config: Optional[Dict[str, Any]] = None,
        llm_model_func: Optional[callable] = None,
        embedding_func: Optional[callable] = None,
        vision_model_func: Optional[callable] = None
    ) -> OperationResult:
        """
        Initialize the GraphitiRAGAnything integration.
        
        Args:
            config: Configuration dictionary
            llm_model_func: LLM model function
            embedding_func: Embedding model function  
            vision_model_func: Vision model function
            
        Returns:
            OperationResult indicating success/failure
        """
        try:
            # Create integration config
            self.config = GraphitiIntegrationConfig(**(config or {}))
            
            # Create RAG-Anything config
            rag_config = GraphitiRAGAnythingConfig(
                working_dir=str(Path(self.settings.storage_path) / "graphiti_rag"),
                backend_type=BackendType.GRAPHITI if self.config.backend_type == "graphiti" else BackendType.LIGHTRAG,
                enable_backend_fallback=self.config.enable_fallback,
                default_group_id=self.config.default_group_id,
                preserve_document_structure=self.config.preserve_document_structure,
                
                # Parser settings from existing config
                parser=self.settings.parser_type,
                parse_method=self.settings.parse_method,
                
                # Graphiti-specific configuration
                graphiti_config={
                    "graph_config": {
                        "provider": self.config.graph_provider,
                        "host": self.config.graph_host,
                        "port": self.config.graph_port,
                        "database": self.config.graph_database,
                        "password": self.config.graph_password,
                    },
                    "llm_config": {
                        "provider": self.config.llm_provider,
                        "model": self.config.llm_model,
                        "api_key": self.config.llm_api_key,
                        "base_url": self.config.llm_base_url,
                    },
                    "group_id": self.config.default_group_id,
                }
            )
            
            # Create GraphitiRAGAnything instance
            self.rag_instance = GraphitiRAGAnything(
                config=rag_config,
                llm_model_func=llm_model_func,
                embedding_func=embedding_func,
                vision_model_func=vision_model_func,
            )
            
            # Initialize the instance
            await self.rag_instance.initialize()
            
            self._initialized = True
            
            return OperationResult(
                success=True,
                message="GraphitiRAGAnything integration initialized successfully",
                data={
                    "backend_type": self.config.backend_type,
                    "working_dir": str(rag_config.working_dir),
                    "graph_provider": self.config.graph_provider,
                }
            )
            
        except Exception as e:
            error_msg = f"Failed to initialize GraphitiRAGAnything integration: {str(e)}"
            return OperationResult(
                success=False,
                message=error_msg,
                data={"error": str(e), "traceback": traceback.format_exc()}
            )
    
    async def process_file(
        self,
        file: UploadFile,
        metadata: Optional[Dict[str, Any]] = None
    ) -> DocumentProcessingResult:
        """
        Process an uploaded file using GraphitiRAGAnything.
        
        Args:
            file: Uploaded file
            metadata: Optional metadata for processing
            
        Returns:
            DocumentProcessingResult with processing details
        """
        if not self._initialized:
            raise HTTPException(
                status_code=500,
                detail="GraphitiRAGAnything integration not initialized"
            )
        
        # Save uploaded file temporarily
        temp_path = Path(self.settings.temp_path) / f"{uuid4()}_{file.filename}"
        temp_path.parent.mkdir(exist_ok=True)
        
        try:
            # Save file content
            content = await file.read()
            with open(temp_path, "wb") as f:
                f.write(content)
            
            # Process with GraphitiRAGAnything
            processing_metadata = {
                "original_filename": file.filename,
                "content_type": file.content_type,
                "file_size": len(content),
                "uploaded_at": datetime.now().isoformat(),
                **(metadata or {})
            }
            
            result = await self.rag_instance.process_document(
                str(temp_path),
                processing_metadata
            )
            
            # Convert to API response format
            return DocumentProcessingResult(
                success=result.success,
                message=result.message,
                filename=file.filename,
                processing_time=result.processing_time,
                entities_created=result.inserted_entities,
                relationships_created=result.inserted_relationships,
                metadata=result.metadata
            )
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error processing file: {str(e)}"
            )
        finally:
            # Clean up temporary file
            if temp_path.exists():
                temp_path.unlink()
    
    async def process_text(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> OperationResult:
        """
        Process raw text using GraphitiRAGAnything.
        
        Args:
            text: Text content to process
            metadata: Optional metadata
            
        Returns:
            OperationResult with processing details
        """
        if not self._initialized:
            raise HTTPException(
                status_code=500,
                detail="GraphitiRAGAnything integration not initialized"
            )
        
        try:
            # Insert text directly
            result = await self.rag_instance.backend.insert_text(text, metadata)
            
            return OperationResult(
                success=result.success,
                message=result.message,
                data={
                    "processing_time": result.processing_time,
                    "entities_created": result.inserted_entities,
                    "relationships_created": result.inserted_relationships,
                    "metadata": result.metadata
                }
            )
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error processing text: {str(e)}"
            )
    
    async def query(
        self,
        query_request: QueryRequest
    ) -> QueryResponse:
        """
        Execute a query using GraphitiRAGAnything.
        
        Args:
            query_request: Query request parameters
            
        Returns:
            QueryResponse with query results
        """
        if not self._initialized:
            raise HTTPException(
                status_code=500,
                detail="GraphitiRAGAnything integration not initialized"
            )
        
        try:
            # Execute query
            result = await self.rag_instance.query(
                query_request.query,
                mode=query_request.mode,
                top_k=query_request.top_k
            )
            
            # Convert to API response format
            return QueryResponse(
                success=True,
                query=query_request.query,
                response=result.content,
                sources=result.sources,
                entities=result.entities,
                relationships=result.relationships,
                metadata=result.metadata,
                processing_time=0.0,  # Will be set by the endpoint
                backend_type=result.backend_type.value if result.backend_type else "unknown"
            )
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error executing query: {str(e)}"
            )
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics from the integration"""
        if not self._initialized:
            raise HTTPException(
                status_code=500,
                detail="GraphitiRAGAnything integration not initialized"
            )
        
        try:
            # Get backend stats
            backend_stats = await self.rag_instance.get_backend_stats()
            
            # Get health check
            health_check = await self.rag_instance.health_check()
            
            # Get config info
            config_info = self.rag_instance.get_config_info()
            
            return {
                "stats": backend_stats,
                "health": health_check,
                "config": config_info,
                "integration_info": {
                    "backend_type": self.config.backend_type,
                    "graph_provider": self.config.graph_provider,
                    "default_group_id": self.config.default_group_id,
                    "initialized": self._initialized,
                    "timestamp": datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error getting stats: {str(e)}"
            )
    
    async def get_entities(
        self,
        limit: int = 100,
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Retrieve entities from the knowledge graph"""
        if not self._initialized:
            raise HTTPException(
                status_code=500,
                detail="GraphitiRAGAnything integration not initialized"
            )
        
        try:
            entities = await self.rag_instance.backend.get_entities(
                limit=limit,
                offset=offset,
                filters=filters
            )
            
            return {
                "entities": entities,
                "total": len(entities),
                "limit": limit,
                "offset": offset,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error retrieving entities: {str(e)}"
            )
    
    async def get_relationships(
        self,
        limit: int = 100,
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Retrieve relationships from the knowledge graph"""
        if not self._initialized:
            raise HTTPException(
                status_code=500,
                detail="GraphitiRAGAnything integration not initialized"
            )
        
        try:
            relationships = await self.rag_instance.backend.get_relationships(
                limit=limit,
                offset=offset,
                filters=filters
            )
            
            return {
                "relationships": relationships,
                "total": len(relationships),
                "limit": limit,
                "offset": offset,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error retrieving relationships: {str(e)}"
            )
    
    async def switch_backend(self, backend_type: str) -> OperationResult:
        """Switch to a different backend"""
        if not self._initialized:
            raise HTTPException(
                status_code=500,
                detail="GraphitiRAGAnything integration not initialized"
            )
        
        try:
            # Convert string to enum
            target_backend = BackendType.GRAPHITI if backend_type.lower() == "graphiti" else BackendType.LIGHTRAG
            
            # Attempt to switch
            success = await self.rag_instance.switch_backend(target_backend)
            
            if success:
                self.config.backend_type = backend_type.lower()
                return OperationResult(
                    success=True,
                    message=f"Successfully switched to {backend_type} backend",
                    data={"new_backend": backend_type}
                )
            else:
                return OperationResult(
                    success=False,
                    message=f"Failed to switch to {backend_type} backend",
                    data={"current_backend": self.config.backend_type}
                )
                
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error switching backend: {str(e)}"
            )
    
    async def finalize(self) -> None:
        """Clean up integration resources"""
        try:
            if self.rag_instance:
                await self.rag_instance.finalize()
            
            self._initialized = False
            
        except Exception as e:
            # Log error but don't raise during cleanup
            print(f"Error during GraphitiIntegrator finalization: {e}")