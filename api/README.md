# RAG-Anything API Server

A production-ready Fastify-based REST API server that exposes [RAG-Anything](https://github.com/HKUDS/RAG-Anything)'s multimodal document processing and retrieval capabilities to non-Python clients.

## Features

- **Multimodal Document Processing**: Upload and process PDF, Office documents, and images with advanced content extraction
- **Intelligent Query System**: Support for text and multimodal queries with various retrieval modes
- **Real-time Processing Updates**: WebSocket and Server-Sent Events for live progress tracking  
- **Secure Authentication**: JWT tokens and API key authentication with role-based access control
- **High Performance**: Built with Fastify for maximum throughput and low latency
- **Production Ready**: Comprehensive logging, monitoring, error handling, and rate limiting
- **Developer Friendly**: OpenAPI documentation, TypeScript support, and Docker containerization

## Architecture

The API server acts as a bridge between Node.js/TypeScript applications and the Python-based RAG-Anything system:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Client Apps   │───▶│  Fastify API    │───▶│  RAG-Anything   │
│  (JS/TS/etc.)   │    │     Server      │    │   (Python)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │                        │
                       ┌─────────────────┐    ┌─────────────────┐
                       │  PostgreSQL     │    │    LightRAG     │
                       │   Database      │    │    Storage      │
                       └─────────────────┘    └─────────────────┘
```

## Quick Start

### Prerequisites

- Node.js 20+
- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Docker & Docker Compose (optional)

### Development Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/HKUDS/RAG-Anything.git
   cd RAG-Anything/api
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

3. **Set up environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Start services with Docker Compose**:
   ```bash
   docker-compose -f docker-compose.dev.yml up -d postgres redis
   ```

5. **Start the development server**:
   ```bash
   npm run dev
   ```

6. **Access the API**:
   - API Server: http://localhost:3000
   - API Documentation: http://localhost:3000/docs
   - Health Check: http://localhost:3000/health

### Production Deployment

#### Using Docker Compose

```bash
# Copy environment file
cp .env.example .env
# Configure production settings in .env

# Start all services
docker-compose up -d

# Check status
docker-compose ps
```

#### Manual Deployment

```bash
# Build the application
npm run build

# Start with PM2 (recommended)
npm install -g pm2
pm2 start ecosystem.config.js

# Or start directly
npm run start:prod
```

## API Documentation

### Authentication

The API supports two authentication methods:

#### API Key Authentication
```bash
curl -H "X-API-Key: rag_your-api-key-here" \
  http://localhost:3000/api/v1/documents
```

#### JWT Token Authentication
```bash
# Login to get tokens
curl -X POST http://localhost:3000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password"}'

# Use access token
curl -H "Authorization: Bearer your-jwt-token" \
  http://localhost:3000/api/v1/documents
```

### Core Endpoints

#### Document Processing

**Upload and process a document:**
```bash
curl -X POST http://localhost:3000/api/v1/documents/process \
  -H "X-API-Key: your-api-key" \
  -F "file=@document.pdf" \
  -F "parse_method=auto"
```

**Process multiple documents:**
```bash
curl -X POST http://localhost:3000/api/v1/documents/batch \
  -H "X-API-Key: your-api-key" \
  -F "files[]=@doc1.pdf" \
  -F "files[]=@doc2.pdf" \
  -F "max_workers=3"
```

#### Query System

**Text query:**
```bash
curl -X POST http://localhost:3000/api/v1/query/text \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is machine learning?",
    "mode": "mix",
    "top_k": 10
  }'
```

**Multimodal query:**
```bash
curl -X POST http://localhost:3000/api/v1/query/multimodal \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Analyze this chart",
    "multimodal_content": [
      {
        "type": "image",
        "data": "base64-encoded-image-data",
        "format": "png"
      }
    ]
  }'
```

#### Real-time Updates

**Server-Sent Events for processing progress:**
```javascript
const eventSource = new EventSource('/api/v1/stream/progress/job-123', {
  headers: { 'X-API-Key': 'your-api-key' }
});

eventSource.onmessage = function(event) {
  const data = JSON.parse(event.data);
  console.log('Progress:', data.progress + '%');
};
```

### Complete API Reference

Visit `/docs` when running the server for interactive OpenAPI documentation with:
- Complete endpoint reference
- Request/response schemas
- Authentication examples
- Rate limiting information

## Configuration

### Environment Variables

Create a `.env` file with the following variables:

```bash
# Server Configuration
NODE_ENV=production
PORT=3000
HOST=0.0.0.0
LOG_LEVEL=info

# Database
DATABASE_URL=postgresql://username:password@localhost:5432/ragapi
DATABASE_MAX_CONNECTIONS=20

# Redis
REDIS_URL=redis://localhost:6379
REDIS_PREFIX=rag-api:

# Authentication
JWT_SECRET=your-super-secret-jwt-key-at-least-32-characters-long
API_KEY_SALT=your-api-key-salt-16chars

# Rate Limiting
RATE_LIMIT_WINDOW_MS=3600000
RATE_LIMIT_MAX_REQUESTS=1000

# File Uploads
UPLOAD_MAX_FILE_SIZE=104857600  # 100MB
UPLOAD_MAX_FILES=100
TEMP_DIR=./temp

# Python Integration
PYTHON_EXECUTABLE=python3
PYTHON_MAX_PROCESSES=4
PYTHON_PROCESS_TIMEOUT=1800000

# RAG-Anything
RAG_STORAGE_DIR=./rag_storage
RAG_OUTPUT_DIR=./output

# External APIs (Optional)
OPENAI_API_KEY=your-openai-key
ANTHROPIC_API_KEY=your-anthropic-key
```

### System Configuration

The API allows dynamic configuration of RAG-Anything settings:

```bash
# Get current configuration
curl http://localhost:3000/api/v1/config \
  -H "Authorization: Bearer admin-token"

# Update configuration
curl -X PATCH http://localhost:3000/api/v1/config \
  -H "Authorization: Bearer admin-token" \
  -H "Content-Type: application/json" \
  -d '{
    "multimodal_processing": {
      "enable_image_processing": false
    },
    "batch_processing": {
      "max_concurrent_files": 4
    }
  }'
```

## Monitoring and Observability

### Health Checks

- **Basic Health**: `GET /health`
- **Readiness Check**: `GET /health/ready`  
- **Liveness Check**: `GET /health/live`

### Metrics

Prometheus metrics are available at `/metrics`:

```bash
curl http://localhost:3000/metrics
```

Key metrics include:
- HTTP request counts and durations
- Active connections
- Processing job statistics
- Python process health
- Memory and CPU usage

### Logging

Structured JSON logs with correlation IDs:

```json
{
  "timestamp": "2024-01-01T12:00:00.000Z",
  "level": "info",
  "message": "Request completed",
  "correlation_id": "req-abc123",
  "user_id": "user-456",
  "method": "POST",
  "url": "/api/v1/documents/process",
  "status_code": 202,
  "duration_ms": 150
}
```

### Performance Monitoring

Optional Grafana dashboard with Docker Compose:

```bash
docker-compose --profile monitoring up -d
```

Access at http://localhost:3001 (admin/admin123)

## Security

### Authentication & Authorization

- **JWT Tokens**: Short-lived access tokens with refresh mechanism
- **API Keys**: Long-lived keys for service-to-service communication
- **Role-based Access**: Admin, user, and readonly roles
- **Rate Limiting**: Configurable limits per user/API key

### Input Validation

- Comprehensive request validation using TypeBox schemas
- File type and size validation
- SQL injection prevention
- XSS protection

### Security Headers

Automatically applied security headers:
- Content Security Policy
- X-Frame-Options: DENY
- X-Content-Type-Options: nosniff
- Strict-Transport-Security (HTTPS only)

## Development

### Project Structure

```
api/
├── src/
│   ├── controllers/     # Route handlers
│   ├── middleware/      # Authentication, validation, etc.
│   ├── routes/          # API route definitions
│   ├── services/        # Business logic and external integrations
│   ├── types/           # TypeScript type definitions
│   ├── utils/           # Utility functions
│   ├── config/          # Configuration management
│   ├── app.ts           # Fastify app setup
│   └── server.ts        # Server entry point
├── scripts/             # Python worker and utilities
├── tests/               # Test files
├── docker-compose.yml   # Production Docker setup
├── docker-compose.dev.yml # Development Docker setup
└── Dockerfile           # Production container
```

### Testing

```bash
# Run all tests
npm test

# Run tests with coverage
npm run test:coverage

# Run integration tests
npm run test:integration

# Watch mode
npm run test:watch
```

### Code Quality

```bash
# Lint code
npm run lint

# Format code
npm run format

# Type checking
npm run typecheck
```

## Deployment

### Docker Production

```bash
# Build production image
docker build -t rag-anything-api .

# Run with docker-compose
docker-compose up -d

# Scale API servers
docker-compose up -d --scale api=3
```

### Kubernetes

Example Kubernetes manifests are in the `k8s/` directory:

```bash
# Deploy to Kubernetes
kubectl apply -f k8s/

# Check status
kubectl get pods -l app=rag-anything-api
```

### PM2 Process Manager

```bash
# Install PM2
npm install -g pm2

# Start application
pm2 start ecosystem.config.js

# Monitor
pm2 monit

# View logs
pm2 logs
```

## Troubleshooting

### Common Issues

**1. Python process fails to start**
```bash
# Check Python environment
python3 --version
pip list | grep raganything

# Check worker script
cd scripts && python3 python_worker.py
```

**2. Database connection errors**
```bash
# Test database connection
npm run db:test

# Check PostgreSQL status
docker-compose logs postgres
```

**3. Memory issues with large files**
```bash
# Increase Node.js memory limit
export NODE_OPTIONS="--max-old-space-size=8192"

# Check file size limits in .env
UPLOAD_MAX_FILE_SIZE=104857600
```

**4. Rate limiting issues**
```bash
# Check Redis connection
redis-cli ping

# View rate limit status
curl -I http://localhost:3000/api/v1/health
```

### Debug Mode

Enable debug logging:

```bash
export LOG_LEVEL=debug
npm run dev
```

### Performance Tuning

For high-load scenarios:

```bash
# Increase process limits
export PYTHON_MAX_PROCESSES=8
export DATABASE_MAX_CONNECTIONS=50

# Enable clustering
export CLUSTER_WORKERS=4
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make changes and add tests
4. Run the test suite: `npm test`
5. Commit changes: `git commit -am 'Add feature'`
6. Push to the branch: `git push origin feature-name`
7. Submit a pull request

## License

MIT License - see the [LICENSE](../LICENSE) file for details.

## Support

- **Documentation**: Complete API docs at `/docs`
- **GitHub Issues**: Report bugs and request features
- **Discord**: Join our community for support and discussions

## Changelog

### v1.0.0
- Initial release with core document processing and query functionality
- JWT and API key authentication
- Docker containerization
- Comprehensive monitoring and logging
- Production-ready deployment configuration