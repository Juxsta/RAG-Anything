import { Server as SocketIOServer } from 'socket.io';
import { createAdapter } from '@socket.io/redis-adapter';
import { createClient } from 'redis';
import { Server } from 'http';
import { authService } from '@/services/auth.js';
import { db } from '@/services/database.js';
import { config } from '@/config/index.js';
import { logger } from '@/utils/logger.js';
import { AuthUser } from '@/types/auth.js';

export interface AuthenticatedSocket {
  id: string;
  user: AuthUser;
  join(room: string): void;
  leave(room: string): void;
  emit(event: string, data: any): void;
  disconnect(close?: boolean): void;
  rooms: Set<string>;
}

export interface WebSocketEvents {
  // Client to server events
  'query:subscribe': (queryId: string) => void;
  'query:unsubscribe': (queryId: string) => void;
  'job:subscribe': (jobId: string) => void;
  'job:unsubscribe': (jobId: string) => void;
  'system:subscribe': () => void;
  'system:unsubscribe': () => void;
  
  // Server to client events
  'query:progress': (data: { queryId: string; progress: number; message?: string }) => void;
  'query:completed': (data: { queryId: string; result: any }) => void;
  'query:failed': (data: { queryId: string; error: string }) => void;
  'job:progress': (data: { jobId: string; progress: number; message?: string }) => void;
  'job:completed': (data: { jobId: string; result: any }) => void;
  'job:failed': (data: { jobId: string; error: string }) => void;
  'system:status': (data: { status: string; message: string }) => void;
  'error': (data: { message: string; code?: string }) => void;
  'authenticated': (data: { userId: string; email: string }) => void;
}

export class WebSocketService {
  private io: SocketIOServer;
  private pubClient: any;
  private subClient: any;
  private connectedUsers: Map<string, Set<string>> = new Map(); // userId -> Set of socketIds
  private socketUsers: Map<string, AuthUser> = new Map(); // socketId -> user
  
  constructor(server: Server) {
    this.io = new SocketIOServer(server, {
      cors: {
        origin: config.ALLOWED_ORIGINS?.split(',') || ['http://localhost:3000'],
        credentials: true,
        methods: ['GET', 'POST'],
      },
      transports: ['websocket', 'polling'],
      pingTimeout: 60000,
      pingInterval: 25000,
    });

    this.initialize();
  }

  /**
   * Initialize WebSocket service
   */
  private async initialize(): Promise<void> {
    try {
      await this.setupRedisAdapter();
      this.setupMiddleware();
      this.setupEventHandlers();
      this.setupJobQueueListeners();
      
      logger.info('WebSocket service initialized successfully');
    } catch (error) {
      logger.error('Failed to initialize WebSocket service', error);
      throw error;
    }
  }

  /**
   * Setup Redis adapter for horizontal scaling
   */
  private async setupRedisAdapter(): Promise<void> {
    try {
      this.pubClient = createClient({ url: config.REDIS_URL });
      this.subClient = this.pubClient.duplicate();

      await Promise.all([
        this.pubClient.connect(),
        this.subClient.connect(),
      ]);

      this.io.adapter(createAdapter(this.pubClient, this.subClient));
      
      logger.info('WebSocket Redis adapter initialized');
    } catch (error) {
      logger.warn('Failed to setup WebSocket Redis adapter, using memory adapter', error);
    }
  }

  /**
   * Setup authentication middleware
   */
  private setupMiddleware(): void {
    this.io.use(async (socket: any, next) => {
      try {
        const token = socket.handshake.auth?.token || socket.handshake.headers?.authorization?.replace('Bearer ', '');
        const apiKey = socket.handshake.auth?.apiKey || socket.handshake.headers?.['x-api-key'];

        let user: AuthUser | null = null;

        if (token) {
          user = await authService.validateJWT(token);
        } else if (apiKey) {
          user = await authService.validateAPIKey(apiKey);
        }

        if (!user) {
          return next(new Error('Authentication failed'));
        }

        socket.user = user;
        next();
      } catch (error) {
        logger.warn('WebSocket authentication failed', {
          socketId: socket.id,
          error: error.message,
        });
        next(new Error('Authentication failed'));
      }
    });

    // Rate limiting middleware
    this.io.use((socket: any, next) => {
      const rateLimiter = new Map();
      const RATE_LIMIT = 100; // messages per minute
      const WINDOW = 60 * 1000; // 1 minute

      socket.on('*', () => {
        const now = Date.now();
        const windowStart = now - WINDOW;
        
        if (!rateLimiter.has(socket.user.id)) {
          rateLimiter.set(socket.user.id, []);
        }
        
        const requests = rateLimiter.get(socket.user.id);
        
        // Remove old requests
        while (requests.length > 0 && requests[0] < windowStart) {
          requests.shift();
        }
        
        if (requests.length >= RATE_LIMIT) {
          socket.emit('error', {
            message: 'Rate limit exceeded',
            code: 'RATE_LIMIT_EXCEEDED',
          });
          return;
        }
        
        requests.push(now);
      });
      
      next();
    });
  }

  /**
   * Setup main event handlers
   */
  private setupEventHandlers(): void {
    this.io.on('connection', (socket: any) => {
      const user = socket.user as AuthUser;
      
      logger.info('WebSocket client connected', {
        socketId: socket.id,
        userId: user.id,
        email: user.email,
      });

      // Track connected user
      this.addConnectedUser(user.id, socket.id);
      this.socketUsers.set(socket.id, user);

      // Join user-specific room
      socket.join(`user:${user.id}`);

      // Send authentication confirmation
      socket.emit('authenticated', {
        userId: user.id,
        email: user.email,
      });

      // Query subscription handlers
      socket.on('query:subscribe', (queryId: string) => {
        if (this.validateQueryAccess(user, queryId)) {
          socket.join(`query:${queryId}`);
          logger.debug('User subscribed to query updates', {
            userId: user.id,
            queryId,
            socketId: socket.id,
          });
        } else {
          socket.emit('error', {
            message: 'Access denied to query',
            code: 'QUERY_ACCESS_DENIED',
          });
        }
      });

      socket.on('query:unsubscribe', (queryId: string) => {
        socket.leave(`query:${queryId}`);
        logger.debug('User unsubscribed from query updates', {
          userId: user.id,
          queryId,
          socketId: socket.id,
        });
      });

      // Job subscription handlers
      socket.on('job:subscribe', (jobId: string) => {
        if (this.validateJobAccess(user, jobId)) {
          socket.join(`job:${jobId}`);
          logger.debug('User subscribed to job updates', {
            userId: user.id,
            jobId,
            socketId: socket.id,
          });
        } else {
          socket.emit('error', {
            message: 'Access denied to job',
            code: 'JOB_ACCESS_DENIED',
          });
        }
      });

      socket.on('job:unsubscribe', (jobId: string) => {
        socket.leave(`job:${jobId}`);
        logger.debug('User unsubscribed from job updates', {
          userId: user.id,
          jobId,
          socketId: socket.id,
        });
      });

      // System updates subscription (admin only)
      socket.on('system:subscribe', () => {
        if (user.role === 'admin') {
          socket.join('system:updates');
          logger.debug('Admin subscribed to system updates', {
            userId: user.id,
            socketId: socket.id,
          });
        } else {
          socket.emit('error', {
            message: 'Admin access required',
            code: 'ADMIN_ACCESS_REQUIRED',
          });
        }
      });

      socket.on('system:unsubscribe', () => {
        socket.leave('system:updates');
        logger.debug('User unsubscribed from system updates', {
          userId: user.id,
          socketId: socket.id,
        });
      });

      // Disconnect handler
      socket.on('disconnect', (reason: string) => {
        logger.info('WebSocket client disconnected', {
          socketId: socket.id,
          userId: user.id,
          reason,
        });

        this.removeConnectedUser(user.id, socket.id);
        this.socketUsers.delete(socket.id);
      });

      // Error handler
      socket.on('error', (error: Error) => {
        logger.error('WebSocket error', {
          socketId: socket.id,
          userId: user.id,
          error: error.message,
        });
      });
    });
  }

  /**
   * Setup job queue event listeners
   */
  private setupJobQueueListeners(): void {
    // This will be connected after job queue service is available
  }

  /**
   * Validate query access for user
   */
  private async validateQueryAccess(user: AuthUser, queryId: string): Promise<boolean> {
    try {
      // Admin can access all queries
      if (user.role === 'admin') {
        return true;
      }

      // Check if user owns the query
      const result = await db.prisma.$queryRaw<Array<{ user_id: string }>>`
        SELECT user_id FROM queries WHERE id = ${queryId}::uuid LIMIT 1
      `;

      return result.length > 0 && result[0].user_id === user.id;
    } catch (error) {
      logger.error('Failed to validate query access', { userId: user.id, queryId, error });
      return false;
    }
  }

  /**
   * Validate job access for user
   */
  private async validateJobAccess(user: AuthUser, jobId: string): Promise<boolean> {
    try {
      // Admin can access all jobs
      if (user.role === 'admin') {
        return true;
      }

      // Check if user owns the job
      const result = await db.prisma.$queryRaw<Array<{ user_id: string }>>`
        SELECT user_id FROM job_status WHERE job_id = ${jobId} LIMIT 1
      `;

      return result.length > 0 && result[0].user_id === user.id;
    } catch (error) {
      logger.error('Failed to validate job access', { userId: user.id, jobId, error });
      return false;
    }
  }

  /**
   * Emit event to job owner
   */
  private async emitToJobOwner(jobId: string, event: string, data: any): Promise<void> {
    try {
      const result = await db.prisma.$queryRaw<Array<{ user_id: string }>>`
        SELECT user_id FROM job_status WHERE job_id = ${jobId} LIMIT 1
      `;

      if (result.length > 0) {
        const userId = result[0].user_id;
        this.io.to(`user:${userId}`).emit(event, data);
      }
    } catch (error) {
      logger.error('Failed to emit to job owner', { jobId, event, error });
    }
  }

  /**
   * Track connected user
   */
  private addConnectedUser(userId: string, socketId: string): void {
    if (!this.connectedUsers.has(userId)) {
      this.connectedUsers.set(userId, new Set());
    }
    this.connectedUsers.get(userId)!.add(socketId);
  }

  /**
   * Remove connected user
   */
  private removeConnectedUser(userId: string, socketId: string): void {
    const userSockets = this.connectedUsers.get(userId);
    if (userSockets) {
      userSockets.delete(socketId);
      if (userSockets.size === 0) {
        this.connectedUsers.delete(userId);
      }
    }
  }

  /**
   * Check if user is connected
   */
  public isUserConnected(userId: string): boolean {
    return this.connectedUsers.has(userId) && this.connectedUsers.get(userId)!.size > 0;
  }

  /**
   * Get connected user count
   */
  public getConnectedUserCount(): number {
    return this.connectedUsers.size;
  }

  /**
   * Get total socket count
   */
  public getTotalSocketCount(): number {
    return this.socketUsers.size;
  }

  /**
   * Broadcast system status to all connected admins
   */
  public broadcastSystemStatus(status: string, message: string): void {
    this.io.to('system:updates').emit('system:status', { status, message });
  }

  /**
   * Send notification to user
   */
  public notifyUser(userId: string, event: string, data: any): void {
    this.io.to(`user:${userId}`).emit(event, data);
  }

  /**
   * Send notification to all connected users
   */
  public broadcast(event: string, data: any): void {
    this.io.emit(event, data);
  }

  /**
   * Server-Sent Events endpoint handler
   */
  public createSSEHandler() {
    return async (request: any, reply: any) => {
      const { jobId, queryId } = request.params;
      const user = request.user as AuthUser;

      if (!user) {
        return reply.code(401).send({ error: 'Authentication required' });
      }

      // Validate access
      if (jobId && !(await this.validateJobAccess(user, jobId))) {
        return reply.code(403).send({ error: 'Access denied' });
      }

      if (queryId && !(await this.validateQueryAccess(user, queryId))) {
        return reply.code(403).send({ error: 'Access denied' });
      }

      // Setup SSE headers
      reply.raw.writeHead(200, {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Cache-Control',
      });

      const sendEvent = (event: string, data: any) => {
        reply.raw.write(`event: ${event}\n`);
        reply.raw.write(`data: ${JSON.stringify(data)}\n\n`);
      };

      // Send connection confirmation
      sendEvent('connected', { 
        timestamp: Date.now(),
        jobId: jobId || null,
        queryId: queryId || null,
      });

      // Setup event listeners will be implemented with job queue integration
      // For now, just send periodic updates
      const updateInterval = setInterval(async () => {
        try {
          if (jobId) {
            // Get job status from database instead of queue service for now
            const status = await db.prisma.$queryRaw<Array<{
              status: string;
              progress: number;
              result: any;
              error_message: string | null;
            }>>`
              SELECT status, progress, result, error_message
              FROM job_status
              WHERE job_id = ${jobId}
            `;

            if (status.length > 0) {
              const jobStatus = status[0];
              sendEvent('status', {
                jobId,
                status: jobStatus.status,
                progress: jobStatus.progress,
                result: jobStatus.result,
                error: jobStatus.error_message,
              });

              if (jobStatus.status === 'completed' || jobStatus.status === 'failed') {
                clearInterval(updateInterval);
                return;
              }
            }
          }
        } catch (error) {
          logger.error('SSE update error', { error });
        }
      }, 2000);

      // Cleanup on disconnect
      request.raw.on('close', () => {
        clearInterval(updateInterval);
      });

      // Keep connection alive
      const keepAlive = setInterval(() => {
        sendEvent('ping', { timestamp: Date.now() });
      }, 30000);

      request.raw.on('close', () => {
        clearInterval(keepAlive);
      });
    };
  }

  /**
   * Shutdown WebSocket service
   */
  async shutdown(): Promise<void> {
    try {
      this.io.close();
      
      if (this.pubClient) {
        await this.pubClient.quit();
      }
      
      if (this.subClient) {
        await this.subClient.quit();
      }
      
      logger.info('WebSocket service shutdown completed');
    } catch (error) {
      logger.error('Error during WebSocket shutdown', error);
    }
  }
}

export default WebSocketService;