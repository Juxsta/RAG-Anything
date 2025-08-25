import { FastifyReply } from 'fastify';
import { SuccessResponse, ErrorResponse, ResponseMeta } from '@/types/common.js';
import { ApiErrorCode, ErrorStatusCodes } from '@/types/api.js';
import { formatErrorResponse } from './errors.js';

// Create success response
export function createSuccessResponse<T>(
  data: T,
  requestId: string,
  processingTime?: number
): SuccessResponse<T> {
  const meta: ResponseMeta = {
    request_id: requestId,
    timestamp: new Date().toISOString(),
    ...(processingTime !== undefined && { processing_time_ms: processingTime }),
  };

  return {
    success: true,
    data,
    meta,
  };
}

// Create error response
export function createErrorResponse(
  code: ApiErrorCode,
  message: string,
  requestId: string,
  details?: any
): ErrorResponse {
  return {
    success: false,
    error: {
      code,
      message,
      details,
      request_id: requestId,
      timestamp: new Date().toISOString(),
      documentation_url: `https://docs.rag-anything.com/api/errors#${code.toLowerCase().replace(/_/g, '-')}`,
    },
  };
}

// Send success response
export function sendSuccess<T>(
  reply: FastifyReply,
  data: T,
  requestId: string,
  processingTime?: number,
  statusCode = 200
): FastifyReply {
  const response = createSuccessResponse(data, requestId, processingTime);
  return reply.status(statusCode).send(response);
}

// Send error response
export function sendError(
  reply: FastifyReply,
  code: ApiErrorCode,
  message: string,
  requestId: string,
  details?: any,
  statusCode?: number
): FastifyReply {
  const response = createErrorResponse(code, message, requestId, details);
  const status = statusCode ?? ErrorStatusCodes[code] ?? 500;
  return reply.status(status).send(response);
}

// Send validation error
export function sendValidationError(
  reply: FastifyReply,
  message: string,
  requestId: string,
  validationErrors?: any[]
): FastifyReply {
  return sendError(
    reply,
    ApiErrorCode.VALIDATION_ERROR,
    message,
    requestId,
    { validation_errors: validationErrors },
    422
  );
}

// Send not found error
export function sendNotFound(
  reply: FastifyReply,
  resource: string,
  requestId: string,
  identifier?: string
): FastifyReply {
  const message = identifier
    ? `${resource} '${identifier}' not found`
    : `${resource} not found`;
  
  return sendError(
    reply,
    ApiErrorCode.NOT_FOUND,
    message,
    requestId,
    { resource, identifier },
    404
  );
}

// Send authentication error
export function sendAuthError(
  reply: FastifyReply,
  message: string,
  requestId: string,
  code: ApiErrorCode = ApiErrorCode.AUTH_INVALID
): FastifyReply {
  return sendError(reply, code, message, requestId, undefined, 401);
}

// Send authorization error
export function sendAuthorizationError(
  reply: FastifyReply,
  requestId: string,
  message = 'Insufficient permissions'
): FastifyReply {
  return sendError(
    reply,
    ApiErrorCode.PERMISSION_DENIED,
    message,
    requestId,
    undefined,
    403
  );
}

// Send rate limit error
export function sendRateLimitError(
  reply: FastifyReply,
  requestId: string,
  limit: number,
  windowMs: number,
  resetTime: Date
): FastifyReply {
  const retryAfter = Math.ceil((resetTime.getTime() - Date.now()) / 1000);
  
  reply.header('Retry-After', retryAfter.toString());
  reply.header('X-RateLimit-Limit', limit.toString());
  reply.header('X-RateLimit-Remaining', '0');
  reply.header('X-RateLimit-Reset', resetTime.toISOString());
  
  return sendError(
    reply,
    ApiErrorCode.RATE_LIMIT_EXCEEDED,
    'Rate limit exceeded',
    requestId,
    {
      limit,
      window_ms: windowMs,
      retry_after: retryAfter,
    },
    429
  );
}

// Send processing error
export function sendProcessingError(
  reply: FastifyReply,
  message: string,
  requestId: string,
  details?: any
): FastifyReply {
  return sendError(
    reply,
    ApiErrorCode.PROCESSING_FAILED,
    message,
    requestId,
    details,
    422
  );
}

// Send internal server error
export function sendInternalError(
  reply: FastifyReply,
  requestId: string,
  error?: Error,
  includeStack = false
): FastifyReply {
  const response = formatErrorResponse(
    error ?? new Error('Internal server error'),
    requestId,
    includeStack
  );
  
  return reply.status(500).send(response);
}

// Send service unavailable error
export function sendServiceUnavailable(
  reply: FastifyReply,
  requestId: string,
  reason?: string,
  estimatedRecovery?: Date
): FastifyReply {
  return sendError(
    reply,
    ApiErrorCode.SERVICE_UNAVAILABLE,
    'Service temporarily unavailable',
    requestId,
    {
      reason,
      ...(estimatedRecovery && { estimated_recovery: estimatedRecovery.toISOString() }),
    },
    503
  );
}

// Pagination response helper
export function createPaginatedResponse<T>(
  items: T[],
  totalItems: number,
  page: number,
  limit: number,
  requestId: string
) {
  const totalPages = Math.ceil(totalItems / limit);
  
  return createSuccessResponse(
    {
      items,
      pagination: {
        current_page: page,
        per_page: limit,
        total_pages: totalPages,
        total_items: totalItems,
        has_next: page < totalPages,
        has_prev: page > 1,
      },
    },
    requestId
  );
}

// Streaming response helpers
export function sendStreamingResponse(
  reply: FastifyReply,
  contentType: string,
  filename?: string
) {
  reply.header('Content-Type', contentType);
  reply.header('Transfer-Encoding', 'chunked');
  
  if (filename) {
    reply.header('Content-Disposition', `attachment; filename="${filename}"`);
  }
  
  return reply;
}

// Server-Sent Events helper
export function sendSSEResponse(reply: FastifyReply) {
  reply.header('Content-Type', 'text/event-stream');
  reply.header('Cache-Control', 'no-cache');
  reply.header('Connection', 'keep-alive');
  reply.header('Access-Control-Allow-Origin', '*');
  reply.header('Access-Control-Allow-Headers', 'Cache-Control');
  
  return reply;
}

// File download response
export function sendFileResponse(
  reply: FastifyReply,
  filePath: string,
  filename?: string,
  contentType?: string
) {
  if (contentType) {
    reply.header('Content-Type', contentType);
  }
  
  if (filename) {
    reply.header('Content-Disposition', `attachment; filename="${filename}"`);
  }
  
  return reply.sendFile(filePath);
}

// CORS headers helper
export function setCORSHeaders(reply: FastifyReply, allowedOrigins: string[] = ['*']) {
  reply.header('Access-Control-Allow-Origin', allowedOrigins.join(', '));
  reply.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS, PATCH');
  reply.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept, Authorization, X-API-Key');
  reply.header('Access-Control-Allow-Credentials', 'true');
  reply.header('Access-Control-Max-Age', '86400'); // 24 hours
  
  return reply;
}

// Cache control headers
export function setCacheHeaders(
  reply: FastifyReply,
  maxAge: number = 3600, // 1 hour default
  options: {
    private?: boolean;
    noCache?: boolean;
    noStore?: boolean;
    mustRevalidate?: boolean;
    immutable?: boolean;
  } = {}
) {
  const cacheDirectives: string[] = [];
  
  if (options.noStore) {
    cacheDirectives.push('no-store');
  } else if (options.noCache) {
    cacheDirectives.push('no-cache');
  } else {
    cacheDirectives.push(options.private ? 'private' : 'public');
    cacheDirectives.push(`max-age=${maxAge}`);
  }
  
  if (options.mustRevalidate) {
    cacheDirectives.push('must-revalidate');
  }
  
  if (options.immutable) {
    cacheDirectives.push('immutable');
  }
  
  reply.header('Cache-Control', cacheDirectives.join(', '));
  
  if (!options.noCache && !options.noStore) {
    const expires = new Date(Date.now() + maxAge * 1000);
    reply.header('Expires', expires.toUTCString());
  }
  
  return reply;
}

// Security headers
export function setSecurityHeaders(reply: FastifyReply) {
  reply.header('X-Content-Type-Options', 'nosniff');
  reply.header('X-Frame-Options', 'DENY');
  reply.header('X-XSS-Protection', '1; mode=block');
  reply.header('Referrer-Policy', 'strict-origin-when-cross-origin');
  reply.header('Permissions-Policy', 'camera=(), microphone=(), geolocation=()');
  
  return reply;
}

// Rate limit headers
export function setRateLimitHeaders(
  reply: FastifyReply,
  limit: number,
  remaining: number,
  resetTime: Date
) {
  reply.header('X-RateLimit-Limit', limit.toString());
  reply.header('X-RateLimit-Remaining', remaining.toString());
  reply.header('X-RateLimit-Reset', resetTime.toISOString());
  
  return reply;
}

// Response timing header
export function setTimingHeader(reply: FastifyReply, startTime: number) {
  const duration = Date.now() - startTime;
  reply.header('X-Response-Time', `${duration}ms`);
  
  return reply;
}