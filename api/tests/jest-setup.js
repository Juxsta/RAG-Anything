/**
 * Jest setup file for additional configuration and global test utilities
 */
// Increase test timeout for CI environments
if (process.env.CI) {
    jest.setTimeout(120000); // 2 minutes for CI
}
else {
    jest.setTimeout(60000); // 1 minute for local development
}
// Custom Jest matchers
expect.extend({
    toBeValidEmail(received) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        const pass = typeof received === 'string' && emailRegex.test(received);
        if (pass) {
            return {
                message: () => `expected ${received} not to be a valid email`,
                pass: true,
            };
        }
        else {
            return {
                message: () => `expected ${received} to be a valid email`,
                pass: false,
            };
        }
    },
    toBeValidApiKey(received) {
        const apiKeyRegex = /^rag_[a-zA-Z0-9]{64}$/;
        const pass = typeof received === 'string' && apiKeyRegex.test(received);
        if (pass) {
            return {
                message: () => `expected ${received} not to be a valid API key`,
                pass: true,
            };
        }
        else {
            return {
                message: () => `expected ${received} to be a valid API key format (rag_xxxxx)`,
                pass: false,
            };
        }
    },
    toHaveValidStructure(received, expectedStructure) {
        const checkStructure = (obj, structure, path = '') => {
            if (typeof structure !== 'object' || structure === null) {
                const pass = typeof obj === typeof structure;
                return {
                    pass,
                    message: pass
                        ? `Expected ${path} not to be of type ${typeof structure}`
                        : `Expected ${path} to be of type ${typeof structure}, got ${typeof obj}`,
                };
            }
            if (Array.isArray(structure)) {
                if (!Array.isArray(obj)) {
                    return {
                        pass: false,
                        message: `Expected ${path} to be an array, got ${typeof obj}`,
                    };
                }
                if (structure.length > 0) {
                    const itemResult = checkStructure(obj[0], structure[0], `${path}[0]`);
                    if (!itemResult.pass) {
                        return itemResult;
                    }
                }
                return { pass: true, message: '' };
            }
            if (typeof obj !== 'object' || obj === null) {
                return {
                    pass: false,
                    message: `Expected ${path} to be an object, got ${typeof obj}`,
                };
            }
            for (const key in structure) {
                const currentPath = path ? `${path}.${key}` : key;
                if (!(key in obj)) {
                    return {
                        pass: false,
                        message: `Expected ${currentPath} to exist`,
                    };
                }
                const result = checkStructure(obj[key], structure[key], currentPath);
                if (!result.pass) {
                    return result;
                }
            }
            return { pass: true, message: '' };
        };
        const result = checkStructure(received, expectedStructure);
        return {
            pass: result.pass,
            message: () => result.message,
        };
    },
    toBeWithinRange(received, min, max) {
        const pass = typeof received === 'number' && received >= min && received <= max;
        if (pass) {
            return {
                message: () => `expected ${received} not to be within range ${min}-${max}`,
                pass: true,
            };
        }
        else {
            return {
                message: () => `expected ${received} to be within range ${min}-${max}`,
                pass: false,
            };
        }
    },
});
// Global error handler for unhandled promises
process.on('unhandledRejection', (reason, promise) => {
    console.error('Unhandled Rejection at:', promise, 'reason:', reason);
    // Don't exit the process in tests
});
// Global error handler for uncaught exceptions  
process.on('uncaughtException', (error) => {
    console.error('Uncaught Exception:', error);
    // Don't exit the process in tests
});
// Mock console methods in CI to reduce noise
if (process.env.CI) {
    global.console = {
        ...console,
        debug: jest.fn(),
        log: jest.fn(),
        info: jest.fn(),
        warn: jest.fn(),
        error: console.error, // Keep errors visible
    };
}
// Set up fake timers for tests that need them
global.beforeEach(() => {
    // Reset any fake timers before each test
    if (jest.isMockFunction(setTimeout)) {
        jest.useRealTimers();
    }
});
// Clean up after each test
global.afterEach(() => {
    // Restore all mocks
    jest.restoreAllMocks();
    // Clear all timers
    if (jest.isMockFunction(setTimeout)) {
        jest.useRealTimers();
    }
});
// Performance monitoring utilities
export const measurePerformance = (name) => {
    const start = process.hrtime.bigint();
    return () => {
        const end = process.hrtime.bigint();
        const duration = Number(end - start) / 1000000; // Convert to milliseconds
        console.log(`[Performance] ${name}: ${duration.toFixed(2)}ms`);
        return duration;
    };
};
// Memory usage monitoring
export const getMemoryUsage = () => {
    const usage = process.memoryUsage();
    return {
        rss: Math.round(usage.rss / 1024 / 1024), // MB
        heapTotal: Math.round(usage.heapTotal / 1024 / 1024), // MB
        heapUsed: Math.round(usage.heapUsed / 1024 / 1024), // MB
        external: Math.round(usage.external / 1024 / 1024), // MB
    };
};
// Test data cleanup utility
export const cleanupTestData = async () => {
    if (global.testEnv) {
        try {
            if (global.testEnv.prisma) {
                // Clean up in dependency order
                await global.testEnv.prisma.$executeRaw `TRUNCATE TABLE refresh_tokens CASCADE`;
                await global.testEnv.prisma.$executeRaw `TRUNCATE TABLE job_status CASCADE`;
                await global.testEnv.prisma.$executeRaw `TRUNCATE TABLE queries CASCADE`;
                await global.testEnv.prisma.$executeRaw `TRUNCATE TABLE documents CASCADE`;
                await global.testEnv.prisma.$executeRaw `TRUNCATE TABLE api_keys CASCADE`;
                await global.testEnv.prisma.$executeRaw `TRUNCATE TABLE users CASCADE`;
            }
            if (global.testEnv.redisClient) {
                await global.testEnv.redisClient.flushAll();
            }
        }
        catch (error) {
            console.error('Error during test data cleanup:', error);
        }
    }
};
// Export for use in tests
export default {};
//# sourceMappingURL=jest-setup.js.map