import { GenericContainer } from 'testcontainers';
import { PrismaClient } from '@prisma/client';
import { createClient } from 'redis';
export async function setupTestEnvironment() {
    console.log('Setting up test environment...');
    // Start PostgreSQL container
    const postgres = await new GenericContainer('postgres:16')
        .withEnvironment({
        POSTGRES_USER: 'test',
        POSTGRES_PASSWORD: 'test',
        POSTGRES_DB: 'rag_test',
    })
        .withExposedPorts(5432)
        .start();
    // Start Redis container
    const redis = await new GenericContainer('redis:7-alpine')
        .withExposedPorts(6379)
        .start();
    // Set environment variables
    const databaseUrl = `postgresql://test:test@${postgres.getHost()}:${postgres.getMappedPort(5432)}/rag_test`;
    const redisUrl = `redis://${redis.getHost()}:${redis.getMappedPort(6379)}`;
    process.env.DATABASE_URL = databaseUrl;
    process.env.REDIS_URL = redisUrl;
    process.env.JWT_SECRET = 'test-jwt-secret-key';
    process.env.NODE_ENV = 'test';
    // Initialize Prisma client
    const prisma = new PrismaClient({
        datasources: {
            db: {
                url: databaseUrl,
            },
        },
    });
    // Initialize Redis client
    const redisClient = createClient({ url: redisUrl });
    await redisClient.connect();
    // Run database migrations
    await runMigrations(prisma);
    const testEnv = {
        postgres,
        redis,
        prisma,
        redisClient,
    };
    global.testEnv = testEnv;
    return testEnv;
}
export async function teardownTestEnvironment() {
    if (global.testEnv) {
        console.log('Tearing down test environment...');
        try {
            await global.testEnv.prisma.$disconnect();
        }
        catch (error) {
            console.warn('Error disconnecting Prisma:', error);
        }
        try {
            await global.testEnv.redisClient.quit();
        }
        catch (error) {
            console.warn('Error disconnecting Redis:', error);
        }
        try {
            await global.testEnv.postgres.stop();
        }
        catch (error) {
            console.warn('Error stopping PostgreSQL container:', error);
        }
        try {
            await global.testEnv.redis.stop();
        }
        catch (error) {
            console.warn('Error stopping Redis container:', error);
        }
    }
}
async function runMigrations(prisma) {
    // Create tables manually for testing since we don't have Prisma migrations yet
    await prisma.$executeRaw `CREATE EXTENSION IF NOT EXISTS "uuid-ossp"`;
    await prisma.$executeRaw `CREATE EXTENSION IF NOT EXISTS "pgcrypto"`;
    // Users table
    await prisma.$executeRaw `
    CREATE TABLE IF NOT EXISTS users (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      email VARCHAR(255) UNIQUE NOT NULL,
      password_hash VARCHAR(255) NOT NULL,
      role VARCHAR(20) NOT NULL DEFAULT 'user',
      is_active BOOLEAN NOT NULL DEFAULT true,
      email_verified BOOLEAN NOT NULL DEFAULT false,
      created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
      last_login TIMESTAMP WITH TIME ZONE,
      login_count INTEGER DEFAULT 0
    )
  `;
    // API keys table
    await prisma.$executeRaw `
    CREATE TABLE IF NOT EXISTS api_keys (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      key_hash VARCHAR(255) NOT NULL UNIQUE,
      key_prefix VARCHAR(20) NOT NULL,
      name VARCHAR(100) NOT NULL,
      scopes JSONB NOT NULL DEFAULT '[]',
      is_active BOOLEAN NOT NULL DEFAULT true,
      expires_at TIMESTAMP WITH TIME ZONE,
      last_used TIMESTAMP WITH TIME ZONE,
      usage_count INTEGER DEFAULT 0,
      created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    )
  `;
    // Query history table
    await prisma.$executeRaw `
    CREATE TABLE IF NOT EXISTS queries (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      query_text TEXT NOT NULL,
      query_type VARCHAR(20) NOT NULL DEFAULT 'text',
      mode VARCHAR(20) NOT NULL DEFAULT 'mix',
      result_text TEXT,
      sources JSONB DEFAULT '[]',
      metadata JSONB DEFAULT '{}',
      processing_time_ms INTEGER,
      tokens_used INTEGER DEFAULT 0,
      cost_usd DECIMAL(10,6) DEFAULT 0,
      ip_address INET,
      user_agent TEXT,
      created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    )
  `;
    // Job status table
    await prisma.$executeRaw `
    CREATE TABLE IF NOT EXISTS job_status (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      job_id VARCHAR(255) NOT NULL UNIQUE,
      job_type VARCHAR(50) NOT NULL,
      status VARCHAR(20) NOT NULL DEFAULT 'pending',
      progress INTEGER DEFAULT 0,
      result JSONB,
      error_message TEXT,
      started_at TIMESTAMP WITH TIME ZONE,
      completed_at TIMESTAMP WITH TIME ZONE,
      created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    )
  `;
    // Documents table
    await prisma.$executeRaw `
    CREATE TABLE IF NOT EXISTS documents (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      filename VARCHAR(255) NOT NULL,
      original_name VARCHAR(255) NOT NULL,
      file_path VARCHAR(500) NOT NULL,
      file_size BIGINT NOT NULL,
      mime_type VARCHAR(100) NOT NULL,
      checksum VARCHAR(64) NOT NULL,
      status VARCHAR(20) NOT NULL DEFAULT 'uploaded',
      processing_metadata JSONB DEFAULT '{}',
      created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    )
  `;
    // Refresh tokens table
    await prisma.$executeRaw `
    CREATE TABLE IF NOT EXISTS refresh_tokens (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      token VARCHAR(64) NOT NULL UNIQUE,
      expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
      revoked BOOLEAN NOT NULL DEFAULT false,
      created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    )
  `;
    // Create indexes
    await prisma.$executeRaw `CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)`;
    await prisma.$executeRaw `CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active, role)`;
    await prisma.$executeRaw `CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash)`;
    await prisma.$executeRaw `CREATE INDEX IF NOT EXISTS idx_api_keys_user_active ON api_keys(user_id, is_active)`;
    await prisma.$executeRaw `CREATE INDEX IF NOT EXISTS idx_queries_user_created ON queries(user_id, created_at DESC)`;
    await prisma.$executeRaw `CREATE INDEX IF NOT EXISTS idx_queries_type_mode ON queries(query_type, mode)`;
    await prisma.$executeRaw `CREATE INDEX IF NOT EXISTS idx_job_status_user ON job_status(user_id, created_at DESC)`;
    await prisma.$executeRaw `CREATE INDEX IF NOT EXISTS idx_job_status_job_id ON job_status(job_id)`;
    await prisma.$executeRaw `CREATE INDEX IF NOT EXISTS idx_documents_user ON documents(user_id, created_at DESC)`;
    await prisma.$executeRaw `CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status)`;
    await prisma.$executeRaw `CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id)`;
    await prisma.$executeRaw `CREATE INDEX IF NOT EXISTS idx_refresh_tokens_token ON refresh_tokens(token)`;
}
// Setup and teardown hooks
beforeAll(async () => {
    await setupTestEnvironment();
}, 60000);
afterAll(async () => {
    await teardownTestEnvironment();
}, 30000);
// Clean up between tests
beforeEach(async () => {
    if (global.testEnv?.prisma) {
        // Clear all tables but keep schema
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
});
// Jest custom matchers
expect.extend({
    toBeUUID(received) {
        const pass = typeof received === 'string' &&
            /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(received);
        if (pass) {
            return {
                message: () => `expected ${received} not to be a valid UUID`,
                pass: true,
            };
        }
        else {
            return {
                message: () => `expected ${received} to be a valid UUID`,
                pass: false,
            };
        }
    },
    toBeISODate(received) {
        const pass = typeof received === 'string' &&
            !isNaN(Date.parse(received));
        if (pass) {
            return {
                message: () => `expected ${received} not to be a valid ISO date`,
                pass: true,
            };
        }
        else {
            return {
                message: () => `expected ${received} to be a valid ISO date`,
                pass: false,
            };
        }
    },
});
//# sourceMappingURL=setup.js.map