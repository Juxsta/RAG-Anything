import { FastifyInstance, FastifyPluginCallback } from 'fastify';
import fp from 'fastify-plugin';
import { Type } from '@sinclair/typebox';
import { TextQueryRequestSchema, QueryResponseSchema } from '@/types/query.js';
import { ProcessingError, ValidationError } from '@/utils/errors.js';
import { encrypt } from '@/utils/crypto.js';
import { jobQueueService } from '@/services/job-queue.js';
import { pythonProcessManager } from '@/services/python-process-manager.js';
import { db } from '@/services/database.js';
import { AuthenticatedRequest } from '@/types/api.js';

/**
 * Query processing routes
 */
export const queryRoutes: FastifyPluginCallback = fp(async (fastify: FastifyInstance) => {
  
  /**
   * Execute text query
   * POST /api/v1/query/text
   */
  fastify.post('/text', {
    schema: {
      description: 'Execute text-only queries with various retrieval modes',
      tags: ['Query'],
      body: TextQueryRequestSchema,
      response: {
        200: {
          description: 'Query executed successfully',
          type: 'object',
          properties: {
            success: { type: 'boolean', const: true },
            data: {
              type: 'object',
              properties: {
                query_id: { type: 'string' },
                result: { type: 'string' },
                sources: {
                  type: 'array',
                  items: {
                    type: 'object',
                    properties: {
                      doc_id: { type: 'string' },
                      chunk_id: { type: 'string' },
                      relevance_score: { type: 'number' },
                      content_preview: { type: 'string' },
                    },
                  },
                },
                metadata: {
                  type: 'object',
                  properties: {
                    mode: { type: 'string' },
                    processing_time_ms: { type: 'number' },
                    total_chunks_searched: { type: 'number' },
                  },
                },
              },
            },
          },
        },
      },
    },
  }, async (request: AuthenticatedRequest, reply) => {
    const { 
      query, 
      mode = 'mix', 
      vlm_enhanced = false,
      stream = false,
      top_k = 10,
      max_tokens = 2000,
      temperature = 0.7 
    } = request.body;
    
    const user = request.user!;
    
    try {
      const queryId = encrypt.uuid();
      
      // For synchronous execution (stream = false), use direct processing
      if (!stream) {
        // Initialize Python process if needed
        if (!pythonProcessManager.initialized) {
          await pythonProcessManager.initialize();
        }

        // Execute query directly through Python process
        const result = await pythonProcessManager.executeQuery(query, mode, vlm_enhanced);

        // Store query in database
        await db.prisma.$executeRaw`
          INSERT INTO queries (
            id, user_id, query_text, query_type, mode, 
            result_text, sources, metadata, processing_time_ms
          )
          VALUES (
            ${queryId}::uuid,
            ${user.id}::uuid,
            ${query},
            'text',
            ${mode},
            ${result.answer || ''},
            ${JSON.stringify(result.sources || [])},
            ${JSON.stringify({
              mode,
              vlm_enhanced,
              top_k,
              max_tokens,
              temperature,
              ...result.metadata
            })},
            ${result.processing_time || 0}
          )
        `;

        const response = {
          query_id: queryId,
          result: result.answer,
          sources: result.sources || [],
          metadata: {
            mode,
            processing_time_ms: result.processing_time,
            total_chunks_searched: result.metadata?.total_chunks || 0,
            vlm_enhanced,
          },
        };

        return reply.sendSuccess(response);
      } else {
        // For streaming, add to job queue
        const jobId = await jobQueueService.addQueryProcessingJob({
          queryId,
          userId: user.id,
          query,
          queryType: 'text',
          mode,
          vlmEnhanced,
          options: { top_k, max_tokens, temperature },
        });

        // Return job ID for tracking
        const response = {
          query_id: queryId,
          job_id: jobId,
          status: 'processing',
          message: 'Query added to processing queue',
          metadata: {
            mode,
            vlm_enhanced,
            stream: true,
          },
        };

        return reply.sendSuccess(response);
      }
      
    } catch (error) {
      throw new ProcessingError('Query execution failed', { error: error.message });
    }
  });

  /**
   * Execute multimodal query
   * POST /api/v1/query/multimodal
   */
  fastify.post('/multimodal', {
    schema: {
      description: 'Execute queries with multimodal content including images and tables',
      tags: ['Query'],
      body: Type.Object({
        query: Type.String({ minLength: 1 }),
        multimodal_content: Type.Array(Type.Object({
          type: Type.Union([
            Type.Literal('image'),
            Type.Literal('table'),
            Type.Literal('equation'),
          ]),
          img_path: Type.Optional(Type.String()),
          data: Type.Optional(Type.String()),
          format: Type.Optional(Type.String()),
          table_data: Type.Optional(Type.String()),
          equation: Type.Optional(Type.String()),
        })),
        mode: Type.Optional(Type.String({ default: 'mix' })),
        stream: Type.Optional(Type.Boolean({ default: false })),
      }),
      response: {
        200: {
          description: 'Multimodal query executed successfully',
          type: 'object',
          properties: {
            success: { type: 'boolean', const: true },
            data: {
              type: 'object',
              properties: {
                query_id: { type: 'string' },
                result: { type: 'string' },
                sources: { type: 'array' },
                metadata: { type: 'object' },
                processing_details: {
                  type: 'object',
                  properties: {
                    image_analysis: { type: 'string' },
                    table_analysis: { type: 'string' },
                    total_processing_time_ms: { type: 'number' },
                  },
                },
              },
            },
          },
        },
      },
    },
  }, async (request: AuthenticatedRequest, reply) => {
    const { query, multimodal_content, mode = 'mix', stream = false } = request.body;
    const user = request.user!;
    
    try {
      const queryId = encrypt.uuid();
      
      // Validate multimodal content
      for (const content of multimodal_content) {
        if (content.type === 'image') {
          if (!content.img_path && !content.data) {
            throw new ValidationError('Image content requires either img_path or data');
          }
        } else if (content.type === 'table') {
          if (!content.table_data) {
            throw new ValidationError('Table content requires table_data');
          }
        } else if (content.type === 'equation') {
          if (!content.equation) {
            throw new ValidationError('Equation content requires equation');
          }
        }
      }

      // For synchronous execution (stream = false), use direct processing
      if (!stream) {
        // Initialize Python process if needed
        if (!pythonProcessManager.initialized) {
          await pythonProcessManager.initialize();
        }

        // Execute multimodal query directly through Python process
        const result = await pythonProcessManager.executeMultimodalQuery(
          query, 
          multimodal_content,
          mode
        );

        // Store query in database
        await db.prisma.$executeRaw`
          INSERT INTO queries (
            id, user_id, query_text, query_type, mode, 
            result_text, sources, metadata, processing_time_ms
          )
          VALUES (
            ${queryId}::uuid,
            ${user.id}::uuid,
            ${query},
            'multimodal',
            ${mode},
            ${result.answer || ''},
            ${JSON.stringify(result.sources || [])},
            ${JSON.stringify({
              mode,
              multimodal_content_count: multimodal_content.length,
              ...result.metadata
            })},
            ${result.processing_time || 0}
          )
        `;

        const response = {
          query_id: queryId,
          result: result.answer,
          sources: result.sources || [],
          metadata: {
            mode,
            processing_time_ms: result.processing_time,
            total_chunks_searched: result.metadata?.total_chunks || 0,
            vlm_enhanced: true,
          },
          processing_details: {
            text_analysis: 'completed',
            image_analysis: multimodal_content.some(c => c.type === 'image') ? 'completed' : 'skipped',
            table_analysis: multimodal_content.some(c => c.type === 'table') ? 'completed' : 'skipped',
            equation_analysis: multimodal_content.some(c => c.type === 'equation') ? 'completed' : 'skipped',
            total_processing_time_ms: result.processing_time,
          },
        };

        return reply.sendSuccess(response);
      } else {
        // For streaming, add to job queue
        const jobId = await jobQueueService.addQueryProcessingJob({
          queryId,
          userId: user.id,
          query,
          queryType: 'multimodal',
          mode,
          multimodalContent: multimodal_content,
        });

        // Return job ID for tracking
        const response = {
          query_id: queryId,
          job_id: jobId,
          status: 'processing',
          message: 'Multimodal query added to processing queue',
          metadata: {
            mode,
            vlm_enhanced: true,
            stream: true,
            multimodal_content_count: multimodal_content.length,
          },
        };

        return reply.sendSuccess(response);
      }
      
    } catch (error) {
      if (error instanceof ValidationError) {
        throw error;
      }
      throw new ProcessingError('Multimodal query execution failed', { error: error.message });
    }
  });

  /**
   * Get query history
   * GET /api/v1/query/history
   */
  fastify.get('/history', {
    schema: {
      description: 'Get user query history with pagination',
      tags: ['Query'],
      querystring: Type.Object({
        page: Type.Optional(Type.Number({ minimum: 1, default: 1 })),
        limit: Type.Optional(Type.Number({ minimum: 1, maximum: 50, default: 20 })),
        type: Type.Optional(Type.String()),
      }),
      response: {
        200: {
          description: 'Query history retrieved successfully',
          type: 'object',
          properties: {
            success: { type: 'boolean', const: true },
            data: {
              type: 'object',
              properties: {
                queries: {
                  type: 'array',
                  items: {
                    type: 'object',
                    properties: {
                      query_id: { type: 'string' },
                      query: { type: 'string' },
                      type: { type: 'string' },
                      mode: { type: 'string' },
                      created_at: { type: 'string' },
                      processing_time_ms: { type: 'number' },
                    },
                  },
                },
                pagination: { type: 'object' },
              },
            },
          },
        },
      },
    },
  }, async (request: AuthenticatedRequest, reply) => {
    const { page = 1, limit = 20, type } = request.query;
    const user = request.user!;
    
    try {
      const offset = (page - 1) * limit;
      
      // Build query with optional type filter
      const typeFilter = type ? `AND query_type = '${type}'` : '';
      
      // Get queries from database
      const queries = await db.prisma.$queryRaw<Array<{
        id: string;
        query_text: string;
        query_type: string;
        mode: string;
        sources: any;
        processing_time_ms: number;
        created_at: Date;
      }>>`
        SELECT id, query_text, query_type, mode, sources, processing_time_ms, created_at
        FROM queries
        WHERE user_id = ${user.id}::uuid ${typeFilter}
        ORDER BY created_at DESC
        LIMIT ${limit} OFFSET ${offset}
      `;

      // Get total count for pagination
      const countResult = await db.prisma.$queryRaw<Array<{ count: number }>>`
        SELECT COUNT(*)::INTEGER as count
        FROM queries
        WHERE user_id = ${user.id}::uuid ${typeFilter}
      `;

      const totalQueries = countResult[0]?.count || 0;
      const totalPages = Math.ceil(totalQueries / limit);

      // Format response
      const formattedQueries = queries.map(query => ({
        query_id: query.id,
        query: query.query_text,
        type: query.query_type,
        mode: query.mode,
        created_at: query.created_at.toISOString(),
        processing_time_ms: query.processing_time_ms || 0,
        sources_count: Array.isArray(query.sources) ? query.sources.length : 0,
      }));
      
      const response = {
        queries: formattedQueries,
        pagination: {
          current_page: page,
          per_page: limit,
          total_pages: totalPages,
          total_queries: totalQueries,
        },
      };
      
      return reply.sendSuccess(response);
      
    } catch (error) {
      throw new ProcessingError('Failed to retrieve query history');
    }
  });

}, {
  name: 'query-routes',
});