import { faker } from '@faker-js/faker';
import crypto from 'crypto';
import { authService } from '@/services/auth';

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
export class UserFactory {
  static create(overrides: Partial<TestUser> = {}): TestUser {
    return {
      email: faker.internet.email().toLowerCase(),
      password: 'TestPassword123!',
      role: 'user',
      isActive: true,
      emailVerified: false,
      ...overrides,
    };
  }

  static createAdmin(overrides: Partial<TestUser> = {}): TestUser {
    return this.create({
      role: 'admin',
      emailVerified: true,
      ...overrides,
    });
  }

  static createBatch(count: number, overrides: Partial<TestUser> = {}): TestUser[] {
    return Array.from({ length: count }, () => this.create(overrides));
  }

  static async createAndSave(overrides: Partial<TestUser> = {}): Promise<TestUser & { id: string }> {
    const userData = this.create(overrides);
    const savedUser = await authService.createUser({
      email: userData.email,
      password: userData.password,
      role: userData.role,
    });
    return { ...userData, id: savedUser.id };
  }

  static async createAdminAndSave(overrides: Partial<TestUser> = {}): Promise<TestUser & { id: string }> {
    return this.createAndSave({ role: 'admin', emailVerified: true, ...overrides });
  }
}

/**
 * Document factory
 */
export class DocumentFactory {
  static create(overrides: Partial<TestDocument> = {}): TestDocument {
    const filename = faker.system.fileName({ extensionCount: 1 });
    const content = Buffer.from(faker.lorem.paragraphs(5));
    
    return {
      filename: `doc_${Date.now()}_${filename}`,
      originalName: filename,
      filePath: `/tmp/test_documents/${filename}`,
      fileSize: content.length,
      mimeType: this.getMimeType(filename),
      checksum: crypto.createHash('sha256').update(content).digest('hex'),
      status: 'uploaded',
      content,
      ...overrides,
    };
  }

  static createPDF(overrides: Partial<TestDocument> = {}): TestDocument {
    return this.create({
      originalName: `${faker.lorem.word()}.pdf`,
      mimeType: 'application/pdf',
      fileSize: faker.number.int({ min: 100000, max: 5000000 }),
      ...overrides,
    });
  }

  static createImage(overrides: Partial<TestDocument> = {}): TestDocument {
    const extensions = ['jpg', 'png', 'gif', 'webp'];
    const ext = faker.helpers.arrayElement(extensions);
    
    return this.create({
      originalName: `${faker.lorem.word()}.${ext}`,
      mimeType: `image/${ext === 'jpg' ? 'jpeg' : ext}`,
      fileSize: faker.number.int({ min: 50000, max: 2000000 }),
      ...overrides,
    });
  }

  static createLargeFile(overrides: Partial<TestDocument> = {}): TestDocument {
    return this.create({
      fileSize: faker.number.int({ min: 50000000, max: 100000000 }), // 50-100MB
      ...overrides,
    });
  }

  static createBatch(count: number, overrides: Partial<TestDocument> = {}): TestDocument[] {
    return Array.from({ length: count }, () => this.create(overrides));
  }

  private static getMimeType(filename: string): string {
    const ext = filename.split('.').pop()?.toLowerCase();
    const mimeTypes: Record<string, string> = {
      pdf: 'application/pdf',
      txt: 'text/plain',
      md: 'text/markdown',
      doc: 'application/msword',
      docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      jpg: 'image/jpeg',
      jpeg: 'image/jpeg',
      png: 'image/png',
      gif: 'image/gif',
      webp: 'image/webp',
    };
    return mimeTypes[ext || ''] || 'application/octet-stream';
  }
}

/**
 * Query factory
 */
export class QueryFactory {
  static create(overrides: Partial<TestQuery> = {}): TestQuery {
    return {
      queryText: faker.lorem.sentence({ min: 3, max: 15 }),
      queryType: faker.helpers.arrayElement(['text', 'multimodal']),
      mode: faker.helpers.arrayElement(['local', 'global', 'hybrid', 'mix']),
      ...overrides,
    };
  }

  static createTextQuery(overrides: Partial<TestQuery> = {}): TestQuery {
    return this.create({
      queryText: `What is ${faker.lorem.words(3)}?`,
      queryType: 'text',
      mode: 'local',
      ...overrides,
    });
  }

  static createMultimodalQuery(overrides: Partial<TestQuery> = {}): TestQuery {
    return this.create({
      queryText: `Analyze the image and tell me about ${faker.lorem.words(2)}`,
      queryType: 'multimodal',
      mode: 'hybrid',
      ...overrides,
    });
  }

  static createComplexQuery(overrides: Partial<TestQuery> = {}): TestQuery {
    const topics = ['artificial intelligence', 'machine learning', 'data science', 'computer vision', 'natural language processing'];
    const topic = faker.helpers.arrayElement(topics);
    
    return this.create({
      queryText: `Provide a comprehensive analysis of ${topic} including historical context, current applications, and future trends. Please include specific examples and cite relevant sources.`,
      queryType: 'text',
      mode: 'mix',
      ...overrides,
    });
  }

  static createBatch(count: number, overrides: Partial<TestQuery> = {}): TestQuery[] {
    return Array.from({ length: count }, () => this.create(overrides));
  }
}

/**
 * API Key factory
 */
export class APIKeyFactory {
  static create(overrides: Partial<TestAPIKey> = {}): TestAPIKey {
    return {
      name: `${faker.lorem.words(2)} API Key`,
      scopes: faker.helpers.arrayElements(['read', 'write', 'admin'], { min: 1, max: 3 }),
      expiresAt: faker.date.future(),
      ...overrides,
    };
  }

  static createExpired(overrides: Partial<TestAPIKey> = {}): TestAPIKey {
    return this.create({
      name: 'Expired API Key',
      expiresAt: faker.date.past(),
      ...overrides,
    });
  }

  static createReadOnly(overrides: Partial<TestAPIKey> = {}): TestAPIKey {
    return this.create({
      name: 'Read Only API Key',
      scopes: ['read'],
      ...overrides,
    });
  }

  static async createAndSave(userId: string, overrides: Partial<TestAPIKey> = {}): Promise<TestAPIKey & { id: string; key: string }> {
    const apiKeyData = this.create(overrides);
    const savedAPIKey = await authService.createAPIKey({
      userId,
      name: apiKeyData.name,
      scopes: apiKeyData.scopes,
      expiresAt: apiKeyData.expiresAt,
    });
    
    return {
      ...apiKeyData,
      id: savedAPIKey.id,
      key: savedAPIKey.key,
    };
  }
}

/**
 * File content generators
 */
export class FileContentFactory {
  static createTextContent(words: number = 1000): Buffer {
    const content = faker.lorem.words(words);
    return Buffer.from(content, 'utf-8');
  }

  static createJSONContent(data: any = null): Buffer {
    const content = data || {
      title: faker.lorem.sentence(),
      content: faker.lorem.paragraphs(3),
      author: faker.person.fullName(),
      tags: faker.lorem.words(5).split(' '),
      createdAt: faker.date.past().toISOString(),
    };
    return Buffer.from(JSON.stringify(content, null, 2), 'utf-8');
  }

  static createMarkdownContent(): Buffer {
    const content = `# ${faker.lorem.sentence()}

${faker.lorem.paragraph()}

## ${faker.lorem.words(3)}

${faker.lorem.paragraphs(2)}

### Key Points

${Array.from({ length: 5 }, () => `- ${faker.lorem.sentence()}`).join('\n')}

## Conclusion

${faker.lorem.paragraph()}
`;
    return Buffer.from(content, 'utf-8');
  }

  static createCSVContent(): Buffer {
    const headers = ['id', 'name', 'email', 'age', 'city'];
    const rows = Array.from({ length: 100 }, (_, i) => [
      i + 1,
      faker.person.fullName(),
      faker.internet.email(),
      faker.number.int({ min: 18, max: 80 }),
      faker.location.city(),
    ]);

    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.join(',')),
    ].join('\n');

    return Buffer.from(csvContent, 'utf-8');
  }

  static createImagePlaceholder(width: number = 800, height: number = 600): Buffer {
    // Create a simple image placeholder data (not a real image, but valid binary data)
    const size = width * height * 3; // RGB
    const data = Buffer.alloc(size);
    
    // Fill with random data to simulate image content
    for (let i = 0; i < size; i++) {
      data[i] = faker.number.int({ min: 0, max: 255 });
    }
    
    return data;
  }
}

/**
 * Performance test data generators
 */
export class PerformanceTestFactory {
  static createConcurrentUsers(count: number): TestUser[] {
    return Array.from({ length: count }, (_, i) => ({
      email: `load-test-user-${i}@example.com`,
      password: 'LoadTest123!',
      role: 'user' as const,
    }));
  }

  static createLoadTestQueries(count: number): TestQuery[] {
    const queryTemplates = [
      'What is the main topic of this document?',
      'Summarize the key findings',
      'What are the implications of this research?',
      'Explain the methodology used',
      'What are the conclusions?',
    ];

    return Array.from({ length: count }, (_, i) => ({
      queryText: faker.helpers.arrayElement(queryTemplates) + ` (Query ${i + 1})`,
      queryType: faker.helpers.arrayElement(['text', 'multimodal']) as 'text' | 'multimodal',
      mode: faker.helpers.arrayElement(['local', 'global', 'hybrid', 'mix']) as 'local' | 'global' | 'hybrid' | 'mix',
    }));
  }

  static createFileUploadBatch(count: number, sizeRange: { min: number; max: number } = { min: 1000, max: 1000000 }): TestDocument[] {
    return Array.from({ length: count }, (_, i) => {
      const size = faker.number.int(sizeRange);
      const content = Buffer.alloc(size);
      
      // Fill with random data
      for (let j = 0; j < size; j++) {
        content[j] = faker.number.int({ min: 0, max: 255 });
      }

      return {
        filename: `load-test-${i}.txt`,
        originalName: `load-test-document-${i}.txt`,
        filePath: `/tmp/load-test-${i}.txt`,
        fileSize: size,
        mimeType: 'text/plain',
        checksum: crypto.createHash('sha256').update(content).digest('hex'),
        content,
      };
    });
  }
}

/**
 * Error scenario generators
 */
export class ErrorScenarioFactory {
  static createMaliciousPayloads(): string[] {
    return [
      // SQL Injection attempts
      "'; DROP TABLE users; --",
      "' OR '1'='1",
      "admin'/*",
      "'; UPDATE users SET role='admin' WHERE id='1'; --",
      
      // XSS attempts
      '<script>alert("XSS")</script>',
      '<img src=x onerror=alert("XSS")>',
      '<svg onload=alert("XSS")>',
      'javascript:alert("XSS")',
      
      // Path traversal
      '../../../etc/passwd',
      '..\\..\\..\\windows\\system32\\config\\sam',
      
      // Command injection
      '; cat /etc/passwd',
      '| ls -la',
      '&& whoami',
      
      // Large payloads
      'A'.repeat(10000),
      'X'.repeat(100000),
    ];
  }

  static createInvalidTokens(): string[] {
    return [
      'invalid-token',
      'Bearer invalid-token',
      'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid.signature',
      '',
      'null',
      'undefined',
      '{}',
      'malformed-jwt',
    ];
  }

  static createInvalidEmailAddresses(): string[] {
    return [
      'invalid-email',
      '@example.com',
      'user@',
      'user..double.dot@example.com',
      'user@example.',
      'user name@example.com',
      'user@ex ample.com',
      '',
    ];
  }

  static createWeakPasswords(): string[] {
    return [
      '123',
      'password',
      'admin',
      'qwerty',
      '12345678',
      'password123',
      '',
    ];
  }
}

/**
 * Mock data seeder
 */
export class TestDataSeeder {
  static async seedUsers(count: number = 10): Promise<Array<TestUser & { id: string }>> {
    const users = UserFactory.createBatch(count);
    const savedUsers = [];
    
    for (const userData of users) {
      const savedUser = await UserFactory.createAndSave(userData);
      savedUsers.push(savedUser);
    }
    
    return savedUsers;
  }

  static async seedAPIKeys(userId: string, count: number = 3): Promise<Array<TestAPIKey & { id: string; key: string }>> {
    const apiKeys = [];
    
    for (let i = 0; i < count; i++) {
      const apiKeyData = APIKeyFactory.create({
        name: `Test API Key ${i + 1}`,
      });
      const savedAPIKey = await APIKeyFactory.createAndSave(userId, apiKeyData);
      apiKeys.push(savedAPIKey);
    }
    
    return apiKeys;
  }

  static async seedDocuments(userId: string, count: number = 5): Promise<TestDocument[]> {
    const documents = DocumentFactory.createBatch(count);
    
    // In a real implementation, you would save these to the database
    // For now, we'll just return the generated data
    return documents.map(doc => ({ ...doc, userId }));
  }

  static async cleanupTestData(): Promise<void> {
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
}