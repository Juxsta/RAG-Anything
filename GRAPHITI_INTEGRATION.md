# RAG-Anything + Graphiti Integration

This document describes the integration between RAG-Anything's powerful multimodal document processing capabilities and Graphiti's episodic knowledge graph system.

## Overview

The integration provides:

- **Backend Abstraction Layer**: Unified interface supporting both LightRAG and Graphiti backends
- **Multimodal Episode Conversion**: Transform parsed documents into structured episodes for Graphiti
- **Seamless Backend Switching**: Switch between LightRAG and Graphiti with fallback support
- **FastAPI Integration**: REST API endpoints for document processing and querying
- **Comprehensive Service Layer**: High-level operations with batch processing and error handling

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    RAG-Anything Core                            │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   MinerU/       │  │   Multimodal    │  │   Enhanced      │ │
│  │   Docling       │  │   Processors    │  │   Markdown      │ │
│  │   Parser        │  │                 │  │   Support       │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                GraphitiRAGAnything Integration                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   Episode       │  │   Backend       │  │   Configuration │ │
│  │   Converter     │  │   Abstraction   │  │   Management    │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────┐                           ┌─────────────────┐
│   LightRAG      │◄─────────────┬─────────────►│   Graphiti      │
│   Backend       │              │              │   Backend       │
│   (Adapter)     │              │              │   (Bridge)      │
└─────────────────┘              │              └─────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Service Layer                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   REST API      │  │   Batch         │  │   Knowledge     │ │
│  │   Endpoints     │  │   Processing    │  │   Graph Mgmt    │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. Backend Abstraction Layer

Located in `raganything/backends/`:

- **`base.py`**: Abstract base classes and interfaces
- **`lightrag_adapter.py`**: Adapter for LightRAG compatibility
- **`graphiti_bridge.py`**: Bridge to Graphiti's episodic system

```python
from raganything import GraphitiRAGAnything, BackendType

# Use with LightRAG backend
config.backend_type = BackendType.LIGHTRAG

# Use with Graphiti backend  
config.backend_type = BackendType.GRAPHITI
```

### 2. Episode Converter

Located in `raganything/episode_converter.py`:

Converts multimodal content into structured episodes:

```python
from raganything import EpisodeConverter

converter = EpisodeConverter(
    default_group_id="my_documents",
    preserve_document_structure=True
)

episodes = converter.convert_document(parsed_content, metadata)
```

### 3. GraphitiRAGAnything Integration Class

Main integration class in `raganything/graphiti_integration.py`:

```python
from raganything import GraphitiRAGAnything, GraphitiRAGAnythingConfig

config = GraphitiRAGAnythingConfig(
    backend_type=BackendType.GRAPHITI,
    enable_backend_fallback=True,
    default_group_id="my_group",
    graphiti_config={
        "graph_config": {
            "provider": "falkordb",
            "host": "localhost",
            "port": 6379,
            "database": "rag_graph"
        }
    }
)

rag = GraphitiRAGAnything(
    config=config,
    llm_model_func=my_llm_func,
    embedding_func=my_embedding_func
)

await rag.initialize()
```

### 4. FastAPI Integration

Located in `python-api/app/integration/` and `python-api/app/services/`:

- **`graphiti_integrator.py`**: REST API integration layer
- **`graphiti_rag_service.py`**: High-level service operations

## Usage Examples

### Basic Document Processing

```python
import asyncio
from raganything import GraphitiRAGAnything, GraphitiRAGAnythingConfig, BackendType

async def process_documents():
    # Configure for Graphiti with fallback
    config = GraphitiRAGAnythingConfig(
        working_dir="./my_rag_storage",
        backend_type=BackendType.GRAPHITI,
        enable_backend_fallback=True,
        default_group_id="research_papers"
    )
    
    # Create instance with your model functions
    rag = GraphitiRAGAnything(
        config=config,
        llm_model_func=your_llm_function,
        embedding_func=your_embedding_function,
        vision_model_func=your_vision_function
    )
    
    try:
        # Initialize
        await rag.initialize()
        
        # Process a document
        result = await rag.process_document(
            "research_paper.pdf",
            metadata={"category": "ai_research", "year": 2024}
        )
        
        print(f"Processing result: {result.success}")
        print(f"Entities created: {result.inserted_entities}")
        
        # Query the knowledge graph
        response = await rag.query(
            "What are the main findings about neural networks?",
            mode="hybrid",
            top_k=10
        )
        
        print(f"Query response: {response.content}")
        
    finally:
        await rag.finalize()

# Run the example
asyncio.run(process_documents())
```

### FastAPI Server

```python
from fastapi import FastAPI, UploadFile, File
from app.services.graphiti_rag_service import GraphitiRAGService

app = FastAPI()
service = GraphitiRAGService()

@app.on_event("startup")
async def startup():
    await service.initialize()

@app.post("/process/file")
async def process_file(file: UploadFile = File(...)):
    result = await service.process_document_file(
        file=file,
        group_id="uploaded_docs"
    )
    return result

@app.post("/query")
async def query(query: str, mode: str = "hybrid"):
    from app.models.queries import QueryRequest
    
    request = QueryRequest(query=query, mode=mode)
    response = await service.execute_query(request)
    return response
```

### Backend Switching

```python
# Start with Graphiti, fallback to LightRAG if needed
config = GraphitiRAGAnythingConfig(
    backend_type=BackendType.GRAPHITI,
    enable_backend_fallback=True
)

rag = GraphitiRAGAnything(config=config, ...)
await rag.initialize()

# Check which backend is actually being used
print(f"Using backend: {rag.backend.backend_type.value}")

# Switch to LightRAG explicitly
success = await rag.switch_backend(BackendType.LIGHTRAG)
if success:
    print("Switched to LightRAG")
```

## Configuration

### Environment Variables

```bash
# Backend selection
export RAG_BACKEND_TYPE=graphiti  # or "lightrag"
export ENABLE_BACKEND_FALLBACK=true

# Graphiti configuration
export GRAPHITI_GROUP_ID=default
export GRAPHITI_GRAPH_PROVIDER=falkordb  # or "neo4j"
export GRAPHITI_GRAPH_HOST=localhost
export GRAPHITI_GRAPH_PORT=6379
export GRAPHITI_GRAPH_DATABASE=rag_graph
export GRAPHITI_GRAPH_PASSWORD=your_password

# Existing RAG-Anything configuration
export WORKING_DIR=./rag_storage
export PARSER=mineru  # or "docling"
export PARSE_METHOD=auto
```

### Programmatic Configuration

```python
config = GraphitiRAGAnythingConfig(
    # Core settings
    working_dir="./custom_storage",
    backend_type=BackendType.GRAPHITI,
    enable_backend_fallback=True,
    
    # Episode settings
    default_group_id="my_documents",
    preserve_document_structure=True,
    
    # Parser settings
    parser="docling",
    parse_method="auto",
    
    # Graphiti-specific settings
    graphiti_config={
        "graph_config": {
            "provider": "neo4j",
            "uri": "bolt://localhost:7687",
            "user": "neo4j",
            "password": "password"
        },
        "llm_config": {
            "model": "gpt-4",
            "api_key": "your-api-key"
        },
        "group_id": "my_documents"
    }
)
```

## API Endpoints

When using the FastAPI integration:

### Document Processing
- `POST /process/text` - Process raw text content
- `POST /process/file` - Process uploaded files
- `POST /process/batch` - Batch process multiple files

### Querying
- `POST /query` - Query the knowledge graph
- `GET /entities` - Retrieve entities
- `GET /relationships` - Retrieve relationships

### Management
- `GET /health` - Health check
- `GET /stats` - Get statistics
- `POST /backend/switch` - Switch backends
- `GET /backend/status` - Get backend status

## Error Handling and Fallbacks

The integration includes comprehensive error handling:

1. **Backend Initialization Failures**: Automatic fallback from Graphiti to LightRAG
2. **Processing Errors**: Graceful handling with detailed error messages
3. **Connection Issues**: Retry logic and failover mechanisms
4. **Resource Cleanup**: Proper finalization of resources

```python
try:
    await rag.initialize()
except Exception as e:
    print(f"Initialization failed: {e}")
    # The system automatically falls back to LightRAG if enabled
```

## Performance Considerations

- **Concurrent Processing**: Configurable limits for batch operations
- **Episode Batching**: Efficient bulk episode insertion
- **Connection Pooling**: Reuse of database connections
- **Caching**: Parse cache and embedding cache support

## Dependencies

### Required
- `raganything` (core library)
- `lightrag` (for LightRAG backend)
- `asyncio` (async operations)

### Optional (for Graphiti backend)
- `graphiti-core` (Graphiti integration)
- `falkordb` or `neo4j` (graph database)

### For FastAPI Integration
- `fastapi`
- `uvicorn`
- `python-multipart`

## Testing

Run the integration examples:

```bash
# Test the core integration
python examples/graphiti_integration_example.py

# Test the FastAPI integration
python examples/fastapi_graphiti_example.py
```

## Troubleshooting

### Common Issues

1. **Graphiti Not Available**: The system automatically falls back to LightRAG
2. **Database Connection Issues**: Check graph database configuration
3. **Model Function Errors**: Ensure LLM and embedding functions are properly configured
4. **Memory Issues**: Adjust batch sizes and concurrent processing limits

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Health Checks

Use the health check endpoint to diagnose issues:

```python
health = await rag.health_check()
print(health)
```

## Future Enhancements

- Additional graph database backends
- Enhanced episode type detection
- Improved semantic tagging
- Real-time synchronization between backends
- Advanced community detection features
- GraphQL API support

## Contributing

The integration follows the existing RAG-Anything patterns and conventions. When contributing:

1. Follow the established architecture patterns
2. Include comprehensive error handling
3. Add appropriate type hints and documentation
4. Test with both LightRAG and Graphiti backends
5. Maintain backward compatibility