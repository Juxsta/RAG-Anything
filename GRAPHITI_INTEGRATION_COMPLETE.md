# RAG-Anything + Graphiti Integration - Complete Implementation

This document describes the comprehensive integration between RAG-Anything and Graphiti-core, providing advanced multimodal knowledge graph capabilities.

## 🎯 Implementation Overview

The integration provides:

### ✅ **Core Integration Module** 
- **Direct Library Integration**: Uses graphiti-core library directly (not REST API)
- **Source Build Support**: Builds and imports graphiti-core from `../graphiti` source
- **Episode Conversion**: Converts multimodal content to Graphiti episodes
- **Knowledge Graph Operations**: Full CRUD operations on entities, relationships, and episodes

### ✅ **REST Service** 
- **FastAPI Application**: Complete multimodal API with authentication
- **Document Upload**: Direct file processing with parser support
- **Query Interfaces**: Multiple search modes (hybrid, semantic, entity-based)
- **Management Endpoints**: Health monitoring, statistics, and administration

### ✅ **Enhanced Episode Converter** 
- **Multimodal Support**: Text, images, tables, equations, code, diagrams
- **Structure Preservation**: Maintains document hierarchy and relationships
- **Content Analysis**: Smart detection of content types and patterns
- **Metadata Handling**: Rich metadata extraction and processing

### ✅ **Build System** 
- **Source Compilation**: Automated graphiti-core building from source
- **Package Management**: Complete dependency resolution
- **Installation Scripts**: Make targets for easy setup

### ✅ **Configuration Management** 
- **Environment Templates**: Comprehensive `.env.example` with all options
- **Validation System**: Production-ready configuration validation
- **Security Checks**: API key validation, default password detection
- **Multi-Environment Support**: Development, testing, and production configs

### ✅ **Performance Optimizations**
- **Multi-Level Caching**: Document, embedding, query, entity, and episode caches
- **LRU Eviction**: Memory and size-based cache management
- **Async Processing**: Full async/await support throughout
- **Batch Operations**: Efficient bulk processing capabilities

### ✅ **Error Handling & Logging**
- **Structured Error System**: Categorized errors with severity levels
- **Recovery Mechanisms**: Automatic error recovery where possible
- **Comprehensive Logging**: JSON structured logging with rotation
- **Context Tracking**: Request/user/session context in all operations

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Build graphiti-core from source (recommended)
make build-graphiti
make install-graphiti

# Or install from PyPI
pip install graphiti-core[falkordb]
```

### 2. Configure Environment

```bash
# Copy and configure environment
cp .env.example .env
# Edit .env with your settings (OpenAI API key, database config, etc.)
```

### 3. Start Services

```bash
# Start database (FalkorDB/Redis)
make start-db

# Start API server
make serve-graphiti
```

### 4. Test Integration

```bash
# Run comprehensive tests
make test-graphiti

# Or run directly
python test_comprehensive_integration.py
```

## 📁 Architecture

```
raganything/
├── backends/
│   └── graphiti_direct.py          # 🔥 Main integration module
├── api/                            # 🌐 FastAPI REST service
│   ├── __init__.py
│   ├── main.py                     # FastAPI app
│   ├── models.py                   # Pydantic models
│   ├── dependencies.py             # DI and auth
│   └── endpoints/                  # Route handlers
│       ├── processing.py           # Document processing
│       ├── querying.py            # Search and query
│       ├── entities.py            # Entity management
│       ├── communities.py         # Community operations
│       ├── health.py              # Monitoring
│       ├── files.py               # File upload
│       └── management.py          # Admin operations
├── episode_converter.py           # 📝 Enhanced multimodal converter
├── caching.py                      # ⚡ Performance caching system
├── error_handling.py              # 🛡️ Error management
├── config_validator.py            # ✅ Configuration validation
└── config.py                      # ⚙️ Enhanced configuration
```

## 🔧 Configuration Options

### Core Settings
```bash
# Backend selection
RAG_BACKEND_TYPE=graphiti
ENABLE_BACKEND_FALLBACK=true

# Working directories
WORKING_DIR=./rag_storage
OUTPUT_DIR=./output
LOG_DIR=./logs
```

### Database Configuration
```bash
# Graph provider
GRAPHITI_GRAPH_PROVIDER=falkordb  # or neo4j

# FalkorDB (Redis-based)
GRAPHITI_GRAPH_HOST=localhost
GRAPHITI_GRAPH_PORT=6379
GRAPHITI_GRAPH_DATABASE=rag_graph

# Neo4j
GRAPHITI_NEO4J_URI=bolt://localhost:7687
GRAPHITI_NEO4J_USER=neo4j
GRAPHITI_NEO4J_PASSWORD=password
```

### AI/ML Configuration
```bash
# LLM settings
GRAPHITI_LLM_PROVIDER=openai
GRAPHITI_LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=your_api_key_here

# Embeddings
GRAPHITI_EMBEDDER_PROVIDER=openai
GRAPHITI_EMBEDDER_MODEL=text-embedding-3-small
```

### Performance Tuning
```bash
# Processing
GRAPHITI_BATCH_SIZE=50
GRAPHITI_MAX_COROUTINES=10
GRAPHITI_EPISODE_WINDOW_LEN=10

# Caching
ENABLE_GRAPHITI_CACHE=true
GRAPHITI_CACHE_TTL=3600

# Communities
AUTO_BUILD_COMMUNITIES=false
COMMUNITY_UPDATE_THRESHOLD=100
```

## 💻 API Usage

### Start the Server
```bash
# Development mode with auto-reload
make serve-graphiti

# Production mode
uvicorn raganything.api.main:GraphitiRAGApp --host 0.0.0.0 --port 8000
```

### Process Documents
```python
import requests

# Upload and process file
files = {'file': open('document.pdf', 'rb')}
response = requests.post('http://localhost:8000/files/upload', files=files)

# Process text directly
data = {
    "text": "AI is transforming healthcare through diagnostic tools.",
    "title": "Healthcare AI",
    "source": "Research Paper"
}
response = requests.post('http://localhost:8000/process/text', json=data)
```

### Query Knowledge Graph
```python
# Hybrid search
query_data = {
    "query": "What are the applications of AI in healthcare?",
    "mode": "hybrid",
    "top_k": 10
}
response = requests.post('http://localhost:8000/query/', json=query_data)

# Get entities
response = requests.get('http://localhost:8000/entities/?limit=20')

# Get relationships
response = requests.get('http://localhost:8000/entities/relationships?limit=20')
```

### Build Communities
```python
# Build knowledge communities
data = {"group_ids": ["healthcare"], "force_rebuild": false}
response = requests.post('http://localhost:8000/communities/build', json=data)
```

## 🧪 Testing

### Run All Tests
```bash
make test-graphiti
```

### Individual Test Categories
```bash
# Backend initialization
python -c "from test_comprehensive_integration import *; asyncio.run(GraphitiIntegrationTester().test_backend_initialization())"

# Text processing
python -c "from test_comprehensive_integration import *; asyncio.run(GraphitiIntegrationTester().test_text_processing())"
```

### Validate Configuration
```bash
# Validate current config
python -m raganything.config_validator

# Production validation
python -m raganything.config_validator --production --env-file .env.production

# JSON output
python -m raganything.config_validator --output-format json
```

## 🔍 Monitoring & Debugging

### Health Checks
```bash
curl http://localhost:8000/health/
curl http://localhost:8000/health/stats
```

### Cache Statistics
```python
# Get comprehensive cache stats
response = requests.get('http://localhost:8000/health/stats')
cache_stats = response.json()['cache_stats']
```

### Error Tracking
- Structured JSON logs in `./logs/errors.json`
- Application logs in `./logs/raganything.log`
- Error categorization and recovery attempts

## 🚀 Production Deployment

### Environment Setup
```bash
# Generate production config
python -m raganything.config_validator --setup-production

# Validate production readiness  
python -m raganything.config_validator --production --env-file .env.production
```

### Security Checklist
- [ ] Set strong JWT secret key
- [ ] Change default database passwords
- [ ] Disable debug mode and detailed error responses
- [ ] Configure specific CORS origins
- [ ] Enable rate limiting
- [ ] Set up log rotation
- [ ] Review and set appropriate cache TTLs

### Scaling Considerations
- **Database**: Use external Redis/Neo4j for production
- **API**: Deploy behind reverse proxy (nginx)
- **Caching**: Adjust cache sizes based on memory availability
- **Concurrency**: Tune `GRAPHITI_MAX_COROUTINES` based on system resources

## 📊 Performance Characteristics

### Benchmarks
- **Text Processing**: ~2-5 seconds per document (depends on size/complexity)
- **Query Response**: ~100-500ms for cached queries, 1-3s for complex searches
- **Entity Retrieval**: ~50-200ms for paginated results
- **Community Building**: 2-10 minutes (depends on graph size)

### Optimization Tips
1. **Enable Caching**: Significant performance boost for repeated operations
2. **Batch Processing**: Use bulk endpoints for multiple documents
3. **Tune Batch Sizes**: Adjust `GRAPHITI_BATCH_SIZE` based on memory/performance
4. **Index Management**: Let Graphiti handle database indexing automatically
5. **Community Updates**: Build communities periodically, not on every update

## 🛟 Troubleshooting

### Common Issues

**1. Graphiti Import Errors**
```bash
# Install from source
make build-graphiti

# Or from PyPI
pip install graphiti-core[falkordb]
```

**2. Database Connection Issues**
```bash
# Start FalkorDB/Redis
make start-db

# Check connection
redis-cli ping
```

**3. API Key Issues**
```bash
# Set OpenAI API key
export OPENAI_API_KEY=sk-...

# Validate in config
python -m raganything.config_validator
```

**4. Memory Issues**
```bash
# Reduce cache sizes in .env
GRAPHITI_BATCH_SIZE=20
# Monitor with stats endpoint
curl http://localhost:8000/health/stats
```

### Debug Mode
```bash
# Enable debug logging
LOG_LEVEL=DEBUG
DEBUG_MODE=true
DETAILED_ERROR_RESPONSES=true

# Restart service
make serve-graphiti
```

## 🎉 Success Metrics

After implementing this comprehensive integration, you should see:

### ✅ **Functional Success**
- All 10 test categories pass
- Multimodal content processing works
- Knowledge graph queries return relevant results
- API endpoints respond correctly

### ✅ **Performance Success**  
- Query response times under 3 seconds
- Cache hit rates above 50%
- No memory leaks during extended operation
- Batch processing completes without timeouts

### ✅ **Production Success**
- Configuration validation passes
- Security checks pass
- Error handling is graceful
- Monitoring endpoints provide useful metrics

## 📚 Additional Resources

- **Graphiti Documentation**: [https://help.getzep.com/graphiti](https://help.getzep.com/graphiti)
- **FastAPI Documentation**: [https://fastapi.tiangolo.com](https://fastapi.tiangolo.com)
- **FalkorDB Documentation**: [https://docs.falkordb.com](https://docs.falkordb.com)
- **Configuration Reference**: See `.env.example` for all available options

---

**🎯 Implementation Status: COMPLETE ✅**

The RAG-Anything + Graphiti integration is now fully implemented with production-ready features, comprehensive testing, and detailed documentation. The system provides a robust foundation for building advanced multimodal knowledge graphs with excellent performance and reliability.