# RAG-Anything API Server OpenAPI Specification

```yaml
openapi: 3.0.3
info:
  title: RAG-Anything API Server
  version: 1.0.0
  description: |
    REST API for RAG-Anything multimodal document processing and retrieval system.
    
    ## Overview
    
    This API provides access to RAG-Anything's advanced document processing, multimodal content extraction, 
    and intelligent query capabilities. It supports:
    
    - **Document Processing**: Upload and process PDF, Office documents, and images
    - **Multimodal Queries**: Query with text, images, tables, and equations
    - **Batch Operations**: Process multiple documents concurrently
    - **Real-time Updates**: WebSocket and SSE support for long-running operations
    - **Configuration Management**: Dynamic system configuration
    
    ## Authentication
    
    The API supports two authentication methods:
    - **JWT Tokens**: For user sessions with refresh token support
    - **API Keys**: For service-to-service communication
    
    Include your authentication in the appropriate header:
    ```
    Authorization: Bearer <jwt-token>
    X-API-Key: <api-key>
    ```
    
    ## Rate Limiting
    
    - **JWT Users**: 5000 requests per hour
    - **API Key Users**: 1000 requests per hour (configurable per key)
    - **Concurrent Operations**: 10 concurrent file uploads, 20 concurrent queries
    
    ## Real-time Features
    
    - **WebSocket**: Real-time progress updates and streaming responses
    - **Server-Sent Events**: HTTP-based real-time updates for job progress
    - **Stream Processing**: Live query results as they're generated
    
  contact:
    name: RAG-Anything API Support
    url: https://github.com/HKUDS/RAG-Anything
  license:
    name: MIT
    url: https://opensource.org/licenses/MIT

servers:
  - url: https://api.rag-anything.com/v1
    description: Production server
  - url: https://staging-api.rag-anything.com/v1
    description: Staging server
  - url: http://localhost:3000/v1
    description: Local development server

security:
  - ApiKeyAuth: []
  - BearerAuth: []

paths:
  # Authentication Endpoints
  /auth/login:
    post:
      summary: User login with JWT tokens
      description: |
        Authenticate user with email/password and receive JWT access and refresh tokens.
        Supports multi-factor authentication if enabled for the user account.
      operationId: loginUser
      tags:
        - Authentication
      security: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - email
                - password
              properties:
                email:
                  type: string
                  format: email
                  description: User email address
                password:
                  type: string
                  minLength: 8
                  description: User password
                mfa_code:
                  type: string
                  pattern: '^[0-9]{6}$'
                  description: MFA code (required if MFA is enabled)
            example:
              email: user@example.com
              password: secure-password
              mfa_code: "123456"
      responses:
        '200':
          description: Login successful
          content:
            application/json:
              schema:
                type: object
                properties:
                  success:
                    type: boolean
                    const: true
                  data:
                    type: object
                    properties:
                      access_token:
                        type: string
                        description: JWT access token (15 minute expiry)
                      refresh_token:
                        type: string
                        description: JWT refresh token (7 day expiry)
                      user:
                        $ref: '#/components/schemas/UserProfile'
                      expires_in:
                        type: integer
                        description: Token expiry time in seconds
                  meta:
                    $ref: '#/components/schemas/ResponseMeta'
        '401':
          description: Authentication failed
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                success: false
                error:
                  code: "AUTH_FAILED"
                  message: "Invalid email or password"
        '423':
          description: Account locked due to failed attempts
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

  /auth/refresh:
    post:
      summary: Refresh JWT access token
      description: |
        Use refresh token to obtain a new access token pair.
        Invalidates the old refresh token for security.
      operationId: refreshToken
      tags:
        - Authentication
      security: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - refresh_token
              properties:
                refresh_token:
                  type: string
                  description: Valid refresh token
      responses:
        '200':
          description: Token refreshed successfully
          content:
            application/json:
              schema:
                type: object
                properties:
                  success:
                    type: boolean
                    const: true
                  data:
                    type: object
                    properties:
                      access_token:
                        type: string
                      refresh_token:
                        type: string
                      expires_in:
                        type: integer
        '401':
          $ref: '#/components/responses/Unauthorized'

  /auth/logout:
    post:
      summary: Logout user
      description: |
        Logout user and invalidate refresh token.
        Clears user session and audit logs the logout event.
      operationId: logoutUser
      tags:
        - Authentication
      responses:
        '200':
          description: Logout successful
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SuccessResponse'

  # API Key Management
  /auth/api-keys:
    get:
      summary: List user API keys
      description: Get list of API keys for the authenticated user
      operationId: listApiKeys
      tags:
        - Authentication
      responses:
        '200':
          description: API keys retrieved successfully
          content:
            application/json:
              schema:
                type: object
                properties:
                  success:
                    type: boolean
                    const: true
                  data:
                    type: object
                    properties:
                      api_keys:
                        type: array
                        items:
                          $ref: '#/components/schemas/ApiKeyInfo'

    post:
      summary: Create new API key
      description: |
        Generate a new API key with specified permissions and rate limits.
        The full key is only returned once upon creation.
      operationId: createApiKey
      tags:
        - Authentication
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - name
              properties:
                name:
                  type: string
                  minLength: 1
                  maxLength: 100
                  description: Descriptive name for the API key
                permissions:
                  type: array
                  items:
                    type: string
                    enum: [documents.read, documents.write, query.execute, config.read, config.write]
                  description: Granted permissions
                rate_limit:
                  type: integer
                  minimum: 100
                  maximum: 10000
                  default: 1000
                  description: Requests per hour
                expires_in_days:
                  type: integer
                  minimum: 1
                  maximum: 365
                  description: API key expiration in days (optional)
      responses:
        '201':
          description: API key created successfully
          content:
            application/json:
              schema:
                type: object
                properties:
                  success:
                    type: boolean
                    const: true
                  data:
                    type: object
                    properties:
                      api_key:
                        type: string
                        description: Full API key (only shown once)
                      key_info:
                        $ref: '#/components/schemas/ApiKeyInfo'

  /auth/api-keys/{keyId}:
    delete:
      summary: Revoke API key
      description: Permanently revoke an API key
      operationId: revokeApiKey
      tags:
        - Authentication
      parameters:
        - name: keyId
          in: path
          required: true
          schema:
            type: string
          description: API key ID
      responses:
        '200':
          description: API key revoked successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SuccessResponse'

  # Document Processing Endpoints
  /documents/process:
    post:
      summary: Process single document
      description: |
        Upload and process a single document with multimodal content extraction.
        Supports PDF, Office documents, images, and text files up to 100MB.
        Returns immediately with job ID for tracking progress via WebSocket or SSE.
      operationId: processDocument
      tags:
        - Document Processing
      requestBody:
        required: true
        content:
          multipart/form-data:
            schema:
              type: object
              required:
                - file
              properties:
                file:
                  type: string
                  format: binary
                  description: Document file to process (max 100MB)
                parse_method:
                  type: string
                  enum: [auto, ocr, txt]
                  default: auto
                  description: Parsing method for document processing
                output_dir:
                  type: string
                  description: Output directory for processed content
                display_stats:
                  type: boolean
                  default: true
                  description: Whether to display processing statistics
                split_by_character:
                  type: string
                  description: Character(s) to use for content splitting
                split_by_character_only:
                  type: boolean
                  default: false
                  description: Whether to split only by specified character
                doc_id:
                  type: string
                  description: Custom document ID (auto-generated if not provided)
                priority:
                  type: integer
                  minimum: 0
                  maximum: 10
                  default: 0
                  description: Job priority (0=lowest, 10=highest)
            encoding:
              file:
                contentType: application/pdf, application/msword, application/vnd.openxmlformats-officedocument.wordprocessingml.document, image/*, text/plain
      responses:
        '202':
          description: Document processing started successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ProcessingResponse'
              example:
                success: true
                data:
                  job_id: "job-abc123"
                  doc_id: "doc-def456"
                  status: "queued"
                  file_info:
                    filename: "document.pdf"
                    size: 2048576
                    type: "application/pdf"
                    checksum: "sha256:abc123..."
                  processing_options:
                    parse_method: "auto"
                    output_dir: "./output"
                    display_stats: true
                  estimated_completion: "2024-01-01T12:05:00Z"
                  progress_urls:
                    websocket: "wss://api.rag-anything.com/ws"
                    sse: "/api/v1/stream/progress/job-abc123"
                meta:
                  request_id: "req-123456"
                  timestamp: "2024-01-01T12:00:00Z"
        '400':
          $ref: '#/components/responses/BadRequest'
        '413':
          $ref: '#/components/responses/PayloadTooLarge'
        '422':
          $ref: '#/components/responses/ValidationError'

  /documents/batch:
    post:
      summary: Process multiple documents
      description: |
        Upload and process multiple documents in batch mode with progress tracking.
        Supports up to 100 files with real-time progress updates via Server-Sent Events.
        Each document gets its own job with individual progress tracking.
      operationId: processBatch
      tags:
        - Document Processing
      requestBody:
        required: true
        content:
          multipart/form-data:
            schema:
              type: object
              required:
                - files
              properties:
                files:
                  type: array
                  items:
                    type: string
                    format: binary
                  description: Array of document files to process (max 100 files)
                parse_method:
                  type: string
                  enum: [auto, ocr, txt]
                  default: auto
                max_workers:
                  type: integer
                  minimum: 1
                  maximum: 10
                  default: 2
                  description: Maximum concurrent processing workers
                recursive:
                  type: boolean
                  default: true
                  description: Whether to recursively process subdirectories
                show_progress:
                  type: boolean
                  default: true
                  description: Whether to provide real-time progress updates
      responses:
        '202':
          description: Batch processing started successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/BatchProcessingResponse'
              example:
                success: true
                data:
                  batch_id: "batch-xyz789"
                  total_files: 5
                  accepted_files: 5
                  rejected_files: 0
                  files:
                    - filename: "doc1.pdf"
                      job_id: "job-001"
                      doc_id: "doc-001"
                      status: "queued"
                    - filename: "doc2.pdf"
                      job_id: "job-002"
                      doc_id: "doc-002"
                      status: "queued"
                  progress_urls:
                    websocket: "wss://api.rag-anything.com/ws"
                    sse: "/api/v1/stream/batch-progress/batch-xyz789"
                  estimated_completion: "2024-01-01T12:15:00Z"
        '400':
          $ref: '#/components/responses/BadRequest'
        '413':
          $ref: '#/components/responses/PayloadTooLarge'

  /documents/content-list:
    post:
      summary: Process pre-parsed content list
      description: |
        Process a pre-parsed content list directly without document parsing.
        Useful for integration with custom parsing workflows or testing.
        Processes content immediately without job queue.
      operationId: processContentList
      tags:
        - Document Processing
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ContentListRequest'
            example:
              content_list:
                - type: "text"
                  text: "Document content here"
                  page_idx: 0
                - type: "image"
                  img_path: "/absolute/path/to/image.jpg"
                  img_caption: ["Image description"]
                  img_footnote: ["Image note"]
                  page_idx: 1
                - type: "table"
                  table_body: "| Col1 | Col2 |\n|------|------|\n| A | B |"
                  table_caption: ["Table title"]
                  table_footnote: ["Table note"]
                  page_idx: 2
              file_path: "document_name"
              doc_id: "custom-doc-id"
              display_stats: true
      responses:
        '200':
          description: Content list processed successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ContentListResponse'
              example:
                success: true
                data:
                  doc_id: "custom-doc-id"
                  processing_summary:
                    total_blocks: 3
                    text_blocks: 1
                    image_blocks: 1
                    table_blocks: 1
                    equation_blocks: 0
                  status: "completed"
                  processing_time_ms: 1500
                  chunks_created: 15
                  entities_extracted: 45
                  relations_created: 23
        '400':
          $ref: '#/components/responses/BadRequest'
        '422':
          $ref: '#/components/responses/ValidationError'

  # Query Endpoints
  /query/text:
    post:
      summary: Execute text query
      description: |
        Execute text-only queries against the knowledge base with various retrieval modes.
        Supports all LightRAG query modes with real-time streaming responses.
        Results include actual sources from processed documents with relevance scores.
      operationId: queryText
      tags:
        - Query
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/TextQueryRequest'
            example:
              query: "What is machine learning and how does it work?"
              mode: "mix"
              vlm_enhanced: true
              stream: false
              top_k: 10
              max_tokens: 2000
              temperature: 0.7
      responses:
        '200':
          description: Query executed successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/QueryResponse'
              example:
                success: true
                data:
                  query_id: "query-abc123"
                  result: "Machine learning is a subset of artificial intelligence that enables computers to learn and improve from experience without being explicitly programmed. It works by analyzing patterns in data..."
                  sources:
                    - doc_id: "doc-123"
                      chunk_id: "chunk-001"
                      file_path: "ml_fundamentals.pdf"
                      relevance_score: 0.95
                      content_preview: "Machine learning is a method of data analysis..."
                      type: "text"
                      modality: "text"
                      page_number: 5
                    - doc_id: "doc-456" 
                      chunk_id: "chunk-015"
                      file_path: "ai_handbook.pdf"
                      relevance_score: 0.87
                      content_preview: "Supervised learning algorithms build models..."
                      type: "multimodal"
                      modality: "image"
                      page_number: 12
                  metadata:
                    mode: "mix"
                    processing_time_ms: 850
                    total_chunks_searched: 1500
                    vlm_enhanced: true
                    model_used: "gpt-4"
                    knowledge_graph_nodes: 145
                    knowledge_graph_relations: 89
            text/event-stream:
              schema:
                type: string
              description: Streaming response when stream=true
              example: |
                event: start
                data: {"query_id": "query-123", "estimated_time": 5000}
                
                event: progress
                data: {"query_id": "query-123", "stage": "retrieval", "progress": 30}
                
                event: chunk
                data: {"query_id": "query-123", "chunk": "Machine learning is", "source": "doc-123"}
                
                event: complete
                data: {"query_id": "query-123", "total_time": 4850}
        '400':
          $ref: '#/components/responses/BadRequest'
        '422':
          $ref: '#/components/responses/ValidationError'

  /query/multimodal:
    post:
      summary: Execute multimodal query
      description: |
        Execute queries with multimodal content including text, images, tables, and equations.
        Supports base64-encoded images, file path references, and complex document analysis.
        Integrates vision models for image analysis and specialized parsers for tables/equations.
      operationId: queryMultimodal
      tags:
        - Query
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/MultimodalQueryRequest'
            example:
              query: "Analyze this chart and compare the trends with the textual data"
              multimodal_content:
                - type: "image"
                  img_path: "/path/to/chart.jpg"
                - type: "image"
                  data: "iVBORw0KGgoAAAANSUhEUgAA..."
                  format: "jpeg"
                - type: "table"
                  table_data: "| Q1 | Q2 | Q3 |\n|----|----|----|---|100 | 150 | 200 |"
                - type: "equation"
                  equation: "E = mc^2"
              mode: "mix"
              stream: false
      responses:
        '200':
          description: Multimodal query executed successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/MultimodalQueryResponse'
              example:
                success: true
                data:
                  query_id: "query-multimodal-456"
                  result: "Based on the analysis of the provided chart and supporting textual data, the trends show consistent growth across all quarters..."
                  sources:
                    - doc_id: "doc-789"
                      chunk_id: "chunk-img-001"
                      file_path: "quarterly_report.pdf"
                      relevance_score: 0.92
                      content_preview: "Figure 2.1: Quarterly performance metrics..."
                      type: "multimodal"
                      modality: "image"
                      page_number: 8
                  metadata:
                    mode: "mix"
                    processing_time_ms: 2340
                    total_chunks_searched: 800
                    vlm_enhanced: true
                  processing_details:
                    image_analysis: "completed"
                    table_analysis: "completed"
                    equation_analysis: "completed"
                    text_analysis: "completed"
                    vision_model_used: "gpt-4-vision"
                    total_processing_time_ms: 2340
        '400':
          $ref: '#/components/responses/BadRequest'
        '422':
          $ref: '#/components/responses/ValidationError'

  /query/history:
    get:
      summary: Get query history
      description: |
        Retrieve user query history with pagination, filtering, and search capabilities.
        Includes performance metrics and caching information for query optimization.
      operationId: getQueryHistory
      tags:
        - Query
      parameters:
        - name: page
          in: query
          schema:
            type: integer
            minimum: 1
            default: 1
          description: Page number for pagination
        - name: limit
          in: query
          schema:
            type: integer
            minimum: 1
            maximum: 100
            default: 20
          description: Number of queries per page
        - name: type
          in: query
          schema:
            type: string
            enum: [text, multimodal]
          description: Filter by query type
        - name: mode
          in: query
          schema:
            type: string
            enum: [local, global, hybrid, naive, mix, bypass]
          description: Filter by query mode
        - name: date_from
          in: query
          schema:
            type: string
            format: date
          description: Filter queries from this date
        - name: date_to
          in: query
          schema:
            type: string
            format: date
          description: Filter queries to this date
        - name: search
          in: query
          schema:
            type: string
          description: Search queries by text content
      responses:
        '200':
          description: Query history retrieved successfully
          content:
            application/json:
              schema:
                type: object
                properties:
                  success:
                    type: boolean
                    const: true
                  data:
                    type: object
                    properties:
                      queries:
                        type: array
                        items:
                          type: object
                          properties:
                            query_id:
                              type: string
                            query:
                              type: string
                            type:
                              type: string
                              enum: [text, multimodal]
                            mode:
                              type: string
                            created_at:
                              type: string
                              format: date-time
                            processing_time_ms:
                              type: number
                            sources_count:
                              type: integer
                            cached:
                              type: boolean
                            vlm_enhanced:
                              type: boolean
                      pagination:
                        $ref: '#/components/schemas/PaginationInfo'
                      analytics:
                        type: object
                        properties:
                          total_queries:
                            type: integer
                          avg_processing_time:
                            type: number
                          cache_hit_rate:
                            type: number
                          most_used_mode:
                            type: string

  # Real-time Streaming Endpoints
  /stream/progress/{jobId}:
    get:
      summary: Stream processing progress (SSE)
      description: |
        Server-Sent Events stream for real-time processing progress updates.
        Provides detailed progress information for document processing and query execution jobs.
        Automatically closes when job completes or fails.
      operationId: streamProgress
      tags:
        - Streaming
      parameters:
        - name: jobId
          in: path
          required: true
          schema:
            type: string
          description: Job ID to monitor
      responses:
        '200':
          description: SSE stream established
          content:
            text/event-stream:
              schema:
                type: string
              example: |
                event: connected
                data: {"job_id": "job-123", "timestamp": "2024-01-01T12:00:00Z", "estimated_duration": 30000}
                
                event: progress
                data: {"job_id": "job-123", "status": "processing", "progress": 25, "stage": "parsing", "message": "Processing page 5 of 20", "timestamp": "2024-01-01T12:00:15Z"}
                
                event: progress
                data: {"job_id": "job-123", "status": "processing", "progress": 50, "stage": "embedding", "message": "Generating embeddings for 450 chunks", "timestamp": "2024-01-01T12:00:30Z"}
                
                event: progress
                data: {"job_id": "job-123", "status": "processing", "progress": 75, "stage": "indexing", "message": "Building knowledge graph", "timestamp": "2024-01-01T12:00:45Z"}
                
                event: complete
                data: {"job_id": "job-123", "status": "completed", "progress": 100, "result": {"doc_id": "doc-456", "chunks_count": 45, "entities_count": 123, "relations_count": 87}, "total_time_ms": 28500, "timestamp": "2024-01-01T12:00:58Z"}
                
                event: error
                data: {"job_id": "job-123", "status": "failed", "error": {"code": "PROCESSING_ERROR", "message": "Failed to parse document", "details": "Unsupported file format"}, "timestamp": "2024-01-01T12:00:30Z"}
        '404':
          description: Job not found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

  /stream/batch-progress/{batchId}:
    get:
      summary: Stream batch processing progress (SSE)
      description: |
        Server-Sent Events stream for batch processing progress.
        Provides updates for all jobs in a batch with individual and overall progress.
      operationId: streamBatchProgress
      tags:
        - Streaming
      parameters:
        - name: batchId
          in: path
          required: true
          schema:
            type: string
          description: Batch ID to monitor
      responses:
        '200':
          description: Batch SSE stream established
          content:
            text/event-stream:
              schema:
                type: string
              example: |
                event: batch_started
                data: {"batch_id": "batch-789", "total_jobs": 5, "timestamp": "2024-01-01T12:00:00Z"}
                
                event: job_progress
                data: {"batch_id": "batch-789", "job_id": "job-001", "filename": "doc1.pdf", "progress": 30, "stage": "parsing", "timestamp": "2024-01-01T12:00:15Z"}
                
                event: batch_progress
                data: {"batch_id": "batch-789", "completed_jobs": 2, "failed_jobs": 0, "active_jobs": 3, "overall_progress": 40, "timestamp": "2024-01-01T12:01:00Z"}
                
                event: batch_complete
                data: {"batch_id": "batch-789", "total_jobs": 5, "completed_jobs": 4, "failed_jobs": 1, "total_time_ms": 125000, "timestamp": "2024-01-01T12:02:05Z"}

  /stream/query/{queryId}:
    get:
      summary: Stream query results (SSE)
      description: |
        Server-Sent Events stream for real-time query result streaming.
        Provides progressive query results as they are generated by the LLM.
      operationId: streamQueryResults
      tags:
        - Streaming
      parameters:
        - name: queryId
          in: path
          required: true
          schema:
            type: string
          description: Query ID to stream
      responses:
        '200':
          description: Query SSE stream established
          content:
            text/event-stream:
              schema:
                type: string
              example: |
                event: query_start
                data: {"query_id": "query-456", "query": "What is machine learning?", "estimated_time": 8000, "timestamp": "2024-01-01T12:00:00Z"}
                
                event: retrieval_complete
                data: {"query_id": "query-456", "sources_found": 15, "search_time_ms": 450, "timestamp": "2024-01-01T12:00:01Z"}
                
                event: generation_chunk
                data: {"query_id": "query-456", "chunk": "Machine learning is a subset of", "chunk_index": 0, "timestamp": "2024-01-01T12:00:02Z"}
                
                event: generation_chunk  
                data: {"query_id": "query-456", "chunk": " artificial intelligence that", "chunk_index": 1, "timestamp": "2024-01-01T12:00:02Z"}
                
                event: query_complete
                data: {"query_id": "query-456", "final_result": "Machine learning is a subset of artificial intelligence...", "sources": [...], "total_time_ms": 7850, "timestamp": "2024-01-01T12:00:07Z"}

  # WebSocket Connection Endpoint
  /ws:
    get:
      summary: WebSocket connection endpoint
      description: |
        Establish WebSocket connection for real-time bidirectional communication.
        Supports authentication via query parameters or handshake headers.
        Enables real-time job progress, query streaming, and system notifications.
        
        **Connection URL**: `wss://api.rag-anything.com/ws?token=<jwt>` or `wss://api.rag-anything.com/ws?apiKey=<key>`
        
        **Supported Events**:
        - `subscribe:job` - Subscribe to job progress updates
        - `subscribe:document` - Subscribe to document processing updates  
        - `subscribe:query` - Subscribe to query progress updates
        - `stream:query` - Execute streaming query
        - `job:progress` - Receive job progress updates
        - `query:chunk` - Receive query result chunks
        - `query:complete` - Receive query completion
        - `system:notification` - Receive system notifications
        
        **Authentication**: Include JWT token or API key in connection parameters
        **Rate Limiting**: 50 events per minute per connection
        **Heartbeat**: 30-second ping/pong to maintain connection
      operationId: connectWebSocket
      tags:
        - Streaming
      parameters:
        - name: token
          in: query
          schema:
            type: string
          description: JWT token for authentication
        - name: apiKey
          in: query
          schema:
            type: string
          description: API key for authentication
      responses:
        '101':
          description: WebSocket connection established
        '401':
          description: Authentication failed
        '429':
          description: Rate limit exceeded

  # Configuration Endpoints
  /config:
    get:
      summary: Get current configuration
      description: |
        Retrieve the current system configuration with sensitive values masked.
        Includes RAG processing settings, model configurations, and system limits.
      operationId: getConfig
      tags:
        - Configuration
      responses:
        '200':
          description: Configuration retrieved successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ConfigResponse'
              example:
                success: true
                data:
                  directory:
                    working_dir: "./rag_storage"
                    parser_output_dir: "./output"
                  parsing:
                    parser: "mineru"
                    parse_method: "auto"
                    display_content_stats: true
                  multimodal_processing:
                    enable_image_processing: true
                    enable_table_processing: true
                    enable_equation_processing: true
                  context_extraction:
                    context_window: 1
                    context_mode: "page"
                    max_context_tokens: 2000
                  batch_processing:
                    max_concurrent_files: 2
                    recursive_folder_processing: true
                  rate_limits:
                    jwt_users: 5000
                    api_key_users: 1000
                    concurrent_uploads: 10
                  models:
                    llm_model: "gpt-4"
                    vision_model: "gpt-4-vision"
                    embedding_model: "text-embedding-ada-002"
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'

    patch:
      summary: Update configuration
      description: |
        Update system configuration dynamically. Only specified fields will be updated.
        Some changes may require processor reinitialization or service restart.
        Configuration changes are logged and can trigger system notifications.
      operationId: updateConfig
      tags:
        - Configuration
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ConfigUpdateRequest'
            example:
              multimodal_processing:
                enable_image_processing: false
              batch_processing:
                max_concurrent_files: 4
              rate_limits:
                api_key_users: 1500
      responses:
        '200':
          description: Configuration updated successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ConfigUpdateResponse'
              example:
                success: true
                data:
                  updated_fields:
                    - "multimodal_processing.enable_image_processing"
                    - "batch_processing.max_concurrent_files"
                    - "rate_limits.api_key_users"
                  warnings:
                    - "Changes require processor reinitialization"
                    - "Rate limit changes take effect immediately"
                  restart_required: false
                  changes_applied_at: "2024-01-01T12:00:00Z"
        '400':
          $ref: '#/components/responses/BadRequest'
        '422':
          $ref: '#/components/responses/ValidationError'

  /config/reset:
    post:
      summary: Reset configuration to defaults
      description: |
        Reset all configuration parameters to their default values.
        This operation requires admin privileges and may cause service disruption.
      operationId: resetConfig
      tags:
        - Configuration
      responses:
        '200':
          description: Configuration reset successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SuccessResponse'
              example:
                success: true
                data:
                  message: "Configuration reset to defaults"
                  reset_at: "2024-01-01T12:00:00Z"
                  restart_required: true
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'

  # Status and Health Endpoints
  /health:
    get:
      summary: Basic health check
      description: |
        Basic health check endpoint for load balancers and monitoring systems.
        Returns HTTP 200 when healthy, 503 when unhealthy.
        Includes service status and basic system information.
      operationId: healthCheck
      tags:
        - Health
      security: []
      responses:
        '200':
          description: Service is healthy
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/HealthResponse'
              example:
                status: "healthy"
                timestamp: "2024-01-01T12:00:00Z"
                version: "1.0.0"
                uptime_seconds: 3600
                checks:
                  database: "healthy"
                  redis: "healthy"
                  python_processes: "healthy"
                  job_queue: "healthy"
                  file_system: "healthy"
        '503':
          description: Service is unhealthy
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/HealthResponse'
              example:
                status: "unhealthy"
                timestamp: "2024-01-01T12:00:00Z"
                version: "1.0.0"
                uptime_seconds: 3600
                checks:
                  database: "unhealthy"
                  redis: "healthy"
                  python_processes: "degraded"
                  job_queue: "healthy"
                  file_system: "healthy"

  /health/ready:
    get:
      summary: Readiness check
      description: |
        Kubernetes readiness probe endpoint.
        Returns 200 when service is ready to accept traffic.
      operationId: readinessCheck
      tags:
        - Health
      security: []
      responses:
        '200':
          description: Service is ready
          content:
            application/json:
              schema:
                type: object
                properties:
                  ready: 
                    type: boolean
                    const: true
                  timestamp:
                    type: string
                    format: date-time
        '503':
          description: Service is not ready

  /status:
    get:
      summary: Detailed system status
      description: |
        Get comprehensive system status including performance metrics,
        processing queue status, storage statistics, and Python process health.
        Provides detailed diagnostics for system administrators.
      operationId: getStatus
      tags:
        - Health
      responses:
        '200':
          description: System status retrieved successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/StatusResponse'
              example:
                success: true
                data:
                  system:
                    status: "operational"
                    version: "1.0.0"
                    uptime_seconds: 86400
                    node_version: "20.9.0"
                    python_version: "3.11.0"
                  performance:
                    memory_usage_mb: 512.5
                    cpu_usage_percent: 25.5
                    active_connections: 15
                    requests_per_minute: 45
                    avg_response_time_ms: 150
                  processing:
                    queue_length: 3
                    active_jobs: 2
                    completed_jobs_today: 150
                    failed_jobs_today: 2
                    python_processes_healthy: 4
                    python_processes_total: 5
                  storage:
                    lightrag_initialized: true
                    total_documents: 1250
                    total_chunks: 15000
                    storage_size_mb: 850.5
                    vector_db_status: "healthy"
                    knowledge_graph_nodes: 5420
                    knowledge_graph_relations: 8950
        '401':
          $ref: '#/components/responses/Unauthorized'

  /processors/info:
    get:
      summary: Get processor information
      description: |
        Get information about available multimodal processors and their capabilities.
        Includes model information, supported formats, and processing statistics.
      operationId: getProcessorInfo
      tags:
        - Health
      responses:
        '200':
          description: Processor information retrieved successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ProcessorInfoResponse'
              example:
                success: true
                data:
                  status: "initialized"
                  processors:
                    image:
                      class: "ImageModalProcessor"
                      supports: ["jpg", "png", "gif", "webp", "tiff"]
                      enabled: true
                      model: "gpt-4-vision"
                    table:
                      class: "TableModalProcessor"
                      supports: ["html", "markdown", "csv"]
                      enabled: true
                      model: "table-transformer"
                    equation:
                      class: "EquationModalProcessor"
                      supports: ["latex", "mathml", "text"]
                      enabled: true
                      model: "mathpix-ocr"
                  models:
                    llm_model: "gpt-4"
                    vision_model: "gpt-4-vision"
                    embedding_model: "text-embedding-ada-002"
                  config:
                    enable_image_processing: true
                    enable_table_processing: true
                    enable_equation_processing: true

  # Document Management Endpoints
  /documents:
    get:
      summary: List documents
      description: |
        List processed documents with pagination, filtering, and search capabilities.
        Supports filtering by status, type, date range, and full-text search.
        Includes document metadata, processing statistics, and source information.
      operationId: listDocuments
      tags:
        - Document Management
      parameters:
        - name: page
          in: query
          schema:
            type: integer
            minimum: 1
            default: 1
          description: Page number for pagination
        - name: limit
          in: query
          schema:
            type: integer
            minimum: 1
            maximum: 100
            default: 20
          description: Number of documents per page
        - name: status
          in: query
          schema:
            type: string
            enum: [queued, processing, completed, failed]
          description: Filter by processing status
        - name: type
          in: query
          schema:
            type: string
          description: Filter by file type (pdf, docx, image, etc.)
        - name: search
          in: query
          schema:
            type: string
          description: Full-text search across document content
        - name: sort
          in: query
          schema:
            type: string
            enum: [created_at, updated_at, filename, size, relevance]
            default: created_at
          description: Sort field
        - name: order
          in: query
          schema:
            type: string
            enum: [asc, desc]
            default: desc
          description: Sort order
        - name: date_from
          in: query
          schema:
            type: string
            format: date
          description: Filter documents from this date
        - name: date_to
          in: query
          schema:
            type: string
            format: date
          description: Filter documents to this date
      responses:
        '200':
          description: Documents retrieved successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/DocumentListResponse'
              example:
                success: true
                data:
                  documents:
                    - doc_id: "doc-abc123"
                      filename: "ml_paper.pdf"
                      status: "completed"
                      created_at: "2024-01-01T10:00:00Z"
                      updated_at: "2024-01-01T10:05:00Z"
                      chunks_count: 45
                      file_size: 2048576
                      content_types: ["text", "image", "table"]
                      processing_time_ms: 28500
                  pagination:
                    current_page: 1
                    per_page: 20
                    total_pages: 5
                    total_documents: 95
                  filters:
                    status: ["queued", "processing", "completed", "failed"]
                    type: ["pdf", "docx", "txt", "image"]
                    content_types: ["text", "image", "table", "equation"]
        '400':
          $ref: '#/components/responses/BadRequest'

  /documents/{docId}:
    get:
      summary: Get document details
      description: |
        Get detailed information about a specific document including processing status,
        content analysis, chunk information, and knowledge graph integration details.
      operationId: getDocument
      tags:
        - Document Management
      parameters:
        - name: docId
          in: path
          required: true
          schema:
            type: string
          description: Document ID
      responses:
        '200':
          description: Document details retrieved successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/DocumentDetailsResponse'
              example:
                success: true
                data:
                  doc_id: "doc-abc123"
                  filename: "ml_paper.pdf"
                  status: "completed"
                  created_at: "2024-01-01T10:00:00Z"
                  updated_at: "2024-01-01T10:05:00Z"
                  chunks_count: 45
                  file_size: 2048576
                  content_types: ["text", "image", "table"]
                  processing_details:
                    text_processed: true
                    multimodal_processed: true
                    chunks_count: 45
                    entities_count: 156
                    relations_count: 89
                    processing_time_ms: 28500
                    parser_used: "mineru"
                    vlm_analysis_time_ms: 5400
                  content_analysis:
                    text_blocks: 35
                    image_blocks: 8
                    table_blocks: 3
                    equation_blocks: 1
                    total_tokens: 12500
                    avg_chunk_size: 275
                  file_info:
                    filename: "ml_paper.pdf"
                    size: 2048576
                    type: "application/pdf"
                    checksum: "sha256:abc123def456..."
                    pages: 20
        '404':
          $ref: '#/components/responses/NotFound'

    delete:
      summary: Delete document
      description: |
        Remove document and all associated data from the system.
        This operation cannot be undone and will cancel any in-progress processing.
        Cleans up all related chunks, embeddings, and knowledge graph data.
      operationId: deleteDocument
      tags:
        - Document Management
      parameters:
        - name: docId
          in: path
          required: true
          schema:
            type: string
          description: Document ID
      responses:
        '200':
          description: Document deleted successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/DocumentDeleteResponse'
              example:
                success: true
                data:
                  doc_id: "doc-abc123"
                  deleted: true
                  cleanup_summary:
                    chunks_removed: 45
                    entities_removed: 156
                    relations_removed: 89
                    files_removed: 3
                    storage_freed_mb: 15.2
                  processing_cancelled: false
                  deleted_at: "2024-01-01T12:00:00Z"
        '404':
          $ref: '#/components/responses/NotFound'

  /documents/{docId}/status:
    get:
      summary: Get document processing status
      description: |
        Get current processing status and detailed progress for a specific document.
        Includes real-time progress information and estimated completion time.
      operationId: getDocumentStatus
      tags:
        - Document Management
      parameters:
        - name: docId
          in: path
          required: true
          schema:
            type: string
          description: Document ID
      responses:
        '200':
          description: Document status retrieved successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/DocumentStatusResponse'
              example:
                success: true
                data:
                  doc_id: "doc-abc123"
                  status: "processing"
                  progress: 65
                  current_stage: "embedding_generation"
                  current_step: "Processing chunk 30 of 45"
                  estimated_completion: "2024-01-01T12:03:00Z"
                  processing_time_elapsed_ms: 18500
                  job_id: "job-def456"
                  stages_completed:
                    - "file_validation"
                    - "document_parsing"
                    - "content_extraction"
                    - "multimodal_analysis"
                  stages_remaining:
                    - "embedding_generation"
                    - "knowledge_graph_integration"
                    - "indexing"
        '404':
          $ref: '#/components/responses/NotFound'

  /documents/{docId}/chunks:
    get:
      summary: Get document chunks
      description: |
        Retrieve processed chunks for a document with pagination and filtering.
        Useful for inspecting document processing results and debugging.
      operationId: getDocumentChunks
      tags:
        - Document Management
      parameters:
        - name: docId
          in: path
          required: true
          schema:
            type: string
          description: Document ID
        - name: page
          in: query
          schema:
            type: integer
            minimum: 1
            default: 1
          description: Page number
        - name: limit
          in: query
          schema:
            type: integer
            minimum: 1
            maximum: 100
            default: 20
          description: Chunks per page
        - name: type
          in: query
          schema:
            type: string
            enum: [text, image, table, equation]
          description: Filter by chunk type
      responses:
        '200':
          description: Document chunks retrieved successfully
          content:
            application/json:
              schema:
                type: object
                properties:
                  success:
                    type: boolean
                    const: true
                  data:
                    type: object
                    properties:
                      chunks:
                        type: array
                        items:
                          type: object
                          properties:
                            chunk_id:
                              type: string
                            type:
                              type: string
                            content:
                              type: string
                            page_number:
                              type: integer
                            tokens:
                              type: integer
                            embedding_model:
                              type: string
                            created_at:
                              type: string
                              format: date-time
                      pagination:
                        $ref: '#/components/schemas/PaginationInfo'

components:
  securitySchemes:
    ApiKeyAuth:
      type: apiKey
      in: header
      name: X-API-Key
      description: API key for authentication
    BearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
      description: JWT token authentication

  schemas:
    # User and Authentication Schemas
    UserProfile:
      type: object
      properties:
        id:
          type: string
          format: uuid
        email:
          type: string
          format: email
        role:
          type: string
          enum: [user, admin, readonly]
        created_at:
          type: string
          format: date-time
        last_login_at:
          type: string
          format: date-time
        preferences:
          type: object
          properties:
            default_query_mode:
              type: string
              enum: [local, global, hybrid, naive, mix, bypass]
            vlm_enhanced_by_default:
              type: boolean

    ApiKeyInfo:
      type: object
      properties:
        id:
          type: string
          format: uuid
        name:
          type: string
        key_prefix:
          type: string
          description: First 10 characters of the API key
        permissions:
          type: array
          items:
            type: string
        rate_limit:
          type: integer
        is_active:
          type: boolean
        last_used_at:
          type: string
          format: date-time
        expires_at:
          type: string
          format: date-time
        created_at:
          type: string
          format: date-time

    # Request Schemas
    TextQueryRequest:
      type: object
      required:
        - query
      properties:
        query:
          type: string
          minLength: 1
          description: Query text
          example: "What is machine learning and how does it work?"
        mode:
          type: string
          enum: [local, global, hybrid, naive, mix, bypass]
          default: mix
          description: Query retrieval mode
        vlm_enhanced:
          type: boolean
          default: false
          description: Enable VLM-enhanced query processing
        stream:
          type: boolean
          default: false
          description: Enable streaming response
        top_k:
          type: integer
          minimum: 1
          maximum: 100
          default: 10
          description: Number of top results to return
        max_tokens:
          type: integer
          minimum: 1
          maximum: 8000
          default: 2000
          description: Maximum tokens in response
        temperature:
          type: number
          minimum: 0
          maximum: 2
          default: 0.7
          description: Response creativity (0 = deterministic, 2 = very creative)
        context_window:
          type: integer
          minimum: 0
          maximum: 5
          default: 1
          description: Number of surrounding chunks to include for context

    MultimodalQueryRequest:
      type: object
      required:
        - query
        - multimodal_content
      properties:
        query:
          type: string
          minLength: 1
          description: Base query text
          example: "Analyze this chart and explain the trends"
        multimodal_content:
          type: array
          minItems: 1
          items:
            $ref: '#/components/schemas/MultimodalContent'
          description: List of multimodal content items
        mode:
          type: string
          enum: [local, global, hybrid, naive, mix, bypass]
          default: mix
        stream:
          type: boolean
          default: false
        top_k:
          type: integer
          minimum: 1
          maximum: 100
          default: 10
        max_tokens:
          type: integer
          minimum: 1
          maximum: 8000
          default: 2000
        temperature:
          type: number
          minimum: 0
          maximum: 2
          default: 0.7

    MultimodalContent:
      type: object
      discriminator:
        propertyName: type
      oneOf:
        - $ref: '#/components/schemas/ImageContent'
        - $ref: '#/components/schemas/TableContent'
        - $ref: '#/components/schemas/EquationContent'

    ImageContent:
      type: object
      required:
        - type
      properties:
        type:
          type: string
          enum: [image]
        img_path:
          type: string
          description: Path to image file (server-side)
        data:
          type: string
          format: byte
          description: Base64-encoded image data
        format:
          type: string
          enum: [jpeg, jpg, png, bmp, tiff, gif, webp]
          description: Image format (required when using data field)
        analysis_options:
          type: object
          properties:
            extract_text:
              type: boolean
              default: true
            detect_objects:
              type: boolean
              default: false
            analyze_charts:
              type: boolean
              default: true

    TableContent:
      type: object
      required:
        - type
        - table_data
      properties:
        type:
          type: string
          enum: [table]
        table_data:
          type: string
          description: Table data in markdown, HTML, or CSV format
          example: "| Column 1 | Column 2 |\n|----------|----------|\n| Value 1  | Value 2  |"
        format:
          type: string
          enum: [markdown, html, csv]
          default: markdown
        analysis_options:
          type: object
          properties:
            analyze_trends:
              type: boolean
              default: true
            extract_statistics:
              type: boolean
              default: true

    EquationContent:
      type: object
      required:
        - type
        - equation
      properties:
        type:
          type: string
          enum: [equation]
        equation:
          type: string
          description: Mathematical equation in LaTeX, MathML, or text format
          example: "E = mc^2"
        format:
          type: string
          enum: [latex, mathml, text]
          default: text

    ContentListRequest:
      type: object
      required:
        - content_list
      properties:
        content_list:
          type: array
          minItems: 1
          items:
            $ref: '#/components/schemas/ContentItem'
          description: List of pre-parsed content items
        file_path:
          type: string
          description: Original file path or name
        doc_id:
          type: string
          description: Custom document ID
        display_stats:
          type: boolean
          default: true

    ContentItem:
      type: object
      discriminator:
        propertyName: type
      oneOf:
        - $ref: '#/components/schemas/TextContentItem'
        - $ref: '#/components/schemas/ImageContentItem'
        - $ref: '#/components/schemas/TableContentItem'
        - $ref: '#/components/schemas/EquationContentItem'

    TextContentItem:
      type: object
      required:
        - type
        - text
      properties:
        type:
          type: string
          enum: [text]
        text:
          type: string
          description: Text content
        page_idx:
          type: integer
          minimum: 0
          description: Page index (0-based)
        section:
          type: string
          description: Section or heading title
        font_size:
          type: number
          description: Font size for importance weighting

    ImageContentItem:
      type: object
      required:
        - type
        - img_path
      properties:
        type:
          type: string
          enum: [image]
        img_path:
          type: string
          description: Absolute path to image file
        img_caption:
          type: array
          items:
            type: string
          description: Image captions
        img_footnote:
          type: array
          items:
            type: string
          description: Image footnotes
        page_idx:
          type: integer
          minimum: 0
          description: Page index (0-based)

    TableContentItem:
      type: object
      required:
        - type
        - table_body
      properties:
        type:
          type: string
          enum: [table]
        table_body:
          type: string
          description: Table content in markdown format
        table_caption:
          type: array
          items:
            type: string
          description: Table captions
        table_footnote:
          type: array
          items:
            type: string
          description: Table footnotes
        page_idx:
          type: integer
          minimum: 0
          description: Page index (0-based)

    EquationContentItem:
      type: object
      required:
        - type
        - equation
      properties:
        type:
          type: string
          enum: [equation]
        equation:
          type: string
          description: Mathematical equation
        page_idx:
          type: integer
          minimum: 0
          description: Page index (0-based)

    ConfigUpdateRequest:
      type: object
      properties:
        directory:
          type: object
          properties:
            working_dir:
              type: string
            parser_output_dir:
              type: string
        parsing:
          type: object
          properties:
            parser:
              type: string
              enum: [mineru, docling]
            parse_method:
              type: string
              enum: [auto, ocr, txt]
            display_content_stats:
              type: boolean
        multimodal_processing:
          type: object
          properties:
            enable_image_processing:
              type: boolean
            enable_table_processing:
              type: boolean
            enable_equation_processing:
              type: boolean
            vision_model:
              type: string
              enum: [gpt-4-vision, claude-3-vision, gemini-pro-vision]
        context_extraction:
          type: object
          properties:
            context_window:
              type: integer
              minimum: 0
              maximum: 5
            context_mode:
              type: string
              enum: [page, chunk, document]
            max_context_tokens:
              type: integer
              minimum: 100
              maximum: 8000
        batch_processing:
          type: object
          properties:
            max_concurrent_files:
              type: integer
              minimum: 1
              maximum: 20
            recursive_folder_processing:
              type: boolean
        rate_limits:
          type: object
          properties:
            jwt_users:
              type: integer
              minimum: 100
              maximum: 50000
            api_key_users:
              type: integer
              minimum: 100
              maximum: 10000
            concurrent_uploads:
              type: integer
              minimum: 1
              maximum: 50
        models:
          type: object
          properties:
            llm_model:
              type: string
            vision_model:
              type: string
            embedding_model:
              type: string

    # Response Schemas
    SuccessResponse:
      type: object
      properties:
        success:
          type: boolean
          const: true
        data:
          type: object
          description: Response data
        meta:
          $ref: '#/components/schemas/ResponseMeta'

    ErrorResponse:
      type: object
      properties:
        success:
          type: boolean
          const: false
        error:
          $ref: '#/components/schemas/ErrorDetails'

    ErrorDetails:
      type: object
      properties:
        code:
          type: string
          description: Error code
          example: "VALIDATION_ERROR"
        message:
          type: string
          description: Human-readable error message
          example: "Request validation failed"
        details:
          type: object
          description: Additional error details
        request_id:
          type: string
          description: Request correlation ID
          example: "req-123456"
        timestamp:
          type: string
          format: date-time
          description: Error timestamp
        documentation_url:
          type: string
          format: uri
          description: Link to error documentation

    ResponseMeta:
      type: object
      properties:
        request_id:
          type: string
          example: "req-123456"
        timestamp:
          type: string
          format: date-time
          example: "2024-01-01T12:00:00Z"
        processing_time_ms:
          type: integer
          example: 150
        rate_limit:
          type: object
          properties:
            limit:
              type: integer
            remaining:
              type: integer
            reset_at:
              type: string
              format: date-time

    ProcessingResponse:
      allOf:
        - $ref: '#/components/schemas/SuccessResponse'
        - type: object
          properties:
            data:
              type: object
              properties:
                job_id:
                  type: string
                  example: "job-abc123"
                doc_id:
                  type: string
                  example: "doc-def456"
                status:
                  type: string
                  enum: [queued, processing, completed, failed]
                  example: "queued"
                file_info:
                  $ref: '#/components/schemas/FileInfo'
                processing_options:
                  type: object
                  additionalProperties: true
                estimated_completion:
                  type: string
                  format: date-time
                  example: "2024-01-01T12:05:00Z"
                progress_urls:
                  type: object
                  properties:
                    websocket:
                      type: string
                      format: uri
                    sse:
                      type: string
                      format: uri

    BatchProcessingResponse:
      allOf:
        - $ref: '#/components/schemas/SuccessResponse'
        - type: object
          properties:
            data:
              type: object
              properties:
                batch_id:
                  type: string
                  example: "batch-xyz789"
                total_files:
                  type: integer
                  example: 5
                accepted_files:
                  type: integer
                  example: 5
                rejected_files:
                  type: integer
                  example: 0
                files:
                  type: array
                  items:
                    $ref: '#/components/schemas/BatchFileInfo'
                progress_urls:
                  type: object
                  properties:
                    websocket:
                      type: string
                      format: uri
                    sse:
                      type: string
                      format: uri
                estimated_completion:
                  type: string
                  format: date-time

    ContentListResponse:
      allOf:
        - $ref: '#/components/schemas/SuccessResponse'
        - type: object
          properties:
            data:
              type: object
              properties:
                doc_id:
                  type: string
                  example: "custom-doc-id"
                processing_summary:
                  $ref: '#/components/schemas/ProcessingSummary'
                status:
                  type: string
                  enum: [completed, failed]
                processing_time_ms:
                  type: integer
                  example: 1500
                chunks_created:
                  type: integer
                entities_extracted:
                  type: integer
                relations_created:
                  type: integer

    QueryResponse:
      allOf:
        - $ref: '#/components/schemas/SuccessResponse'
        - type: object
          properties:
            data:
              type: object
              properties:
                query_id:
                  type: string
                  example: "query-abc123"
                result:
                  type: string
                  description: Complete query result text
                sources:
                  type: array
                  items:
                    $ref: '#/components/schemas/QuerySource'
                metadata:
                  $ref: '#/components/schemas/QueryMetadata'
                cached:
                  type: boolean
                  description: Whether result was served from cache

    MultimodalQueryResponse:
      allOf:
        - $ref: '#/components/schemas/QueryResponse'
        - type: object
          properties:
            data:
              type: object
              properties:
                processing_details:
                  $ref: '#/components/schemas/MultimodalProcessingDetails'
                multimodal_analysis:
                  type: object
                  properties:
                    images_analyzed:
                      type: integer
                    tables_processed:
                      type: integer
                    equations_parsed:
                      type: integer
                    vision_model_used:
                      type: string

    ConfigResponse:
      allOf:
        - $ref: '#/components/schemas/SuccessResponse'
        - type: object
          properties:
            data:
              $ref: '#/components/schemas/SystemConfig'

    ConfigUpdateResponse:
      allOf:
        - $ref: '#/components/schemas/SuccessResponse'
        - type: object
          properties:
            data:
              type: object
              properties:
                updated_fields:
                  type: array
                  items:
                    type: string
                  example: ["multimodal_processing.enable_image_processing"]
                warnings:
                  type: array
                  items:
                    type: string
                  example: ["Changes require processor reinitialization"]
                restart_required:
                  type: boolean
                  example: false
                changes_applied_at:
                  type: string
                  format: date-time

    HealthResponse:
      type: object
      properties:
        status:
          type: string
          enum: [healthy, unhealthy, degraded, starting]
          example: "healthy"
        timestamp:
          type: string
          format: date-time
          example: "2024-01-01T12:00:00Z"
        version:
          type: string
          example: "1.0.0"
        uptime_seconds:
          type: integer
          example: 3600
        checks:
          type: object
          additionalProperties:
            type: string
            enum: [healthy, unhealthy, unknown]
        response_time_ms:
          type: integer
          description: Total health check duration

    StatusResponse:
      allOf:
        - $ref: '#/components/schemas/SuccessResponse'
        - type: object
          properties:
            data:
              type: object
              properties:
                system:
                  $ref: '#/components/schemas/SystemStatus'
                performance:
                  $ref: '#/components/schemas/PerformanceMetrics'
                processing:
                  $ref: '#/components/schemas/ProcessingMetrics'
                storage:
                  $ref: '#/components/schemas/StorageMetrics'

    ProcessorInfoResponse:
      allOf:
        - $ref: '#/components/schemas/SuccessResponse'
        - type: object
          properties:
            data:
              type: object
              properties:
                status:
                  type: string
                  enum: [initialized, not_initialized, error]
                processors:
                  type: object
                  additionalProperties:
                    $ref: '#/components/schemas/ProcessorInfo'
                models:
                  $ref: '#/components/schemas/ModelInfo'
                config:
                  $ref: '#/components/schemas/SystemConfig'

    DocumentListResponse:
      allOf:
        - $ref: '#/components/schemas/SuccessResponse'
        - type: object
          properties:
            data:
              type: object
              properties:
                documents:
                  type: array
                  items:
                    $ref: '#/components/schemas/DocumentSummary'
                pagination:
                  $ref: '#/components/schemas/PaginationInfo'
                filters:
                  $ref: '#/components/schemas/AvailableFilters'

    DocumentDetailsResponse:
      allOf:
        - $ref: '#/components/schemas/SuccessResponse'
        - type: object
          properties:
            data:
              $ref: '#/components/schemas/DocumentDetails'

    DocumentDeleteResponse:
      allOf:
        - $ref: '#/components/schemas/SuccessResponse'
        - type: object
          properties:
            data:
              type: object
              properties:
                doc_id:
                  type: string
                  example: "doc-abc123"
                deleted:
                  type: boolean
                  example: true
                cleanup_summary:
                  $ref: '#/components/schemas/CleanupSummary'
                processing_cancelled:
                  type: boolean
                  example: false
                deleted_at:
                  type: string
                  format: date-time

    DocumentStatusResponse:
      allOf:
        - $ref: '#/components/schemas/SuccessResponse'
        - type: object
          properties:
            data:
              type: object
              properties:
                doc_id:
                  type: string
                  example: "doc-abc123"
                status:
                  type: string
                  enum: [queued, processing, completed, failed]
                progress:
                  type: integer
                  minimum: 0
                  maximum: 100
                  description: Processing progress percentage
                current_stage:
                  type: string
                  description: Current processing stage
                current_step:
                  type: string
                  description: Current processing step description
                estimated_completion:
                  type: string
                  format: date-time
                processing_time_elapsed_ms:
                  type: integer
                job_id:
                  type: string
                stages_completed:
                  type: array
                  items:
                    type: string
                stages_remaining:
                  type: array
                  items:
                    type: string
                error:
                  type: string
                  description: Error message if status is failed

    # Supporting Schemas
    FileInfo:
      type: object
      properties:
        filename:
          type: string
          example: "document.pdf"
        size:
          type: integer
          example: 2048576
        type:
          type: string
          example: "application/pdf"
        checksum:
          type: string
          example: "sha256:abc123def456..."
        pages:
          type: integer
          example: 20
        uploaded_at:
          type: string
          format: date-time

    BatchFileInfo:
      type: object
      properties:
        filename:
          type: string
          example: "doc1.pdf"
        job_id:
          type: string
          example: "job-abc123"
        doc_id:
          type: string
          example: "doc-def456"
        status:
          type: string
          enum: [queued, processing, completed, failed]
        error:
          type: string
          description: Error message if processing failed
        processing_time_ms:
          type: integer

    ProcessingSummary:
      type: object
      properties:
        total_blocks:
          type: integer
          example: 3
        text_blocks:
          type: integer
          example: 1
        image_blocks:
          type: integer
          example: 1
        table_blocks:
          type: integer
          example: 1
        equation_blocks:
          type: integer
          example: 0

    QuerySource:
      type: object
      properties:
        doc_id:
          type: string
          example: "doc-def456"
        chunk_id:
          type: string
          example: "chunk-ghi789"
        file_path:
          type: string
          example: "document.pdf"
        relevance_score:
          type: number
          example: 0.95
          minimum: 0
          maximum: 1
        content_preview:
          type: string
          example: "Machine learning definition..."
        type:
          type: string
          enum: [text, multimodal]
        modality:
          type: string
          enum: [text, image, table, equation]
        page_number:
          type: integer
          minimum: 1
        section:
          type: string
          description: Section or heading title
        context:
          type: string
          description: Surrounding context for better understanding

    QueryMetadata:
      type: object
      properties:
        mode:
          type: string
          example: "mix"
        processing_time_ms:
          type: integer
          example: 850
        total_chunks_searched:
          type: integer
          example: 1500
        vlm_enhanced:
          type: boolean
          example: true
        model_used:
          type: string
          example: "gpt-4"
        knowledge_graph_nodes:
          type: integer
          example: 145
        knowledge_graph_relations:
          type: integer
          example: 89
        cache_hit:
          type: boolean
          example: false

    MultimodalProcessingDetails:
      type: object
      properties:
        text_analysis:
          type: string
          enum: [completed, failed, skipped]
        image_analysis:
          type: string
          enum: [completed, failed, skipped]
        table_analysis:
          type: string
          enum: [completed, failed, skipped]
        equation_analysis:
          type: string
          enum: [completed, failed, skipped]
        total_processing_time_ms:
          type: integer
          example: 2340
        vision_model_used:
          type: string
          example: "gpt-4-vision"

    SystemConfig:
      type: object
      properties:
        directory:
          type: object
          properties:
            working_dir:
              type: string
              example: "./rag_storage"
            parser_output_dir:
              type: string
              example: "./output"
        parsing:
          type: object
          properties:
            parser:
              type: string
              example: "mineru"
            parse_method:
              type: string
              example: "auto"
            display_content_stats:
              type: boolean
              example: true
        multimodal_processing:
          type: object
          properties:
            enable_image_processing:
              type: boolean
              example: true
            enable_table_processing:
              type: boolean
              example: true
            enable_equation_processing:
              type: boolean
              example: true
        context_extraction:
          type: object
          properties:
            context_window:
              type: integer
              example: 1
            context_mode:
              type: string
              example: "page"
            max_context_tokens:
              type: integer
              example: 2000
        batch_processing:
          type: object
          properties:
            max_concurrent_files:
              type: integer
              example: 2
            supported_file_extensions:
              type: array
              items:
                type: string
              example: [".pdf", ".docx"]
            recursive_folder_processing:
              type: boolean
              example: true
        rate_limits:
          type: object
          properties:
            jwt_users:
              type: integer
              example: 5000
            api_key_users:
              type: integer
              example: 1000
            concurrent_uploads:
              type: integer
              example: 10

    SystemStatus:
      type: object
      properties:
        status:
          type: string
          enum: [operational, degraded, outage]
        version:
          type: string
          example: "1.0.0"
        uptime_seconds:
          type: integer
          example: 3600
        node_version:
          type: string
          example: "20.9.0"
        python_version:
          type: string
          example: "3.11.0"

    PerformanceMetrics:
      type: object
      properties:
        memory_usage_mb:
          type: number
          example: 512.5
        cpu_usage_percent:
          type: number
          example: 25.5
        active_connections:
          type: integer
          example: 15
        requests_per_minute:
          type: integer
          example: 45
        avg_response_time_ms:
          type: number
          example: 150
        cache_hit_rate:
          type: number
          example: 0.75
          minimum: 0
          maximum: 1

    ProcessingMetrics:
      type: object
      properties:
        queue_length:
          type: integer
          example: 3
        active_jobs:
          type: integer
          example: 2
        completed_jobs_today:
          type: integer
          example: 150
        failed_jobs_today:
          type: integer
          example: 2
        python_processes_healthy:
          type: integer
          example: 4
        python_processes_total:
          type: integer
          example: 5
        avg_processing_time_ms:
          type: number
          example: 15000

    StorageMetrics:
      type: object
      properties:
        lightrag_initialized:
          type: boolean
          example: true
        total_documents:
          type: integer
          example: 1250
        total_chunks:
          type: integer
          example: 15000
        storage_size_mb:
          type: number
          example: 850.5
        vector_db_status:
          type: string
          enum: [healthy, degraded, unhealthy]
          example: "healthy"
        knowledge_graph_nodes:
          type: integer
          example: 5420
        knowledge_graph_relations:
          type: integer
          example: 8950

    ProcessorInfo:
      type: object
      properties:
        class:
          type: string
          example: "ImageModalProcessor"
        supports:
          type: array
          items:
            type: string
          example: ["jpg", "png", "gif"]
        enabled:
          type: boolean
          example: true
        model:
          type: string
          example: "gpt-4-vision"
        version:
          type: string
          example: "1.2.0"

    ModelInfo:
      type: object
      properties:
        llm_model:
          type: string
          example: "gpt-4"
        vision_model:
          type: string
          example: "gpt-4-vision"
        embedding_model:
          type: string
          example: "text-embedding-ada-002"
        models_initialized:
          type: boolean
          example: true

    DocumentSummary:
      type: object
      properties:
        doc_id:
          type: string
          example: "doc-abc123"
        filename:
          type: string
          example: "ml_paper.pdf"
        status:
          type: string
          enum: [queued, processing, completed, failed]
        created_at:
          type: string
          format: date-time
        updated_at:
          type: string
          format: date-time
        chunks_count:
          type: integer
          example: 45
        file_size:
          type: integer
          example: 2048576
        content_types:
          type: array
          items:
            type: string
          example: ["text", "image", "table"]
        processing_time_ms:
          type: integer
          example: 28500

    DocumentDetails:
      allOf:
        - $ref: '#/components/schemas/DocumentSummary'
        - type: object
          properties:
            processing_details:
              type: object
              properties:
                text_processed:
                  type: boolean
                multimodal_processed:
                  type: boolean
                chunks_count:
                  type: integer
                entities_count:
                  type: integer
                relations_count:
                  type: integer
                processing_time_ms:
                  type: integer
                parser_used:
                  type: string
                vlm_analysis_time_ms:
                  type: integer
            content_analysis:
              type: object
              properties:
                text_blocks:
                  type: integer
                image_blocks:
                  type: integer
                table_blocks:
                  type: integer
                equation_blocks:
                  type: integer
                total_tokens:
                  type: integer
                avg_chunk_size:
                  type: number
            file_info:
              $ref: '#/components/schemas/FileInfo'

    CleanupSummary:
      type: object
      properties:
        chunks_removed:
          type: integer
          example: 45
        entities_removed:
          type: integer
          example: 120
        relations_removed:
          type: integer
          example: 85
        files_removed:
          type: integer
          example: 3
        storage_freed_mb:
          type: number
          example: 15.2

    PaginationInfo:
      type: object
      properties:
        current_page:
          type: integer
          example: 1
        per_page:
          type: integer
          example: 20
        total_pages:
          type: integer
          example: 5
        total_documents:
          type: integer
          example: 95
        has_next:
          type: boolean
        has_previous:
          type: boolean

    AvailableFilters:
      type: object
      properties:
        status:
          type: array
          items:
            type: string
          example: ["queued", "processing", "completed", "failed"]
        type:
          type: array
          items:
            type: string
          example: ["pdf", "docx", "image"]
        content_types:
          type: array
          items:
            type: string
          example: ["text", "image", "table", "equation"]

  responses:
    BadRequest:
      description: Bad request - invalid input parameters
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
          example:
            success: false
            error:
              code: "BAD_REQUEST"
              message: "Invalid request format"
              request_id: "req-123456"
              timestamp: "2024-01-01T12:00:00Z"

    Unauthorized:
      description: Unauthorized - missing or invalid authentication
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
          example:
            success: false
            error:
              code: "AUTH_MISSING"
              message: "Authentication required"
              request_id: "req-123456"
              timestamp: "2024-01-01T12:00:00Z"

    Forbidden:
      description: Forbidden - insufficient permissions
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
          example:
            success: false
            error:
              code: "PERMISSION_DENIED"
              message: "Insufficient permissions for this operation"
              request_id: "req-123456"
              timestamp: "2024-01-01T12:00:00Z"

    NotFound:
      description: Not found - resource does not exist
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
          example:
            success: false
            error:
              code: "NOT_FOUND"
              message: "Document not found"
              request_id: "req-123456"
              timestamp: "2024-01-01T12:00:00Z"

    PayloadTooLarge:
      description: Payload too large - file size exceeds limits
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
          example:
            success: false
            error:
              code: "FILE_TOO_LARGE"
              message: "File size exceeds maximum allowed size of 100MB"
              request_id: "req-123456"
              timestamp: "2024-01-01T12:00:00Z"

    ValidationError:
      description: Validation error - request data is invalid
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
          example:
            success: false
            error:
              code: "VALIDATION_ERROR"
              message: "Request validation failed"
              details:
                field: "query"
                reason: "Query text cannot be empty"
              request_id: "req-123456"
              timestamp: "2024-01-01T12:00:00Z"

    TooManyRequests:
      description: Too many requests - rate limit exceeded
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
          example:
            success: false
            error:
              code: "RATE_LIMIT_EXCEEDED"
              message: "Rate limit exceeded. Try again later."
              details:
                limit: 1000
                window: "1 hour"
                retry_after: 3600
              request_id: "req-123456"
              timestamp: "2024-01-01T12:00:00Z"

    InternalServerError:
      description: Internal server error - unexpected server failure
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
          example:
            success: false
            error:
              code: "INTERNAL_ERROR"
              message: "An unexpected error occurred"
              request_id: "req-123456"
              timestamp: "2024-01-01T12:00:00Z"

    ServiceUnavailable:
      description: Service unavailable - system overloaded or in maintenance
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
          example:
            success: false
            error:
              code: "SERVICE_UNAVAILABLE"
              message: "Service temporarily unavailable"
              details:
                reason: "System maintenance"
                estimated_recovery: "2024-01-01T13:00:00Z"
              request_id: "req-123456"
              timestamp: "2024-01-01T12:00:00Z"
```

## WebSocket Events Specification

### Connection Events

```typescript
// Connection established
{
  event: 'connected',
  data: {
    connection_id: 'conn-123',
    user_id: 'user-456', 
    timestamp: '2024-01-01T12:00:00Z',
    server_version: '1.0.0'
  }
}

// Authentication failed
{
  event: 'auth_error',
  data: {
    error: 'Invalid token',
    timestamp: '2024-01-01T12:00:00Z'
  }
}
```

### Job Progress Events

```typescript
// Job progress update
{
  event: 'job:progress',
  data: {
    job_id: 'job-123',
    doc_id: 'doc-456',
    status: 'processing',
    progress: 75,
    stage: 'embedding_generation',
    message: 'Processing chunk 30 of 40',
    timestamp: '2024-01-01T12:00:30Z',
    estimated_completion: '2024-01-01T12:01:00Z'
  }
}

// Job completed
{
  event: 'job:complete',
  data: {
    job_id: 'job-123',
    doc_id: 'doc-456', 
    status: 'completed',
    result: {
      chunks_count: 45,
      entities_extracted: 156,
      relations_created: 89,
      processing_time_ms: 28500
    },
    timestamp: '2024-01-01T12:01:00Z'
  }
}

// Job failed
{
  event: 'job:error',
  data: {
    job_id: 'job-123',
    doc_id: 'doc-456',
    status: 'failed',
    error: {
      code: 'PARSING_ERROR',
      message: 'Failed to parse document',
      details: 'Unsupported file format'
    },
    timestamp: '2024-01-01T12:00:45Z'
  }
}
```

### Query Streaming Events

```typescript
// Query started
{
  event: 'query:start',
  data: {
    query_id: 'query-789',
    query: 'What is machine learning?',
    mode: 'mix',
    estimated_time: 8000,
    timestamp: '2024-01-01T12:00:00Z'
  }
}

// Query chunk (streaming response)
{
  event: 'query:chunk',
  data: {
    query_id: 'query-789',
    chunk: 'Machine learning is a subset of',
    chunk_index: 0,
    timestamp: '2024-01-01T12:00:02Z'
  }
}

// Query complete
{
  event: 'query:complete',
  data: {
    query_id: 'query-789',
    result: 'Machine learning is a subset of artificial intelligence...',
    sources: [...],
    metadata: {
      processing_time_ms: 7850,
      chunks_searched: 1500,
      model_used: 'gpt-4'
    },
    timestamp: '2024-01-01T12:00:08Z'
  }
}
```

### System Events

```typescript
// System notification
{
  event: 'system:notification',
  data: {
    type: 'maintenance',
    message: 'Scheduled maintenance in 30 minutes',
    severity: 'warning',
    scheduled_at: '2024-01-01T13:00:00Z',
    timestamp: '2024-01-01T12:30:00Z'
  }
}

// Configuration changed
{
  event: 'system:config_changed',
  data: {
    changed_fields: ['multimodal_processing.enable_image_processing'],
    restart_required: false,
    timestamp: '2024-01-01T12:00:00Z'
  }
}
```

## Usage Examples

### Authentication

```bash
# User login
curl -X POST "https://api.rag-anything.com/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "secure-password"
  }'

# Create API key  
curl -X POST "https://api.rag-anything.com/v1/auth/api-keys" \
  -H "Authorization: Bearer <jwt-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production API Key",
    "permissions": ["documents.read", "documents.write", "query.execute"],
    "rate_limit": 1500
  }'
```

### Document Processing

```bash
# Process single document
curl -X POST "https://api.rag-anything.com/v1/documents/process" \
  -H "X-API-Key: <api-key>" \
  -F "file=@document.pdf" \
  -F "parse_method=auto" \
  -F "display_stats=true" \
  -F "priority=5"

# Process multiple documents in batch
curl -X POST "https://api.rag-anything.com/v1/documents/batch" \
  -H "X-API-Key: <api-key>" \
  -F "files[]=@doc1.pdf" \
  -F "files[]=@doc2.pdf" \
  -F "max_workers=3"
```

### Querying with Real Results

```bash
# Text query with real processing
curl -X POST "https://api.rag-anything.com/v1/query/text" \
  -H "X-API-Key: <api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the key machine learning algorithms discussed?",
    "mode": "mix",
    "vlm_enhanced": true,
    "top_k": 10,
    "context_window": 2
  }'

# Multimodal query with image analysis
curl -X POST "https://api.rag-anything.com/v1/query/multimodal" \
  -H "X-API-Key: <api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Analyze this performance chart and explain the trends",
    "multimodal_content": [
      {
        "type": "image",
        "data": "iVBORw0KGgoAAAANSUhEUgAA...",
        "format": "png",
        "analysis_options": {
          "extract_text": true,
          "analyze_charts": true
        }
      }
    ],
    "mode": "mix"
  }'
```

### Real-time Updates

```javascript
// WebSocket connection for real-time updates
const ws = new WebSocket('wss://api.rag-anything.com/ws?token=<jwt-token>');

ws.onopen = function() {
  // Subscribe to job progress
  ws.send(JSON.stringify({
    event: 'subscribe:job',
    data: { job_id: 'job-123' }
  }));
  
  // Subscribe to document processing
  ws.send(JSON.stringify({
    event: 'subscribe:document', 
    data: { doc_id: 'doc-456' }
  }));
};

ws.onmessage = function(event) {
  const message = JSON.parse(event.data);
  
  switch(message.event) {
    case 'job:progress':
      console.log('Job progress:', message.data.progress + '%');
      break;
    case 'job:complete':
      console.log('Job completed:', message.data.result);
      break;
    case 'query:chunk':
      // Real-time query streaming
      process.stdout.write(message.data.chunk);
      break;
  }
};

// Server-Sent Events for progress tracking  
const eventSource = new EventSource(
  'https://api.rag-anything.com/v1/stream/progress/job-123',
  {
    headers: {
      'Authorization': 'Bearer <jwt-token>'
    }
  }
);

eventSource.addEventListener('progress', function(event) {
  const data = JSON.parse(event.data);
  console.log('Progress update:', data.progress + '%', data.message);
});

eventSource.addEventListener('complete', function(event) {
  const result = JSON.parse(event.data);
  console.log('Processing completed:', result);
  eventSource.close();
});
```

### Streaming Query Results

```bash
# Stream query results via SSE
curl -N -H "X-API-Key: <api-key>" \
  "https://api.rag-anything.com/v1/stream/query/query-456"

# Expected output:
# event: query_start
# data: {"query_id": "query-456", "estimated_time": 8000}
#
# event: generation_chunk
# data: {"chunk": "Machine learning is", "chunk_index": 0}
#
# event: generation_chunk  
# data: {"chunk": " a powerful approach", "chunk_index": 1}
#
# event: query_complete
# data: {"final_result": "Machine learning is a powerful approach...", "sources": [...]}
```

## SDK Generation

This OpenAPI specification supports automatic SDK generation for multiple programming languages with complete WebSocket and SSE support:

- **JavaScript/TypeScript**: Full WebSocket client with reconnection
- **Python**: Real-time event handling with asyncio support
- **Java**: WebSocket client with Spring integration
- **C#**: SignalR-compatible WebSocket implementation
- **Go**: Gorilla WebSocket integration
- **PHP**: ReactPHP WebSocket support
- **Ruby**: EventMachine WebSocket client

## API Design Principles

1. **No Mock Responses**: All endpoints return actual processing results from RAG-Anything Python core
2. **Real-time First**: WebSocket and SSE support for all long-running operations  
3. **Authentication Security**: Database-integrated auth with comprehensive audit logging
4. **Progressive Enhancement**: Graceful fallback from WebSocket to SSE to polling
5. **Comprehensive Monitoring**: Built-in health checks, metrics, and status endpoints
6. **Type Safety**: Complete TypeScript-compatible schemas with validation
7. **Error Transparency**: Detailed error responses with correlation IDs and context
8. **Performance Optimization**: Caching, rate limiting, and connection management built-in