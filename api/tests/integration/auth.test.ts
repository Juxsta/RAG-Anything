import { FastifyInstance } from 'fastify';
import { build } from '@/app';
import { authService } from '@/services/auth';

describe('Auth Integration Tests', () => {
  let app: FastifyInstance;

  beforeAll(async () => {
    app = await build({ logger: false });
    await app.ready();
  });

  afterAll(async () => {
    await app.close();
  });

  beforeEach(async () => {
    // Clean up and prepare test data
    if (global.testEnv?.prisma) {
      await global.testEnv.prisma.$executeRaw`TRUNCATE TABLE refresh_tokens CASCADE`;
      await global.testEnv.prisma.$executeRaw`TRUNCATE TABLE api_keys CASCADE`;
      await global.testEnv.prisma.$executeRaw`TRUNCATE TABLE users CASCADE`;
    }
  });

  describe('POST /api/v1/auth/login', () => {
    it('should login with valid credentials', async () => {
      // Create a test user
      const testUser = await authService.createUser({
        email: 'test@example.com',
        password: 'SecurePassword123!',
        role: 'user',
      });

      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/auth/login',
        payload: {
          email: 'test@example.com',
          password: 'SecurePassword123!',
        },
      });

      expect(response.statusCode).toBe(200);
      const body = JSON.parse(response.body);
      
      expect(body.success).toBe(true);
      expect(body.data).toHaveProperty('access_token');
      expect(body.data).toHaveProperty('refresh_token');
      expect(body.data.token_type).toBe('Bearer');
      expect(body.data.expires_in).toBe(3600);
      expect(body.data.user).toEqual({
        id: testUser.id,
        email: 'test@example.com',
        role: 'user',
        apiKey: false,
        emailVerified: false,
      });
    });

    it('should return 401 for invalid email', async () => {
      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/auth/login',
        payload: {
          email: 'nonexistent@example.com',
          password: 'password123',
        },
      });

      expect(response.statusCode).toBe(401);
      const body = JSON.parse(response.body);
      expect(body.success).toBe(false);
      expect(body.error.message).toContain('Invalid email or password');
    });

    it('should return 401 for invalid password', async () => {
      await authService.createUser({
        email: 'test@example.com',
        password: 'SecurePassword123!',
        role: 'user',
      });

      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/auth/login',
        payload: {
          email: 'test@example.com',
          password: 'wrongpassword',
        },
      });

      expect(response.statusCode).toBe(401);
      const body = JSON.parse(response.body);
      expect(body.success).toBe(false);
    });

    it('should return 400 for invalid request body', async () => {
      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/auth/login',
        payload: {
          email: 'invalid-email',
          // password missing
        },
      });

      expect(response.statusCode).toBe(400);
    });

    it('should return 401 for deactivated user', async () => {
      const testUser = await authService.createUser({
        email: 'test@example.com',
        password: 'SecurePassword123!',
        role: 'user',
      });

      // Deactivate user
      await global.testEnv.prisma.$executeRaw`
        UPDATE users SET is_active = false WHERE id = ${testUser.id}::uuid
      `;

      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/auth/login',
        payload: {
          email: 'test@example.com',
          password: 'SecurePassword123!',
        },
      });

      expect(response.statusCode).toBe(401);
    });
  });

  describe('POST /api/v1/auth/refresh', () => {
    it('should refresh tokens with valid refresh token', async () => {
      // Create user and login to get refresh token
      await authService.createUser({
        email: 'test@example.com',
        password: 'SecurePassword123!',
        role: 'user',
      });

      const loginResponse = await authService.login({
        email: 'test@example.com',
        password: 'SecurePassword123!',
      });

      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/auth/refresh',
        payload: {
          refresh_token: loginResponse.refreshToken,
        },
      });

      expect(response.statusCode).toBe(200);
      const body = JSON.parse(response.body);
      
      expect(body.success).toBe(true);
      expect(body.data).toHaveProperty('access_token');
      expect(body.data).toHaveProperty('refresh_token');
      expect(body.data.token_type).toBe('Bearer');
      expect(body.data.expires_in).toBe(3600);

      // New tokens should be different from original
      expect(body.data.access_token).not.toBe(loginResponse.accessToken);
      expect(body.data.refresh_token).not.toBe(loginResponse.refreshToken);
    });

    it('should return 401 for invalid refresh token', async () => {
      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/auth/refresh',
        payload: {
          refresh_token: 'invalid-refresh-token',
        },
      });

      expect(response.statusCode).toBe(401);
      const body = JSON.parse(response.body);
      expect(body.success).toBe(false);
    });

    it('should return 401 for expired refresh token', async () => {
      // Create user and login
      const testUser = await authService.createUser({
        email: 'test@example.com',
        password: 'SecurePassword123!',
        role: 'user',
      });

      // Insert expired refresh token manually
      const expiredToken = 'expired-token-123';
      await global.testEnv.prisma.$executeRaw`
        INSERT INTO refresh_tokens (user_id, token, expires_at, revoked)
        VALUES (${testUser.id}::uuid, ${expiredToken}, ${new Date(Date.now() - 86400000)}, false)
      `;

      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/auth/refresh',
        payload: {
          refresh_token: expiredToken,
        },
      });

      expect(response.statusCode).toBe(401);
    });

    it('should return 401 for revoked refresh token', async () => {
      const testUser = await authService.createUser({
        email: 'test@example.com',
        password: 'SecurePassword123!',
        role: 'user',
      });

      // Insert revoked refresh token manually
      const revokedToken = 'revoked-token-123';
      await global.testEnv.prisma.$executeRaw`
        INSERT INTO refresh_tokens (user_id, token, expires_at, revoked)
        VALUES (${testUser.id}::uuid, ${revokedToken}, ${new Date(Date.now() + 86400000)}, true)
      `;

      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/auth/refresh',
        payload: {
          refresh_token: revokedToken,
        },
      });

      expect(response.statusCode).toBe(401);
    });
  });

  describe('POST /api/v1/auth/api-keys', () => {
    let accessToken: string;
    let testUser: any;

    beforeEach(async () => {
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

    it('should create API key with valid authentication', async () => {
      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/auth/api-keys',
        headers: {
          authorization: `Bearer ${accessToken}`,
        },
        payload: {
          name: 'Test API Key',
          permissions: ['read', 'write'],
        },
      });

      expect(response.statusCode).toBe(201);
      const body = JSON.parse(response.body);
      
      expect(body.success).toBe(true);
      expect(body.data.name).toBe('Test API Key');
      expect(body.data.key).toMatch(/^rag_/);
      expect(body.data.key).toHaveLength(67);
      expect(body.data.permissions).toEqual(['read', 'write']);
      expect(body.data).toHaveProperty('id');
      expect(body.data).toHaveProperty('prefix');
      expect(body.data).toHaveProperty('created_at');
    });

    it('should create API key with expiration date', async () => {
      const expiresAt = new Date(Date.now() + 86400000).toISOString(); // 1 day

      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/auth/api-keys',
        headers: {
          authorization: `Bearer ${accessToken}`,
        },
        payload: {
          name: 'Expiring API Key',
          expires_at: expiresAt,
        },
      });

      expect(response.statusCode).toBe(201);
      const body = JSON.parse(response.body);
      expect(body.data.expires_at).toBe(expiresAt);
    });

    it('should return 401 without authentication', async () => {
      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/auth/api-keys',
        payload: {
          name: 'Test API Key',
        },
      });

      expect(response.statusCode).toBe(401);
    });

    it('should return 401 with invalid token', async () => {
      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/auth/api-keys',
        headers: {
          authorization: 'Bearer invalid-token',
        },
        payload: {
          name: 'Test API Key',
        },
      });

      expect(response.statusCode).toBe(401);
    });

    it('should return 400 for invalid request body', async () => {
      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/auth/api-keys',
        headers: {
          authorization: `Bearer ${accessToken}`,
        },
        payload: {
          // name is required but missing
          permissions: ['read'],
        },
      });

      expect(response.statusCode).toBe(400);
    });
  });

  describe('API Key Authentication', () => {
    let testUser: any;
    let apiKey: string;

    beforeEach(async () => {
      testUser = await authService.createUser({
        email: 'test@example.com',
        password: 'SecurePassword123!',
        role: 'user',
      });

      const apiKeyResult = await authService.createAPIKey({
        userId: testUser.id,
        name: 'Test API Key',
        scopes: ['read', 'write'],
      });

      apiKey = apiKeyResult.key;
    });

    it('should authenticate with valid API key', async () => {
      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/auth/api-keys',
        headers: {
          'x-api-key': apiKey,
        },
        payload: {
          name: 'Another API Key',
        },
      });

      expect(response.statusCode).toBe(201);
    });

    it('should return 401 with invalid API key format', async () => {
      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/auth/api-keys',
        headers: {
          'x-api-key': 'invalid-api-key',
        },
        payload: {
          name: 'Test API Key',
        },
      });

      expect(response.statusCode).toBe(401);
    });

    it('should return 401 with non-existent API key', async () => {
      const fakeApiKey = 'rag_' + 'a'.repeat(64);
      
      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/auth/api-keys',
        headers: {
          'x-api-key': fakeApiKey,
        },
        payload: {
          name: 'Test API Key',
        },
      });

      expect(response.statusCode).toBe(401);
    });

    it('should return 401 with inactive API key', async () => {
      // Deactivate the API key
      await global.testEnv.prisma.$executeRaw`
        UPDATE api_keys SET is_active = false WHERE user_id = ${testUser.id}::uuid
      `;

      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/auth/api-keys',
        headers: {
          'x-api-key': apiKey,
        },
        payload: {
          name: 'Test API Key',
        },
      });

      expect(response.statusCode).toBe(401);
    });

    it('should track API key usage', async () => {
      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/auth/api-keys',
        headers: {
          'x-api-key': apiKey,
        },
        payload: {
          name: 'Another API Key',
        },
      });

      expect(response.statusCode).toBe(201);

      // Check that usage was tracked
      const keyData = await global.testEnv.prisma.$queryRaw<Array<{
        usage_count: number;
        last_used: Date;
      }>>`
        SELECT usage_count, last_used FROM api_keys WHERE user_id = ${testUser.id}::uuid
      `;

      expect(keyData[0].usage_count).toBeGreaterThan(0);
      expect(keyData[0].last_used).toBeTruthy();
    });
  });
});