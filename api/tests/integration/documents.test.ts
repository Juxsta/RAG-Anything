import { FastifyInstance } from 'fastify';
import { build } from '@/app';
import { authService } from '@/services/auth';
import { jobQueueService } from '@/services/job-queue';
import { fileOps } from '@/utils/file';
import fs from 'fs/promises';
import path from 'path';

// Mock dependencies
jest.mock('@/services/job-queue');
jest.mock('@/utils/file');

const mockJobQueue = jobQueueService as jest.Mocked<typeof jobQueueService>;
const mockFileOps = fileOps as jest.Mocked<typeof fileOps>;

describe('Documents Integration Tests', () => {
  let app: FastifyInstance;
  let accessToken: string;
  let testUser: any;

  beforeAll(async () => {
    app = await build({ logger: false });
    await app.ready();
  });

  afterAll(async () => {
    await app.close();
  });

  beforeEach(async () => {
    jest.clearAllMocks();
    
    // Clean up and prepare test data
    if (global.testEnv?.prisma) {
      await global.testEnv.prisma.$executeRaw`TRUNCATE TABLE documents CASCADE`;
      await global.testEnv.prisma.$executeRaw`TRUNCATE TABLE users CASCADE`;
    }

    // Create test user and get access token
    testUser = await authService.createUser({
      email: 'test@example.com',
      password: 'SecurePassword123!',
      role: 'user',
    });

    const loginResult = await authService.login({
      email: 'test@example.com',
      password: 'SecurePassword123!',
    });

    accessToken = loginResult.accessToken;
  });

  describe('POST /api/v1/documents/process', () => {
    it('should process document successfully', async () => {
      // Mock file operations
      mockFileOps.validateFile.mockResolvedValue({
        valid: true,
        errors: [],
      });
      
      mockFileOps.saveFile.mockResolvedValue({
        filename: 'test-document.pdf',
        path: '/uploads/test-document.pdf',
        size: 1024000,
        mimeType: 'application/pdf',
        checksum: 'abc123hash',
      });

      mockJobQueue.addDocumentProcessingJob.mockResolvedValue('job-123');

      // Create a test file buffer
      const testFileBuffer = Buffer.from('test file content');
      
      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/documents/process',
        headers: {
          authorization: `Bearer ${accessToken}`,
          'content-type': 'multipart/form-data; boundary=----formdata-boundary',
        },
        payload: [
          '------formdata-boundary',
          'Content-Disposition: form-data; name="file"; filename="test.pdf"',
          'Content-Type: application/pdf',
          '',
          testFileBuffer.toString(),
          '------formdata-boundary--',
        ].join('\r\n'),
      });

      expect(response.statusCode).toBe(202);
      const body = JSON.parse(response.body);
      
      expect(body.success).toBe(true);
      expect(body.data.status).toBe('queued');
      expect(body.data).toHaveProperty('job_id');
      expect(body.data).toHaveProperty('doc_id');
      expect(body.data.file_info).toEqual({
        filename: 'test-document.pdf',
        size: 1024000,
        type: 'application/pdf',
        checksum: 'abc123hash',
      });
      
      expect(mockJobQueue.addDocumentProcessingJob).toHaveBeenCalledWith({
        documentId: expect.any(String),
        userId: testUser.id,
        filePath: '/uploads/test-document.pdf',
        filename: 'test-document.pdf',
        options: {
          parseMethod: 'auto',
          displayStats: true,
        },
      });

      // Verify document was stored in database
      const documents = await global.testEnv.prisma.$queryRaw<Array<{
        filename: string;
        status: string;
        user_id: string;
      }>>`
        SELECT filename, status, user_id
        FROM documents
        WHERE user_id = ${testUser.id}::uuid
      `;

      expect(documents).toHaveLength(1);
      expect(documents[0].filename).toBe('test-document.pdf');
      expect(documents[0].status).toBe('uploaded');
    });

    it('should return 401 without authentication', async () => {
      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/documents/process',
        headers: {
          'content-type': 'multipart/form-data; boundary=----formdata-boundary',
        },
        payload: [
          '------formdata-boundary',
          'Content-Disposition: form-data; name="file"; filename="test.pdf"',
          'Content-Type: application/pdf',
          '',
          'test content',
          '------formdata-boundary--',
        ].join('\r\n'),
      });

      expect(response.statusCode).toBe(401);
    });

    it('should return 400 for non-multipart request', async () => {
      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/documents/process',
        headers: {
          authorization: `Bearer ${accessToken}`,
          'content-type': 'application/json',
        },
        payload: { file: 'not a file' },
      });

      expect(response.statusCode).toBe(400);
      const body = JSON.parse(response.body);
      expect(body.error.message).toContain('multipart/form-data');
    });

    it('should return 400 for missing file', async () => {
      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/documents/process',
        headers: {
          authorization: `Bearer ${accessToken}`,
          'content-type': 'multipart/form-data; boundary=----formdata-boundary',
        },
        payload: [
          '------formdata-boundary',
          'Content-Disposition: form-data; name="other"',
          '',
          'not a file',
          '------formdata-boundary--',
        ].join('\r\n'),
      });

      expect(response.statusCode).toBe(400);
    });

    it('should return 400 for invalid file', async () => {
      mockFileOps.validateFile.mockResolvedValue({
        valid: false,
        errors: ['Unsupported file type', 'File too large'],
      });

      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/documents/process',
        headers: {
          authorization: `Bearer ${accessToken}`,
          'content-type': 'multipart/form-data; boundary=----formdata-boundary',
        },
        payload: [
          '------formdata-boundary',
          'Content-Disposition: form-data; name="file"; filename="invalid.exe"',
          'Content-Type: application/octet-stream',
          '',
          'malicious content',
          '------formdata-boundary--',
        ].join('\r\n'),
      });

      expect(response.statusCode).toBe(400);
      const body = JSON.parse(response.body);
      expect(body.error.details.errors).toEqual(['Unsupported file type', 'File too large']);
    });

    it('should handle file save errors', async () => {
      mockFileOps.validateFile.mockResolvedValue({
        valid: true,
        errors: [],
      });
      
      mockFileOps.saveFile.mockRejectedValue(new Error('Disk full'));

      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/documents/process',
        headers: {
          authorization: `Bearer ${accessToken}`,
          'content-type': 'multipart/form-data; boundary=----formdata-boundary',
        },
        payload: [
          '------formdata-boundary',
          'Content-Disposition: form-data; name="file"; filename="test.pdf"',
          'Content-Type: application/pdf',
          '',
          'test content',
          '------formdata-boundary--',
        ].join('\r\n'),
      });

      expect(response.statusCode).toBe(500);
      const body = JSON.parse(response.body);
      expect(body.error.message).toContain('Failed to process document');
    });
  });

  describe('GET /api/v1/documents', () => {
    beforeEach(async () => {
      // Create some test documents
      await global.testEnv.prisma.$executeRaw`
        INSERT INTO documents (id, user_id, filename, original_name, file_path, file_size, mime_type, checksum, status, processing_metadata, created_at)
        VALUES 
          (uuid_generate_v4(), ${testUser.id}::uuid, 'doc1.pdf', 'Document 1.pdf', '/uploads/doc1.pdf', 1024000, 'application/pdf', 'hash1', 'processed', '{"chunks_count": 10}', CURRENT_TIMESTAMP - INTERVAL '1 hour'),
          (uuid_generate_v4(), ${testUser.id}::uuid, 'doc2.docx', 'Document 2.docx', '/uploads/doc2.docx', 2048000, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'hash2', 'processing', '{"chunks_count": 0}', CURRENT_TIMESTAMP - INTERVAL '30 minutes'),
          (uuid_generate_v4(), ${testUser.id}::uuid, 'doc3.txt', 'Document 3.txt', '/uploads/doc3.txt', 5120, 'text/plain', 'hash3', 'failed', '{"error": "Processing failed"}', CURRENT_TIMESTAMP - INTERVAL '15 minutes')
      `;
    });

    it('should return documents with pagination', async () => {
      const response = await app.inject({
        method: 'GET',
        url: '/api/v1/documents?page=1&limit=2',
        headers: {
          authorization: `Bearer ${accessToken}`,
        },
      });

      expect(response.statusCode).toBe(200);
      const body = JSON.parse(response.body);
      
      expect(body.success).toBe(true);
      expect(body.data.documents).toHaveLength(2);
      expect(body.data.pagination).toEqual({
        current_page: 1,
        per_page: 2,
        total_pages: 2,
        total_documents: 3,
      });

      // Should be ordered by created_at DESC
      expect(new Date(body.data.documents[0].created_at))
        .toBeAfter(new Date(body.data.documents[1].created_at));
    });

    it('should filter documents by status', async () => {
      const response = await app.inject({
        method: 'GET',
        url: '/api/v1/documents?status=processed',
        headers: {
          authorization: `Bearer ${accessToken}`,
        },
      });

      expect(response.statusCode).toBe(200);
      const body = JSON.parse(response.body);
      
      expect(body.data.documents).toHaveLength(1);
      expect(body.data.documents[0].status).toBe('processed');
      expect(body.data.documents[0].filename).toBe('doc1.pdf');
    });

    it('should search documents by filename', async () => {
      const response = await app.inject({
        method: 'GET',
        url: '/api/v1/documents?search=doc1',
        headers: {
          authorization: `Bearer ${accessToken}`,
        },
      });

      expect(response.statusCode).toBe(200);
      const body = JSON.parse(response.body);
      
      expect(body.data.documents).toHaveLength(1);
      expect(body.data.documents[0].filename).toBe('doc1.pdf');
    });

    it('should return empty results for user with no documents', async () => {
      const anotherUser = await authService.createUser({
        email: 'another@example.com',
        password: 'Password123!',
        role: 'user',
      });

      const anotherLogin = await authService.login({
        email: 'another@example.com',
        password: 'Password123!',
      });

      const response = await app.inject({
        method: 'GET',
        url: '/api/v1/documents',
        headers: {
          authorization: `Bearer ${anotherLogin.accessToken}`,
        },
      });

      expect(response.statusCode).toBe(200);
      const body = JSON.parse(response.body);
      
      expect(body.data.documents).toHaveLength(0);
      expect(body.data.pagination.total_documents).toBe(0);
    });

    it('should return 401 without authentication', async () => {
      const response = await app.inject({
        method: 'GET',
        url: '/api/v1/documents',
      });

      expect(response.statusCode).toBe(401);
    });

    it('should include document metadata in response', async () => {
      const response = await app.inject({
        method: 'GET',
        url: '/api/v1/documents',
        headers: {
          authorization: `Bearer ${accessToken}`,
        },
      });

      expect(response.statusCode).toBe(200);
      const body = JSON.parse(response.body);
      
      body.data.documents.forEach((doc: any) => {
        expect(doc).toHaveProperty('doc_id');
        expect(doc).toHaveProperty('filename');
        expect(doc).toHaveProperty('original_name');
        expect(doc).toHaveProperty('status');
        expect(doc).toHaveProperty('file_size');
        expect(doc).toHaveProperty('mime_type');
        expect(doc).toHaveProperty('chunks_count');
        expect(doc).toHaveProperty('content_types');
        expect(doc).toHaveProperty('created_at');
        expect(doc).toHaveProperty('updated_at');
      });
    });

    it('should provide filter options in response', async () => {
      const response = await app.inject({
        method: 'GET',
        url: '/api/v1/documents',
        headers: {
          authorization: `Bearer ${accessToken}`,
        },
      });

      expect(response.statusCode).toBe(200);
      const body = JSON.parse(response.body);
      
      expect(body.data.filters).toEqual({
        status: ['uploaded', 'processing', 'processed', 'failed'],
        type: ['pdf', 'docx', 'pptx', 'txt', 'md'],
        content_types: ['text', 'image', 'table', 'equation'],
      });
    });
  });

  describe('GET /api/v1/documents/:docId', () => {
    let documentId: string;

    beforeEach(async () => {
      const docResult = await global.testEnv.prisma.$queryRaw<Array<{ id: string }>>`
        INSERT INTO documents (id, user_id, filename, original_name, file_path, file_size, mime_type, checksum, status, processing_metadata)
        VALUES (uuid_generate_v4(), ${testUser.id}::uuid, 'detail-doc.pdf', 'Detail Document.pdf', '/uploads/detail-doc.pdf', 2048000, 'application/pdf', 'detailhash', 'processed', '{"chunks_count": 25, "entities_count": 100, "text_blocks": 20, "image_blocks": 3}')
        RETURNING id
      `;
      documentId = docResult[0].id;
    });

    it('should return document details', async () => {
      const response = await app.inject({
        method: 'GET',
        url: `/api/v1/documents/${documentId}`,
        headers: {
          authorization: `Bearer ${accessToken}`,
        },
      });

      expect(response.statusCode).toBe(200);
      const body = JSON.parse(response.body);
      
      expect(body.success).toBe(true);
      expect(body.data.doc_id).toBe(documentId);
      expect(body.data.filename).toBe('detail-doc.pdf');
      expect(body.data.original_name).toBe('Detail Document.pdf');
      expect(body.data.status).toBe('processed');
      expect(body.data.chunks_count).toBe(25);
      
      expect(body.data.processing_details).toEqual({
        text_processed: false,
        multimodal_processed: false,
        chunks_count: 25,
        entities_count: 100,
        relations_count: 0,
        processing_time_ms: 0,
      });
      
      expect(body.data.content_analysis).toEqual({
        text_blocks: 20,
        image_blocks: 3,
        table_blocks: 0,
        equation_blocks: 0,
        total_tokens: 0,
      });
      
      expect(body.data.file_info).toEqual({
        filename: 'detail-doc.pdf',
        original_name: 'Detail Document.pdf',
        size: 2048000,
        type: 'application/pdf',
        checksum: 'detailhash',
        file_path: '/uploads/detail-doc.pdf',
      });
    });

    it('should return 404 for non-existent document', async () => {
      const fakeId = '123e4567-e89b-12d3-a456-426614174000';
      
      const response = await app.inject({
        method: 'GET',
        url: `/api/v1/documents/${fakeId}`,
        headers: {
          authorization: `Bearer ${accessToken}`,
        },
      });

      expect(response.statusCode).toBe(404);
      const body = JSON.parse(response.body);
      expect(body.error.message).toContain('Document not found');
    });

    it('should return 404 for document belonging to another user', async () => {
      // Create another user and their document
      const anotherUser = await authService.createUser({
        email: 'another@example.com',
        password: 'Password123!',
        role: 'user',
      });

      const otherDocResult = await global.testEnv.prisma.$queryRaw<Array<{ id: string }>>`
        INSERT INTO documents (id, user_id, filename, original_name, file_path, file_size, mime_type, checksum, status)
        VALUES (uuid_generate_v4(), ${anotherUser.id}::uuid, 'other-doc.pdf', 'Other Document.pdf', '/uploads/other-doc.pdf', 1024000, 'application/pdf', 'otherhash', 'processed')
        RETURNING id
      `;
      const otherDocId = otherDocResult[0].id;

      const response = await app.inject({
        method: 'GET',
        url: `/api/v1/documents/${otherDocId}`,
        headers: {
          authorization: `Bearer ${accessToken}`,
        },
      });

      expect(response.statusCode).toBe(404);
    });

    it('should return 401 without authentication', async () => {
      const response = await app.inject({
        method: 'GET',
        url: `/api/v1/documents/${documentId}`,
      });

      expect(response.statusCode).toBe(401);
    });
  });

  describe('DELETE /api/v1/documents/:docId', () => {
    let documentId: string;

    beforeEach(async () => {
      const docResult = await global.testEnv.prisma.$queryRaw<Array<{ id: string }>>`
        INSERT INTO documents (id, user_id, filename, original_name, file_path, file_size, mime_type, checksum, status, processing_metadata)
        VALUES (uuid_generate_v4(), ${testUser.id}::uuid, 'delete-doc.pdf', 'Delete Document.pdf', '/uploads/delete-doc.pdf', 1024000, 'application/pdf', 'deletehash', 'processed', '{"chunks_count": 15, "entities_count": 50}')
        RETURNING id
      `;
      documentId = docResult[0].id;

      // Mock file operations
      mockFileOps.deleteFile.mockResolvedValue();
    });

    it('should delete document successfully', async () => {
      const response = await app.inject({
        method: 'DELETE',
        url: `/api/v1/documents/${documentId}`,
        headers: {
          authorization: `Bearer ${accessToken}`,
        },
      });

      expect(response.statusCode).toBe(200);
      const body = JSON.parse(response.body);
      
      expect(body.success).toBe(true);
      expect(body.data.doc_id).toBe(documentId);
      expect(body.data.deleted).toBe(true);
      expect(body.data.cleanup_summary).toEqual({
        chunks_removed: 15,
        entities_removed: 50,
        relations_removed: 0,
        files_removed: 1,
        storage_freed_mb: 1.0,
      });
      expect(body.data.processing_cancelled).toBe(false);

      // Verify document was deleted from database
      const documents = await global.testEnv.prisma.$queryRaw<Array<{ id: string }>>`
        SELECT id FROM documents WHERE id = ${documentId}::uuid
      `;
      expect(documents).toHaveLength(0);

      // Verify file deletion was attempted
      expect(mockFileOps.deleteFile).toHaveBeenCalledWith('/uploads/delete-doc.pdf');
    });

    it('should handle file deletion errors gracefully', async () => {
      mockFileOps.deleteFile.mockRejectedValue(new Error('File not found'));

      const response = await app.inject({
        method: 'DELETE',
        url: `/api/v1/documents/${documentId}`,
        headers: {
          authorization: `Bearer ${accessToken}`,
        },
      });

      expect(response.statusCode).toBe(200);
      const body = JSON.parse(response.body);
      
      expect(body.data.deleted).toBe(true);
      expect(body.data.cleanup_summary.files_removed).toBe(0);
      expect(body.data.cleanup_summary.storage_freed_mb).toBe(0);
    });

    it('should cancel active processing jobs', async () => {
      // Create a mock active job
      await global.testEnv.prisma.$executeRaw`
        INSERT INTO job_status (job_id, user_id, job_type, status, result)
        VALUES ('active-job-123', ${testUser.id}::uuid, 'document_processing', 'active', '{"documentId": "${documentId}"}')
      `;

      mockJobQueue.cancelJob.mockResolvedValue(true);

      const response = await app.inject({
        method: 'DELETE',
        url: `/api/v1/documents/${documentId}`,
        headers: {
          authorization: `Bearer ${accessToken}`,
        },
      });

      expect(response.statusCode).toBe(200);
      const body = JSON.parse(response.body);
      
      expect(body.data.processing_cancelled).toBe(true);
      expect(mockJobQueue.cancelJob).toHaveBeenCalledWith('active-job-123');
    });

    it('should return 404 for non-existent document', async () => {
      const fakeId = '123e4567-e89b-12d3-a456-426614174000';
      
      const response = await app.inject({
        method: 'DELETE',
        url: `/api/v1/documents/${fakeId}`,
        headers: {
          authorization: `Bearer ${accessToken}`,
        },
      });

      expect(response.statusCode).toBe(404);
    });

    it('should return 404 for document belonging to another user', async () => {
      const anotherUser = await authService.createUser({
        email: 'another@example.com',
        password: 'Password123!',
        role: 'user',
      });

      const otherDocResult = await global.testEnv.prisma.$queryRaw<Array<{ id: string }>>`
        INSERT INTO documents (id, user_id, filename, original_name, file_path, file_size, mime_type, checksum, status)
        VALUES (uuid_generate_v4(), ${anotherUser.id}::uuid, 'other-doc.pdf', 'Other Document.pdf', '/uploads/other-doc.pdf', 1024000, 'application/pdf', 'otherhash', 'processed')
        RETURNING id
      `;
      const otherDocId = otherDocResult[0].id;

      const response = await app.inject({
        method: 'DELETE',
        url: `/api/v1/documents/${otherDocId}`,
        headers: {
          authorization: `Bearer ${accessToken}`,
        },
      });

      expect(response.statusCode).toBe(404);
    });

    it('should return 401 without authentication', async () => {
      const response = await app.inject({
        method: 'DELETE',
        url: `/api/v1/documents/${documentId}`,
      });

      expect(response.statusCode).toBe(401);
    });
  });
});