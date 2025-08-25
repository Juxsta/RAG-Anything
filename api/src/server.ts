#!/usr/bin/env node

/**
 * RAG-Anything API Server
 * 
 * Fastify-based REST API server that exposes RAG-Anything's multimodal
 * document processing and retrieval capabilities to non-Python clients.
 */

import { fileURLToPath } from 'url';
import path from 'path';
import process from 'process';

import { config, validateConfig, isDevelopment, isProduction } from '@/config/index.js';
import { logger, logError } from '@/utils/logger.js';
import { setupGlobalErrorHandlers } from '@/utils/errors.js';
import { buildApp } from './app.js';

// Get current directory
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Setup global error handlers
setupGlobalErrorHandlers();

// Validate configuration
const configValidation = validateConfig();
if (!configValidation.valid) {
  logger.error('Configuration validation failed', {
    errors: configValidation.errors,
  });
  process.exit(1);
}

// Server instance
let server: Awaited<ReturnType<typeof buildApp>> | null = null;

/**
 * Start the server
 */
async function startServer(): Promise<void> {
  try {
    logger.info('Starting RAG-Anything API Server', {
      version: process.env.npm_package_version || '1.0.0',
      environment: config.NODE_ENV,
      port: config.PORT,
      host: config.HOST,
    });

    // Build and configure the Fastify app
    server = await buildApp({
      logger: isDevelopment ? {
        level: 'debug',
        prettyPrint: true,
      } : {
        level: 'info',
      },
      trustProxy: isProduction,
      disableRequestLogging: false,
      bodyLimit: config.UPLOAD_MAX_FILE_SIZE,
      keepAliveTimeout: 30000,
      maxParamLength: 1000,
    });

    // Start listening
    await server.listen({
      port: config.PORT,
      host: config.HOST,
    });

    logger.info('Server started successfully', {
      port: config.PORT,
      host: config.HOST,
      environment: config.NODE_ENV,
      pid: process.pid,
    });

    // Register ready state
    process.send?.('ready');

  } catch (error) {
    logError(logger, error as Error, 'Failed to start server');
    process.exit(1);
  }
}

/**
 * Graceful shutdown handler
 */
async function gracefulShutdown(signal: string): Promise<void> {
  logger.info(`Received ${signal}, starting graceful shutdown`);

  try {
    if (server) {
      // Stop accepting new connections
      await server.close();
      logger.info('Server connections closed');
    }

    // Additional cleanup can be added here
    logger.info('Graceful shutdown completed');
    process.exit(0);

  } catch (error) {
    logError(logger, error as Error, 'Error during graceful shutdown');
    process.exit(1);
  }
}

/**
 * Register shutdown handlers
 */
function registerShutdownHandlers(): void {
  // Handle process termination signals
  process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
  process.on('SIGINT', () => gracefulShutdown('SIGINT'));
  
  // Handle PM2 graceful shutdown
  process.on('message', (message) => {
    if (message === 'shutdown') {
      gracefulShutdown('PM2 shutdown');
    }
  });
}

/**
 * Main function
 */
async function main(): Promise<void> {
  // Register signal handlers for graceful shutdown
  registerShutdownHandlers();

  // Start the server
  await startServer();
}

// Start the application
if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch((error) => {
    logError(logger, error as Error, 'Failed to start application');
    process.exit(1);
  });
}