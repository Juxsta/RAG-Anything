import { FastifyInstance } from 'fastify';
import { build } from '@/app';
import { authService } from '@/services/auth';
import { pythonProcessManager } from '@/services/python-process-manager';
import { jobQueueService } from '@/services/job-queue';

// Mock the Python process manager and job queue service
jest.mock('@/services/python-process-manager');
jest.mock('@/services/job-queue');

const mockPythonManager = pythonProcessManager as jest.Mocked<typeof pythonProcessManager>;
const mockJobQueue = jobQueueService as jest.Mocked<typeof jobQueueService>;

describe('Query Integration Tests', () => {
  let app: FastifyInstance;
  let accessToken: string;
  let testUser: any;

  beforeAll(async () => {
    app = await build({ logger: false });
    await app.ready();
  });

  afterAll(async () => {
    await app.close();
  });

  beforeEach(async () => {
    jest.clearAllMocks();
    
    // Clean up and prepare test data
    if (global.testEnv?.prisma) {
      await global.testEnv.prisma.$executeRaw`TRUNCATE TABLE queries CASCADE`;
      await global.testEnv.prisma.$executeRaw`TRUNCATE TABLE users CASCADE`;
    }

    // Create test user and get access token
    testUser = await authService.createUser({
      email: 'test@example.com',
      password: 'SecurePassword123!',
      role: 'user',
    });

    const loginResult = await authService.login({
      email: 'test@example.com',
      password: 'SecurePassword123!',
    });

    accessToken = loginResult.accessToken;
  });

  describe('POST /api/v1/query/text', () => {
    it('should execute text query successfully (synchronous)', async () => {
      // Mock Python process manager
      mockPythonManager.initialized = true;
      mockPythonManager.executeQuery.mockResolvedValue({
        answer: 'AI is artificial intelligence that enables machines to learn and make decisions.',
        sources: [
          {
            doc_id: 'doc-123',
            chunk_id: 'chunk-001',
            relevance_score: 0.95,
            content_preview: 'Artificial intelligence (AI) refers to...',
          },
        ],
        processing_time: 1500,
        metadata: { total_chunks: 100 },
      });

      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/query/text',
        headers: {
          authorization: `Bearer ${accessToken}`,
        },
        payload: {
          query: 'What is artificial intelligence?',
          mode: 'mix',
          vlm_enhanced: false,
          stream: false,
        },
      });

      expect(response.statusCode).toBe(200);
      const body = JSON.parse(response.body);
      
      expect(body.success).toBe(true);
      expect(body.data.result).toBe('AI is artificial intelligence that enables machines to learn and make decisions.');
      expect(body.data.sources).toHaveLength(1);
      expect(body.data.sources[0]).toEqual({
        doc_id: 'doc-123',
        chunk_id: 'chunk-001',
        relevance_score: 0.95,
        content_preview: 'Artificial intelligence (AI) refers to...',
      });
      expect(body.data.metadata.processing_time_ms).toBe(1500);
      expect(body.data).toHaveProperty('query_id');

      // Verify query was stored in database
      const storedQueries = await global.testEnv.prisma.$queryRaw<Array<{
        query_text: string;
        query_type: string;
        mode: string;
        result_text: string;
      }>>`
        SELECT query_text, query_type, mode, result_text
        FROM queries
        WHERE user_id = ${testUser.id}::uuid
      `;

      expect(storedQueries).toHaveLength(1);
      expect(storedQueries[0].query_text).toBe('What is artificial intelligence?');
      expect(storedQueries[0].query_type).toBe('text');
      expect(storedQueries[0].mode).toBe('mix');
    });

    it('should queue text query for streaming', async () => {
      mockJobQueue.addQueryProcessingJob.mockResolvedValue('job-123');

      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/query/text',
        headers: {
          authorization: `Bearer ${accessToken}`,
        },
        payload: {
          query: 'What is machine learning?',
          mode: 'hybrid',
          stream: true,
        },
      });

      expect(response.statusCode).toBe(200);
      const body = JSON.parse(response.body);
      
      expect(body.success).toBe(true);
      expect(body.data.status).toBe('processing');
      expect(body.data.job_id).toBe('job-123');
      expect(body.data.metadata.stream).toBe(true);
      
      expect(mockJobQueue.addQueryProcessingJob).toHaveBeenCalledWith({
        queryId: expect.any(String),
        userId: testUser.id,
        query: 'What is machine learning?',
        queryType: 'text',
        mode: 'hybrid',
        vlmEnhanced: false,
        options: expect.any(Object),
      });
    });

    it('should initialize Python manager if not initialized', async () => {
      mockPythonManager.initialized = false;
      mockPythonManager.initialize.mockResolvedValue();
      mockPythonManager.executeQuery.mockResolvedValue({
        answer: 'Test answer',
        sources: [],
        processing_time: 1000,
      });

      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/query/text',
        headers: {
          authorization: `Bearer ${accessToken}`,
        },
        payload: {
          query: 'Test query',
          stream: false,
        },
      });

      expect(response.statusCode).toBe(200);
      expect(mockPythonManager.initialize).toHaveBeenCalled();
    });

    it('should return 401 without authentication', async () => {
      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/query/text',
        payload: {
          query: 'What is AI?',
        },
      });

      expect(response.statusCode).toBe(401);
    });

    it('should return 400 for invalid request body', async () => {
      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/query/text',
        headers: {
          authorization: `Bearer ${accessToken}`,
        },
        payload: {
          // query is missing
          mode: 'mix',
        },
      });

      expect(response.statusCode).toBe(400);
    });

    it('should handle Python processing errors', async () => {
      mockPythonManager.initialized = true;
      mockPythonManager.executeQuery.mockRejectedValue(new Error('Processing failed'));

      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/query/text',
        headers: {
          authorization: `Bearer ${accessToken}`,
        },
        payload: {
          query: 'Failing query',
          stream: false,
        },
      });

      expect(response.statusCode).toBe(500);
      const body = JSON.parse(response.body);
      expect(body.success).toBe(false);
      expect(body.error.message).toContain('Query execution failed');
    });

    it('should support different query modes', async () => {
      mockPythonManager.initialized = true;
      mockPythonManager.executeQuery.mockResolvedValue({
        answer: 'Test answer',
        sources: [],
        processing_time: 1000,
      });

      const modes = ['naive', 'local', 'global', 'hybrid', 'mix'];

      for (const mode of modes) {
        const response = await app.inject({
          method: 'POST',
          url: '/api/v1/query/text',
          headers: {
            authorization: `Bearer ${accessToken}`,
          },
          payload: {
            query: `Test query with ${mode} mode`,
            mode,
            stream: false,
          },
        });

        expect(response.statusCode).toBe(200);
        expect(mockPythonManager.executeQuery).toHaveBeenCalledWith(
          `Test query with ${mode} mode`,
          mode,
          false
        );
      }
    });

    it('should support VLM enhanced queries', async () => {
      mockPythonManager.initialized = true;
      mockPythonManager.executeQuery.mockResolvedValue({
        answer: 'VLM enhanced answer',
        sources: [],
        processing_time: 2000,
      });

      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/query/text',
        headers: {
          authorization: `Bearer ${accessToken}`,
        },
        payload: {
          query: 'Analyze this visual content',
          vlm_enhanced: true,
          stream: false,
        },
      });

      expect(response.statusCode).toBe(200);
      expect(mockPythonManager.executeQuery).toHaveBeenCalledWith(
        'Analyze this visual content',
        'mix',
        true
      );
    });
  });

  describe('POST /api/v1/query/multimodal', () => {
    it('should execute multimodal query successfully', async () => {
      mockPythonManager.initialized = true;
      mockPythonManager.executeMultimodalQuery.mockResolvedValue({
        answer: 'The image shows a data visualization chart showing AI adoption trends over time.',
        sources: [
          {
            doc_id: 'doc-456',
            chunk_id: 'chunk-img-001',
            relevance_score: 0.92,
            content_preview: 'Figure 1: AI adoption trends...',
          },
        ],
        processing_time: 2500,
        metadata: { image_processed: true },
      });

      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/query/multimodal',
        headers: {
          authorization: `Bearer ${accessToken}`,
        },
        payload: {
          query: 'What does this chart show about AI trends?',
          multimodal_content: [
            {
              type: 'image',
              img_path: '/path/to/chart.jpg',
            },
          ],
          mode: 'mix',
          stream: false,
        },
      });

      expect(response.statusCode).toBe(200);
      const body = JSON.parse(response.body);
      
      expect(body.success).toBe(true);
      expect(body.data.result).toBe('The image shows a data visualization chart showing AI adoption trends over time.');
      expect(body.data.processing_details.image_analysis).toBe('completed');
      expect(body.data.metadata.vlm_enhanced).toBe(true);
    });

    it('should validate multimodal content', async () => {
      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/query/multimodal',
        headers: {
          authorization: `Bearer ${accessToken}`,
        },
        payload: {
          query: 'What is in this image?',
          multimodal_content: [
            {
              type: 'image',
              // missing img_path and data
            },
          ],
        },
      });

      expect(response.statusCode).toBe(400);
      const body = JSON.parse(response.body);
      expect(body.error.message).toContain('Image content requires either img_path or data');
    });

    it('should handle table content', async () => {
      mockPythonManager.initialized = true;
      mockPythonManager.executeMultimodalQuery.mockResolvedValue({
        answer: 'The table shows quarterly revenue data.',
        sources: [],
        processing_time: 1800,
      });

      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/query/multimodal',
        headers: {
          authorization: `Bearer ${accessToken}`,
        },
        payload: {
          query: 'What information is in this table?',
          multimodal_content: [
            {
              type: 'table',
              table_data: 'Q1,Q2,Q3,Q4\n100,150,200,180',
            },
          ],
          stream: false,
        },
      });

      expect(response.statusCode).toBe(200);
      const body = JSON.parse(response.body);
      expect(body.data.processing_details.table_analysis).toBe('completed');
    });

    it('should handle equation content', async () => {
      mockPythonManager.initialized = true;
      mockPythonManager.executeMultimodalQuery.mockResolvedValue({
        answer: 'This is the quadratic formula.',
        sources: [],
        processing_time: 1200,
      });

      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/query/multimodal',
        headers: {
          authorization: `Bearer ${accessToken}`,
        },
        payload: {
          query: 'Explain this mathematical equation',
          multimodal_content: [
            {
              type: 'equation',
              equation: 'x = (-b ± √(b²-4ac)) / 2a',
            },
          ],
          stream: false,
        },
      });

      expect(response.statusCode).toBe(200);
      const body = JSON.parse(response.body);
      expect(body.data.processing_details.equation_analysis).toBe('completed');
    });

    it('should queue multimodal query for streaming', async () => {
      mockJobQueue.addQueryProcessingJob.mockResolvedValue('job-456');

      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/query/multimodal',
        headers: {
          authorization: `Bearer ${accessToken}`,
        },
        payload: {
          query: 'Analyze this image and table',
          multimodal_content: [
            { type: 'image', img_path: '/path/to/image.jpg' },
            { type: 'table', table_data: 'col1,col2\n1,2' },
          ],
          stream: true,
        },
      });

      expect(response.statusCode).toBe(200);
      const body = JSON.parse(response.body);
      expect(body.data.job_id).toBe('job-456');
      expect(body.data.metadata.multimodal_content_count).toBe(2);
    });

    it('should validate table content requirement', async () => {
      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/query/multimodal',
        headers: {
          authorization: `Bearer ${accessToken}`,
        },
        payload: {
          query: 'What is in this table?',
          multimodal_content: [
            {
              type: 'table',
              // missing table_data
            },
          ],
        },
      });

      expect(response.statusCode).toBe(400);
      const body = JSON.parse(response.body);
      expect(body.error.message).toContain('Table content requires table_data');
    });

    it('should validate equation content requirement', async () => {
      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/query/multimodal',
        headers: {
          authorization: `Bearer ${accessToken}`,
        },
        payload: {
          query: 'Explain this equation',
          multimodal_content: [
            {
              type: 'equation',
              // missing equation
            },
          ],
        },
      });

      expect(response.statusCode).toBe(400);
      const body = JSON.parse(response.body);
      expect(body.error.message).toContain('Equation content requires equation');
    });
  });

  describe('GET /api/v1/query/history', () => {
    beforeEach(async () => {
      // Create some test queries
      await global.testEnv.prisma.$executeRaw`
        INSERT INTO queries (id, user_id, query_text, query_type, mode, result_text, sources, processing_time_ms, created_at)
        VALUES 
          (uuid_generate_v4(), ${testUser.id}::uuid, 'What is AI?', 'text', 'mix', 'AI is...', '[]', 1500, CURRENT_TIMESTAMP - INTERVAL '1 hour'),
          (uuid_generate_v4(), ${testUser.id}::uuid, 'Analyze this image', 'multimodal', 'hybrid', 'The image shows...', '[{"doc_id":"doc-1"}]', 2500, CURRENT_TIMESTAMP - INTERVAL '30 minutes'),
          (uuid_generate_v4(), ${testUser.id}::uuid, 'What is ML?', 'text', 'local', 'ML is...', '[]', 1200, CURRENT_TIMESTAMP - INTERVAL '15 minutes')
      `;
    });

    it('should return query history with pagination', async () => {
      const response = await app.inject({
        method: 'GET',
        url: '/api/v1/query/history?page=1&limit=2',
        headers: {
          authorization: `Bearer ${accessToken}`,
        },
      });

      expect(response.statusCode).toBe(200);
      const body = JSON.parse(response.body);
      
      expect(body.success).toBe(true);
      expect(body.data.queries).toHaveLength(2);
      expect(body.data.pagination.current_page).toBe(1);
      expect(body.data.pagination.per_page).toBe(2);
      expect(body.data.pagination.total_queries).toBe(3);
      expect(body.data.pagination.total_pages).toBe(2);

      // Should be ordered by created_at DESC (most recent first)
      expect(new Date(body.data.queries[0].created_at))
        .toBeAfter(new Date(body.data.queries[1].created_at));
    });

    it('should filter query history by type', async () => {
      const response = await app.inject({
        method: 'GET',
        url: '/api/v1/query/history?type=text',
        headers: {
          authorization: `Bearer ${accessToken}`,
        },
      });

      expect(response.statusCode).toBe(200);
      const body = JSON.parse(response.body);
      
      expect(body.data.queries).toHaveLength(2);
      body.data.queries.forEach((query: any) => {
        expect(query.type).toBe('text');
      });
    });

    it('should return empty results for user with no queries', async () => {
      // Create another user with no queries
      const anotherUser = await authService.createUser({
        email: 'another@example.com',
        password: 'Password123!',
        role: 'user',
      });

      const anotherLogin = await authService.login({
        email: 'another@example.com',
        password: 'Password123!',
      });

      const response = await app.inject({
        method: 'GET',
        url: '/api/v1/query/history',
        headers: {
          authorization: `Bearer ${anotherLogin.accessToken}`,
        },
      });

      expect(response.statusCode).toBe(200);
      const body = JSON.parse(response.body);
      
      expect(body.data.queries).toHaveLength(0);
      expect(body.data.pagination.total_queries).toBe(0);
    });

    it('should handle pagination beyond available pages', async () => {
      const response = await app.inject({
        method: 'GET',
        url: '/api/v1/query/history?page=10&limit=20',
        headers: {
          authorization: `Bearer ${accessToken}`,
        },
      });

      expect(response.statusCode).toBe(200);
      const body = JSON.parse(response.body);
      
      expect(body.data.queries).toHaveLength(0);
      expect(body.data.pagination.current_page).toBe(10);
    });

    it('should return 401 without authentication', async () => {
      const response = await app.inject({
        method: 'GET',
        url: '/api/v1/query/history',
      });

      expect(response.statusCode).toBe(401);
    });

    it('should validate query parameters', async () => {
      const response = await app.inject({
        method: 'GET',
        url: '/api/v1/query/history?page=0&limit=100', // invalid page and limit
        headers: {
          authorization: `Bearer ${accessToken}`,
        },
      });

      expect(response.statusCode).toBe(400);
    });

    it('should include query metadata in response', async () => {
      const response = await app.inject({
        method: 'GET',
        url: '/api/v1/query/history',
        headers: {
          authorization: `Bearer ${accessToken}`,
        },
      });

      expect(response.statusCode).toBe(200);
      const body = JSON.parse(response.body);
      
      body.data.queries.forEach((query: any) => {
        expect(query).toHaveProperty('query_id');
        expect(query).toHaveProperty('query');
        expect(query).toHaveProperty('type');
        expect(query).toHaveProperty('mode');
        expect(query).toHaveProperty('created_at');
        expect(query).toHaveProperty('processing_time_ms');
        expect(query).toHaveProperty('sources_count');
        expect(typeof query.sources_count).toBe('number');
      });
    });
  });
});