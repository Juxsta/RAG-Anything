"""
Document processing endpoints for RAG-Anything API.

Handles text processing, batch operations, and multimodal content ingestion.
"""

import time
import uuid
from typing import Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse

from ..models import (
    TextProcessingRequest, ProcessingResult, BatchProcessingRequest,
    BatchProcessingStatus, ProcessingStatus, ErrorResponse
)
from ..dependencies import get_rag_service, get_current_user

router = APIRouter(prefix="/process", tags=["processing"])


@router.post("/text", response_model=ProcessingResult)
async def process_text(
    request: TextProcessingRequest,
    rag_service=Depends(get_rag_service),
    current_user=Depends(get_current_user)
) -> ProcessingResult:
    """
    Process plain text content and add it to the knowledge graph.
    
    This endpoint accepts text content and processes it through the RAG system,
    extracting entities, relationships, and creating episodes in the graph database.
    """
    try:
        start_time = time.time()
        
        # Prepare metadata
        metadata = {
            **request.metadata,
            'title': request.title,
            'source': request.source,
            'group_id': request.group_id,
            'processed_by': current_user.get('user_id', 'unknown') if current_user else 'anonymous',
            'processing_timestamp': datetime.now().isoformat()
        }
        
        # Process the text
        result = await rag_service.insert_text(
            text=request.text,
            metadata=metadata
        )
        
        processing_time = time.time() - start_time
        
        return ProcessingResult(
            success=result.success,
            message=result.message,
            processing_id=str(uuid.uuid4()),
            inserted_entities=result.inserted_entities,
            inserted_relationships=result.inserted_relationships,
            episodes_processed=1,
            processing_time=processing_time,
            metadata=result.metadata
        )
        
    except Exception as e:
        processing_time = time.time() - start_time
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                message=f"Text processing failed: {str(e)}",
                error_type=type(e).__name__,
                details={'processing_time': processing_time},
                request_id=str(uuid.uuid4())
            ).model_dump()
        )


@router.post("/multimodal", response_model=ProcessingResult)
async def process_multimodal_content(
    content: Dict[str, Any],
    metadata: Dict[str, Any] = {},
    rag_service=Depends(get_rag_service),
    current_user=Depends(get_current_user)
) -> ProcessingResult:
    """
    Process multimodal content including text, images, tables, and equations.
    
    This endpoint handles complex multimodal content and converts it into
    structured episodes for the knowledge graph.
    """
    try:
        start_time = time.time()
        
        # Enhance metadata
        enhanced_metadata = {
            **metadata,
            'processed_by': current_user.get('user_id', 'unknown') if current_user else 'anonymous',
            'processing_timestamp': datetime.now().isoformat(),
            'content_types': list(content.keys()) if isinstance(content, dict) else ['unknown']
        }
        
        # Process multimodal content
        result = await rag_service.insert_multimodal_content(
            content=content,
            metadata=enhanced_metadata
        )
        
        processing_time = time.time() - start_time
        
        return ProcessingResult(
            success=result.success,
            message=result.message,
            processing_id=str(uuid.uuid4()),
            inserted_entities=result.inserted_entities,
            inserted_relationships=result.inserted_relationships,
            episodes_processed=result.metadata.get('episodes_processed', 1),
            processing_time=processing_time,
            metadata=result.metadata
        )
        
    except Exception as e:
        processing_time = time.time() - start_time
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                message=f"Multimodal content processing failed: {str(e)}",
                error_type=type(e).__name__,
                details={'processing_time': processing_time},
                request_id=str(uuid.uuid4())
            ).model_dump()
        )


@router.post("/batch", response_model=BatchProcessingStatus)
async def start_batch_processing(
    request: BatchProcessingRequest,
    background_tasks: BackgroundTasks,
    rag_service=Depends(get_rag_service),
    current_user=Depends(get_current_user)
) -> BatchProcessingStatus:
    """
    Start batch processing of multiple documents.
    
    This endpoint initiates background processing of multiple documents
    and returns a batch ID for tracking progress.
    """
    try:
        batch_id = str(uuid.uuid4())
        start_time = datetime.now()
        
        # Create initial batch status
        batch_status = BatchProcessingStatus(
            batch_id=batch_id,
            status=ProcessingStatus.IN_PROGRESS,
            total_documents=len(request.documents),
            processed_documents=0,
            failed_documents=0,
            start_time=start_time,
            estimated_completion=None,
            results=[]
        )
        
        # Store batch status for tracking
        await rag_service.store_batch_status(batch_id, batch_status)
        
        # Start background processing
        background_tasks.add_task(
            _process_batch_background,
            batch_id,
            request,
            rag_service,
            current_user
        )
        
        return batch_status
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                message=f"Failed to start batch processing: {str(e)}",
                error_type=type(e).__name__,
                request_id=str(uuid.uuid4())
            ).model_dump()
        )


@router.get("/batch/{batch_id}", response_model=BatchProcessingStatus)
async def get_batch_status(
    batch_id: str,
    rag_service=Depends(get_rag_service),
    current_user=Depends(get_current_user)
) -> BatchProcessingStatus:
    """
    Get the status of a batch processing operation.
    
    Returns current progress, completion status, and results for individual documents.
    """
    try:
        batch_status = await rag_service.get_batch_status(batch_id)
        
        if not batch_status:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(
                    message=f"Batch {batch_id} not found",
                    error_type="BatchNotFound",
                    request_id=str(uuid.uuid4())
                ).model_dump()
            )
        
        return batch_status
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                message=f"Failed to get batch status: {str(e)}",
                error_type=type(e).__name__,
                request_id=str(uuid.uuid4())
            ).model_dump()
        )


async def _process_batch_background(
    batch_id: str,
    request: BatchProcessingRequest,
    rag_service,
    current_user: Dict[str, Any] = None
):
    """Background task for processing batch documents"""
    try:
        processed_count = 0
        failed_count = 0
        results = []
        
        # Enhanced batch metadata
        batch_metadata = {
            **request.batch_metadata,
            'batch_id': batch_id,
            'group_id': request.group_id,
            'processed_by': current_user.get('user_id', 'unknown') if current_user else 'anonymous',
            'batch_start_time': datetime.now().isoformat()
        }
        
        for i, document in enumerate(request.documents):
            try:
                doc_start_time = time.time()
                
                # Prepare document metadata
                doc_metadata = {
                    **batch_metadata,
                    'batch_document_index': i,
                    'document_id': document.get('id', f'doc_{i}')
                }
                
                # Determine if this is text or multimodal content
                if isinstance(document, dict) and 'text' in document and len(document) == 1:
                    # Plain text document
                    result = await rag_service.insert_text(
                        text=document['text'],
                        metadata=doc_metadata
                    )
                else:
                    # Multimodal or complex document
                    result = await rag_service.insert_multimodal_content(
                        content=document,
                        metadata=doc_metadata
                    )
                
                doc_processing_time = time.time() - doc_start_time
                
                if result.success:
                    processed_count += 1
                else:
                    failed_count += 1
                
                # Create processing result for this document
                doc_result = ProcessingResult(
                    success=result.success,
                    message=result.message,
                    processing_id=f"{batch_id}_doc_{i}",
                    inserted_entities=result.inserted_entities,
                    inserted_relationships=result.inserted_relationships,
                    episodes_processed=result.metadata.get('episodes_processed', 1),
                    processing_time=doc_processing_time,
                    metadata={
                        **result.metadata,
                        'document_index': i
                    }
                )
                
                results.append(doc_result)
                
                # Update batch status periodically
                if (i + 1) % 10 == 0 or (i + 1) == len(request.documents):
                    await _update_batch_status(
                        rag_service,
                        batch_id,
                        processed_count + failed_count,
                        failed_count,
                        results
                    )
                
            except Exception as e:
                failed_count += 1
                error_result = ProcessingResult(
                    success=False,
                    message=f"Document processing failed: {str(e)}",
                    processing_id=f"{batch_id}_doc_{i}",
                    processing_time=0.0,
                    metadata={'document_index': i, 'error': str(e)}
                )
                results.append(error_result)
        
        # Final status update
        await _update_batch_status(
            rag_service,
            batch_id,
            processed_count + failed_count,
            failed_count,
            results,
            final=True
        )
        
    except Exception as e:
        # Update batch status with error
        await _update_batch_status(
            rag_service,
            batch_id,
            0,
            len(request.documents),
            [],
            error=str(e)
        )


async def _update_batch_status(
    rag_service,
    batch_id: str,
    processed: int,
    failed: int,
    results: list,
    final: bool = False,
    error: str = None
):
    """Update batch processing status"""
    try:
        current_status = await rag_service.get_batch_status(batch_id)
        if not current_status:
            return
        
        # Update status
        if error:
            current_status.status = ProcessingStatus.FAILED
        elif final:
            current_status.status = ProcessingStatus.COMPLETED
        else:
            current_status.status = ProcessingStatus.IN_PROGRESS
        
        current_status.processed_documents = processed
        current_status.failed_documents = failed
        current_status.results = results
        
        if final:
            current_status.estimated_completion = datetime.now()
        
        await rag_service.store_batch_status(batch_id, current_status)
        
    except Exception as e:
        # Log error but don't fail the batch processing
        print(f"Failed to update batch status for {batch_id}: {e}")