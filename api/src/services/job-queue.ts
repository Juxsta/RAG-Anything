import { Queue, Worker, Job, QueueEvents } from 'bullmq';
import { createClient } from 'redis';
import { EventEmitter } from 'events';
import { config } from '@/config/index.js';
import { logger } from '@/utils/logger.js';
import { pythonProcessManager } from '@/services/python-process-manager.js';
import { db } from '@/services/database.js';

// Job data interfaces
export interface DocumentProcessingJobData {
  documentId: string;
  userId: string;
  filePath: string;
  filename: string;
  options?: Record<string, any>;
}

export interface QueryProcessingJobData {
  queryId: string;
  userId: string;
  query: string;
  queryType: 'text' | 'multimodal';
  mode: 'naive' | 'local' | 'global' | 'hybrid' | 'mix';
  vlmEnhanced?: boolean;
  multimodalContent?: any[];
  options?: Record<string, any>;
}

export interface JobProgressData {
  jobId: string;
  progress: number;
  message?: string;
  data?: any;
}

export interface JobResult {
  jobId: string;
  result: any;
  processingTime: number;
  metadata?: Record<string, any>;
}

// Job status enum
export enum JobStatus {
  PENDING = 'pending',
  ACTIVE = 'active',
  COMPLETED = 'completed',
  FAILED = 'failed',
  DELAYED = 'delayed',
  WAITING = 'waiting',
}

export class JobQueueService extends EventEmitter {
  private documentQueue: Queue<DocumentProcessingJobData>;
  private queryQueue: Queue<QueryProcessingJobData>;
  private documentWorker: Worker<DocumentProcessingJobData>;
  private queryWorker: Worker<QueryProcessingJobData>;
  private queueEvents: QueueEvents;
  private redisConnection: any;

  constructor() {
    super();
    
    // Create Redis connection
    this.redisConnection = createClient({
      url: config.REDIS_URL,
      maxRetriesPerRequest: 3,
      retryDelayOnFailover: 100,
      enableOfflineQueue: false,
    });

    // Initialize queues
    this.documentQueue = new Queue<DocumentProcessingJobData>('document-processing', {
      connection: this.redisConnection,
      defaultJobOptions: {
        removeOnComplete: 100,
        removeOnFail: 50,
        attempts: 3,
        backoff: {
          type: 'exponential',
          delay: 2000,
        },
      },
    });

    this.queryQueue = new Queue<QueryProcessingJobData>('query-processing', {
      connection: this.redisConnection,
      defaultJobOptions: {
        removeOnComplete: 100,
        removeOnFail: 50,
        attempts: 3,
        backoff: {
          type: 'exponential',
          delay: 1000,
        },
      },
    });

    // Initialize workers
    this.documentWorker = new Worker<DocumentProcessingJobData>(
      'document-processing',
      this.processDocumentJob.bind(this),
      {
        connection: this.redisConnection,
        concurrency: 2,
      }
    );

    this.queryWorker = new Worker<QueryProcessingJobData>(
      'query-processing', 
      this.processQueryJob.bind(this),
      {
        connection: this.redisConnection,
        concurrency: 5,
      }
    );

    // Initialize queue events
    this.queueEvents = new QueueEvents('document-processing', {
      connection: this.redisConnection,
    });

    this.setupEventHandlers();
  }

  /**
   * Initialize the job queue service
   */
  async initialize(): Promise<void> {
    try {
      await this.redisConnection.connect();
      logger.info('Job queue service initialized successfully');
    } catch (error) {
      logger.error('Failed to initialize job queue service', error);
      throw error;
    }
  }

  /**
   * Setup event handlers for job progress tracking
   */
  private setupEventHandlers(): void {
    // Document processing events
    this.documentWorker.on('progress', (job: Job, progress: number) => {
      const progressData: JobProgressData = {
        jobId: job.id!,
        progress,
        message: `Processing document: ${progress}%`,
      };
      
      this.emit('jobProgress', progressData);
      this.updateJobStatus(job.id!, JobStatus.ACTIVE, progress);
    });

    this.documentWorker.on('completed', (job: Job, result: any) => {
      const completedData: JobResult = {
        jobId: job.id!,
        result,
        processingTime: job.processedOn! - job.timestamp,
      };
      
      this.emit('jobCompleted', completedData);
      this.updateJobStatus(job.id!, JobStatus.COMPLETED, 100, result);
    });

    this.documentWorker.on('failed', (job: Job, error: Error) => {
      this.emit('jobFailed', {
        jobId: job.id!,
        error: error.message,
      });
      
      this.updateJobStatus(job.id!, JobStatus.FAILED, job.progress || 0, null, error.message);
    });

    // Query processing events
    this.queryWorker.on('progress', (job: Job, progress: number) => {
      const progressData: JobProgressData = {
        jobId: job.id!,
        progress,
        message: `Processing query: ${progress}%`,
      };
      
      this.emit('jobProgress', progressData);
      this.updateJobStatus(job.id!, JobStatus.ACTIVE, progress);
    });

    this.queryWorker.on('completed', (job: Job, result: any) => {
      const completedData: JobResult = {
        jobId: job.id!,
        result,
        processingTime: job.processedOn! - job.timestamp,
      };
      
      this.emit('jobCompleted', completedData);
      this.updateJobStatus(job.id!, JobStatus.COMPLETED, 100, result);
    });

    this.queryWorker.on('failed', (job: Job, error: Error) => {
      this.emit('jobFailed', {
        jobId: job.id!,
        error: error.message,
      });
      
      this.updateJobStatus(job.id!, JobStatus.FAILED, job.progress || 0, null, error.message);
    });
  }

  /**
   * Add document processing job
   */
  async addDocumentProcessingJob(
    data: DocumentProcessingJobData,
    options?: {
      priority?: number;
      delay?: number;
    }
  ): Promise<string> {
    try {
      // Create job status record
      await this.createJobStatus({
        userId: data.userId,
        jobType: 'document_processing',
        jobData: data,
      });

      const job = await this.documentQueue.add('process-document', data, {
        priority: options?.priority,
        delay: options?.delay,
      });

      logger.info('Document processing job added', {
        jobId: job.id,
        documentId: data.documentId,
        userId: data.userId,
      });

      return job.id!;
    } catch (error) {
      logger.error('Failed to add document processing job', error);
      throw error;
    }
  }

  /**
   * Add query processing job
   */
  async addQueryProcessingJob(
    data: QueryProcessingJobData,
    options?: {
      priority?: number;
      delay?: number;
    }
  ): Promise<string> {
    try {
      // Create job status record
      await this.createJobStatus({
        userId: data.userId,
        jobType: 'query_processing',
        jobData: data,
      });

      const job = await this.queryQueue.add('process-query', data, {
        priority: options?.priority,
        delay: options?.delay,
      });

      logger.info('Query processing job added', {
        jobId: job.id,
        queryId: data.queryId,
        userId: data.userId,
      });

      return job.id!;
    } catch (error) {
      logger.error('Failed to add query processing job', error);
      throw error;
    }
  }

  /**
   * Process document job
   */
  private async processDocumentJob(job: Job<DocumentProcessingJobData>): Promise<any> {
    const { documentId, userId, filePath, filename, options = {} } = job.data;
    
    logger.info('Starting document processing', {
      jobId: job.id,
      documentId,
      filename,
    });

    try {
      // Update progress: 10%
      await job.updateProgress(10);

      // Initialize Python process if needed
      if (!pythonProcessManager.initialized) {
        await pythonProcessManager.initialize();
      }

      // Update progress: 20%
      await job.updateProgress(20);

      // Process document using Python RAG-Anything
      const result = await pythonProcessManager.processDocument(
        filePath,
        documentId,
        options
      );

      // Update progress: 80%
      await job.updateProgress(80);

      // Update document status in database
      await db.prisma.$executeRaw`
        UPDATE documents 
        SET status = 'processed',
            processing_metadata = ${JSON.stringify(result.metadata || {})},
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ${documentId}::uuid
      `;

      // Update progress: 100%
      await job.updateProgress(100);

      logger.info('Document processing completed', {
        jobId: job.id,
        documentId,
        processingTime: result.processing_time,
      });

      return {
        documentId,
        status: 'completed',
        result: result,
        processingTime: result.processing_time,
      };

    } catch (error) {
      logger.error('Document processing failed', {
        jobId: job.id,
        documentId,
        error: error.message,
      });

      // Update document status to failed
      await db.prisma.$executeRaw`
        UPDATE documents 
        SET status = 'failed',
            processing_metadata = ${JSON.stringify({ error: error.message })},
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ${documentId}::uuid
      `;

      throw error;
    }
  }

  /**
   * Process query job
   */
  private async processQueryJob(job: Job<QueryProcessingJobData>): Promise<any> {
    const { queryId, userId, query, queryType, mode, vlmEnhanced = false, multimodalContent = [], options = {} } = job.data;
    
    logger.info('Starting query processing', {
      jobId: job.id,
      queryId,
      queryType,
      mode,
    });

    try {
      // Update progress: 10%
      await job.updateProgress(10);

      // Initialize Python process if needed
      if (!pythonProcessManager.initialized) {
        await pythonProcessManager.initialize();
      }

      // Update progress: 30%
      await job.updateProgress(30);

      let result: any;

      if (queryType === 'multimodal' && multimodalContent.length > 0) {
        // Process multimodal query
        result = await pythonProcessManager.executeMultimodalQuery(
          query,
          multimodalContent,
          mode
        );
      } else {
        // Process text query
        result = await pythonProcessManager.executeQuery(query, mode, vlmEnhanced);
      }

      // Update progress: 80%
      await job.updateProgress(80);

      // Store query result in database
      await db.prisma.$executeRaw`
        INSERT INTO queries (
          id, user_id, query_text, query_type, mode, 
          result_text, sources, metadata, processing_time_ms
        )
        VALUES (
          ${queryId}::uuid,
          ${userId}::uuid,
          ${query},
          ${queryType},
          ${mode},
          ${result.answer || ''},
          ${JSON.stringify(result.sources || [])},
          ${JSON.stringify(result.metadata || {})},
          ${result.processing_time || 0}
        )
        ON CONFLICT (id) DO UPDATE SET
          result_text = EXCLUDED.result_text,
          sources = EXCLUDED.sources,
          metadata = EXCLUDED.metadata,
          processing_time_ms = EXCLUDED.processing_time_ms
      `;

      // Update progress: 100%
      await job.updateProgress(100);

      logger.info('Query processing completed', {
        jobId: job.id,
        queryId,
        processingTime: result.processing_time,
      });

      return {
        queryId,
        query,
        answer: result.answer,
        sources: result.sources,
        metadata: result.metadata,
        processingTime: result.processing_time,
      };

    } catch (error) {
      logger.error('Query processing failed', {
        jobId: job.id,
        queryId,
        error: error.message,
      });

      throw error;
    }
  }

  /**
   * Get job status
   */
  async getJobStatus(jobId: string): Promise<{
    status: JobStatus;
    progress: number;
    result?: any;
    error?: string;
  } | null> {
    try {
      const jobStatus = await db.prisma.$queryRaw<Array<{
        status: string;
        progress: number;
        result: any;
        error_message: string | null;
      }>>`
        SELECT status, progress, result, error_message
        FROM job_status
        WHERE job_id = ${jobId}
      `;

      if (!jobStatus || jobStatus.length === 0) {
        return null;
      }

      const status = jobStatus[0];
      return {
        status: status.status as JobStatus,
        progress: status.progress,
        result: status.result,
        error: status.error_message || undefined,
      };

    } catch (error) {
      logger.error('Failed to get job status', { jobId, error });
      return null;
    }
  }

  /**
   * Get user's jobs
   */
  async getUserJobs(
    userId: string,
    options: {
      limit?: number;
      offset?: number;
      status?: JobStatus;
    } = {}
  ): Promise<Array<{
    jobId: string;
    jobType: string;
    status: JobStatus;
    progress: number;
    result?: any;
    error?: string;
    createdAt: Date;
    startedAt?: Date;
    completedAt?: Date;
  }>> {
    try {
      const { limit = 50, offset = 0, status } = options;
      
      const whereClause = status 
        ? `WHERE user_id = $1::uuid AND status = $2`
        : `WHERE user_id = $1::uuid`;
      
      const params = status ? [userId, status] : [userId];

      const jobs = await db.prisma.$queryRaw<Array<{
        job_id: string;
        job_type: string;
        status: string;
        progress: number;
        result: any;
        error_message: string | null;
        created_at: Date;
        started_at: Date | null;
        completed_at: Date | null;
      }>>`
        SELECT job_id, job_type, status, progress, result, error_message,
               created_at, started_at, completed_at
        FROM job_status
        ${whereClause}
        ORDER BY created_at DESC
        LIMIT ${limit} OFFSET ${offset}
      `;

      return jobs.map(job => ({
        jobId: job.job_id,
        jobType: job.job_type,
        status: job.status as JobStatus,
        progress: job.progress,
        result: job.result,
        error: job.error_message || undefined,
        createdAt: job.created_at,
        startedAt: job.started_at || undefined,
        completedAt: job.completed_at || undefined,
      }));

    } catch (error) {
      logger.error('Failed to get user jobs', { userId, error });
      return [];
    }
  }

  /**
   * Cancel job
   */
  async cancelJob(jobId: string): Promise<boolean> {
    try {
      // Try to remove from document queue
      const docJob = await this.documentQueue.getJob(jobId);
      if (docJob) {
        await docJob.remove();
        await this.updateJobStatus(jobId, JobStatus.FAILED, docJob.progress || 0, null, 'Cancelled by user');
        return true;
      }

      // Try to remove from query queue
      const queryJob = await this.queryQueue.getJob(jobId);
      if (queryJob) {
        await queryJob.remove();
        await this.updateJobStatus(jobId, JobStatus.FAILED, queryJob.progress || 0, null, 'Cancelled by user');
        return true;
      }

      return false;
    } catch (error) {
      logger.error('Failed to cancel job', { jobId, error });
      return false;
    }
  }

  /**
   * Create job status record in database
   */
  private async createJobStatus(data: {
    userId: string;
    jobType: string;
    jobData: any;
  }): Promise<void> {
    const jobId = `${data.jobType}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    await db.prisma.$executeRaw`
      INSERT INTO job_status (job_id, user_id, job_type, status, progress)
      VALUES (${jobId}, ${data.userId}::uuid, ${data.jobType}, ${JobStatus.PENDING}, 0)
    `;
  }

  /**
   * Update job status in database
   */
  private async updateJobStatus(
    jobId: string,
    status: JobStatus,
    progress: number,
    result?: any,
    errorMessage?: string
  ): Promise<void> {
    try {
      const now = new Date();
      
      if (status === JobStatus.ACTIVE) {
        await db.prisma.$executeRaw`
          UPDATE job_status
          SET status = ${status},
              progress = ${progress},
              started_at = COALESCE(started_at, ${now})
          WHERE job_id = ${jobId}
        `;
      } else if (status === JobStatus.COMPLETED || status === JobStatus.FAILED) {
        await db.prisma.$executeRaw`
          UPDATE job_status
          SET status = ${status},
              progress = ${progress},
              result = ${result ? JSON.stringify(result) : null},
              error_message = ${errorMessage || null},
              completed_at = ${now}
          WHERE job_id = ${jobId}
        `;
      } else {
        await db.prisma.$executeRaw`
          UPDATE job_status
          SET status = ${status},
              progress = ${progress}
          WHERE job_id = ${jobId}
        `;
      }
    } catch (error) {
      logger.error('Failed to update job status', { jobId, status, error });
    }
  }

  /**
   * Get queue statistics
   */
  async getQueueStats(): Promise<{
    documentQueue: {
      waiting: number;
      active: number;
      completed: number;
      failed: number;
    };
    queryQueue: {
      waiting: number;
      active: number;
      completed: number;
      failed: number;
    };
  }> {
    const [docStats, queryStats] = await Promise.all([
      this.documentQueue.getJobCounts(),
      this.queryQueue.getJobCounts(),
    ]);

    return {
      documentQueue: {
        waiting: docStats.waiting,
        active: docStats.active,
        completed: docStats.completed,
        failed: docStats.failed,
      },
      queryQueue: {
        waiting: queryStats.waiting,
        active: queryStats.active,
        completed: queryStats.completed,
        failed: queryStats.failed,
      },
    };
  }

  /**
   * Cleanup and shutdown
   */
  async shutdown(): Promise<void> {
    try {
      await this.documentWorker.close();
      await this.queryWorker.close();
      await this.documentQueue.close();
      await this.queryQueue.close();
      await this.queueEvents.close();
      await this.redisConnection.quit();
      
      logger.info('Job queue service shutdown completed');
    } catch (error) {
      logger.error('Error during job queue shutdown', error);
    }
  }
}

// Singleton instance
export const jobQueueService = new JobQueueService();