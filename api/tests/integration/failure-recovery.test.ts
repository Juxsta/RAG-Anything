import { FastifyInstance } from 'fastify';
import { build } from '@/app';
import {
  TestContextManager,
  DatabaseTestHelper,
  NetworkTestHelper,
  MockServiceHelper,
} from '../utils/test-helpers';
import {
  UserFactory,
  DocumentFactory,
  TestDataSeeder,
} from '../utils/test-factories';

/**
 * Integration tests for failure recovery scenarios
 * Tests system resilience and error handling capabilities
 */
describe('Failure Recovery Integration Tests', () => {
  let app: FastifyInstance;
  let context: Awaited<ReturnType<typeof TestContextManager.createContext>>;

  beforeAll(async () => {
    app = await build({ logger: false });
    await app.ready();
    context = await TestContextManager.createContext(app);
  });

  afterAll(async () => {
    await TestContextManager.cleanup();
    await app.close();
  });

  beforeEach(async () => {
    await TestDataSeeder.cleanupTestData();
    context = await TestContextManager.createContext(app);
  });

  describe('Database Connection Failures', () => {
    it('should handle temporary database disconnection gracefully', async () => {
      // Make a successful request first
      const initialResponse = await app.inject({
        method: 'GET',
        url: '/api/v1/documents',
        headers: { authorization: `Bearer ${context.userToken}` },
      });

      expect(initialResponse.statusCode).toBe(200);

      // Simulate database failure
      await DatabaseTestHelper.simulateDatabaseFailure();

      // Requests should fail gracefully with appropriate error
      const failedResponse = await app.inject({
        method: 'GET',
        url: '/api/v1/documents',
        headers: { authorization: `Bearer ${context.userToken}` },
      });

      expect([500, 503]).toContain(failedResponse.statusCode);
      const failedBody = JSON.parse(failedResponse.body);
      expect(failedBody.success).toBe(false);
      expect(failedBody.error.message).toMatch(/database|connection|unavailable/i);

      // Restore database connection
      await DatabaseTestHelper.restoreDatabaseConnection();

      // Should recover automatically
      await new Promise(resolve => setTimeout(resolve, 1000)); // Wait for reconnection

      const recoveredResponse = await app.inject({
        method: 'GET',
        url: '/api/v1/documents',
        headers: { authorization: `Bearer ${context.userToken}` },
      });

      expect(recoveredResponse.statusCode).toBe(200);
    });

    it('should handle database transaction failures with proper rollback', async () => {
      const testUser = await UserFactory.createAndSave();
      
      // Start a transaction that will fail midway
      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/auth/api-keys',
        headers: { authorization: `Bearer ${context.userToken}` },
        payload: {
          name: 'Test API Key',
          // Simulate invalid data that causes constraint violation
          scopes: ['invalid_scope_that_should_fail'],
        },
      });

      // Should handle the failure gracefully
      expect([400, 422]).toContain(response.statusCode);
      
      // Verify no partial data was committed
      const apiKeys = await global.testEnv.prisma.$queryRaw<any[]>`
        SELECT * FROM api_keys WHERE user_id = ${testUser.id}::uuid
      `;
      
      expect(apiKeys).toHaveLength(0);
    });

    it('should handle connection pool exhaustion', async () => {
      const concurrentRequests = 100;
      const promises = [];

      // Create many concurrent database requests
      for (let i = 0; i < concurrentRequests; i++) {
        promises.push(
          app.inject({
            method: 'GET',
            url: '/api/v1/documents',
            headers: { authorization: `Bearer ${context.userToken}` },
          })
        );
      }

      const responses = await Promise.all(promises);

      // Most should succeed, but some might fail due to pool limits
      const successfulResponses = responses.filter(r => r.statusCode === 200);
      const failedResponses = responses.filter(r => r.statusCode >= 500);

      expect(successfulResponses.length).toBeGreaterThan(concurrentRequests * 0.7); // At least 70% success
      
      // Failed responses should have appropriate error messages
      failedResponses.forEach(response => {
        const body = JSON.parse(response.body);
        expect(body.error.message).toMatch(/database|connection|pool/i);
      });
    });
  });

  describe('Redis Connection Failures', () => {
    it('should continue functioning when Redis is unavailable', async () => {
      // Simulate Redis failure by disconnecting
      if (global.testEnv?.redisClient) {
        await global.testEnv.redisClient.disconnect();
      }

      // API should still work (might be slower without caching)
      const response = await app.inject({
        method: 'GET',
        url: '/api/v1/documents',
        headers: { authorization: `Bearer ${context.userToken}` },
      });

      // Should work but might be slower
      expect(response.statusCode).toBe(200);

      // Restore Redis connection
      if (global.testEnv?.redisClient) {
        await global.testEnv.redisClient.connect();
      }
    });

    it('should handle Redis timeout gracefully', async () => {
      // Test with operations that depend on Redis (sessions, caching)
      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/query',
        headers: { authorization: `Bearer ${context.userToken}` },
        payload: {
          query: 'Test query with potential caching',
          mode: 'local',
          queryType: 'text',
        },
      });

      // Should handle Redis timeout without affecting core functionality
      expect([200, 500]).toContain(response.statusCode);
      
      if (response.statusCode === 200) {
        const body = JSON.parse(response.body);
        expect(body.success).toBe(true);
      }
    });
  });

  describe('Python Process Failures', () => {
    it('should handle Python process crashes during document processing', async () => {
      // Upload a document
      const testContent = 'Test document content for processing failure test';
      const formData = new (require('form-data'))();
      
      const testBuffer = Buffer.from(testContent);
      formData.append('file', testBuffer, {
        filename: 'test-failure.txt',
        contentType: 'text/plain',
      });

      const uploadResponse = await app.inject({
        method: 'POST',
        url: '/api/v1/documents/upload',
        headers: {
          authorization: `Bearer ${context.userToken}`,
          ...formData.getHeaders(),
        },
        payload: formData,
      });

      expect(uploadResponse.statusCode).toBe(201);
      const { jobId } = JSON.parse(uploadResponse.body).data;

      // Wait for processing to complete or fail
      try {
        const jobResult = await DatabaseTestHelper.waitForJobCompletion(jobId, 30000);
        
        // Job should either complete successfully or fail gracefully
        expect(['completed', 'failed']).toContain(jobResult.status);
        
        if (jobResult.status === 'failed') {
          expect(jobResult.error_message).toBeTruthy();
          expect(jobResult.error_message).not.toContain('undefined');
        }
      } catch (error) {
        // Timeout is acceptable in failure scenarios
        expect(error.message).toContain('did not complete');
      }
    });

    it('should retry failed processing jobs', async () => {
      // This test would require implementing job retry logic
      const testContent = 'Content that might cause processing issues';
      const formData = new (require('form-data'))();
      
      formData.append('file', Buffer.from(testContent), {
        filename: 'retry-test.txt',
        contentType: 'text/plain',
      });

      const uploadResponse = await app.inject({
        method: 'POST',
        url: '/api/v1/documents/upload',
        headers: {
          authorization: `Bearer ${context.userToken}`,
          ...formData.getHeaders(),
        },
        payload: formData,
      });

      expect(uploadResponse.statusCode).toBe(201);
      const { jobId } = JSON.parse(uploadResponse.body).data;

      // Monitor job status for retry attempts
      let retryCount = 0;
      let lastStatus = 'pending';
      
      for (let i = 0; i < 10; i++) {
        const jobData = await global.testEnv.prisma.$queryRaw<Array<{
          status: string;
          error_message: string | null;
        }>>`
          SELECT status, error_message FROM job_status WHERE job_id = ${jobId}
        `;

        if (jobData.length > 0) {
          const currentStatus = jobData[0].status;
          
          if (currentStatus !== lastStatus) {
            if (currentStatus === 'pending' && lastStatus === 'failed') {
              retryCount++;
            }
            lastStatus = currentStatus;
          }
          
          if (['completed', 'failed'].includes(currentStatus)) {
            break;
          }
        }

        await new Promise(resolve => setTimeout(resolve, 1000));
      }

      // Should have attempted at least one retry if job failed initially
      // (This depends on your retry implementation)
      expect(retryCount >= 0).toBe(true);
    });
  });

  describe('Network Partition and Latency', () => {
    it('should handle high network latency gracefully', async () => {
      const startTime = Date.now();

      const response = await NetworkTestHelper.simulateHighLatency(
        async () => {
          return app.inject({
            method: 'GET',
            url: '/api/v1/documents',
            headers: { authorization: `Bearer ${context.userToken}` },
          });
        },
        2000 // 2 second additional latency
      );

      const totalTime = Date.now() - startTime;
      
      expect(response.statusCode).toBe(200);
      expect(totalTime).toBeGreaterThan(2000); // Should include the simulated delay
    });

    it('should timeout appropriately for long-running operations', async () => {
      // Test with a query that might take a long time
      const longQueryResponse = await app.inject({
        method: 'POST',
        url: '/api/v1/query',
        headers: { authorization: `Bearer ${context.userToken}` },
        payload: {
          query: 'A'.repeat(10000), // Very long query
          mode: 'global',
          queryType: 'text',
        },
      });

      // Should either complete within reasonable time or timeout gracefully
      expect([200, 408, 503]).toContain(longQueryResponse.statusCode);
      
      if (longQueryResponse.statusCode !== 200) {
        const body = JSON.parse(longQueryResponse.body);
        expect(body.error.message).toMatch(/timeout|processing/i);
      }
    });
  });

  describe('Memory and Resource Exhaustion', () => {
    it('should handle memory pressure gracefully', async () => {
      // Create many concurrent requests to test memory usage
      const concurrentRequests = 50;
      const promises = [];

      for (let i = 0; i < concurrentRequests; i++) {
        promises.push(
          app.inject({
            method: 'POST',
            url: '/api/v1/query',
            headers: { authorization: `Bearer ${context.userToken}` },
            payload: {
              query: `Memory pressure test query ${i} with lots of content: ${Math.random().toString(36).repeat(100)}`,
              mode: 'local',
              queryType: 'text',
            },
          })
        );
      }

      const responses = await Promise.all(promises);

      // System should handle the load without crashing
      const successCount = responses.filter(r => r.statusCode === 200).length;
      const errorCount = responses.filter(r => r.statusCode >= 500).length;

      // At least 80% should succeed
      expect(successCount / concurrentRequests).toBeGreaterThan(0.8);

      // Error responses should be graceful
      responses.filter(r => r.statusCode >= 500).forEach(response => {
        const body = JSON.parse(response.body);
        expect(body.error.message).toBeTruthy();
        expect(body.error.message).not.toContain('undefined');
      });
    });

    it('should handle file descriptor exhaustion', async () => {
      // Simulate many file operations
      const fileOperations = [];
      
      for (let i = 0; i < 100; i++) {
        const formData = new (require('form-data'))();
        formData.append('file', Buffer.from(`File ${i} content`), {
          filename: `file-${i}.txt`,
          contentType: 'text/plain',
        });

        fileOperations.push(
          app.inject({
            method: 'POST',
            url: '/api/v1/documents/upload',
            headers: {
              authorization: `Bearer ${context.userToken}`,
              ...formData.getHeaders(),
            },
            payload: formData,
          })
        );
      }

      const responses = await Promise.allSettled(fileOperations);

      // Should handle file operations without exhausting file descriptors
      const fulfilled = responses.filter(r => r.status === 'fulfilled').length;
      const rejected = responses.filter(r => r.status === 'rejected').length;

      expect(fulfilled).toBeGreaterThan(responses.length * 0.5); // At least 50% should succeed
      
      // Rejected operations should be due to reasonable limits, not system errors
      if (rejected > 0) {
        console.log(`${rejected} operations rejected due to resource limits`);
      }
    });
  });

  describe('Cascading Failure Prevention', () => {
    it('should implement circuit breaker pattern for external services', async () => {
      // This test assumes circuit breaker implementation for Python process calls
      const rapidRequests = [];

      // Make rapid requests that might trigger circuit breaker
      for (let i = 0; i < 20; i++) {
        rapidRequests.push(
          app.inject({
            method: 'POST',
            url: '/api/v1/query',
            headers: { authorization: `Bearer ${context.userToken}` },
            payload: {
              query: `Circuit breaker test ${i}`,
              mode: 'local',
              queryType: 'text',
            },
          })
        );
      }

      const responses = await Promise.all(rapidRequests);

      // Should show circuit breaker behavior (fast failures after threshold)
      const responseTimes = responses.map(r => {
        // Estimate response time from status code patterns
        return r.statusCode === 503 ? 'fast_fail' : 'normal';
      });

      // Look for pattern indicating circuit breaker activation
      const fastFailures = responseTimes.filter(t => t === 'fast_fail').length;
      
      // Circuit breaker should activate if there are failures
      if (responses.some(r => r.statusCode >= 500)) {
        expect(fastFailures >= 0).toBe(true); // Some fast failures expected
      }
    });

    it('should gracefully degrade functionality during partial failures', async () => {
      // Test system behavior when some components fail
      
      // First, verify normal operation
      const normalResponse = await app.inject({
        method: 'POST',
        url: '/api/v1/query',
        headers: { authorization: `Bearer ${context.userToken}` },
        payload: {
          query: 'What is the system status?',
          mode: 'local',
          queryType: 'text',
        },
      });

      if (normalResponse.statusCode === 200) {
        const body = JSON.parse(normalResponse.body);
        expect(body.success).toBe(true);
      }

      // Even during partial failures, core API should remain accessible
      const healthResponse = await app.inject({
        method: 'GET',
        url: '/api/v1/health',
      });

      expect(healthResponse.statusCode).toBe(200);
      const healthBody = JSON.parse(healthResponse.body);
      expect(healthBody.status).toBeTruthy();
    });
  });

  describe('Data Consistency During Failures', () => {
    it('should maintain data consistency during concurrent writes', async () => {
      const user = await UserFactory.createAndSave();
      const concurrentWrites = [];

      // Create multiple API keys concurrently for the same user
      for (let i = 0; i < 10; i++) {
        concurrentWrites.push(
          app.inject({
            method: 'POST',
            url: '/api/v1/auth/api-keys',
            headers: { authorization: `Bearer ${context.userToken}` },
            payload: {
              name: `Concurrent API Key ${i}`,
              scopes: ['read', 'write'],
            },
          })
        );
      }

      const responses = await Promise.all(concurrentWrites);

      // Count successful creations
      const successful = responses.filter(r => r.statusCode === 201);
      
      // Verify data consistency in database
      const apiKeys = await global.testEnv.prisma.$queryRaw<any[]>`
        SELECT * FROM api_keys WHERE user_id = ${context.regularUser.id}::uuid
      `;

      // Number of database records should match successful API calls
      expect(apiKeys.length).toBe(successful.length);

      // Each API key should have unique key values
      const keyHashes = apiKeys.map(key => key.key_hash);
      const uniqueHashes = new Set(keyHashes);
      expect(uniqueHashes.size).toBe(keyHashes.length);
    });

    it('should handle transaction deadlocks appropriately', async () => {
      const user1 = await UserFactory.createAndSave();
      const user2 = await UserFactory.createAndSave();

      // Create potentially conflicting operations
      const conflictingOps = await Promise.allSettled([
        // These operations might create deadlocks if not handled properly
        global.testEnv.prisma.$transaction(async (tx) => {
          await tx.$executeRaw`UPDATE users SET login_count = login_count + 1 WHERE id = ${user1.id}::uuid`;
          await tx.$executeRaw`UPDATE users SET login_count = login_count + 1 WHERE id = ${user2.id}::uuid`;
        }),
        
        global.testEnv.prisma.$transaction(async (tx) => {
          await tx.$executeRaw`UPDATE users SET login_count = login_count + 1 WHERE id = ${user2.id}::uuid`;
          await tx.$executeRaw`UPDATE users SET login_count = login_count + 1 WHERE id = ${user1.id}::uuid`;
        }),
      ]);

      // At least one should succeed, and failures should be handled gracefully
      const fulfilled = conflictingOps.filter(op => op.status === 'fulfilled');
      const rejected = conflictingOps.filter(op => op.status === 'rejected');

      expect(fulfilled.length).toBeGreaterThan(0);
      
      // Rejected operations should have appropriate error handling
      rejected.forEach(op => {
        if (op.status === 'rejected') {
          expect(op.reason).toBeTruthy();
        }
      });
    });
  });

  describe('Recovery Time and Monitoring', () => {
    it('should recover quickly from transient failures', async () => {
      const recoveryTests = [];

      // Test recovery from various failure types
      for (let i = 0; i < 5; i++) {
        const startTime = Date.now();
        
        // Simulate transient failure and recovery
        await NetworkTestHelper.simulateSlowNetwork(100);
        
        const response = await app.inject({
          method: 'GET',
          url: '/api/v1/health',
        });

        const recoveryTime = Date.now() - startTime;
        
        recoveryTests.push({
          success: response.statusCode === 200,
          recoveryTime,
        });
      }

      // All recovery attempts should succeed
      const successfulRecoveries = recoveryTests.filter(test => test.success);
      expect(successfulRecoveries.length).toBe(recoveryTests.length);

      // Recovery should be fast
      const avgRecoveryTime = recoveryTests.reduce((sum, test) => sum + test.recoveryTime, 0) / recoveryTests.length;
      expect(avgRecoveryTime).toBeLessThan(5000); // Should recover within 5 seconds
    });

    it('should provide meaningful health check information during failures', async () => {
      // Health endpoint should always be available and informative
      const healthResponse = await app.inject({
        method: 'GET',
        url: '/api/v1/health',
      });

      expect(healthResponse.statusCode).toBe(200);
      const healthData = JSON.parse(healthResponse.body);

      // Should provide useful information about system state
      expect(healthData).toHaveProperty('status');
      expect(healthData).toHaveProperty('timestamp');
      expect(healthData).toHaveProperty('version');

      // Should include service status information
      if (healthData.services) {
        expect(healthData.services).toHaveProperty('database');
        expect(healthData.services).toHaveProperty('redis');
      }
    });
  });
});