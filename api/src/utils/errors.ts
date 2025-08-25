import { ApiErrorCode, ErrorStatusCodes } from '@/types/api.js';

// Base API error class
export class ApiError extends Error {
  public readonly code: ApiErrorCode;
  public readonly statusCode: number;
  public readonly details?: any;
  public readonly isOperational: boolean;

  constructor(
    code: ApiErrorCode,
    message: string,
    details?: any,
    statusCode?: number,
    isOperational = true
  ) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.statusCode = statusCode ?? ErrorStatusCodes[code] ?? 500;
    this.details = details;
    this.isOperational = isOperational;

    // Maintains proper stack trace for where our error was thrown
    Error.captureStackTrace(this, this.constructor);
  }

  toJSON() {
    return {
      name: this.name,
      code: this.code,
      message: this.message,
      statusCode: this.statusCode,
      details: this.details,
      stack: this.stack,
    };
  }
}

// Specific error classes
export class ValidationError extends ApiError {
  constructor(message: string, details?: any) {
    super(ApiErrorCode.VALIDATION_ERROR, message, details, 422);
  }
}

export class AuthenticationError extends ApiError {
  constructor(message: string, code: ApiErrorCode = ApiErrorCode.AUTH_INVALID) {
    super(code, message, undefined, 401);
  }
}

export class AuthorizationError extends ApiError {
  constructor(message: string = 'Insufficient permissions') {
    super(ApiErrorCode.PERMISSION_DENIED, message, undefined, 403);
  }
}

export class RateLimitError extends ApiError {
  constructor(limit: number, windowMs: number, resetTime: Date) {
    super(
      ApiErrorCode.RATE_LIMIT_EXCEEDED,
      'Rate limit exceeded',
      {
        limit,
        window_ms: windowMs,
        retry_after: Math.ceil((resetTime.getTime() - Date.now()) / 1000),
      },
      429
    );
  }
}

export class FileUploadError extends ApiError {
  constructor(message: string, code: ApiErrorCode = ApiErrorCode.FILE_UPLOAD_FAILED) {
    super(code, message, undefined, 400);
  }
}

export class ProcessingError extends ApiError {
  constructor(message: string, details?: any) {
    super(ApiErrorCode.PROCESSING_FAILED, message, details, 422);
  }
}

export class PythonProcessError extends ApiError {
  constructor(message: string, details?: any) {
    super(ApiErrorCode.PYTHON_PROCESS_ERROR, message, details, 502);
  }
}

export class NotFoundError extends ApiError {
  constructor(resource: string, identifier?: string) {
    const message = identifier 
      ? `${resource} '${identifier}' not found`
      : `${resource} not found`;
    super(ApiErrorCode.NOT_FOUND, message, { resource, identifier }, 404);
  }
}

export class ConflictError extends ApiError {
  constructor(message: string, details?: any) {
    super(ApiErrorCode.ALREADY_EXISTS, message, details, 409);
  }
}

export class DatabaseError extends ApiError {
  constructor(message: string, originalError?: Error) {
    super(
      ApiErrorCode.DATABASE_ERROR,
      'Database operation failed',
      {
        originalMessage: message,
        originalError: originalError?.message,
      },
      503
    );
  }
}

export class RedisError extends ApiError {
  constructor(message: string, originalError?: Error) {
    super(
      ApiErrorCode.REDIS_ERROR,
      'Cache operation failed',
      {
        originalMessage: message,
        originalError: originalError?.message,
      },
      503
    );
  }
}

export class ConfigurationError extends ApiError {
  constructor(message: string, details?: any) {
    super(ApiErrorCode.CONFIGURATION_ERROR, message, details, 500, false);
  }
}

// Error handling utilities
export function isOperationalError(error: Error): boolean {
  if (error instanceof ApiError) {
    return error.isOperational;
  }
  return false;
}

export function getErrorStatusCode(error: Error): number {
  if (error instanceof ApiError) {
    return error.statusCode;
  }
  return 500;
}

export function getErrorCode(error: Error): string {
  if (error instanceof ApiError) {
    return error.code;
  }
  return ApiErrorCode.INTERNAL_ERROR;
}

// Error response formatter
export function formatErrorResponse(
  error: Error,
  requestId: string,
  includeStack = false
) {
  const isApiError = error instanceof ApiError;
  
  return {
    success: false,
    error: {
      code: isApiError ? error.code : ApiErrorCode.INTERNAL_ERROR,
      message: isApiError ? error.message : 'Internal server error',
      details: isApiError ? error.details : undefined,
      request_id: requestId,
      timestamp: new Date().toISOString(),
      ...(includeStack && { stack: error.stack }),
      documentation_url: getDocumentationUrl(isApiError ? error.code : ApiErrorCode.INTERNAL_ERROR),
    },
  };
}

// Get documentation URL for error code
function getDocumentationUrl(code: ApiErrorCode): string {
  const baseUrl = 'https://docs.rag-anything.com/api/errors';
  return `${baseUrl}#${code.toLowerCase().replace(/_/g, '-')}`;
}

// Error classification
export function classifyError(error: Error): {
  severity: 'low' | 'medium' | 'high' | 'critical';
  category: 'client' | 'server' | 'external' | 'operational';
  shouldNotify: boolean;
} {
  if (error instanceof ApiError) {
    switch (error.code) {
      case ApiErrorCode.VALIDATION_ERROR:
      case ApiErrorCode.BAD_REQUEST:
      case ApiErrorCode.NOT_FOUND:
      case ApiErrorCode.AUTH_INVALID:
      case ApiErrorCode.AUTH_MISSING:
        return { severity: 'low', category: 'client', shouldNotify: false };
      
      case ApiErrorCode.PERMISSION_DENIED:
      case ApiErrorCode.RATE_LIMIT_EXCEEDED:
        return { severity: 'medium', category: 'client', shouldNotify: false };
      
      case ApiErrorCode.PROCESSING_FAILED:
      case ApiErrorCode.FILE_UPLOAD_FAILED:
        return { severity: 'medium', category: 'operational', shouldNotify: false };
      
      case ApiErrorCode.PYTHON_PROCESS_ERROR:
      case ApiErrorCode.DATABASE_ERROR:
      case ApiErrorCode.REDIS_ERROR:
        return { severity: 'high', category: 'server', shouldNotify: true };
      
      case ApiErrorCode.SERVICE_UNAVAILABLE:
      case ApiErrorCode.CONFIGURATION_ERROR:
        return { severity: 'critical', category: 'server', shouldNotify: true };
      
      default:
        return { severity: 'high', category: 'server', shouldNotify: true };
    }
  }
  
  // Unknown errors are treated as critical
  return { severity: 'critical', category: 'server', shouldNotify: true };
}

// Async error wrapper
export function asyncHandler<T extends any[], R>(
  fn: (...args: T) => Promise<R>
): (...args: T) => Promise<R> {
  return async (...args: T): Promise<R> => {
    try {
      return await fn(...args);
    } catch (error) {
      // Re-throw ApiErrors as-is, wrap others
      if (error instanceof ApiError) {
        throw error;
      }
      throw new ApiError(
        ApiErrorCode.INTERNAL_ERROR,
        'An unexpected error occurred',
        { originalError: error instanceof Error ? error.message : String(error) },
        500,
        false
      );
    }
  };
}

// Promise rejection handler
export function handleUnhandledRejection(reason: any, promise: Promise<any>) {
  const error = reason instanceof Error ? reason : new Error(String(reason));
  console.error('Unhandled Promise Rejection:', error);
  
  // Log to monitoring service in production
  if (process.env.NODE_ENV === 'production') {
    // TODO: Send to error tracking service (Sentry, etc.)
  }
}

// Uncaught exception handler
export function handleUncaughtException(error: Error) {
  console.error('Uncaught Exception:', error);
  
  // Log to monitoring service in production
  if (process.env.NODE_ENV === 'production') {
    // TODO: Send to error tracking service (Sentry, etc.)
  }
  
  // Graceful shutdown
  process.exit(1);
}

// Setup global error handlers
export function setupGlobalErrorHandlers() {
  process.on('unhandledRejection', handleUnhandledRejection);
  process.on('uncaughtException', handleUncaughtException);
}