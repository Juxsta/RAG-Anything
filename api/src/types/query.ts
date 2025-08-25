import { Type, Static } from '@sinclair/typebox';
import { QueryModeSchema, MultimodalContentSchema } from './common.js';

// Query source schema
export const QuerySourceSchema = Type.Object({
  doc_id: Type.String(),
  chunk_id: Type.String(),
  file_path: Type.String(),
  relevance_score: Type.Number(),
  content_preview: Type.String(),
  type: Type.Union([Type.Literal('text'), Type.Literal('multimodal')]),
  modality: Type.Union([
    Type.Literal('text'),
    Type.Literal('image'),
    Type.Literal('table'),
    Type.Literal('equation'),
  ]),
});

export type QuerySource = Static<typeof QuerySourceSchema>;

// Query metadata schema
export const QueryMetadataSchema = Type.Object({
  mode: Type.String(),
  processing_time_ms: Type.Number(),
  total_chunks_searched: Type.Number(),
  vlm_enhanced: Type.Boolean(),
});

export type QueryMetadata = Static<typeof QueryMetadataSchema>;

// Text query request schema
export const TextQueryRequestSchema = Type.Object({
  query: Type.String({ minLength: 1 }),
  mode: Type.Optional(Type.Union([QueryModeSchema], { default: 'mix' })),
  vlm_enhanced: Type.Optional(Type.Boolean({ default: false })),
  stream: Type.Optional(Type.Boolean({ default: false })),
  top_k: Type.Optional(Type.Number({ minimum: 1, maximum: 100, default: 10 })),
  max_tokens: Type.Optional(Type.Number({ minimum: 1, maximum: 8000, default: 2000 })),
  temperature: Type.Optional(Type.Number({ minimum: 0, maximum: 2, default: 0.7 })),
});

export type TextQueryRequest = Static<typeof TextQueryRequestSchema>;

// Multimodal query request schema
export const MultimodalQueryRequestSchema = Type.Object({
  query: Type.String({ minLength: 1 }),
  multimodal_content: Type.Array(MultimodalContentSchema),
  mode: Type.Optional(Type.Union([QueryModeSchema], { default: 'mix' })),
  stream: Type.Optional(Type.Boolean({ default: false })),
});

export type MultimodalQueryRequest = Static<typeof MultimodalQueryRequestSchema>;

// Query response schema
export const QueryResponseSchema = Type.Object({
  success: Type.Literal(true),
  data: Type.Object({
    query_id: Type.String(),
    result: Type.String(),
    sources: Type.Array(QuerySourceSchema),
    metadata: QueryMetadataSchema,
  }),
  meta: Type.Object({
    request_id: Type.String(),
    timestamp: Type.String({ format: 'date-time' }),
    processing_time_ms: Type.Number(),
  }),
});

export type QueryResponse = Static<typeof QueryResponseSchema>;

// Multimodal processing details schema
export const MultimodalProcessingDetailsSchema = Type.Object({
  text_analysis: Type.Union([
    Type.Literal('completed'),
    Type.Literal('failed'),
    Type.Literal('skipped'),
  ]),
  image_analysis: Type.Union([
    Type.Literal('completed'),
    Type.Literal('failed'),
    Type.Literal('skipped'),
  ]),
  table_analysis: Type.Union([
    Type.Literal('completed'),
    Type.Literal('failed'),
    Type.Literal('skipped'),
  ]),
  equation_analysis: Type.Union([
    Type.Literal('completed'),
    Type.Literal('failed'),
    Type.Literal('skipped'),
  ]),
  total_processing_time_ms: Type.Number(),
});

export type MultimodalProcessingDetails = Static<typeof MultimodalProcessingDetailsSchema>;

// Multimodal query response schema
export const MultimodalQueryResponseSchema = Type.Intersect([
  QueryResponseSchema,
  Type.Object({
    data: Type.Object({
      processing_details: MultimodalProcessingDetailsSchema,
    }),
  }),
]);

export type MultimodalQueryResponse = Static<typeof MultimodalQueryResponseSchema>;

// Stream query chunk schema for real-time responses
export const QueryStreamChunkSchema = Type.Object({
  chunk_id: Type.String(),
  content: Type.String(),
  is_final: Type.Boolean({ default: false }),
  metadata: Type.Optional(Type.Any()),
});

export type QueryStreamChunk = Static<typeof QueryStreamChunkSchema>;