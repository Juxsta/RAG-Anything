import dotenv from 'dotenv';
import { z } from 'zod';
import { AppConfig } from '@/types/config.js';

// Load environment variables
dotenv.config();

// Environment validation schema
const envSchema = z.object({
  // Server
  NODE_ENV: z.enum(['development', 'staging', 'production', 'test']).default('development'),
  PORT: z.coerce.number().default(3000),
  HOST: z.string().default('0.0.0.0'),
  LOG_LEVEL: z.enum(['error', 'warn', 'info', 'debug']).default('info'),
  
  // Database
  DATABASE_URL: z.string().min(1),
  DATABASE_MAX_CONNECTIONS: z.coerce.number().default(20),
  
  // Redis
  REDIS_URL: z.string().min(1),
  REDIS_PREFIX: z.string().default('rag-api:'),
  
  // Authentication
  JWT_SECRET: z.string().min(32),
  JWT_ISSUER: z.string().default('rag-anything-api'),
  JWT_AUDIENCE: z.string().default('rag-anything-clients'),
  API_KEY_SALT: z.string().min(16),
  
  // Rate limiting
  RATE_LIMIT_WINDOW_MS: z.coerce.number().default(60 * 60 * 1000), // 1 hour
  RATE_LIMIT_MAX_REQUESTS: z.coerce.number().default(1000),
  
  // File uploads
  UPLOAD_MAX_FILE_SIZE: z.coerce.number().default(100 * 1024 * 1024), // 100MB
  UPLOAD_MAX_FILES: z.coerce.number().default(100),
  TEMP_DIR: z.string().default('./temp'),
  CLEANUP_INTERVAL_MS: z.coerce.number().default(60 * 60 * 1000), // 1 hour
  
  // Python integration
  PYTHON_EXECUTABLE: z.string().default('python3'),
  PYTHON_WORKER_SCRIPT: z.string().default('../scripts/python_worker.py'),
  PYTHON_PROCESS_TIMEOUT: z.coerce.number().default(30 * 60 * 1000), // 30 minutes
  PYTHON_MAX_PROCESSES: z.coerce.number().default(4),
  
  // RAG-Anything
  RAG_STORAGE_DIR: z.string().default('./rag_storage'),
  RAG_OUTPUT_DIR: z.string().default('./output'),
  
  // Monitoring
  PROMETHEUS_METRICS_ENABLED: z.coerce.boolean().default(true),
  HEALTH_CHECK_TIMEOUT: z.coerce.number().default(5000),
  
  // External services (optional)
  OPENAI_API_KEY: z.string().optional(),
  ANTHROPIC_API_KEY: z.string().optional(),
});

// Validate and export configuration
export const config: AppConfig = envSchema.parse(process.env);

// Environment-specific overrides
export const isDevelopment = config.NODE_ENV === 'development';
export const isProduction = config.NODE_ENV === 'production';
export const isTest = config.NODE_ENV === 'test';

// Derived configuration
export const derivedConfig = {
  // Database
  isDatabaseSSL: config.DATABASE_URL.includes('ssl=true'),
  
  // Logging
  enableDebugLogging: config.LOG_LEVEL === 'debug' || isDevelopment,
  
  // CORS
  corsOrigins: isDevelopment 
    ? ['http://localhost:3000', 'http://localhost:3001', 'http://127.0.0.1:3000']
    : process.env.CORS_ORIGINS?.split(',') || ['https://*.rag-anything.com'],
  
  // Security
  enableHelmet: isProduction,
  enableRateLimit: !isTest,
  
  // File paths (absolute)
  tempDirAbsolute: new URL(config.TEMP_DIR, import.meta.url).pathname,
  ragStorageDirAbsolute: new URL(config.RAG_STORAGE_DIR, import.meta.url).pathname,
  ragOutputDirAbsolute: new URL(config.RAG_OUTPUT_DIR, import.meta.url).pathname,
  
  // WebSocket
  websocketPath: '/socket.io',
  websocketMaxConnections: 1000,
  
  // Queue settings
  queueSettings: {
    removeOnComplete: 100,
    removeOnFail: 50,
    attempts: isProduction ? 3 : 1,
    backoff: {
      type: 'exponential' as const,
      delay: 2000,
    },
  },
};

// Configuration validation
export function validateConfig(): { valid: boolean; errors?: string[] } {
  try {
    envSchema.parse(process.env);
    return { valid: true };
  } catch (error) {
    if (error instanceof z.ZodError) {
      return {
        valid: false,
        errors: error.errors.map(err => `${err.path.join('.')}: ${err.message}`),
      };
    }
    return {
      valid: false,
      errors: ['Unknown configuration error'],
    };
  }
}

// Export default config
export default config;