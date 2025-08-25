import crypto from 'crypto';
import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';
import { config } from '@/config/index.js';
import { JWTPayload, UserRole } from '@/types/auth.js';

// Password hashing
export const password = {
  // Hash password
  async hash(plainPassword: string, saltRounds = 12): Promise<string> {
    return await bcrypt.hash(plainPassword, saltRounds);
  },

  // Verify password
  async verify(plainPassword: string, hashedPassword: string): Promise<boolean> {
    return await bcrypt.compare(plainPassword, hashedPassword);
  },

  // Generate secure random password
  generateRandom(length = 16): string {
    const charset = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*';
    let password = '';
    for (let i = 0; i < length; i++) {
      password += charset.charAt(crypto.randomInt(0, charset.length));
    }
    return password;
  },
};

// API key management
export const apiKey = {
  // Generate new API key
  generate(): { key: string; hash: string } {
    const key = `rag_${crypto.randomBytes(32).toString('hex')}`;
    const hash = crypto
      .createHmac('sha256', config.API_KEY_SALT)
      .update(key)
      .digest('hex');
    
    return { key, hash };
  },

  // Hash API key for storage/comparison
  hash(key: string): string {
    return crypto
      .createHmac('sha256', config.API_KEY_SALT)
      .update(key)
      .digest('hex');
  },

  // Verify API key
  verify(key: string, hash: string): boolean {
    return crypto.timingSafeEqual(
      Buffer.from(apiKey.hash(key)),
      Buffer.from(hash)
    );
  },
};

// JWT token management
export const token = {
  // Generate JWT tokens
  generateTokens(userId: string, role: UserRole): { accessToken: string; refreshToken: string } {
    const accessPayload: Omit<JWTPayload, 'iat' | 'exp'> = {
      sub: userId,
      type: 'access',
      iss: config.JWT_ISSUER,
    };

    const refreshPayload: Omit<JWTPayload, 'iat' | 'exp'> = {
      sub: userId,
      type: 'refresh',
      iss: config.JWT_ISSUER,
    };

    const accessToken = jwt.sign(accessPayload, config.JWT_SECRET, {
      expiresIn: '15m',
      audience: config.JWT_AUDIENCE,
    });

    const refreshToken = jwt.sign(refreshPayload, config.JWT_SECRET, {
      expiresIn: '7d',
      audience: config.JWT_AUDIENCE,
    });

    return { accessToken, refreshToken };
  },

  // Verify JWT token
  verify(token: string): JWTPayload {
    return jwt.verify(token, config.JWT_SECRET, {
      audience: config.JWT_AUDIENCE,
      issuer: config.JWT_ISSUER,
    }) as JWTPayload;
  },

  // Decode JWT token without verification (for debugging)
  decode(token: string): JWTPayload | null {
    return jwt.decode(token) as JWTPayload | null;
  },

  // Get token expiration time
  getExpirationTime(token: string): Date | null {
    const decoded = token.decode(token);
    return decoded?.exp ? new Date(decoded.exp * 1000) : null;
  },
};

// Encryption utilities
export const encrypt = {
  // Generate random bytes
  randomBytes(size: number): Buffer {
    return crypto.randomBytes(size);
  },

  // Generate random string
  randomString(length: number): string {
    return crypto.randomBytes(Math.ceil(length / 2)).toString('hex').slice(0, length);
  },

  // Generate UUID v4
  uuid(): string {
    return crypto.randomUUID();
  },

  // Generate secure random integer
  randomInt(min: number, max: number): number {
    return crypto.randomInt(min, max + 1);
  },

  // Create hash
  hash(data: string, algorithm: 'sha256' | 'sha512' = 'sha256'): string {
    return crypto.createHash(algorithm).update(data).digest('hex');
  },

  // Create HMAC
  hmac(data: string, key: string, algorithm: 'sha256' | 'sha512' = 'sha256'): string {
    return crypto.createHmac(algorithm, key).update(data).digest('hex');
  },

  // Encrypt data with AES-256-GCM
  encryptAES(plaintext: string, key: Buffer): { encrypted: string; iv: string; tag: string } {
    const iv = crypto.randomBytes(12); // 96-bit IV for GCM
    const cipher = crypto.createCipher('aes-256-gcm', key, { iv });
    
    let encrypted = cipher.update(plaintext, 'utf8', 'hex');
    encrypted += cipher.final('hex');
    
    const tag = cipher.getAuthTag().toString('hex');
    
    return {
      encrypted,
      iv: iv.toString('hex'),
      tag,
    };
  },

  // Decrypt data with AES-256-GCM
  decryptAES(encrypted: string, key: Buffer, iv: string, tag: string): string {
    const decipher = crypto.createDecipher('aes-256-gcm', key, {
      iv: Buffer.from(iv, 'hex'),
    });
    decipher.setAuthTag(Buffer.from(tag, 'hex'));
    
    let decrypted = decipher.update(encrypted, 'hex', 'utf8');
    decrypted += decipher.final('utf8');
    
    return decrypted;
  },
};

// File integrity
export const integrity = {
  // Calculate file checksum
  async calculateChecksum(filePath: string, algorithm: 'md5' | 'sha256' = 'sha256'): Promise<string> {
    const hash = crypto.createHash(algorithm);
    const fs = await import('fs');
    const stream = fs.createReadStream(filePath);
    
    return new Promise((resolve, reject) => {
      stream.on('error', reject);
      stream.on('data', chunk => hash.update(chunk));
      stream.on('end', () => resolve(hash.digest('hex')));
    });
  },

  // Calculate buffer checksum
  calculateBufferChecksum(buffer: Buffer, algorithm: 'md5' | 'sha256' = 'sha256'): string {
    return crypto.createHash(algorithm).update(buffer).digest('hex');
  },

  // Verify file integrity
  async verifyFileIntegrity(filePath: string, expectedChecksum: string, algorithm: 'md5' | 'sha256' = 'sha256'): Promise<boolean> {
    const actualChecksum = await integrity.calculateChecksum(filePath, algorithm);
    return crypto.timingSafeEqual(
      Buffer.from(actualChecksum),
      Buffer.from(expectedChecksum)
    );
  },
};

// Rate limiting helpers
export const rateLimiting = {
  // Generate rate limit key
  generateKey(identifier: string, window: string): string {
    return `rate_limit:${identifier}:${window}`;
  },

  // Get current time window
  getCurrentWindow(windowMs: number): number {
    return Math.floor(Date.now() / windowMs);
  },

  // Generate sliding window keys
  getSlidingWindowKeys(identifier: string, windowMs: number, buckets = 10): string[] {
    const now = Date.now();
    const bucketMs = windowMs / buckets;
    const keys: string[] = [];
    
    for (let i = 0; i < buckets; i++) {
      const bucketTime = Math.floor((now - i * bucketMs) / bucketMs);
      keys.push(`rate_limit:${identifier}:${bucketTime}`);
    }
    
    return keys;
  },
};

// Security headers
export const security = {
  // Generate Content Security Policy
  generateCSP(): string {
    const directives = [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline'",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: https:",
      "font-src 'self' https:",
      "connect-src 'self' https:",
      "frame-ancestors 'none'",
      "base-uri 'self'",
      "form-action 'self'",
    ];
    return directives.join('; ');
  },

  // Generate nonce for CSP
  generateNonce(): string {
    return crypto.randomBytes(16).toString('base64');
  },

  // Validate origin
  isValidOrigin(origin: string, allowedOrigins: string[]): boolean {
    return allowedOrigins.some(allowed => {
      if (allowed === '*') return true;
      if (allowed.startsWith('*.')) {
        const domain = allowed.slice(2);
        return origin.endsWith(domain);
      }
      return origin === allowed;
    });
  },
};