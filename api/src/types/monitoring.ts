import { Type, Static } from '@sinclair/typebox';
import { HealthStatusSchema } from './common.js';

// Health response schema
export const HealthResponseSchema = Type.Object({
  status: HealthStatusSchema,
  timestamp: Type.String({ format: 'date-time' }),
  version: Type.String(),
  uptime_seconds: Type.Number(),
  checks: Type.Record(Type.String(), HealthStatusSchema),
});

export type HealthResponse = Static<typeof HealthResponseSchema>;

// System status schema
export const SystemStatusSchema = Type.Object({
  status: Type.Union([
    Type.Literal('operational'),
    Type.Literal('degraded'),
    Type.Literal('outage'),
  ]),
  version: Type.String(),
  uptime_seconds: Type.Number(),
  node_version: Type.String(),
  python_version: Type.String(),
});

export type SystemStatus = Static<typeof SystemStatusSchema>;

// Performance metrics schema
export const PerformanceMetricsSchema = Type.Object({
  memory_usage_mb: Type.Number(),
  cpu_usage_percent: Type.Number(),
  active_connections: Type.Number(),
  requests_per_minute: Type.Number(),
});

export type PerformanceMetrics = Static<typeof PerformanceMetricsSchema>;

// Processing metrics schema
export const ProcessingMetricsSchema = Type.Object({
  queue_length: Type.Number(),
  active_jobs: Type.Number(),
  completed_jobs_today: Type.Number(),
  failed_jobs_today: Type.Number(),
});

export type ProcessingMetrics = Static<typeof ProcessingMetricsSchema>;

// Storage metrics schema
export const StorageMetricsSchema = Type.Object({
  lightrag_initialized: Type.Boolean(),
  total_documents: Type.Number(),
  total_chunks: Type.Number(),
  storage_size_mb: Type.Number(),
});

export type StorageMetrics = Static<typeof StorageMetricsSchema>;

// Processor info schema
export const ProcessorInfoSchema = Type.Object({
  class: Type.String(),
  supports: Type.Array(Type.String()),
  enabled: Type.Boolean(),
});

export type ProcessorInfo = Static<typeof ProcessorInfoSchema>;

// Model info schema
export const ModelInfoSchema = Type.Object({
  llm_model: Type.String(),
  vision_model: Type.String(),
  embedding_model: Type.String(),
});

export type ModelInfo = Static<typeof ModelInfoSchema>;

// Status response schema
export const StatusResponseSchema = Type.Object({
  success: Type.Literal(true),
  data: Type.Object({
    system: SystemStatusSchema,
    performance: PerformanceMetricsSchema,
    processing: ProcessingMetricsSchema,
    storage: StorageMetricsSchema,
  }),
  meta: Type.Object({
    request_id: Type.String(),
    timestamp: Type.String({ format: 'date-time' }),
  }),
});

export type StatusResponse = Static<typeof StatusResponseSchema>;

// Processor info response schema
export const ProcessorInfoResponseSchema = Type.Object({
  success: Type.Literal(true),
  data: Type.Object({
    status: Type.Union([Type.Literal('initialized'), Type.Literal('not_initialized')]),
    processors: Type.Record(Type.String(), ProcessorInfoSchema),
    models: ModelInfoSchema,
    config: Type.Any(), // SystemConfig but avoiding circular dependency
  }),
  meta: Type.Object({
    request_id: Type.String(),
    timestamp: Type.String({ format: 'date-time' }),
  }),
});

export type ProcessorInfoResponse = Static<typeof ProcessorInfoResponseSchema>;

// Prometheus metrics interface
export interface PrometheusMetrics {
  // HTTP metrics
  http_requests_total: number;
  http_request_duration_seconds: number[];
  
  // Application metrics
  active_connections: number;
  processing_jobs_active: number;
  processing_jobs_queued: number;
  
  // System metrics
  memory_usage_bytes: number;
  cpu_usage_percent: number;
  
  // Business metrics
  documents_processed_total: number;
  queries_executed_total: number;
  
  // Error metrics
  errors_total: number;
  python_process_failures_total: number;
}