import { FastifyInstance } from 'fastify';
import { Server } from 'http';
import { Socket } from 'socket.io-client';
import FormData from 'form-data';
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
export declare class TestContextManager {
    private static instance;
    static createContext(app: FastifyInstance): Promise<TestContext>;
    static cleanup(): Promise<void>;
    static getInstance(): TestContext | null;
}
/**
 * WebSocket test client for testing real-time features
 */
export declare class WebSocketTestHelper {
    private socket;
    private events;
    private readonly baseUrl;
    private readonly authToken?;
    private readonly apiKey?;
    constructor(baseUrl: string, authToken?: string, apiKey?: string);
    connect(): Promise<void>;
    disconnect(): Promise<void>;
    emit(eventName: string, data: any): void;
    waitForEvent(eventName: string, timeout?: number): Promise<any>;
    getEvents(eventName: string): any[];
    clearEvents(): void;
    isConnected(): boolean;
}
/**
 * File upload test helpers
 */
export declare class FileUploadHelper {
    static createTestFile(content: string | Buffer, filename?: string): Promise<string>;
    static createFormData(files: {
        path: string;
        fieldName?: string;
        filename?: string;
    }[]): Promise<FormData>;
    static uploadFile(app: FastifyInstance, filePath: string, token?: string, apiKey?: string): Promise<any>;
    static cleanup(): Promise<void>;
}
/**
 * Database test helpers
 */
export declare class DatabaseTestHelper {
    static waitForJobCompletion(jobId: string, timeout?: number): Promise<any>;
    static getQueryHistory(userId: string, limit?: number): Promise<any[]>;
    static getUserDocuments(userId: string): Promise<any[]>;
    static getAPIKeyUsage(keyHash: string): Promise<any>;
    static simulateDatabaseFailure(): Promise<void>;
    static restoreDatabaseConnection(): Promise<void>;
}
/**
 * Performance monitoring helpers
 */
export declare class PerformanceTestHelper {
    private static metrics;
    static startTimer(label: string): () => number;
    static measureEndpoint(app: FastifyInstance, method: string, url: string, options?: any): Promise<{
        duration: number;
        response: any;
    }>;
    static getMetrics(label: string): {
        count: number;
        avg: number;
        min: number;
        max: number;
        p95: number;
    };
    static clearMetrics(): void;
    static getAllMetrics(): Record<string, ReturnType<typeof PerformanceTestHelper.getMetrics>>;
}
/**
 * Network simulation helpers
 */
export declare class NetworkTestHelper {
    static simulateSlowNetwork(delayMs: number): Promise<void>;
    static simulateNetworkPartition(durationMs: number): Promise<void>;
    static simulateHighLatency<T>(operation: () => Promise<T>, latencyMs: number): Promise<T>;
}
/**
 * Security test helpers
 */
export declare class SecurityTestHelper {
    static readonly SQL_INJECTION_PAYLOADS: string[];
    static readonly XSS_PAYLOADS: string[];
    static readonly PATH_TRAVERSAL_PAYLOADS: string[];
    static testRateLimit(app: FastifyInstance, endpoint: string, method?: string, attempts?: number, headers?: any): Promise<{
        blockedCount: number;
        responses: any[];
    }>;
    static testAuthBypass(app: FastifyInstance, protectedEndpoint: string, method?: string): Promise<{
        vulnerableEndpoints: string[];
    }>;
}
/**
 * Mock service helpers
 */
export declare class MockServiceHelper {
    static createMockPythonProcess(): any;
    static createMockWebSocketServer(): any;
    static createMockRedisClient(): any;
}
/**
 * Test report helpers
 */
export declare class TestReportHelper {
    static generatePerformanceReport(): string;
    static saveTestArtifacts(testName: string, data: any): Promise<void>;
}
//# sourceMappingURL=test-helpers.d.ts.map