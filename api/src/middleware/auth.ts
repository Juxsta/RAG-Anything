import { FastifyInstance, FastifyPluginCallback } from 'fastify';
import fp from 'fastify-plugin';
import { AuthenticationError, AuthorizationError } from '@/utils/errors.js';
import { authService } from '@/services/auth.js';
import { AuthenticatedRequest } from '@/types/api.js';
import { UserRole } from '@/types/auth.js';

/**
 * Authentication middleware
 * Validates JWT tokens and API keys
 */
export const authenticationMiddleware: FastifyPluginCallback = fp(async (fastify: FastifyInstance) => {
  
  fastify.addHook('onRequest', async (request: AuthenticatedRequest, reply) => {
    const authHeader = request.headers.authorization;
    const apiKeyHeader = request.headers['x-api-key'] as string;

    try {
      if (authHeader?.startsWith('Bearer ')) {
        // JWT token authentication
        const tokenString = authHeader.substring(7);
        const user = await authService.validateJWT(tokenString);
        
        if (!user) {
          throw new AuthenticationError('Invalid or expired token');
        }
        
        request.user = user;
        
      } else if (apiKeyHeader) {
        // API key authentication
        const user = await authService.validateAPIKey(apiKeyHeader);
        
        if (!user) {
          throw new AuthenticationError('Invalid or expired API key');
        }
        
        request.user = user;
        
      } else {
        throw new AuthenticationError('Authentication required');
      }
      
    } catch (error) {
      if (error instanceof AuthenticationError) {
        throw error;
      }
      throw new AuthenticationError('Invalid authentication credentials');
    }
  });

}, {
  name: 'authentication-middleware',
});

/**
 * Authorization middleware factory
 * Creates middleware that checks for specific roles or permissions
 */
export function createAuthorizationMiddleware(requiredRoles: UserRole[] = []) {
  return fp(async (fastify: FastifyInstance) => {
    fastify.addHook('onRequest', async (request: AuthenticatedRequest, reply) => {
      if (!request.user) {
        throw new AuthenticationError('Authentication required');
      }
      
      const hasPermission = await authService.checkPermissions(request.user, requiredRoles);
      if (!hasPermission) {
        throw new AuthorizationError(`Access denied. Required roles: ${requiredRoles.join(', ')}`);
      }
    });
  }, {
    name: 'authorization-middleware',
  });
}