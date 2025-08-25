import { Type, Static } from '@sinclair/typebox';

// Common response meta schema
export const ResponseMetaSchema = Type.Object({
  request_id: Type.String(),
  timestamp: Type.String({ format: 'date-time' }),
  processing_time_ms: Type.Optional(Type.Number()),
});

export type ResponseMeta = Static<typeof ResponseMetaSchema>;

// Success response schema
export const SuccessResponseSchema = Type.Object({
  success: Type.Literal(true),
  data: Type.Any(),
  meta: ResponseMetaSchema,
});

export type SuccessResponse<T = any> = {
  success: true;
  data: T;
  meta: ResponseMeta;
};

// Error details schema
export const ErrorDetailsSchema = Type.Object({
  code: Type.String(),
  message: Type.String(),
  details: Type.Optional(Type.Any()),
  request_id: Type.String(),
  timestamp: Type.String({ format: 'date-time' }),
  documentation_url: Type.Optional(Type.String({ format: 'uri' })),
});

export type ErrorDetails = Static<typeof ErrorDetailsSchema>;

// Error response schema
export const ErrorResponseSchema = Type.Object({
  success: Type.Literal(false),
  error: ErrorDetailsSchema,
});

export type ErrorResponse = {
  success: false;
  error: ErrorDetails;
};

// Pagination schema
export const PaginationSchema = Type.Object({
  page: Type.Number({ minimum: 1, default: 1 }),
  limit: Type.Number({ minimum: 1, maximum: 100, default: 20 }),
  sort: Type.Optional(Type.String({ default: 'created_at' })),
  order: Type.Optional(Type.Union([Type.Literal('asc'), Type.Literal('desc')], { default: 'desc' })),
});

export type PaginationParams = Static<typeof PaginationSchema>;

// Pagination info schema
export const PaginationInfoSchema = Type.Object({
  current_page: Type.Number(),
  per_page: Type.Number(),
  total_pages: Type.Number(),
  total_items: Type.Number(),
});

export type PaginationInfo = Static<typeof PaginationInfoSchema>;

// File info schema
export const FileInfoSchema = Type.Object({
  filename: Type.String(),
  size: Type.Number(),
  type: Type.String(),
  checksum: Type.Optional(Type.String()),
});

export type FileInfo = Static<typeof FileInfoSchema>;

// Status enum
export const ProcessingStatusSchema = Type.Union([
  Type.Literal('queued'),
  Type.Literal('processing'),
  Type.Literal('completed'),
  Type.Literal('failed'),
]);

export type ProcessingStatus = Static<typeof ProcessingStatusSchema>;

// Content type enum
export const ContentTypeSchema = Type.Union([
  Type.Literal('text'),
  Type.Literal('image'),
  Type.Literal('table'),
  Type.Literal('equation'),
]);

export type ContentType = Static<typeof ContentTypeSchema>;

// Multimodal content schemas
export const ImageContentSchema = Type.Object({
  type: Type.Literal('image'),
  img_path: Type.Optional(Type.String()),
  data: Type.Optional(Type.String({ format: 'byte' })),
  format: Type.Optional(Type.Union([
    Type.Literal('jpeg'),
    Type.Literal('jpg'),
    Type.Literal('png'),
    Type.Literal('bmp'),
    Type.Literal('tiff'),
    Type.Literal('gif'),
    Type.Literal('webp'),
  ])),
});

export const TableContentSchema = Type.Object({
  type: Type.Literal('table'),
  table_data: Type.String(),
});

export const EquationContentSchema = Type.Object({
  type: Type.Literal('equation'),
  equation: Type.String(),
});

export const MultimodalContentSchema = Type.Union([
  ImageContentSchema,
  TableContentSchema,
  EquationContentSchema,
]);

export type ImageContent = Static<typeof ImageContentSchema>;
export type TableContent = Static<typeof TableContentSchema>;
export type EquationContent = Static<typeof EquationContentSchema>;
export type MultimodalContent = Static<typeof MultimodalContentSchema>;

// Query mode enum
export const QueryModeSchema = Type.Union([
  Type.Literal('local'),
  Type.Literal('global'),
  Type.Literal('hybrid'),
  Type.Literal('naive'),
  Type.Literal('mix'),
  Type.Literal('bypass'),
]);

export type QueryMode = Static<typeof QueryModeSchema>;

// Environment enum
export const EnvironmentSchema = Type.Union([
  Type.Literal('development'),
  Type.Literal('staging'),
  Type.Literal('production'),
  Type.Literal('test'),
]);

export type Environment = Static<typeof EnvironmentSchema>;

// Health status enum
export const HealthStatusSchema = Type.Union([
  Type.Literal('healthy'),
  Type.Literal('unhealthy'),
  Type.Literal('starting'),
  Type.Literal('unknown'),
]);

export type HealthStatus = Static<typeof HealthStatusSchema>;