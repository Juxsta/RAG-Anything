import { FastifyInstance, FastifyPluginCallback } from 'fastify';
import fp from 'fastify-plugin';
import { RateLimitError } from '@/utils/errors.js';
import { AuthenticatedRequest } from '@/types/api.js';
import { config } from '@/config/index.js';

/**
 * Rate limiting middleware
 * Implements sliding window rate limiting using Redis
 */
export const rateLimitingMiddleware: FastifyPluginCallback = fp(async (fastify: FastifyInstance) => {
  
  fastify.addHook('onRequest', async (request: AuthenticatedRequest, reply) => {
    const identifier = getRateLimitIdentifier(request);
    const limit = getRateLimit(request);
    const windowMs = config.RATE_LIMIT_WINDOW_MS;
    
    try {
      // TODO: Implement actual Redis-based rate limiting
      // For now, just add headers without actual limiting
      const remaining = limit - 1; // Simulate remaining requests
      const resetTime = new Date(Date.now() + windowMs);
      
      // Set rate limit headers
      reply.header('X-RateLimit-Limit', limit.toString());
      reply.header('X-RateLimit-Remaining', remaining.toString());
      reply.header('X-RateLimit-Reset', resetTime.toISOString());
      
      // Store rate limit info in request for later use
      request.rateLimitInfo = {
        limit,
        remaining,
        resetTime: resetTime.getTime(),
        windowMs,
      };
      
      // TODO: Check actual rate limit from Redis
      // if (remaining < 0) {
      //   throw new RateLimitError(limit, windowMs, resetTime);
      // }
      
    } catch (error) {
      if (error instanceof RateLimitError) {
        throw error;
      }
      // Log error but don't fail the request
      request.log?.warn('Rate limiting error', { error: error.message });
    }
  });

}, {
  name: 'rate-limiting-middleware',
});

/**
 * Get rate limit identifier for the request
 */
function getRateLimitIdentifier(request: AuthenticatedRequest): string {
  if (request.user?.apiKey) {
    return `api_key:${request.user.id}`;
  } else if (request.user?.id) {
    return `user:${request.user.id}`;
  } else {
    return `ip:${request.ip}`;
  }
}

/**
 * Get rate limit for the request based on user type
 */
function getRateLimit(request: AuthenticatedRequest): number {
  if (request.user?.apiKey) {
    return config.RATE_LIMIT_MAX_REQUESTS; // API keys get full limit
  } else if (request.user?.role === 'admin') {
    return config.RATE_LIMIT_MAX_REQUESTS * 2; // Admins get double limit
  } else {
    return config.RATE_LIMIT_MAX_REQUESTS;
  }
}