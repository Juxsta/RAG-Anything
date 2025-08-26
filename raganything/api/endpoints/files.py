"""
File upload and processing endpoints for RAG-Anything API.
"""

import time
import uuid
from typing import List

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form

from ..models import (
    FileProcessingRequest, FileProcessingResult, ProcessingResult,
    ContentType, ErrorResponse
)
from ..dependencies import get_rag_service, get_current_user

router = APIRouter(prefix="/files", tags=["files"])


@router.post("/upload", response_model=FileProcessingResult)
async def upload_and_process_file(
    file: UploadFile = File(...),
    group_id: str = Form(None),
    parser_preference: str = Form("auto"),
    rag_service=Depends(get_rag_service),
    current_user=Depends(get_current_user)
):
    """Upload and process a single file."""
    try:
        start_time = time.time()
        
        # Read file content
        file_content = await file.read()
        file_size = len(file_content)
        
        # Process file using RAG service
        processing_result = await rag_service.process_file(
            filename=file.filename,
            content=file_content,
            content_type=file.content_type,
            group_id=group_id,
            parser_preference=parser_preference,
            metadata={'uploaded_by': current_user.get('user_id') if current_user else 'anonymous'}
        )
        
        parsing_time = time.time() - start_time
        
        return FileProcessingResult(
            filename=file.filename,
            file_size=file_size,
            content_type=file.content_type,
            processing_result=ProcessingResult(
                success=processing_result.success,
                message=processing_result.message,
                processing_id=str(uuid.uuid4()),
                inserted_entities=processing_result.inserted_entities,
                inserted_relationships=processing_result.inserted_relationships,
                episodes_processed=processing_result.metadata.get('episodes_processed', 0),
                processing_time=processing_result.processing_time,
                metadata=processing_result.metadata
            ),
            extracted_content_types=[ContentType.MIXED],  # Would be determined by parser
            parsing_method=parser_preference,
            parsing_time=parsing_time
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                message=f"File processing failed: {str(e)}",
                error_type=type(e).__name__,
                details={'filename': file.filename},
                request_id=str(uuid.uuid4())
            ).model_dump()
        )


@router.post("/upload-batch", response_model=List[FileProcessingResult])
async def upload_and_process_files(
    files: List[UploadFile] = File(...),
    group_id: str = Form(None),
    parser_preference: str = Form("auto"),
    rag_service=Depends(get_rag_service),
    current_user=Depends(get_current_user)
):
    """Upload and process multiple files."""
    try:
        results = []
        
        for file in files:
            try:
                start_time = time.time()
                
                file_content = await file.read()
                file_size = len(file_content)
                
                processing_result = await rag_service.process_file(
                    filename=file.filename,
                    content=file_content,
                    content_type=file.content_type,
                    group_id=group_id,
                    parser_preference=parser_preference,
                    metadata={'uploaded_by': current_user.get('user_id') if current_user else 'anonymous'}
                )
                
                parsing_time = time.time() - start_time
                
                results.append(FileProcessingResult(
                    filename=file.filename,
                    file_size=file_size,
                    content_type=file.content_type,
                    processing_result=ProcessingResult(
                        success=processing_result.success,
                        message=processing_result.message,
                        processing_id=str(uuid.uuid4()),
                        inserted_entities=processing_result.inserted_entities,
                        inserted_relationships=processing_result.inserted_relationships,
                        episodes_processed=processing_result.metadata.get('episodes_processed', 0),
                        processing_time=processing_result.processing_time,
                        metadata=processing_result.metadata
                    ),
                    extracted_content_types=[ContentType.MIXED],
                    parsing_method=parser_preference,
                    parsing_time=parsing_time
                ))
                
            except Exception as e:
                results.append(FileProcessingResult(
                    filename=file.filename,
                    file_size=0,
                    content_type=file.content_type or "unknown",
                    processing_result=ProcessingResult(
                        success=False,
                        message=f"File processing failed: {str(e)}",
                        processing_id=str(uuid.uuid4()),
                        processing_time=0.0,
                        metadata={'error': str(e)}
                    ),
                    extracted_content_types=[],
                    parsing_method=parser_preference,
                    parsing_time=0.0
                ))
        
        return results
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                message=f"Batch file processing failed: {str(e)}",
                error_type=type(e).__name__,
                request_id=str(uuid.uuid4())
            ).model_dump()
        )