import { teardownTestEnvironment } from './setup';
/**
 * Global teardown for all Jest tests
 * Runs once after all test suites complete
 */
export default async function globalTeardown() {
    console.log('🧹 Starting global test teardown...');
    try {
        // Teardown test environment
        await teardownTestEnvironment();
        // Clean up any remaining resources
        if (global.gc) {
            global.gc(); // Force garbage collection if available
        }
        console.log('✅ Global test teardown completed successfully');
    }
    catch (error) {
        console.error('❌ Global test teardown failed:', error);
        // Don't exit with error in teardown to avoid masking test failures
    }
}
//# sourceMappingURL=global-teardown.js.map