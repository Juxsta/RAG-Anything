import { JobQueueService, JobStatus } from '@/services/job-queue';
import { Queue, Worker, Job } from 'bullmq';
import { createClient } from 'redis';
import { pythonProcessManager } from '@/services/python-process-manager';
import { db } from '@/services/database';

// Mock dependencies
jest.mock('bullmq');
jest.mock('redis');
jest.mock('@/services/python-process-manager');
jest.mock('@/services/database');

const mockQueue = Queue as jest.MockedClass<typeof Queue>;
const mockWorker = Worker as jest.MockedClass<typeof Worker>;
const mockCreateClient = createClient as jest.MockedFunction<typeof createClient>;
const mockPythonManager = pythonProcessManager as jest.Mocked<typeof pythonProcessManager>;
const mockDb = db as jest.Mocked<typeof db>;

describe('JobQueueService', () => {
  let jobQueueService: JobQueueService;
  let mockRedisClient: any;
  let mockDocumentQueue: jest.Mocked<Queue>;
  let mockQueryQueue: jest.Mocked<Queue>;
  let mockDocumentWorker: jest.Mocked<Worker>;
  let mockQueryWorker: jest.Mocked<Worker>;

  beforeEach(() => {
    jest.clearAllMocks();

    // Mock Redis client
    mockRedisClient = {
      connect: jest.fn(),
    };
    mockCreateClient.mockReturnValue(mockRedisClient);

    // Mock queues
    mockDocumentQueue = {
      add: jest.fn(),
      getJob: jest.fn(),
      getJobCounts: jest.fn(),
      close: jest.fn(),
    } as any;

    mockQueryQueue = {
      add: jest.fn(),
      getJob: jest.fn(), 
      getJobCounts: jest.fn(),
      close: jest.fn(),
    } as any;

    // Mock workers
    mockDocumentWorker = {
      on: jest.fn(),
      close: jest.fn(),
    } as any;

    mockQueryWorker = {
      on: jest.fn(),
      close: jest.fn(),
    } as any;

    mockQueue.mockImplementation((name: string) => {
      if (name === 'document-processing') return mockDocumentQueue as any;
      if (name === 'query-processing') return mockQueryQueue as any;
      return {} as any;
    });

    mockWorker.mockImplementation((name: string) => {
      if (name === 'document-processing') return mockDocumentWorker as any;
      if (name === 'query-processing') return mockQueryWorker as any;
      return {} as any;
    });

    jobQueueService = new JobQueueService();
  });

  afterEach(() => {
    jest.resetAllMocks();
  });

  describe('initialize', () => {
    it('should initialize redis connection successfully', async () => {
      mockRedisClient.connect.mockResolvedValue(undefined);

      await jobQueueService.initialize();

      expect(mockRedisClient.connect).toHaveBeenCalled();
    });

    it('should handle connection errors', async () => {
      const error = new Error('Connection failed');
      mockRedisClient.connect.mockRejectedValue(error);

      await expect(jobQueueService.initialize()).rejects.toThrow('Connection failed');
    });
  });

  describe('addDocumentProcessingJob', () => {
    beforeEach(() => {
      mockDb.prisma.$executeRaw.mockResolvedValue(1);
    });

    it('should add document processing job successfully', async () => {
      const jobData = {
        documentId: 'doc-123',
        userId: 'user-123',
        filePath: '/path/to/file.pdf',
        filename: 'file.pdf',
      };

      const mockJob = { id: 'job-123' } as Job;
      mockDocumentQueue.add.mockResolvedValue(mockJob);

      const jobId = await jobQueueService.addDocumentProcessingJob(jobData);

      expect(jobId).toBe('job-123');
      expect(mockDocumentQueue.add).toHaveBeenCalledWith(
        'process-document',
        jobData,
        expect.any(Object)
      );
      expect(mockDb.prisma.$executeRaw).toHaveBeenCalled();
    });

    it('should handle job creation with priority and delay options', async () => {
      const jobData = {
        documentId: 'doc-123',
        userId: 'user-123',
        filePath: '/path/to/file.pdf',
        filename: 'file.pdf',
      };

      const mockJob = { id: 'job-123' } as Job;
      mockDocumentQueue.add.mockResolvedValue(mockJob);

      await jobQueueService.addDocumentProcessingJob(jobData, {
        priority: 10,
        delay: 5000,
      });

      expect(mockDocumentQueue.add).toHaveBeenCalledWith(
        'process-document',
        jobData,
        expect.objectContaining({
          priority: 10,
          delay: 5000,
        })
      );
    });

    it('should handle job creation failures', async () => {
      const jobData = {
        documentId: 'doc-123',
        userId: 'user-123',
        filePath: '/path/to/file.pdf',
        filename: 'file.pdf',
      };

      mockDocumentQueue.add.mockRejectedValue(new Error('Queue error'));

      await expect(jobQueueService.addDocumentProcessingJob(jobData))
        .rejects
        .toThrow('Queue error');
    });
  });

  describe('addQueryProcessingJob', () => {
    beforeEach(() => {
      mockDb.prisma.$executeRaw.mockResolvedValue(1);
    });

    it('should add query processing job successfully', async () => {
      const jobData = {
        queryId: 'query-123',
        userId: 'user-123',
        query: 'What is AI?',
        queryType: 'text' as const,
        mode: 'mix' as const,
      };

      const mockJob = { id: 'job-456' } as Job;
      mockQueryQueue.add.mockResolvedValue(mockJob);

      const jobId = await jobQueueService.addQueryProcessingJob(jobData);

      expect(jobId).toBe('job-456');
      expect(mockQueryQueue.add).toHaveBeenCalledWith(
        'process-query',
        jobData,
        expect.any(Object)
      );
    });

    it('should add multimodal query processing job', async () => {
      const jobData = {
        queryId: 'query-123',
        userId: 'user-123',
        query: 'What is in this image?',
        queryType: 'multimodal' as const,
        mode: 'mix' as const,
        multimodalContent: [{ type: 'image', img_path: '/path/to/image.jpg' }],
      };

      const mockJob = { id: 'job-789' } as Job;
      mockQueryQueue.add.mockResolvedValue(mockJob);

      const jobId = await jobQueueService.addQueryProcessingJob(jobData);

      expect(jobId).toBe('job-789');
    });
  });

  describe('processDocumentJob', () => {
    it('should process document job successfully', async () => {
      const mockJob = {
        id: 'job-123',
        data: {
          documentId: 'doc-123',
          userId: 'user-123',
          filePath: '/path/to/file.pdf',
          filename: 'file.pdf',
          options: {},
        },
        updateProgress: jest.fn(),
      } as any;

      mockPythonManager.initialized = true;
      mockPythonManager.processDocument.mockResolvedValue({
        processing_time: 5000,
        metadata: { pages: 10 },
      });
      mockDb.prisma.$executeRaw.mockResolvedValue(1);

      const processor = jobQueueService['processDocumentJob'].bind(jobQueueService);
      const result = await processor(mockJob);

      expect(result.status).toBe('completed');
      expect(mockJob.updateProgress).toHaveBeenCalledWith(10);
      expect(mockJob.updateProgress).toHaveBeenCalledWith(20);
      expect(mockJob.updateProgress).toHaveBeenCalledWith(80);
      expect(mockJob.updateProgress).toHaveBeenCalledWith(100);
      expect(mockPythonManager.processDocument).toHaveBeenCalledWith(
        '/path/to/file.pdf',
        'doc-123',
        {}
      );
    });

    it('should handle document processing errors', async () => {
      const mockJob = {
        id: 'job-123',
        data: {
          documentId: 'doc-123',
          userId: 'user-123',
          filePath: '/path/to/invalid.pdf',
          filename: 'invalid.pdf',
          options: {},
        },
        updateProgress: jest.fn(),
      } as any;

      mockPythonManager.initialized = true;
      mockPythonManager.processDocument.mockRejectedValue(new Error('File not found'));
      mockDb.prisma.$executeRaw.mockResolvedValue(1);

      const processor = jobQueueService['processDocumentJob'].bind(jobQueueService);
      
      await expect(processor(mockJob)).rejects.toThrow('File not found');
      expect(mockDb.prisma.$executeRaw).toHaveBeenCalledWith(
        expect.stringContaining("status = 'failed'")
      );
    });

    it('should initialize Python manager if not initialized', async () => {
      const mockJob = {
        id: 'job-123',
        data: {
          documentId: 'doc-123',
          userId: 'user-123',
          filePath: '/path/to/file.pdf',
          filename: 'file.pdf',
          options: {},
        },
        updateProgress: jest.fn(),
      } as any;

      mockPythonManager.initialized = false;
      mockPythonManager.initialize.mockResolvedValue();
      mockPythonManager.processDocument.mockResolvedValue({
        processing_time: 5000,
        metadata: { pages: 10 },
      });
      mockDb.prisma.$executeRaw.mockResolvedValue(1);

      const processor = jobQueueService['processDocumentJob'].bind(jobQueueService);
      await processor(mockJob);

      expect(mockPythonManager.initialize).toHaveBeenCalled();
    });
  });

  describe('processQueryJob', () => {
    it('should process text query job successfully', async () => {
      const mockJob = {
        id: 'job-456',
        data: {
          queryId: 'query-123',
          userId: 'user-123',
          query: 'What is AI?',
          queryType: 'text',
          mode: 'mix',
          vlmEnhanced: false,
          multimodalContent: [],
          options: {},
        },
        updateProgress: jest.fn(),
      } as any;

      mockPythonManager.initialized = true;
      mockPythonManager.executeQuery.mockResolvedValue({
        answer: 'AI is artificial intelligence',
        sources: [{ doc_id: 'doc-1', score: 0.9 }],
        processing_time: 2000,
      });
      mockDb.prisma.$executeRaw.mockResolvedValue(1);

      const processor = jobQueueService['processQueryJob'].bind(jobQueueService);
      const result = await processor(mockJob);

      expect(result.answer).toBe('AI is artificial intelligence');
      expect(mockPythonManager.executeQuery).toHaveBeenCalledWith(
        'What is AI?',
        'mix',
        false
      );
    });

    it('should process multimodal query job successfully', async () => {
      const mockJob = {
        id: 'job-789',
        data: {
          queryId: 'query-456',
          userId: 'user-123',
          query: 'What is in this image?',
          queryType: 'multimodal',
          mode: 'mix',
          multimodalContent: [{ type: 'image', img_path: '/path/to/image.jpg' }],
          options: {},
        },
        updateProgress: jest.fn(),
      } as any;

      mockPythonManager.initialized = true;
      mockPythonManager.executeMultimodalQuery.mockResolvedValue({
        answer: 'The image shows a cat',
        sources: [{ doc_id: 'doc-2', score: 0.8 }],
        processing_time: 3000,
      });
      mockDb.prisma.$executeRaw.mockResolvedValue(1);

      const processor = jobQueueService['processQueryJob'].bind(jobQueueService);
      const result = await processor(mockJob);

      expect(result.answer).toBe('The image shows a cat');
      expect(mockPythonManager.executeMultimodalQuery).toHaveBeenCalledWith(
        'What is in this image?',
        [{ type: 'image', img_path: '/path/to/image.jpg' }],
        'mix'
      );
    });

    it('should handle query processing errors', async () => {
      const mockJob = {
        id: 'job-fail',
        data: {
          queryId: 'query-fail',
          userId: 'user-123',
          query: 'Invalid query',
          queryType: 'text',
          mode: 'mix',
          vlmEnhanced: false,
          multimodalContent: [],
          options: {},
        },
        updateProgress: jest.fn(),
      } as any;

      mockPythonManager.initialized = true;
      mockPythonManager.executeQuery.mockRejectedValue(new Error('Query failed'));

      const processor = jobQueueService['processQueryJob'].bind(jobQueueService);
      
      await expect(processor(mockJob)).rejects.toThrow('Query failed');
    });
  });

  describe('getJobStatus', () => {
    it('should return job status from database', async () => {
      const mockJobStatus = [{
        status: 'completed',
        progress: 100,
        result: { answer: 'Test result' },
        error_message: null,
      }];

      mockDb.prisma.$queryRaw.mockResolvedValue(mockJobStatus as any);

      const status = await jobQueueService.getJobStatus('job-123');

      expect(status).toEqual({
        status: JobStatus.COMPLETED,
        progress: 100,
        result: { answer: 'Test result' },
        error: undefined,
      });
    });

    it('should return null if job not found', async () => {
      mockDb.prisma.$queryRaw.mockResolvedValue([]);

      const status = await jobQueueService.getJobStatus('nonexistent-job');

      expect(status).toBeNull();
    });

    it('should handle database errors gracefully', async () => {
      mockDb.prisma.$queryRaw.mockRejectedValue(new Error('Database error'));

      const status = await jobQueueService.getJobStatus('job-123');

      expect(status).toBeNull();
    });
  });

  describe('getUserJobs', () => {
    it('should return user jobs with pagination', async () => {
      const mockJobs = [
        {
          job_id: 'job-1',
          job_type: 'query_processing',
          status: 'completed',
          progress: 100,
          result: { answer: 'Result 1' },
          error_message: null,
          created_at: new Date(),
          started_at: new Date(),
          completed_at: new Date(),
        },
        {
          job_id: 'job-2',
          job_type: 'document_processing',
          status: 'processing',
          progress: 50,
          result: null,
          error_message: null,
          created_at: new Date(),
          started_at: new Date(),
          completed_at: null,
        },
      ];

      mockDb.prisma.$queryRaw.mockResolvedValue(mockJobs as any);

      const jobs = await jobQueueService.getUserJobs('user-123');

      expect(jobs).toHaveLength(2);
      expect(jobs[0]).toEqual({
        jobId: 'job-1',
        jobType: 'query_processing',
        status: JobStatus.COMPLETED,
        progress: 100,
        result: { answer: 'Result 1' },
        error: undefined,
        createdAt: expect.any(Date),
        startedAt: expect.any(Date),
        completedAt: expect.any(Date),
      });
    });

    it('should filter jobs by status', async () => {
      mockDb.prisma.$queryRaw.mockResolvedValue([]);

      await jobQueueService.getUserJobs('user-123', { status: JobStatus.COMPLETED });

      expect(mockDb.prisma.$queryRaw).toHaveBeenCalledWith(
        expect.stringContaining("status = $2")
      );
    });

    it('should handle pagination options', async () => {
      mockDb.prisma.$queryRaw.mockResolvedValue([]);

      await jobQueueService.getUserJobs('user-123', {
        limit: 10,
        offset: 20,
      });

      expect(mockDb.prisma.$queryRaw).toHaveBeenCalledWith(
        expect.stringContaining("LIMIT 10 OFFSET 20")
      );
    });

    it('should return empty array on database error', async () => {
      mockDb.prisma.$queryRaw.mockRejectedValue(new Error('Database error'));

      const jobs = await jobQueueService.getUserJobs('user-123');

      expect(jobs).toEqual([]);
    });
  });

  describe('cancelJob', () => {
    it('should cancel job from document queue', async () => {
      const mockJob = {
        remove: jest.fn(),
        progress: 30,
      };
      mockDocumentQueue.getJob.mockResolvedValue(mockJob as any);

      const cancelled = await jobQueueService.cancelJob('job-123');

      expect(cancelled).toBe(true);
      expect(mockJob.remove).toHaveBeenCalled();
    });

    it('should cancel job from query queue', async () => {
      const mockJob = {
        remove: jest.fn(),
        progress: 60,
      };
      mockDocumentQueue.getJob.mockResolvedValue(null);
      mockQueryQueue.getJob.mockResolvedValue(mockJob as any);

      const cancelled = await jobQueueService.cancelJob('job-456');

      expect(cancelled).toBe(true);
      expect(mockJob.remove).toHaveBeenCalled();
    });

    it('should return false if job not found', async () => {
      mockDocumentQueue.getJob.mockResolvedValue(null);
      mockQueryQueue.getJob.mockResolvedValue(null);

      const cancelled = await jobQueueService.cancelJob('nonexistent-job');

      expect(cancelled).toBe(false);
    });

    it('should handle cancellation errors gracefully', async () => {
      mockDocumentQueue.getJob.mockRejectedValue(new Error('Queue error'));

      const cancelled = await jobQueueService.cancelJob('job-123');

      expect(cancelled).toBe(false);
    });
  });

  describe('getQueueStats', () => {
    it('should return queue statistics', async () => {
      const mockDocStats = {
        waiting: 5,
        active: 2,
        completed: 100,
        failed: 3,
      };

      const mockQueryStats = {
        waiting: 10,
        active: 5,
        completed: 200,
        failed: 1,
      };

      mockDocumentQueue.getJobCounts.mockResolvedValue(mockDocStats as any);
      mockQueryQueue.getJobCounts.mockResolvedValue(mockQueryStats as any);

      const stats = await jobQueueService.getQueueStats();

      expect(stats).toEqual({
        documentQueue: mockDocStats,
        queryQueue: mockQueryStats,
      });
    });
  });

  describe('shutdown', () => {
    it('should shutdown all components gracefully', async () => {
      await jobQueueService.shutdown();

      expect(mockDocumentWorker.close).toHaveBeenCalled();
      expect(mockQueryWorker.close).toHaveBeenCalled();
      expect(mockDocumentQueue.close).toHaveBeenCalled();
      expect(mockQueryQueue.close).toHaveBeenCalled();
    });

    it('should handle shutdown errors gracefully', async () => {
      mockDocumentWorker.close.mockRejectedValue(new Error('Shutdown error'));

      // Should not throw
      await jobQueueService.shutdown();

      expect(mockDocumentWorker.close).toHaveBeenCalled();
    });
  });
});