import { FullConfig } from '@playwright/test';
import { TestContextManager } from '../../utils/test-helpers';

async function globalTeardown(config: FullConfig) {
  console.log('Starting global teardown...');
  
  try {
    // Clean up test context
    await TestContextManager.cleanup();
    
    // Close the API server
    const app = (global as any).__APP__;
    if (app) {
      await app.close();
    }
    
    console.log('Global teardown completed successfully');
  } catch (error) {
    console.error('Error during global teardown:', error);
  }
}

export default globalTeardown;