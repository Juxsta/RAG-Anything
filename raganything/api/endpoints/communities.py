"""
Community management endpoints for RAG-Anything API.
"""

import time
import uuid
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks

from ..models import (
    CommunityInfo, CommunityBuildRequest, ProcessingResult,
    PaginatedCommunitiesResponse, ErrorResponse
)
from ..dependencies import get_rag_service, get_current_user

router = APIRouter(prefix="/communities", tags=["communities"])


@router.get("/", response_model=PaginatedCommunitiesResponse)
async def get_communities(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    group_ids: Optional[List[str]] = Query(None),
    rag_service=Depends(get_rag_service),
    current_user=Depends(get_current_user)
):
    """Get paginated list of communities."""
    try:
        communities = await rag_service.get_communities(
            limit=limit,
            offset=offset,
            group_ids=group_ids
        )
        
        community_items = [CommunityInfo(**community) for community in communities]
        
        return PaginatedCommunitiesResponse(
            items=community_items,
            limit=limit,
            offset=offset,
            has_more=len(communities) == limit
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                message=f"Failed to retrieve communities: {str(e)}",
                error_type=type(e).__name__,
                request_id=str(uuid.uuid4())
            ).model_dump()
        )


@router.post("/build", response_model=ProcessingResult)
async def build_communities(
    request: CommunityBuildRequest,
    background_tasks: BackgroundTasks,
    rag_service=Depends(get_rag_service),
    current_user=Depends(get_current_user)
):
    """Build or rebuild communities in the knowledge graph."""
    try:
        start_time = time.time()
        
        # Start community building (can be done in background for large graphs)
        result = await rag_service.build_communities(
            group_ids=request.group_ids,
            force_rebuild=request.force_rebuild
        )
        
        processing_time = time.time() - start_time
        
        return ProcessingResult(
            success=result['success'],
            message=f"Community building completed. Created {result.get('communities_created', 0)} communities.",
            processing_id=str(uuid.uuid4()),
            inserted_entities=result.get('communities_created', 0),
            inserted_relationships=result.get('community_edges_created', 0),
            episodes_processed=0,
            processing_time=processing_time,
            metadata=result
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                message=f"Community building failed: {str(e)}",
                error_type=type(e).__name__,
                request_id=str(uuid.uuid4())
            ).model_dump()
        )