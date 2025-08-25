import { TestContextManager } from '../../utils/test-helpers';
async function globalTeardown(config) {
    console.log('Starting global teardown...');
    try {
        // Clean up test context
        await TestContextManager.cleanup();
        // Close the API server
        const app = global.__APP__;
        if (app) {
            await app.close();
        }
        console.log('Global teardown completed successfully');
    }
    catch (error) {
        console.error('Error during global teardown:', error);
    }
}
export default globalTeardown;
//# sourceMappingURL=global-teardown.js.map