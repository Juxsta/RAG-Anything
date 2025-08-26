"""
Entity and relationship management endpoints for RAG-Anything API.
"""

import uuid
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Depends, Query

from ..models import (
    EntityInfo, RelationshipInfo, PaginatedEntitiesResponse, 
    PaginatedRelationshipsResponse, PaginationRequest,
    EntityFiltersRequest, RelationshipFiltersRequest, ErrorResponse
)
from ..dependencies import get_rag_service, get_current_user

router = APIRouter(prefix="/entities", tags=["entities"])


@router.get("/", response_model=PaginatedEntitiesResponse)
async def get_entities(
    limit: int = Query(20, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    group_ids: Optional[List[str]] = Query(None),
    rag_service=Depends(get_rag_service),
    current_user=Depends(get_current_user)
):
    """Get paginated list of entities from the knowledge graph."""
    try:
        filters = {'group_ids': group_ids} if group_ids else None
        
        entities = await rag_service.get_entities(
            limit=limit,
            offset=offset,
            filters=filters
        )
        
        # Convert to EntityInfo objects
        entity_items = [EntityInfo(**entity) for entity in entities]
        
        return PaginatedEntitiesResponse(
            items=entity_items,
            limit=limit,
            offset=offset,
            has_more=len(entities) == limit
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                message=f"Failed to retrieve entities: {str(e)}",
                error_type=type(e).__name__,
                request_id=str(uuid.uuid4())
            ).model_dump()
        )


@router.get("/relationships", response_model=PaginatedRelationshipsResponse)
async def get_relationships(
    limit: int = Query(20, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    group_ids: Optional[List[str]] = Query(None),
    rag_service=Depends(get_rag_service),
    current_user=Depends(get_current_user)
):
    """Get paginated list of relationships from the knowledge graph."""
    try:
        filters = {'group_ids': group_ids} if group_ids else None
        
        relationships = await rag_service.get_relationships(
            limit=limit,
            offset=offset,
            filters=filters
        )
        
        # Convert to RelationshipInfo objects
        relationship_items = [RelationshipInfo(**rel) for rel in relationships]
        
        return PaginatedRelationshipsResponse(
            items=relationship_items,
            limit=limit,
            offset=offset,
            has_more=len(relationships) == limit
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                message=f"Failed to retrieve relationships: {str(e)}",
                error_type=type(e).__name__,
                request_id=str(uuid.uuid4())
            ).model_dump()
        )


@router.get("/{entity_uuid}", response_model=EntityInfo)
async def get_entity_details(
    entity_uuid: str,
    rag_service=Depends(get_rag_service),
    current_user=Depends(get_current_user)
):
    """Get detailed information about a specific entity."""
    try:
        entity = await rag_service.get_entity_by_uuid(entity_uuid)
        
        if not entity:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(
                    message=f"Entity {entity_uuid} not found",
                    error_type="EntityNotFound",
                    request_id=str(uuid.uuid4())
                ).model_dump()
            )
        
        return EntityInfo(**entity)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                message=f"Failed to get entity details: {str(e)}",
                error_type=type(e).__name__,
                request_id=str(uuid.uuid4())
            ).model_dump()
        )