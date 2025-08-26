"""
Configuration classes for RAGAnything

Contains configuration dataclasses with environment variable support
"""

from dataclasses import dataclass, field
from typing import List, Optional
from lightrag.utils import get_env_value


@dataclass
class RAGAnythingConfig:
    """Configuration class for RAGAnything with environment variable support"""

    # Directory Configuration
    # ---
    working_dir: str = field(default=get_env_value("WORKING_DIR", "./rag_storage", str))
    """Directory where RAG storage and cache files are stored."""

    # Parser Configuration
    # ---
    parse_method: str = field(default=get_env_value("PARSE_METHOD", "auto", str))
    """Default parsing method for document parsing: 'auto', 'ocr', or 'txt'."""

    parser_output_dir: str = field(default=get_env_value("OUTPUT_DIR", "./output", str))
    """Default output directory for parsed content."""

    parser: str = field(default=get_env_value("PARSER", "mineru", str))
    """Parser selection: 'mineru' or 'docling'."""

    display_content_stats: bool = field(
        default=get_env_value("DISPLAY_CONTENT_STATS", True, bool)
    )
    """Whether to display content statistics during parsing."""

    # Multimodal Processing Configuration
    # ---
    enable_image_processing: bool = field(
        default=get_env_value("ENABLE_IMAGE_PROCESSING", True, bool)
    )
    """Enable image content processing."""

    enable_table_processing: bool = field(
        default=get_env_value("ENABLE_TABLE_PROCESSING", True, bool)
    )
    """Enable table content processing."""

    enable_equation_processing: bool = field(
        default=get_env_value("ENABLE_EQUATION_PROCESSING", True, bool)
    )
    """Enable equation content processing."""

    # Batch Processing Configuration
    # ---
    max_concurrent_files: int = field(
        default=get_env_value("MAX_CONCURRENT_FILES", 1, int)
    )
    """Maximum number of files to process concurrently."""

    supported_file_extensions: List[str] = field(
        default_factory=lambda: get_env_value(
            "SUPPORTED_FILE_EXTENSIONS",
            ".pdf,.jpg,.jpeg,.png,.bmp,.tiff,.tif,.gif,.webp,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.txt,.md",
            str,
        ).split(",")
    )
    """List of supported file extensions for batch processing."""

    recursive_folder_processing: bool = field(
        default=get_env_value("RECURSIVE_FOLDER_PROCESSING", True, bool)
    )
    """Whether to recursively process subfolders in batch mode."""

    # Context Extraction Configuration
    # ---
    context_window: int = field(default=get_env_value("CONTEXT_WINDOW", 1, int))
    """Number of pages/chunks to include before and after current item for context."""

    context_mode: str = field(default=get_env_value("CONTEXT_MODE", "page", str))
    """Context extraction mode: 'page' for page-based, 'chunk' for chunk-based."""

    max_context_tokens: int = field(
        default=get_env_value("MAX_CONTEXT_TOKENS", 2000, int)
    )
    """Maximum number of tokens in extracted context."""

    include_headers: bool = field(default=get_env_value("INCLUDE_HEADERS", True, bool))
    """Whether to include document headers and titles in context."""

    include_captions: bool = field(
        default=get_env_value("INCLUDE_CAPTIONS", True, bool)
    )
    """Whether to include image/table captions in context."""

    context_filter_content_types: List[str] = field(
        default_factory=lambda: get_env_value(
            "CONTEXT_FILTER_CONTENT_TYPES", "text", str
        ).split(",")
    )
    """Content types to include in context extraction (e.g., 'text', 'image', 'table')."""

    content_format: str = field(default=get_env_value("CONTENT_FORMAT", "minerU", str))
    """Default content format for context extraction when processing documents."""

    # Backend Selection Configuration
    # ---
    backend_type: str = field(default=get_env_value("RAG_BACKEND_TYPE", "lightrag", str))
    """Backend type selection: 'lightrag' or 'graphiti'."""

    enable_backend_fallback: bool = field(
        default=get_env_value("ENABLE_BACKEND_FALLBACK", True, bool)
    )
    """Enable fallback to LightRAG if Graphiti backend fails."""

    # Graphiti-specific Configuration
    # ---
    graphiti_group_id: str = field(default=get_env_value("GRAPHITI_GROUP_ID", "default", str))
    """Default group ID for Graphiti episodes."""

    # Database Configuration
    graphiti_graph_provider: str = field(
        default=get_env_value("GRAPHITI_GRAPH_PROVIDER", "falkordb", str)
    )
    """Graph provider for Graphiti: 'falkordb' or 'neo4j'."""

    # FalkorDB Configuration
    graphiti_graph_host: str = field(
        default=get_env_value("GRAPHITI_GRAPH_HOST", "localhost", str)
    )
    """Host for the graph database."""

    graphiti_graph_port: int = field(
        default=get_env_value("GRAPHITI_GRAPH_PORT", 6379, int)
    )
    """Port for the graph database."""

    graphiti_graph_database: str = field(
        default=get_env_value("GRAPHITI_GRAPH_DATABASE", "rag_graph", str)
    )
    """Database name for the graph."""

    graphiti_graph_password: Optional[str] = field(
        default=get_env_value("GRAPHITI_GRAPH_PASSWORD", None, str)
    )
    """Password for the graph database (optional)."""

    # Neo4j Configuration
    graphiti_neo4j_uri: str = field(
        default=get_env_value("GRAPHITI_NEO4J_URI", "bolt://localhost:7687", str)
    )
    """Neo4j URI for graph database connection."""

    graphiti_neo4j_user: str = field(
        default=get_env_value("GRAPHITI_NEO4J_USER", "neo4j", str)
    )
    """Neo4j username."""

    graphiti_neo4j_password: str = field(
        default=get_env_value("GRAPHITI_NEO4J_PASSWORD", "password", str)
    )
    """Neo4j password."""

    # LLM Configuration for Graphiti
    graphiti_llm_provider: str = field(
        default=get_env_value("GRAPHITI_LLM_PROVIDER", "openai", str)
    )
    """LLM provider for Graphiti: 'openai', 'anthropic', or 'custom'."""

    graphiti_llm_model: str = field(
        default=get_env_value("GRAPHITI_LLM_MODEL", "gpt-4o-mini", str)
    )
    """LLM model name for Graphiti operations."""

    graphiti_llm_api_key: Optional[str] = field(
        default=get_env_value("GRAPHITI_LLM_API_KEY", None, str)
    )
    """API key for LLM provider (falls back to OPENAI_API_KEY if not set)."""

    graphiti_llm_base_url: Optional[str] = field(
        default=get_env_value("GRAPHITI_LLM_BASE_URL", None, str)
    )
    """Base URL for LLM provider (for custom endpoints)."""

    # Embedder Configuration for Graphiti
    graphiti_embedder_provider: str = field(
        default=get_env_value("GRAPHITI_EMBEDDER_PROVIDER", "openai", str)
    )
    """Embedder provider for Graphiti."""

    graphiti_embedder_model: str = field(
        default=get_env_value("GRAPHITI_EMBEDDER_MODEL", "text-embedding-3-small", str)
    )
    """Embedder model for generating embeddings."""

    graphiti_embedder_api_key: Optional[str] = field(
        default=get_env_value("GRAPHITI_EMBEDDER_API_KEY", None, str)
    )
    """API key for embedder provider."""

    # Episode Processing Configuration
    preserve_document_structure: bool = field(
        default=get_env_value("PRESERVE_DOCUMENT_STRUCTURE", True, bool)
    )
    """Whether to preserve document structure in episodes."""

    store_raw_episode_content: bool = field(
        default=get_env_value("STORE_RAW_EPISODE_CONTENT", True, bool)
    )
    """Whether to store raw episode content in the graph database."""

    # Performance Configuration
    graphiti_max_coroutines: Optional[int] = field(
        default=get_env_value("GRAPHITI_MAX_COROUTINES", None, int)
    )
    """Maximum number of concurrent operations for Graphiti."""

    graphiti_batch_size: int = field(
        default=get_env_value("GRAPHITI_BATCH_SIZE", 50, int)
    )
    """Batch size for processing episodes."""

    graphiti_episode_window_len: int = field(
        default=get_env_value("GRAPHITI_EPISODE_WINDOW_LEN", 10, int)
    )
    """Number of previous episodes to consider for context."""

    # Caching Configuration
    enable_graphiti_cache: bool = field(
        default=get_env_value("ENABLE_GRAPHITI_CACHE", True, bool)
    )
    """Enable caching for Graphiti operations."""

    graphiti_cache_ttl: int = field(
        default=get_env_value("GRAPHITI_CACHE_TTL", 3600, int)
    )
    """Cache TTL in seconds for Graphiti operations."""

    # Community Building Configuration
    auto_build_communities: bool = field(
        default=get_env_value("AUTO_BUILD_COMMUNITIES", False, bool)
    )
    """Whether to automatically build communities."""

    community_update_threshold: int = field(
        default=get_env_value("COMMUNITY_UPDATE_THRESHOLD", 100, int)
    )
    """Number of episodes to process before updating communities."""

    # Model Function Configuration (for custom integrations)
    llm_model_func: Optional[callable] = field(default=None)
    """Custom LLM model function for integration."""

    embedding_func: Optional[callable] = field(default=None)
    """Custom embedding function for integration."""

    vision_model_func: Optional[callable] = field(default=None)
    """Custom vision model function for multimodal processing."""

    def __post_init__(self):
        """Post-initialization setup for backward compatibility"""
        # Support legacy environment variable names for backward compatibility
        legacy_parse_method = get_env_value("MINERU_PARSE_METHOD", None, str)
        if legacy_parse_method and not get_env_value("PARSE_METHOD", None, str):
            self.parse_method = legacy_parse_method
            import warnings

            warnings.warn(
                "MINERU_PARSE_METHOD is deprecated. Use PARSE_METHOD instead.",
                DeprecationWarning,
                stacklevel=2,
            )

    @property
    def mineru_parse_method(self) -> str:
        """
        Backward compatibility property for old code.

        .. deprecated::
           Use `parse_method` instead. This property will be removed in a future version.
        """
        import warnings

        warnings.warn(
            "mineru_parse_method is deprecated. Use parse_method instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.parse_method

    @mineru_parse_method.setter
    def mineru_parse_method(self, value: str):
        """Setter for backward compatibility"""
        import warnings

        warnings.warn(
            "mineru_parse_method is deprecated. Use parse_method instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.parse_method = value

    def get_graphiti_config(self) -> dict:
        """Get comprehensive Graphiti configuration dictionary"""
        # Determine the API key to use - prioritize graphiti-specific, fall back to OPENAI_API_KEY
        import os
        llm_api_key = self.graphiti_llm_api_key or os.getenv('OPENAI_API_KEY')
        embedder_api_key = self.graphiti_embedder_api_key or os.getenv('OPENAI_API_KEY')
        
        return {
            # Database configuration
            'graph_provider': self.graphiti_graph_provider,
            'falkordb_host': self.graphiti_graph_host,
            'falkordb_port': self.graphiti_graph_port,
            'falkordb_database': self.graphiti_graph_database,
            'falkordb_password': self.graphiti_graph_password,
            'neo4j_uri': self.graphiti_neo4j_uri,
            'neo4j_user': self.graphiti_neo4j_user,
            'neo4j_password': self.graphiti_neo4j_password,
            
            # LLM configuration
            'llm_provider': self.graphiti_llm_provider,
            'llm_model': self.graphiti_llm_model,
            'llm_api_key': llm_api_key,
            'llm_base_url': self.graphiti_llm_base_url,
            
            # Embedder configuration
            'embedder_provider': self.graphiti_embedder_provider,
            'embedder_model': self.graphiti_embedder_model,
            'embedder_api_key': embedder_api_key,
            
            # Episode processing configuration
            'default_group_id': self.graphiti_group_id,
            'preserve_document_structure': self.preserve_document_structure,
            'store_raw_episode_content': self.store_raw_episode_content,
            
            # Performance configuration
            'max_coroutines': self.graphiti_max_coroutines,
            'batch_size': self.graphiti_batch_size,
            'episode_window_len': self.graphiti_episode_window_len,
            
            # Caching configuration
            'enable_cache': self.enable_graphiti_cache,
            'cache_ttl': self.graphiti_cache_ttl,
            
            # Community configuration
            'auto_build_communities': self.auto_build_communities,
            'community_update_threshold': self.community_update_threshold,
        }

    def get_backend_config_kwargs(self) -> dict:
        """Get backend configuration kwargs for GraphitiDirectBackend"""
        return {
            'graphiti_config': self.get_graphiti_config()
        }
