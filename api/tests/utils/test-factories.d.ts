/**
 * Test data factories for generating realistic test data
 */
export interface TestUser {
    id?: string;
    email: string;
    password: string;
    role: 'user' | 'admin';
    isActive?: boolean;
    emailVerified?: boolean;
}
export interface TestDocument {
    id?: string;
    filename: string;
    originalName: string;
    filePath: string;
    fileSize: number;
    mimeType: string;
    checksum: string;
    status?: string;
    content?: Buffer;
}
export interface TestQuery {
    id?: string;
    queryText: string;
    queryType: 'text' | 'multimodal';
    mode: 'local' | 'global' | 'hybrid' | 'mix';
    userId?: string;
}
export interface TestAPIKey {
    id?: string;
    name: string;
    key?: string;
    scopes: string[];
    expiresAt?: Date;
    userId?: string;
}
/**
 * User factory
 */
export declare class UserFactory {
    static create(overrides?: Partial<TestUser>): TestUser;
    static createAdmin(overrides?: Partial<TestUser>): TestUser;
    static createBatch(count: number, overrides?: Partial<TestUser>): TestUser[];
    static createAndSave(overrides?: Partial<TestUser>): Promise<TestUser & {
        id: string;
    }>;
    static createAdminAndSave(overrides?: Partial<TestUser>): Promise<TestUser & {
        id: string;
    }>;
}
/**
 * Document factory
 */
export declare class DocumentFactory {
    static create(overrides?: Partial<TestDocument>): TestDocument;
    static createPDF(overrides?: Partial<TestDocument>): TestDocument;
    static createImage(overrides?: Partial<TestDocument>): TestDocument;
    static createLargeFile(overrides?: Partial<TestDocument>): TestDocument;
    static createBatch(count: number, overrides?: Partial<TestDocument>): TestDocument[];
    private static getMimeType;
}
/**
 * Query factory
 */
export declare class QueryFactory {
    static create(overrides?: Partial<TestQuery>): TestQuery;
    static createTextQuery(overrides?: Partial<TestQuery>): TestQuery;
    static createMultimodalQuery(overrides?: Partial<TestQuery>): TestQuery;
    static createComplexQuery(overrides?: Partial<TestQuery>): TestQuery;
    static createBatch(count: number, overrides?: Partial<TestQuery>): TestQuery[];
}
/**
 * API Key factory
 */
export declare class APIKeyFactory {
    static create(overrides?: Partial<TestAPIKey>): TestAPIKey;
    static createExpired(overrides?: Partial<TestAPIKey>): TestAPIKey;
    static createReadOnly(overrides?: Partial<TestAPIKey>): TestAPIKey;
    static createAndSave(userId: string, overrides?: Partial<TestAPIKey>): Promise<TestAPIKey & {
        id: string;
        key: string;
    }>;
}
/**
 * File content generators
 */
export declare class FileContentFactory {
    static createTextContent(words?: number): Buffer;
    static createJSONContent(data?: any): Buffer;
    static createMarkdownContent(): Buffer;
    static createCSVContent(): Buffer;
    static createImagePlaceholder(width?: number, height?: number): Buffer;
}
/**
 * Performance test data generators
 */
export declare class PerformanceTestFactory {
    static createConcurrentUsers(count: number): TestUser[];
    static createLoadTestQueries(count: number): TestQuery[];
    static createFileUploadBatch(count: number, sizeRange?: {
        min: number;
        max: number;
    }): TestDocument[];
}
/**
 * Error scenario generators
 */
export declare class ErrorScenarioFactory {
    static createMaliciousPayloads(): string[];
    static createInvalidTokens(): string[];
    static createInvalidEmailAddresses(): string[];
    static createWeakPasswords(): string[];
}
/**
 * Mock data seeder
 */
export declare class TestDataSeeder {
    static seedUsers(count?: number): Promise<Array<TestUser & {
        id: string;
    }>>;
    static seedAPIKeys(userId: string, count?: number): Promise<Array<TestAPIKey & {
        id: string;
        key: string;
    }>>;
    static seedDocuments(userId: string, count?: number): Promise<TestDocument[]>;
    static cleanupTestData(): Promise<void>;
}
//# sourceMappingURL=test-factories.d.ts.map