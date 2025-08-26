"""
Querying and search endpoints for RAG-Anything API.

Handles knowledge graph queries, semantic search, and result formatting.
"""

import time
import uuid
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import JSONResponse

from ..models import (
    QueryRequest, QueryResult, ErrorResponse, EntityInfo, 
    RelationshipInfo, EpisodeInfo
)
from ..dependencies import get_rag_service, get_current_user

router = APIRouter(prefix="/query", tags=["querying"])


@router.post("/", response_model=QueryResult)
async def execute_query(
    request: QueryRequest,
    rag_service=Depends(get_rag_service),
    current_user=Depends(get_current_user)
) -> QueryResult:
    """
    Execute a query against the knowledge graph.
    
    Supports multiple query modes including hybrid search, semantic search,
    and specialized searches for entities, episodes, and communities.
    """
    try:
        start_time = time.time()
        
        # Execute the query
        result = await rag_service.query(
            query=request.query,
            mode=request.mode.value,
            top_k=request.top_k,
            group_ids=request.group_ids,
            center_node_uuid=request.center_node_uuid
        )
        
        execution_time = time.time() - start_time
        
        # Filter sources and metadata based on request preferences
        sources = result.sources if request.include_sources else []
        query_metadata = result.metadata if request.include_metadata else {}
        
        # Add execution metadata
        query_metadata.update({
            'execution_time': execution_time,
            'user_id': current_user.get('user_id', 'anonymous') if current_user else 'anonymous',
            'query_timestamp': time.time()
        })
        
        return QueryResult(
            content=result.content,
            sources=sources,
            entities=result.entities,
            relationships=result.relationships,
            query_metadata=query_metadata,
            execution_time=execution_time
        )
        
    except Exception as e:
        execution_time = time.time() - start_time
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                message=f"Query execution failed: {str(e)}",
                error_type=type(e).__name__,
                details={
                    'query': request.query,
                    'mode': request.mode.value,
                    'execution_time': execution_time
                },
                request_id=str(uuid.uuid4())
            ).model_dump()
        )


@router.get("/similar-entities/{entity_uuid}")
async def find_similar_entities(
    entity_uuid: str,
    limit: int = Query(10, ge=1, le=100),
    threshold: float = Query(0.7, ge=0.0, le=1.0),
    rag_service=Depends(get_rag_service),
    current_user=Depends(get_current_user)
) -> List[EntityInfo]:
    """
    Find entities similar to the specified entity.
    
    Uses embedding similarity to find related entities in the knowledge graph.
    """
    try:
        # Execute similarity search using the entity as center
        result = await rag_service.query(
            query="",  # Empty query for similarity search
            mode="entities",
            top_k=limit,
            center_node_uuid=entity_uuid
        )
        
        # Convert to EntityInfo objects
        similar_entities = []
        for entity_data in result.entities:
            similar_entities.append(EntityInfo(**entity_data))
        
        return similar_entities
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                message=f"Similar entity search failed: {str(e)}",
                error_type=type(e).__name__,
                details={'entity_uuid': entity_uuid},
                request_id=str(uuid.uuid4())
            ).model_dump()
        )


@router.get("/entity-relationships/{entity_uuid}")
async def get_entity_relationships(
    entity_uuid: str,
    relationship_type: Optional[str] = Query(None),
    direction: str = Query("both", regex="^(inbound|outbound|both)$"),
    limit: int = Query(20, ge=1, le=100),
    rag_service=Depends(get_rag_service),
    current_user=Depends(get_current_user)
) -> List[RelationshipInfo]:
    """
    Get all relationships for a specific entity.
    
    Returns inbound, outbound, or both types of relationships for the entity.
    """
    try:
        # Get relationships using filters
        filters = {
            'source_entity_uuid': entity_uuid if direction in ['outbound', 'both'] else None,
            'target_entity_uuid': entity_uuid if direction in ['inbound', 'both'] else None,
            'relationship_types': [relationship_type] if relationship_type else None
        }
        
        relationships = await rag_service.get_relationships(
            limit=limit,
            filters={k: v for k, v in filters.items() if v is not None}
        )
        
        # Convert to RelationshipInfo objects
        relationship_info = []
        for rel_data in relationships:
            relationship_info.append(RelationshipInfo(**rel_data))
        
        return relationship_info
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                message=f"Entity relationship retrieval failed: {str(e)}",
                error_type=type(e).__name__,
                details={'entity_uuid': entity_uuid, 'direction': direction},
                request_id=str(uuid.uuid4())
            ).model_dump()
        )


@router.get("/path/{source_uuid}/{target_uuid}")
async def find_path_between_entities(
    source_uuid: str,
    target_uuid: str,
    max_depth: int = Query(5, ge=1, le=10),
    rag_service=Depends(get_rag_service),
    current_user=Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Find the shortest path between two entities in the knowledge graph.
    
    Returns the path as a sequence of entities and relationships.
    """
    try:
        # Use breadth-first search query mode
        result = await rag_service.query(
            query=f"path between entities",
            mode="hybrid",
            top_k=50,
            bfs_origin_node_uuids=[source_uuid],
            center_node_uuid=target_uuid
        )
        
        # Extract path information from results
        # This would need to be implemented based on Graphiti's path finding capabilities
        path_data = {
            'source_uuid': source_uuid,
            'target_uuid': target_uuid,
            'path_found': len(result.relationships) > 0,
            'path_length': len(result.relationships),
            'entities_in_path': result.entities,
            'relationships_in_path': result.relationships,
            'max_depth_searched': max_depth
        }
        
        return path_data
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                message=f"Path finding failed: {str(e)}",
                error_type=type(e).__name__,
                details={
                    'source_uuid': source_uuid, 
                    'target_uuid': target_uuid,
                    'max_depth': max_depth
                },
                request_id=str(uuid.uuid4())
            ).model_dump()
        )


@router.post("/semantic-search")
async def semantic_search(
    query: str,
    content_types: Optional[List[str]] = Query(None),
    time_range: Optional[str] = Query(None),
    group_ids: Optional[List[str]] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    rag_service=Depends(get_rag_service),
    current_user=Depends(get_current_user)
) -> QueryResult:
    """
    Perform semantic search across episodes and content.
    
    Searches through episode content using semantic similarity
    and returns matching episodes with context.
    """
    try:
        start_time = time.time()
        
        # Build search filters
        search_filters = {}
        if content_types:
            search_filters['content_types'] = content_types
        if time_range:
            search_filters['time_range'] = time_range
        
        # Execute semantic search
        result = await rag_service.query(
            query=query,
            mode="episodes",
            top_k=limit,
            group_ids=group_ids,
            search_filter=search_filters
        )
        
        execution_time = time.time() - start_time
        
        # Add search metadata
        result.metadata.update({
            'search_type': 'semantic',
            'execution_time': execution_time,
            'filters_applied': search_filters,
            'user_id': current_user.get('user_id', 'anonymous') if current_user else 'anonymous'
        })
        
        return QueryResult(
            content=result.content,
            sources=result.sources,
            entities=result.entities,
            relationships=result.relationships,
            query_metadata=result.metadata,
            execution_time=execution_time
        )
        
    except Exception as e:
        execution_time = time.time() - start_time
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                message=f"Semantic search failed: {str(e)}",
                error_type=type(e).__name__,
                details={
                    'query': query,
                    'execution_time': execution_time
                },
                request_id=str(uuid.uuid4())
            ).model_dump()
        )


@router.get("/recent-episodes")
async def get_recent_episodes(
    limit: int = Query(20, ge=1, le=100),
    group_ids: Optional[List[str]] = Query(None),
    episode_type: Optional[str] = Query(None),
    rag_service=Depends(get_rag_service),
    current_user=Depends(get_current_user)
) -> List[EpisodeInfo]:
    """
    Get recent episodes from the knowledge graph.
    
    Returns the most recently created or updated episodes.
    """
    try:
        # Get recent episodes
        episodes = await rag_service.get_recent_episodes(
            limit=limit,
            group_ids=group_ids,
            episode_type=episode_type
        )
        
        # Convert to EpisodeInfo objects
        episode_info = []
        for episode_data in episodes:
            episode_info.append(EpisodeInfo(**episode_data))
        
        return episode_info
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                message=f"Recent episodes retrieval failed: {str(e)}",
                error_type=type(e).__name__,
                details={'limit': limit, 'group_ids': group_ids},
                request_id=str(uuid.uuid4())
            ).model_dump()
        )


@router.post("/explain-query")
async def explain_query_execution(
    request: QueryRequest,
    rag_service=Depends(get_rag_service),
    current_user=Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Explain how a query would be executed without running it.
    
    Returns execution plan, search strategy, and estimated performance metrics.
    """
    try:
        # Get query execution plan
        execution_plan = await rag_service.explain_query(
            query=request.query,
            mode=request.mode.value,
            top_k=request.top_k,
            group_ids=request.group_ids
        )
        
        return {
            'query': request.query,
            'mode': request.mode.value,
            'execution_plan': execution_plan,
            'estimated_execution_time': execution_plan.get('estimated_time', 0.0),
            'search_strategy': execution_plan.get('strategy', 'hybrid'),
            'indexes_used': execution_plan.get('indexes', []),
            'optimization_suggestions': execution_plan.get('suggestions', [])
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                message=f"Query explanation failed: {str(e)}",
                error_type=type(e).__name__,
                details={'query': request.query},
                request_id=str(uuid.uuid4())
            ).model_dump()
        )