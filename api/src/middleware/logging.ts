import { FastifyInstance, FastifyPluginCallback } from 'fastify';
import fp from 'fastify-plugin';
import { logHttpRequest, createRequestLogger } from '@/utils/logger.js';
import { AuthenticatedRequest } from '@/types/api.js';

/**
 * Request logging middleware
 * Logs HTTP requests with timing, user info, and response details
 */
export const requestLoggingMiddleware: FastifyPluginCallback = fp(async (fastify: FastifyInstance) => {
  // Pre-request logging
  fastify.addHook('onRequest', async (request: AuthenticatedRequest, reply) => {
    // Create request-specific logger
    const requestLogger = createRequestLogger(
      request.correlationId || 'unknown',
      request.method,
      request.url,
      request.headers['user-agent'] as string
    );

    // Attach logger to request
    request.log = requestLogger;

    // Log request start
    requestLogger.info('Request started', {
      method: request.method,
      url: request.url,
      ip: request.ip,
      user_agent: request.headers['user-agent'],
      content_type: request.headers['content-type'],
      content_length: request.headers['content-length'],
      headers: {
        // Log selected headers (exclude sensitive ones)
        'accept': request.headers.accept,
        'accept-encoding': request.headers['accept-encoding'],
        'accept-language': request.headers['accept-language'],
        'cache-control': request.headers['cache-control'],
        'origin': request.headers.origin,
        'referer': request.headers.referer,
        'x-forwarded-for': request.headers['x-forwarded-for'],
        'x-real-ip': request.headers['x-real-ip'],
      },
    });
  });

  // Post-response logging
  fastify.addHook('onResponse', async (request: AuthenticatedRequest, reply) => {
    const duration = request.startTime ? Date.now() - request.startTime : 0;
    const requestLogger = request.log;

    if (requestLogger) {
      logHttpRequest(
        requestLogger,
        request.method,
        request.url,
        reply.statusCode,
        duration,
        request.headers['user-agent'] as string,
        request.ip
      );

      // Additional response logging
      requestLogger.info('Request completed', {
        method: request.method,
        url: request.url,
        status_code: reply.statusCode,
        duration_ms: duration,
        response_size: reply.getHeader('content-length') || 0,
        cache_status: reply.getHeader('x-cache') || 'unknown',
        user_id: request.user?.id,
        api_key_used: request.user?.apiKey || false,
      });
    }
  });

  // Error logging
  fastify.addHook('onError', async (request: AuthenticatedRequest, reply, error) => {
    const duration = request.startTime ? Date.now() - request.startTime : 0;
    const requestLogger = request.log;

    if (requestLogger) {
      requestLogger.error('Request error', {
        method: request.method,
        url: request.url,
        duration_ms: duration,
        error: {
          name: error.name,
          message: error.message,
          code: (error as any).code,
          statusCode: (error as any).statusCode,
          stack: error.stack,
        },
        user_id: request.user?.id,
        api_key_used: request.user?.apiKey || false,
      });
    }
  });

  // Log slow requests
  fastify.addHook('onResponse', async (request: AuthenticatedRequest, reply) => {
    const duration = request.startTime ? Date.now() - request.startTime : 0;
    const slowRequestThreshold = 1000; // 1 second

    if (duration > slowRequestThreshold && request.log) {
      request.log.warn('Slow request detected', {
        method: request.method,
        url: request.url,
        duration_ms: duration,
        threshold_ms: slowRequestThreshold,
        user_id: request.user?.id,
      });
    }
  });
}, {
  name: 'request-logging-middleware',
});