# RAG-Anything + Graphiti Integration - API Specification

## OpenAPI 3.0 Specification

```yaml
openapi: 3.0.3
info:
  title: RAG-Anything + Graphiti Integration API
  description: |
    REST API for RAG-Anything with Graphiti episodic knowledge graph integration.
    Provides multimodal document processing, episode management, and advanced
    graph-based querying capabilities.
  version: 1.0.0
  contact:
    name: RAG-Anything Development Team
    url: https://github.com/ericreyes/RAG-Anything
  license:
    name: MIT
    url: https://opensource.org/licenses/MIT

servers:
  - url: https://api.raganything.dev/v1
    description: Production server
  - url: https://staging-api.raganything.dev/v1
    description: Staging server
  - url: http://localhost:8000/v1
    description: Local development server

security:
  - ApiKeyAuth: []
  - BearerAuth: []

paths:
  # Document Processing Endpoints
  
  /documents/upload:
    post:
      summary: Upload and process multimodal documents
      description: |
        Upload documents for multimodal processing and conversion to episodes.
        Supports PDF, DOCX, images, and other document formats.
      operationId: uploadDocument
      tags:
        - Documents
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
                  description: The document file to process
                group_id:
                  type: string
                  default: "default"
                  description: Group ID for organizing episodes
                parser:
                  type: string
                  enum: [mineru, docling]
                  default: mineru
                  description: Parser to use for document processing
                parse_method:
                  type: string
                  enum: [auto, layout, ocr]
                  default: auto
                  description: Parsing method for document extraction
                preserve_structure:
                  type: boolean
                  default: true
                  description: Maintain document hierarchy in episodes
                metadata:
                  type: string
                  description: JSON string of additional metadata
              required:
                - file
            encoding:
              file:
                contentType: application/pdf, application/vnd.openxmlformats-officedocument.wordprocessingml.document, image/png, image/jpeg, text/plain
      responses:
        '202':
          description: Document accepted for processing
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/DocumentProcessingResponse'
        '400':
          description: Invalid request or unsupported file format
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
        '413':
          description: File too large
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

  /documents/{document_id}/status:
    get:
      summary: Get document processing status
      description: Check the processing status and progress of an uploaded document
      operationId: getDocumentStatus
      tags:
        - Documents
      parameters:
        - name: document_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
          description: Unique document identifier
      responses:
        '200':
          description: Document processing status
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ProcessingStatus'
        '404':
          description: Document not found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

  /documents/{document_id}/episodes:
    get:
      summary: List episodes for a document
      description: Retrieve all episodes generated from a specific document
      operationId: getDocumentEpisodes
      tags:
        - Documents
        - Episodes
      parameters:
        - name: document_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
        - name: page
          in: query
          schema:
            type: integer
            minimum: 1
            default: 1
        - name: limit
          in: query
          schema:
            type: integer
            minimum: 1
            maximum: 100
            default: 20
      responses:
        '200':
          description: List of episodes
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/EpisodeListResponse'

  # Episode Management Endpoints
  
  /episodes:
    get:
      summary: List episodes
      description: Retrieve episodes with filtering and pagination
      operationId: listEpisodes
      tags:
        - Episodes
      parameters:
        - name: group_id
          in: query
          schema:
            type: string
          description: Filter by group ID
        - name: start_time
          in: query
          schema:
            type: string
            format: date-time
          description: Filter episodes after this time
        - name: end_time
          in: query
          schema:
            type: string
            format: date-time
          description: Filter episodes before this time
        - name: content_type
          in: query
          schema:
            type: string
            enum: [text, image, table, mixed]
          description: Filter by content type
        - name: page
          in: query
          schema:
            type: integer
            minimum: 1
            default: 1
        - name: limit
          in: query
          schema:
            type: integer
            minimum: 1
            maximum: 100
            default: 20
        - name: sort
          in: query
          schema:
            type: string
            enum: [created_at, reference_time, name]
            default: created_at
        - name: order
          in: query
          schema:
            type: string
            enum: [asc, desc]
            default: desc
      responses:
        '200':
          description: List of episodes
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/EpisodeListResponse'

    post:
      summary: Create episode
      description: Manually create a new episode
      operationId: createEpisode
      tags:
        - Episodes
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CreateEpisodeRequest'
      responses:
        '201':
          description: Episode created successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Episode'
        '400':
          description: Invalid episode data
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

  /episodes/{episode_id}:
    get:
      summary: Get episode by ID
      description: Retrieve detailed information about a specific episode
      operationId: getEpisode
      tags:
        - Episodes
      parameters:
        - name: episode_id
          in: path
          required: true
          schema:
            type: string
          description: Episode identifier
      responses:
        '200':
          description: Episode details
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Episode'
        '404':
          description: Episode not found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

    put:
      summary: Update episode
      description: Update an existing episode's content or metadata
      operationId: updateEpisode
      tags:
        - Episodes
      parameters:
        - name: episode_id
          in: path
          required: true
          schema:
            type: string
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/UpdateEpisodeRequest'
      responses:
        '200':
          description: Episode updated successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Episode'
        '404':
          description: Episode not found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

    delete:
      summary: Delete episode
      description: Remove an episode and its associated data
      operationId: deleteEpisode
      tags:
        - Episodes
      parameters:
        - name: episode_id
          in: path
          required: true
          schema:
            type: string
      responses:
        '204':
          description: Episode deleted successfully
        '404':
          description: Episode not found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

  # Query and Search Endpoints
  
  /query:
    post:
      summary: Query knowledge graph
      description: |
        Perform advanced queries against the episodic knowledge graph.
        Supports various search modes including semantic, temporal, and hybrid search.
      operationId: queryGraph
      tags:
        - Query
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/QueryRequest'
      responses:
        '200':
          description: Query results
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/QueryResponse'
        '400':
          description: Invalid query
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

  /search/semantic:
    post:
      summary: Semantic search
      description: Perform semantic search using embeddings
      operationId: semanticSearch
      tags:
        - Search
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/SemanticSearchRequest'
      responses:
        '200':
          description: Search results
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SearchResponse'

  /search/temporal:
    post:
      summary: Temporal search
      description: Search episodes within a specific time range
      operationId: temporalSearch
      tags:
        - Search
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/TemporalSearchRequest'
      responses:
        '200':
          description: Search results
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SearchResponse'

  # Graph Analysis Endpoints
  
  /graph/entities:
    get:
      summary: Get entities
      description: Retrieve entities from the knowledge graph
      operationId: getEntities
      tags:
        - Graph
      parameters:
        - name: type
          in: query
          schema:
            type: string
          description: Filter by entity type
        - name: limit
          in: query
          schema:
            type: integer
            minimum: 1
            maximum: 1000
            default: 100
        - name: offset
          in: query
          schema:
            type: integer
            minimum: 0
            default: 0
      responses:
        '200':
          description: List of entities
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/EntityListResponse'

  /graph/relationships:
    get:
      summary: Get relationships
      description: Retrieve relationships from the knowledge graph
      operationId: getRelationships
      tags:
        - Graph
      parameters:
        - name: entity_id
          in: query
          schema:
            type: string
          description: Filter relationships by entity
        - name: relationship_type
          in: query
          schema:
            type: string
          description: Filter by relationship type
        - name: limit
          in: query
          schema:
            type: integer
            minimum: 1
            maximum: 1000
            default: 100
        - name: offset
          in: query
          schema:
            type: integer
            minimum: 0
            default: 0
      responses:
        '200':
          description: List of relationships
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/RelationshipListResponse'

  /graph/communities:
    get:
      summary: Get community structure
      description: Retrieve community information from the graph
      operationId: getCommunities
      tags:
        - Graph
      parameters:
        - name: level
          in: query
          schema:
            type: integer
            minimum: 0
          description: Community hierarchy level
        - name: min_size
          in: query
          schema:
            type: integer
            minimum: 1
            default: 5
          description: Minimum community size
      responses:
        '200':
          description: Community structure
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CommunityResponse'

  # Migration and Backend Management
  
  /migration/export:
    post:
      summary: Export knowledge graph
      description: Export the current knowledge graph for backup or migration
      operationId: exportGraph
      tags:
        - Migration
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ExportRequest'
      responses:
        '202':
          description: Export started
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ExportResponse'

  /migration/import:
    post:
      summary: Import knowledge graph
      description: Import a previously exported knowledge graph
      operationId: importGraph
      tags:
        - Migration
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
                  description: Exported graph file
                merge_strategy:
                  type: string
                  enum: [replace, merge, skip_conflicts]
                  default: merge
              required:
                - file
      responses:
        '202':
          description: Import started
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ImportResponse'

  /backend/switch:
    post:
      summary: Switch backend
      description: Switch between LightRAG and Graphiti backends
      operationId: switchBackend
      tags:
        - Backend
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/SwitchBackendRequest'
      responses:
        '200':
          description: Backend switched successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/BackendStatusResponse'

  # System Management Endpoints
  
  /health:
    get:
      summary: Health check
      description: Check system health and component status
      operationId: healthCheck
      tags:
        - System
      responses:
        '200':
          description: System health status
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/HealthResponse'

  /metrics:
    get:
      summary: Get system metrics
      description: Retrieve system performance and usage metrics
      operationId: getMetrics
      tags:
        - System
      responses:
        '200':
          description: System metrics
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/MetricsResponse'

  /config:
    get:
      summary: Get system configuration
      description: Retrieve current system configuration
      operationId: getConfig
      tags:
        - System
      responses:
        '200':
          description: System configuration
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ConfigResponse'

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
      description: JWT bearer token

  schemas:
    # Document Processing Schemas
    
    DocumentProcessingResponse:
      type: object
      properties:
        document_id:
          type: string
          format: uuid
          description: Unique document identifier
        status:
          type: string
          enum: [accepted, processing, completed, failed]
        message:
          type: string
          description: Processing status message
        estimated_completion:
          type: string
          format: date-time
          description: Estimated completion time
        created_at:
          type: string
          format: date-time
      required:
        - document_id
        - status

    ProcessingStatus:
      type: object
      properties:
        document_id:
          type: string
          format: uuid
        status:
          type: string
          enum: [accepted, processing, completed, failed]
        progress:
          type: number
          minimum: 0
          maximum: 100
          description: Processing progress percentage
        stage:
          type: string
          enum: [uploading, parsing, extracting, converting, indexing]
        episodes_created:
          type: integer
          minimum: 0
        processing_time:
          type: number
          description: Processing time in seconds
        error_message:
          type: string
          description: Error message if processing failed
        started_at:
          type: string
          format: date-time
        completed_at:
          type: string
          format: date-time
      required:
        - document_id
        - status
        - progress

    # Episode Schemas
    
    Episode:
      type: object
      properties:
        id:
          type: string
          description: Episode identifier
        name:
          type: string
          description: Episode name
        content:
          type: string
          description: Episode text content
        source_description:
          type: string
          description: Description of content source
        group_id:
          type: string
          description: Group identifier
        reference_time:
          type: string
          format: date-time
          description: Temporal reference
        content_type:
          type: string
          enum: [text, image, table, mixed]
        multimodal_content:
          $ref: '#/components/schemas/MultimodalContent'
        metadata:
          type: object
          additionalProperties: true
          description: Additional episode metadata
        extraction_confidence:
          type: number
          minimum: 0
          maximum: 1
          description: Confidence score for content extraction
        created_at:
          type: string
          format: date-time
        updated_at:
          type: string
          format: date-time
      required:
        - id
        - name
        - content
        - group_id
        - reference_time

    MultimodalContent:
      type: object
      properties:
        images:
          type: array
          items:
            $ref: '#/components/schemas/ImageContent'
        tables:
          type: array
          items:
            $ref: '#/components/schemas/TableContent'
        equations:
          type: array
          items:
            $ref: '#/components/schemas/EquationContent'

    ImageContent:
      type: object
      properties:
        id:
          type: string
        image_path:
          type: string
          description: Path to image file
        description:
          type: string
          description: AI-generated image description
        extracted_text:
          type: string
          description: OCR extracted text
        confidence_score:
          type: number
          minimum: 0
          maximum: 1
        dimensions:
          type: object
          properties:
            width:
              type: integer
            height:
              type: integer

    TableContent:
      type: object
      properties:
        id:
          type: string
        table_data:
          type: array
          items:
            type: array
            items:
              type: string
          description: Table data as 2D array
        headers:
          type: array
          items:
            type: string
        extraction_method:
          type: string
          enum: [layout_detection, ocr, hybrid]
        confidence_score:
          type: number
          minimum: 0
          maximum: 1

    EquationContent:
      type: object
      properties:
        id:
          type: string
        latex:
          type: string
          description: LaTeX representation
        mathml:
          type: string
          description: MathML representation
        rendered_image:
          type: string
          description: Path to rendered equation image

    CreateEpisodeRequest:
      type: object
      properties:
        name:
          type: string
          description: Episode name
        content:
          type: string
          description: Episode content
        source_description:
          type: string
        group_id:
          type: string
          default: "default"
        reference_time:
          type: string
          format: date-time
        multimodal_content:
          $ref: '#/components/schemas/MultimodalContent'
        metadata:
          type: object
          additionalProperties: true
      required:
        - name
        - content

    UpdateEpisodeRequest:
      type: object
      properties:
        name:
          type: string
        content:
          type: string
        source_description:
          type: string
        multimodal_content:
          $ref: '#/components/schemas/MultimodalContent'
        metadata:
          type: object
          additionalProperties: true

    EpisodeListResponse:
      type: object
      properties:
        episodes:
          type: array
          items:
            $ref: '#/components/schemas/Episode'
        pagination:
          $ref: '#/components/schemas/Pagination'
      required:
        - episodes
        - pagination

    # Query and Search Schemas
    
    QueryRequest:
      type: object
      properties:
        query:
          type: string
          description: Query string
        mode:
          type: string
          enum: [local, global, hybrid, naive]
          default: hybrid
          description: Query processing mode
        top_k:
          type: integer
          minimum: 1
          maximum: 100
          default: 10
          description: Number of results to return
        group_id:
          type: string
          description: Limit query to specific group
        time_range:
          $ref: '#/components/schemas/TimeRange'
        include_multimodal:
          type: boolean
          default: true
          description: Include multimodal content in results
        rerank:
          type: boolean
          default: false
          description: Apply cross-encoder reranking
      required:
        - query

    QueryResponse:
      type: object
      properties:
        query:
          type: string
          description: Original query
        results:
          type: array
          items:
            $ref: '#/components/schemas/QueryResult'
        total_results:
          type: integer
        query_time:
          type: number
          description: Query execution time in seconds
        mode:
          type: string
        metadata:
          type: object
          additionalProperties: true
      required:
        - query
        - results
        - query_time

    QueryResult:
      type: object
      properties:
        episode_id:
          type: string
        content:
          type: string
        score:
          type: number
          minimum: 0
          maximum: 1
        source_episode:
          $ref: '#/components/schemas/Episode'
        entities:
          type: array
          items:
            $ref: '#/components/schemas/Entity'
        relationships:
          type: array
          items:
            $ref: '#/components/schemas/Relationship'
        explanation:
          type: string
          description: Why this result was selected
      required:
        - episode_id
        - content
        - score

    SemanticSearchRequest:
      type: object
      properties:
        query:
          type: string
        embedding_model:
          type: string
          default: "text-embedding-3-large"
        top_k:
          type: integer
          minimum: 1
          maximum: 100
          default: 20
        threshold:
          type: number
          minimum: 0
          maximum: 1
          description: Minimum similarity threshold
        group_id:
          type: string
      required:
        - query

    TemporalSearchRequest:
      type: object
      properties:
        time_range:
          $ref: '#/components/schemas/TimeRange'
        query:
          type: string
          description: Optional text query within time range
        group_id:
          type: string
        sort_by:
          type: string
          enum: [reference_time, created_at, relevance]
          default: reference_time
        order:
          type: string
          enum: [asc, desc]
          default: desc
      required:
        - time_range

    SearchResponse:
      type: object
      properties:
        results:
          type: array
          items:
            $ref: '#/components/schemas/SearchResult'
        total_results:
          type: integer
        search_time:
          type: number
        pagination:
          $ref: '#/components/schemas/Pagination'
      required:
        - results
        - total_results

    SearchResult:
      type: object
      properties:
        episode:
          $ref: '#/components/schemas/Episode'
        score:
          type: number
          minimum: 0
          maximum: 1
        highlights:
          type: array
          items:
            type: string
          description: Highlighted matching text snippets
      required:
        - episode
        - score

    # Graph Analysis Schemas
    
    Entity:
      type: object
      properties:
        id:
          type: string
        name:
          type: string
        type:
          type: string
        properties:
          type: object
          additionalProperties: true
        created_at:
          type: string
          format: date-time
      required:
        - id
        - name
        - type

    Relationship:
      type: object
      properties:
        id:
          type: string
        source_entity_id:
          type: string
        target_entity_id:
          type: string
        relationship_type:
          type: string
        properties:
          type: object
          additionalProperties: true
        strength:
          type: number
          minimum: 0
          maximum: 1
        created_at:
          type: string
          format: date-time
      required:
        - id
        - source_entity_id
        - target_entity_id
        - relationship_type

    EntityListResponse:
      type: object
      properties:
        entities:
          type: array
          items:
            $ref: '#/components/schemas/Entity'
        total_count:
          type: integer
        pagination:
          $ref: '#/components/schemas/Pagination'
      required:
        - entities
        - total_count

    RelationshipListResponse:
      type: object
      properties:
        relationships:
          type: array
          items:
            $ref: '#/components/schemas/Relationship'
        total_count:
          type: integer
        pagination:
          $ref: '#/components/schemas/Pagination'
      required:
        - relationships
        - total_count

    CommunityResponse:
      type: object
      properties:
        communities:
          type: array
          items:
            $ref: '#/components/schemas/Community'
        hierarchy_levels:
          type: integer
        total_communities:
          type: integer
      required:
        - communities

    Community:
      type: object
      properties:
        id:
          type: string
        level:
          type: integer
          description: Hierarchy level
        title:
          type: string
        description:
          type: string
        entities:
          type: array
          items:
            type: string
          description: Entity IDs in this community
        size:
          type: integer
          description: Number of entities
        density:
          type: number
          minimum: 0
          maximum: 1
          description: Community connection density
      required:
        - id
        - level
        - entities
        - size

    # Migration and Backend Schemas
    
    ExportRequest:
      type: object
      properties:
        format:
          type: string
          enum: [graphml, json, cypher]
          default: json
        include_multimodal:
          type: boolean
          default: true
        group_ids:
          type: array
          items:
            type: string
          description: Specific groups to export (empty = all)
        time_range:
          $ref: '#/components/schemas/TimeRange'
      required:
        - format

    ExportResponse:
      type: object
      properties:
        export_id:
          type: string
          format: uuid
        status:
          type: string
          enum: [started, processing, completed, failed]
        download_url:
          type: string
          format: uri
          description: URL to download completed export
        estimated_completion:
          type: string
          format: date-time
      required:
        - export_id
        - status

    ImportResponse:
      type: object
      properties:
        import_id:
          type: string
          format: uuid
        status:
          type: string
          enum: [started, processing, completed, failed]
        imported_episodes:
          type: integer
          minimum: 0
        imported_entities:
          type: integer
          minimum: 0
        imported_relationships:
          type: integer
          minimum: 0
        conflicts:
          type: integer
          minimum: 0
          description: Number of conflicts encountered
      required:
        - import_id
        - status

    SwitchBackendRequest:
      type: object
      properties:
        backend:
          type: string
          enum: [lightrag, graphiti]
        migrate_data:
          type: boolean
          default: true
          description: Whether to migrate existing data
        backup_current:
          type: boolean
          default: true
          description: Create backup before switching
      required:
        - backend

    BackendStatusResponse:
      type: object
      properties:
        current_backend:
          type: string
          enum: [lightrag, graphiti]
        status:
          type: string
          enum: [active, switching, error]
        migration_progress:
          type: number
          minimum: 0
          maximum: 100
        switch_completed_at:
          type: string
          format: date-time
      required:
        - current_backend
        - status

    # System Management Schemas
    
    HealthResponse:
      type: object
      properties:
        status:
          type: string
          enum: [healthy, degraded, unhealthy]
        components:
          type: object
          properties:
            graphiti:
              $ref: '#/components/schemas/ComponentHealth'
            neo4j:
              $ref: '#/components/schemas/ComponentHealth'
            redis:
              $ref: '#/components/schemas/ComponentHealth'
            parsers:
              $ref: '#/components/schemas/ComponentHealth'
        uptime:
          type: number
          description: Uptime in seconds
        version:
          type: string
        timestamp:
          type: string
          format: date-time
      required:
        - status
        - components
        - timestamp

    ComponentHealth:
      type: object
      properties:
        status:
          type: string
          enum: [healthy, warning, error]
        response_time:
          type: number
          description: Response time in milliseconds
        error_message:
          type: string
        last_check:
          type: string
          format: date-time
      required:
        - status

    MetricsResponse:
      type: object
      properties:
        performance:
          type: object
          properties:
            avg_response_time:
              type: number
            requests_per_second:
              type: number
            error_rate:
              type: number
            cache_hit_rate:
              type: number
        usage:
          type: object
          properties:
            total_documents:
              type: integer
            total_episodes:
              type: integer
            total_entities:
              type: integer
            total_relationships:
              type: integer
            storage_used:
              type: number
              description: Storage used in bytes
        capacity:
          type: object
          properties:
            cpu_usage:
              type: number
              minimum: 0
              maximum: 100
            memory_usage:
              type: number
              minimum: 0
              maximum: 100
            disk_usage:
              type: number
              minimum: 0
              maximum: 100
        timestamp:
          type: string
          format: date-time
      required:
        - timestamp

    ConfigResponse:
      type: object
      properties:
        backend:
          type: object
          properties:
            type:
              type: string
              enum: [lightrag, graphiti]
            configuration:
              type: object
              additionalProperties: true
        parsers:
          type: object
          properties:
            default:
              type: string
              enum: [mineru, docling]
            available:
              type: array
              items:
                type: string
        models:
          type: object
          properties:
            llm:
              type: string
            embedding:
              type: string
            vision:
              type: string
        features:
          type: object
          properties:
            multimodal_processing:
              type: boolean
            backend_fallback:
              type: boolean
            caching:
              type: boolean
        limits:
          type: object
          properties:
            max_file_size:
              type: number
            max_episodes_per_document:
              type: integer
            rate_limit:
              type: object
              properties:
                requests_per_minute:
                  type: integer
                requests_per_hour:
                  type: integer
      required:
        - backend
        - parsers
        - models

    # Common Schemas
    
    TimeRange:
      type: object
      properties:
        start:
          type: string
          format: date-time
        end:
          type: string
          format: date-time
      required:
        - start
        - end

    Pagination:
      type: object
      properties:
        page:
          type: integer
          minimum: 1
        limit:
          type: integer
          minimum: 1
        total_pages:
          type: integer
        total_items:
          type: integer
        has_next:
          type: boolean
        has_previous:
          type: boolean
      required:
        - page
        - limit
        - total_pages
        - total_items
        - has_next
        - has_previous

    ErrorResponse:
      type: object
      properties:
        error:
          type: string
          description: Error type
        message:
          type: string
          description: Human-readable error message
        details:
          type: object
          additionalProperties: true
          description: Additional error details
        request_id:
          type: string
          description: Unique request identifier for debugging
        timestamp:
          type: string
          format: date-time
      required:
        - error
        - message
        - timestamp

tags:
  - name: Documents
    description: Document upload and processing operations
  - name: Episodes
    description: Episode management and CRUD operations
  - name: Query
    description: Advanced graph querying capabilities
  - name: Search
    description: Semantic and temporal search operations
  - name: Graph
    description: Graph analysis and exploration
  - name: Migration
    description: Data migration and backend switching
  - name: Backend
    description: Backend management operations
  - name: System
    description: System health and configuration
```

## API Usage Examples

### Upload and Process a Document

```bash
curl -X POST "https://api.raganything.dev/v1/documents/upload" \
  -H "X-API-Key: your-api-key" \
  -F "file=@research_paper.pdf" \
  -F "group_id=research_project_1" \
  -F "parser=mineru" \
  -F "preserve_structure=true" \
  -F "metadata={\"author\":\"John Doe\",\"category\":\"research\"}"
```

### Query the Knowledge Graph

```bash
curl -X POST "https://api.raganything.dev/v1/query" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the main findings about machine learning in the uploaded documents?",
    "mode": "hybrid",
    "top_k": 5,
    "include_multimodal": true,
    "rerank": true
  }'
```

### Perform Semantic Search

```bash
curl -X POST "https://api.raganything.dev/v1/search/semantic" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "neural network architectures",
    "top_k": 10,
    "threshold": 0.7,
    "group_id": "research_project_1"
  }'
```

### Get Processing Status

```bash
curl "https://api.raganything.dev/v1/documents/550e8400-e29b-41d4-a716-446655440000/status" \
  -H "X-API-Key: your-api-key"
```

### Switch Backend

```bash
curl -X POST "https://api.raganything.dev/v1/backend/switch" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "backend": "graphiti",
    "migrate_data": true,
    "backup_current": true
  }'
```

## Rate Limiting

The API implements rate limiting to ensure fair usage:

- **Standard tier**: 100 requests/minute, 1000 requests/hour
- **Premium tier**: 500 requests/minute, 5000 requests/hour
- **Enterprise tier**: Custom limits

Rate limit headers are included in all responses:
- `X-RateLimit-Limit`: Request limit per window
- `X-RateLimit-Remaining`: Remaining requests in window
- `X-RateLimit-Reset`: Window reset time (Unix timestamp)

## Error Handling

The API uses standard HTTP status codes and provides detailed error information:

- **400 Bad Request**: Invalid request parameters or data
- **401 Unauthorized**: Missing or invalid authentication
- **403 Forbidden**: Insufficient permissions
- **404 Not Found**: Resource not found
- **413 Payload Too Large**: File size exceeds limits
- **429 Too Many Requests**: Rate limit exceeded
- **500 Internal Server Error**: Server error
- **503 Service Unavailable**: Service temporarily unavailable

All error responses follow the `ErrorResponse` schema with detailed error information and unique request IDs for debugging.

## WebSocket Support (Future)

The API will support WebSocket connections for real-time updates:

- **Document processing progress**: Real-time processing status updates
- **Query streaming**: Stream query results as they become available
- **Graph updates**: Live notifications of graph changes
- **System events**: Real-time system health and performance metrics

WebSocket endpoints will be available at `wss://api.raganything.dev/v1/ws/` with the same authentication mechanisms as the REST API.