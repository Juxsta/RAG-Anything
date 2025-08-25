import { FastifyInstance } from 'fastify';
import { Server } from 'http';
import { io as SocketIOClient, Socket } from 'socket.io-client';
import FormData from 'form-data';
import fs from 'fs';
import path from 'path';
import { promisify } from 'util';
import { UserFactory, APIKeyFactory, DocumentFactory } from './test-factories';
import { authService } from '@/services/auth';

/**
 * Test helper utilities for integration and E2E tests
 */

export interface TestContext {
  app: FastifyInstance;
  server: Server;
  baseUrl: string;
  adminUser?: any;
  regularUser?: any;
  adminToken?: string;
  userToken?: string;
  adminApiKey?: string;
  userApiKey?: string;
}

export interface WebSocketTestClient {
  socket: Socket;
  events: Map<string, any[]>;
  connect: () => Promise<void>;
  disconnect: () => Promise<void>;
  waitForEvent: (eventName: string, timeout?: number) => Promise<any>;
  emit: (eventName: string, data: any) => void;
}

/**
 * Test context manager for setting up complete test environments
 */
export class TestContextManager {
  private static instance: TestContext | null = null;

  static async createContext(app: FastifyInstance): Promise<TestContext> {
    if (this.instance) {
      return this.instance;
    }

    const server = app.server;
    const address = server.address();
    const port = typeof address === 'object' && address ? address.port : 3000;
    const baseUrl = `http://localhost:${port}`;

    // Create test users
    const adminUser = await UserFactory.createAdminAndSave({
      email: 'admin@test.com',
      password: 'AdminPassword123!',
    });

    const regularUser = await UserFactory.createAndSave({
      email: 'user@test.com',
      password: 'UserPassword123!',
    });

    // Get auth tokens
    const adminLogin = await authService.login({
      email: adminUser.email,
      password: adminUser.password,
    });

    const userLogin = await authService.login({
      email: regularUser.email,
      password: regularUser.password,
    });

    // Create API keys
    const adminAPIKey = await APIKeyFactory.createAndSave(adminUser.id, {
      name: 'Admin Test API Key',
      scopes: ['read', 'write', 'admin'],
    });

    const userAPIKey = await APIKeyFactory.createAndSave(regularUser.id, {
      name: 'User Test API Key',
      scopes: ['read', 'write'],
    });

    this.instance = {
      app,
      server,
      baseUrl,
      adminUser,
      regularUser,
      adminToken: adminLogin.accessToken,
      userToken: userLogin.accessToken,
      adminApiKey: adminAPIKey.key,
      userApiKey: userAPIKey.key,
    };

    return this.instance;
  }

  static async cleanup(): Promise<void> {
    this.instance = null;
    
    // Clean up test data
    if (global.testEnv?.prisma) {
      await global.testEnv.prisma.$executeRaw`TRUNCATE TABLE refresh_tokens CASCADE`;
      await global.testEnv.prisma.$executeRaw`TRUNCATE TABLE job_status CASCADE`;
      await global.testEnv.prisma.$executeRaw`TRUNCATE TABLE queries CASCADE`;
      await global.testEnv.prisma.$executeRaw`TRUNCATE TABLE documents CASCADE`;
      await global.testEnv.prisma.$executeRaw`TRUNCATE TABLE api_keys CASCADE`;
      await global.testEnv.prisma.$executeRaw`TRUNCATE TABLE users CASCADE`;
    }

    if (global.testEnv?.redisClient) {
      await global.testEnv.redisClient.flushAll();
    }
  }

  static getInstance(): TestContext | null {
    return this.instance;
  }
}

/**
 * WebSocket test client for testing real-time features
 */
export class WebSocketTestHelper {
  private socket: Socket | null = null;
  private events: Map<string, any[]> = new Map();
  private readonly baseUrl: string;
  private readonly authToken?: string;
  private readonly apiKey?: string;

  constructor(baseUrl: string, authToken?: string, apiKey?: string) {
    this.baseUrl = baseUrl;
    this.authToken = authToken;
    this.apiKey = apiKey;
  }

  async connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      const auth: any = {};
      
      if (this.authToken) {
        auth.token = this.authToken;
      }
      
      if (this.apiKey) {
        auth.apiKey = this.apiKey;
      }

      this.socket = SocketIOClient(this.baseUrl, {
        auth,
        transports: ['websocket'],
        timeout: 5000,
      });

      this.socket.on('connect', () => {
        resolve();
      });

      this.socket.on('connect_error', (error) => {
        reject(new Error(`WebSocket connection failed: ${error.message}`));
      });

      // Capture all events
      this.socket.onAny((eventName, ...args) => {
        if (!this.events.has(eventName)) {
          this.events.set(eventName, []);
        }
        this.events.get(eventName)!.push(args);
      });

      // Set connection timeout
      setTimeout(() => {
        if (!this.socket?.connected) {
          reject(new Error('WebSocket connection timeout'));
        }
      }, 5000);
    });
  }

  async disconnect(): Promise<void> {
    return new Promise((resolve) => {
      if (this.socket) {
        this.socket.disconnect();
        this.socket = null;
        this.events.clear();
      }
      resolve();
    });
  }

  emit(eventName: string, data: any): void {
    if (!this.socket || !this.socket.connected) {
      throw new Error('WebSocket not connected');
    }
    this.socket.emit(eventName, data);
  }

  async waitForEvent(eventName: string, timeout: number = 5000): Promise<any> {
    return new Promise((resolve, reject) => {
      const timeoutId = setTimeout(() => {
        reject(new Error(`Timeout waiting for event: ${eventName}`));
      }, timeout);

      const checkEvents = () => {
        const events = this.events.get(eventName);
        if (events && events.length > 0) {
          clearTimeout(timeoutId);
          resolve(events[events.length - 1]); // Return latest event
        } else {
          setTimeout(checkEvents, 50); // Check every 50ms
        }
      };

      checkEvents();
    });
  }

  getEvents(eventName: string): any[] {
    return this.events.get(eventName) || [];
  }

  clearEvents(): void {
    this.events.clear();
  }

  isConnected(): boolean {
    return this.socket ? this.socket.connected : false;
  }
}

/**
 * File upload test helpers
 */
export class FileUploadHelper {
  static async createTestFile(content: string | Buffer, filename: string = 'test.txt'): Promise<string> {
    const tempDir = '/tmp/test-uploads';
    if (!fs.existsSync(tempDir)) {
      fs.mkdirSync(tempDir, { recursive: true });
    }

    const filePath = path.join(tempDir, filename);
    const fileContent = typeof content === 'string' ? Buffer.from(content) : content;
    
    await promisify(fs.writeFile)(filePath, fileContent);
    return filePath;
  }

  static async createFormData(files: { path: string; fieldName?: string; filename?: string }[]): Promise<FormData> {
    const form = new FormData();
    
    for (const file of files) {
      const stream = fs.createReadStream(file.path);
      form.append(
        file.fieldName || 'file',
        stream,
        file.filename || path.basename(file.path)
      );
    }
    
    return form;
  }

  static async uploadFile(
    app: FastifyInstance,
    filePath: string,
    token?: string,
    apiKey?: string
  ): Promise<any> {
    const form = await this.createFormData([{ path: filePath }]);
    
    const headers: any = {
      ...form.getHeaders(),
    };

    if (token) {
      headers.authorization = `Bearer ${token}`;
    }

    if (apiKey) {
      headers['x-api-key'] = apiKey;
    }

    const response = await app.inject({
      method: 'POST',
      url: '/api/v1/documents/upload',
      headers,
      payload: form,
    });

    return {
      statusCode: response.statusCode,
      body: JSON.parse(response.body),
    };
  }

  static async cleanup(): Promise<void> {
    const tempDir = '/tmp/test-uploads';
    if (fs.existsSync(tempDir)) {
      const files = fs.readdirSync(tempDir);
      for (const file of files) {
        fs.unlinkSync(path.join(tempDir, file));
      }
      fs.rmdirSync(tempDir);
    }
  }
}

/**
 * Database test helpers
 */
export class DatabaseTestHelper {
  static async waitForJobCompletion(jobId: string, timeout: number = 30000): Promise<any> {
    const startTime = Date.now();
    
    while (Date.now() - startTime < timeout) {
      const jobData = await global.testEnv.prisma.$queryRaw<Array<{
        id: string;
        status: string;
        result: any;
        error_message: string | null;
      }>>`
        SELECT id, status, result, error_message 
        FROM job_status 
        WHERE job_id = ${jobId}
      `;

      if (jobData.length > 0) {
        const job = jobData[0];
        if (job.status === 'completed' || job.status === 'failed') {
          return job;
        }
      }

      await new Promise(resolve => setTimeout(resolve, 100));
    }

    throw new Error(`Job ${jobId} did not complete within ${timeout}ms`);
  }

  static async getQueryHistory(userId: string, limit: number = 10): Promise<any[]> {
    return await global.testEnv.prisma.$queryRaw<any[]>`
      SELECT * FROM queries 
      WHERE user_id = ${userId}::uuid 
      ORDER BY created_at DESC 
      LIMIT ${limit}
    `;
  }

  static async getUserDocuments(userId: string): Promise<any[]> {
    return await global.testEnv.prisma.$queryRaw<any[]>`
      SELECT * FROM documents 
      WHERE user_id = ${userId}::uuid 
      ORDER BY created_at DESC
    `;
  }

  static async getAPIKeyUsage(keyHash: string): Promise<any> {
    const usage = await global.testEnv.prisma.$queryRaw<Array<{
      usage_count: number;
      last_used: Date | null;
    }>>`
      SELECT usage_count, last_used 
      FROM api_keys 
      WHERE key_hash = ${keyHash}
    `;
    
    return usage[0] || null;
  }

  static async simulateDatabaseFailure(): Promise<void> {
    // Simulate database connection loss
    await global.testEnv.prisma.$disconnect();
  }

  static async restoreDatabaseConnection(): Promise<void> {
    // Restore database connection
    await global.testEnv.prisma.$connect();
  }
}

/**
 * Performance monitoring helpers
 */
export class PerformanceTestHelper {
  private static metrics: Map<string, number[]> = new Map();

  static startTimer(label: string): () => number {
    const startTime = Date.now();
    
    return () => {
      const duration = Date.now() - startTime;
      if (!this.metrics.has(label)) {
        this.metrics.set(label, []);
      }
      this.metrics.get(label)!.push(duration);
      return duration;
    };
  }

  static async measureEndpoint(
    app: FastifyInstance,
    method: string,
    url: string,
    options: any = {}
  ): Promise<{ duration: number; response: any }> {
    const stopTimer = this.startTimer(`${method} ${url}`);
    
    const response = await app.inject({
      method,
      url,
      ...options,
    });
    
    const duration = stopTimer();
    
    return { duration, response };
  }

  static getMetrics(label: string): { count: number; avg: number; min: number; max: number; p95: number } {
    const times = this.metrics.get(label) || [];
    
    if (times.length === 0) {
      return { count: 0, avg: 0, min: 0, max: 0, p95: 0 };
    }

    const sorted = [...times].sort((a, b) => a - b);
    const sum = times.reduce((a, b) => a + b, 0);
    
    return {
      count: times.length,
      avg: sum / times.length,
      min: sorted[0],
      max: sorted[sorted.length - 1],
      p95: sorted[Math.floor(sorted.length * 0.95)],
    };
  }

  static clearMetrics(): void {
    this.metrics.clear();
  }

  static getAllMetrics(): Record<string, ReturnType<typeof PerformanceTestHelper.getMetrics>> {
    const result: any = {};
    for (const [label] of this.metrics) {
      result[label] = this.getMetrics(label);
    }
    return result;
  }
}

/**
 * Network simulation helpers
 */
export class NetworkTestHelper {
  static async simulateSlowNetwork(delayMs: number): Promise<void> {
    await new Promise(resolve => setTimeout(resolve, delayMs));
  }

  static async simulateNetworkPartition(durationMs: number): Promise<void> {
    // Simulate network issues by disconnecting Redis
    if (global.testEnv?.redisClient) {
      await global.testEnv.redisClient.disconnect();
      
      setTimeout(async () => {
        await global.testEnv.redisClient.connect();
      }, durationMs);
    }
  }

  static async simulateHighLatency<T>(
    operation: () => Promise<T>,
    latencyMs: number
  ): Promise<T> {
    await this.simulateSlowNetwork(latencyMs);
    return await operation();
  }
}

/**
 * Security test helpers
 */
export class SecurityTestHelper {
  static readonly SQL_INJECTION_PAYLOADS = [
    "'; DROP TABLE users; --",
    "' OR '1'='1",
    "admin'--",
    "'; UPDATE users SET role='admin' WHERE id='1'; --",
    "' UNION SELECT * FROM users--",
  ];

  static readonly XSS_PAYLOADS = [
    '<script>alert("XSS")</script>',
    '<img src=x onerror=alert("XSS")>',
    '<svg onload=alert("XSS")>',
    'javascript:alert("XSS")',
    '<iframe src="javascript:alert(\'XSS\')"></iframe>',
  ];

  static readonly PATH_TRAVERSAL_PAYLOADS = [
    '../../../etc/passwd',
    '..\\..\\..\\windows\\system32\\config\\sam',
    '....//....//....//etc/passwd',
    '../../../../../../etc/passwd',
  ];

  static async testRateLimit(
    app: FastifyInstance,
    endpoint: string,
    method: string = 'GET',
    attempts: number = 20,
    headers: any = {}
  ): Promise<{ blockedCount: number; responses: any[] }> {
    const responses = [];
    let blockedCount = 0;

    for (let i = 0; i < attempts; i++) {
      const response = await app.inject({
        method,
        url: endpoint,
        headers,
      });

      responses.push({
        attempt: i + 1,
        statusCode: response.statusCode,
        body: JSON.parse(response.body),
      });

      if (response.statusCode === 429) {
        blockedCount++;
      }

      // Small delay to avoid overwhelming the test
      await new Promise(resolve => setTimeout(resolve, 10));
    }

    return { blockedCount, responses };
  }

  static async testAuthBypass(
    app: FastifyInstance,
    protectedEndpoint: string,
    method: string = 'GET'
  ): Promise<{ vulnerableEndpoints: string[] }> {
    const vulnerableEndpoints = [];
    
    const bypassAttempts = [
      // No authentication
      {},
      
      // Malformed tokens
      { authorization: 'Bearer invalid-token' },
      { authorization: 'Bearer ' },
      { authorization: 'Bearer null' },
      { authorization: 'Basic dGVzdDp0ZXN0' }, // test:test
      
      // Invalid API keys
      { 'x-api-key': 'invalid-key' },
      { 'x-api-key': '' },
      { 'x-api-key': 'null' },
      
      // Header manipulation
      { 'user-id': 'admin' },
      { 'x-user-role': 'admin' },
      { 'x-forwarded-user': 'admin' },
    ];

    for (const headers of bypassAttempts) {
      const response = await app.inject({
        method,
        url: protectedEndpoint,
        headers,
      });

      // If we get anything other than 401/403, it might be vulnerable
      if (response.statusCode !== 401 && response.statusCode !== 403) {
        vulnerableEndpoints.push(`${method} ${protectedEndpoint} with headers: ${JSON.stringify(headers)}`);
      }
    }

    return { vulnerableEndpoints };
  }
}

/**
 * Mock service helpers
 */
export class MockServiceHelper {
  static createMockPythonProcess(): any {
    return {
      send: jest.fn().mockResolvedValue(undefined),
      kill: jest.fn(),
      on: jest.fn(),
      removeListener: jest.fn(),
      pid: 12345,
      connected: true,
    };
  }

  static createMockWebSocketServer(): any {
    return {
      emit: jest.fn(),
      to: jest.fn().mockReturnThis(),
      use: jest.fn(),
      on: jest.fn(),
      close: jest.fn(),
    };
  }

  static createMockRedisClient(): any {
    const mockData: Map<string, any> = new Map();
    
    return {
      set: jest.fn().mockImplementation((key, value) => {
        mockData.set(key, value);
        return Promise.resolve('OK');
      }),
      get: jest.fn().mockImplementation((key) => {
        return Promise.resolve(mockData.get(key));
      }),
      del: jest.fn().mockImplementation((key) => {
        mockData.delete(key);
        return Promise.resolve(1);
      }),
      flushAll: jest.fn().mockImplementation(() => {
        mockData.clear();
        return Promise.resolve('OK');
      }),
      connect: jest.fn().mockResolvedValue(undefined),
      disconnect: jest.fn().mockResolvedValue(undefined),
      quit: jest.fn().mockResolvedValue(undefined),
    };
  }
}

/**
 * Test report helpers
 */
export class TestReportHelper {
  static generatePerformanceReport(): string {
    const metrics = PerformanceTestHelper.getAllMetrics();
    
    let report = '# Performance Test Report\n\n';
    report += `Generated at: ${new Date().toISOString()}\n\n`;
    
    report += '## Endpoint Performance\n\n';
    report += '| Endpoint | Count | Avg (ms) | Min (ms) | Max (ms) | P95 (ms) |\n';
    report += '|----------|-------|----------|----------|----------|----------|\n';
    
    for (const [endpoint, stats] of Object.entries(metrics)) {
      report += `| ${endpoint} | ${stats.count} | ${stats.avg.toFixed(2)} | ${stats.min} | ${stats.max} | ${stats.p95} |\n`;
    }
    
    return report;
  }

  static async saveTestArtifacts(testName: string, data: any): Promise<void> {
    const artifactsDir = '/tmp/test-artifacts';
    if (!fs.existsSync(artifactsDir)) {
      fs.mkdirSync(artifactsDir, { recursive: true });
    }

    const filename = `${testName}-${Date.now()}.json`;
    const filePath = path.join(artifactsDir, filename);
    
    await promisify(fs.writeFile)(
      filePath,
      JSON.stringify(data, null, 2)
    );
  }
}