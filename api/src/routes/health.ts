import { FastifyInstance, FastifyPluginCallback } from 'fastify';
import fp from 'fastify-plugin';
import { Type } from '@sinclair/typebox';
import { HealthResponseSchema } from '@/types/monitoring.js';
import { config } from '@/config/index.js';
import { db } from '@/services/database.js';
import { pythonProcessManager } from '@/services/python-process-manager.js';
import { createClient } from 'redis';

/**
 * Health check routes
 * No authentication required for health endpoints
 */
export const healthRoutes: FastifyPluginCallback = fp(async (fastify: FastifyInstance) => {
  
  /**
   * Basic health check
   * GET /health
   */
  fastify.get('/', {
    schema: {
      description: 'Basic health check endpoint for load balancers',
      tags: ['Health'],
      response: {
        200: {
          description: 'Service is healthy',
          ...HealthResponseSchema,
        },
        503: {
          description: 'Service is unhealthy',
          ...HealthResponseSchema,
        },
      },
    },
  }, async (request, reply) => {
    const startTime = Date.now();
    const uptime = Math.floor(process.uptime());
    
    try {
      // Perform basic health checks
      const checks = {
        python_process: pythonProcessManager.initialized ? 'healthy' : 'unhealthy',
        lightrag_storage: await checkFileSystem(),
        parser_availability: await checkPythonWorker(),
      };
      
      const allHealthy = Object.values(checks).every(status => status === 'healthy');
      const overallStatus = allHealthy ? 'healthy' : 'unhealthy';
      
      const healthResponse = {
        status: overallStatus,
        timestamp: new Date().toISOString(),
        version: process.env.npm_package_version || '1.0.0',
        uptime_seconds: uptime,
        checks,
      };
      
      const statusCode = allHealthy ? 200 : 503;
      
      // Set cache headers (short cache for health checks)
      reply.header('Cache-Control', 'no-cache, must-revalidate');
      reply.header('Expires', '0');
      
      return reply.status(statusCode).send(healthResponse);
      
    } catch (error) {
      const healthResponse = {
        status: 'unhealthy',
        timestamp: new Date().toISOString(),
        version: process.env.npm_package_version || '1.0.0',
        uptime_seconds: uptime,
        checks: {
          system: 'unhealthy',
        },
      };
      
      return reply.status(503).send(healthResponse);
    }
  });

  /**
   * Readiness check
   * GET /health/ready
   */
  fastify.get('/ready', {
    schema: {
      description: 'Readiness check including dependencies',
      tags: ['Health'],
      response: {
        200: {
          description: 'Service is ready',
          ...HealthResponseSchema,
        },
        503: {
          description: 'Service is not ready',
          ...HealthResponseSchema,
        },
      },
    },
  }, async (request, reply) => {
    const uptime = Math.floor(process.uptime());
    
    try {
      // Check critical dependencies
      const checks = {
        database: await checkDatabase(),
        redis: await checkRedis(),
        python_worker: await checkPythonWorker(),
        file_system: await checkFileSystem(),
      };
      
      const allReady = Object.values(checks).every(status => status === 'healthy');
      const overallStatus = allReady ? 'healthy' : 'unhealthy';
      
      const readinessResponse = {
        status: overallStatus,
        timestamp: new Date().toISOString(),
        version: process.env.npm_package_version || '1.0.0',
        uptime_seconds: uptime,
        checks,
      };
      
      const statusCode = allReady ? 200 : 503;
      
      return reply.status(statusCode).send(readinessResponse);
      
    } catch (error) {
      return reply.status(503).send({
        status: 'unhealthy',
        timestamp: new Date().toISOString(),
        version: process.env.npm_package_version || '1.0.0',
        uptime_seconds: uptime,
        checks: {
          system: 'unhealthy',
        },
      });
    }
  });

  /**
   * Liveness check
   * GET /health/live
   */
  fastify.get('/live', {
    schema: {
      description: 'Liveness check for container orchestrators',
      tags: ['Health'],
      response: {
        200: {
          description: 'Service is alive',
          type: 'object',
          properties: {
            status: { type: 'string' },
            timestamp: { type: 'string' },
          },
        },
      },
    },
  }, async (request, reply) => {
    // Simple liveness check - just return 200 if the process is running
    return reply.send({
      status: 'alive',
      timestamp: new Date().toISOString(),
    });
  });

}, {
  name: 'health-routes',
});

/**
 * Check database connectivity
 */
async function checkDatabase(): Promise<'healthy' | 'unhealthy'> {
  try {
    const healthCheck = await db.healthCheck();
    return healthCheck.status === 'healthy' ? 'healthy' : 'unhealthy';
  } catch (error) {
    return 'unhealthy';
  }
}

/**
 * Check Redis connectivity
 */
async function checkRedis(): Promise<'healthy' | 'unhealthy'> {
  try {
    const redis = createClient({ url: config.REDIS_URL });
    await redis.connect();
    const pong = await redis.ping();
    await redis.quit();
    return pong === 'PONG' ? 'healthy' : 'unhealthy';
  } catch (error) {
    return 'unhealthy';
  }
}

/**
 * Check Python worker availability
 */
async function checkPythonWorker(): Promise<'healthy' | 'unhealthy'> {
  try {
    if (!pythonProcessManager.initialized) {
      return 'unhealthy';
    }
    
    const response = await pythonProcessManager.healthCheck();
    return response ? 'healthy' : 'unhealthy';
  } catch (error) {
    return 'unhealthy';
  }
}

/**
 * Check file system accessibility
 */
async function checkFileSystem(): Promise<'healthy' | 'unhealthy'> {
  try {
    const fs = await import('fs/promises');
    
    // Check if temp directory is accessible
    await fs.access(config.TEMP_DIR);
    
    // Check if RAG storage directory is accessible
    await fs.access(config.RAG_STORAGE_DIR);
    
    return 'healthy';
  } catch (error) {
    return 'unhealthy';
  }
}