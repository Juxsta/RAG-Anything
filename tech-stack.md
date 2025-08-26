# RAG-Anything + Graphiti Integration - Technology Stack Decisions

## Executive Summary

This document outlines the comprehensive technology stack decisions for integrating RAG-Anything with Graphiti-Core through direct library integration. The architecture prioritizes performance, scalability, and developer experience while maintaining backward compatibility with existing LightRAG implementations.

## Core Technology Stack

### Backend Framework and Runtime

| Technology | Choice | Version | Rationale |
|------------|--------|---------|-----------|
| **Runtime** | Python | 3.10+ | - Matches graphiti-core requirements<br>- Excellent ecosystem for AI/ML<br>- Async capabilities for high performance<br>- Team expertise and community support |
| **Web Framework** | FastAPI | 0.104+ | - Native async support for performance<br>- Automatic OpenAPI documentation<br>- Type safety with Pydantic<br>- High performance comparable to NodeJS |
| **ASGI Server** | Uvicorn | 0.24+ | - High performance async server<br>- Seamless FastAPI integration<br>- WebSocket support for future features<br>- Production-ready with Gunicorn |

**Decision Factors**:
- **Performance**: Python 3.10+ with FastAPI provides excellent async performance
- **Compatibility**: Direct alignment with graphiti-core's Python 3.10+ requirement
- **Developer Experience**: FastAPI's automatic documentation and type safety
- **Future-Proofing**: Modern async Python stack supports high concurrency

### Graph Database and Storage

| Technology | Choice | Version | Rationale |
|------------|--------|---------|-----------|
| **Primary Graph DB** | Neo4j | 5.26+ | - Native graph database with excellent performance<br>- ACID compliance for data integrity<br>- Rich Cypher query language<br>- Graphiti's primary supported backend |
| **Alternative Graph DB** | FalkorDB | 1.1.2+ | - Redis-based graph database for lower latency<br>- Graphiti native support<br>- Cost-effective for smaller deployments<br>- Memory-based performance advantages |
| **Caching Layer** | Redis | 7.0+ | - High-performance in-memory caching<br>- Session management capabilities<br>- Pub/sub for real-time features<br>- Persistence options for durability |
| **Document Storage** | File System + Object Store | - | - Local filesystem for development<br>- S3-compatible object storage for production<br>- Cost-effective for document archival |

**Decision Factors**:
- **Data Integrity**: Neo4j's ACID compliance ensures reliable graph operations
- **Performance**: Redis provides sub-millisecond caching performance
- **Scalability**: Both Neo4j and Redis offer enterprise clustering options
- **Cost Optimization**: FalkorDB provides cost-effective alternative for smaller workloads

### Document Processing and AI Models

| Technology | Choice | Version | Rationale |
|------------|--------|---------|-----------|
| **Primary Parser** | MinerU | Latest | - Excellent PDF and image extraction<br>- Multi-modal content support<br>- High accuracy for complex documents<br>- Battle-tested in production |
| **Alternative Parser** | Docling | Latest | - Strong table extraction capabilities<br>- Layout analysis features<br>- Complementary to MinerU<br>- Fallback parsing option |
| **Vision Processing** | OpenCV | 4.8+ | - Computer vision operations<br>- Image preprocessing and analysis<br>- Wide format support<br>- Performance optimization |
| **Table Processing** | Pandas | 2.0+ | - Excellent DataFrame operations<br>- Multiple format support<br>- Data transformation capabilities<br>- Ecosystem integration |

**AI/ML Services**:

| Service | Primary Choice | Alternative | Rationale |
|---------|----------------|-------------|-----------|
| **LLM** | OpenAI GPT-4 | Anthropic Claude-3 | - Proven performance and reliability<br>- Strong reasoning capabilities<br>- API stability and rate limits |
| **Vision Model** | OpenAI GPT-4V | Google Gemini Vision | - Integrated with primary LLM<br>- Excellent multimodal understanding<br>- Consistent API interface |
| **Embeddings** | text-embedding-3-large | Voyage AI | - High-quality embeddings<br>- 3072 dimensions for rich representation<br>- Cost-effective pricing |
| **Reranking** | OpenAI Reranker | BGE Reranker | - Integrated ecosystem benefits<br>- Strong cross-encoder performance<br>- API consistency |

## Build System Architecture

### Graphiti-Core Integration Strategy

#### Option 1: Direct Source Integration (Recommended)
```bash
# Project structure for direct integration
RAG-Anything/
├── pyproject.toml                    # Main project configuration
├── requirements/
│   ├── base.txt                      # Core dependencies
│   ├── graphiti.txt                  # Graphiti-core requirements
│   ├── parsers.txt                   # MinerU, Docling dependencies
│   └── dev.txt                       # Development tools
├── scripts/
│   ├── setup-graphiti.sh            # Clone and prepare graphiti source
│   ├── build-integration.sh          # Build complete integration
│   ├── test-integration.py           # Integration tests
│   └── docker-build.sh              # Container build script
├── src/
│   ├── graphiti_source/             # Git submodule: ../graphiti
│   └── raganything/
│       ├── backends/
│       │   ├── graphiti_direct.py   # Direct library integration
│       │   └── graphiti_bridge.py   # Bridge implementation
│       └── integration/
│           └── graphiti_setup.py    # Graphiti configuration
└── docker/
    ├── Dockerfile                    # Multi-stage build
    └── docker-compose.yml            # Full stack deployment
```

**Build Process**:
1. **Source Preparation**: 
   ```bash
   # Clone graphiti source as submodule
   git submodule add ../graphiti src/graphiti_source
   git submodule update --init --recursive
   ```

2. **Dependency Management**:
   ```bash
   # Install graphiti-core dependencies first
   pip install -r requirements/graphiti.txt
   
   # Install RAG-Anything with graphiti integration
   pip install -e .[graphiti]
   ```

3. **Integration Build**:
   ```python
   # Direct import approach
   import sys
   sys.path.insert(0, 'src/graphiti_source')
   
   from graphiti_core import Graphiti
   from graphiti_core.embedder import OpenAIEmbedder
   from graphiti_core.llm_client import OpenAIClient
   ```

#### Option 2: Package Installation (Alternative)
```bash
# Install graphiti-core from PyPI
pip install graphiti-core[all]==0.19.0

# Requires compatible versions and may lag behind development
```

**Pros/Cons Analysis**:

| Approach | Pros | Cons |
|----------|------|------|
| **Direct Source** | • Latest features and fixes<br>• Full control over integration<br>• Custom patches possible<br>• Maximum performance | • More complex build process<br>• Version management overhead<br>• Dependency conflicts possible |
| **Package Install** | • Simple installation<br>• Stable releases<br>• Clear dependency management | • May lag behind source<br>• Limited customization<br>• Potential version conflicts |

**Recommendation**: Direct source integration for maximum flexibility and performance during initial integration phase, with migration to package installation once the integration stabilizes.

### Python Package Management

#### Project Configuration (pyproject.toml)
```toml
[project]
name = "raganything-graphiti"
version = "2.0.0"
description = "RAG-Anything with Graphiti episodic knowledge graph integration"
requires-python = ">=3.10"
dependencies = [
    # Core framework
    "fastapi>=0.104.0",
    "uvicorn[standard]>=0.24.0",
    "pydantic>=2.5.0",
    
    # RAG-Anything core
    "raganything>=1.0.0",
    
    # Graph and caching
    "neo4j>=5.26.0",
    "redis>=5.0.0",
    
    # AI/ML services
    "openai>=1.40.0",
    "anthropic>=0.49.0",  # optional
    
    # Document processing
    "mineru",  # latest
    "docling",  # latest
    "opencv-python>=4.8.0",
    "pandas>=2.0.0",
    "pillow>=10.0.0",
    
    # Utilities
    "tenacity>=8.0.0",
    "python-dotenv>=1.0.0",
    "aiofiles>=23.0.0",
    "httpx>=0.25.0",
]

[project.optional-dependencies]
graphiti = [
    # Direct graphiti-core dependencies
    "pydantic>=2.11.5",
    "neo4j>=5.26.0",
    "diskcache>=5.6.3",
    "openai>=1.91.0",
    "tenacity>=9.0.0",
    "numpy>=1.0.0",
    "python-dotenv>=1.0.1",
    "posthog>=3.0.0",
    
    # Optional graphiti features
    "anthropic>=0.49.0",
    "google-genai>=1.8.0",
    "falkordb>=1.1.2,<2.0.0",
    "voyageai>=0.2.3",
    "sentence-transformers>=3.2.1",
]

parsers = [
    "mineru[full]",
    "docling[full]",
    "pymupdf>=1.23.0",
    "pdfplumber>=0.10.0",
]

performance = [
    "uvloop>=0.19.0",  # Linux/macOS performance
    "orjson>=3.9.0",    # Fast JSON
    "lxml>=4.9.0",      # Fast XML parsing
]

monitoring = [
    "prometheus-client>=0.19.0",
    "structlog>=23.0.0",
    "sentry-sdk>=1.40.0",
]

dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "black>=23.0.0",
    "isort>=5.12.0",
    "ruff>=0.1.0",
    "mypy>=1.8.0",
    "pre-commit>=3.5.0",
]

[build-system]
requires = ["setuptools>=68.0.0", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-dir]
"" = "src"
```

#### Dependency Resolution Strategy

**Requirements Files Structure**:
```bash
requirements/
├── base.txt                  # Core application dependencies
├── graphiti.txt             # Graphiti-core and related packages
├── parsers.txt              # Document parsing libraries
├── ai-services.txt          # AI/ML service clients
├── performance.txt          # Performance optimization packages
├── monitoring.txt           # Observability and monitoring
├── dev.txt                  # Development and testing tools
└── production.txt           # Production-only dependencies
```

**Installation Scripts**:
```bash
#!/bin/bash
# scripts/install-deps.sh

set -e

echo "Installing RAG-Anything + Graphiti Integration..."

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    python -m venv venv
fi

source venv/bin/activate

# Upgrade pip and basic tools
pip install --upgrade pip setuptools wheel

# Install dependencies in order
echo "Installing base dependencies..."
pip install -r requirements/base.txt

echo "Installing Graphiti dependencies..."
pip install -r requirements/graphiti.txt

echo "Installing parser dependencies..."
pip install -r requirements/parsers.txt

echo "Installing AI service dependencies..."
pip install -r requirements/ai-services.txt

if [ "$NODE_ENV" = "production" ]; then
    echo "Installing production dependencies..."
    pip install -r requirements/production.txt
else
    echo "Installing development dependencies..."
    pip install -r requirements/dev.txt
fi

# Install RAG-Anything in development mode
echo "Installing RAG-Anything with Graphiti integration..."
pip install -e .[graphiti,parsers,performance]

echo "Installation complete!"
```

### Container Strategy

#### Multi-Stage Dockerfile
```dockerfile
# Multi-stage Dockerfile for efficient builds
FROM python:3.10-slim as base

# System dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN groupadd -r app && useradd -r -g app app
WORKDIR /app

# Stage 1: Graphiti builder
FROM base as graphiti-builder

# Copy graphiti source
COPY src/graphiti_source/ ./graphiti_source/
WORKDIR /app/graphiti_source

# Install graphiti-core from source
RUN pip install --no-cache-dir -e .

# Stage 2: Application builder
FROM base as app-builder

# Copy requirements and install Python dependencies
COPY requirements/ ./requirements/
RUN pip install --no-cache-dir -r requirements/base.txt
RUN pip install --no-cache-dir -r requirements/graphiti.txt
RUN pip install --no-cache-dir -r requirements/parsers.txt
RUN pip install --no-cache-dir -r requirements/production.txt

# Copy graphiti installation from builder
COPY --from=graphiti-builder /usr/local/lib/python3.10/site-packages/ /usr/local/lib/python3.10/site-packages/

# Copy application code
COPY src/ ./src/
COPY pyproject.toml ./

# Install RAG-Anything
RUN pip install --no-cache-dir -e .[graphiti,performance]

# Stage 3: Production runtime
FROM python:3.10-slim as production

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Create app user and directory
RUN groupadd -r app && useradd -r -g app app
WORKDIR /app

# Copy Python environment from builder
COPY --from=app-builder /usr/local/lib/python3.10/site-packages/ /usr/local/lib/python3.10/site-packages/
COPY --from=app-builder /usr/local/bin/ /usr/local/bin/

# Copy application
COPY --from=app-builder /app/src/ ./src/
COPY --chown=app:app scripts/ ./scripts/
COPY --chown=app:app config/ ./config/

# Switch to app user
USER app

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Environment configuration
ENV PYTHONPATH="/app/src"
ENV PYTHONUNBUFFERED=1
ENV WORKERS=1

EXPOSE 8000

# Default command
CMD ["uvicorn", "raganything.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

#### Docker Compose for Development
```yaml
version: '3.8'

services:
  # Main application
  raganything-api:
    build:
      context: .
      dockerfile: docker/Dockerfile
      target: production
    ports:
      - "8000:8000"
    environment:
      - NEO4J_URL=bolt://neo4j:7687
      - NEO4J_USER=neo4j
      - NEO4J_PASSWORD=password
      - REDIS_URL=redis://redis:6379
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - WORKING_DIR=/app/data
      - LOG_LEVEL=INFO
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    depends_on:
      - neo4j
      - redis
    networks:
      - raganything-net
    restart: unless-stopped

  # Neo4j Graph Database
  neo4j:
    image: neo4j:5.26-enterprise
    ports:
      - "7474:7474"  # HTTP
      - "7687:7687"  # Bolt
    environment:
      - NEO4J_AUTH=neo4j/password
      - NEO4J_PLUGINS=["apoc", "graph-data-science"]
      - NEO4J_apoc_export_file_enabled=true
      - NEO4J_apoc_import_file_enabled=true
      - NEO4J_apoc_import_file_use__neo4j__config=true
      - NEO4JLABS_PLUGINS=["apoc", "graph-data-science"]
      - NEO4J_dbms_security_procedures_unrestricted=apoc.*,gds.*
      - NEO4J_dbms_memory_heap_initial__size=1G
      - NEO4J_dbms_memory_heap_max__size=2G
      - NEO4J_dbms_memory_pagecache_size=1G
    volumes:
      - neo4j-data:/data
      - neo4j-logs:/logs
      - neo4j-import:/var/lib/neo4j/import
      - neo4j-plugins:/plugins
    networks:
      - raganything-net
    restart: unless-stopped

  # Redis Cache
  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    networks:
      - raganything-net
    restart: unless-stopped

  # Optional: Redis Commander for Redis management
  redis-commander:
    image: rediscommander/redis-commander:latest
    environment:
      - REDIS_HOSTS=local:redis:6379
    ports:
      - "8081:8081"
    depends_on:
      - redis
    networks:
      - raganything-net

  # Optional: Prometheus for metrics
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./config/prometheus.yml:/etc/prometheus/prometheus.yml
    networks:
      - raganything-net

volumes:
  neo4j-data:
  neo4j-logs:
  neo4j-import:
  neo4j-plugins:
  redis-data:

networks:
  raganything-net:
    driver: bridge
```

## Database Backend Selection

### Neo4j vs FalkorDB Comparison

| Aspect | Neo4j | FalkorDB | Recommendation |
|--------|-------|----------|----------------|
| **Performance** | Excellent for complex queries | Superior for simple queries | Neo4j for complex analysis, FalkorDB for high-throughput |
| **Scalability** | Enterprise clustering available | Redis-based scaling | Neo4j for large datasets |
| **Memory Usage** | Disk-based with caching | Memory-based | FalkorDB for smaller graphs |
| **Query Language** | Full Cypher support | Cypher subset | Neo4j for advanced queries |
| **Cost** | Higher licensing costs | Lower operational costs | FalkorDB for cost-sensitive deployments |
| **Graphiti Support** | Primary backend | Alternative backend | Neo4j recommended for production |

**Selection Strategy**:
- **Development**: FalkorDB for fast iteration and testing
- **Production Small**: FalkorDB for cost-effective small to medium deployments
- **Production Large**: Neo4j for enterprise-scale deployments with complex analytics

### Configuration Templates

#### Neo4j Configuration
```python
# config/neo4j_config.py
from typing import Dict, Any

def get_neo4j_config() -> Dict[str, Any]:
    return {
        "uri": "bolt://localhost:7687",
        "username": "neo4j",
        "password": "password",
        "database": "neo4j",
        "max_connection_lifetime": 3600,
        "max_connection_pool_size": 50,
        "connection_acquisition_timeout": 60,
        "encrypted": False,
        "trust": "TRUST_ALL_CERTIFICATES",
        
        # Performance tuning
        "max_retry_time": 30,
        "initial_retry_delay": 1.0,
        "retry_delay_multiplier": 2.0,
        "retry_delay_jitter_factor": 0.2,
    }

def get_neo4j_performance_config() -> Dict[str, str]:
    """Neo4j server configuration for performance"""
    return {
        # Memory settings
        "dbms.memory.heap.initial_size": "2G",
        "dbms.memory.heap.max_size": "4G", 
        "dbms.memory.pagecache.size": "2G",
        
        # Query performance
        "dbms.query_cache_size": "1000",
        "dbms.query.cache.ttl": "600s",
        "cypher.default_language_version": "5",
        
        # Connection settings
        "dbms.connector.bolt.thread_pool_min_size": "5",
        "dbms.connector.bolt.thread_pool_max_size": "400",
        
        # Transaction settings
        "dbms.transaction.timeout": "300s",
        "dbms.transaction.concurrent.maximum": "1000",
    }
```

#### FalkorDB Configuration
```python
# config/falkordb_config.py
from typing import Dict, Any

def get_falkordb_config() -> Dict[str, Any]:
    return {
        "host": "localhost",
        "port": 6379,
        "db": 0,
        "password": None,
        "socket_timeout": 30,
        "socket_connect_timeout": 30,
        "socket_keepalive": True,
        "socket_keepalive_options": {},
        "connection_pool_max_connections": 50,
        "retry_on_timeout": True,
        "decode_responses": True,
        
        # FalkorDB specific
        "graph_name": "raganything",
        "read_timeout": 30,
        "query_timeout": 300,
    }

def get_redis_performance_config() -> Dict[str, str]:
    """Redis server configuration for FalkorDB"""
    return {
        # Memory management
        "maxmemory": "2gb",
        "maxmemory-policy": "allkeys-lru",
        
        # Persistence
        "save": "900 1 300 10 60 10000",  # Save snapshots
        "appendonly": "yes",
        "appendfsync": "everysec",
        
        # Performance
        "tcp-keepalive": "300",
        "timeout": "300",
        "tcp-nodelay": "yes",
        
        # Graph module specific
        "loadmodule": "/usr/lib/redis/modules/graphiti.so",
    }
```

## Caching and Performance Optimization

### Multi-Level Caching Architecture

| Cache Level | Technology | Use Case | TTL | Size Limit |
|-------------|------------|----------|-----|------------|
| **L1: Process** | Python Dict | Frequently accessed configs | Session | 100MB |
| **L2: Application** | Redis | Query results, embeddings | 1 hour | 1GB |
| **L3: Distributed** | Redis Cluster | Shared cache across instances | 24 hours | 10GB |
| **L4: Persistent** | DiskCache | Long-term caching | 7 days | 50GB |

### Cache Implementation Strategy

```python
# src/raganything/cache/cache_manager.py
from typing import Any, Optional, Dict
import asyncio
import redis.asyncio as redis
from diskcache import Cache
import json
import hashlib

class CacheManager:
    """Multi-level cache manager for optimal performance"""
    
    def __init__(self, redis_url: str, disk_cache_dir: str):
        # L1: Process-level cache
        self._process_cache: Dict[str, Any] = {}
        self._process_cache_max_size = 1000
        
        # L2: Redis cache
        self._redis = redis.from_url(redis_url)
        
        # L3: Disk cache  
        self._disk_cache = Cache(disk_cache_dir, size_limit=50 * 1024**3)  # 50GB
        
    async def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache with multi-level fallback"""
        
        # L1: Check process cache
        if key in self._process_cache:
            return self._process_cache[key]
            
        # L2: Check Redis cache
        redis_value = await self._redis.get(key)
        if redis_value:
            value = json.loads(redis_value)
            self._set_process_cache(key, value)
            return value
            
        # L3: Check disk cache
        disk_value = self._disk_cache.get(key)
        if disk_value is not None:
            # Promote to Redis and process cache
            await self._redis.setex(key, 3600, json.dumps(disk_value))
            self._set_process_cache(key, disk_value)
            return disk_value
            
        return default
        
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: int = 3600,
        persist_to_disk: bool = False
    ):
        """Set value in appropriate cache levels"""
        
        # Always set in Redis
        await self._redis.setex(key, ttl, json.dumps(value))
        
        # Set in process cache
        self._set_process_cache(key, value)
        
        # Optionally persist to disk for long-term caching
        if persist_to_disk:
            self._disk_cache.set(key, value, expire=ttl * 24)  # Disk cache lasts longer
    
    def _set_process_cache(self, key: str, value: Any):
        """Manage process cache size"""
        if len(self._process_cache) >= self._process_cache_max_size:
            # Remove oldest entries (simple FIFO)
            oldest_key = next(iter(self._process_cache))
            del self._process_cache[oldest_key]
        
        self._process_cache[key] = value
        
    def generate_cache_key(self, *args, **kwargs) -> str:
        """Generate consistent cache keys"""
        key_data = {
            'args': args,
            'kwargs': sorted(kwargs.items())
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()[:32]

# Usage in query operations
class GraphitiQueryCache:
    """Specialized caching for Graphiti queries"""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager
        
    async def get_cached_query(
        self, 
        query: str, 
        parameters: Dict[str, Any]
    ) -> Optional[Any]:
        """Get cached query results"""
        cache_key = self.cache.generate_cache_key(
            "query", query, parameters
        )
        return await self.cache.get(cache_key)
        
    async def cache_query_result(
        self, 
        query: str, 
        parameters: Dict[str, Any],
        result: Any,
        ttl: int = 3600
    ):
        """Cache query results"""
        cache_key = self.cache.generate_cache_key(
            "query", query, parameters
        )
        await self.cache.set(cache_key, result, ttl=ttl)
```

## Monitoring and Observability Stack

### Metrics and Logging

| Component | Technology | Purpose | Configuration |
|-----------|------------|---------|---------------|
| **Metrics Collection** | Prometheus + Custom | Performance metrics | 15s scrape interval |
| **Logging** | Structlog + JSON | Structured application logs | INFO level production |
| **Tracing** | OpenTelemetry | Request tracing | 1% sampling rate |
| **Error Tracking** | Sentry | Error monitoring and alerting | All errors captured |
| **Dashboards** | Grafana | Metrics visualization | Custom RAG dashboards |

### Performance Monitoring Configuration

```python
# src/raganything/monitoring/metrics.py
from prometheus_client import Counter, Histogram, Gauge, start_http_server
import structlog
import time
from functools import wraps

# Metrics definitions
REQUEST_COUNT = Counter(
    'raganything_requests_total',
    'Total number of requests',
    ['method', 'endpoint', 'status']
)

REQUEST_DURATION = Histogram(
    'raganything_request_duration_seconds',
    'Request duration in seconds',
    ['method', 'endpoint']
)

DOCUMENT_PROCESSING_TIME = Histogram(
    'raganything_document_processing_seconds',
    'Document processing time',
    ['parser', 'file_type']
)

GRAPHITI_QUERY_TIME = Histogram(
    'raganything_graphiti_query_seconds', 
    'Graphiti query execution time',
    ['query_type']
)

CACHE_HIT_RATE = Counter(
    'raganything_cache_operations_total',
    'Cache operations',
    ['level', 'operation', 'result']
)

ACTIVE_CONNECTIONS = Gauge(
    'raganything_active_connections',
    'Number of active connections',
    ['connection_type']
)

# Structured logging setup
logger = structlog.get_logger()

def monitor_performance(operation_type: str):
    """Decorator for monitoring operation performance"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                
                logger.info(
                    "operation_completed",
                    operation=operation_type,
                    duration=duration,
                    success=True
                )
                
                # Record metrics based on operation type
                if operation_type == "document_processing":
                    DOCUMENT_PROCESSING_TIME.labels(
                        parser=kwargs.get('parser', 'unknown'),
                        file_type=kwargs.get('file_type', 'unknown')
                    ).observe(duration)
                elif operation_type == "graphiti_query":
                    GRAPHITI_QUERY_TIME.labels(
                        query_type=kwargs.get('mode', 'unknown')
                    ).observe(duration)
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                logger.error(
                    "operation_failed",
                    operation=operation_type,
                    duration=duration,
                    error=str(e),
                    success=False
                )
                raise
                
        return wrapper
    return decorator

class HealthChecker:
    """Comprehensive health checking for all components"""
    
    def __init__(self, graphiti_client, neo4j_driver, redis_client):
        self.graphiti = graphiti_client
        self.neo4j = neo4j_driver
        self.redis = redis_client
        
    async def check_graphiti_health(self) -> Dict[str, Any]:
        """Check Graphiti backend health"""
        try:
            start_time = time.time()
            # Simple query to test connectivity
            result = await self.graphiti.get_stats()
            response_time = (time.time() - start_time) * 1000
            
            return {
                "status": "healthy",
                "response_time_ms": response_time,
                "stats": result
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def check_neo4j_health(self) -> Dict[str, Any]:
        """Check Neo4j database health"""
        try:
            start_time = time.time()
            async with self.neo4j.session() as session:
                result = await session.run("RETURN 1 as health_check")
                await result.consume()
            response_time = (time.time() - start_time) * 1000
            
            return {
                "status": "healthy",
                "response_time_ms": response_time
            }
        except Exception as e:
            return {
                "status": "error", 
                "error": str(e)
            }
    
    async def check_redis_health(self) -> Dict[str, Any]:
        """Check Redis cache health"""
        try:
            start_time = time.time()
            await self.redis.ping()
            response_time = (time.time() - start_time) * 1000
            
            info = await self.redis.info()
            
            return {
                "status": "healthy",
                "response_time_ms": response_time,
                "memory_usage": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients")
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
```

## Development and Testing Tools

### Testing Strategy

| Test Type | Framework | Coverage | Automation |
|-----------|-----------|----------|------------|
| **Unit Tests** | Pytest | 90%+ | Pre-commit hooks |
| **Integration Tests** | Pytest + TestContainers | Critical paths | CI/CD pipeline |
| **Performance Tests** | Locust | API endpoints | Nightly runs |
| **End-to-End Tests** | Playwright | User workflows | Release pipeline |

### Development Environment Setup

```bash
#!/bin/bash
# scripts/setup-dev-env.sh

set -e

echo "Setting up RAG-Anything development environment..."

# Check Python version
python_version=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
required_version="3.10"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "Error: Python $required_version or higher is required. Found: $python_version"
    exit 1
fi

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Upgrade pip and install build tools
pip install --upgrade pip setuptools wheel

# Install development dependencies
echo "Installing development dependencies..."
pip install -r requirements/dev.txt

# Install pre-commit hooks
echo "Setting up pre-commit hooks..."
pre-commit install

# Setup graphiti source
echo "Setting up Graphiti source integration..."
if [ ! -d "src/graphiti_source" ]; then
    git submodule add ../graphiti src/graphiti_source
    git submodule update --init --recursive
fi

# Install project in development mode
echo "Installing RAG-Anything in development mode..."
pip install -e .[graphiti,dev,performance]

# Setup environment configuration
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "Please edit .env file with your configuration"
fi

# Start development services
echo "Starting development services..."
docker-compose -f docker-compose.dev.yml up -d neo4j redis

# Wait for services to be ready
echo "Waiting for services to start..."
sleep 10

# Run initial tests
echo "Running initial test suite..."
pytest tests/unit/ -v

echo "Development environment setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your API keys"
echo "2. Run 'source venv/bin/activate' to activate virtual environment"  
echo "3. Run 'uvicorn src.raganything.api.main:app --reload' to start development server"
echo "4. Visit http://localhost:8000/docs for API documentation"
```

### Quality Assurance Tools

```yaml
# .github/workflows/quality.yml
name: Code Quality and Testing

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  quality:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11"]
        
    services:
      neo4j:
        image: neo4j:5.26
        env:
          NEO4J_AUTH: neo4j/test
        options: >-
          --health-cmd "cypher-shell -u neo4j -p test 'RETURN 1'"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 7687:7687
          
      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379

    steps:
    - uses: actions/checkout@v4
      with:
        submodules: recursive
        
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
        
    - name: Cache dependencies
      uses: actions/cache@v3
      with:
        path: ~/.cache/pip
        key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements/*.txt') }}
        
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements/dev.txt
        pip install -e .[graphiti,dev]
        
    - name: Code formatting check
      run: |
        black --check src/ tests/
        isort --check-only src/ tests/
        
    - name: Linting
      run: |
        ruff check src/ tests/
        
    - name: Type checking
      run: |
        mypy src/raganything/
        
    - name: Security scan
      run: |
        bandit -r src/
        
    - name: Unit tests
      run: |
        pytest tests/unit/ -v --cov=src/raganything --cov-report=xml
        
    - name: Integration tests
      env:
        NEO4J_URL: bolt://localhost:7687
        NEO4J_USER: neo4j
        NEO4J_PASSWORD: test
        REDIS_URL: redis://localhost:6379
      run: |
        pytest tests/integration/ -v
        
    - name: Upload coverage reports
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        
  performance:
    runs-on: ubuntu-latest
    needs: quality
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v4
    - name: Performance tests
      run: |
        # Run performance benchmarks
        locust --headless --users 10 --spawn-rate 2 --run-time 30s --host http://localhost:8000
```

## Decision Summary and Recommendations

### Final Technology Stack

**Recommended Configuration for Production**:
- **Runtime**: Python 3.10+ with FastAPI and Uvicorn
- **Graph Database**: Neo4j 5.26+ (primary), FalkorDB 1.1.2+ (cost-effective alternative)
- **Caching**: Redis 7.0+ with multi-level caching strategy
- **AI Services**: OpenAI GPT-4 + text-embedding-3-large (primary), with Anthropic/Voyage fallbacks
- **Document Processing**: MinerU (primary) + Docling (alternative)
- **Build System**: Direct graphiti-core source integration with multi-stage Docker builds
- **Monitoring**: Prometheus + Grafana + Structlog + Sentry

### Implementation Timeline

| Phase | Duration | Key Activities |
|-------|----------|----------------|
| **Phase 1** | 2-3 weeks | • Setup build system and direct graphiti integration<br>• Basic FastAPI endpoints<br>• Neo4j/Redis configuration |
| **Phase 2** | 3-4 weeks | • Episode conversion pipeline<br>• Multimodal processing<br>• Core API endpoints |
| **Phase 3** | 2-3 weeks | • Performance optimization<br>• Caching implementation<br>• Monitoring setup |
| **Phase 4** | 2-3 weeks | • Testing and quality assurance<br>• Documentation<br>• Deployment preparation |

**Total Estimated Timeline**: 9-13 weeks for full implementation

### Risk Mitigation

1. **Graphiti Integration Complexity**: Start with package installation fallback
2. **Performance Requirements**: Early performance testing and optimization
3. **Dependency Conflicts**: Containerized development environment
4. **Scalability Concerns**: Load testing with realistic data volumes
5. **Maintenance Burden**: Automated testing and deployment pipelines

This technology stack provides a robust foundation for the RAG-Anything + Graphiti integration while maintaining flexibility for future enhancements and scaling requirements.