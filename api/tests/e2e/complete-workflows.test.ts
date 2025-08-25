import { FastifyInstance } from 'fastify';
import { build } from '@/app';
import {
  TestContextManager,
  WebSocketTestHelper,
  FileUploadHelper,
  DatabaseTestHelper,
  PerformanceTestHelper,
} from '../utils/test-helpers';
import {
  UserFactory,
  DocumentFactory,
  QueryFactory,
  TestDataSeeder,
} from '../utils/test-factories';

/**
 * End-to-End tests covering complete user workflows
 * These tests simulate real user interactions and validate the entire system
 */
describe('Complete User Workflows E2E Tests', () => {
  let app: FastifyInstance;
  let context: Awaited<ReturnType<typeof TestContextManager.createContext>>;
  let wsHelper: WebSocketTestHelper;

  beforeAll(async () => {
    app = await build({ logger: false });
    await app.ready();
    context = await TestContextManager.createContext(app);
  });

  afterAll(async () => {
    if (wsHelper) {
      await wsHelper.disconnect();
    }
    await TestContextManager.cleanup();
    await app.close();
  });

  beforeEach(async () => {
    await TestDataSeeder.cleanupTestData();
    PerformanceTestHelper.clearMetrics();
    
    // Create fresh context for each test
    context = await TestContextManager.createContext(app);
  });

  afterEach(async () => {
    if (wsHelper?.isConnected()) {
      await wsHelper.disconnect();
    }
    await FileUploadHelper.cleanup();
  });

  describe('Complete Document Processing Workflow', () => {
    it('should handle complete document upload → processing → query workflow', async () => {
      const stopTimer = PerformanceTestHelper.startTimer('Complete Workflow');

      // Step 1: Upload document
      const testContent = `
        # Machine Learning Overview
        
        Machine learning is a subset of artificial intelligence that focuses on algorithms
        that can learn and make predictions from data without being explicitly programmed.
        
        ## Key Concepts
        - Supervised learning
        - Unsupervised learning
        - Reinforcement learning
        
        ## Applications
        Machine learning has applications in various fields including:
        - Natural language processing
        - Computer vision
        - Recommendation systems
        - Autonomous vehicles
      `;

      const filePath = await FileUploadHelper.createTestFile(testContent, 'ml-overview.md');
      const uploadResponse = await FileUploadHelper.uploadFile(app, filePath, context.userToken);

      expect(uploadResponse.statusCode).toBe(201);
      expect(uploadResponse.body.success).toBe(true);
      expect(uploadResponse.body.data).toHaveProperty('documentId');
      expect(uploadResponse.body.data).toHaveProperty('jobId');

      const { documentId, jobId } = uploadResponse.body.data;

      // Step 2: Monitor processing via WebSocket
      wsHelper = new WebSocketTestHelper(context.baseUrl, context.userToken);
      await wsHelper.connect();

      // Subscribe to job updates
      wsHelper.emit('subscribe', { jobId });

      // Wait for processing completion
      const jobCompletedEvent = await wsHelper.waitForEvent('job:completed', 30000);
      expect(jobCompletedEvent).toBeTruthy();
      expect(jobCompletedEvent[0].jobId).toBe(jobId);
      expect(jobCompletedEvent[0].status).toBe('completed');

      // Step 3: Verify document status in database
      const documents = await DatabaseTestHelper.getUserDocuments(context.regularUser.id);
      expect(documents).toHaveLength(1);
      expect(documents[0].id).toBe(documentId);
      expect(documents[0].status).toBe('processed');

      // Step 4: Query the processed document
      const queryResponse = await app.inject({
        method: 'POST',
        url: '/api/v1/query',
        headers: { authorization: `Bearer ${context.userToken}` },
        payload: {
          query: 'What are the key concepts in machine learning?',
          mode: 'local',
          queryType: 'text',
        },
      });

      expect(queryResponse.statusCode).toBe(200);
      const queryBody = JSON.parse(queryResponse.body);
      expect(queryBody.success).toBe(true);
      expect(queryBody.data).toHaveProperty('result');
      expect(queryBody.data).toHaveProperty('sources');
      expect(queryBody.data.sources).toHaveLength(1);
      expect(queryBody.data.sources[0].documentId).toBe(documentId);

      // Step 5: Verify query was logged
      const queryHistory = await DatabaseTestHelper.getQueryHistory(context.regularUser.id, 1);
      expect(queryHistory).toHaveLength(1);
      expect(queryHistory[0].query_text).toBe('What are the key concepts in machine learning?');

      const totalTime = stopTimer();
      expect(totalTime).toBeLessThan(60000); // Should complete within 60 seconds

      // Log performance metrics
      console.log('Complete workflow performance:', PerformanceTestHelper.getAllMetrics());
    });

    it('should handle multiple document upload and batch processing', async () => {
      const documents = DocumentFactory.createBatch(3, {
        originalName: 'batch-doc.txt',
        content: Buffer.from('This is a test document for batch processing.'),
      });

      const uploadPromises = documents.map(async (doc, index) => {
        const filePath = await FileUploadHelper.createTestFile(
          doc.content!,
          `batch-doc-${index}.txt`
        );
        return FileUploadHelper.uploadFile(app, filePath, context.userToken);
      });

      const uploadResponses = await Promise.all(uploadPromises);

      // All uploads should succeed
      uploadResponses.forEach((response) => {
        expect(response.statusCode).toBe(201);
        expect(response.body.success).toBe(true);
      });

      // Wait for all processing to complete
      const jobIds = uploadResponses.map(r => r.body.data.jobId);
      
      for (const jobId of jobIds) {
        await DatabaseTestHelper.waitForJobCompletion(jobId, 30000);
      }

      // Verify all documents are processed
      const processedDocs = await DatabaseTestHelper.getUserDocuments(context.regularUser.id);
      expect(processedDocs).toHaveLength(3);
      processedDocs.forEach(doc => {
        expect(doc.status).toBe('processed');
      });

      // Test cross-document query
      const queryResponse = await app.inject({
        method: 'POST',
        url: '/api/v1/query',
        headers: { authorization: `Bearer ${context.userToken}` },
        payload: {
          query: 'What information is available in the uploaded documents?',
          mode: 'global',
          queryType: 'text',
        },
      });

      expect(queryResponse.statusCode).toBe(200);
      const queryBody = JSON.parse(queryResponse.body);
      expect(queryBody.data.sources).toHaveLength(3);
    });
  });

  describe('Multi-User Scenarios', () => {
    it('should handle concurrent users without data leakage', async () => {
      // Create additional users
      const user1 = await UserFactory.createAndSave({
        email: 'user1@test.com',
        password: 'Password123!',
      });

      const user2 = await UserFactory.createAndSave({
        email: 'user2@test.com',
        password: 'Password123!',
      });

      // Get auth tokens
      const user1Login = await app.inject({
        method: 'POST',
        url: '/api/v1/auth/login',
        payload: { email: user1.email, password: user1.password },
      });

      const user2Login = await app.inject({
        method: 'POST',
        url: '/api/v1/auth/login',
        payload: { email: user2.email, password: user2.password },
      });

      const user1Token = JSON.parse(user1Login.body).data.access_token;
      const user2Token = JSON.parse(user2Login.body).data.access_token;

      // User 1 uploads a private document
      const user1FilePath = await FileUploadHelper.createTestFile(
        'This is user 1 private content',
        'user1-private.txt'
      );
      const user1Upload = await FileUploadHelper.uploadFile(app, user1FilePath, user1Token);

      // User 2 uploads a different document
      const user2FilePath = await FileUploadHelper.createTestFile(
        'This is user 2 private content',
        'user2-private.txt'
      );
      const user2Upload = await FileUploadHelper.uploadFile(app, user2FilePath, user2Token);

      expect(user1Upload.statusCode).toBe(201);
      expect(user2Upload.statusCode).toBe(201);

      // Wait for processing
      await DatabaseTestHelper.waitForJobCompletion(user1Upload.body.data.jobId, 30000);
      await DatabaseTestHelper.waitForJobCompletion(user2Upload.body.data.jobId, 30000);

      // User 1 queries - should only see their own documents
      const user1Query = await app.inject({
        method: 'POST',
        url: '/api/v1/query',
        headers: { authorization: `Bearer ${user1Token}` },
        payload: {
          query: 'What content is available?',
          mode: 'local',
          queryType: 'text',
        },
      });

      expect(user1Query.statusCode).toBe(200);
      const user1QueryBody = JSON.parse(user1Query.body);
      expect(user1QueryBody.data.sources).toHaveLength(1);
      expect(user1QueryBody.data.sources[0].documentId).toBe(user1Upload.body.data.documentId);

      // User 2 queries - should only see their own documents
      const user2Query = await app.inject({
        method: 'POST',
        url: '/api/v1/query',
        headers: { authorization: `Bearer ${user2Token}` },
        payload: {
          query: 'What content is available?',
          mode: 'local',
          queryType: 'text',
        },
      });

      expect(user2Query.statusCode).toBe(200);
      const user2QueryBody = JSON.parse(user2Query.body);
      expect(user2QueryBody.data.sources).toHaveLength(1);
      expect(user2QueryBody.data.sources[0].documentId).toBe(user2Upload.body.data.documentId);

      // Verify data isolation
      expect(user1QueryBody.data.sources[0].documentId).not.toBe(
        user2QueryBody.data.sources[0].documentId
      );
    });

    it('should handle admin access to all user data', async () => {
      // Regular user uploads document
      const userFilePath = await FileUploadHelper.createTestFile(
        'Regular user document content',
        'user-doc.txt'
      );
      const userUpload = await FileUploadHelper.uploadFile(app, userFilePath, context.userToken);
      
      await DatabaseTestHelper.waitForJobCompletion(userUpload.body.data.jobId, 30000);

      // Admin should be able to access system-wide information
      const adminSystemQuery = await app.inject({
        method: 'GET',
        url: '/api/v1/admin/system/stats',
        headers: { authorization: `Bearer ${context.adminToken}` },
      });

      expect(adminSystemQuery.statusCode).toBe(200);
      const statsBody = JSON.parse(adminSystemQuery.body);
      expect(statsBody.data.totalDocuments).toBeGreaterThan(0);
      expect(statsBody.data.totalUsers).toBeGreaterThan(0);
    });
  });

  describe('WebSocket Real-time Features', () => {
    beforeEach(async () => {
      wsHelper = new WebSocketTestHelper(context.baseUrl, context.userToken);
      await wsHelper.connect();
    });

    it('should receive real-time job progress updates', async () => {
      // Upload a document to trigger job processing
      const filePath = await FileUploadHelper.createTestFile(
        'Document content for job progress testing',
        'progress-test.txt'
      );
      const uploadResponse = await FileUploadHelper.uploadFile(app, filePath, context.userToken);
      const { jobId } = uploadResponse.body.data;

      // Subscribe to job updates
      wsHelper.emit('subscribe', { jobId });

      // Should receive progress updates
      const progressEvent = await wsHelper.waitForEvent('job:progress', 15000);
      expect(progressEvent).toBeTruthy();
      expect(progressEvent[0].jobId).toBe(jobId);
      expect(progressEvent[0].progress).toBeGreaterThan(0);

      // Should receive completion event
      const completedEvent = await wsHelper.waitForEvent('job:completed', 30000);
      expect(completedEvent).toBeTruthy();
      expect(completedEvent[0].jobId).toBe(jobId);
      expect(completedEvent[0].status).toBe('completed');
    });

    it('should handle WebSocket authentication properly', async () => {
      // Disconnect current authenticated connection
      await wsHelper.disconnect();

      // Try to connect without authentication
      const unauthenticatedWs = new WebSocketTestHelper(context.baseUrl);
      
      await expect(unauthenticatedWs.connect()).rejects.toThrow('WebSocket connection failed');

      // Try with invalid token
      const invalidTokenWs = new WebSocketTestHelper(context.baseUrl, 'invalid-token');
      
      await expect(invalidTokenWs.connect()).rejects.toThrow('WebSocket connection failed');

      // Valid connection should work
      const validWs = new WebSocketTestHelper(context.baseUrl, context.userToken);
      await expect(validWs.connect()).resolves.not.toThrow();
      await validWs.disconnect();
    });

    it('should handle system notifications for admins', async () => {
      // Connect as admin
      await wsHelper.disconnect();
      wsHelper = new WebSocketTestHelper(context.baseUrl, context.adminToken);
      await wsHelper.connect();

      // Join admin channels
      wsHelper.emit('join', { room: 'system:updates' });

      // Simulate system event (this would normally be triggered by system monitoring)
      // For testing, we'll use the WebSocket service directly
      const systemEventResponse = await app.inject({
        method: 'POST',
        url: '/api/v1/admin/system/broadcast',
        headers: { authorization: `Bearer ${context.adminToken}` },
        payload: {
          event: 'system:status',
          data: { status: 'healthy', message: 'All systems operational' },
        },
      });

      expect(systemEventResponse.statusCode).toBe(200);

      // Admin should receive the system notification
      const systemNotification = await wsHelper.waitForEvent('system:status', 5000);
      expect(systemNotification).toBeTruthy();
      expect(systemNotification[0].status).toBe('healthy');
    });
  });

  describe('Error Recovery Scenarios', () => {
    it('should handle database connection loss gracefully', async () => {
      // Simulate database failure
      await DatabaseTestHelper.simulateDatabaseFailure();

      const response = await app.inject({
        method: 'GET',
        url: '/api/v1/documents',
        headers: { authorization: `Bearer ${context.userToken}` },
      });

      // Should return appropriate error, not crash
      expect([500, 503]).toContain(response.statusCode);
      const body = JSON.parse(response.body);
      expect(body.success).toBe(false);
      expect(body.error.message).toContain('database');

      // Restore connection
      await DatabaseTestHelper.restoreDatabaseConnection();

      // Should work again
      const retryResponse = await app.inject({
        method: 'GET',
        url: '/api/v1/documents',
        headers: { authorization: `Bearer ${context.userToken}` },
      });

      expect(retryResponse.statusCode).toBe(200);
    });

    it('should handle WebSocket disconnections gracefully', async () => {
      wsHelper = new WebSocketTestHelper(context.baseUrl, context.userToken);
      await wsHelper.connect();

      // Start a long-running job
      const filePath = await FileUploadHelper.createTestFile(
        'Content for disconnect test',
        'disconnect-test.txt'
      );
      const uploadResponse = await FileUploadHelper.uploadFile(app, filePath, context.userToken);
      const { jobId } = uploadResponse.body.data;

      wsHelper.emit('subscribe', { jobId });

      // Simulate disconnection
      await wsHelper.disconnect();

      // Job should continue processing even without WebSocket connection
      await DatabaseTestHelper.waitForJobCompletion(jobId, 30000);

      // Verify job completed successfully
      const completedJob = await DatabaseTestHelper.waitForJobCompletion(jobId, 1000);
      expect(completedJob.status).toBe('completed');
    });

    it('should handle large file uploads with timeouts', async () => {
      // Create a large file (simulated)
      const largeContent = 'A'.repeat(10 * 1024 * 1024); // 10MB
      const largeFilePath = await FileUploadHelper.createTestFile(largeContent, 'large-file.txt');

      const uploadResponse = await FileUploadHelper.uploadFile(app, largeFilePath, context.userToken);

      // Should handle large files (may take longer but should not fail)
      expect(uploadResponse.statusCode).toBe(201);
      
      const { jobId } = uploadResponse.body.data;
      
      // Wait for processing with extended timeout
      const jobResult = await DatabaseTestHelper.waitForJobCompletion(jobId, 60000);
      expect(['completed', 'failed']).toContain(jobResult.status);
    });
  });

  describe('Concurrent Operations', () => {
    it('should handle concurrent uploads from same user', async () => {
      const concurrentUploads = 5;
      const uploadPromises = [];

      for (let i = 0; i < concurrentUploads; i++) {
        const filePath = FileUploadHelper.createTestFile(
          `Document ${i} content`,
          `concurrent-${i}.txt`
        );
        uploadPromises.push(
          filePath.then(path => 
            FileUploadHelper.uploadFile(app, path, context.userToken)
          )
        );
      }

      const uploadResponses = await Promise.all(uploadPromises);

      // All uploads should succeed
      uploadResponses.forEach((response, index) => {
        expect(response.statusCode).toBe(201);
        expect(response.body.success).toBe(true);
      });

      // Wait for all jobs to complete
      const jobIds = uploadResponses.map(r => r.body.data.jobId);
      const jobPromises = jobIds.map(jobId => 
        DatabaseTestHelper.waitForJobCompletion(jobId, 60000)
      );

      const completedJobs = await Promise.all(jobPromises);
      completedJobs.forEach(job => {
        expect(['completed', 'failed']).toContain(job.status);
      });
    });

    it('should handle concurrent queries efficiently', async () => {
      // First, upload a document to query against
      const filePath = await FileUploadHelper.createTestFile(
        'Shared document for concurrent queries',
        'shared-doc.txt'
      );
      const uploadResponse = await FileUploadHelper.uploadFile(app, filePath, context.userToken);
      await DatabaseTestHelper.waitForJobCompletion(uploadResponse.body.data.jobId, 30000);

      const concurrentQueries = 10;
      const queries = QueryFactory.createBatch(concurrentQueries);

      const queryPromises = queries.map(query => 
        PerformanceTestHelper.measureEndpoint(
          app,
          'POST',
          '/api/v1/query',
          {
            headers: { authorization: `Bearer ${context.userToken}` },
            payload: query,
          }
        )
      );

      const results = await Promise.all(queryPromises);

      // All queries should succeed
      results.forEach((result, index) => {
        expect(result.response.statusCode).toBe(200);
        expect(result.duration).toBeLessThan(30000); // Should complete within 30 seconds
      });

      // Check performance metrics
      const metrics = PerformanceTestHelper.getMetrics('POST /api/v1/query');
      expect(metrics.avg).toBeLessThan(10000); // Average response time should be reasonable
      expect(metrics.p95).toBeLessThan(20000); // 95th percentile should be acceptable
    });
  });

  describe('System Integration', () => {
    it('should maintain data consistency across all services', async () => {
      // Upload document
      const filePath = await FileUploadHelper.createTestFile(
        'Integration test content',
        'integration-test.txt'
      );
      const uploadResponse = await FileUploadHelper.uploadFile(app, filePath, context.userToken);
      const { documentId, jobId } = uploadResponse.body.data;

      // Wait for processing
      await DatabaseTestHelper.waitForJobCompletion(jobId, 30000);

      // Verify document in database
      const documents = await DatabaseTestHelper.getUserDocuments(context.regularUser.id);
      const document = documents.find(doc => doc.id === documentId);
      expect(document).toBeTruthy();
      expect(document.status).toBe('processed');

      // Query the document
      const queryResponse = await app.inject({
        method: 'POST',
        url: '/api/v1/query',
        headers: { authorization: `Bearer ${context.userToken}` },
        payload: {
          query: 'What is the content of this document?',
          mode: 'local',
          queryType: 'text',
        },
      });

      expect(queryResponse.statusCode).toBe(200);
      const queryBody = JSON.parse(queryResponse.body);

      // Verify query was logged with correct document reference
      const queryHistory = await DatabaseTestHelper.getQueryHistory(context.regularUser.id, 1);
      expect(queryHistory).toHaveLength(1);
      expect(queryHistory[0].sources).toContainEqual(
        expect.objectContaining({ documentId })
      );

      // Verify system metrics are updated
      const metricsResponse = await app.inject({
        method: 'GET',
        url: '/api/v1/admin/system/metrics',
        headers: { authorization: `Bearer ${context.adminToken}` },
      });

      expect(metricsResponse.statusCode).toBe(200);
      const metricsBody = JSON.parse(metricsResponse.body);
      expect(metricsBody.data.documentsProcessed).toBeGreaterThan(0);
      expect(metricsBody.data.queriesExecuted).toBeGreaterThan(0);
    });
  });
});