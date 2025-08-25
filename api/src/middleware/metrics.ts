import { FastifyInstance, FastifyPluginCallback } from 'fastify';
import fp from 'fastify-plugin';
import promClient from 'prom-client';
import { AuthenticatedRequest } from '@/types/api.js';

// Prometheus metrics
const httpRequestsTotal = new promClient.Counter({
  name: 'http_requests_total',
  help: 'Total number of HTTP requests',
  labelNames: ['method', 'route', 'status_code', 'user_type'],
});

const httpRequestDuration = new promClient.Histogram({
  name: 'http_request_duration_seconds',
  help: 'Duration of HTTP requests in seconds',
  labelNames: ['method', 'route', 'status_code'],
  buckets: [0.1, 0.3, 0.5, 0.7, 1, 3, 5, 7, 10],
});

const activeConnections = new promClient.Gauge({
  name: 'http_connections_active',
  help: 'Number of active HTTP connections',
});

const processingJobsActive = new promClient.Gauge({
  name: 'processing_jobs_active',
  help: 'Number of active processing jobs',
});

const documentsProcessedTotal = new promClient.Counter({
  name: 'documents_processed_total',
  help: 'Total number of documents processed',
  labelNames: ['status', 'type'],
});

const queriesExecutedTotal = new promClient.Counter({
  name: 'queries_executed_total',
  help: 'Total number of queries executed',
  labelNames: ['type', 'mode'],
});

// Initialize default metrics
promClient.collectDefaultMetrics({
  prefix: 'rag_api_',
  gcDurationBuckets: [0.001, 0.01, 0.1, 1, 2, 5],
});

/**
 * Metrics collection middleware
 */
export const metricsMiddleware: FastifyPluginCallback = fp(async (fastify: FastifyInstance) => {
  
  // Track active connections
  fastify.addHook('onRequest', async (request: AuthenticatedRequest, reply) => {
    activeConnections.inc();
  });

  fastify.addHook('onResponse', async (request: AuthenticatedRequest, reply) => {
    activeConnections.dec();
    
    const duration = request.startTime ? (Date.now() - request.startTime) / 1000 : 0;
    const route = request.routerPath || request.url;
    const userType = request.user?.apiKey ? 'api_key' : 'user';

    // Record HTTP metrics
    httpRequestsTotal.inc({
      method: request.method,
      route,
      status_code: reply.statusCode,
      user_type: userType,
    });

    httpRequestDuration.observe(
      {
        method: request.method,
        route,
        status_code: reply.statusCode,
      },
      duration
    );
  });

  // Metrics endpoint
  fastify.get('/metrics', {
    schema: {
      description: 'Prometheus metrics endpoint',
      tags: ['Monitoring'],
      response: {
        200: {
          description: 'Prometheus metrics in text format',
          type: 'string',
        },
      },
    },
  }, async (request, reply) => {
    reply.header('Content-Type', promClient.register.contentType);
    return promClient.register.metrics();
  });

}, {
  name: 'metrics-middleware',
});

// Export individual metrics for use in other parts of the application
export const metrics = {
  httpRequestsTotal,
  httpRequestDuration,
  activeConnections,
  processingJobsActive,
  documentsProcessedTotal,
  queriesExecutedTotal,
};