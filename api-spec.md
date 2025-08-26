# RAG-Anything + Graphiti Integration - API Specification

## OpenAPI 3.0 Specification

```yaml
openapi: 3.0.3
info:
  title: RAG-Anything Multimodal API with Backend Abstraction
  version: 2.0.0
  description: |
    REST API for RAG-Anything multimodal document processing with support for both LightRAG and Graphiti backends.
    
    This API provides:
    - Multimodal document processing (PDF, Office, images, text)
    - Backend abstraction (LightRAG for vector search, Graphiti for knowledge graphs)
    - Advanced querying capabilities with cross-modal search
    - Knowledge base management with backend selection
    - Real-time processing with streaming support
    - Enterprise-grade security with comprehensive validation
    - Rate limiting and abuse prevention
    - Comprehensive monitoring and audit logging
    
    ## Backend Selection
    
    Most endpoints support backend selection through:
    - Query parameter: `?backend=lightrag|graphiti`
    - Header: `X-Backend: lightrag|graphiti`
    - Request body field: `"backend": "lightrag|graphiti"`
    
    If no backend is specified, the system defaults to LightRAG for backward compatibility.
    
    ## Authentication & Security
    
    ### Authentication Methods
    - **API Key**: Include `X-API-Key` header with valid API key
    - **JWT Token**: Include `Authorization: Bearer <token>` header
    - **OAuth 2.0**: Standard OAuth 2.0 flow with PKCE (for client applications)
    
    ### Security Features
    - **Rate Limiting**: Automatic rate limiting based on user tier and endpoint
    - **Input Validation**: Comprehensive validation of all inputs
    - **File Upload Security**: Malware scanning and content validation
    - **Audit Logging**: All API calls are logged for security monitoring
    - **IP Whitelisting**: Optional IP restriction for sensitive endpoints
    
    ### Rate Limits
    Default rate limits (per user):
    - **Standard User**: 100 requests/minute, 1000 requests/hour
    - **Premium User**: 500 requests/minute, 5000 requests/hour
    - **Enterprise User**: 1000 requests/minute, 10000 requests/hour
    
    Rate limit headers are included in all responses:
    - `X-RateLimit-Limit`: Request limit per window
    - `X-RateLimit-Remaining`: Requests remaining in current window
    - `X-RateLimit-Reset`: Unix timestamp when the rate limit resets
    
  contact:
    name: RAG-Anything Support
    url: https://github.com/adithya-s-k/RAG-Anything
  license:
    name: MIT
    url: https://opensource.org/licenses/MIT

servers:
  - url: http://localhost:8000
    description: Development server
  - url: https://api.raganything.dev
    description: Production server

paths:
  # Authentication Endpoints
  /api/v1/auth/login:
    post:
      summary: Authenticate user and get access token
      operationId: loginUser
      tags:
        - Authentication
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/LoginRequest'
      responses:
        '200':
          description: Authentication successful
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AuthResponse'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '429':
          $ref: '#/components/responses/RateLimited'

  /api/v1/auth/refresh:
    post:
      summary: Refresh access token using refresh token
      operationId: refreshToken
      tags:
        - Authentication
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/RefreshTokenRequest'
      responses:
        '200':
          description: Token refreshed successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AuthResponse'
        '401':
          $ref: '#/components/responses/Unauthorized'

  /api/v1/auth/logout:
    post:
      summary: Logout user and invalidate tokens
      operationId: logoutUser
      tags:
        - Authentication
      security:
        - BearerAuth: []
        - ApiKeyAuth: []
      responses:
        '200':
          description: Logout successful
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/LogoutResponse'
        '401':
          $ref: '#/components/responses/Unauthorized'

  # Health and Monitoring Endpoints
  /api/v1/health:
    get:
      summary: General system health check
      operationId: getSystemHealth
      tags:
        - Health & Monitoring
      responses:
        '200':
          description: System health status
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/HealthResponse'
              example:
                status: "healthy"
                version: "2.0.0"
                uptime: "2d 4h 23m"
                backend_status:
                  lightrag: "healthy"
                  graphiti: "healthy"
                security_status:
                  authentication_service: "healthy"
                  rate_limiter: "healthy"
                  security_monitor: "healthy"

  /api/v1/health/backend/{backend}:
    get:
      summary: Backend-specific health check
      operationId: getBackendHealth
      tags:
        - Health & Monitoring
      parameters:
        - name: backend
          in: path
          required: true
          schema:
            type: string
            enum: [lightrag, graphiti]
          description: Backend type to check
      responses:
        '200':
          description: Backend health status
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/BackendHealthResponse'

  /api/v1/health/security:
    get:
      summary: Security services health check
      operationId: getSecurityHealth
      tags:
        - Health & Monitoring
      security:
        - BearerAuth: []
        - ApiKeyAuth: []
      responses:
        '200':
          description: Security services status
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SecurityHealthResponse'

  # Document Processing Endpoints
  /api/v1/documents/process:
    post:
      summary: Process a single document with backend selection
      operationId: processDocument
      tags:
        - Document Processing
      security:
        - BearerAuth: []
        - ApiKeyAuth: []
      parameters:
        - $ref: '#/components/parameters/BackendParam'
      requestBody:
        required: true
        content:
          multipart/form-data:
            schema:
              type: object
              properties:
                file:
                  type: string
                  format: binary
                  description: |
                    Document file to process. Supported formats: PDF, DOCX, TXT, MD, PNG, JPG, JPEG.
                    Maximum file size: 100MB.
                    Files are automatically scanned for malware.
                backend:
                  $ref: '#/components/schemas/BackendType'
                config:
                  $ref: '#/components/schemas/ProcessingConfig'
              required:
                - file
      responses:
        '200':
          description: Document processed successfully
          headers:
            X-RateLimit-Limit:
              $ref: '#/components/headers/X-RateLimit-Limit'
            X-RateLimit-Remaining:
              $ref: '#/components/headers/X-RateLimit-Remaining'
            X-RateLimit-Reset:
              $ref: '#/components/headers/X-RateLimit-Reset'
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/DocumentProcessResponse'
        '400':
          $ref: '#/components/responses/BadRequest'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'
        '413':
          $ref: '#/components/responses/FileTooLarge'
        '415':
          $ref: '#/components/responses/UnsupportedMediaType'
        '429':
          $ref: '#/components/responses/RateLimited'
        '500':
          $ref: '#/components/responses/InternalServerError'

  /api/v1/documents/batch:
    post:
      summary: Process multiple documents in batch
      operationId: processBatchDocuments
      tags:
        - Document Processing
      security:
        - BearerAuth: []
        - ApiKeyAuth: []
      parameters:
        - $ref: '#/components/parameters/BackendParam'
      requestBody:
        required: true
        content:
          multipart/form-data:
            schema:
              type: object
              properties:
                files:
                  type: array
                  items:
                    type: string
                    format: binary
                  description: |
                    Multiple document files to process (max 10 files per batch).
                    Each file must meet individual size and type requirements.
                  maxItems: 10
                backend:
                  $ref: '#/components/schemas/BackendType'
                config:
                  $ref: '#/components/schemas/BatchProcessingConfig'
              required:
                - files
      responses:
        '200':
          description: Batch processing initiated
          headers:
            X-RateLimit-Limit:
              $ref: '#/components/headers/X-RateLimit-Limit'
            X-RateLimit-Remaining:
              $ref: '#/components/headers/X-RateLimit-Remaining'
            X-RateLimit-Reset:
              $ref: '#/components/headers/X-RateLimit-Reset'
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/BatchProcessResponse'
        '400':
          $ref: '#/components/responses/BadRequest'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'
        '429':
          $ref: '#/components/responses/RateLimited'

  /api/v1/documents/{document_id}:
    get:
      summary: Get document processing status and results
      operationId: getDocument
      tags:
        - Document Processing
      security:
        - BearerAuth: []
        - ApiKeyAuth: []
      parameters:
        - name: document_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
          description: Unique document identifier
        - $ref: '#/components/parameters/BackendParam'
      responses:
        '200':
          description: Document information retrieved
          headers:
            X-RateLimit-Limit:
              $ref: '#/components/headers/X-RateLimit-Limit'
            X-RateLimit-Remaining:
              $ref: '#/components/headers/X-RateLimit-Remaining'
            X-RateLimit-Reset:
              $ref: '#/components/headers/X-RateLimit-Reset'
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/DocumentInfo'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'
        '404':
          $ref: '#/components/responses/NotFound'
        '429':
          $ref: '#/components/responses/RateLimited'

    delete:
      summary: Remove document from backend storage
      operationId: deleteDocument
      tags:
        - Document Processing
      security:
        - BearerAuth: []
        - ApiKeyAuth: []
      parameters:
        - name: document_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
          description: Unique document identifier
        - $ref: '#/components/parameters/BackendParam'
      responses:
        '200':
          description: Document deleted successfully
          headers:
            X-RateLimit-Limit:
              $ref: '#/components/headers/X-RateLimit-Limit'
            X-RateLimit-Remaining:
              $ref: '#/components/headers/X-RateLimit-Remaining'
            X-RateLimit-Reset:
              $ref: '#/components/headers/X-RateLimit-Reset'
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/DeleteResponse'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'
        '404':
          $ref: '#/components/responses/NotFound'
        '429':
          $ref: '#/components/responses/RateLimited'

  # Query Processing Endpoints
  /api/v1/query:
    post:
      summary: Execute query with backend selection
      operationId: executeQuery
      tags:
        - Query Processing
      security:
        - BearerAuth: []
        - ApiKeyAuth: []
      parameters:
        - $ref: '#/components/parameters/BackendParam'
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/QueryRequest'
      responses:
        '200':
          description: Query executed successfully
          headers:
            X-RateLimit-Limit:
              $ref: '#/components/headers/X-RateLimit-Limit'
            X-RateLimit-Remaining:
              $ref: '#/components/headers/X-RateLimit-Remaining'
            X-RateLimit-Reset:
              $ref: '#/components/headers/X-RateLimit-Reset'
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/QueryResponse'
            application/x-ndjson:
              schema:
                $ref: '#/components/schemas/StreamingQueryResponse'
        '400':
          $ref: '#/components/responses/BadRequest'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'
        '429':
          $ref: '#/components/responses/RateLimited'

  /api/v1/query/multimodal:
    post:
      summary: Execute multimodal query across content types
      operationId: executeMultimodalQuery
      tags:
        - Query Processing
      security:
        - BearerAuth: []
        - ApiKeyAuth: []
      parameters:
        - $ref: '#/components/parameters/BackendParam'
      requestBody:
        required: true
        content:
          multipart/form-data:
            schema:
              type: object
              properties:
                text:
                  type: string
                  description: Text query component
                  maxLength: 10000
                image:
                  type: string
                  format: binary
                  description: |
                    Image query component (optional).
                    Supported formats: PNG, JPG, JPEG.
                    Maximum size: 10MB.
                backend:
                  $ref: '#/components/schemas/BackendType'
                config:
                  $ref: '#/components/schemas/MultimodalQueryConfig'
              required:
                - text
      responses:
        '200':
          description: Multimodal query results
          headers:
            X-RateLimit-Limit:
              $ref: '#/components/headers/X-RateLimit-Limit'
            X-RateLimit-Remaining:
              $ref: '#/components/headers/X-RateLimit-Remaining'
            X-RateLimit-Reset:
              $ref: '#/components/headers/X-RateLimit-Reset'
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/MultimodalQueryResponse'
        '400':
          $ref: '#/components/responses/BadRequest'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'
        '429':
          $ref: '#/components/responses/RateLimited'

  # Backend-Agnostic Knowledge Base Endpoints
  /api/v1/kb/stats:
    get:
      summary: Get knowledge base statistics
      operationId: getKBStats
      tags:
        - Knowledge Base Management
      security:
        - BearerAuth: []
        - ApiKeyAuth: []
      parameters:
        - $ref: '#/components/parameters/BackendParam'
      responses:
        '200':
          description: Knowledge base statistics
          headers:
            X-RateLimit-Limit:
              $ref: '#/components/headers/X-RateLimit-Limit'
            X-RateLimit-Remaining:
              $ref: '#/components/headers/X-RateLimit-Remaining'
            X-RateLimit-Reset:
              $ref: '#/components/headers/X-RateLimit-Reset'
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/KBStats'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'
        '429':
          $ref: '#/components/responses/RateLimited'

  /api/v1/kb/clear:
    delete:
      summary: Clear all data from knowledge base
      operationId: clearKB
      tags:
        - Knowledge Base Management
      security:
        - BearerAuth: []
        - ApiKeyAuth: []
      parameters:
        - $ref: '#/components/parameters/BackendParam'
        - name: confirm
          in: query
          required: true
          schema:
            type: string
            enum: ['DELETE_ALL_DATA']
          description: Confirmation string required for destructive operation
      responses:
        '200':
          description: Knowledge base cleared
          headers:
            X-RateLimit-Limit:
              $ref: '#/components/headers/X-RateLimit-Limit'
            X-RateLimit-Remaining:
              $ref: '#/components/headers/X-RateLimit-Remaining'
            X-RateLimit-Reset:
              $ref: '#/components/headers/X-RateLimit-Reset'
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ClearResponse'
        '400':
          $ref: '#/components/responses/BadRequest'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'
        '429':
          $ref: '#/components/responses/RateLimited'

  # Graphiti-Specific Endpoints
  /api/v1/graphiti/entities:
    get:
      summary: Get entities from knowledge graph
      operationId: getGraphitiEntities
      tags:
        - Graphiti Knowledge Graph
      security:
        - BearerAuth: []
        - ApiKeyAuth: []
      parameters:
        - name: limit
          in: query
          schema:
            type: integer
            default: 50
            minimum: 1
            maximum: 500
        - name: offset
          in: query
          schema:
            type: integer
            default: 0
            minimum: 0
        - name: entity_type
          in: query
          schema:
            type: string
            pattern: '^[a-zA-Z0-9_-]+$'
          description: Filter by entity type (alphanumeric, underscore, dash only)
        - name: search
          in: query
          schema:
            type: string
            maxLength: 1000
          description: Search entities by name/content
      responses:
        '200':
          description: List of entities
          headers:
            X-RateLimit-Limit:
              $ref: '#/components/headers/X-RateLimit-Limit'
            X-RateLimit-Remaining:
              $ref: '#/components/headers/X-RateLimit-Remaining'
            X-RateLimit-Reset:
              $ref: '#/components/headers/X-RateLimit-Reset'
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/EntityListResponse'
        '400':
          $ref: '#/components/responses/BadRequest'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'
        '429':
          $ref: '#/components/responses/RateLimited'

  /api/v1/graphiti/entities/{entity_uuid}:
    get:
      summary: Get specific entity with relationships
      operationId: getGraphitiEntity
      tags:
        - Graphiti Knowledge Graph
      security:
        - BearerAuth: []
        - ApiKeyAuth: []
      parameters:
        - name: entity_uuid
          in: path
          required: true
          schema:
            type: string
            format: uuid
        - name: include_relationships
          in: query
          schema:
            type: boolean
            default: true
        - name: relationship_limit
          in: query
          schema:
            type: integer
            default: 50
            minimum: 1
            maximum: 200
      responses:
        '200':
          description: Entity details with relationships
          headers:
            X-RateLimit-Limit:
              $ref: '#/components/headers/X-RateLimit-Limit'
            X-RateLimit-Remaining:
              $ref: '#/components/headers/X-RateLimit-Remaining'
            X-RateLimit-Reset:
              $ref: '#/components/headers/X-RateLimit-Reset'
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/EntityDetailResponse'
        '400':
          $ref: '#/components/responses/BadRequest'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'
        '404':
          $ref: '#/components/responses/NotFound'
        '429':
          $ref: '#/components/responses/RateLimited'

  # Security and Administration Endpoints
  /api/v1/admin/security/audit:
    get:
      summary: Get security audit logs
      operationId: getSecurityAuditLogs
      tags:
        - Security Administration
      security:
        - BearerAuth: []
      parameters:
        - name: from_date
          in: query
          schema:
            type: string
            format: date-time
        - name: to_date
          in: query
          schema:
            type: string
            format: date-time
        - name: event_type
          in: query
          schema:
            type: string
            enum: [authentication, authorization, file_upload, query, admin]
        - name: limit
          in: query
          schema:
            type: integer
            default: 100
            minimum: 1
            maximum: 1000
      responses:
        '200':
          description: Security audit logs
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SecurityAuditResponse'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'
        '429':
          $ref: '#/components/responses/RateLimited'

  /api/v1/admin/security/threats:
    get:
      summary: Get detected security threats
      operationId: getSecurityThreats
      tags:
        - Security Administration
      security:
        - BearerAuth: []
      parameters:
        - name: severity
          in: query
          schema:
            type: string
            enum: [low, medium, high, critical]
        - name: status
          in: query
          schema:
            type: string
            enum: [active, resolved, investigating]
        - name: limit
          in: query
          schema:
            type: integer
            default: 50
            minimum: 1
            maximum: 500
      responses:
        '200':
          description: Security threats
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SecurityThreatsResponse'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'
        '429':
          $ref: '#/components/responses/RateLimited'

components:
  parameters:
    BackendParam:
      name: backend
      in: query
      schema:
        $ref: '#/components/schemas/BackendType'
      description: Backend type to use for the operation

  headers:
    X-RateLimit-Limit:
      description: The number of allowed requests in the current period
      schema:
        type: integer
    X-RateLimit-Remaining:
      description: The number of requests left in the current period
      schema:
        type: integer
    X-RateLimit-Reset:
      description: Unix timestamp when the rate limit resets
      schema:
        type: integer

  schemas:
    BackendType:
      type: string
      enum: [lightrag, graphiti]
      default: lightrag
      description: Storage backend type

    EpisodeSourceType:
      type: string
      enum: [message, document, media, system]
      description: Source type of the episode

    # Authentication Schemas
    LoginRequest:
      type: object
      properties:
        email:
          type: string
          format: email
          maxLength: 255
        password:
          type: string
          minLength: 8
          maxLength: 128
        mfa_code:
          type: string
          pattern: '^[0-9]{6}$'
          description: Multi-factor authentication code (if enabled)
      required:
        - email
        - password

    RefreshTokenRequest:
      type: object
      properties:
        refresh_token:
          type: string
          description: Valid refresh token
      required:
        - refresh_token

    AuthResponse:
      type: object
      properties:
        access_token:
          type: string
          description: JWT access token
        refresh_token:
          type: string
          description: Refresh token for getting new access tokens
        token_type:
          type: string
          enum: [bearer]
          default: bearer
        expires_in:
          type: integer
          description: Token expiration time in seconds
        user:
          $ref: '#/components/schemas/UserInfo'

    UserInfo:
      type: object
      properties:
        user_id:
          type: string
          format: uuid
        email:
          type: string
          format: email
        role:
          type: string
          enum: [user, admin, enterprise]
        permissions:
          type: array
          items:
            type: string
        rate_limit_tier:
          type: string
          enum: [standard, premium, enterprise]

    LogoutResponse:
      type: object
      properties:
        message:
          type: string
          example: "Successfully logged out"

    # Security Schemas
    SecurityHealthResponse:
      type: object
      properties:
        authentication_service:
          type: string
          enum: [healthy, degraded, unhealthy]
        rate_limiter:
          type: string
          enum: [healthy, degraded, unhealthy]
        input_validator:
          type: string
          enum: [healthy, degraded, unhealthy]
        security_monitor:
          type: string
          enum: [healthy, degraded, unhealthy]
        threat_detection:
          type: string
          enum: [healthy, degraded, unhealthy]
        audit_logging:
          type: string
          enum: [healthy, degraded, unhealthy]
        overall_status:
          type: string
          enum: [healthy, degraded, unhealthy]
        checked_at:
          type: string
          format: date-time

    SecurityAuditResponse:
      type: object
      properties:
        audit_logs:
          type: array
          items:
            $ref: '#/components/schemas/SecurityAuditEvent'
        total_count:
          type: integer
        page_info:
          $ref: '#/components/schemas/PageInfo'

    SecurityAuditEvent:
      type: object
      properties:
        event_id:
          type: string
          format: uuid
        timestamp:
          type: string
          format: date-time
        event_type:
          type: string
          enum: [authentication, authorization, file_upload, query, admin, security_threat]
        user_id:
          type: string
          format: uuid
        ip_address:
          type: string
        user_agent:
          type: string
        endpoint:
          type: string
        method:
          type: string
          enum: [GET, POST, PUT, DELETE, PATCH]
        status_code:
          type: integer
        details:
          type: object
        risk_level:
          type: string
          enum: [low, medium, high, critical]

    SecurityThreatsResponse:
      type: object
      properties:
        threats:
          type: array
          items:
            $ref: '#/components/schemas/SecurityThreat'
        total_count:
          type: integer
        active_threats:
          type: integer
        critical_threats:
          type: integer

    SecurityThreat:
      type: object
      properties:
        threat_id:
          type: string
          format: uuid
        detected_at:
          type: string
          format: date-time
        threat_type:
          type: string
          enum: [malicious_file, injection_attempt, brute_force, anomalous_behavior, rate_limit_abuse]
        severity:
          type: string
          enum: [low, medium, high, critical]
        status:
          type: string
          enum: [active, resolved, investigating]
        source_ip:
          type: string
        user_id:
          type: string
          format: uuid
          nullable: true
        description:
          type: string
        automated_response:
          type: string
          enum: [none, rate_limit, block_ip, disable_account]
        details:
          type: object

    # Request/Response Schemas with Enhanced Security
    ProcessingConfig:
      type: object
      properties:
        parser:
          type: string
          enum: [mineru, docling]
          default: mineru
        enable_image_processing:
          type: boolean
          default: true
        enable_table_processing:
          type: boolean
          default: true
        enable_equation_processing:
          type: boolean
          default: true
        context_window:
          type: integer
          default: 3
          minimum: 1
          maximum: 10
        max_context_tokens:
          type: integer
          default: 1000
          minimum: 100
          maximum: 10000
        # Security settings
        content_filtering:
          type: boolean
          default: true
          description: Enable automatic content filtering for sensitive information
        pii_detection:
          type: boolean
          default: true
          description: Enable PII detection and handling

    BatchProcessingConfig:
      allOf:
        - $ref: '#/components/schemas/ProcessingConfig'
        - type: object
          properties:
            max_concurrent_files:
              type: integer
              default: 3
              minimum: 1
              maximum: 10
            recursive_folder_processing:
              type: boolean
              default: true
            fail_fast:
              type: boolean
              default: false
              description: Stop batch processing on first error

    DocumentProcessResponse:
      type: object
      properties:
        document_id:
          type: string
          format: uuid
        status:
          type: string
          enum: [processing, completed, failed, security_review]
        backend:
          $ref: '#/components/schemas/BackendType'
        processing_stats:
          type: object
          properties:
            total_chunks:
              type: integer
            processing_time:
              type: number
              format: float
            content_types:
              type: array
              items:
                type: string
            security_checks_passed:
              type: boolean
            pii_detected:
              type: boolean
            content_filtered:
              type: boolean
        # Graphiti-specific fields (only present when backend=graphiti)
        graphiti_stats:
          type: object
          properties:
            episodes_created:
              type: integer
            entities_extracted:
              type: integer
            relationships_discovered:
              type: integer
          nullable: true
        # Security metadata
        security_metadata:
          type: object
          properties:
            scan_results:
              type: object
              properties:
                malware_detected:
                  type: boolean
                content_policy_violations:
                  type: array
                  items:
                    type: string
                risk_score:
                  type: number
                  format: float
                  minimum: 0
                  maximum: 1
            access_classification:
              type: string
              enum: [public, internal, confidential, restricted]
            retention_policy:
              type: string
              description: Data retention policy applied

    BatchProcessResponse:
      type: object
      properties:
        batch_id:
          type: string
          format: uuid
        total_files:
          type: integer
        status:
          type: string
          enum: [queued, processing, completed, failed, partial_failure]
        backend:
          $ref: '#/components/schemas/BackendType'
        estimated_completion:
          type: string
          format: date-time
        security_summary:
          type: object
          properties:
            files_passed_security:
              type: integer
            files_failed_security:
              type: integer
            files_in_review:
              type: integer
            total_risk_score:
              type: number
              format: float

    QueryRequest:
      type: object
      properties:
        query:
          type: string
          description: Query text
          minLength: 1
          maxLength: 10000
        backend:
          $ref: '#/components/schemas/BackendType'
        parameters:
          type: object
          description: Backend-specific query parameters
          properties:
            # Common parameters
            limit:
              type: integer
              default: 10
              minimum: 1
              maximum: 100
            include_metadata:
              type: boolean
              default: true
            # LightRAG-specific
            similarity_threshold:
              type: number
              format: float
              minimum: 0
              maximum: 1
            # Graphiti-specific
            center_node_uuid:
              type: string
              format: uuid
            include_communities:
              type: boolean
              default: false
            temporal_filter:
              type: object
              properties:
                from_date:
                  type: string
                  format: date-time
                to_date:
                  type: string
                  format: date-time
            # Security parameters
            content_filter:
              type: boolean
              default: true
              description: Apply content filtering to results
            access_level:
              type: string
              enum: [public, internal, confidential]
              description: Maximum access level for returned content
        streaming:
          type: boolean
          default: false
        # Security context
        security_context:
          type: object
          properties:
            user_clearance:
              type: string
              enum: [public, internal, confidential, restricted]
            data_classification:
              type: array
              items:
                type: string
      required:
        - query

    QueryResponse:
      type: object
      properties:
        query:
          type: string
        backend:
          $ref: '#/components/schemas/BackendType'
        results:
          type: array
          items:
            type: object
            properties:
              content:
                type: string
              relevance_score:
                type: number
                format: float
              source_metadata:
                type: object
              access_level:
                type: string
                enum: [public, internal, confidential, restricted]
              content_warnings:
                type: array
                items:
                  type: string
        metadata:
          type: object
          properties:
            query_time:
              type: number
              format: float
            total_results:
              type: integer
            filtered_results:
              type: integer
              description: Results filtered due to security/access controls
            backend_specific:
              type: object
            security_metadata:
              type: object
              properties:
                content_filtered:
                  type: boolean
                access_controlled:
                  type: boolean
                risk_assessment:
                  type: string
                  enum: [low, medium, high]

    # Common Schemas with Security Enhancements
    HealthResponse:
      type: object
      properties:
        status:
          type: string
          enum: [healthy, degraded, unhealthy]
        version:
          type: string
        uptime:
          type: string
        backend_status:
          type: object
          additionalProperties:
            type: string
        security_status:
          type: object
          properties:
            authentication_service:
              type: string
              enum: [healthy, degraded, unhealthy]
            rate_limiter:
              type: string
              enum: [healthy, degraded, unhealthy]
            security_monitor:
              type: string
              enum: [healthy, degraded, unhealthy]
            threat_detection:
              type: string
              enum: [healthy, degraded, unhealthy]
        last_security_scan:
          type: string
          format: date-time
        active_threats:
          type: integer
        maintenance_mode:
          type: boolean

    BackendHealthResponse:
      type: object
      properties:
        backend:
          $ref: '#/components/schemas/BackendType'
        status:
          type: string
          enum: [healthy, degraded, unhealthy]
        details:
          type: object
          properties:
            connection_status:
              type: string
              enum: [connected, disconnected, limited]
            response_time:
              type: number
              format: float
            error_rate:
              type: number
              format: float
            last_successful_operation:
              type: string
              format: date-time
            security_validation:
              type: boolean
        checked_at:
          type: string
          format: date-time

    ErrorResponse:
      type: object
      properties:
        error:
          type: string
        message:
          type: string
        details:
          type: object
        timestamp:
          type: string
          format: date-time
        request_id:
          type: string
          format: uuid
          description: Unique request identifier for tracking
        security_incident:
          type: boolean
          description: Whether this error triggered a security incident

    # Additional schemas from the original spec remain the same...
    MultimodalQueryConfig:
      type: object
      properties:
        text_weight:
          type: number
          format: float
          default: 0.7
          minimum: 0
          maximum: 1
        image_weight:
          type: number
          format: float
          default: 0.3
          minimum: 0
          maximum: 1
        cross_modal_threshold:
          type: number
          format: float
          default: 0.6
          minimum: 0
          maximum: 1
        content_filtering:
          type: boolean
          default: true

    MultimodalQueryResponse:
      type: object
      properties:
        results:
          type: array
          items:
            type: object
            properties:
              content:
                type: string
              content_type:
                type: string
                enum: [text, image, table, equation]
              similarity_scores:
                type: object
                properties:
                  text:
                    type: number
                    format: float
                  image:
                    type: number
                    format: float
                  combined:
                    type: number
                    format: float
              metadata:
                type: object
              access_level:
                type: string
                enum: [public, internal, confidential, restricted]
        security_metadata:
          type: object
          properties:
            content_filtered:
              type: boolean
            modality_restrictions:
              type: array
              items:
                type: string

    KBStats:
      type: object
      properties:
        backend:
          $ref: '#/components/schemas/BackendType'
        document_count:
          type: integer
        total_size:
          type: integer
          description: Total size in bytes
        last_updated:
          type: string
          format: date-time
        security_stats:
          type: object
          properties:
            documents_with_pii:
              type: integer
            documents_under_review:
              type: integer
            access_restricted_documents:
              type: integer
            last_security_scan:
              type: string
              format: date-time
        # LightRAG-specific stats
        lightrag_stats:
          type: object
          properties:
            chunk_count:
              type: integer
            vector_dimension:
              type: integer
          nullable: true
        # Graphiti-specific stats
        graphiti_stats:
          type: object
          properties:
            episode_count:
              type: integer
            entity_count:
              type: integer
            relationship_count:
              type: integer
            community_count:
              type: integer
          nullable: true

    PageInfo:
      type: object
      properties:
        page:
          type: integer
        per_page:
          type: integer
        total_pages:
          type: integer
        has_next_page:
          type: boolean
        has_previous_page:
          type: boolean

    DeleteResponse:
      type: object
      properties:
        status:
          type: string
          enum: [success, not_found]
        message:
          type: string
        security_cleanup:
          type: boolean
          description: Whether security-related data was also cleaned up

    ClearResponse:
      type: object
      properties:
        backend:
          $ref: '#/components/schemas/BackendType'
        items_deleted:
          type: integer
        security_items_deleted:
          type: integer
        message:
          type: string
        audit_log_id:
          type: string
          format: uuid
          description: Audit log entry for this destructive operation

    # Graphiti-specific schemas (simplified for brevity, same as before)
    EntityListResponse:
      type: object
      properties:
        entities:
          type: array
          items:
            $ref: '#/components/schemas/Entity'
        total_count:
          type: integer
        page_info:
          $ref: '#/components/schemas/PageInfo'

    Entity:
      type: object
      properties:
        uuid:
          type: string
          format: uuid
        name:
          type: string
        entity_type:
          type: string
        summary:
          type: string
        created_at:
          type: string
          format: date-time
        updated_at:
          type: string
          format: date-time
        relationship_count:
          type: integer
        episode_mentions:
          type: integer
        access_level:
          type: string
          enum: [public, internal, confidential, restricted]

    EntityDetailResponse:
      type: object
      properties:
        entity:
          $ref: '#/components/schemas/Entity'
        relationships:
          type: array
          items:
            $ref: '#/components/schemas/EntityRelationship'
        episodes:
          type: array
          items:
            $ref: '#/components/schemas/Episode'

    EntityRelationship:
      type: object
      properties:
        uuid:
          type: string
          format: uuid
        relationship_type:
          type: string
        target_entity:
          $ref: '#/components/schemas/Entity'
        fact:
          type: string
        confidence:
          type: number
          format: float
        valid_at:
          type: string
          format: date-time
        episodes:
          type: array
          items:
            type: string
            format: uuid

    Episode:
      type: object
      properties:
        uuid:
          type: string
          format: uuid
        name:
          type: string
        content:
          type: string
        source:
          $ref: '#/components/schemas/EpisodeSourceType'
        source_description:
          type: string
        valid_at:
          type: string
          format: date-time
        created_at:
          type: string
          format: date-time
        content_type:
          type: string
          enum: [text, image, table, equation]
        entity_count:
          type: integer
        relationship_count:
          type: integer
        access_level:
          type: string
          enum: [public, internal, confidential, restricted]

    DocumentInfo:
      type: object
      properties:
        document_id:
          type: string
          format: uuid
        filename:
          type: string
        content_type:
          type: string
        processed_at:
          type: string
          format: date-time
        backend:
          $ref: '#/components/schemas/BackendType'
        status:
          type: string
          enum: [processing, completed, failed, security_review]
        processing_stats:
          type: object
        access_level:
          type: string
          enum: [public, internal, confidential, restricted]
        security_metadata:
          type: object
          properties:
            malware_scan_result:
              type: string
              enum: [clean, suspicious, infected]
            content_policy_status:
              type: string
              enum: [compliant, review_required, violation]
            pii_classification:
              type: array
              items:
                type: string
        # Backend-specific data
        lightrag_data:
          type: object
          properties:
            chunk_count:
              type: integer
            total_tokens:
              type: integer
          nullable: true
        graphiti_data:
          type: object
          properties:
            episode_uuids:
              type: array
              items:
                type: string
                format: uuid
            entity_count:
              type: integer
            relationship_count:
              type: integer
          nullable: true

    StreamingQueryResponse:
      type: object
      properties:
        chunk:
          type: string
        metadata:
          type: object
        final:
          type: boolean

  responses:
    BadRequest:
      description: Bad request - invalid input or malformed request
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
          examples:
            InvalidInput:
              value:
                error: "INVALID_INPUT"
                message: "Request validation failed"
                details:
                  field_errors:
                    query: ["Query cannot be empty"]
                timestamp: "2024-01-15T10:30:00Z"
                request_id: "123e4567-e89b-12d3-a456-426614174000"
            SecurityValidation:
              value:
                error: "SECURITY_VALIDATION_FAILED"
                message: "Input failed security validation"
                details:
                  violations: ["Potential SQL injection detected"]
                timestamp: "2024-01-15T10:30:00Z"
                security_incident: true

    Unauthorized:
      description: Authentication required or invalid credentials
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
          examples:
            InvalidToken:
              value:
                error: "INVALID_TOKEN"
                message: "Authentication token is invalid or expired"
                timestamp: "2024-01-15T10:30:00Z"
            MissingAuth:
              value:
                error: "AUTHENTICATION_REQUIRED"
                message: "Authentication is required for this endpoint"
                timestamp: "2024-01-15T10:30:00Z"

    Forbidden:
      description: Access denied - insufficient permissions
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
          examples:
            InsufficientPermissions:
              value:
                error: "INSUFFICIENT_PERMISSIONS"
                message: "User does not have required permissions for this resource"
                details:
                  required_permissions: ["admin:read"]
                  user_permissions: ["user:read"]
                timestamp: "2024-01-15T10:30:00Z"

    NotFound:
      description: Resource not found or access denied
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
          examples:
            ResourceNotFound:
              value:
                error: "RESOURCE_NOT_FOUND"
                message: "The requested resource was not found"
                timestamp: "2024-01-15T10:30:00Z"

    FileTooLarge:
      description: File exceeds maximum size limit
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
          examples:
            FileTooLarge:
              value:
                error: "FILE_TOO_LARGE"
                message: "File size exceeds maximum limit of 100MB"
                details:
                  max_size_bytes: 104857600
                  file_size_bytes: 157286400
                timestamp: "2024-01-15T10:30:00Z"

    UnsupportedMediaType:
      description: Unsupported file type or format
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
          examples:
            UnsupportedFileType:
              value:
                error: "UNSUPPORTED_MEDIA_TYPE"
                message: "File type is not supported"
                details:
                  supported_types: [".pdf", ".docx", ".txt", ".md", ".png", ".jpg", ".jpeg"]
                  detected_type: ".exe"
                timestamp: "2024-01-15T10:30:00Z"
                security_incident: true

    RateLimited:
      description: Rate limit exceeded
      headers:
        X-RateLimit-Limit:
          $ref: '#/components/headers/X-RateLimit-Limit'
        X-RateLimit-Remaining:
          schema:
            type: integer
            example: 0
        X-RateLimit-Reset:
          $ref: '#/components/headers/X-RateLimit-Reset'
        Retry-After:
          description: Seconds until rate limit resets
          schema:
            type: integer
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
          examples:
            RateLimitExceeded:
              value:
                error: "RATE_LIMIT_EXCEEDED"
                message: "Rate limit exceeded. Please try again later."
                details:
                  limit: 100
                  window: "1 hour"
                  reset_at: "2024-01-15T11:30:00Z"
                timestamp: "2024-01-15T10:30:00Z"

    InternalServerError:
      description: Internal server error
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
          examples:
            InternalError:
              value:
                error: "INTERNAL_SERVER_ERROR"
                message: "An internal server error occurred"
                timestamp: "2024-01-15T10:30:00Z"
                request_id: "123e4567-e89b-12d3-a456-426614174000"

  securitySchemes:
    ApiKeyAuth:
      type: apiKey
      in: header
      name: X-API-Key
      description: |
        API key authentication. Include your API key in the X-API-Key header.
        API keys have different rate limits based on your subscription tier.
    BearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
      description: |
        JWT token authentication. Obtain a token using the /auth/login endpoint
        and include it in the Authorization header as 'Bearer <token>'.
    OAuth2:
      type: oauth2
      flows:
        authorizationCode:
          authorizationUrl: https://api.raganything.dev/oauth/authorize
          tokenUrl: https://api.raganything.dev/oauth/token
          refreshUrl: https://api.raganything.dev/oauth/refresh
          scopes:
            read: Read access to documents and knowledge base
            write: Write access for document processing
            admin: Administrative access to system management
            delete: Permission to delete documents and clear knowledge base

security:
  - ApiKeyAuth: []
  - BearerAuth: []
  - OAuth2: [read, write]

tags:
  - name: Authentication
    description: User authentication and session management
  - name: Health & Monitoring
    description: System health and monitoring endpoints
  - name: Document Processing
    description: Document upload and processing with backend selection
  - name: Query Processing
    description: Query execution with multimodal support
  - name: Knowledge Base Management
    description: Knowledge base operations and statistics
  - name: Graphiti Knowledge Graph
    description: Graphiti-specific knowledge graph operations
  - name: Security Administration
    description: Security monitoring and administration (admin access required)
```

## API Security Specifications

### Authentication & Authorization

#### Multi-tier Authentication
The API supports multiple authentication methods to accommodate different use cases:

1. **API Key Authentication**
   - Simple header-based authentication
   - Suitable for server-to-server communication
   - Rate limits based on API key tier
   - Automatic rotation and expiration support

2. **JWT Token Authentication**
   - Stateless token-based authentication
   - Short-lived access tokens with refresh capability
   - Includes user permissions and rate limit tier
   - Automatic token validation and blacklist checking

3. **OAuth 2.0 with PKCE**
   - Standard OAuth 2.0 flow for client applications
   - PKCE extension for enhanced security
   - Scope-based access control
   - Suitable for web and mobile applications

#### Role-Based Access Control (RBAC)

```yaml
Roles:
  user:
    permissions: [read:documents, write:documents, query:basic]
    rate_limits:
      requests_per_minute: 100
      requests_per_hour: 1000
  
  admin:
    permissions: [read:*, write:*, delete:*, admin:*]
    rate_limits:
      requests_per_minute: 500
      requests_per_hour: 5000
  
  enterprise:
    permissions: [read:*, write:*, query:advanced, analytics:*]
    rate_limits:
      requests_per_minute: 1000
      requests_per_hour: 10000
```

### Input Validation & Security

#### File Upload Security
All file uploads undergo comprehensive security validation:

1. **File Type Validation**
   ```yaml
   allowed_extensions: [.pdf, .docx, .txt, .md, .png, .jpg, .jpeg]
   blocked_extensions: [.exe, .bat, .sh, .ps1, .scr]
   mime_type_validation: strict
   magic_number_verification: enabled
   ```

2. **Content Security**
   ```yaml
   max_file_size: 100MB
   malware_scanning: enabled
   content_policy_enforcement: strict
   pii_detection: enabled
   sensitive_content_filtering: enabled
   ```

3. **Processing Security**
   ```yaml
   sandboxed_processing: enabled
   resource_limits:
     memory: 1GB
     cpu_time: 300s
     disk_space: 500MB
   ```

#### Query Input Validation
All query inputs are validated and sanitized:

1. **SQL/NoSQL Injection Prevention**
   - Parameterized query construction
   - Input sanitization and escaping
   - Pattern-based injection detection
   - Query complexity limits

2. **Content Filtering**
   - Profanity and inappropriate content filtering
   - Sensitive information detection
   - Context-aware content warnings
   - Access level enforcement

### Rate Limiting & Abuse Prevention

#### Multi-tier Rate Limiting
```yaml
Rate Limiting Strategy:
  algorithm: sliding_window
  storage: redis
  
  limits:
    standard_user:
      requests_per_minute: 100
      requests_per_hour: 1000
      concurrent_requests: 10
      
    premium_user:
      requests_per_minute: 500
      requests_per_hour: 5000
      concurrent_requests: 25
      
    enterprise_user:
      requests_per_minute: 1000
      requests_per_hour: 10000
      concurrent_requests: 50

  endpoint_specific:
    /documents/process:
      multiplier: 2  # Counts as 2 requests
      burst_allowance: 5
    
    /kb/clear:
      special_limit: 1_per_day
      confirmation_required: true
```

#### Abuse Detection & Response
```yaml
Abuse Detection:
  patterns:
    - rapid_sequential_requests
    - unusual_geographic_access
    - failed_authentication_attempts
    - malicious_file_uploads
    - injection_attempt_patterns
  
  automated_responses:
    warning: rate_limit_reduction
    moderate: temporary_account_suspension
    severe: ip_blocking
    critical: permanent_account_suspension
```

### Security Monitoring & Audit

#### Comprehensive Audit Logging
All API interactions are logged with security context:

```yaml
Audit Log Structure:
  event_id: uuid
  timestamp: iso8601
  user_id: uuid
  session_id: uuid
  ip_address: string
  user_agent: string
  endpoint: string
  method: http_method
  request_id: uuid
  response_code: integer
  processing_time: float
  security_context:
    threat_level: enum
    content_filtered: boolean
    access_controlled: boolean
    pii_detected: boolean
  backend_context:
    backend_used: string
    operation_type: string
    resource_usage: object
```

#### Security Event Monitoring
Real-time monitoring of security events:

```yaml
Monitored Events:
  authentication:
    - successful_login
    - failed_login_attempt
    - token_refresh
    - suspicious_login_pattern
  
  file_operations:
    - malicious_file_detected
    - oversized_file_rejected
    - unsupported_format_attempt
    - content_policy_violation
  
  query_operations:
    - injection_attempt_detected
    - unusual_query_pattern
    - excessive_result_requests
    - sensitive_data_access
  
  system_operations:
    - privilege_escalation_attempt
    - unauthorized_admin_access
    - bulk_deletion_attempt
    - configuration_change
```

### Privacy & Compliance

#### Data Classification & Handling
```yaml
Data Classification:
  public:
    encryption: in_transit
    retention: indefinite
    access: unrestricted
  
  internal:
    encryption: in_transit_and_rest
    retention: 7_years
    access: authenticated_users
  
  confidential:
    encryption: in_transit_and_rest_with_key_rotation
    retention: 5_years
    access: authorized_personnel_only
  
  restricted:
    encryption: end_to_end_with_hardware_keys
    retention: 3_years_with_secure_deletion
    access: explicit_approval_required
```

#### GDPR/CCPA Compliance
```yaml
Privacy Features:
  consent_management:
    - explicit_consent_required
    - granular_permissions
    - consent_withdrawal_support
    - consent_audit_trail
  
  data_subject_rights:
    - right_to_access
    - right_to_rectification
    - right_to_erasure
    - right_to_portability
    - right_to_restrict_processing
  
  automated_compliance:
    - pii_detection_and_classification
    - automated_retention_enforcement
    - secure_deletion_procedures
    - compliance_reporting
```

## API Design Principles

### Security-First Design
- **Zero Trust Architecture**: Every request is validated and authenticated
- **Defense in Depth**: Multiple layers of security controls
- **Principle of Least Privilege**: Minimal necessary access granted
- **Secure by Default**: Secure configurations and safe defaults

### Performance with Security
- **Optimized Security Checks**: Efficient validation without compromising performance
- **Caching Strategy**: Security-aware caching with appropriate TTLs
- **Resource Management**: Prevent resource exhaustion attacks
- **Graceful Degradation**: Maintain functionality under security constraints

### Observability & Transparency
- **Comprehensive Logging**: Detailed security and operational logs
- **Real-time Monitoring**: Immediate threat detection and response
- **Audit Trails**: Complete history of security-relevant events
- **Compliance Reporting**: Automated compliance status reporting

This enhanced API specification provides enterprise-grade security while maintaining the flexibility and functionality required for multimodal document processing and knowledge graph operations. The security controls are designed to prevent common attack vectors while enabling legitimate use cases through proper authentication and authorization.