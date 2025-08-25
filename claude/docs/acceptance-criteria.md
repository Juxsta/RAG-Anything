# RAG-Anything API Server Acceptance Criteria

## API Endpoint Specifications

### Document Processing Endpoints

#### POST /api/v1/documents/process
**Purpose**: Process a single document with multimodal content extraction

**Request Specification**:
```http
POST /api/v1/documents/process
Content-Type: multipart/form-data
Authorization: Bearer {api_key}

Form Data:
- file: (binary file data, max 100MB)
- parse_method: (optional) "auto" | "ocr" | "txt"
- output_dir: (optional) string
- display_stats: (optional) boolean
- split_by_character: (optional) string
- split_by_character_only: (optional) boolean
- doc_id: (optional) string
- Additional parser parameters as form fields
```

**Response Specification**:
```json
{
  "success": true,
  "data": {
    "job_id": "job-abc123",
    "doc_id": "doc-def456",
    "status": "processing",
    "file_info": {
      "filename": "document.pdf",
      "size": 2048576,
      "type": "application/pdf"
    },
    "processing_options": {
      "parse_method": "auto",
      "output_dir": "./output",
      "display_stats": true
    },
    "estimated_completion": "2024-01-01T12:05:00Z"
  },
  "meta": {
    "request_id": "req-123456",
    "timestamp": "2024-01-01T12:00:00Z"
  }
}
```

**Acceptance Criteria**:
- [ ] **MUST** accept files up to 100MB in size
- [ ] **MUST** validate file types against supported extensions
- [ ] **MUST** return 202 status code for successful submission
- [ ] **MUST** return unique job_id for tracking processing status
- [ ] **MUST** return appropriate error codes for validation failures
- [ ] **MUST** support all RAG-Anything parser parameters
- [ ] **SHOULD** provide estimated completion time
- [ ] **SHOULD** sanitize and validate all input parameters

#### POST /api/v1/documents/batch
**Purpose**: Process multiple documents in batch mode

**Request Specification**:
```http
POST /api/v1/documents/batch
Content-Type: multipart/form-data
Authorization: Bearer {api_key}

Form Data:
- files[]: (multiple binary files, max 100 files total)
- parse_method: (optional) "auto" | "ocr" | "txt"
- output_dir: (optional) string
- max_workers: (optional) integer (1-10)
- recursive: (optional) boolean
- show_progress: (optional) boolean
```

**Response Specification**:
```json
{
  "success": true,
  "data": {
    "batch_id": "batch-xyz789",
    "total_files": 5,
    "accepted_files": 5,
    "rejected_files": 0,
    "files": [
      {
        "filename": "doc1.pdf",
        "job_id": "job-abc123",
        "doc_id": "doc-def456",
        "status": "queued"
      }
    ],
    "progress_url": "/api/v1/batch/batch-xyz789/progress",
    "estimated_completion": "2024-01-01T12:15:00Z"
  }
}
```

**Acceptance Criteria**:
- [ ] **MUST** accept up to 100 files per batch request
- [ ] **MUST** validate each file individually before queuing
- [ ] **MUST** return batch_id for tracking overall progress
- [ ] **MUST** provide individual job_id for each accepted file
- [ ] **MUST** reject batch if any file exceeds size limits
- [ ] **MUST** support Server-Sent Events for progress updates
- [ ] **SHOULD** process files concurrently based on max_workers
- [ ] **SHOULD** continue processing if individual files fail

#### POST /api/v1/documents/content-list
**Purpose**: Process pre-parsed content list directly

**Request Specification**:
```json
{
  "content_list": [
    {
      "type": "text",
      "text": "Document content here",
      "page_idx": 0
    },
    {
      "type": "image",
      "img_path": "/absolute/path/to/image.jpg",
      "img_caption": ["Image description"],
      "img_footnote": ["Image note"],
      "page_idx": 1
    },
    {
      "type": "table",
      "table_body": "| Col1 | Col2 |\n|------|------|\n| A | B |",
      "table_caption": ["Table title"],
      "table_footnote": ["Table note"],
      "page_idx": 2
    }
  ],
  "file_path": "document_name",
  "split_by_character": "\n\n",
  "split_by_character_only": false,
  "doc_id": "custom-doc-id",
  "display_stats": true
}
```

**Response Specification**:
```json
{
  "success": true,
  "data": {
    "doc_id": "custom-doc-id",
    "processing_summary": {
      "total_blocks": 3,
      "text_blocks": 1,
      "image_blocks": 1,
      "table_blocks": 1,
      "equation_blocks": 0
    },
    "status": "completed",
    "processing_time_ms": 1500
  }
}
```

**Acceptance Criteria**:
- [ ] **MUST** validate content_list structure and required fields
- [ ] **MUST** support all RAG-Anything content types (text, image, table, equation)
- [ ] **MUST** validate image paths exist and are accessible
- [ ] **MUST** return processing summary with block counts
- [ ] **MUST** generate doc_id if not provided
- [ ] **SHOULD** process content blocks in order
- [ ] **SHOULD** provide detailed error messages for invalid content

### Query Endpoints

#### POST /api/v1/query/text
**Purpose**: Execute text-only queries against the knowledge base

**Request Specification**:
```json
{
  "query": "What is machine learning?",
  "mode": "mix",
  "vlm_enhanced": true,
  "stream": false,
  "top_k": 10,
  "max_tokens": 2000,
  "temperature": 0.7
}
```

**Response Specification**:
```json
{
  "success": true,
  "data": {
    "query_id": "query-abc123",
    "result": "Machine learning is...",
    "sources": [
      {
        "doc_id": "doc-def456",
        "chunk_id": "chunk-ghi789",
        "file_path": "document.pdf",
        "relevance_score": 0.95,
        "content_preview": "Machine learning definition..."
      }
    ],
    "metadata": {
      "mode": "mix",
      "processing_time_ms": 850,
      "total_chunks_searched": 1500,
      "vlm_enhanced": true
    }
  }
}
```

**Acceptance Criteria**:
- [ ] **MUST** support all LightRAG query modes (local, global, hybrid, naive, mix, bypass)
- [ ] **MUST** return structured results with source citations
- [ ] **MUST** include relevance scores for source ranking
- [ ] **MUST** handle empty results gracefully
- [ ] **MUST** validate query parameters and return appropriate errors
- [ ] **SHOULD** support VLM-enhanced queries when vision models available
- [ ] **SHOULD** include processing metadata (time, chunks searched)
- [ ] **SHOULD** support streaming responses for long queries

#### POST /api/v1/query/multimodal
**Purpose**: Execute queries with multimodal content (text + images/tables)

**Request Specification**:
```json
{
  "query": "Analyze this chart and compare with the text",
  "multimodal_content": [
    {
      "type": "image",
      "img_path": "/path/to/chart.jpg"
    },
    {
      "type": "image",
      "data": "base64-encoded-image-data",
      "format": "jpeg"
    },
    {
      "type": "table",
      "table_data": "| Q1 | Q2 |\n|----|----|"
    }
  ],
  "mode": "mix",
  "stream": false
}
```

**Response Specification**:
```json
{
  "success": true,
  "data": {
    "query_id": "query-multimodal-123",
    "result": "Analysis of the chart shows...",
    "sources": [
      {
        "doc_id": "doc-def456",
        "chunk_id": "chunk-img789",
        "type": "multimodal",
        "modality": "image",
        "file_path": "presentation.pdf",
        "relevance_score": 0.92
      }
    ],
    "processing_details": {
      "text_analysis": "Completed",
      "image_analysis": "Completed",
      "table_analysis": "Completed",
      "total_processing_time_ms": 2340
    }
  }
}
```

**Acceptance Criteria**:
- [ ] **MUST** support base64-encoded images in requests
- [ ] **MUST** support file path references for existing images
- [ ] **MUST** validate image formats and content
- [ ] **MUST** process each multimodal content type with appropriate processor
- [ ] **MUST** combine multimodal analysis with text query
- [ ] **SHOULD** return processing details for each modality
- [ ] **SHOULD** handle mixed success/failure in multimodal content
- [ ] **SHOULD** support streaming for complex multimodal queries

### Configuration Endpoints

#### GET /api/v1/config
**Purpose**: Retrieve current system configuration

**Response Specification**:
```json
{
  "success": true,
  "data": {
    "directory": {
      "working_dir": "./rag_storage",
      "parser_output_dir": "./output"
    },
    "parsing": {
      "parser": "mineru",
      "parse_method": "auto",
      "display_content_stats": true
    },
    "multimodal_processing": {
      "enable_image_processing": true,
      "enable_table_processing": true,
      "enable_equation_processing": true
    },
    "context_extraction": {
      "context_window": 1,
      "context_mode": "page",
      "max_context_tokens": 2000
    },
    "batch_processing": {
      "max_concurrent_files": 2,
      "supported_file_extensions": [".pdf", ".docx"],
      "recursive_folder_processing": true
    }
  }
}
```

**Acceptance Criteria**:
- [ ] **MUST** return complete current configuration
- [ ] **MUST** mask or omit sensitive configuration values
- [ ] **MUST** indicate configuration source (environment, default, override)
- [ ] **SHOULD** include validation information for each parameter
- [ ] **SHOULD** show available options for enumerated values

#### PATCH /api/v1/config
**Purpose**: Update system configuration dynamically

**Request Specification**:
```json
{
  "multimodal_processing": {
    "enable_image_processing": false
  },
  "batch_processing": {
    "max_concurrent_files": 4
  }
}
```

**Response Specification**:
```json
{
  "success": true,
  "data": {
    "updated_fields": [
      "multimodal_processing.enable_image_processing",
      "batch_processing.max_concurrent_files"
    ],
    "warnings": [
      "Changes to multimodal_processing require processor reinitialization"
    ],
    "restart_required": false
  }
}
```

**Acceptance Criteria**:
- [ ] **MUST** validate all configuration changes before applying
- [ ] **MUST** support partial updates (only specified fields changed)
- [ ] **MUST** return validation errors without changing configuration
- [ ] **MUST** apply changes immediately where possible
- [ ] **SHOULD** warn about changes requiring restart
- [ ] **SHOULD** provide rollback capability for failed updates

### Status and Health Endpoints

#### GET /api/v1/health
**Purpose**: Basic health check for load balancers and monitoring

**Response Specification**:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00Z",
  "version": "1.0.0",
  "uptime_seconds": 3600,
  "checks": {
    "python_process": "healthy",
    "lightrag_storage": "healthy",
    "parser_availability": "healthy"
  }
}
```

**Acceptance Criteria**:
- [ ] **MUST** respond within 100ms
- [ ] **MUST** return 200 status when healthy
- [ ] **MUST** return 503 status when unhealthy
- [ ] **MUST** check critical dependencies (Python, storage)
- [ ] **SHOULD** include basic system metrics
- [ ] **SHOULD** not require authentication

#### GET /api/v1/status
**Purpose**: Detailed system status and metrics

**Response Specification**:
```json
{
  "success": true,
  "data": {
    "system": {
      "status": "operational",
      "version": "1.0.0",
      "uptime_seconds": 3600,
      "node_version": "18.17.0",
      "python_version": "3.9.0"
    },
    "performance": {
      "memory_usage_mb": 512,
      "cpu_usage_percent": 25.5,
      "active_connections": 15,
      "requests_per_minute": 45
    },
    "processing": {
      "queue_length": 3,
      "active_jobs": 2,
      "completed_jobs_today": 150,
      "failed_jobs_today": 2
    },
    "storage": {
      "lightrag_initialized": true,
      "total_documents": 1250,
      "total_chunks": 15000,
      "storage_size_mb": 850
    }
  }
}
```

**Acceptance Criteria**:
- [ ] **MUST** include system performance metrics
- [ ] **MUST** show processing queue status
- [ ] **MUST** report storage and database statistics
- [ ] **MUST** indicate overall system health
- [ ] **SHOULD** include recent error rates
- [ ] **SHOULD** show resource utilization trends

### Document Management Endpoints

#### GET /api/v1/documents
**Purpose**: List processed documents with pagination and filtering

**Request Parameters**:
```
?page=1&limit=20&status=completed&type=pdf&search=machine%20learning&sort=created_at&order=desc
```

**Response Specification**:
```json
{
  "success": true,
  "data": {
    "documents": [
      {
        "doc_id": "doc-abc123",
        "filename": "ml_paper.pdf",
        "status": "completed",
        "created_at": "2024-01-01T10:00:00Z",
        "updated_at": "2024-01-01T10:05:00Z",
        "chunks_count": 45,
        "file_size": 2048576,
        "content_types": ["text", "image", "table"]
      }
    ],
    "pagination": {
      "current_page": 1,
      "per_page": 20,
      "total_pages": 5,
      "total_documents": 95
    },
    "filters": {
      "status": ["processing", "completed", "failed"],
      "type": ["pdf", "docx", "image"],
      "content_types": ["text", "image", "table", "equation"]
    }
  }
}
```

**Acceptance Criteria**:
- [ ] **MUST** support pagination with configurable page sizes
- [ ] **MUST** support filtering by status, type, and date
- [ ] **MUST** support text search across document content
- [ ] **MUST** support sorting by multiple fields
- [ ] **MUST** return appropriate metadata for each document
- [ ] **SHOULD** support advanced query syntax
- [ ] **SHOULD** cache results for performance

#### GET /api/v1/documents/{docId}
**Purpose**: Get detailed information about a specific document

**Response Specification**:
```json
{
  "success": true,
  "data": {
    "doc_id": "doc-abc123",
    "filename": "ml_paper.pdf",
    "status": "completed",
    "created_at": "2024-01-01T10:00:00Z",
    "updated_at": "2024-01-01T10:05:00Z",
    "processing_details": {
      "text_processed": true,
      "multimodal_processed": true,
      "chunks_count": 45,
      "entities_count": 120,
      "relations_count": 85,
      "processing_time_ms": 45000
    },
    "content_analysis": {
      "text_blocks": 35,
      "image_blocks": 8,
      "table_blocks": 2,
      "equation_blocks": 0,
      "total_tokens": 15000
    },
    "file_info": {
      "original_filename": "ml_paper.pdf",
      "file_size": 2048576,
      "file_type": "application/pdf",
      "checksum": "sha256:abc123..."
    }
  }
}
```

**Acceptance Criteria**:
- [ ] **MUST** return complete document metadata and status
- [ ] **MUST** include processing statistics and timeline
- [ ] **MUST** show content analysis results
- [ ] **MUST** return 404 for non-existent documents
- [ ] **SHOULD** include links to related resources (chunks, entities)
- [ ] **SHOULD** show processing error details if failed

#### DELETE /api/v1/documents/{docId}
**Purpose**: Remove document and all associated data from the system

**Response Specification**:
```json
{
  "success": true,
  "data": {
    "doc_id": "doc-abc123",
    "deleted": true,
    "cleanup_summary": {
      "chunks_removed": 45,
      "entities_removed": 120,
      "relations_removed": 85,
      "files_removed": 3,
      "storage_freed_mb": 15.2
    },
    "processing_cancelled": false
  }
}
```

**Acceptance Criteria**:
- [ ] **MUST** remove all document data from all storage systems
- [ ] **MUST** cancel any in-progress processing before deletion
- [ ] **MUST** return cleanup summary showing what was removed
- [ ] **MUST** return 404 for documents that don't exist
- [ ] **SHOULD** create audit log entries for deletions
- [ ] **SHOULD** support soft delete option for data recovery

## Error Response Specifications

### Standard Error Format
All API endpoints must return errors in the following standardized format:

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": {
      "field": "file",
      "reason": "File size exceeds maximum allowed size of 100MB"
    },
    "request_id": "req-123456",
    "timestamp": "2024-01-01T12:00:00Z",
    "documentation_url": "https://api-docs.example.com/errors/validation-error"
  }
}
```

### HTTP Status Code Usage

| Status Code | Usage | Examples |
|-------------|-------|----------|
| 200 | Successful GET/PATCH requests | Configuration retrieval, status checks |
| 201 | Successful resource creation | Document processing initiated |
| 202 | Accepted for processing | Async operations started |
| 204 | Successful deletion | Document deleted |
| 400 | Client request errors | Invalid JSON, missing required fields |
| 401 | Authentication required | Missing or invalid API key |
| 403 | Forbidden | Insufficient permissions |
| 404 | Resource not found | Document doesn't exist |
| 409 | Conflict | Document already processing |
| 413 | Payload too large | File size exceeds limits |
| 422 | Validation failed | Valid JSON but invalid data |
| 429 | Rate limit exceeded | Too many requests |
| 500 | Internal server error | Unexpected server failures |
| 502 | Bad gateway | Python process communication failure |
| 503 | Service unavailable | System overloaded or maintenance |
| 504 | Gateway timeout | Python process timeout |

### Error Code Categories

**Authentication & Authorization**:
- `AUTH_MISSING` - No authentication provided
- `AUTH_INVALID` - Invalid credentials
- `AUTH_EXPIRED` - Expired credentials
- `PERMISSION_DENIED` - Insufficient permissions
- `RATE_LIMIT_EXCEEDED` - Rate limit hit

**Validation Errors**:
- `VALIDATION_ERROR` - General validation failure
- `INVALID_FORMAT` - Invalid data format
- `MISSING_FIELD` - Required field missing
- `INVALID_VALUE` - Field value out of range/invalid
- `FILE_TOO_LARGE` - File exceeds size limit
- `UNSUPPORTED_FORMAT` - File type not supported

**Processing Errors**:
- `PROCESSING_FAILED` - Document processing failed
- `PARSER_ERROR` - Document parser failure
- `PYTHON_ERROR` - Python process error
- `STORAGE_ERROR` - Database/storage failure
- `MODEL_ERROR` - AI model processing error

**System Errors**:
- `INTERNAL_ERROR` - Unexpected server error
- `SERVICE_UNAVAILABLE` - System overloaded
- `TIMEOUT_ERROR` - Operation timeout
- `DEPENDENCY_ERROR` - External service failure

## Performance Requirements

### Response Time Targets
- **Health endpoints**: < 100ms (95th percentile)
- **Query endpoints**: < 2000ms (95th percentile, excluding processing time)
- **Configuration endpoints**: < 300ms (95th percentile)
- **Document listing**: < 500ms (95th percentile)
- **File upload initiation**: < 1000ms (95th percentile)

### Throughput Requirements
- **Concurrent connections**: Support 100+ simultaneous connections
- **Requests per second**: Handle 50+ RPS for read operations
- **File uploads**: Support 5+ concurrent file uploads
- **Query throughput**: Process 10+ concurrent queries

### Resource Utilization
- **Memory usage**: < 4GB per Node.js process
- **CPU usage**: < 80% under normal load
- **Disk I/O**: Efficient temporary file handling
- **Network**: Optimize for minimal bandwidth usage

## Security Requirements

### Authentication & Authorization
- **API Key Management**: Secure generation, storage, and validation
- **JWT Support**: Optional JWT token authentication
- **Role-Based Access**: Admin, user, and read-only roles
- **Audit Logging**: Complete audit trail for security events

### Data Protection
- **HTTPS Only**: All production traffic encrypted
- **Input Validation**: Comprehensive validation and sanitization
- **File Security**: Virus scanning for uploaded files
- **Data Retention**: Configurable retention policies

### Network Security
- **CORS Configuration**: Proper cross-origin request handling
- **Rate Limiting**: Prevent abuse and DoS attacks
- **Request Size Limits**: Protect against large payload attacks
- **IP Filtering**: Optional IP whitelist/blacklist support

## Monitoring and Observability

### Logging Requirements
- **Structured Logging**: JSON format with consistent fields
- **Log Levels**: DEBUG, INFO, WARN, ERROR with appropriate usage
- **Correlation IDs**: Track requests across system boundaries
- **Sensitive Data**: Never log passwords, API keys, or personal data

### Metrics Collection
- **Request Metrics**: Count, duration, status codes per endpoint
- **System Metrics**: CPU, memory, disk usage
- **Business Metrics**: Documents processed, queries executed
- **Error Metrics**: Error rates by type and endpoint

### Health Monitoring
- **Dependency Checks**: Monitor Python processes, storage systems
- **Performance Monitoring**: Track response times and throughput
- **Alert Thresholds**: Configurable alerting for critical issues
- **Dashboard Support**: Export metrics in Prometheus format

## Documentation Requirements

### API Documentation
- **OpenAPI 3.0**: Complete specification with examples
- **Interactive Docs**: Swagger UI or similar interface
- **SDK Generation**: Support for multiple programming languages
- **Postman Collection**: Ready-to-use API collection

### Developer Resources
- **Getting Started**: Quick start guide with examples
- **Authentication Guide**: Detailed auth setup instructions
- **Error Handling**: Comprehensive error handling guide
- **Best Practices**: Performance and usage recommendations