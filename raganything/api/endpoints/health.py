"""
Health monitoring and statistics endpoints for RAG-Anything API.
"""

from datetime import datetime
from fastapi import APIRouter, Depends

from ..models import HealthStatus, SystemStats
from ..dependencies import get_rag_service, get_current_user

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/", response_model=HealthStatus)
async def health_check(
    rag_service=Depends(get_rag_service)
):
    """Get system health status."""
    health = await rag_service.health_check()
    
    return HealthStatus(
        status=health.get('status', 'unknown'),
        backend_type=health.get('backend_type', 'unknown'),
        initialized=health.get('initialized', False),
        database_connectivity=health.get('database_connectivity', 'unknown'),
        timestamp=datetime.now(),
        components=health
    )


@router.get("/stats", response_model=SystemStats)
async def get_system_stats(
    rag_service=Depends(get_rag_service),
    current_user=Depends(get_current_user)
):
    """Get comprehensive system statistics."""
    stats = await rag_service.get_stats()
    
    return SystemStats(
        backend_type=stats.get('backend_type', 'unknown'),
        entity_count=stats.get('entity_count', 0),
        relationship_count=stats.get('relationship_count', 0),
        episode_count=stats.get('total_episodes', 0),
        community_count=stats.get('community_count', 0),
        performance_metrics=stats.get('performance_stats', {}),
        cache_stats=stats.get('cache_stats', {}),
        timestamp=datetime.now()
    )