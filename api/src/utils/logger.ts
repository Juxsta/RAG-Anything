import winston from 'winston';
import DailyRotateFile from 'winston-daily-rotate-file';
import { config } from '@/config/index.js';

// Define log levels
const logLevels = {
  error: 0,
  warn: 1,
  info: 2,
  debug: 3,
};

// Custom log format
const logFormat = winston.format.combine(
  winston.format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss.SSS' }),
  winston.format.errors({ stack: true }),
  winston.format.json(),
  winston.format.printf(({ level, message, timestamp, stack, ...meta }) => {
    const logEntry = {
      timestamp,
      level,
      message,
      service: 'rag-anything-api',
      version: process.env.npm_package_version || '1.0.0',
      environment: config.NODE_ENV,
      ...(meta.correlationId && { correlation_id: meta.correlationId }),
      ...(meta.userId && { user_id: meta.userId }),
      ...(meta.requestId && { request_id: meta.requestId }),
      ...(meta.duration && { duration_ms: meta.duration }),
      ...(stack && { stack }),
      ...meta,
    };
    return JSON.stringify(logEntry);
  })
);

// Console format for development
const consoleFormat = winston.format.combine(
  winston.format.colorize(),
  winston.format.timestamp({ format: 'HH:mm:ss.SSS' }),
  winston.format.printf(({ level, message, timestamp, correlationId, ...meta }) => {
    const correlation = correlationId ? `[${correlationId.slice(0, 8)}]` : '';
    const metaStr = Object.keys(meta).length > 0 ? ` ${JSON.stringify(meta)}` : '';
    return `${timestamp} ${level} ${correlation} ${message}${metaStr}`;
  })
);

// Create logger instance
const logger = winston.createLogger({
  levels: logLevels,
  level: config.LOG_LEVEL,
  format: logFormat,
  defaultMeta: {
    service: 'rag-anything-api',
    environment: config.NODE_ENV,
  },
  transports: [],
});

// Console transport (always enabled)
logger.add(
  new winston.transports.Console({
    format: config.NODE_ENV === 'production' ? logFormat : consoleFormat,
    level: config.LOG_LEVEL,
  })
);

// File transports (disabled in test environment)
if (config.NODE_ENV !== 'test') {
  // Error log file
  logger.add(
    new DailyRotateFile({
      filename: 'logs/error-%DATE%.log',
      datePattern: 'YYYY-MM-DD',
      level: 'error',
      maxSize: '20m',
      maxFiles: '14d',
      format: logFormat,
    })
  );

  // Combined log file
  logger.add(
    new DailyRotateFile({
      filename: 'logs/combined-%DATE%.log',
      datePattern: 'YYYY-MM-DD',
      maxSize: '20m',
      maxFiles: '7d',
      format: logFormat,
    })
  );

  // Debug log file (only in development)
  if (config.NODE_ENV === 'development') {
    logger.add(
      new DailyRotateFile({
        filename: 'logs/debug-%DATE%.log',
        datePattern: 'YYYY-MM-DD',
        level: 'debug',
        maxSize: '50m',
        maxFiles: '3d',
        format: logFormat,
      })
    );
  }
}

// Create child logger with correlation ID
export function createChildLogger(correlationId: string, userId?: string) {
  return logger.child({
    correlationId,
    ...(userId && { userId }),
  });
}

// Request logger middleware helper
export function createRequestLogger(requestId: string, method: string, url: string, userAgent?: string) {
  return logger.child({
    requestId,
    method,
    url,
    userAgent,
  });
}

// Performance logger helper
export function logPerformance(
  logger: winston.Logger,
  operation: string,
  duration: number,
  metadata?: Record<string, any>
) {
  logger.info(`${operation} completed`, {
    operation,
    duration_ms: duration,
    ...metadata,
  });
}

// Error logger helper
export function logError(
  logger: winston.Logger,
  error: Error,
  context?: string,
  metadata?: Record<string, any>
) {
  logger.error(`${context ? `${context}: ` : ''}${error.message}`, {
    error: {
      name: error.name,
      message: error.message,
      stack: error.stack,
    },
    context,
    ...metadata,
  });
}

// Database query logger
export function logDatabaseQuery(
  logger: winston.Logger,
  query: string,
  duration: number,
  rowCount?: number
) {
  if (config.LOG_LEVEL === 'debug') {
    logger.debug('Database query executed', {
      query: query.replace(/\s+/g, ' ').trim(),
      duration_ms: duration,
      ...(rowCount !== undefined && { row_count: rowCount }),
    });
  }
}

// HTTP request logger
export function logHttpRequest(
  logger: winston.Logger,
  method: string,
  url: string,
  statusCode: number,
  duration: number,
  userAgent?: string,
  userIp?: string
) {
  logger.info('HTTP request completed', {
    http: {
      method,
      url,
      status_code: statusCode,
      duration_ms: duration,
      user_agent: userAgent,
      user_ip: userIp,
    },
  });
}

// Job processing logger
export function logJobEvent(
  logger: winston.Logger,
  event: 'started' | 'completed' | 'failed' | 'retry',
  jobId: string,
  jobType: string,
  duration?: number,
  error?: Error
) {
  const level = event === 'failed' ? 'error' : 'info';
  logger[level](`Job ${event}`, {
    job: {
      id: jobId,
      type: jobType,
      event,
      ...(duration && { duration_ms: duration }),
      ...(error && { error: error.message }),
    },
  });
}

// Security event logger
export function logSecurityEvent(
  logger: winston.Logger,
  event: 'auth_success' | 'auth_failure' | 'rate_limit' | 'suspicious_activity',
  details: Record<string, any>
) {
  logger.warn(`Security event: ${event}`, {
    security: {
      event,
      ...details,
    },
  });
}

// Health check logger
export function logHealthCheck(
  logger: winston.Logger,
  component: string,
  status: 'healthy' | 'unhealthy',
  duration: number,
  details?: Record<string, any>
) {
  const level = status === 'unhealthy' ? 'error' : 'debug';
  logger[level](`Health check: ${component}`, {
    health: {
      component,
      status,
      duration_ms: duration,
      ...details,
    },
  });
}

// Export the main logger and utilities
export {
  logger,
  logLevels,
};

export default logger;