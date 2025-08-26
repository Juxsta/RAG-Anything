"""
Comprehensive Graphiti-Core Direct Integration for RAG-Anything.

This module provides direct integration with graphiti-core library, supporting:
- Full multimodal content processing through episodes
- Direct library integration (not REST API)
- Comprehensive error handling and logging
- Performance optimizations with caching
- Production-ready configuration management
"""

import asyncio
import time
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, Callable
from uuid import uuid4
from dataclasses import dataclass, field

from lightrag.utils import logger

from .base import BaseRAGBackend, BackendConfig, BackendType, QueryResult, InsertResult
from ..episode_converter import EpisodeConverter, EpisodeContent
from ..error_handling import (
    handle_error, ErrorContext, GraphitiError, ProcessingError,
    error_handler_decorator, async_error_context
)

try:
    from graphiti_core import Graphiti
    from graphiti_core.nodes import EpisodeType, EntityNode, EpisodicNode
    from graphiti_core.edges import EntityEdge
    from graphiti_core.driver.falkordb_driver import FalkorDriver
    from graphiti_core.driver.neo4j_driver import Neo4jDriver
    from graphiti_core.llm_client import OpenAIClient, AnthropicClient
    from graphiti_core.embedder import OpenAIEmbedder
    from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
    from graphiti_core.search.search_config_recipes import COMBINED_HYBRID_SEARCH_CROSS_ENCODER
    from graphiti_core.search.search_filters import SearchFilters
    GRAPHITI_AVAILABLE = True
except ImportError as e:
    GRAPHITI_AVAILABLE = False
    logger.warning(f"Graphiti-core not available: {e}")
    Graphiti = None
    EpisodeType = None
    EntityNode = None
    EpisodicNode = None
    EntityEdge = None
    FalkorDriver = None
    Neo4jDriver = None
    OpenAIClient = None
    AnthropicClient = None
    OpenAIEmbedder = None
    OpenAIRerankerClient = None
    COMBINED_HYBRID_SEARCH_CROSS_ENCODER = None
    SearchFilters = None


@dataclass
class GraphitiDirectConfig:
    """Configuration for direct Graphiti integration"""
    # Database configuration
    graph_provider: str = "falkordb"  # "falkordb" or "neo4j"
    
    # FalkorDB configuration
    falkordb_host: str = "localhost"
    falkordb_port: int = 6379
    falkordb_database: str = "rag_graph"
    falkordb_password: Optional[str] = None
    
    # Neo4j configuration
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"
    
    # LLM configuration
    llm_provider: str = "openai"  # "openai", "anthropic", or "custom"
    llm_model: str = "gpt-4o-mini"
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    
    # Embedder configuration
    embedder_provider: str = "openai"
    embedder_model: str = "text-embedding-3-small"
    embedder_api_key: Optional[str] = None
    
    # Episode processing
    default_group_id: str = "default"
    preserve_document_structure: bool = True
    store_raw_episode_content: bool = True
    
    # Performance settings
    max_coroutines: Optional[int] = None
    batch_size: int = 50
    episode_window_len: int = 10
    
    # Caching settings
    enable_cache: bool = True
    cache_ttl: int = 3600  # 1 hour
    
    # Community building
    auto_build_communities: bool = False
    community_update_threshold: int = 100  # episodes


class GraphitiDirectBackend(BaseRAGBackend):
    """
    Direct Graphiti-Core Integration Backend.
    
    This backend provides comprehensive integration with graphiti-core library,
    supporting multimodal content processing through episodes with advanced
    semantic understanding and graph-based knowledge representation.
    """
    
    def __init__(self, config: BackendConfig):
        """
        Initialize the Graphiti Direct backend.
        
        Args:
            config: Backend configuration containing graphiti-specific settings
        """
        if not GRAPHITI_AVAILABLE:
            raise ImportError(
                "Graphiti-core is not available. Please install it with: "
                "pip install graphiti-core[falkordb]"
            )
            
        if config.backend_type != BackendType.GRAPHITI:
            raise ValueError("Config backend_type must be GRAPHITI for GraphitiDirectBackend")
            
        super().__init__(config)
        
        # Initialize graphiti configuration
        graphiti_kwargs = config.backend_kwargs.get('graphiti_config', {})
        self.graphiti_config = GraphitiDirectConfig(**graphiti_kwargs)
        
        # Initialize components
        self.graphiti_client: Optional[Graphiti] = None
        self.episode_converter: Optional[EpisodeConverter] = None
        self.logger = logger
        
        # Performance tracking
        self._stats = {
            'episodes_added': 0,
            'entities_created': 0,
            'relationships_created': 0,
            'queries_executed': 0,
            'last_community_build': None
        }
        
        # Initialize caches
        self._entity_cache = {}
        self._relationship_cache = {}
        
        # Initialize performance caching
        from ..caching import get_cache_manager
        cache_config = {
            'document_cache_size': self.graphiti_config.batch_size * 2,
            'embedding_cache_size': 2000,
            'query_cache_size': 1000,
            'entity_cache_size': 5000,
            'episode_cache_size': self.graphiti_config.batch_size * 3,
            'document_ttl': self.graphiti_config.cache_ttl,
            'embedding_ttl': self.graphiti_config.cache_ttl * 4,
            'query_ttl': 300,  # 5 minutes for queries
            'entity_ttl': self.graphiti_config.cache_ttl,
            'episode_ttl': self.graphiti_config.cache_ttl * 2
        }
        
        self.cache_manager = get_cache_manager(cache_config) if self.graphiti_config.enable_cache else None
        
    async def initialize(self) -> None:
        """Initialize the Graphiti Direct backend with all components"""
        async with async_error_context("GraphitiDirectBackend", "initialization"):
            try:
                self.logger.info("Initializing Graphiti Direct backend...")
                
                # Initialize episode converter
                self.episode_converter = EpisodeConverter(
                    default_group_id=self.graphiti_config.default_group_id,
                    preserve_document_structure=self.graphiti_config.preserve_document_structure
                )
                
                # Create graph driver
                graph_driver = self._create_graph_driver()
                self.logger.info(f"Created graph driver: {type(graph_driver).__name__}")
                
                # Create LLM client
                llm_client = self._create_llm_client()
                self.logger.info(f"Created LLM client: {type(llm_client).__name__}")
                
                # Create embedder
                embedder = self._create_embedder()
                self.logger.info(f"Created embedder: {type(embedder).__name__}")
                
                # Create cross encoder for reranking
                cross_encoder = self._create_cross_encoder()
                self.logger.info(f"Created cross encoder: {type(cross_encoder).__name__}")
                
                # Initialize Graphiti client
                self.graphiti_client = Graphiti(
                    graph_driver=graph_driver,
                    llm_client=llm_client,
                    embedder=embedder,
                    cross_encoder=cross_encoder,
                    store_raw_episode_content=self.graphiti_config.store_raw_episode_content,
                    max_coroutines=self.graphiti_config.max_coroutines,
                    ensure_ascii=False  # Preserve non-ASCII characters
                )
                
                # Build database schema
                self.logger.info("Building database indices and constraints...")
                await self.graphiti_client.build_indices_and_constraints()
                
                self._initialized = True
                self.logger.info("Graphiti Direct backend initialized successfully")
                
            except Exception as e:
                error_context = ErrorContext(
                    operation="initialization",
                    component="GraphitiDirectBackend",
                    additional_data={
                        "graph_provider": self.graphiti_config.graph_provider,
                        "llm_provider": self.graphiti_config.llm_provider
                    }
                )
                handled_error = handle_error(e, error_context)
                raise GraphitiError(f"Graphiti initialization failed: {handled_error.message}") from e
    
    def _create_graph_driver(self):
        """Create and configure the graph database driver"""
        provider = self.graphiti_config.graph_provider.lower()
        
        if provider == "falkordb":
            return FalkorDriver(
                host=self.graphiti_config.falkordb_host,
                port=self.graphiti_config.falkordb_port,
                database=self.graphiti_config.falkordb_database,
                password=self.graphiti_config.falkordb_password
            )
        elif provider == "neo4j":
            return Neo4jDriver(
                uri=self.graphiti_config.neo4j_uri,
                user=self.graphiti_config.neo4j_user,
                password=self.graphiti_config.neo4j_password
            )
        else:
            raise ValueError(f"Unsupported graph provider: {provider}")
    
    def _create_llm_client(self):
        """Create and configure the LLM client"""
        # Use custom LLM function if provided
        if self.config.llm_model_func:
            return GraphitiLLMWrapper(self.config.llm_model_func)
        
        provider = self.graphiti_config.llm_provider.lower()
        
        if provider == "openai":
            return OpenAIClient(
                api_key=self.graphiti_config.llm_api_key,
                base_url=self.graphiti_config.llm_base_url,
                model=self.graphiti_config.llm_model
            )
        elif provider == "anthropic":
            return AnthropicClient(
                api_key=self.graphiti_config.llm_api_key,
                model=self.graphiti_config.llm_model
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
    
    def _create_embedder(self):
        """Create and configure the embedder client"""
        # Use custom embedding function if provided
        if self.config.embedding_func:
            return GraphitiEmbedderWrapper(self.config.embedding_func)
        
        provider = self.graphiti_config.embedder_provider.lower()
        
        if provider == "openai":
            return OpenAIEmbedder(
                api_key=self.graphiti_config.embedder_api_key,
                model=self.graphiti_config.embedder_model
            )
        else:
            raise ValueError(f"Unsupported embedder provider: {provider}")
    
    def _create_cross_encoder(self):
        """Create and configure the cross encoder for reranking"""
        return OpenAIRerankerClient(
            api_key=self.graphiti_config.llm_api_key,
            model=self.graphiti_config.llm_model
        )
    
    async def finalize(self) -> None:
        """Clean up Graphiti resources"""
        try:
            if self.graphiti_client:
                await self.graphiti_client.close()
                self.logger.info("Closed Graphiti client connection")
            
            # Clear caches if cache manager is available
            if self.cache_manager:
                self.cache_manager.invalidate_cache()
                self.cache_manager.shutdown()
                self.logger.info("Cache manager shutdown complete")
            
            self._initialized = False
            self.logger.info("Graphiti Direct backend finalized successfully")
            
        except Exception as e:
            self.logger.error(f"Error during Graphiti Direct backend finalization: {e}")
            raise
    
    @error_handler_decorator("GraphitiDirectBackend", "insert_text")
    async def insert_text(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> InsertResult:
        """Insert plain text content as a Graphiti episode"""
        if not self._initialized:
            raise GraphitiError("Backend not initialized. Call initialize() first.")
        
        start_time = time.time()
        metadata = metadata or {}
        
        async with async_error_context("GraphitiDirectBackend", "insert_text", metadata.get('user_id')):
            try:
                # Create episode data
                episode_name = metadata.get('title', f"Text Episode {datetime.now().strftime('%Y%m%d_%H%M%S')}")
                episode_data = {
                    'name': episode_name,
                    'episode_body': text,
                    'source_description': metadata.get('source', 'Text input'),
                    'reference_time': metadata.get('timestamp') or datetime.now(),
                    'source': EpisodeType.message,
                    'group_id': metadata.get('group_id', self.graphiti_config.default_group_id),
                    'uuid': metadata.get('uuid', str(uuid4())),
                    'update_communities': self._should_update_communities(),
                }
                
                # Add episode to Graphiti with progress tracking
                progress_msgs = []
                
                async def progress_callback(msg: str):
                    progress_msgs.append(f"[{time.time() - start_time:.1f}s] {msg}")
                    self.logger.debug(f"Episode processing: {msg}")
                
                result = await self.graphiti_client.add_episode(
                    progress_callback=progress_callback,
                    **episode_data
                )
                
                # Update stats
                self._stats['episodes_added'] += 1
                self._stats['entities_created'] += len(result.nodes)
                self._stats['relationships_created'] += len(result.edges)
                
                processing_time = time.time() - start_time
                
                return InsertResult(
                    success=True,
                    message=f"Text episode added successfully. Created {len(result.nodes)} entities and {len(result.edges)} relationships.",
                    inserted_entities=len(result.nodes),
                    inserted_relationships=len(result.edges),
                    processing_time=processing_time,
                    metadata={
                        **metadata,
                        'episode_uuid': result.episode.uuid,
                        'group_id': result.episode.group_id,
                        'processing_steps': progress_msgs,
                        'communities_updated': len(result.communities)
                    }
                )
                
            except Exception as e:
                processing_time = time.time() - start_time
                error_context = ErrorContext(
                    operation="insert_text",
                    component="GraphitiDirectBackend",
                    user_id=metadata.get('user_id'),
                    additional_data={
                        'text_length': len(text),
                        'group_id': metadata.get('group_id', self.graphiti_config.default_group_id)
                    }
                )
                handled_error = handle_error(e, error_context)
                
                return InsertResult(
                    success=False,
                    message=handled_error.user_message,
                    processing_time=processing_time,
                    metadata={**metadata, 'error_type': type(e).__name__, 'error_category': handled_error.category.value}
                )
    
    async def insert_multimodal_content(
        self,
        content: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> InsertResult:
        """Insert multimodal content as structured Graphiti episodes"""
        if not self._initialized:
            raise RuntimeError("Backend not initialized. Call initialize() first.")
        
        start_time = time.time()
        metadata = metadata or {}
        
        try:
            # Convert multimodal content to episode format using enhanced converter
            episodes = self.episode_converter.convert_document(content, metadata)
            
            if not episodes:
                return InsertResult(
                    success=False,
                    message="No episodes could be created from the multimodal content",
                    processing_time=time.time() - start_time,
                    metadata=metadata
                )
            
            # Process episodes in batches for efficiency
            batch_size = self.graphiti_config.batch_size
            total_entities = 0
            total_relationships = 0
            total_communities = 0
            episode_results = []
            
            for i in range(0, len(episodes), batch_size):
                batch = episodes[i:i + batch_size]
                batch_start = time.time()
                
                self.logger.info(f"Processing episode batch {i//batch_size + 1}/{(len(episodes) + batch_size - 1)//batch_size} ({len(batch)} episodes)")
                
                # Process batch episodes
                for episode_content in batch:
                    try:
                        episode_data = {
                            **episode_content.to_dict(),
                            'update_communities': self._should_update_communities(),
                        }
                        
                        # Add episode with progress tracking
                        progress_msgs = []
                        
                        async def progress_callback(msg: str):
                            progress_msgs.append(f"[{time.time() - batch_start:.1f}s] {episode_content.name}: {msg}")
                        
                        result = await self.graphiti_client.add_episode(
                            progress_callback=progress_callback,
                            **episode_data
                        )
                        
                        total_entities += len(result.nodes)
                        total_relationships += len(result.edges)
                        total_communities += len(result.communities)
                        
                        episode_results.append({
                            'episode_uuid': result.episode.uuid,
                            'entities': len(result.nodes),
                            'relationships': len(result.edges),
                            'communities': len(result.communities),
                            'processing_steps': progress_msgs
                        })
                        
                    except Exception as e:
                        self.logger.error(f"Failed to process episode {episode_content.name}: {e}")
                        episode_results.append({
                            'episode_name': episode_content.name,
                            'error': str(e),
                            'error_type': type(e).__name__
                        })
                
                batch_time = time.time() - batch_start
                self.logger.info(f"Completed batch in {batch_time:.2f}s")
                
                # Brief pause between batches to prevent overwhelming the system
                if i + batch_size < len(episodes):
                    await asyncio.sleep(0.1)
            
            # Update global stats
            self._stats['episodes_added'] += len(episodes)
            self._stats['entities_created'] += total_entities
            self._stats['relationships_created'] += total_relationships
            
            processing_time = time.time() - start_time
            
            return InsertResult(
                success=True,
                message=f"Multimodal content processed successfully. Created {total_entities} entities and {total_relationships} relationships from {len(episodes)} episodes.",
                inserted_entities=total_entities,
                inserted_relationships=total_relationships,
                processing_time=processing_time,
                metadata={
                    **metadata,
                    'episodes_processed': len(episodes),
                    'communities_created': total_communities,
                    'episode_results': episode_results,
                    'content_types': list(content.keys()) if isinstance(content, dict) else ['mixed']
                }
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"Failed to insert multimodal episode: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            
            return InsertResult(
                success=False,
                message=error_msg,
                processing_time=processing_time,
                metadata={**metadata, 'error_type': type(e).__name__}
            )
    
    async def query(
        self,
        query: str,
        mode: str = "hybrid",
        top_k: int = 10,
        **kwargs
    ) -> QueryResult:
        """Query using Graphiti's advanced search capabilities"""
        if not self._initialized:
            raise RuntimeError("Backend not initialized. Call initialize() first.")
        
        query_start = datetime.now()
        
        try:
            # Configure search based on mode
            search_config = COMBINED_HYBRID_SEARCH_CROSS_ENCODER.model_copy()
            search_config.limit = top_k
            
            # Extract search parameters
            group_ids = kwargs.get('group_ids', [self.graphiti_config.default_group_id])
            center_node_uuid = kwargs.get('center_node_uuid')
            search_filter = kwargs.get('search_filter', SearchFilters())
            
            # Perform advanced search
            search_results = await self.graphiti_client.search_(
                query=query,
                config=search_config,
                group_ids=group_ids,
                center_node_uuid=center_node_uuid,
                search_filter=search_filter
            )
            
            # Format results into readable content
            content = self._format_search_results(search_results, mode)
            
            # Extract structured data
            sources = self._extract_sources(search_results)
            entities = self._extract_entities(search_results)
            relationships = self._extract_relationships(search_results)
            
            # Update stats
            self._stats['queries_executed'] += 1
            
            return QueryResult(
                content=content,
                sources=sources,
                entities=entities,
                relationships=relationships,
                metadata={
                    "mode": mode,
                    "top_k": top_k,
                    "group_ids": group_ids,
                    "search_config": search_config.model_dump(),
                    "total_edges": len(search_results.edges),
                    "total_nodes": len(search_results.nodes),
                    "total_episodes": len(search_results.episodes),
                    "total_communities": len(search_results.communities),
                    "additional_params": kwargs
                },
                query_time=query_start,
                backend_type=BackendType.GRAPHITI
            )
            
        except Exception as e:
            self.logger.error(f"Error during Graphiti query: {e}", exc_info=True)
            return QueryResult(
                content=f"Query failed: {str(e)}",
                metadata={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "mode": mode,
                    "query": query
                },
                query_time=query_start,
                backend_type=BackendType.GRAPHITI
            )
    
    def _format_search_results(self, results, mode: str) -> str:
        """Format Graphiti search results into readable content"""
        if not results or (not results.edges and not results.nodes and not results.episodes):
            return "No relevant results found."
        
        sections = []
        
        # Add relationship facts from edges
        if results.edges:
            facts = []
            for i, edge in enumerate(results.edges[:10], 1):  # Limit to top 10
                fact = getattr(edge, 'fact', str(edge))
                confidence = results.edge_reranker_scores[i-1] if i-1 < len(results.edge_reranker_scores) else 0.0
                facts.append(f"{i}. {fact} (confidence: {confidence:.3f})")
            sections.append("## Key Facts:\n" + "\n".join(facts))
        
        # Add entity information
        if results.nodes and mode in ["hybrid", "entities"]:
            entities = []
            for i, node in enumerate(results.nodes[:5], 1):  # Limit to top 5 entities
                name = getattr(node, 'name', str(node))
                summary = getattr(node, 'summary', '')
                confidence = results.node_reranker_scores[i-1] if i-1 < len(results.node_reranker_scores) else 0.0
                entities.append(f"{i}. **{name}**: {summary} (confidence: {confidence:.3f})")
            sections.append("## Related Entities:\n" + "\n".join(entities))
        
        # Add episode context
        if results.episodes and mode in ["hybrid", "episodes"]:
            episodes = []
            for i, episode in enumerate(results.episodes[:3], 1):  # Limit to top 3 episodes
                name = getattr(episode, 'name', f'Episode {i}')
                content = getattr(episode, 'content', '')[:200] + "..." if len(getattr(episode, 'content', '')) > 200 else getattr(episode, 'content', '')
                confidence = results.episode_reranker_scores[i-1] if i-1 < len(results.episode_reranker_scores) else 0.0
                episodes.append(f"{i}. **{name}**: {content} (confidence: {confidence:.3f})")
            sections.append("## Episode Context:\n" + "\n".join(episodes))
        
        # Add community insights
        if results.communities:
            communities = []
            for i, community in enumerate(results.communities[:3], 1):  # Limit to top 3 communities
                name = getattr(community, 'name', f'Community {i}')
                summary = getattr(community, 'summary', '')[:150] + "..." if len(getattr(community, 'summary', '')) > 150 else getattr(community, 'summary', '')
                confidence = results.community_reranker_scores[i-1] if i-1 < len(results.community_reranker_scores) else 0.0
                communities.append(f"{i}. **{name}**: {summary} (confidence: {confidence:.3f})")
            sections.append("## Community Insights:\n" + "\n".join(communities))
        
        return "\n\n".join(sections)
    
    def _extract_sources(self, results) -> List[Dict[str, Any]]:
        """Extract source information from Graphiti search results"""
        sources = []
        
        # Add episode sources
        for episode in results.episodes:
            sources.append({
                "uuid": episode.uuid,
                "type": "episode",
                "name": episode.name,
                "source_description": getattr(episode, 'source_description', 'Unknown'),
                "valid_at": getattr(episode, 'valid_at', None),
                "group_id": getattr(episode, 'group_id', None)
            })
        
        # Add edge sources
        for edge in results.edges:
            sources.append({
                "uuid": edge.uuid,
                "type": "relationship",
                "name": getattr(edge, 'name', 'Unknown relationship'),
                "source_uuid": getattr(edge, 'source_uuid', None),
                "target_uuid": getattr(edge, 'target_uuid', None),
                "episodes": getattr(edge, 'episodes', [])
            })
        
        return sources
    
    def _extract_entities(self, results) -> List[Dict[str, Any]]:
        """Extract entity information from Graphiti search results"""
        entities = []
        
        for node in results.nodes:
            entities.append({
                "uuid": node.uuid,
                "name": node.name,
                "summary": getattr(node, 'summary', ''),
                "labels": getattr(node, 'labels', []),
                "group_id": getattr(node, 'group_id', None),
                "created_at": getattr(node, 'created_at', None),
                "embedding": getattr(node, 'name_embedding', None) is not None
            })
        
        return entities
    
    def _extract_relationships(self, results) -> List[Dict[str, Any]]:
        """Extract relationship information from Graphiti search results"""
        relationships = []
        
        for edge in results.edges:
            relationships.append({
                "uuid": edge.uuid,
                "name": getattr(edge, 'name', 'Unknown'),
                "fact": getattr(edge, 'fact', ''),
                "source_uuid": getattr(edge, 'source_uuid', None),
                "target_uuid": getattr(edge, 'target_uuid', None),
                "group_id": getattr(edge, 'group_id', None),
                "created_at": getattr(edge, 'created_at', None),
                "valid_at": getattr(edge, 'valid_at', None),
                "invalid_at": getattr(edge, 'invalid_at', None),
                "episodes": getattr(edge, 'episodes', [])
            })
        
        return relationships
    
    async def get_entities(
        self,
        limit: int = 100,
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve entities from Graphiti's knowledge graph with caching"""
        if not self._initialized:
            raise RuntimeError("Backend not initialized. Call initialize() first.")
        
        try:
            # Use cache manager if available
            if self.cache_manager:
                async def compute_entities():
                    return await self._fetch_entities_from_db(limit, offset, filters)
                
                cache_key = f"entities_{limit}_{offset}_{hash(str(filters))}"
                return await self.cache_manager.get_or_compute_query(
                    query=cache_key,
                    mode="entity_fetch",
                    params={"limit": limit, "offset": offset, "filters": filters},
                    compute_fn=compute_entities
                )
            else:
                return await self._fetch_entities_from_db(limit, offset, filters)
            
        except Exception as e:
            self.logger.error(f"Error retrieving entities: {e}", exc_info=True)
            return []
    
    async def _fetch_entities_from_db(
        self, 
        limit: int, 
        offset: int, 
        filters: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Internal method to fetch entities from database"""
        # Determine group IDs to query
        group_ids = None
        if filters and 'group_ids' in filters:
            group_ids = filters['group_ids']
        elif not filters or not filters.get('all_groups', False):
            group_ids = [self.graphiti_config.default_group_id]
        
        # Get entities using Graphiti's node retrieval
        entities = await EntityNode.get_by_group_ids(
            self.graphiti_client.driver,
            group_ids
        )
        
        # Apply offset and limit
        entities = entities[offset:offset + limit] if entities else []
        
        # Convert to standardized format
        result = []
        for entity in entities:
            entity_data = {
                "uuid": entity.uuid,
                "name": entity.name,
                "summary": getattr(entity, 'summary', ''),
                "labels": getattr(entity, 'labels', []),
                "group_id": getattr(entity, 'group_id', None),
                "created_at": getattr(entity, 'created_at', None),
                "embedding_available": getattr(entity, 'name_embedding', None) is not None
            }
            result.append(entity_data)
            
            # Cache individual entity if cache manager is available
            if self.cache_manager:
                self.cache_manager.cache_entity(entity.uuid, entity_data)
        
        return result
    
    async def get_relationships(
        self,
        limit: int = 100,
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve relationships from Graphiti's knowledge graph"""
        if not self._initialized:
            raise RuntimeError("Backend not initialized. Call initialize() first.")
        
        try:
            # Check cache first
            cache_key = f"relationships_{limit}_{offset}_{hash(str(filters))}"
            if self.graphiti_config.enable_cache and cache_key in self._relationship_cache:
                cache_entry = self._relationship_cache[cache_key]
                if time.time() - cache_entry['timestamp'] < self.graphiti_config.cache_ttl:
                    return cache_entry['data']
            
            # Determine group IDs to query
            group_ids = None
            if filters and 'group_ids' in filters:
                group_ids = filters['group_ids']
            elif not filters or not filters.get('all_groups', False):
                group_ids = [self.graphiti_config.default_group_id]
            
            # Get edges using Graphiti's edge retrieval
            edges = await EntityEdge.get_by_group_ids(
                self.graphiti_client.driver,
                group_ids
            )
            
            # Apply offset and limit
            edges = edges[offset:offset + limit] if edges else []
            
            # Convert to standardized format
            result = []
            for edge in edges:
                result.append({
                    "uuid": edge.uuid,
                    "name": getattr(edge, 'name', 'Unknown'),
                    "fact": getattr(edge, 'fact', ''),
                    "source_uuid": getattr(edge, 'source_uuid', None),
                    "target_uuid": getattr(edge, 'target_uuid', None),
                    "group_id": getattr(edge, 'group_id', None),
                    "created_at": getattr(edge, 'created_at', None),
                    "valid_at": getattr(edge, 'valid_at', None),
                    "invalid_at": getattr(edge, 'invalid_at', None),
                    "episodes": getattr(edge, 'episodes', []),
                    "embedding_available": getattr(edge, 'fact_embedding', None) is not None
                })
            
            # Cache the result
            if self.graphiti_config.enable_cache:
                self._relationship_cache[cache_key] = {
                    'data': result,
                    'timestamp': time.time()
                }
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error retrieving relationships: {e}", exc_info=True)
            return []
    
    async def build_communities(self, group_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """Build communities using Graphiti's community detection"""
        if not self._initialized:
            raise RuntimeError("Backend not initialized. Call initialize() first.")
        
        try:
            self.logger.info("Starting community building...")
            start_time = time.time()
            
            # Use provided group IDs or default
            if group_ids is None:
                group_ids = [self.graphiti_config.default_group_id]
            
            # Build communities
            communities, community_edges = await self.graphiti_client.build_communities(group_ids)
            
            build_time = time.time() - start_time
            
            # Update stats
            self._stats['last_community_build'] = datetime.now()
            
            self.logger.info(f"Built {len(communities)} communities with {len(community_edges)} edges in {build_time:.2f}s")
            
            return {
                "success": True,
                "communities_created": len(communities),
                "community_edges_created": len(community_edges),
                "build_time": build_time,
                "group_ids": group_ids
            }
            
        except Exception as e:
            self.logger.error(f"Error building communities: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    def _should_update_communities(self) -> bool:
        """Determine if communities should be updated based on configuration and stats"""
        if not self.graphiti_config.auto_build_communities:
            return False
        
        # Update communities every N episodes
        return (self._stats['episodes_added'] % self.graphiti_config.community_update_threshold) == 0
    
    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check of the Graphiti Direct backend"""
        base_health = await super().health_check()
        
        graphiti_health = {
            **base_health,
            "graphiti_config": {
                "graph_provider": self.graphiti_config.graph_provider,
                "default_group_id": self.graphiti_config.default_group_id,
                "store_raw_content": self.graphiti_config.store_raw_episode_content,
                "auto_build_communities": self.graphiti_config.auto_build_communities
            },
            "stats": self._stats.copy(),
            "caches": {
                "entity_cache_size": len(self._entity_cache),
                "relationship_cache_size": len(self._relationship_cache)
            }
        }
        
        if self.graphiti_client:
            try:
                # Test database connectivity
                test_episodes = await self.graphiti_client.retrieve_episodes(
                    reference_time=datetime.now(),
                    last_n=1,
                    group_ids=[self.graphiti_config.default_group_id]
                )
                graphiti_health["database_connectivity"] = "healthy"
                graphiti_health["sample_episodes_retrieved"] = len(test_episodes)
            except Exception as e:
                graphiti_health["database_connectivity"] = f"error: {str(e)}"
        
        return graphiti_health
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics about the knowledge graph"""
        base_stats = await super().get_stats()
        
        if not self._initialized:
            return {**base_stats, "graphiti_stats": "backend_not_initialized"}
        
        try:
            # Get detailed statistics
            entities = await self.get_entities(limit=0)  # Get count
            relationships = await self.get_relationships(limit=0)  # Get count
            
            # Get recent episodes
            recent_episodes = await self.graphiti_client.retrieve_episodes(
                reference_time=datetime.now(),
                last_n=10,
                group_ids=[self.graphiti_config.default_group_id]
            )
            
            graphiti_stats = {
                **base_stats,
                "graphiti_version": "0.19.0",
                "graph_provider": self.graphiti_config.graph_provider,
                "total_episodes": len(recent_episodes),
                "recent_episodes": len(recent_episodes),
                "cache_stats": {
                    "entity_cache_hits": len(self._entity_cache),
                    "relationship_cache_hits": len(self._relationship_cache),
                    "cache_enabled": self.graphiti_config.enable_cache
                },
                "performance_stats": self._stats.copy()
            }
            
            return graphiti_stats
            
        except Exception as e:
            return {
                **base_stats,
                "graphiti_stats": f"error: {str(e)}",
                "error_type": type(e).__name__
            }


class GraphitiLLMWrapper:
    """Wrapper to adapt external LLM functions to Graphiti's LLM client interface"""
    
    def __init__(self, llm_func: Callable):
        self.llm_func = llm_func
        self.logger = logger
    
    async def __call__(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Adapt the call to external LLM function"""
        try:
            # Convert messages to prompt format expected by external function
            if isinstance(messages, list) and len(messages) > 0:
                # Take the last message content or combine all messages
                if len(messages) == 1:
                    prompt = messages[0].get("content", "")
                else:
                    prompt = "\n".join([msg.get("content", "") for msg in messages])
            else:
                prompt = str(messages)
            
            # Call the external function
            if asyncio.iscoroutinefunction(self.llm_func):
                result = await self.llm_func(prompt, **kwargs)
            else:
                result = self.llm_func(prompt, **kwargs)
            
            return str(result)
            
        except Exception as e:
            self.logger.error(f"LLM function call failed: {e}")
            raise RuntimeError(f"LLM function call failed: {e}") from e


class GraphitiEmbedderWrapper:
    """Wrapper to adapt external embedding functions to Graphiti's embedder interface"""
    
    def __init__(self, embedding_func: Callable):
        self.embedding_func = embedding_func
        self.logger = logger
    
    async def embed(self, texts: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
        """Adapt the call to external embedding function"""
        try:
            if asyncio.iscoroutinefunction(self.embedding_func):
                result = await self.embedding_func(texts)
            else:
                result = self.embedding_func(texts)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Embedding function call failed: {e}")
            raise RuntimeError(f"Embedding function call failed: {e}") from e