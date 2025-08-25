import { Type, Static } from '@sinclair/typebox';
import { EnvironmentSchema } from './common.js';

// System configuration schema
export const SystemConfigSchema = Type.Object({
  directory: Type.Object({
    working_dir: Type.String(),
    parser_output_dir: Type.String(),
  }),
  parsing: Type.Object({
    parser: Type.Union([Type.Literal('mineru'), Type.Literal('docling')]),
    parse_method: Type.Union([Type.Literal('auto'), Type.Literal('ocr'), Type.Literal('txt')]),
    display_content_stats: Type.Boolean(),
  }),
  multimodal_processing: Type.Object({
    enable_image_processing: Type.Boolean(),
    enable_table_processing: Type.Boolean(),
    enable_equation_processing: Type.Boolean(),
  }),
  context_extraction: Type.Object({
    context_window: Type.Number(),
    context_mode: Type.Union([Type.Literal('page'), Type.Literal('chunk')]),
    max_context_tokens: Type.Number(),
  }),
  batch_processing: Type.Object({
    max_concurrent_files: Type.Number(),
    supported_file_extensions: Type.Array(Type.String()),
    recursive_folder_processing: Type.Boolean(),
  }),
});

export type SystemConfig = Static<typeof SystemConfigSchema>;

// Configuration update request schema
export const ConfigUpdateRequestSchema = Type.Partial(SystemConfigSchema);

export type ConfigUpdateRequest = Static<typeof ConfigUpdateRequestSchema>;

// Configuration response schema
export const ConfigResponseSchema = Type.Object({
  success: Type.Literal(true),
  data: SystemConfigSchema,
  meta: Type.Object({
    request_id: Type.String(),
    timestamp: Type.String({ format: 'date-time' }),
  }),
});

export type ConfigResponse = Static<typeof ConfigResponseSchema>;

// Configuration update response schema
export const ConfigUpdateResponseSchema = Type.Object({
  success: Type.Literal(true),
  data: Type.Object({
    updated_fields: Type.Array(Type.String()),
    warnings: Type.Array(Type.String()),
    restart_required: Type.Boolean(),
  }),
  meta: Type.Object({
    request_id: Type.String(),
    timestamp: Type.String({ format: 'date-time' }),
  }),
});

export type ConfigUpdateResponse = Static<typeof ConfigUpdateResponseSchema>;

// Environment configuration
export interface AppConfig {
  // Server
  NODE_ENV: string;
  PORT: number;
  HOST: string;
  LOG_LEVEL: string;
  
  // Database
  DATABASE_URL: string;
  DATABASE_MAX_CONNECTIONS: number;
  
  // Redis
  REDIS_URL: string;
  REDIS_PREFIX: string;
  
  // Authentication
  JWT_SECRET: string;
  JWT_ISSUER: string;
  JWT_AUDIENCE: string;
  API_KEY_SALT: string;
  
  // Rate limiting
  RATE_LIMIT_WINDOW_MS: number;
  RATE_LIMIT_MAX_REQUESTS: number;
  
  // File uploads
  UPLOAD_MAX_FILE_SIZE: number;
  UPLOAD_MAX_FILES: number;
  TEMP_DIR: string;
  CLEANUP_INTERVAL_MS: number;
  
  // Python integration
  PYTHON_EXECUTABLE: string;
  PYTHON_WORKER_SCRIPT: string;
  PYTHON_PROCESS_TIMEOUT: number;
  PYTHON_MAX_PROCESSES: number;
  
  // RAG-Anything
  RAG_STORAGE_DIR: string;
  RAG_OUTPUT_DIR: string;
  
  // Monitoring
  PROMETHEUS_METRICS_ENABLED: boolean;
  HEALTH_CHECK_TIMEOUT: number;
  
  // External services
  OPENAI_API_KEY?: string;
  ANTHROPIC_API_KEY?: string;
}