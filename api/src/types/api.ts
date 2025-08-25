import { FastifyRequest, FastifyReply } from 'fastify';
import { UserAuthInfo, RateLimitInfo } from './auth.js';

// Extended Fastify request interface
export interface AuthenticatedRequest extends FastifyRequest {
  user?: UserAuthInfo;
  correlationId?: string;
  startTime?: number;
  rateLimitInfo?: RateLimitInfo;
}

// Extended Fastify reply interface
export interface AuthenticatedReply extends FastifyReply {
  sendSuccess<T>(data: T, meta?: Partial<{ processing_time_ms: number }>): FastifyReply;
  sendError(code: string, message: string, details?: any, statusCode?: number): FastifyReply;
}

// Route handler type
export type RouteHandler<TRequest = any, TResponse = any> = (
  request: AuthenticatedRequest & { body: TRequest },
  reply: AuthenticatedReply
) => Promise<TResponse> | TResponse;

// File upload info
export interface UploadedFile {
  fieldname: string;
  originalname: string;
  encoding: string;
  mimetype: string;
  size: number;
  buffer: Buffer;
  filename: string;
  path?: string;
}

// Multipart file data
export interface MultipartFile {
  data: AsyncIterable<Buffer>;
  file: NodeJS.ReadableStream;
  fields: {
    filename?: { value: string };
    encoding?: { value: string };
    mimetype?: { value: string };
  };
  fieldname: string;
}

// API error codes
export enum ApiErrorCode {
  // Authentication errors
  AUTH_MISSING = 'AUTH_MISSING',
  AUTH_INVALID = 'AUTH_INVALID',
  AUTH_EXPIRED = 'AUTH_EXPIRED',
  PERMISSION_DENIED = 'PERMISSION_DENIED',
  
  // Rate limiting
  RATE_LIMIT_EXCEEDED = 'RATE_LIMIT_EXCEEDED',
  
  // Validation errors
  VALIDATION_ERROR = 'VALIDATION_ERROR',
  BAD_REQUEST = 'BAD_REQUEST',
  
  // File errors
  FILE_TOO_LARGE = 'FILE_TOO_LARGE',
  FILE_TYPE_NOT_SUPPORTED = 'FILE_TYPE_NOT_SUPPORTED',
  FILE_UPLOAD_FAILED = 'FILE_UPLOAD_FAILED',
  
  // Processing errors
  PROCESSING_FAILED = 'PROCESSING_FAILED',
  PROCESSING_TIMEOUT = 'PROCESSING_TIMEOUT',
  PYTHON_PROCESS_ERROR = 'PYTHON_PROCESS_ERROR',
  
  // Resource errors
  NOT_FOUND = 'NOT_FOUND',
  ALREADY_EXISTS = 'ALREADY_EXISTS',
  RESOURCE_LOCKED = 'RESOURCE_LOCKED',
  
  // System errors
  INTERNAL_ERROR = 'INTERNAL_ERROR',
  SERVICE_UNAVAILABLE = 'SERVICE_UNAVAILABLE',
  DATABASE_ERROR = 'DATABASE_ERROR',
  REDIS_ERROR = 'REDIS_ERROR',
  
  // Configuration errors
  CONFIGURATION_ERROR = 'CONFIGURATION_ERROR',
  INVALID_CONFIGURATION = 'INVALID_CONFIGURATION',
}

// HTTP status codes mapping
export const ErrorStatusCodes: Record<ApiErrorCode, number> = {
  [ApiErrorCode.AUTH_MISSING]: 401,
  [ApiErrorCode.AUTH_INVALID]: 401,
  [ApiErrorCode.AUTH_EXPIRED]: 401,
  [ApiErrorCode.PERMISSION_DENIED]: 403,
  [ApiErrorCode.RATE_LIMIT_EXCEEDED]: 429,
  [ApiErrorCode.VALIDATION_ERROR]: 422,
  [ApiErrorCode.BAD_REQUEST]: 400,
  [ApiErrorCode.FILE_TOO_LARGE]: 413,
  [ApiErrorCode.FILE_TYPE_NOT_SUPPORTED]: 422,
  [ApiErrorCode.FILE_UPLOAD_FAILED]: 400,
  [ApiErrorCode.PROCESSING_FAILED]: 422,
  [ApiErrorCode.PROCESSING_TIMEOUT]: 408,
  [ApiErrorCode.PYTHON_PROCESS_ERROR]: 502,
  [ApiErrorCode.NOT_FOUND]: 404,
  [ApiErrorCode.ALREADY_EXISTS]: 409,
  [ApiErrorCode.RESOURCE_LOCKED]: 423,
  [ApiErrorCode.INTERNAL_ERROR]: 500,
  [ApiErrorCode.SERVICE_UNAVAILABLE]: 503,
  [ApiErrorCode.DATABASE_ERROR]: 503,
  [ApiErrorCode.REDIS_ERROR]: 503,
  [ApiErrorCode.CONFIGURATION_ERROR]: 500,
  [ApiErrorCode.INVALID_CONFIGURATION]: 422,
};

// API response utilities
export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: {
    code: string;
    message: string;
    details?: any;
    request_id: string;
    timestamp: string;
    documentation_url?: string;
  };
  meta?: {
    request_id: string;
    timestamp: string;
    processing_time_ms?: number;
  };
}

// Streaming response types
export interface StreamingResponse {
  stream: NodeJS.ReadableStream;
  contentType: string;
  filename?: string;
}

// Server-Sent Events response
export interface SSEResponse {
  write(event: string, data: any, id?: string): void;
  end(): void;
}

// OpenAPI specification extensions
export interface OpenAPIExtension {
  'x-rate-limit'?: {
    limit: number;
    window: string;
  };
  'x-auth-required'?: boolean;
  'x-permissions'?: string[];
  'x-file-upload'?: {
    maxSize: number;
    allowedTypes: string[];
  };
}