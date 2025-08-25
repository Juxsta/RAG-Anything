import { chromium, FullConfig } from '@playwright/test';
import { TestContextManager } from '../../utils/test-helpers';
import { build } from '@/app';

async function globalSetup(config: FullConfig) {
  console.log('Starting global setup...');
  
  // Start the API server for testing
  const app = await build({ logger: false });
  await app.ready();
  
  // Create test context
  const context = await TestContextManager.createContext(app);
  
  // Setup browser for authentication
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  try {
    // Navigate to login page (if you have a web UI)
    // For API-only testing, we'll just prepare the auth state
    await page.goto('http://localhost:3000/api/v1/health');
    
    // Store authentication state
    await page.context().storageState({ 
      path: 'test-results/auth-state.json' 
    });
    
    console.log('Global setup completed successfully');
  } finally {
    await browser.close();
  }
  
  // Store app instance for cleanup
  (global as any).__APP__ = app;
}

export default globalSetup;