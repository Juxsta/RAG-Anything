import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';
import crypto from 'crypto';
import { db } from '@/services/database.js';
import { config } from '@/config/index.js';
import { logger } from '@/utils/logger.js';
import { 
  AuthenticationError, 
  AuthorizationError, 
  ValidationError 
} from '@/utils/errors.js';
import { AuthUser, UserRole, JWTPayload } from '@/types/auth.js';

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface CreateUserData {
  email: string;
  password: string;
  role?: UserRole;
}

export interface CreateAPIKeyData {
  userId: string;
  name: string;
  scopes?: string[];
  expiresAt?: Date;
}

export interface RefreshTokenData {
  userId: string;
  token: string;
  expiresAt: Date;
}

export class AuthService {
  private readonly saltRounds = 12;
  private readonly jwtSecret: string;
  private readonly jwtExpiresIn: string;
  private readonly refreshTokenExpiresIn: string;

  constructor() {
    this.jwtSecret = config.JWT_SECRET;
    this.jwtExpiresIn = config.JWT_EXPIRES_IN || '1h';
    this.refreshTokenExpiresIn = config.REFRESH_TOKEN_EXPIRES_IN || '7d';
  }

  /**
   * Validate JWT token and return user data
   */
  async validateJWT(token: string): Promise<AuthUser | null> {
    try {
      const payload = jwt.verify(token, this.jwtSecret) as JWTPayload;
      
      // Fetch user from database
      const user = await db.prisma.$queryRaw<Array<{
        id: string;
        email: string;
        role: string;
        is_active: boolean;
        email_verified: boolean;
      }>>`
        SELECT id, email, role, is_active, email_verified
        FROM users 
        WHERE id = ${payload.sub}::uuid 
        AND is_active = true
      `;
      
      if (!user || user.length === 0) {
        return null;
      }

      const userData = user[0];
      
      // Update last login
      await db.prisma.$executeRaw`
        UPDATE users 
        SET last_login = CURRENT_TIMESTAMP, 
            login_count = login_count + 1
        WHERE id = ${userData.id}::uuid
      `;
      
      return {
        id: userData.id,
        email: userData.email,
        role: userData.role as UserRole,
        apiKey: false,
        emailVerified: userData.email_verified,
      };
      
    } catch (error) {
      logger.warn('JWT validation failed', { error: error.message });
      return null;
    }
  }

  /**
   * Validate API key and return user data
   */
  async validateAPIKey(keyString: string): Promise<AuthUser | null> {
    try {
      if (!keyString.startsWith('rag_') || keyString.length !== 67) {
        return null;
      }
      
      const keyHash = crypto.createHash('sha256').update(keyString).digest('hex');
      const keyPrefix = keyString.substring(0, 20);
      
      const apiKeyData = await db.prisma.$queryRaw<Array<{
        id: string;
        user_id: string;
        scopes: any;
        user_email: string;
        user_role: string;
        user_is_active: boolean;
      }>>`
        SELECT 
          ak.id,
          ak.user_id,
          ak.scopes,
          u.email as user_email,
          u.role as user_role,
          u.is_active as user_is_active
        FROM api_keys ak
        JOIN users u ON ak.user_id = u.id
        WHERE ak.key_hash = ${keyHash}
        AND ak.key_prefix = ${keyPrefix}
        AND ak.is_active = true
        AND u.is_active = true
        AND (ak.expires_at IS NULL OR ak.expires_at > CURRENT_TIMESTAMP)
      `;
      
      if (!apiKeyData || apiKeyData.length === 0) {
        return null;
      }

      const keyData = apiKeyData[0];
      
      // Update usage tracking
      await db.prisma.$executeRaw`
        UPDATE api_keys 
        SET last_used = CURRENT_TIMESTAMP, 
            usage_count = usage_count + 1
        WHERE id = ${keyData.id}::uuid
      `;
      
      return {
        id: keyData.user_id,
        email: keyData.user_email,
        role: keyData.user_role as UserRole,
        apiKey: true,
        scopes: Array.isArray(keyData.scopes) ? keyData.scopes : [],
      };
      
    } catch (error) {
      logger.warn('API key validation failed', { error: error.message });
      return null;
    }
  }

  /**
   * Login user with email and password
   */
  async login(credentials: LoginCredentials): Promise<{
    user: AuthUser;
    accessToken: string;
    refreshToken: string;
  }> {
    const { email, password } = credentials;

    // Find user by email
    const users = await db.prisma.$queryRaw<Array<{
      id: string;
      email: string;
      password_hash: string;
      role: string;
      is_active: boolean;
      email_verified: boolean;
      login_count: number;
    }>>`
      SELECT id, email, password_hash, role, is_active, email_verified, login_count
      FROM users 
      WHERE email = ${email.toLowerCase()}
    `;

    if (!users || users.length === 0) {
      throw new AuthenticationError('Invalid email or password');
    }

    const user = users[0];

    if (!user.is_active) {
      throw new AuthenticationError('Account is deactivated');
    }

    // Verify password
    const isValidPassword = await bcrypt.compare(password, user.password_hash);
    if (!isValidPassword) {
      throw new AuthenticationError('Invalid email or password');
    }

    // Generate tokens
    const accessToken = this.generateAccessToken(user.id, user.role as UserRole);
    const refreshToken = this.generateRefreshToken();

    // Store refresh token
    await this.storeRefreshToken({
      userId: user.id,
      token: refreshToken,
      expiresAt: new Date(Date.now() + this.parseExpirationTime(this.refreshTokenExpiresIn)),
    });

    // Update login tracking
    await db.prisma.$executeRaw`
      UPDATE users 
      SET last_login = CURRENT_TIMESTAMP, 
          login_count = login_count + 1
      WHERE id = ${user.id}::uuid
    `;

    const authUser: AuthUser = {
      id: user.id,
      email: user.email,
      role: user.role as UserRole,
      apiKey: false,
      emailVerified: user.email_verified,
    };

    logger.info('User logged in successfully', { 
      userId: user.id, 
      email: user.email,
      loginCount: user.login_count + 1,
    });

    return {
      user: authUser,
      accessToken,
      refreshToken,
    };
  }

  /**
   * Refresh access token
   */
  async refreshToken(refreshToken: string): Promise<{
    accessToken: string;
    refreshToken: string;
  }> {
    // Validate refresh token
    const refreshTokenData = await db.prisma.$queryRaw<Array<{
      user_id: string;
      user_role: string;
      expires_at: Date;
    }>>`
      SELECT rt.user_id, u.role as user_role, rt.expires_at
      FROM refresh_tokens rt
      JOIN users u ON rt.user_id = u.id
      WHERE rt.token = ${refreshToken}
      AND rt.expires_at > CURRENT_TIMESTAMP
      AND rt.revoked = false
      AND u.is_active = true
    `;

    if (!refreshTokenData || refreshTokenData.length === 0) {
      throw new AuthenticationError('Invalid or expired refresh token');
    }

    const tokenData = refreshTokenData[0];

    // Generate new tokens
    const newAccessToken = this.generateAccessToken(tokenData.user_id, tokenData.user_role as UserRole);
    const newRefreshToken = this.generateRefreshToken();

    // Revoke old refresh token and store new one
    await db.prisma.$transaction([
      db.prisma.$executeRaw`
        UPDATE refresh_tokens 
        SET revoked = true 
        WHERE token = ${refreshToken}
      `,
      db.prisma.$executeRaw`
        INSERT INTO refresh_tokens (user_id, token, expires_at)
        VALUES (${tokenData.user_id}::uuid, ${newRefreshToken}, ${new Date(Date.now() + this.parseExpirationTime(this.refreshTokenExpiresIn))})
      `,
    ]);

    return {
      accessToken: newAccessToken,
      refreshToken: newRefreshToken,
    };
  }

  /**
   * Create new user
   */
  async createUser(userData: CreateUserData): Promise<AuthUser> {
    const { email, password, role = 'user' } = userData;

    // Validate email format
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      throw new ValidationError('Invalid email format');
    }

    // Validate password strength
    if (password.length < 8) {
      throw new ValidationError('Password must be at least 8 characters long');
    }

    const emailLower = email.toLowerCase();

    // Check if user already exists
    const existingUsers = await db.prisma.$queryRaw<Array<{ id: string }>>`
      SELECT id FROM users WHERE email = ${emailLower}
    `;

    if (existingUsers && existingUsers.length > 0) {
      throw new ValidationError('User with this email already exists');
    }

    // Hash password
    const passwordHash = await bcrypt.hash(password, this.saltRounds);

    // Create user
    const newUsers = await db.prisma.$queryRaw<Array<{
      id: string;
      email: string;
      role: string;
      email_verified: boolean;
    }>>`
      INSERT INTO users (email, password_hash, role)
      VALUES (${emailLower}, ${passwordHash}, ${role})
      RETURNING id, email, role, email_verified
    `;

    const newUser = newUsers[0];

    logger.info('New user created', { 
      userId: newUser.id, 
      email: newUser.email,
      role: newUser.role,
    });

    return {
      id: newUser.id,
      email: newUser.email,
      role: newUser.role as UserRole,
      apiKey: false,
      emailVerified: newUser.email_verified,
    };
  }

  /**
   * Create API key for user
   */
  async createAPIKey(data: CreateAPIKeyData): Promise<{
    key: string;
    keyId: string;
    prefix: string;
  }> {
    const { userId, name, scopes = [], expiresAt } = data;

    // Generate API key
    const keyString = this.generateAPIKey();
    const keyHash = crypto.createHash('sha256').update(keyString).digest('hex');
    const keyPrefix = keyString.substring(0, 20);

    // Store API key
    const apiKeys = await db.prisma.$queryRaw<Array<{ id: string }>>`
      INSERT INTO api_keys (user_id, key_hash, key_prefix, name, scopes, expires_at)
      VALUES (
        ${userId}::uuid, 
        ${keyHash}, 
        ${keyPrefix}, 
        ${name}, 
        ${JSON.stringify(scopes)}, 
        ${expiresAt || null}
      )
      RETURNING id
    `;

    const keyId = apiKeys[0].id;

    logger.info('API key created', { 
      userId, 
      keyId, 
      name,
      scopes: scopes.length,
    });

    return {
      key: keyString,
      keyId,
      prefix: keyPrefix,
    };
  }

  /**
   * Revoke API key
   */
  async revokeAPIKey(keyId: string, userId: string): Promise<void> {
    const result = await db.prisma.$executeRaw`
      UPDATE api_keys 
      SET is_active = false 
      WHERE id = ${keyId}::uuid AND user_id = ${userId}::uuid
    `;

    if (result === 0) {
      throw new ValidationError('API key not found or access denied');
    }

    logger.info('API key revoked', { keyId, userId });
  }

  /**
   * List user's API keys
   */
  async listAPIKeys(userId: string): Promise<Array<{
    id: string;
    name: string;
    prefix: string;
    scopes: string[];
    isActive: boolean;
    lastUsed: Date | null;
    usageCount: number;
    createdAt: Date;
    expiresAt: Date | null;
  }>> {
    const apiKeys = await db.prisma.$queryRaw<Array<{
      id: string;
      name: string;
      key_prefix: string;
      scopes: any;
      is_active: boolean;
      last_used: Date | null;
      usage_count: number;
      created_at: Date;
      expires_at: Date | null;
    }>>`
      SELECT id, name, key_prefix, scopes, is_active, last_used, usage_count, created_at, expires_at
      FROM api_keys
      WHERE user_id = ${userId}::uuid
      ORDER BY created_at DESC
    `;

    return apiKeys.map(key => ({
      id: key.id,
      name: key.name,
      prefix: key.key_prefix,
      scopes: Array.isArray(key.scopes) ? key.scopes : [],
      isActive: key.is_active,
      lastUsed: key.last_used,
      usageCount: key.usage_count,
      createdAt: key.created_at,
      expiresAt: key.expires_at,
    }));
  }

  /**
   * Logout user (revoke refresh token)
   */
  async logout(refreshToken: string): Promise<void> {
    await db.prisma.$executeRaw`
      UPDATE refresh_tokens 
      SET revoked = true 
      WHERE token = ${refreshToken}
    `;
  }

  /**
   * Check if user has required permissions
   */
  async checkPermissions(user: AuthUser, requiredRoles: UserRole[]): Promise<boolean> {
    if (requiredRoles.length === 0) {
      return true;
    }

    return requiredRoles.includes(user.role);
  }

  /**
   * Generate JWT access token
   */
  private generateAccessToken(userId: string, role: UserRole): string {
    const payload: JWTPayload = {
      sub: userId,
      role,
      type: 'access',
      iat: Math.floor(Date.now() / 1000),
    };

    return jwt.sign(payload, this.jwtSecret, {
      expiresIn: this.jwtExpiresIn,
      issuer: 'rag-anything-api',
      audience: 'rag-anything-client',
    });
  }

  /**
   * Generate refresh token
   */
  private generateRefreshToken(): string {
    return crypto.randomBytes(32).toString('hex');
  }

  /**
   * Generate API key
   */
  private generateAPIKey(): string {
    const randomBytes = crypto.randomBytes(32);
    const keyBody = randomBytes.toString('base64url');
    return `rag_${keyBody}`;
  }

  /**
   * Store refresh token in database
   */
  private async storeRefreshToken(data: RefreshTokenData): Promise<void> {
    await db.prisma.$executeRaw`
      INSERT INTO refresh_tokens (user_id, token, expires_at)
      VALUES (${data.userId}::uuid, ${data.token}, ${data.expiresAt})
    `;
  }

  /**
   * Parse expiration time string to milliseconds
   */
  private parseExpirationTime(expiration: string): number {
    const unit = expiration.slice(-1);
    const value = parseInt(expiration.slice(0, -1));

    switch (unit) {
      case 's': return value * 1000;
      case 'm': return value * 60 * 1000;
      case 'h': return value * 60 * 60 * 1000;
      case 'd': return value * 24 * 60 * 60 * 1000;
      default: throw new Error(`Invalid expiration format: ${expiration}`);
    }
  }
}

// Singleton instance
export const authService = new AuthService();