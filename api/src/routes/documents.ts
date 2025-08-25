import { FastifyInstance, FastifyPluginCallback } from 'fastify';
import fp from 'fastify-plugin';
import { Type } from '@sinclair/typebox';
import { ProcessDocumentRequestSchema, ProcessingResponseSchema } from '@/types/documents.js';
import { ProcessingError, ValidationError, NotFoundError } from '@/utils/errors.js';
import { fileOps } from '@/utils/file.js';
import { encrypt } from '@/utils/crypto.js';
import { jobQueueService } from '@/services/job-queue.js';
import { db } from '@/services/database.js';
import { AuthenticatedRequest } from '@/types/api.js';

/**
 * Document processing routes
 */
export const documentsRoutes: FastifyPluginCallback = fp(async (fastify: FastifyInstance) => {
  
  /**
   * Process single document
   * POST /api/v1/documents/process
   */
  fastify.post('/process', {
    schema: {
      description: 'Upload and process a single document with multimodal content extraction',
      tags: ['Document Processing'],
      consumes: ['multipart/form-data'],
      body: {
        type: 'object',
        properties: {
          file: { isFile: true },
          parse_method: { type: 'string', enum: ['auto', 'ocr', 'txt'], default: 'auto' },
          output_dir: { type: 'string' },
          display_stats: { type: 'boolean', default: true },
          doc_id: { type: 'string' },
        },
        required: ['file'],
      },
      response: {
        202: {
          description: 'Document processing started successfully',
          type: 'object',
          properties: {
            success: { type: 'boolean', const: true },
            data: {
              type: 'object',
              properties: {
                job_id: { type: 'string' },
                doc_id: { type: 'string' },
                status: { type: 'string' },
                file_info: {
                  type: 'object',
                  properties: {
                    filename: { type: 'string' },
                    size: { type: 'number' },
                    type: { type: 'string' },
                  },
                },
                estimated_completion: { type: 'string' },
              },
            },
          },
        },
      },
    },
  }, async (request: AuthenticatedRequest, reply) => {
    const user = request.user!;

    if (!request.isMultipart()) {
      throw new ValidationError('Request must be multipart/form-data');
    }

    try {
      const data = await request.file();
      if (!data) {
        throw new ValidationError('File is required');
      }

      // Convert file stream to buffer
      const buffer = await data.toBuffer();
      
      // Validate file
      const validation = await fileOps.validateFile(buffer, data.filename);
      if (!validation.valid) {
        throw new ValidationError('File validation failed', {
          errors: validation.errors,
        });
      }

      // Save file
      const fileMetadata = await fileOps.saveFile(buffer, data.filename, 'uploads');
      
      // Generate document ID
      const docId = encrypt.uuid();
      
      // Store document metadata in database
      await db.prisma.$executeRaw`
        INSERT INTO documents (
          id, user_id, filename, original_name, file_path, 
          file_size, mime_type, checksum, status
        )
        VALUES (
          ${docId}::uuid,
          ${user.id}::uuid,
          ${fileMetadata.filename},
          ${data.filename},
          ${fileMetadata.path},
          ${fileMetadata.size},
          ${fileMetadata.mimeType},
          ${fileMetadata.checksum},
          'uploaded'
        )
      `;
      
      // Queue document processing job
      const jobId = await jobQueueService.addDocumentProcessingJob({
        documentId: docId,
        userId: user.id,
        filePath: fileMetadata.path,
        filename: fileMetadata.filename,
        options: {
          parseMethod: 'auto',
          displayStats: true,
        },
      });
      
      const response = {
        job_id: jobId,
        doc_id: docId,
        status: 'queued' as const,
        file_info: {
          filename: fileMetadata.filename,
          size: fileMetadata.size,
          type: fileMetadata.mimeType,
          checksum: fileMetadata.checksum,
        },
        processing_options: {
          parse_method: 'auto',
          display_stats: true,
        },
        estimated_completion: new Date(Date.now() + 5 * 60 * 1000).toISOString(), // 5 minutes
      };
      
      return reply.status(202).sendSuccess(response);
      
    } catch (error) {
      if (error instanceof ValidationError) {
        throw error;
      }
      throw new ProcessingError('Failed to process document', { error: error.message });
    }
  });

  /**
   * Get document list
   * GET /api/v1/documents
   */
  fastify.get('/', {
    schema: {
      description: 'List processed documents with pagination',
      tags: ['Document Management'],
      querystring: Type.Object({
        page: Type.Optional(Type.Number({ minimum: 1, default: 1 })),
        limit: Type.Optional(Type.Number({ minimum: 1, maximum: 100, default: 20 })),
        status: Type.Optional(Type.String()),
        search: Type.Optional(Type.String()),
      }),
      response: {
        200: {
          description: 'Documents retrieved successfully',
          type: 'object',
          properties: {
            success: { type: 'boolean', const: true },
            data: {
              type: 'object',
              properties: {
                documents: {
                  type: 'array',
                  items: {
                    type: 'object',
                    properties: {
                      doc_id: { type: 'string' },
                      filename: { type: 'string' },
                      status: { type: 'string' },
                      created_at: { type: 'string' },
                      chunks_count: { type: 'number' },
                    },
                  },
                },
                pagination: {
                  type: 'object',
                  properties: {
                    current_page: { type: 'number' },
                    per_page: { type: 'number' },
                    total_pages: { type: 'number' },
                    total_documents: { type: 'number' },
                  },
                },
              },
            },
          },
        },
      },
    },
  }, async (request: AuthenticatedRequest, reply) => {
    const { page = 1, limit = 20, status, search } = request.query;
    const user = request.user!;
    
    try {
      const offset = (page - 1) * limit;
      
      // Build query filters
      const statusFilter = status ? `AND status = '${status}'` : '';
      const searchFilter = search ? `AND (filename ILIKE '%${search}%' OR original_name ILIKE '%${search}%')` : '';
      
      // Get documents from database
      const documents = await db.prisma.$queryRaw<Array<{
        id: string;
        filename: string;
        original_name: string;
        status: string;
        file_size: number;
        mime_type: string;
        processing_metadata: any;
        created_at: Date;
        updated_at: Date;
      }>>`
        SELECT id, filename, original_name, status, file_size, mime_type, 
               processing_metadata, created_at, updated_at
        FROM documents
        WHERE user_id = ${user.id}::uuid ${statusFilter} ${searchFilter}
        ORDER BY created_at DESC
        LIMIT ${limit} OFFSET ${offset}
      `;

      // Get total count for pagination
      const countResult = await db.prisma.$queryRaw<Array<{ count: number }>>`
        SELECT COUNT(*)::INTEGER as count
        FROM documents
        WHERE user_id = ${user.id}::uuid ${statusFilter} ${searchFilter}
      `;

      const totalDocuments = countResult[0]?.count || 0;
      const totalPages = Math.ceil(totalDocuments / limit);

      // Format response
      const formattedDocuments = documents.map(doc => {
        const metadata = doc.processing_metadata || {};
        return {
          doc_id: doc.id,
          filename: doc.filename,
          original_name: doc.original_name,
          status: doc.status,
          created_at: doc.created_at.toISOString(),
          updated_at: doc.updated_at.toISOString(),
          chunks_count: metadata.chunks_count || 0,
          file_size: doc.file_size,
          content_types: metadata.content_types || ['text'],
          mime_type: doc.mime_type,
        };
      });
      
      const response = {
        documents: formattedDocuments,
        pagination: {
          current_page: page,
          per_page: limit,
          total_pages: totalPages,
          total_documents: totalDocuments,
        },
        filters: {
          status: ['uploaded', 'processing', 'processed', 'failed'],
          type: ['pdf', 'docx', 'pptx', 'txt', 'md'],
          content_types: ['text', 'image', 'table', 'equation'],
        },
      };
      
      return reply.sendSuccess(response);
      
    } catch (error) {
      throw new ProcessingError('Failed to retrieve documents');
    }
  });

  /**
   * Get document details
   * GET /api/v1/documents/:docId
   */
  fastify.get('/:docId', {
    schema: {
      description: 'Get detailed information about a specific document',
      tags: ['Document Management'],
      params: Type.Object({
        docId: Type.String(),
      }),
      response: {
        200: {
          description: 'Document details retrieved successfully',
          type: 'object',
          properties: {
            success: { type: 'boolean', const: true },
            data: {
              type: 'object',
              properties: {
                doc_id: { type: 'string' },
                filename: { type: 'string' },
                status: { type: 'string' },
                processing_details: { type: 'object' },
                content_analysis: { type: 'object' },
              },
            },
          },
        },
        404: {
          description: 'Document not found',
          type: 'object',
          properties: {
            success: { type: 'boolean', const: false },
            error: { type: 'object' },
          },
        },
      },
    },
  }, async (request: AuthenticatedRequest, reply) => {
    const { docId } = request.params;
    const user = request.user!;
    
    try {
      // Get document from database
      const documents = await db.prisma.$queryRaw<Array<{
        id: string;
        filename: string;
        original_name: string;
        file_path: string;
        status: string;
        file_size: number;
        mime_type: string;
        checksum: string;
        processing_metadata: any;
        created_at: Date;
        updated_at: Date;
      }>>`
        SELECT id, filename, original_name, file_path, status, file_size, 
               mime_type, checksum, processing_metadata, created_at, updated_at
        FROM documents
        WHERE id = ${docId}::uuid AND user_id = ${user.id}::uuid
      `;

      if (!documents || documents.length === 0) {
        throw new NotFoundError('Document', docId);
      }

      const document = documents[0];
      const metadata = document.processing_metadata || {};
      
      const documentDetails = {
        doc_id: document.id,
        filename: document.filename,
        original_name: document.original_name,
        status: document.status,
        created_at: document.created_at.toISOString(),
        updated_at: document.updated_at.toISOString(),
        chunks_count: metadata.chunks_count || 0,
        file_size: document.file_size,
        content_types: metadata.content_types || ['text'],
        processing_details: {
          text_processed: metadata.text_processed || false,
          multimodal_processed: metadata.multimodal_processed || false,
          chunks_count: metadata.chunks_count || 0,
          entities_count: metadata.entities_count || 0,
          relations_count: metadata.relations_count || 0,
          processing_time_ms: metadata.processing_time_ms || 0,
        },
        content_analysis: {
          text_blocks: metadata.text_blocks || 0,
          image_blocks: metadata.image_blocks || 0,
          table_blocks: metadata.table_blocks || 0,
          equation_blocks: metadata.equation_blocks || 0,
          total_tokens: metadata.total_tokens || 0,
        },
        file_info: {
          filename: document.filename,
          original_name: document.original_name,
          size: document.file_size,
          type: document.mime_type,
          checksum: document.checksum,
          file_path: document.file_path,
        },
      };
      
      return reply.sendSuccess(documentDetails);
      
    } catch (error) {
      if (error instanceof NotFoundError) {
        throw error;
      }
      throw new ProcessingError('Failed to retrieve document details');
    }
  });

  /**
   * Delete document
   * DELETE /api/v1/documents/:docId
   */
  fastify.delete('/:docId', {
    schema: {
      description: 'Remove document and all associated data from the system',
      tags: ['Document Management'],
      params: Type.Object({
        docId: Type.String(),
      }),
      response: {
        200: {
          description: 'Document deleted successfully',
          type: 'object',
          properties: {
            success: { type: 'boolean', const: true },
            data: {
              type: 'object',
              properties: {
                doc_id: { type: 'string' },
                deleted: { type: 'boolean' },
                cleanup_summary: { type: 'object' },
              },
            },
          },
        },
      },
    },
  }, async (request: AuthenticatedRequest, reply) => {
    const { docId } = request.params;
    const user = request.user!;
    
    try {
      // Check if document exists and get its info
      const documents = await db.prisma.$queryRaw<Array<{
        id: string;
        filename: string;
        file_path: string;
        status: string;
        file_size: number;
        processing_metadata: any;
      }>>`
        SELECT id, filename, file_path, status, file_size, processing_metadata
        FROM documents
        WHERE id = ${docId}::uuid AND user_id = ${user.id}::uuid
      `;

      if (!documents || documents.length === 0) {
        throw new NotFoundError('Document', docId);
      }

      const document = documents[0];
      const metadata = document.processing_metadata || {};
      
      // Cancel any pending jobs for this document
      let processingCancelled = false;
      const activeJobs = await db.prisma.$queryRaw<Array<{ job_id: string }>>`
        SELECT job_id FROM job_status 
        WHERE user_id = ${user.id}::uuid 
        AND job_type = 'document_processing'
        AND status IN ('pending', 'active')
        AND result->>'documentId' = ${docId}
      `;

      if (activeJobs.length > 0) {
        for (const job of activeJobs) {
          await jobQueueService.cancelJob(job.job_id);
        }
        processingCancelled = true;
      }

      // Delete from database (cascade will handle related records)
      const deleteResult = await db.prisma.$executeRaw`
        DELETE FROM documents 
        WHERE id = ${docId}::uuid AND user_id = ${user.id}::uuid
      `;

      if (deleteResult === 0) {
        throw new NotFoundError('Document', docId);
      }

      // Clean up file from storage
      let filesRemoved = 0;
      let storageFreedMb = 0;
      
      try {
        await fileOps.deleteFile(document.file_path);
        filesRemoved = 1;
        storageFreedMb = Math.round((document.file_size / 1024 / 1024) * 100) / 100;
      } catch (fileError) {
        // Log but don't fail the delete operation if file cleanup fails
        console.warn(`Failed to delete file ${document.file_path}:`, fileError);
      }

      const cleanupSummary = {
        chunks_removed: metadata.chunks_count || 0,
        entities_removed: metadata.entities_count || 0,
        relations_removed: metadata.relations_count || 0,
        files_removed: filesRemoved,
        storage_freed_mb: storageFreedMb,
      };
      
      const response = {
        doc_id: docId,
        deleted: true,
        cleanup_summary: cleanupSummary,
        processing_cancelled: processingCancelled,
      };
      
      return reply.sendSuccess(response);
      
    } catch (error) {
      if (error instanceof NotFoundError) {
        throw error;
      }
      throw new ProcessingError('Failed to delete document');
    }
  });

}, {
  name: 'documents-routes',
});