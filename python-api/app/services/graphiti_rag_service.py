"""
High-level service for GraphitiRAGAnything operations.

This service provides a clean, business-logic layer on top of the GraphitiIntegrator,
handling complex workflows, data validation, and coordination between different
components of the system.
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from app.config import get_settings
from app.models.common import OperationResult
from app.models.documents import DocumentProcessingResult, BatchProcessingResult
from app.models.queries import QueryRequest, QueryResponse
from app.services.file_service import FileService
from app.services.document_service import DocumentService
from app.integration.graphiti_integrator import GraphitiIntegrator, GraphitiIntegrationConfig

logger = logging.getLogger(__name__)


class GraphitiRAGService:
    """
    High-level service for GraphitiRAGAnything operations.
    
    This service provides business logic coordination for:
    - Document processing workflows
    - Query orchestration
    - Knowledge graph management
    - Multimodal content handling
    - Community and entity operations
    """
    
    def __init__(self):
        """Initialize the GraphitiRAG service"""
        self.settings = get_settings()
        self.file_service = FileService()
        self.document_service = DocumentService()
        self.integrator: Optional[GraphitiIntegrator] = None
        self._initialized = False
    
    async def initialize(
        self,
        graphiti_config: Optional[Dict[str, Any]] = None,
        llm_model_func: Optional[callable] = None,
        embedding_func: Optional[callable] = None,
        vision_model_func: Optional[callable] = None
    ) -> OperationResult:
        """
        Initialize the GraphitiRAG service.
        
        Args:
            graphiti_config: Graphiti-specific configuration
            llm_model_func: LLM model function
            embedding_func: Embedding function
            vision_model_func: Vision model function
            
        Returns:
            OperationResult indicating initialization success
        """
        try:
            logger.info("Initializing GraphitiRAG service")
            
            # Create integrator
            self.integrator = GraphitiIntegrator()
            
            # Initialize with configuration
            result = await self.integrator.initialize(
                config=graphiti_config,
                llm_model_func=llm_model_func,
                embedding_func=embedding_func,
                vision_model_func=vision_model_func
            )
            
            if result.success:
                self._initialized = True
                logger.info("GraphitiRAG service initialized successfully")
            else:
                logger.error(f"Failed to initialize GraphitiRAG service: {result.message}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error during GraphitiRAG service initialization: {e}")
            return OperationResult(
                success=False,
                message=f"Service initialization failed: {str(e)}",
                data={"error": str(e)}
            )
    
    async def process_document_file(
        self,
        file: UploadFile,
        metadata: Optional[Dict[str, Any]] = None,
        group_id: Optional[str] = None,
        enable_multimodal: bool = True
    ) -> DocumentProcessingResult:
        """
        Process a document file with comprehensive workflow.
        
        Args:
            file: Uploaded file to process
            metadata: Additional metadata
            group_id: Specific group ID for organization
            enable_multimodal: Enable multimodal processing
            
        Returns:
            DocumentProcessingResult with detailed processing information
        """
        if not self._initialized:
            raise HTTPException(status_code=500, detail="Service not initialized")
        
        start_time = datetime.now()
        
        try:
            logger.info(f"Processing document file: {file.filename}")
            
            # Validate file
            validation_result = await self.file_service.validate_file(file)
            if not validation_result.success:
                raise HTTPException(status_code=400, detail=validation_result.message)
            
            # Prepare processing metadata
            processing_metadata = {
                "group_id": group_id or "default",
                "enable_multimodal": enable_multimodal,
                "processing_strategy": "graphiti_episodic",
                "uploaded_by": metadata.get("user_id") if metadata else "system",
                "processing_timestamp": start_time.isoformat(),
                **(metadata or {})
            }
            
            # Process with integrator
            result = await self.integrator.process_file(file, processing_metadata)
            
            # Calculate total processing time
            end_time = datetime.now()
            result.processing_time = (end_time - start_time).total_seconds()
            
            # Log processing completion
            logger.info(
                f"Document processing completed: {file.filename} - "
                f"Success: {result.success}, Entities: {result.entities_created}, "
                f"Relationships: {result.relationships_created}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing document file {file.filename}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Document processing failed: {str(e)}"
            )
    
    async def process_text_content(
        self,
        text: str,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        group_id: Optional[str] = None
    ) -> OperationResult:
        """
        Process raw text content.
        
        Args:
            text: Text content to process
            title: Optional title for the content
            metadata: Additional metadata
            group_id: Specific group ID
            
        Returns:
            OperationResult with processing details
        """
        if not self._initialized:
            raise HTTPException(status_code=500, detail="Service not initialized")
        
        try:
            logger.info(f"Processing text content: {title or 'Untitled'}")
            
            # Prepare metadata
            processing_metadata = {
                "title": title or f"Text Content {datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "group_id": group_id or "default",
                "content_type": "text",
                "processed_at": datetime.now().isoformat(),
                **(metadata or {})
            }
            
            # Process with integrator
            result = await self.integrator.process_text(text, processing_metadata)
            
            logger.info(f"Text processing completed: {result.success}")
            return result
            
        except Exception as e:
            logger.error(f"Error processing text content: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Text processing failed: {str(e)}"
            )
    
    async def batch_process_documents(
        self,
        files: List[UploadFile],
        metadata: Optional[Dict[str, Any]] = None,
        group_id: Optional[str] = None,
        max_concurrent: int = 3
    ) -> BatchProcessingResult:
        """
        Process multiple documents concurrently.
        
        Args:
            files: List of files to process
            metadata: Shared metadata
            group_id: Group ID for all documents
            max_concurrent: Maximum concurrent processing
            
        Returns:
            BatchProcessingResult with comprehensive results
        """
        if not self._initialized:
            raise HTTPException(status_code=500, detail="Service not initialized")
        
        start_time = datetime.now()
        logger.info(f"Starting batch processing of {len(files)} documents")
        
        # Prepare batch metadata
        batch_metadata = {
            "batch_id": str(uuid4()),
            "total_files": len(files),
            "started_at": start_time.isoformat(),
            **(metadata or {})
        }
        
        # Process files with concurrency control
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_single_file(file: UploadFile, index: int) -> Tuple[int, DocumentProcessingResult]:
            async with semaphore:
                try:
                    file_metadata = {**batch_metadata, "batch_index": index}
                    result = await self.process_document_file(
                        file, file_metadata, group_id
                    )
                    return index, result
                except Exception as e:
                    logger.error(f"Error processing file {file.filename} in batch: {e}")
                    return index, DocumentProcessingResult(
                        success=False,
                        message=f"Processing failed: {str(e)}",
                        filename=file.filename,
                        processing_time=0.0,
                        entities_created=0,
                        relationships_created=0,
                        metadata={"error": str(e)}
                    )
        
        # Execute batch processing
        tasks = [process_single_file(file, i) for i, file in enumerate(files)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Compile batch results
        successful_results = []
        failed_results = []
        total_entities = 0
        total_relationships = 0
        
        for result in results:
            if isinstance(result, Exception):
                failed_results.append({
                    "error": str(result),
                    "filename": "unknown",
                    "index": -1
                })
                continue
            
            index, doc_result = result
            if doc_result.success:
                successful_results.append(doc_result)
                total_entities += doc_result.entities_created
                total_relationships += doc_result.relationships_created
            else:
                failed_results.append({
                    "filename": doc_result.filename,
                    "error": doc_result.message,
                    "index": index
                })
        
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()
        
        batch_result = BatchProcessingResult(
            success=len(successful_results) > 0,
            message=f"Processed {len(successful_results)}/{len(files)} documents successfully",
            total_files=len(files),
            successful_files=len(successful_results),
            failed_files=len(failed_results),
            total_processing_time=total_time,
            total_entities_created=total_entities,
            total_relationships_created=total_relationships,
            results=successful_results,
            errors=failed_results,
            metadata=batch_metadata
        )
        
        logger.info(
            f"Batch processing completed: {len(successful_results)}/{len(files)} successful, "
            f"Total time: {total_time:.2f}s"
        )
        
        return batch_result
    
    async def execute_query(
        self,
        query_request: QueryRequest,
        group_id: Optional[str] = None
    ) -> QueryResponse:
        """
        Execute a comprehensive query with enhanced processing.
        
        Args:
            query_request: Query parameters
            group_id: Specific group to query
            
        Returns:
            QueryResponse with results and metadata
        """
        if not self._initialized:
            raise HTTPException(status_code=500, detail="Service not initialized")
        
        start_time = datetime.now()
        
        try:
            logger.info(f"Executing query: {query_request.query[:100]}...")
            
            # Add group filtering if specified
            if group_id:
                query_request.metadata = query_request.metadata or {}
                query_request.metadata["group_id"] = group_id
            
            # Execute query through integrator
            response = await self.integrator.query(query_request)
            
            # Calculate processing time
            end_time = datetime.now()
            response.processing_time = (end_time - start_time).total_seconds()
            
            # Enhance response metadata
            response.metadata = response.metadata or {}
            response.metadata.update({
                "service_processing_time": response.processing_time,
                "query_timestamp": start_time.isoformat(),
                "response_timestamp": end_time.isoformat(),
                "group_filter": group_id
            })
            
            logger.info(f"Query executed successfully in {response.processing_time:.2f}s")
            return response
            
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Query execution failed: {str(e)}"
            )
    
    async def get_knowledge_graph_stats(
        self,
        group_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get comprehensive knowledge graph statistics"""
        if not self._initialized:
            raise HTTPException(status_code=500, detail="Service not initialized")
        
        try:
            # Get base stats from integrator
            stats = await self.integrator.get_stats()
            
            # Add service-level enhancements
            service_stats = {
                "service_info": {
                    "service_name": "GraphitiRAG Service",
                    "version": "1.0.0",
                    "initialized": self._initialized,
                    "timestamp": datetime.now().isoformat()
                },
                "query_group": group_id,
                **stats
            }
            
            return service_stats
            
        except Exception as e:
            logger.error(f"Error getting knowledge graph stats: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get stats: {str(e)}"
            )
    
    async def get_entities(
        self,
        limit: int = 100,
        offset: int = 0,
        group_id: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Retrieve entities with service-level enhancements"""
        if not self._initialized:
            raise HTTPException(status_code=500, detail="Service not initialized")
        
        try:
            # Prepare filters
            enhanced_filters = filters or {}
            if group_id:
                enhanced_filters["group_id"] = group_id
            
            # Get entities from integrator
            result = await self.integrator.get_entities(
                limit=limit,
                offset=offset,
                filters=enhanced_filters
            )
            
            # Add service metadata
            result["service_metadata"] = {
                "queried_at": datetime.now().isoformat(),
                "group_filter": group_id,
                "service": "GraphitiRAG"
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error retrieving entities: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve entities: {str(e)}"
            )
    
    async def get_relationships(
        self,
        limit: int = 100,
        offset: int = 0,
        group_id: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Retrieve relationships with service-level enhancements"""
        if not self._initialized:
            raise HTTPException(status_code=500, detail="Service not initialized")
        
        try:
            # Prepare filters
            enhanced_filters = filters or {}
            if group_id:
                enhanced_filters["group_id"] = group_id
            
            # Get relationships from integrator
            result = await self.integrator.get_relationships(
                limit=limit,
                offset=offset,
                filters=enhanced_filters
            )
            
            # Add service metadata
            result["service_metadata"] = {
                "queried_at": datetime.now().isoformat(),
                "group_filter": group_id,
                "service": "GraphitiRAG"
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error retrieving relationships: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve relationships: {str(e)}"
            )
    
    async def manage_backend(
        self,
        action: str,
        **kwargs
    ) -> OperationResult:
        """
        Manage backend operations (switch, restart, etc.)
        
        Args:
            action: Action to perform ('switch', 'restart', 'status')
            **kwargs: Action-specific parameters
            
        Returns:
            OperationResult with action results
        """
        if not self._initialized:
            raise HTTPException(status_code=500, detail="Service not initialized")
        
        try:
            if action == "switch":
                backend_type = kwargs.get("backend_type")
                if not backend_type:
                    raise ValueError("backend_type required for switch action")
                
                result = await self.integrator.switch_backend(backend_type)
                return result
            
            elif action == "status":
                stats = await self.integrator.get_stats()
                return OperationResult(
                    success=True,
                    message="Backend status retrieved",
                    data=stats
                )
            
            elif action == "restart":
                # Restart the integrator
                await self.integrator.finalize()
                init_result = await self.integrator.initialize()
                return init_result
            
            else:
                return OperationResult(
                    success=False,
                    message=f"Unknown action: {action}",
                    data={"available_actions": ["switch", "status", "restart"]}
                )
                
        except Exception as e:
            logger.error(f"Error managing backend: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Backend management failed: {str(e)}"
            )
    
    async def finalize(self) -> None:
        """Clean up service resources"""
        try:
            if self.integrator:
                await self.integrator.finalize()
            
            self._initialized = False
            logger.info("GraphitiRAG service finalized")
            
        except Exception as e:
            logger.error(f"Error during service finalization: {e}")
            # Don't raise during cleanup