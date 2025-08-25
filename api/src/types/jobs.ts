import { Type, Static } from '@sinclair/typebox';
import { ProcessingStatusSchema } from './common.js';

// Job priority enum
export const JobPrioritySchema = Type.Union([
  Type.Literal('low'),
  Type.Literal('normal'),
  Type.Literal('high'),
  Type.Literal('urgent'),
]);

export type JobPriority = Static<typeof JobPrioritySchema>;

// Job type enum
export const JobTypeSchema = Type.Union([
  Type.Literal('document_processing'),
  Type.Literal('batch_processing'),
  Type.Literal('content_list_processing'),
  Type.Literal('query_processing'),
  Type.Literal('multimodal_query'),
  Type.Literal('cleanup'),
]);

export type JobType = Static<typeof JobTypeSchema>;

// Base job data
export interface BaseJobData {
  id: string;
  type: JobType;
  priority: JobPriority;
  userId?: string;
  correlationId?: string;
  createdAt: Date;
}

// Document processing job data
export interface DocumentProcessingJobData extends BaseJobData {
  type: 'document_processing';
  filePath: string;
  fileName: string;
  fileSize: number;
  docId: string;
  options: {
    parseMethod: 'auto' | 'ocr' | 'txt';
    outputDir?: string;
    displayStats: boolean;
    splitByCharacter?: string;
    splitByCharacterOnly: boolean;
  };
}

// Batch processing job data
export interface BatchProcessingJobData extends BaseJobData {
  type: 'batch_processing';
  batchId: string;
  files: Array<{
    filePath: string;
    fileName: string;
    fileSize: number;
    docId: string;
  }>;
  options: {
    parseMethod: 'auto' | 'ocr' | 'txt';
    maxWorkers: number;
    recursive: boolean;
    showProgress: boolean;
  };
}

// Content list processing job data
export interface ContentListProcessingJobData extends BaseJobData {
  type: 'content_list_processing';
  docId: string;
  contentList: any[];
  filePath?: string;
  displayStats: boolean;
}

// Query processing job data
export interface QueryProcessingJobData extends BaseJobData {
  type: 'query_processing' | 'multimodal_query';
  queryId: string;
  query: string;
  mode: string;
  options: {
    vlmEnhanced?: boolean;
    stream?: boolean;
    topK?: number;
    maxTokens?: number;
    temperature?: number;
    multimodalContent?: any[];
  };
}

// Cleanup job data
export interface CleanupJobData extends BaseJobData {
  type: 'cleanup';
  targetType: 'document' | 'temp_files' | 'expired_sessions';
  targetId?: string;
}

// Union type for all job data
export type JobData = 
  | DocumentProcessingJobData
  | BatchProcessingJobData
  | ContentListProcessingJobData
  | QueryProcessingJobData
  | CleanupJobData;

// Job progress update
export interface JobProgressUpdate {
  jobId: string;
  progress: number; // 0-100
  status: 'queued' | 'processing' | 'completed' | 'failed';
  message?: string;
  currentStep?: string;
  estimatedCompletion?: Date;
  result?: any;
  error?: string;
}

// Job result schemas
export const JobResultSchema = Type.Object({
  jobId: Type.String(),
  status: ProcessingStatusSchema,
  result: Type.Optional(Type.Any()),
  error: Type.Optional(Type.String()),
  processingTimeMs: Type.Number(),
  completedAt: Type.String({ format: 'date-time' }),
});

export type JobResult = Static<typeof JobResultSchema>;

// Job queue statistics
export interface QueueStats {
  waiting: number;
  active: number;
  completed: number;
  failed: number;
  delayed: number;
  paused: number;
}

// Job events for WebSocket updates
export type JobEvent = 
  | { type: 'job:queued'; data: { jobId: string; queuePosition: number } }
  | { type: 'job:started'; data: { jobId: string; startedAt: Date } }
  | { type: 'job:progress'; data: JobProgressUpdate }
  | { type: 'job:completed'; data: { jobId: string; result: any } }
  | { type: 'job:failed'; data: { jobId: string; error: string } }
  | { type: 'batch:progress'; data: { batchId: string; completed: number; total: number } };