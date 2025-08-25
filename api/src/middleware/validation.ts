import { FastifyInstance, FastifyPluginCallback } from 'fastify';
import fp from 'fastify-plugin';
import { ValidationError } from '@/utils/errors.js';
import { validators, sanitizers } from '@/utils/validation.js';
import { AuthenticatedRequest } from '@/types/api.js';

/**
 * Validation middleware
 * Provides request validation utilities and common validation rules
 */
export const validationMiddleware: FastifyPluginCallback = fp(async (fastify: FastifyInstance) => {
  
  // Add validation utilities to request object
  fastify.decorateRequest('validate', null);
  fastify.decorateRequest('sanitize', null);

  // Pre-validation hook
  fastify.addHook('onRequest', async (request: AuthenticatedRequest, reply) => {
    // Add validation helpers to request
    request.validate = validators;
    request.sanitize = sanitizers;
  });

  // Schema validation hook
  fastify.addHook('preValidation', async (request: AuthenticatedRequest, reply) => {
    // Additional custom validations can be added here
    
    // Validate content-type for POST/PUT/PATCH requests
    if (['POST', 'PUT', 'PATCH'].includes(request.method)) {
      const contentType = request.headers['content-type'];
      
      if (!contentType) {
        throw new ValidationError('Content-Type header is required for this request');
      }

      // Validate JSON content type for non-multipart requests
      if (!contentType.includes('multipart/form-data') && 
          !contentType.includes('application/json') &&
          !contentType.includes('text/plain')) {
        throw new ValidationError('Unsupported Content-Type. Expected application/json or multipart/form-data');
      }
    }

    // Validate file upload requests
    if (request.isMultipart()) {
      const contentLength = request.headers['content-length'];
      
      if (!contentLength) {
        throw new ValidationError('Content-Length header is required for file uploads');
      }

      const size = parseInt(contentLength, 10);
      if (isNaN(size) || size <= 0) {
        throw new ValidationError('Invalid Content-Length header');
      }

      // Additional file upload validations are handled in route handlers
    }

    // Validate query parameters
    if (request.query && typeof request.query === 'object') {
      const query = request.query as Record<string, any>;
      
      // Validate pagination parameters if present
      if (query.page !== undefined || query.limit !== undefined) {
        const page = query.page ? parseInt(query.page, 10) : 1;
        const limit = query.limit ? parseInt(query.limit, 10) : 20;
        
        const paginationValidation = validators.isValidPagination(page, limit);
        if (!paginationValidation.valid) {
          throw new ValidationError('Invalid pagination parameters', {
            issues: paginationValidation.issues,
          });
        }
      }

      // Validate UUID parameters
      Object.keys(query).forEach(key => {
        if (key.endsWith('_id') || key.endsWith('Id')) {
          const value = query[key];
          if (typeof value === 'string' && value.length > 0 && !validators.isUUID(value)) {
            throw new ValidationError(`Invalid UUID format for parameter: ${key}`, {
              parameter: key,
              value: value,
            });
          }
        }
      });

      // Sanitize string query parameters
      Object.keys(query).forEach(key => {
        const value = query[key];
        if (typeof value === 'string') {
          // Basic sanitization
          query[key] = sanitizers.cleanQueryParam(value);
        }
      });
    }

    // Validate route parameters
    if (request.params && typeof request.params === 'object') {
      const params = request.params as Record<string, any>;
      
      // Validate UUID route parameters
      Object.keys(params).forEach(key => {
        if (key.endsWith('Id') || key === 'id') {
          const value = params[key];
          if (typeof value === 'string' && !validators.isUUID(value)) {
            throw new ValidationError(`Invalid UUID format for route parameter: ${key}`, {
              parameter: key,
              value: value,
            });
          }
        }
      });

      // Validate file paths in parameters
      Object.keys(params).forEach(key => {
        if (key.includes('path') || key.includes('file')) {
          const value = params[key];
          if (typeof value === 'string' && !validators.isValidFilePath(value)) {
            throw new ValidationError(`Invalid file path format for parameter: ${key}`, {
              parameter: key,
              value: value,
            });
          }
        }
      });
    }
  });

  // Post-validation sanitization
  fastify.addHook('preHandler', async (request: AuthenticatedRequest, reply) => {
    // Sanitize request body if it's JSON
    if (request.body && typeof request.body === 'object' && !request.isMultipart()) {
      sanitizeObject(request.body as Record<string, any>);
    }
  });

}, {
  name: 'validation-middleware',
});

/**
 * Recursively sanitize object properties
 */
function sanitizeObject(obj: Record<string, any>): void {
  Object.keys(obj).forEach(key => {
    const value = obj[key];
    
    if (typeof value === 'string') {
      // Sanitize string values
      obj[key] = sanitizers.normalizeWhitespace(sanitizers.stripHTML(value));
    } else if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
      // Recursively sanitize nested objects
      sanitizeObject(value);
    } else if (Array.isArray(value)) {
      // Sanitize array elements
      value.forEach((item, index) => {
        if (typeof item === 'string') {
          value[index] = sanitizers.normalizeWhitespace(sanitizers.stripHTML(item));
        } else if (typeof item === 'object' && item !== null) {
          sanitizeObject(item);
        }
      });
    }
  });
}