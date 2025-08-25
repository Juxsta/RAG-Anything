import { db } from '@/services/database';

describe('DatabaseService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  afterEach(() => {
    jest.resetAllMocks();
  });

  describe('getInstance', () => {
    it('should return singleton instance', () => {
      const instance1 = db;
      const instance2 = db;
      
      expect(instance1).toBe(instance2);
      expect(instance1).toBeDefined();
    });
  });

  describe('connect', () => {
    it('should connect to database successfully', async () => {
      const mockConnect = jest.fn().mockResolvedValue(undefined);
      db.prisma.$connect = mockConnect;

      await db.connect();

      expect(mockConnect).toHaveBeenCalled();
    });

    it('should handle connection errors', async () => {
      const mockConnect = jest.fn().mockRejectedValue(new Error('Connection failed'));
      db.prisma.$connect = mockConnect;

      await expect(db.connect()).rejects.toThrow('Connection failed');
    });
  });

  describe('disconnect', () => {
    it('should disconnect from database', async () => {
      const mockDisconnect = jest.fn().mockResolvedValue(undefined);
      db.prisma.$disconnect = mockDisconnect;

      await db.disconnect();

      expect(mockDisconnect).toHaveBeenCalled();
    });
  });

  describe('healthCheck', () => {
    it('should return healthy status when database is accessible', async () => {
      const mockQueryRaw = jest.fn().mockResolvedValue([{ result: 1 }]);
      db.prisma.$queryRaw = mockQueryRaw;

      const result = await db.healthCheck();

      expect(result.status).toBe('healthy');
      expect(result.latency).toBeGreaterThanOrEqual(0);
      expect(mockQueryRaw).toHaveBeenCalled();
    });

    it('should return unhealthy status when database is not accessible', async () => {
      const mockQueryRaw = jest.fn().mockRejectedValue(new Error('Database error'));
      db.prisma.$queryRaw = mockQueryRaw;

      const result = await db.healthCheck();

      expect(result.status).toBe('unhealthy');
      expect(result.latency).toBe(-1);
    });

    it('should measure query latency', async () => {
      const mockQueryRaw = jest.fn().mockImplementation(() => {
        return new Promise(resolve => {
          setTimeout(() => resolve([{ result: 1 }]), 50);
        });
      });
      db.prisma.$queryRaw = mockQueryRaw;

      const result = await db.healthCheck();

      expect(result.status).toBe('healthy');
      expect(result.latency).toBeGreaterThan(40);
    });
  });
});