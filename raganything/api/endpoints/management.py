"""
System management endpoints for RAG-Anything API.
"""

import uuid
from typing import List

from fastapi import APIRouter, HTTPException, Depends

from ..models import (
    BackendSwitchRequest, BackendStatus, MigrationRequest, 
    MigrationStatus, ErrorResponse
)
from ..dependencies import get_rag_service, get_admin_user

router = APIRouter(prefix="/manage", tags=["management"])


@router.get("/backend-status", response_model=BackendStatus)
async def get_backend_status(
    rag_service=Depends(get_rag_service),
    current_user=Depends(get_admin_user)
):
    """Get status of all available backends."""
    try:
        status = await rag_service.get_backend_status()
        
        return BackendStatus(
            active_backend=status['active_backend'],
            available_backends=status['available_backends'],
            backend_health=status['backend_health'],
            fallback_enabled=status.get('fallback_enabled', False),
            last_switch=status.get('last_switch')
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                message=f"Failed to get backend status: {str(e)}",
                error_type=type(e).__name__,
                request_id=str(uuid.uuid4())
            ).model_dump()
        )


@router.post("/switch-backend")
async def switch_backend(
    request: BackendSwitchRequest,
    rag_service=Depends(get_rag_service),
    current_user=Depends(get_admin_user)
):
    """Switch to a different backend."""
    try:
        result = await rag_service.switch_backend(
            target_backend=request.target_backend,
            preserve_data=request.preserve_data,
            force_switch=request.force_switch
        )
        
        return {
            'success': result['success'],
            'message': result['message'],
            'previous_backend': result.get('previous_backend'),
            'current_backend': result.get('current_backend'),
            'switch_time': result.get('switch_time')
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                message=f"Backend switch failed: {str(e)}",
                error_type=type(e).__name__,
                request_id=str(uuid.uuid4())
            ).model_dump()
        )