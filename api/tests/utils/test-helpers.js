import { io as SocketIOClient } from 'socket.io-client';
import FormData from 'form-data';
import fs from 'fs';
import path from 'path';
import { promisify } from 'util';
import { UserFactory, APIKeyFactory } from './test-factories';
import { authService } from '@/services/auth';
/**
 * Test context manager for setting up complete test environments
 */
export class TestContextManager {
    static instance = null;
    static async createContext(app) {
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
    static async cleanup() {
        this.instance = null;
        // Clean up test data
        if (global.testEnv?.prisma) {
            await global.testEnv.prisma.$executeRaw `TRUNCATE TABLE refresh_tokens CASCADE`;
            await global.testEnv.prisma.$executeRaw `TRUNCATE TABLE job_status CASCADE`;
            await global.testEnv.prisma.$executeRaw `TRUNCATE TABLE queries CASCADE`;
            await global.testEnv.prisma.$executeRaw `TRUNCATE TABLE documents CASCADE`;
            await global.testEnv.prisma.$executeRaw `TRUNCATE TABLE api_keys CASCADE`;
            await global.testEnv.prisma.$executeRaw `TRUNCATE TABLE users CASCADE`;
        }
        if (global.testEnv?.redisClient) {
            await global.testEnv.redisClient.flushAll();
        }
    }
    static getInstance() {
        return this.instance;
    }
}
/**
 * WebSocket test client for testing real-time features
 */
export class WebSocketTestHelper {
    socket = null;
    events = new Map();
    baseUrl;
    authToken;
    apiKey;
    constructor(baseUrl, authToken, apiKey) {
        this.baseUrl = baseUrl;
        this.authToken = authToken;
        this.apiKey = apiKey;
    }
    async connect() {
        return new Promise((resolve, reject) => {
            const auth = {};
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
                this.events.get(eventName).push(args);
            });
            // Set connection timeout
            setTimeout(() => {
                if (!this.socket?.connected) {
                    reject(new Error('WebSocket connection timeout'));
                }
            }, 5000);
        });
    }
    async disconnect() {
        return new Promise((resolve) => {
            if (this.socket) {
                this.socket.disconnect();
                this.socket = null;
                this.events.clear();
            }
            resolve();
        });
    }
    emit(eventName, data) {
        if (!this.socket || !this.socket.connected) {
            throw new Error('WebSocket not connected');
        }
        this.socket.emit(eventName, data);
    }
    async waitForEvent(eventName, timeout = 5000) {
        return new Promise((resolve, reject) => {
            const timeoutId = setTimeout(() => {
                reject(new Error(`Timeout waiting for event: ${eventName}`));
            }, timeout);
            const checkEvents = () => {
                const events = this.events.get(eventName);
                if (events && events.length > 0) {
                    clearTimeout(timeoutId);
                    resolve(events[events.length - 1]); // Return latest event
                }
                else {
                    setTimeout(checkEvents, 50); // Check every 50ms
                }
            };
            checkEvents();
        });
    }
    getEvents(eventName) {
        return this.events.get(eventName) || [];
    }
    clearEvents() {
        this.events.clear();
    }
    isConnected() {
        return this.socket ? this.socket.connected : false;
    }
}
/**
 * File upload test helpers
 */
export class FileUploadHelper {
    static async createTestFile(content, filename = 'test.txt') {
        const tempDir = '/tmp/test-uploads';
        if (!fs.existsSync(tempDir)) {
            fs.mkdirSync(tempDir, { recursive: true });
        }
        const filePath = path.join(tempDir, filename);
        const fileContent = typeof content === 'string' ? Buffer.from(content) : content;
        await promisify(fs.writeFile)(filePath, fileContent);
        return filePath;
    }
    static async createFormData(files) {
        const form = new FormData();
        for (const file of files) {
            const stream = fs.createReadStream(file.path);
            form.append(file.fieldName || 'file', stream, file.filename || path.basename(file.path));
        }
        return form;
    }
    static async uploadFile(app, filePath, token, apiKey) {
        const form = await this.createFormData([{ path: filePath }]);
        const headers = {
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
    static async cleanup() {
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
    static async waitForJobCompletion(jobId, timeout = 30000) {
        const startTime = Date.now();
        while (Date.now() - startTime < timeout) {
            const jobData = await global.testEnv.prisma.$queryRaw `
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
    static async getQueryHistory(userId, limit = 10) {
        return await global.testEnv.prisma.$queryRaw `
      SELECT * FROM queries 
      WHERE user_id = ${userId}::uuid 
      ORDER BY created_at DESC 
      LIMIT ${limit}
    `;
    }
    static async getUserDocuments(userId) {
        return await global.testEnv.prisma.$queryRaw `
      SELECT * FROM documents 
      WHERE user_id = ${userId}::uuid 
      ORDER BY created_at DESC
    `;
    }
    static async getAPIKeyUsage(keyHash) {
        const usage = await global.testEnv.prisma.$queryRaw `
      SELECT usage_count, last_used 
      FROM api_keys 
      WHERE key_hash = ${keyHash}
    `;
        return usage[0] || null;
    }
    static async simulateDatabaseFailure() {
        // Simulate database connection loss
        await global.testEnv.prisma.$disconnect();
    }
    static async restoreDatabaseConnection() {
        // Restore database connection
        await global.testEnv.prisma.$connect();
    }
}
/**
 * Performance monitoring helpers
 */
export class PerformanceTestHelper {
    static metrics = new Map();
    static startTimer(label) {
        const startTime = Date.now();
        return () => {
            const duration = Date.now() - startTime;
            if (!this.metrics.has(label)) {
                this.metrics.set(label, []);
            }
            this.metrics.get(label).push(duration);
            return duration;
        };
    }
    static async measureEndpoint(app, method, url, options = {}) {
        const stopTimer = this.startTimer(`${method} ${url}`);
        const response = await app.inject({
            method,
            url,
            ...options,
        });
        const duration = stopTimer();
        return { duration, response };
    }
    static getMetrics(label) {
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
    static clearMetrics() {
        this.metrics.clear();
    }
    static getAllMetrics() {
        const result = {};
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
    static async simulateSlowNetwork(delayMs) {
        await new Promise(resolve => setTimeout(resolve, delayMs));
    }
    static async simulateNetworkPartition(durationMs) {
        // Simulate network issues by disconnecting Redis
        if (global.testEnv?.redisClient) {
            await global.testEnv.redisClient.disconnect();
            setTimeout(async () => {
                await global.testEnv.redisClient.connect();
            }, durationMs);
        }
    }
    static async simulateHighLatency(operation, latencyMs) {
        await this.simulateSlowNetwork(latencyMs);
        return await operation();
    }
}
/**
 * Security test helpers
 */
export class SecurityTestHelper {
    static SQL_INJECTION_PAYLOADS = [
        "'; DROP TABLE users; --",
        "' OR '1'='1",
        "admin'--",
        "'; UPDATE users SET role='admin' WHERE id='1'; --",
        "' UNION SELECT * FROM users--",
    ];
    static XSS_PAYLOADS = [
        '<script>alert("XSS")</script>',
        '<img src=x onerror=alert("XSS")>',
        '<svg onload=alert("XSS")>',
        'javascript:alert("XSS")',
        '<iframe src="javascript:alert(\'XSS\')"></iframe>',
    ];
    static PATH_TRAVERSAL_PAYLOADS = [
        '../../../etc/passwd',
        '..\\..\\..\\windows\\system32\\config\\sam',
        '....//....//....//etc/passwd',
        '../../../../../../etc/passwd',
    ];
    static async testRateLimit(app, endpoint, method = 'GET', attempts = 20, headers = {}) {
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
    static async testAuthBypass(app, protectedEndpoint, method = 'GET') {
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
    static createMockPythonProcess() {
        return {
            send: jest.fn().mockResolvedValue(undefined),
            kill: jest.fn(),
            on: jest.fn(),
            removeListener: jest.fn(),
            pid: 12345,
            connected: true,
        };
    }
    static createMockWebSocketServer() {
        return {
            emit: jest.fn(),
            to: jest.fn().mockReturnThis(),
            use: jest.fn(),
            on: jest.fn(),
            close: jest.fn(),
        };
    }
    static createMockRedisClient() {
        const mockData = new Map();
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
    static generatePerformanceReport() {
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
    static async saveTestArtifacts(testName, data) {
        const artifactsDir = '/tmp/test-artifacts';
        if (!fs.existsSync(artifactsDir)) {
            fs.mkdirSync(artifactsDir, { recursive: true });
        }
        const filename = `${testName}-${Date.now()}.json`;
        const filePath = path.join(artifactsDir, filename);
        await promisify(fs.writeFile)(filePath, JSON.stringify(data, null, 2));
    }
}
//# sourceMappingURL=test-helpers.js.map