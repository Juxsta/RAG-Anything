import { Static, TSchema } from '@sinclair/typebox';
import { Value } from '@sinclair/typebox/value';
import { ValidationError } from './errors.js';

// Validation result type
export interface ValidationResult<T> {
  success: boolean;
  data?: T;
  errors?: Array<{
    path: string;
    message: string;
    value: any;
  }>;
}

// Validate data against TypeBox schema
export function validateSchema<T extends TSchema>(
  schema: T,
  data: unknown
): ValidationResult<Static<T>> {
  try {
    const errors = [...Value.Errors(schema, data)];
    
    if (errors.length > 0) {
      return {
        success: false,
        errors: errors.map(error => ({
          path: error.path,
          message: error.message,
          value: error.value,
        })),
      };
    }

    // Transform/clean the data
    const validData = Value.Clean(schema, data);
    
    return {
      success: true,
      data: validData as Static<T>,
    };
  } catch (error) {
    return {
      success: false,
      errors: [{
        path: '',
        message: error instanceof Error ? error.message : 'Validation failed',
        value: data,
      }],
    };
  }
}

// Validate and throw on error
export function validateSchemaOrThrow<T extends TSchema>(
  schema: T,
  data: unknown,
  errorMessage = 'Validation failed'
): Static<T> {
  const result = validateSchema(schema, data);
  
  if (!result.success) {
    throw new ValidationError(errorMessage, {
      validation_errors: result.errors,
    });
  }
  
  return result.data!;
}

// Common validation functions
export const validators = {
  // Email validation
  isEmail(email: string): boolean {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  },

  // UUID validation
  isUUID(uuid: string): boolean {
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
    return uuidRegex.test(uuid);
  },

  // URL validation
  isURL(url: string): boolean {
    try {
      new URL(url);
      return true;
    } catch {
      return false;
    }
  },

  // File path validation
  isValidFilePath(path: string): boolean {
    // Prevent directory traversal
    if (path.includes('..') || path.includes('~')) {
      return false;
    }
    // Check for null bytes
    if (path.includes('\0')) {
      return false;
    }
    return true;
  },

  // MIME type validation
  isValidMimeType(mimeType: string, allowedTypes: string[]): boolean {
    return allowedTypes.some(allowed => {
      if (allowed.endsWith('/*')) {
        return mimeType.startsWith(allowed.slice(0, -1));
      }
      return mimeType === allowed;
    });
  },

  // File size validation
  isValidFileSize(size: number, maxSize: number): boolean {
    return size > 0 && size <= maxSize;
  },

  // Password strength validation
  isStrongPassword(password: string): { valid: boolean; issues: string[] } {
    const issues: string[] = [];
    
    if (password.length < 8) {
      issues.push('Password must be at least 8 characters long');
    }
    
    if (!/[A-Z]/.test(password)) {
      issues.push('Password must contain at least one uppercase letter');
    }
    
    if (!/[a-z]/.test(password)) {
      issues.push('Password must contain at least one lowercase letter');
    }
    
    if (!/[0-9]/.test(password)) {
      issues.push('Password must contain at least one number');
    }
    
    if (!/[^A-Za-z0-9]/.test(password)) {
      issues.push('Password must contain at least one special character');
    }
    
    return {
      valid: issues.length === 0,
      issues,
    };
  },

  // API key format validation
  isValidAPIKey(apiKey: string): boolean {
    // Expected format: rag_<64 hex characters>
    const apiKeyRegex = /^rag_[0-9a-f]{64}$/;
    return apiKeyRegex.test(apiKey);
  },

  // JSON validation
  isValidJSON(jsonString: string): boolean {
    try {
      JSON.parse(jsonString);
      return true;
    } catch {
      return false;
    }
  },

  // Pagination parameters validation
  isValidPagination(page: number, limit: number): { valid: boolean; issues: string[] } {
    const issues: string[] = [];
    
    if (!Number.isInteger(page) || page < 1) {
      issues.push('Page must be a positive integer');
    }
    
    if (!Number.isInteger(limit) || limit < 1 || limit > 100) {
      issues.push('Limit must be an integer between 1 and 100');
    }
    
    return {
      valid: issues.length === 0,
      issues,
    };
  },

  // Date range validation
  isValidDateRange(startDate: Date, endDate: Date): boolean {
    return startDate <= endDate;
  },

  // IP address validation
  isValidIP(ip: string): boolean {
    const ipv4Regex = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
    const ipv6Regex = /^(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$/;
    return ipv4Regex.test(ip) || ipv6Regex.test(ip);
  },
};

// Sanitization functions
export const sanitizers = {
  // Remove HTML tags
  stripHTML(input: string): string {
    return input.replace(/<[^>]*>/g, '');
  },

  // Sanitize filename
  sanitizeFilename(filename: string): string {
    // Remove or replace dangerous characters
    return filename
      .replace(/[<>:"/\\|?*]/g, '_')
      .replace(/\0/g, '')
      .replace(/\.\./g, '__')
      .trim();
  },

  // Normalize whitespace
  normalizeWhitespace(input: string): string {
    return input.replace(/\s+/g, ' ').trim();
  },

  // Escape SQL-like patterns for LIKE queries
  escapeLikePattern(pattern: string): string {
    return pattern.replace(/[%_\\]/g, '\\$&');
  },

  // Clean query parameters
  cleanQueryParam(param: string | undefined, defaultValue = ''): string {
    if (!param) return defaultValue;
    return sanitizers.normalizeWhitespace(sanitizers.stripHTML(param));
  },
};

// Request validation helpers
export function validateRequestBody<T extends TSchema>(
  schema: T,
  body: unknown,
  fieldName = 'request body'
): Static<T> {
  return validateSchemaOrThrow(schema, body, `Invalid ${fieldName}`);
}

export function validateQueryParams<T extends TSchema>(
  schema: T,
  query: unknown,
  fieldName = 'query parameters'
): Static<T> {
  return validateSchemaOrThrow(schema, query, `Invalid ${fieldName}`);
}

export function validateRouteParams<T extends TSchema>(
  schema: T,
  params: unknown,
  fieldName = 'route parameters'
): Static<T> {
  return validateSchemaOrThrow(schema, params, `Invalid ${fieldName}`);
}