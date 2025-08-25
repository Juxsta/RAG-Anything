import { Type, Static } from '@sinclair/typebox';
import { FileInfoSchema, ProcessingStatusSchema, ContentTypeSchema } from './common.js';

// Document processing request schemas
export const ProcessDocumentRequestSchema = Type.Object({
  file: Type.Any(), // Multipart file
  parse_method: Type.Optional(Type.Union([
    Type.Literal('auto'),
    Type.Literal('ocr'),
    Type.Literal('txt'),
  ], { default: 'auto' })),
  output_dir: Type.Optional(Type.String()),
  display_stats: Type.Optional(Type.Boolean({ default: true })),
  split_by_character: Type.Optional(Type.String()),
  split_by_character_only: Type.Optional(Type.Boolean({ default: false })),
  doc_id: Type.Optional(Type.String()),
});

export type ProcessDocumentRequest = Static<typeof ProcessDocumentRequestSchema>;

// Batch processing request schema
export const BatchProcessRequestSchema = Type.Object({
  files: Type.Array(Type.Any()), // Array of multipart files
  parse_method: Type.Optional(Type.Union([
    Type.Literal('auto'),
    Type.Literal('ocr'),
    Type.Literal('txt'),
  ], { default: 'auto' })),
  max_workers: Type.Optional(Type.Number({ minimum: 1, maximum: 10, default: 2 })),
  recursive: Type.Optional(Type.Boolean({ default: true })),
  show_progress: Type.Optional(Type.Boolean({ default: true })),
});

export type BatchProcessRequest = Static<typeof BatchProcessRequestSchema>;

// Content item schemas
export const TextContentItemSchema = Type.Object({
  type: Type.Literal('text'),
  text: Type.String(),
  page_idx: Type.Optional(Type.Number({ minimum: 0 })),
});

export const ImageContentItemSchema = Type.Object({
  type: Type.Literal('image'),
  img_path: Type.String(),
  img_caption: Type.Optional(Type.Array(Type.String())),
  img_footnote: Type.Optional(Type.Array(Type.String())),
  page_idx: Type.Optional(Type.Number({ minimum: 0 })),
});

export const TableContentItemSchema = Type.Object({
  type: Type.Literal('table'),
  table_body: Type.String(),
  table_caption: Type.Optional(Type.Array(Type.String())),
  table_footnote: Type.Optional(Type.Array(Type.String())),
  page_idx: Type.Optional(Type.Number({ minimum: 0 })),
});

export const EquationContentItemSchema = Type.Object({
  type: Type.Literal('equation'),
  equation: Type.String(),
  page_idx: Type.Optional(Type.Number({ minimum: 0 })),
});

export const ContentItemSchema = Type.Union([
  TextContentItemSchema,
  ImageContentItemSchema,
  TableContentItemSchema,
  EquationContentItemSchema,
]);

export type TextContentItem = Static<typeof TextContentItemSchema>;
export type ImageContentItem = Static<typeof ImageContentItemSchema>;
export type TableContentItem = Static<typeof TableContentItemSchema>;
export type EquationContentItem = Static<typeof EquationContentItemSchema>;
export type ContentItem = Static<typeof ContentItemSchema>;

// Content list request schema
export const ContentListRequestSchema = Type.Object({
  content_list: Type.Array(ContentItemSchema),
  file_path: Type.Optional(Type.String()),
  doc_id: Type.Optional(Type.String()),
  display_stats: Type.Optional(Type.Boolean({ default: true })),
});

export type ContentListRequest = Static<typeof ContentListRequestSchema>;

// Processing summary schema
export const ProcessingSummarySchema = Type.Object({
  total_blocks: Type.Number(),
  text_blocks: Type.Number(),
  image_blocks: Type.Number(),
  table_blocks: Type.Number(),
  equation_blocks: Type.Number(),
});

export type ProcessingSummary = Static<typeof ProcessingSummarySchema>;

// Document processing response schemas
export const ProcessingResponseSchema = Type.Object({
  success: Type.Literal(true),
  data: Type.Object({
    job_id: Type.String(),
    doc_id: Type.String(),
    status: ProcessingStatusSchema,
    file_info: FileInfoSchema,
    processing_options: Type.Any(),
    estimated_completion: Type.Optional(Type.String({ format: 'date-time' })),
  }),
  meta: Type.Object({
    request_id: Type.String(),
    timestamp: Type.String({ format: 'date-time' }),
  }),
});

export type ProcessingResponse = Static<typeof ProcessingResponseSchema>;

// Batch file info schema
export const BatchFileInfoSchema = Type.Object({
  filename: Type.String(),
  job_id: Type.String(),
  doc_id: Type.String(),
  status: ProcessingStatusSchema,
  error: Type.Optional(Type.String()),
});

export type BatchFileInfo = Static<typeof BatchFileInfoSchema>;

// Batch processing response schema
export const BatchProcessingResponseSchema = Type.Object({
  success: Type.Literal(true),
  data: Type.Object({
    batch_id: Type.String(),
    total_files: Type.Number(),
    accepted_files: Type.Number(),
    rejected_files: Type.Number(),
    files: Type.Array(BatchFileInfoSchema),
    progress_url: Type.String({ format: 'uri' }),
    estimated_completion: Type.Optional(Type.String({ format: 'date-time' })),
  }),
  meta: Type.Object({
    request_id: Type.String(),
    timestamp: Type.String({ format: 'date-time' }),
  }),
});

export type BatchProcessingResponse = Static<typeof BatchProcessingResponseSchema>;

// Content list response schema
export const ContentListResponseSchema = Type.Object({
  success: Type.Literal(true),
  data: Type.Object({
    doc_id: Type.String(),
    processing_summary: ProcessingSummarySchema,
    status: Type.Union([Type.Literal('completed'), Type.Literal('failed')]),
    processing_time_ms: Type.Number(),
  }),
  meta: Type.Object({
    request_id: Type.String(),
    timestamp: Type.String({ format: 'date-time' }),
  }),
});

export type ContentListResponse = Static<typeof ContentListResponseSchema>;

// Document summary schema
export const DocumentSummarySchema = Type.Object({
  doc_id: Type.String(),
  filename: Type.String(),
  status: ProcessingStatusSchema,
  created_at: Type.String({ format: 'date-time' }),
  updated_at: Type.String({ format: 'date-time' }),
  chunks_count: Type.Number(),
  file_size: Type.Number(),
  content_types: Type.Array(ContentTypeSchema),
});

export type DocumentSummary = Static<typeof DocumentSummarySchema>;

// Document details schema
export const DocumentDetailsSchema = Type.Intersect([
  DocumentSummarySchema,
  Type.Object({
    processing_details: Type.Object({
      text_processed: Type.Boolean(),
      multimodal_processed: Type.Boolean(),
      chunks_count: Type.Number(),
      entities_count: Type.Number(),
      relations_count: Type.Number(),
      processing_time_ms: Type.Number(),
    }),
    content_analysis: Type.Object({
      text_blocks: Type.Number(),
      image_blocks: Type.Number(),
      table_blocks: Type.Number(),
      equation_blocks: Type.Number(),
      total_tokens: Type.Number(),
    }),
    file_info: FileInfoSchema,
  }),
]);

export type DocumentDetails = Static<typeof DocumentDetailsSchema>;

// Document list query params
export const DocumentListQuerySchema = Type.Object({
  page: Type.Optional(Type.Number({ minimum: 1, default: 1 })),
  limit: Type.Optional(Type.Number({ minimum: 1, maximum: 100, default: 20 })),
  status: Type.Optional(ProcessingStatusSchema),
  type: Type.Optional(Type.String()),
  search: Type.Optional(Type.String()),
  sort: Type.Optional(Type.Union([
    Type.Literal('created_at'),
    Type.Literal('updated_at'),
    Type.Literal('filename'),
    Type.Literal('size'),
  ], { default: 'created_at' })),
  order: Type.Optional(Type.Union([Type.Literal('asc'), Type.Literal('desc')], { default: 'desc' })),
});

export type DocumentListQuery = Static<typeof DocumentListQuerySchema>;

// Available filters schema
export const AvailableFiltersSchema = Type.Object({
  status: Type.Array(Type.String()),
  type: Type.Array(Type.String()),
  content_types: Type.Array(Type.String()),
});

export type AvailableFilters = Static<typeof AvailableFiltersSchema>;

// Document list response schema
export const DocumentListResponseSchema = Type.Object({
  success: Type.Literal(true),
  data: Type.Object({
    documents: Type.Array(DocumentSummarySchema),
    pagination: Type.Object({
      current_page: Type.Number(),
      per_page: Type.Number(),
      total_pages: Type.Number(),
      total_documents: Type.Number(),
    }),
    filters: AvailableFiltersSchema,
  }),
  meta: Type.Object({
    request_id: Type.String(),
    timestamp: Type.String({ format: 'date-time' }),
  }),
});

export type DocumentListResponse = Static<typeof DocumentListResponseSchema>;

// Document status response schema
export const DocumentStatusResponseSchema = Type.Object({
  success: Type.Literal(true),
  data: Type.Object({
    doc_id: Type.String(),
    status: ProcessingStatusSchema,
    progress: Type.Number({ minimum: 0, maximum: 100 }),
    current_step: Type.Optional(Type.String()),
    estimated_completion: Type.Optional(Type.String({ format: 'date-time' })),
    error: Type.Optional(Type.String()),
  }),
  meta: Type.Object({
    request_id: Type.String(),
    timestamp: Type.String({ format: 'date-time' }),
  }),
});

export type DocumentStatusResponse = Static<typeof DocumentStatusResponseSchema>;

// Cleanup summary schema
export const CleanupSummarySchema = Type.Object({
  chunks_removed: Type.Number(),
  entities_removed: Type.Number(),
  relations_removed: Type.Number(),
  files_removed: Type.Number(),
  storage_freed_mb: Type.Number(),
});

export type CleanupSummary = Static<typeof CleanupSummarySchema>;

// Document delete response schema
export const DocumentDeleteResponseSchema = Type.Object({
  success: Type.Literal(true),
  data: Type.Object({
    doc_id: Type.String(),
    deleted: Type.Boolean(),
    cleanup_summary: CleanupSummarySchema,
    processing_cancelled: Type.Boolean(),
  }),
  meta: Type.Object({
    request_id: Type.String(),
    timestamp: Type.String({ format: 'date-time' }),
  }),
});

export type DocumentDeleteResponse = Static<typeof DocumentDeleteResponseSchema>;