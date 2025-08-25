import Fastify, { FastifyInstance, FastifyServerOptions } from 'fastify';
import { TypeBoxTypeProvider } from '@fastify/type-provider-typebox';

// Import plugins
import fastifyCors from '@fastify/cors';
import fastifyHelmet from '@fastify/helmet';
import fastifyMultipart from '@fastify/multipart';
import fastifyRateLimit from '@fastify/rate-limit';
import fastifySwagger from '@fastify/swagger';
import fastifySwaggerUi from '@fastify/swagger-ui';

// Import configuration and utilities
import { config, derivedConfig } from '@/config/index.js';
import { logger, createChildLogger } from '@/utils/logger.js';
import { ApiError, formatErrorResponse } from '@/utils/errors.js';
import { encrypt } from '@/utils/crypto.js';

// Import middleware
import { authenticationMiddleware } from '@/middleware/auth.js';
import { rateLimitingMiddleware } from '@/middleware/rate-limit.js';
import { requestLoggingMiddleware } from '@/middleware/logging.js';
import { metricsMiddleware } from '@/middleware/metrics.js';
import { validationMiddleware } from '@/middleware/validation.js';

// Import routes
import { healthRoutes } from '@/routes/health.js';
import { authRoutes } from '@/routes/auth.js';
import { documentsRoutes } from '@/routes/documents.js';
import { queryRoutes } from '@/routes/query.js';
import { configRoutes } from '@/routes/config.js';

/**
 * Build and configure the Fastify application
 */
export async function buildApp(opts: FastifyServerOptions = {}): Promise<FastifyInstance> {
  // Create Fastify instance with TypeBox type provider
  const app = Fastify({
    logger: false, // We use Winston for logging
    genReqId: () => encrypt.uuid(),
    ...opts,
  }).withTypeProvider<TypeBoxTypeProvider>();

  // Add custom properties to request/reply
  app.decorateRequest('correlationId', null);
  app.decorateRequest('user', null);
  app.decorateRequest('startTime', null);
  app.decorateReply('sendSuccess', function<T>(data: T, meta?: any) {
    const correlationId = this.request.correlationId || 'unknown';
    const processingTime = this.request.startTime ? Date.now() - this.request.startTime : undefined;
    
    return this.send({
      success: true,
      data,
      meta: {
        request_id: correlationId,
        timestamp: new Date().toISOString(),
        ...(processingTime && { processing_time_ms: processingTime }),
        ...meta,
      },
    });
  });

  app.decorateReply('sendError', function(code: string, message: string, details?: any, statusCode = 500) {
    const correlationId = this.request.correlationId || 'unknown';
    
    const errorResponse = {
      success: false,
      error: {
        code,
        message,
        details,
        request_id: correlationId,
        timestamp: new Date().toISOString(),
        documentation_url: `https://docs.rag-anything.com/api/errors#${code.toLowerCase().replace(/_/g, '-')}`,
      },
    };
    
    return this.status(statusCode).send(errorResponse);
  });

  // Register core plugins
  await registerCorePlugins(app);

  // Register security plugins
  await registerSecurityPlugins(app);

  // Register middleware
  await registerMiddleware(app);

  // Register routes
  await registerRoutes(app);

  // Register error handlers
  registerErrorHandlers(app);

  return app;
}

/**
 * Register core Fastify plugins
 */
async function registerCorePlugins(app: FastifyInstance): Promise<void> {
  // CORS configuration
  await app.register(fastifyCors, {
    origin: derivedConfig.corsOrigins,
    credentials: true,
    methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'PATCH'],
    allowedHeaders: [
      'Origin',
      'X-Requested-With',
      'Content-Type',
      'Accept',
      'Authorization',
      'X-API-Key',
      'X-Correlation-ID',
    ],
  });

  // Multipart support for file uploads
  await app.register(fastifyMultipart, {
    limits: {
      fileSize: config.UPLOAD_MAX_FILE_SIZE,
      files: config.UPLOAD_MAX_FILES,
      fields: 20,
      fieldSize: 1024 * 1024, // 1MB
    },
    attachFieldsToBody: 'keyValues',
    sharedSchemaId: 'MultipartFileType',
  });

  // OpenAPI documentation
  if (config.NODE_ENV !== 'production') {
    await app.register(fastifySwagger, {
      openapi: {
        openapi: '3.0.0',
        info: {
          title: 'RAG-Anything API',
          description: 'REST API for RAG-Anything multimodal document processing and retrieval system',
          version: '1.0.0',
          contact: {
            name: 'RAG-Anything API Support',
            url: 'https://github.com/HKUDS/RAG-Anything',
          },
          license: {
            name: 'MIT',
            url: 'https://opensource.org/licenses/MIT',
          },
        },
        servers: [
          {
            url: 'https://api.rag-anything.com/v1',
            description: 'Production server',
          },
          {
            url: 'http://localhost:3000/api/v1',
            description: 'Development server',
          },
        ],
        components: {
          securitySchemes: {
            ApiKeyAuth: {
              type: 'apiKey',
              in: 'header',
              name: 'X-API-Key',
            },
            BearerAuth: {
              type: 'http',
              scheme: 'bearer',
              bearerFormat: 'JWT',
            },
          },
        },
        security: [{ ApiKeyAuth: [] }, { BearerAuth: [] }],
      },
    });

    await app.register(fastifySwaggerUi, {
      routePrefix: '/docs',
      uiConfig: {
        docExpansion: 'none',
        deepLinking: false,
      },
      uiHooks: {
        onRequest: function (request, reply, next) {
          next();
        },
        preHandler: function (request, reply, next) {
          next();
        },
      },
      staticCSP: true,
      transformStaticCSP: (header) => header,
      transformSpecification: (swaggerObject) => {
        return swaggerObject;
      },
      transformSpecificationClone: true,
    });
  }
}

/**
 * Register security plugins
 */
async function registerSecurityPlugins(app: FastifyInstance): Promise<void> {
  // Security headers
  if (derivedConfig.enableHelmet) {
    await app.register(fastifyHelmet, {
      contentSecurityPolicy: {
        directives: {
          defaultSrc: [\"'self'\"],
          scriptSrc: [\"'self'\", \"'unsafe-inline'\"],
          styleSrc: [\"'self'\", \"'unsafe-inline'\"],
          imgSrc: [\"'self'\", 'data:', 'https:'],
          fontSrc: [\"'self'\", 'https:'],
          connectSrc: [\"'self'\", 'https:'],
          frameAncestors: [\"'none'\"],
          baseUri: [\"'self'\"],
          formAction: [\"'self'\"],
        },
      },
    });
  }

  // Rate limiting
  if (derivedConfig.enableRateLimit) {
    await app.register(fastifyRateLimit, {
      global: false, // We'll handle rate limiting in middleware
      max: config.RATE_LIMIT_MAX_REQUESTS,
      timeWindow: config.RATE_LIMIT_WINDOW_MS,
      errorResponseBuilder: (request, context) => {
        const correlationId = request.correlationId || 'unknown';
        return {
          success: false,
          error: {
            code: 'RATE_LIMIT_EXCEEDED',
            message: 'Rate limit exceeded',
            request_id: correlationId,
            timestamp: new Date().toISOString(),
            details: {
              limit: context.max,
              window_ms: context.timeWindow,
              retry_after: Math.round(context.ttl / 1000),
            },
          },
        };
      },
    });
  }
}

/**
 * Register middleware
 */
async function registerMiddleware(app: FastifyInstance): Promise<void> {
  // Request context middleware (correlation ID, timing)
  app.addHook('onRequest', async (request, reply) => {
    // Set correlation ID
    request.correlationId = request.headers['x-correlation-id'] as string || encrypt.uuid();
    reply.header('x-correlation-id', request.correlationId);
    
    // Set request start time
    request.startTime = Date.now();
    
    // Create request logger
    request.log = createChildLogger(request.correlationId);
  });

  // Request logging middleware
  await app.register(requestLoggingMiddleware);

  // Metrics collection middleware
  if (config.PROMETHEUS_METRICS_ENABLED) {
    await app.register(metricsMiddleware);
  }

  // Validation middleware
  await app.register(validationMiddleware);

  // Response timing
  app.addHook('onSend', async (request, reply, payload) => {
    if (request.startTime) {
      const duration = Date.now() - request.startTime;
      reply.header('x-response-time', `${duration}ms`);
    }
    return payload;
  });
}

/**
 * Register API routes
 */
async function registerRoutes(app: FastifyInstance): Promise<void> {
  // API version prefix
  const apiPrefix = '/api/v1';

  // Health routes (no auth required)
  await app.register(healthRoutes, { prefix: '/health' });

  // Authentication routes
  await app.register(authRoutes, { prefix: `${apiPrefix}/auth` });

  // Protected routes (require authentication)
  await app.register(async function(protectedApp) {
    // Authentication middleware for protected routes
    await protectedApp.register(authenticationMiddleware);
    
    // Rate limiting for protected routes
    if (derivedConfig.enableRateLimit) {
      await protectedApp.register(rateLimitingMiddleware);
    }

    // Documents routes
    await protectedApp.register(documentsRoutes, { prefix: `${apiPrefix}/documents` });
    
    // Query routes
    await protectedApp.register(queryRoutes, { prefix: `${apiPrefix}/query` });
    
    // Configuration routes
    await protectedApp.register(configRoutes, { prefix: `${apiPrefix}/config` });
  });

  // Catch-all 404 handler
  app.setNotFoundHandler(async (request, reply) => {
    const correlationId = request.correlationId || 'unknown';
    return reply.status(404).send({
      success: false,
      error: {
        code: 'NOT_FOUND',
        message: `Route ${request.method} ${request.url} not found`,
        request_id: correlationId,
        timestamp: new Date().toISOString(),
      },
    });
  });
}

/**
 * Register error handlers
 */
function registerErrorHandlers(app: FastifyInstance): void {
  // Global error handler
  app.setErrorHandler(async (error, request, reply) => {
    const correlationId = request.correlationId || 'unknown';
    
    // Log error
    const requestLogger = createChildLogger(correlationId, request.user?.id);
    requestLogger.error('Request error', {
      error: {
        name: error.name,
        message: error.message,
        stack: error.stack,
        statusCode: error.statusCode,
      },
      request: {
        method: request.method,
        url: request.url,
        headers: request.headers,
        ip: request.ip,
      },
    });

    // Handle API errors
    if (error instanceof ApiError) {
      return reply.status(error.statusCode).send({
        success: false,
        error: {
          code: error.code,
          message: error.message,
          details: error.details,
          request_id: correlationId,
          timestamp: new Date().toISOString(),
        },
      });
    }

    // Handle validation errors
    if (error.validation) {
      return reply.status(400).send({
        success: false,
        error: {
          code: 'VALIDATION_ERROR',
          message: 'Request validation failed',
          details: {
            validation_errors: error.validation,
          },
          request_id: correlationId,
          timestamp: new Date().toISOString(),
        },
      });
    }

    // Handle Fastify errors
    if (error.statusCode) {
      return reply.status(error.statusCode).send({
        success: false,
        error: {
          code: 'REQUEST_ERROR',
          message: error.message || 'Request failed',
          request_id: correlationId,
          timestamp: new Date().toISOString(),
        },
      });
    }

    // Handle unknown errors
    const includeStack = config.NODE_ENV === 'development';
    const errorResponse = formatErrorResponse(error, correlationId, includeStack);
    
    return reply.status(500).send(errorResponse);
  });

  // Handle async errors
  app.setDefaultRoute((request, reply) => {
    const correlationId = request.correlationId || 'unknown';
    reply.status(404).send({
      success: false,
      error: {
        code: 'NOT_FOUND',
        message: 'Route not found',
        request_id: correlationId,
        timestamp: new Date().toISOString(),
      },
    });
  });
}