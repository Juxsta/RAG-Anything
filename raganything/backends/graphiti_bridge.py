"""
Graphiti Bridge for Backend Abstraction Layer.

This bridge provides integration with Graphiti's episodic knowledge graph,
converting multimodal content to episodes and leveraging Graphiti's semantic
understanding capabilities.
"""

import asyncio
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from lightrag.utils import logger

from .base import BaseRAGBackend, BackendConfig, BackendType, QueryResult, InsertResult

try:
    from graphiti_core import Graphiti
    from graphiti_core.nodes import EpisodicNode, EpisodeType
    from graphiti_core.driver.falkordb_driver import FalkorDriver
    from graphiti_core.llm_client import OpenAIClient
    GRAPHITI_AVAILABLE = True
except ImportError:
    GRAPHITI_AVAILABLE = False
    Graphiti = None
    EpisodicNode = None
    EpisodeType = None
    FalkorDriver = None
    OpenAIClient = None


class GraphitiBridge(BaseRAGBackend):
    """
    Bridge for Graphiti backend that implements the BaseRAGBackend interface.
    
    This class integrates with Graphiti's episodic knowledge graph system,
    converting multimodal content into episodes for semantic processing.
    """
    
    def __init__(self, config: BackendConfig):
        """
        Initialize the Graphiti bridge.
        
        Args:
            config: Backend configuration
        """
        if not GRAPHITI_AVAILABLE:
            raise ImportError(
                "Graphiti is not installed. Please install it with: "
                "pip install graphiti-core"
            )
            
        if config.backend_type != BackendType.GRAPHITI:
            raise ValueError("Config backend_type must be GRAPHITI for GraphitiBridge")
            
        super().__init__(config)
        self.graphiti_client: Optional[Graphiti] = None
        self.logger = logger
        
        # Extract Graphiti-specific configuration
        self.graph_config = config.backend_kwargs.get('graph_config', {})
        self.llm_config = config.backend_kwargs.get('llm_config', {})
        self.group_id = config.backend_kwargs.get('group_id', 'default')
        
    async def initialize(self) -> None:
        """Initialize the Graphiti backend"""
        try:
            # Set up graph driver
            graph_driver = self._create_graph_driver()
            
            # Set up LLM client
            llm_client = self._create_llm_client()
            
            # Initialize Graphiti client
            self.graphiti_client = Graphiti(
                graph_driver=graph_driver,
                llm_client=llm_client
            )
            
            # Build indices and constraints
            await self.graphiti_client.build_indices_and_constraints()
            
            self._initialized = True
            self.logger.info("Graphiti bridge initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Graphiti bridge: {e}")
            raise
    
    def _create_graph_driver(self):
        """Create and configure the graph driver"""
        graph_provider = self.graph_config.get('provider', 'falkordb')
        
        if graph_provider == 'falkordb':
            return FalkorDriver(
                host=self.graph_config.get('host', 'localhost'),
                port=self.graph_config.get('port', 6379),
                database=self.graph_config.get('database', 'rag_graph'),
                password=self.graph_config.get('password', None)
            )
        else:
            # Default to Neo4j
            from graphiti_core.driver.neo4j_driver import Neo4jDriver
            return Neo4jDriver(
                uri=self.graph_config.get('uri', 'bolt://localhost:7687'),
                user=self.graph_config.get('user', 'neo4j'),
                password=self.graph_config.get('password', 'password')
            )
    
    def _create_llm_client(self):
        """Create and configure the LLM client"""
        # Use provided LLM model function if available
        if self.config.llm_model_func:
            # Create a wrapper that adapts to Graphiti's LLM client interface
            return GraphitiLLMWrapper(self.config.llm_model_func)
        
        # Otherwise create OpenAI client
        return OpenAIClient(
            api_key=self.llm_config.get('api_key'),
            base_url=self.llm_config.get('base_url'),
            model=self.llm_config.get('model', 'gpt-4o-mini')
        )
    
    async def finalize(self) -> None:
        """Clean up Graphiti resources"""
        try:
            if self.graphiti_client:
                await self.graphiti_client.close()
            
            self._initialized = False
            self.logger.info("Graphiti bridge finalized successfully")
            
        except Exception as e:
            self.logger.error(f"Error during Graphiti bridge finalization: {e}")
            raise
    
    async def insert_text(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> InsertResult:
        """Insert text content as a Graphiti episode"""
        if not self._initialized:
            raise RuntimeError("Backend not initialized. Call initialize() first.")
        
        start_time = time.time()
        
        try:
            # Create episode from text
            episode_data = {
                'name': metadata.get('title', f"Text Episode {datetime.now().strftime('%Y%m%d_%H%M%S')}"),
                'episode_body': text,
                'source_description': metadata.get('source', 'Text input'),
                'reference_time': datetime.now(),
                'source': EpisodeType.message,
                'group_id': metadata.get('group_id', self.group_id),
                'uuid': metadata.get('uuid', str(uuid4())),
            }
            
            # Add episode to Graphiti
            result = await self.graphiti_client.add_episode(**episode_data)
            
            processing_time = time.time() - start_time
            
            return InsertResult(
                success=True,
                message="Text episode added successfully",
                inserted_entities=result.get('entities_created', 0) if isinstance(result, dict) else 0,
                inserted_relationships=result.get('edges_created', 0) if isinstance(result, dict) else 0,
                processing_time=processing_time,
                metadata={
                    **(metadata or {}),
                    'episode_uuid': episode_data['uuid'],
                    'group_id': episode_data['group_id']
                }
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"Error inserting text episode: {e}")
            
            return InsertResult(
                success=False,
                message=f"Failed to insert text episode: {str(e)}",
                processing_time=processing_time,
                metadata=metadata or {}
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
        
        try:
            # Convert multimodal content to episode format
            episode_body = self._create_episode_body(content)
            
            episode_data = {
                'name': content.get('title') or metadata.get('title', 
                    f"Multimodal Episode {datetime.now().strftime('%Y%m%d_%H%M%S')}"),
                'episode_body': episode_body,
                'source_description': content.get('source_description') or 
                    metadata.get('source', 'Multimodal content'),
                'reference_time': content.get('timestamp') or datetime.now(),
                'source': self._determine_episode_type(content),
                'group_id': metadata.get('group_id', self.group_id),
                'uuid': metadata.get('uuid', str(uuid4())),
            }
            
            # Add episode to Graphiti
            result = await self.graphiti_client.add_episode(**episode_data)
            
            processing_time = time.time() - start_time
            
            return InsertResult(
                success=True,
                message="Multimodal episode added successfully",
                inserted_entities=result.get('entities_created', 0) if isinstance(result, dict) else 0,
                inserted_relationships=result.get('edges_created', 0) if isinstance(result, dict) else 0,
                processing_time=processing_time,
                metadata={
                    **(metadata or {}),
                    'episode_uuid': episode_data['uuid'],
                    'content_types': list(content.keys()),
                    'group_id': episode_data['group_id']
                }
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"Error inserting multimodal episode: {e}")
            
            return InsertResult(
                success=False,
                message=f"Failed to insert multimodal episode: {str(e)}",
                processing_time=processing_time,
                metadata=metadata or {}
            )
    
    def _create_episode_body(self, content: Dict[str, Any]) -> str:
        """Create structured episode body from multimodal content"""
        sections = []
        
        # Add title if available
        if 'title' in content:
            sections.append(f"# {content['title']}\n")
        
        # Add main text content
        if 'text' in content:
            sections.append(content['text'])
        
        # Add contextual information
        if 'context' in content:
            sections.append(f"\n## Context\n{content['context']}")
        
        # Add image descriptions
        if 'image_caption' in content:
            sections.append(f"\n## Visual Content\n{content['image_caption']}")
        
        # Add table content
        if 'table_content' in content:
            sections.append(f"\n## Table Data\n{content['table_content']}")
        
        # Add equations
        if 'equation' in content:
            sections.append(f"\n## Mathematical Content\n{content['equation']}")
        
        # Add any additional structured data
        for key, value in content.items():
            if key not in ['title', 'text', 'context', 'image_caption', 'table_content', 'equation', 'timestamp', 'source_description']:
                sections.append(f"\n## {key.replace('_', ' ').title()}\n{value}")
        
        return "\n\n".join(sections)
    
    def _determine_episode_type(self, content: Dict[str, Any]) -> EpisodeType:
        """Determine the appropriate episode type based on content"""
        # Check content types and return appropriate episode type
        if 'image_caption' in content:
            return EpisodeType.observation  # Images are observations
        elif 'table_content' in content:
            return EpisodeType.observation  # Tables are structured observations
        elif 'equation' in content:
            return EpisodeType.observation  # Equations are mathematical observations
        else:
            return EpisodeType.message  # Default to message type
    
    async def query(
        self,
        query: str,
        mode: str = "hybrid",
        top_k: int = 10,
        **kwargs
    ) -> QueryResult:
        """Query using Graphiti's search capabilities"""
        if not self._initialized:
            raise RuntimeError("Backend not initialized. Call initialize() first.")
        
        query_start = datetime.now()
        
        try:
            # Use Graphiti's search method
            # Note: Adjust based on actual Graphiti search API
            search_results = await self.graphiti_client.search(
                query=query,
                limit=top_k,
                group_ids=[self.group_id] if kwargs.get('group_specific', True) else None,
                **kwargs
            )
            
            # Convert Graphiti results to standardized format
            content = self._format_search_results(search_results)
            
            return QueryResult(
                content=content,
                sources=self._extract_sources(search_results),
                entities=self._extract_entities(search_results),
                relationships=self._extract_relationships(search_results),
                metadata={
                    "mode": mode,
                    "top_k": top_k,
                    "group_id": self.group_id,
                    "additional_params": kwargs
                },
                query_time=query_start,
                backend_type=BackendType.GRAPHITI
            )
            
        except Exception as e:
            self.logger.error(f"Error during Graphiti query: {e}")
            return QueryResult(
                content=f"Query failed: {str(e)}",
                metadata={"error": str(e), "mode": mode},
                query_time=query_start,
                backend_type=BackendType.GRAPHITI
            )
    
    def _format_search_results(self, results: Any) -> str:
        """Format Graphiti search results into readable content"""
        if not results:
            return "No results found."
        
        # This would need to be adapted based on Graphiti's actual result format
        if isinstance(results, list):
            formatted_results = []
            for i, result in enumerate(results[:10], 1):  # Limit to top 10
                if hasattr(result, 'episode_body'):
                    formatted_results.append(f"{i}. {result.episode_body}")
                elif isinstance(result, dict):
                    formatted_results.append(f"{i}. {result.get('content', str(result))}")
                else:
                    formatted_results.append(f"{i}. {str(result)}")
            return "\n\n".join(formatted_results)
        
        return str(results)
    
    def _extract_sources(self, results: Any) -> List[Dict[str, Any]]:
        """Extract source information from Graphiti results"""
        sources = []
        if isinstance(results, list):
            for result in results:
                if hasattr(result, 'uuid'):
                    sources.append({
                        "uuid": result.uuid,
                        "type": "episode",
                        "source": getattr(result, 'source_description', 'Unknown')
                    })
        return sources
    
    def _extract_entities(self, results: Any) -> List[Dict[str, Any]]:
        """Extract entity information from Graphiti results"""
        # This would need to be implemented based on Graphiti's result structure
        return []
    
    def _extract_relationships(self, results: Any) -> List[Dict[str, Any]]:
        """Extract relationship information from Graphiti results"""
        # This would need to be implemented based on Graphiti's result structure  
        return []
    
    async def get_entities(
        self,
        limit: int = 100,
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve entities from Graphiti's knowledge graph"""
        if not self._initialized:
            raise RuntimeError("Backend not initialized. Call initialize() first.")
        
        try:
            # Use Graphiti's entity retrieval methods
            # This would need to be adapted based on actual Graphiti API
            from graphiti_core.nodes import EntityNode
            
            entities = await EntityNode.get_by_group_ids(
                self.graphiti_client.driver,
                [self.group_id] if not filters or not filters.get('all_groups') else None
            )
            
            # Convert to standardized format
            result = []
            for entity in entities[offset:offset + limit]:
                result.append({
                    "uuid": entity.uuid,
                    "name": entity.name,
                    "summary": getattr(entity, 'summary', ''),
                    "group_id": entity.group_id,
                    "created_at": getattr(entity, 'created_at', None),
                })
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error retrieving entities: {e}")
            return []
    
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
            # Use Graphiti's relationship retrieval methods
            from graphiti_core.edges import EntityEdge
            
            edges = await EntityEdge.get_by_group_ids(
                self.graphiti_client.driver,
                [self.group_id] if not filters or not filters.get('all_groups') else None
            )
            
            # Convert to standardized format
            result = []
            for edge in edges[offset:offset + limit]:
                result.append({
                    "uuid": edge.uuid,
                    "name": edge.name,
                    "fact": getattr(edge, 'fact', ''),
                    "source_uuid": getattr(edge, 'source_uuid', None),
                    "target_uuid": getattr(edge, 'target_uuid', None),
                    "group_id": getattr(edge, 'group_id', None),
                    "created_at": getattr(edge, 'created_at', None),
                })
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error retrieving relationships: {e}")
            return []


class GraphitiLLMWrapper:
    """Wrapper to adapt external LLM functions to Graphiti's LLM client interface"""
    
    def __init__(self, llm_func: callable):
        self.llm_func = llm_func
    
    async def __call__(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Adapt the call to external LLM function"""
        try:
            # Convert messages to appropriate format for the external function
            # This would need to be adapted based on the specific LLM function interface
            prompt = "\n".join([msg.get("content", "") for msg in messages])
            result = await self.llm_func(prompt, **kwargs)
            return result
        except Exception as e:
            raise RuntimeError(f"LLM function call failed: {e}")