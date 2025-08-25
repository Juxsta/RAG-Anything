import { setupTestEnvironment } from './setup';

/**
 * Global setup for all Jest tests
 * Runs once before all test suites
 */
export default async function globalSetup(): Promise<void> {
  console.log('🚀 Starting global test setup...');
  
  try {
    // Set test environment variables
    process.env.NODE_ENV = 'test';
    process.env.LOG_LEVEL = 'error'; // Minimize logging during tests
    process.env.JWT_SECRET = process.env.JWT_SECRET || 'test-jwt-secret-key-for-testing';
    
    // Setup test environment if not already done
    if (!global.testEnv) {
      await setupTestEnvironment();
    }
    
    console.log('✅ Global test setup completed successfully');
  } catch (error) {
    console.error('❌ Global test setup failed:', error);
    process.exit(1);
  }
}