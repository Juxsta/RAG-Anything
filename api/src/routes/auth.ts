import { FastifyInstance, FastifyPluginCallback } from 'fastify';
import fp from 'fastify-plugin';
import { Type } from '@sinclair/typebox';
import { LoginRequestSchema, TokensResponseSchema } from '@/types/auth.js';
import { ValidationError, AuthenticationError } from '@/utils/errors.js';
import { authService } from '@/services/auth.js';
import { AuthenticatedRequest } from '@/types/api.js';

/**
 * Authentication routes
 */
export const authRoutes: FastifyPluginCallback = fp(async (fastify: FastifyInstance) => {
  
  /**
   * User login
   * POST /api/v1/auth/login
   */
  fastify.post('/login', {
    schema: {
      description: 'User authentication with email and password',
      tags: ['Authentication'],
      body: LoginRequestSchema,
      response: {
        200: {
          description: 'Login successful',
          type: 'object',
          properties: {
            success: { type: 'boolean', const: true },
            data: TokensResponseSchema,
            meta: {
              type: 'object',
              properties: {
                request_id: { type: 'string' },
                timestamp: { type: 'string' },
              },
            },
          },
        },
        401: {
          description: 'Invalid credentials',
          type: 'object',
          properties: {
            success: { type: 'boolean', const: false },
            error: {
              type: 'object',
              properties: {
                code: { type: 'string' },
                message: { type: 'string' },
              },
            },
          },
        },
      },
    },
  }, async (request, reply) => {
    const { email, password } = request.body;
    
    try {
      // Authenticate user with database
      const loginResult = await authService.login({ email, password });

      return reply.sendSuccess({
        user: loginResult.user,
        access_token: loginResult.accessToken,
        refresh_token: loginResult.refreshToken,
        token_type: 'Bearer' as const,
        expires_in: 3600, // 1 hour
      }, 'Login successful');
      
    } catch (error) {
      if (error instanceof AuthenticationError) {
        throw error;
      }
      throw new AuthenticationError('Login failed');
    }
  });

  /**
   * Token refresh
   * POST /api/v1/auth/refresh
   */
  fastify.post('/refresh', {
    schema: {
      description: 'Refresh access token using refresh token',
      tags: ['Authentication'],
      body: Type.Object({
        refresh_token: Type.String(),
      }),
      response: {
        200: {
          description: 'Token refresh successful',
          type: 'object',
          properties: {
            success: { type: 'boolean', const: true },
            data: TokensResponseSchema,
          },
        },
      },
    },
  }, async (request, reply) => {
    const { refresh_token } = request.body;
    
    try {
      // Use auth service to refresh token
      const refreshResult = await authService.refreshToken(refresh_token);
      
      return reply.sendSuccess({
        access_token: refreshResult.accessToken,
        refresh_token: refreshResult.refreshToken,
        token_type: 'Bearer' as const,
        expires_in: 3600, // 1 hour
      }, 'Token refreshed successfully');
      
    } catch (error) {
      if (error instanceof AuthenticationError) {
        throw error;
      }
      throw new AuthenticationError('Invalid refresh token');
    }
  });

  /**
   * Create API key
   * POST /api/v1/auth/api-keys
   */
  fastify.post('/api-keys', {
    schema: {
      description: 'Create new API key',
      tags: ['Authentication'],
      security: [{ BearerAuth: [] }],
      body: Type.Object({
        name: Type.String({ minLength: 1, maxLength: 100 }),
        permissions: Type.Optional(Type.Array(Type.String())),
        expires_at: Type.Optional(Type.String({ format: 'date-time' })),
      }),
      response: {
        201: {
          description: 'API key created successfully',
          type: 'object',
          properties: {
            success: { type: 'boolean', const: true },
            data: {
              type: 'object',
              properties: {
                id: { type: 'string' },
                name: { type: 'string' },
                key: { type: 'string' },
                permissions: { type: 'array', items: { type: 'string' } },
                created_at: { type: 'string' },
                expires_at: { type: 'string', nullable: true },
              },
            },
          },
        },
      },
    },
  }, async (request: AuthenticatedRequest, reply) => {
    // This route would be protected by authentication middleware
    const { name, permissions = [], expires_at } = request.body;
    
    try {
      if (!request.user) {
        throw new AuthenticationError('Authentication required');
      }

      // Create API key in database
      const apiKeyResult = await authService.createAPIKey({
        userId: request.user.id,
        name,
        scopes: permissions,
        expiresAt: expires_at ? new Date(expires_at) : undefined,
      });
      
      const apiKeyData = {
        id: apiKeyResult.keyId,
        name,
        key: apiKeyResult.key,
        prefix: apiKeyResult.prefix,
        permissions,
        created_at: new Date().toISOString(),
        expires_at: expires_at || null,
      };
      
      return reply.status(201).sendSuccess(apiKeyData, 'API key created successfully');
      
    } catch (error) {
      if (error instanceof ValidationError) {
        throw error;
      }
      throw new ValidationError('Failed to create API key');
    }
  });

}, {
  name: 'auth-routes',
});