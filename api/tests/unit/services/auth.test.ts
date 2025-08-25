import { AuthService } from '@/services/auth';
import { db } from '@/services/database';
import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';
import { AuthenticationError, ValidationError } from '@/utils/errors';

// Mock the database service
jest.mock('@/services/database');
jest.mock('bcryptjs');
jest.mock('jsonwebtoken');

const mockDb = db as jest.Mocked<typeof db>;
const mockBcrypt = bcrypt as jest.Mocked<typeof bcrypt>;
const mockJwt = jwt as jest.Mocked<typeof jwt>;

describe('AuthService', () => {
  let authService: AuthService;

  beforeEach(() => {
    jest.clearAllMocks();
    authService = new AuthService();
    
    // Setup environment
    process.env.JWT_SECRET = 'test-jwt-secret';
    process.env.JWT_EXPIRES_IN = '1h';
    process.env.REFRESH_TOKEN_EXPIRES_IN = '7d';
  });

  afterEach(() => {
    jest.resetAllMocks();
  });

  describe('validateJWT', () => {
    it('should validate a valid JWT token and return user data', async () => {
      const mockPayload = { sub: 'user-123', role: 'user' };
      const mockUser = [{
        id: 'user-123',
        email: 'test@example.com',
        role: 'user',
        is_active: true,
        email_verified: true,
      }];

      mockJwt.verify.mockReturnValue(mockPayload as any);
      mockDb.prisma.$queryRaw.mockResolvedValue(mockUser as any);
      mockDb.prisma.$executeRaw.mockResolvedValue(1);

      const result = await authService.validateJWT('valid-token');

      expect(result).toEqual({
        id: 'user-123',
        email: 'test@example.com',
        role: 'user',
        apiKey: false,
        emailVerified: true,
      });
      expect(mockJwt.verify).toHaveBeenCalledWith('valid-token', 'test-jwt-secret');
      expect(mockDb.prisma.$queryRaw).toHaveBeenCalled();
    });

    it('should return null for invalid JWT token', async () => {
      mockJwt.verify.mockImplementation(() => {
        throw new Error('Invalid token');
      });

      const result = await authService.validateJWT('invalid-token');

      expect(result).toBeNull();
    });

    it('should return null if user not found in database', async () => {
      const mockPayload = { sub: 'user-123', role: 'user' };
      
      mockJwt.verify.mockReturnValue(mockPayload as any);
      mockDb.prisma.$queryRaw.mockResolvedValue([]);

      const result = await authService.validateJWT('valid-token');

      expect(result).toBeNull();
    });

    it('should return null if user is inactive', async () => {
      const mockPayload = { sub: 'user-123', role: 'user' };
      const mockUser = [{
        id: 'user-123',
        email: 'test@example.com',
        role: 'user',
        is_active: false,
        email_verified: true,
      }];

      mockJwt.verify.mockReturnValue(mockPayload as any);
      mockDb.prisma.$queryRaw.mockResolvedValue([]);

      const result = await authService.validateJWT('valid-token');

      expect(result).toBeNull();
    });
  });

  describe('validateAPIKey', () => {
    it('should validate a valid API key and return user data', async () => {
      const apiKeyString = 'rag_' + 'a'.repeat(64); // Valid format
      const mockKeyData = [{
        id: 'key-123',
        user_id: 'user-123',
        scopes: ['read', 'write'],
        user_email: 'test@example.com',
        user_role: 'user',
        user_is_active: true,
      }];

      mockDb.prisma.$queryRaw.mockResolvedValue(mockKeyData as any);
      mockDb.prisma.$executeRaw.mockResolvedValue(1);

      const result = await authService.validateAPIKey(apiKeyString);

      expect(result).toEqual({
        id: 'user-123',
        email: 'test@example.com',
        role: 'user',
        apiKey: true,
        scopes: ['read', 'write'],
      });
    });

    it('should return null for invalid API key format', async () => {
      const result = await authService.validateAPIKey('invalid-key');
      expect(result).toBeNull();
    });

    it('should return null for API key not found in database', async () => {
      const apiKeyString = 'rag_' + 'a'.repeat(64);
      
      mockDb.prisma.$queryRaw.mockResolvedValue([]);

      const result = await authService.validateAPIKey(apiKeyString);

      expect(result).toBeNull();
    });
  });

  describe('login', () => {
    it('should successfully login with valid credentials', async () => {
      const credentials = { email: 'test@example.com', password: 'password123' };
      const mockUser = [{
        id: 'user-123',
        email: 'test@example.com',
        password_hash: 'hashed-password',
        role: 'user',
        is_active: true,
        email_verified: true,
        login_count: 5,
      }];

      mockDb.prisma.$queryRaw.mockResolvedValue(mockUser as any);
      mockBcrypt.compare.mockResolvedValue(true as never);
      mockDb.prisma.$transaction.mockResolvedValue(undefined as any);
      mockDb.prisma.$executeRaw.mockResolvedValue(1);

      // Mock JWT generation
      authService['generateAccessToken'] = jest.fn().mockReturnValue('access-token');
      authService['generateRefreshToken'] = jest.fn().mockReturnValue('refresh-token');
      authService['storeRefreshToken'] = jest.fn().mockResolvedValue(undefined);

      const result = await authService.login(credentials);

      expect(result.user).toEqual({
        id: 'user-123',
        email: 'test@example.com',
        role: 'user',
        apiKey: false,
        emailVerified: true,
      });
      expect(result.accessToken).toBe('access-token');
      expect(result.refreshToken).toBe('refresh-token');
    });

    it('should throw AuthenticationError for invalid email', async () => {
      const credentials = { email: 'nonexistent@example.com', password: 'password123' };
      
      mockDb.prisma.$queryRaw.mockResolvedValue([]);

      await expect(authService.login(credentials))
        .rejects
        .toThrow(AuthenticationError);
    });

    it('should throw AuthenticationError for invalid password', async () => {
      const credentials = { email: 'test@example.com', password: 'wrongpassword' };
      const mockUser = [{
        id: 'user-123',
        email: 'test@example.com',
        password_hash: 'hashed-password',
        role: 'user',
        is_active: true,
        email_verified: true,
        login_count: 5,
      }];

      mockDb.prisma.$queryRaw.mockResolvedValue(mockUser as any);
      mockBcrypt.compare.mockResolvedValue(false as never);

      await expect(authService.login(credentials))
        .rejects
        .toThrow(AuthenticationError);
    });

    it('should throw AuthenticationError for inactive user', async () => {
      const credentials = { email: 'test@example.com', password: 'password123' };
      const mockUser = [{
        id: 'user-123',
        email: 'test@example.com',
        password_hash: 'hashed-password',
        role: 'user',
        is_active: false,
        email_verified: true,
        login_count: 5,
      }];

      mockDb.prisma.$queryRaw.mockResolvedValue(mockUser as any);

      await expect(authService.login(credentials))
        .rejects
        .toThrow(AuthenticationError);
    });
  });

  describe('createUser', () => {
    it('should create a new user with valid data', async () => {
      const userData = {
        email: 'newuser@example.com',
        password: 'securepassword123',
        role: 'user' as const,
      };

      // Mock email uniqueness check
      mockDb.prisma.$queryRaw.mockResolvedValueOnce([]); // No existing user
      
      // Mock password hashing
      mockBcrypt.hash.mockResolvedValue('hashed-password' as never);
      
      // Mock user creation
      const mockNewUser = [{
        id: 'user-new',
        email: 'newuser@example.com',
        role: 'user',
        email_verified: false,
      }];
      mockDb.prisma.$queryRaw.mockResolvedValueOnce(mockNewUser as any);

      const result = await authService.createUser(userData);

      expect(result).toEqual({
        id: 'user-new',
        email: 'newuser@example.com',
        role: 'user',
        apiKey: false,
        emailVerified: false,
      });
      expect(mockBcrypt.hash).toHaveBeenCalledWith('securepassword123', 12);
    });

    it('should throw ValidationError for invalid email', async () => {
      const userData = {
        email: 'invalid-email',
        password: 'securepassword123',
      };

      await expect(authService.createUser(userData))
        .rejects
        .toThrow(ValidationError);
    });

    it('should throw ValidationError for weak password', async () => {
      const userData = {
        email: 'test@example.com',
        password: 'weak',
      };

      await expect(authService.createUser(userData))
        .rejects
        .toThrow(ValidationError);
    });

    it('should throw ValidationError for existing email', async () => {
      const userData = {
        email: 'existing@example.com',
        password: 'securepassword123',
      };

      // Mock existing user
      mockDb.prisma.$queryRaw.mockResolvedValue([{ id: 'existing-user' }] as any);

      await expect(authService.createUser(userData))
        .rejects
        .toThrow(ValidationError);
    });
  });

  describe('createAPIKey', () => {
    it('should create a new API key for user', async () => {
      const keyData = {
        userId: 'user-123',
        name: 'Test API Key',
        scopes: ['read'],
      };

      const mockKeyResult = [{ id: 'key-123' }];
      mockDb.prisma.$queryRaw.mockResolvedValue(mockKeyResult as any);

      authService['generateAPIKey'] = jest.fn().mockReturnValue('rag_generated_key');

      const result = await authService.createAPIKey(keyData);

      expect(result.key).toBe('rag_generated_key');
      expect(result.keyId).toBe('key-123');
      expect(result.prefix).toBe('rag_generated_key');
    });
  });

  describe('checkPermissions', () => {
    it('should return true if user has required role', async () => {
      const user = {
        id: 'user-123',
        email: 'test@example.com',
        role: 'admin' as const,
        apiKey: false,
      };

      const result = await authService.checkPermissions(user, ['admin']);
      expect(result).toBe(true);
    });

    it('should return false if user does not have required role', async () => {
      const user = {
        id: 'user-123',
        email: 'test@example.com',
        role: 'user' as const,
        apiKey: false,
      };

      const result = await authService.checkPermissions(user, ['admin']);
      expect(result).toBe(false);
    });

    it('should return true if no roles are required', async () => {
      const user = {
        id: 'user-123',
        email: 'test@example.com',
        role: 'user' as const,
        apiKey: false,
      };

      const result = await authService.checkPermissions(user, []);
      expect(result).toBe(true);
    });
  });

  describe('refreshToken', () => {
    it('should refresh tokens with valid refresh token', async () => {
      const refreshToken = 'valid-refresh-token';
      const mockTokenData = [{
        user_id: 'user-123',
        user_role: 'user',
        expires_at: new Date(Date.now() + 86400000), // 1 day from now
      }];

      mockDb.prisma.$queryRaw.mockResolvedValue(mockTokenData as any);
      mockDb.prisma.$transaction.mockResolvedValue(undefined as any);

      authService['generateAccessToken'] = jest.fn().mockReturnValue('new-access-token');
      authService['generateRefreshToken'] = jest.fn().mockReturnValue('new-refresh-token');

      const result = await authService.refreshToken(refreshToken);

      expect(result.accessToken).toBe('new-access-token');
      expect(result.refreshToken).toBe('new-refresh-token');
    });

    it('should throw AuthenticationError for invalid refresh token', async () => {
      mockDb.prisma.$queryRaw.mockResolvedValue([]);

      await expect(authService.refreshToken('invalid-token'))
        .rejects
        .toThrow(AuthenticationError);
    });
  });

  describe('listAPIKeys', () => {
    it('should return user API keys', async () => {
      const userId = 'user-123';
      const mockKeys = [
        {
          id: 'key-1',
          name: 'Test Key 1',
          key_prefix: 'rag_abc123',
          scopes: ['read'],
          is_active: true,
          last_used: new Date(),
          usage_count: 5,
          created_at: new Date(),
          expires_at: null,
        },
      ];

      mockDb.prisma.$queryRaw.mockResolvedValue(mockKeys as any);

      const result = await authService.listAPIKeys(userId);

      expect(result).toHaveLength(1);
      expect(result[0]).toEqual(expect.objectContaining({
        id: 'key-1',
        name: 'Test Key 1',
        prefix: 'rag_abc123',
        scopes: ['read'],
        isActive: true,
        usageCount: 5,
      }));
    });
  });

  describe('revokeAPIKey', () => {
    it('should revoke an API key', async () => {
      mockDb.prisma.$executeRaw.mockResolvedValue(1); // 1 row affected

      await authService.revokeAPIKey('key-123', 'user-123');

      expect(mockDb.prisma.$executeRaw).toHaveBeenCalled();
    });

    it('should throw ValidationError if key not found', async () => {
      mockDb.prisma.$executeRaw.mockResolvedValue(0); // 0 rows affected

      await expect(authService.revokeAPIKey('key-123', 'user-123'))
        .rejects
        .toThrow(ValidationError);
    });
  });

  describe('logout', () => {
    it('should revoke refresh token', async () => {
      mockDb.prisma.$executeRaw.mockResolvedValue(1);

      await authService.logout('refresh-token');

      expect(mockDb.prisma.$executeRaw).toHaveBeenCalled();
    });
  });
});