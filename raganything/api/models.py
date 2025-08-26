"""
Pydantic models for FastAPI REST service.

This module defines all the request and response models used by the
RAG-Anything API with Graphiti integration.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict


class ProcessingStatus(str, Enum):
    """Status of processing operations"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class QueryMode(str, Enum):
    """Query execution modes"""
    HYBRID = "hybrid"
    SEMANTIC = "semantic" 
    KEYWORD = "keyword"
    ENTITIES = "entities"
    EPISODES = "episodes"
    COMMUNITIES = "communities"


class ContentType(str, Enum):
    """Types of content that can be processed"""
    TEXT = "text"
    IMAGE = "image"
    TABLE = "table"
    EQUATION = "equation"
    MIXED = "mixed"


# Request Models

class TextProcessingRequest(BaseModel):
    """Request for processing plain text content"""
    text: str = Field(..., description="Text content to process")
    title: Optional[str] = Field(None, description="Optional title for the content")
    source: Optional[str] = Field(None, description="Source description")
    group_id: Optional[str] = Field(None, description="Group ID for organizing content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "text": "Artificial intelligence is transforming healthcare through advanced diagnostic tools.",
            "title": "AI in Healthcare",
            "source": "Medical Journal Article",
            "group_id": "healthcare_documents",
            "metadata": {"author": "Dr. Smith", "publication_date": "2024-01-15"}
        }
    })


class QueryRequest(BaseModel):
    """Request for querying the knowledge graph"""
    query: str = Field(..., description="Search query")
    mode: QueryMode = Field(QueryMode.HYBRID, description="Query execution mode")
    top_k: int = Field(10, ge=1, le=100, description="Maximum number of results to return")
    group_ids: Optional[List[str]] = Field(None, description="Specific groups to search in")
    center_node_uuid: Optional[str] = Field(None, description="UUID of center node for proximity search")
    include_sources: bool = Field(True, description="Include source information in results")
    include_metadata: bool = Field(True, description="Include metadata in results")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "query": "What are the latest developments in machine learning?",
            "mode": "hybrid",
            "top_k": 10,
            "group_ids": ["research_papers"],
            "include_sources": True,
            "include_metadata": True
        }
    })


class BatchProcessingRequest(BaseModel):
    """Request for batch processing multiple documents"""
    documents: List[Dict[str, Any]] = Field(..., description="List of documents to process")
    batch_metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata for the entire batch")
    group_id: Optional[str] = Field(None, description="Group ID for all documents")
    parallel_processing: bool = Field(True, description="Whether to process documents in parallel")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "documents": [
                {"text": "Document 1 content", "title": "Doc 1"},
                {"text": "Document 2 content", "title": "Doc 2"}
            ],
            "batch_metadata": {"batch_id": "batch_001", "processing_date": "2024-01-15"},
            "group_id": "batch_documents",
            "parallel_processing": True
        }
    })


class CommunityBuildRequest(BaseModel):
    """Request for building communities"""
    group_ids: Optional[List[str]] = Field(None, description="Specific groups to build communities for")
    force_rebuild: bool = Field(False, description="Force rebuild even if communities exist")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "group_ids": ["research_papers", "healthcare_documents"],
            "force_rebuild": False
        }
    })


class EntityFiltersRequest(BaseModel):
    """Request filters for entity retrieval"""
    group_ids: Optional[List[str]] = Field(None, description="Filter by group IDs")
    entity_types: Optional[List[str]] = Field(None, description="Filter by entity types")
    created_after: Optional[datetime] = Field(None, description="Filter entities created after this date")
    created_before: Optional[datetime] = Field(None, description="Filter entities created before this date")
    has_summary: Optional[bool] = Field(None, description="Filter entities that have/don't have summaries")


class RelationshipFiltersRequest(BaseModel):
    """Request filters for relationship retrieval"""
    group_ids: Optional[List[str]] = Field(None, description="Filter by group IDs")
    relationship_types: Optional[List[str]] = Field(None, description="Filter by relationship types")
    source_entity_uuid: Optional[str] = Field(None, description="Filter by source entity UUID")
    target_entity_uuid: Optional[str] = Field(None, description="Filter by target entity UUID")
    valid_after: Optional[datetime] = Field(None, description="Filter relationships valid after this date")
    valid_before: Optional[datetime] = Field(None, description="Filter relationships valid before this date")


# Response Models

class ProcessingResult(BaseModel):
    """Result of content processing operations"""
    success: bool = Field(..., description="Whether processing was successful")
    message: str = Field(..., description="Processing status message")
    processing_id: Optional[str] = Field(None, description="Unique processing identifier")
    inserted_entities: int = Field(0, description="Number of entities created")
    inserted_relationships: int = Field(0, description="Number of relationships created")
    episodes_processed: int = Field(0, description="Number of episodes processed")
    processing_time: float = Field(0.0, description="Processing time in seconds")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional processing metadata")


class QueryResult(BaseModel):
    """Result of knowledge graph queries"""
    content: str = Field(..., description="Formatted query results")
    sources: List[Dict[str, Any]] = Field(default_factory=list, description="Source information")
    entities: List[Dict[str, Any]] = Field(default_factory=list, description="Related entities")
    relationships: List[Dict[str, Any]] = Field(default_factory=list, description="Related relationships")
    query_metadata: Dict[str, Any] = Field(default_factory=dict, description="Query execution metadata")
    execution_time: float = Field(0.0, description="Query execution time in seconds")


class EntityInfo(BaseModel):
    """Information about a knowledge graph entity"""
    uuid: str = Field(..., description="Unique entity identifier")
    name: str = Field(..., description="Entity name")
    summary: str = Field("", description="Entity summary")
    labels: List[str] = Field(default_factory=list, description="Entity labels/types")
    group_id: Optional[str] = Field(None, description="Group ID")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    embedding_available: bool = Field(False, description="Whether embeddings are available")


class RelationshipInfo(BaseModel):
    """Information about a knowledge graph relationship"""
    uuid: str = Field(..., description="Unique relationship identifier")
    name: str = Field(..., description="Relationship name")
    fact: str = Field("", description="Factual description of the relationship")
    source_uuid: Optional[str] = Field(None, description="Source entity UUID")
    target_uuid: Optional[str] = Field(None, description="Target entity UUID")
    group_id: Optional[str] = Field(None, description="Group ID")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    valid_at: Optional[datetime] = Field(None, description="When relationship became valid")
    invalid_at: Optional[datetime] = Field(None, description="When relationship became invalid")
    episodes: List[str] = Field(default_factory=list, description="Related episode UUIDs")
    embedding_available: bool = Field(False, description="Whether embeddings are available")


class CommunityInfo(BaseModel):
    """Information about a knowledge graph community"""
    uuid: str = Field(..., description="Unique community identifier")
    name: str = Field(..., description="Community name")
    summary: str = Field("", description="Community summary")
    member_count: int = Field(0, description="Number of entities in community")
    group_id: Optional[str] = Field(None, description="Group ID")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")


class EpisodeInfo(BaseModel):
    """Information about an episode"""
    uuid: str = Field(..., description="Unique episode identifier") 
    name: str = Field(..., description="Episode name")
    content: str = Field("", description="Episode content")
    source_description: str = Field("", description="Source description")
    group_id: Optional[str] = Field(None, description="Group ID")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    valid_at: Optional[datetime] = Field(None, description="Reference timestamp")
    entity_count: int = Field(0, description="Number of related entities")


class HealthStatus(BaseModel):
    """Health status of the system"""
    status: str = Field(..., description="Overall system status")
    backend_type: str = Field(..., description="Active backend type")
    initialized: bool = Field(..., description="Whether backend is initialized")
    database_connectivity: str = Field(..., description="Database connection status")
    timestamp: datetime = Field(..., description="Status check timestamp")
    components: Dict[str, Any] = Field(default_factory=dict, description="Component-specific health info")


class SystemStats(BaseModel):
    """System statistics and metrics"""
    backend_type: str = Field(..., description="Active backend type")
    entity_count: int = Field(0, description="Total number of entities")
    relationship_count: int = Field(0, description="Total number of relationships")
    episode_count: int = Field(0, description="Total number of episodes")
    community_count: int = Field(0, description="Total number of communities")
    performance_metrics: Dict[str, Any] = Field(default_factory=dict, description="Performance metrics")
    cache_stats: Dict[str, Any] = Field(default_factory=dict, description="Cache statistics")
    timestamp: datetime = Field(..., description="Stats generation timestamp")


class BatchProcessingStatus(BaseModel):
    """Status of batch processing operations"""
    batch_id: str = Field(..., description="Batch processing identifier")
    status: ProcessingStatus = Field(..., description="Current processing status")
    total_documents: int = Field(0, description="Total documents in batch")
    processed_documents: int = Field(0, description="Number of processed documents")
    failed_documents: int = Field(0, description="Number of failed documents")
    start_time: datetime = Field(..., description="Batch processing start time")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")
    results: List[ProcessingResult] = Field(default_factory=list, description="Individual document results")


class ErrorResponse(BaseModel):
    """Error response model"""
    error: bool = Field(True, description="Indicates this is an error response")
    message: str = Field(..., description="Error message")
    error_type: str = Field(..., description="Type of error")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.now, description="Error timestamp")
    request_id: Optional[str] = Field(None, description="Request identifier for tracking")


# File Upload Models

class FileProcessingRequest(BaseModel):
    """Request for processing uploaded files"""
    group_id: Optional[str] = Field(None, description="Group ID for organizing content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    parser_preference: Optional[str] = Field(None, description="Preferred parser (mineru, docling)")
    parse_method: str = Field("auto", description="Parsing method")


class FileProcessingResult(BaseModel):
    """Result of file processing"""
    filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., description="File size in bytes")
    content_type: str = Field(..., description="MIME type")
    processing_result: ProcessingResult = Field(..., description="Processing outcome")
    extracted_content_types: List[ContentType] = Field(default_factory=list, description="Types of content extracted")
    parsing_method: str = Field(..., description="Parsing method used")
    parsing_time: float = Field(0.0, description="Time spent parsing the file")


# Pagination Models

class PaginationRequest(BaseModel):
    """Request parameters for paginated endpoints"""
    limit: int = Field(20, ge=1, le=1000, description="Number of items per page")
    offset: int = Field(0, ge=0, description="Number of items to skip")


class PaginatedResponse(BaseModel):
    """Generic paginated response wrapper"""
    items: List[Any] = Field(..., description="Items for current page")
    total_count: Optional[int] = Field(None, description="Total number of items")
    limit: int = Field(..., description="Items per page limit")
    offset: int = Field(..., description="Number of items skipped")
    has_more: bool = Field(..., description="Whether there are more items available")


class PaginatedEntitiesResponse(PaginatedResponse):
    """Paginated response for entities"""
    items: List[EntityInfo] = Field(..., description="Entity items for current page")


class PaginatedRelationshipsResponse(PaginatedResponse):
    """Paginated response for relationships"""
    items: List[RelationshipInfo] = Field(..., description="Relationship items for current page")


class PaginatedEpisodesResponse(PaginatedResponse):
    """Paginated response for episodes"""  
    items: List[EpisodeInfo] = Field(..., description="Episode items for current page")


class PaginatedCommunitiesResponse(PaginatedResponse):
    """Paginated response for communities"""
    items: List[CommunityInfo] = Field(..., description="Community items for current page")


# Migration and Management Models

class MigrationRequest(BaseModel):
    """Request for data migration operations"""
    source_backend: str = Field(..., description="Source backend type")
    target_backend: str = Field(..., description="Target backend type")
    group_ids: Optional[List[str]] = Field(None, description="Specific groups to migrate")
    preserve_timestamps: bool = Field(True, description="Whether to preserve original timestamps")
    batch_size: int = Field(100, description="Migration batch size")


class MigrationStatus(BaseModel):
    """Status of migration operations"""
    migration_id: str = Field(..., description="Migration operation identifier")
    status: ProcessingStatus = Field(..., description="Current migration status")
    source_backend: str = Field(..., description="Source backend")
    target_backend: str = Field(..., description="Target backend")
    total_items: int = Field(0, description="Total items to migrate")
    migrated_items: int = Field(0, description="Number of migrated items")
    failed_items: int = Field(0, description="Number of failed items")
    start_time: datetime = Field(..., description="Migration start time")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")
    error_details: List[str] = Field(default_factory=list, description="Migration errors")


class BackendSwitchRequest(BaseModel):
    """Request to switch active backend"""
    target_backend: str = Field(..., description="Target backend to switch to")
    preserve_data: bool = Field(True, description="Whether to preserve existing data")
    force_switch: bool = Field(False, description="Force switch even if target backend has issues")


class BackendStatus(BaseModel):
    """Status of available backends"""
    active_backend: str = Field(..., description="Currently active backend")
    available_backends: List[str] = Field(..., description="List of available backends")
    backend_health: Dict[str, Any] = Field(..., description="Health status of each backend")
    fallback_enabled: bool = Field(..., description="Whether backend fallback is enabled")
    last_switch: Optional[datetime] = Field(None, description="Last backend switch time")