import { Server as SocketIOServer } from 'socket.io';
import { createClient } from 'redis';
import { Server } from 'http';
import WebSocketService from '@/services/websocket';
import { authService } from '@/services/auth';
import { db } from '@/services/database';

// Mock dependencies
jest.mock('socket.io');
jest.mock('redis');
jest.mock('@/services/auth');
jest.mock('@/services/database');

const mockSocketIOServer = SocketIOServer as jest.MockedClass<typeof SocketIOServer>;
const mockCreateClient = createClient as jest.MockedFunction<typeof createClient>;
const mockAuthService = authService as jest.Mocked<typeof authService>;
const mockDb = db as jest.Mocked<typeof db>;

describe('WebSocketService', () => {
  let webSocketService: WebSocketService;
  let mockServer: Server;
  let mockIO: jest.Mocked<SocketIOServer>;
  let mockRedisClient: any;

  beforeEach(() => {
    jest.clearAllMocks();

    mockServer = {} as Server;
    
    // Mock Socket.IO server
    mockIO = {
      use: jest.fn(),
      on: jest.fn(),
      to: jest.fn().mockReturnThis(),
      emit: jest.fn(),
      adapter: jest.fn(),
      close: jest.fn(),
    } as any;

    mockSocketIOServer.mockImplementation(() => mockIO);

    // Mock Redis client
    mockRedisClient = {
      connect: jest.fn(),
      duplicate: jest.fn().mockReturnThis(),
      quit: jest.fn(),
    };
    mockCreateClient.mockReturnValue(mockRedisClient);

    webSocketService = new WebSocketService(mockServer);
  });

  afterEach(() => {
    jest.resetAllMocks();
  });

  describe('constructor', () => {
    it('should initialize Socket.IO server with correct configuration', () => {
      expect(mockSocketIOServer).toHaveBeenCalledWith(mockServer, expect.objectContaining({
        cors: expect.objectContaining({
          credentials: true,
          methods: ['GET', 'POST'],
        }),
        transports: ['websocket', 'polling'],
        pingTimeout: 60000,
        pingInterval: 25000,
      }));
    });

    it('should setup middleware for authentication', () => {
      expect(mockIO.use).toHaveBeenCalled();
    });

    it('should setup connection event handlers', () => {
      expect(mockIO.on).toHaveBeenCalledWith('connection', expect.any(Function));
    });
  });

  describe('authentication middleware', () => {
    let authMiddleware: Function;

    beforeEach(() => {
      const useCalls = (mockIO.use as jest.Mock).mock.calls;
      authMiddleware = useCalls[0][0]; // First middleware call
    });

    it('should authenticate with valid JWT token', async () => {
      const mockSocket = {
        handshake: {
          auth: { token: 'valid-jwt-token' },
          headers: {},
        },
      };

      const mockUser = {
        id: 'user-123',
        email: 'test@example.com',
        role: 'user',
        apiKey: false,
      };

      mockAuthService.validateJWT.mockResolvedValue(mockUser);

      const next = jest.fn();
      await authMiddleware(mockSocket, next);

      expect(mockSocket.user).toEqual(mockUser);
      expect(next).toHaveBeenCalledWith();
    });

    it('should authenticate with valid API key', async () => {
      const mockSocket = {
        handshake: {
          auth: { apiKey: 'valid-api-key' },
          headers: {},
        },
      };

      const mockUser = {
        id: 'user-456',
        email: 'api@example.com',
        role: 'user',
        apiKey: true,
      };

      mockAuthService.validateJWT.mockResolvedValue(null);
      mockAuthService.validateAPIKey.mockResolvedValue(mockUser);

      const next = jest.fn();
      await authMiddleware(mockSocket, next);

      expect(mockSocket.user).toEqual(mockUser);
      expect(next).toHaveBeenCalledWith();
    });

    it('should reject authentication without token or API key', async () => {
      const mockSocket = {
        handshake: {
          auth: {},
          headers: {},
        },
      };

      mockAuthService.validateJWT.mockResolvedValue(null);
      mockAuthService.validateAPIKey.mockResolvedValue(null);

      const next = jest.fn();
      await authMiddleware(mockSocket, next);

      expect(next).toHaveBeenCalledWith(expect.any(Error));
    });

    it('should use authorization header as fallback for JWT', async () => {
      const mockSocket = {
        handshake: {
          auth: {},
          headers: { authorization: 'Bearer jwt-from-header' },
        },
      };

      const mockUser = {
        id: 'user-789',
        email: 'header@example.com',
        role: 'user',
        apiKey: false,
      };

      mockAuthService.validateJWT.mockResolvedValue(mockUser);

      const next = jest.fn();
      await authMiddleware(mockSocket, next);

      expect(mockAuthService.validateJWT).toHaveBeenCalledWith('jwt-from-header');
      expect(mockSocket.user).toEqual(mockUser);
    });

    it('should use x-api-key header as fallback for API key', async () => {
      const mockSocket = {
        handshake: {
          auth: {},
          headers: { 'x-api-key': 'api-key-from-header' },
        },
      };

      const mockUser = {
        id: 'user-api',
        email: 'apikey@example.com',
        role: 'user',
        apiKey: true,
      };

      mockAuthService.validateJWT.mockResolvedValue(null);
      mockAuthService.validateAPIKey.mockResolvedValue(mockUser);

      const next = jest.fn();
      await authMiddleware(mockSocket, next);

      expect(mockAuthService.validateAPIKey).toHaveBeenCalledWith('api-key-from-header');
      expect(mockSocket.user).toEqual(mockUser);
    });
  });

  describe('connection management', () => {
    it('should track connected users', () => {
      webSocketService['addConnectedUser']('user-123', 'socket-1');
      webSocketService['addConnectedUser']('user-123', 'socket-2');
      webSocketService['addConnectedUser']('user-456', 'socket-3');

      expect(webSocketService.isUserConnected('user-123')).toBe(true);
      expect(webSocketService.isUserConnected('user-456')).toBe(true);
      expect(webSocketService.isUserConnected('user-789')).toBe(false);
      
      expect(webSocketService.getConnectedUserCount()).toBe(2);
      expect(webSocketService.getTotalSocketCount()).toBe(0); // No sockets in socketUsers map yet
    });

    it('should remove connected users', () => {
      webSocketService['addConnectedUser']('user-123', 'socket-1');
      webSocketService['addConnectedUser']('user-123', 'socket-2');
      
      webSocketService['removeConnectedUser']('user-123', 'socket-1');
      expect(webSocketService.isUserConnected('user-123')).toBe(true); // Still has socket-2
      
      webSocketService['removeConnectedUser']('user-123', 'socket-2');
      expect(webSocketService.isUserConnected('user-123')).toBe(false); // No more sockets
    });
  });

  describe('access validation', () => {
    it('should validate query access for admin users', async () => {
      const adminUser = {
        id: 'admin-1',
        email: 'admin@example.com',
        role: 'admin' as const,
        apiKey: false,
      };

      const hasAccess = await webSocketService['validateQueryAccess'](adminUser, 'query-123');
      expect(hasAccess).toBe(true);
    });

    it('should validate query access for query owner', async () => {
      const user = {
        id: 'user-123',
        email: 'user@example.com',
        role: 'user' as const,
        apiKey: false,
      };

      const mockQueryData = [{ user_id: 'user-123' }];
      mockDb.prisma.$queryRaw.mockResolvedValue(mockQueryData as any);

      const hasAccess = await webSocketService['validateQueryAccess'](user, 'query-123');
      expect(hasAccess).toBe(true);
    });

    it('should deny query access for non-owner', async () => {
      const user = {
        id: 'user-123',
        email: 'user@example.com',
        role: 'user' as const,
        apiKey: false,
      };

      const mockQueryData = [{ user_id: 'other-user' }];
      mockDb.prisma.$queryRaw.mockResolvedValue(mockQueryData as any);

      const hasAccess = await webSocketService['validateQueryAccess'](user, 'query-123');
      expect(hasAccess).toBe(false);
    });

    it('should deny query access for non-existent query', async () => {
      const user = {
        id: 'user-123',
        email: 'user@example.com',
        role: 'user' as const,
        apiKey: false,
      };

      mockDb.prisma.$queryRaw.mockResolvedValue([]);

      const hasAccess = await webSocketService['validateQueryAccess'](user, 'nonexistent-query');
      expect(hasAccess).toBe(false);
    });

    it('should handle database errors in query access validation', async () => {
      const user = {
        id: 'user-123',
        email: 'user@example.com',
        role: 'user' as const,
        apiKey: false,
      };

      mockDb.prisma.$queryRaw.mockRejectedValue(new Error('Database error'));

      const hasAccess = await webSocketService['validateQueryAccess'](user, 'query-123');
      expect(hasAccess).toBe(false);
    });
  });

  describe('job access validation', () => {
    it('should validate job access for admin users', async () => {
      const adminUser = {
        id: 'admin-1',
        email: 'admin@example.com',
        role: 'admin' as const,
        apiKey: false,
      };

      const hasAccess = await webSocketService['validateJobAccess'](adminUser, 'job-123');
      expect(hasAccess).toBe(true);
    });

    it('should validate job access for job owner', async () => {
      const user = {
        id: 'user-123',
        email: 'user@example.com',
        role: 'user' as const,
        apiKey: false,
      };

      const mockJobData = [{ user_id: 'user-123' }];
      mockDb.prisma.$queryRaw.mockResolvedValue(mockJobData as any);

      const hasAccess = await webSocketService['validateJobAccess'](user, 'job-123');
      expect(hasAccess).toBe(true);
    });

    it('should deny job access for non-owner', async () => {
      const user = {
        id: 'user-123',
        email: 'user@example.com',
        role: 'user' as const,
        apiKey: false,
      };

      const mockJobData = [{ user_id: 'other-user' }];
      mockDb.prisma.$queryRaw.mockResolvedValue(mockJobData as any);

      const hasAccess = await webSocketService['validateJobAccess'](user, 'job-123');
      expect(hasAccess).toBe(false);
    });
  });

  describe('broadcasting methods', () => {
    it('should broadcast system status to admins', () => {
      webSocketService.broadcastSystemStatus('healthy', 'All systems operational');

      expect(mockIO.to).toHaveBeenCalledWith('system:updates');
      expect(mockIO.emit).toHaveBeenCalledWith('system:status', {
        status: 'healthy',
        message: 'All systems operational',
      });
    });

    it('should notify specific user', () => {
      webSocketService.notifyUser('user-123', 'notification', { message: 'Hello' });

      expect(mockIO.to).toHaveBeenCalledWith('user:user-123');
      expect(mockIO.emit).toHaveBeenCalledWith('notification', { message: 'Hello' });
    });

    it('should broadcast to all users', () => {
      webSocketService.broadcast('announcement', { message: 'Server maintenance' });

      expect(mockIO.emit).toHaveBeenCalledWith('announcement', { message: 'Server maintenance' });
    });
  });

  describe('SSE handler', () => {
    it('should create SSE handler function', () => {
      const handler = webSocketService.createSSEHandler();
      expect(typeof handler).toBe('function');
    });

    it('should handle SSE connection', async () => {
      const handler = webSocketService.createSSEHandler();
      
      const mockRequest = {
        params: { jobId: 'job-123' },
        user: {
          id: 'user-123',
          email: 'test@example.com',
          role: 'user',
          apiKey: false,
        },
        raw: {
          on: jest.fn(),
        },
      };

      const mockReply = {
        raw: {
          writeHead: jest.fn(),
          write: jest.fn(),
        },
        code: jest.fn().mockReturnThis(),
        send: jest.fn(),
      };

      mockDb.prisma.$queryRaw.mockResolvedValue([{ user_id: 'user-123' }]);

      await handler(mockRequest as any, mockReply as any);

      expect(mockReply.raw.writeHead).toHaveBeenCalledWith(200, expect.objectContaining({
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
      }));
    });

    it('should deny SSE access without authentication', async () => {
      const handler = webSocketService.createSSEHandler();
      
      const mockRequest = {
        params: { jobId: 'job-123' },
        // No user property
      };

      const mockReply = {
        code: jest.fn().mockReturnThis(),
        send: jest.fn(),
      };

      await handler(mockRequest as any, mockReply as any);

      expect(mockReply.code).toHaveBeenCalledWith(401);
      expect(mockReply.send).toHaveBeenCalledWith({ error: 'Authentication required' });
    });

    it('should deny SSE access for unauthorized jobs', async () => {
      const handler = webSocketService.createSSEHandler();
      
      const mockRequest = {
        params: { jobId: 'job-123' },
        user: {
          id: 'user-123',
          email: 'test@example.com',
          role: 'user',
          apiKey: false,
        },
      };

      const mockReply = {
        code: jest.fn().mockReturnThis(),
        send: jest.fn(),
      };

      // Mock job access validation to return false
      mockDb.prisma.$queryRaw.mockResolvedValue([{ user_id: 'other-user' }]);

      await handler(mockRequest as any, mockReply as any);

      expect(mockReply.code).toHaveBeenCalledWith(403);
      expect(mockReply.send).toHaveBeenCalledWith({ error: 'Access denied' });
    });
  });

  describe('shutdown', () => {
    it('should shutdown gracefully', async () => {
      await webSocketService.shutdown();

      expect(mockIO.close).toHaveBeenCalled();
    });

    it('should handle shutdown errors', async () => {
      mockIO.close.mockImplementation(() => {
        throw new Error('Shutdown error');
      });

      // Should not throw
      await expect(webSocketService.shutdown()).resolves.not.toThrow();
    });

    it('should quit Redis clients if available', async () => {
      webSocketService['pubClient'] = mockRedisClient;
      webSocketService['subClient'] = mockRedisClient;

      await webSocketService.shutdown();

      expect(mockRedisClient.quit).toHaveBeenCalledTimes(2);
    });
  });

  describe('emitToJobOwner', () => {
    it('should emit event to job owner', async () => {
      const mockJobData = [{ user_id: 'user-123' }];
      mockDb.prisma.$queryRaw.mockResolvedValue(mockJobData as any);

      await webSocketService['emitToJobOwner']('job-123', 'job:completed', { result: 'success' });

      expect(mockIO.to).toHaveBeenCalledWith('user:user-123');
      expect(mockIO.emit).toHaveBeenCalledWith('job:completed', { result: 'success' });
    });

    it('should handle database errors when emitting to job owner', async () => {
      mockDb.prisma.$queryRaw.mockRejectedValue(new Error('Database error'));

      // Should not throw
      await expect(
        webSocketService['emitToJobOwner']('job-123', 'job:completed', { result: 'success' })
      ).resolves.not.toThrow();
    });
  });
});