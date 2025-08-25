/**
 * Jest setup file for additional configuration and global test utilities
 */
declare global {
    namespace jest {
        interface Matchers<R> {
            toBeUUID(): R;
            toBeISODate(): R;
            toBeValidEmail(): R;
            toBeValidApiKey(): R;
            toHaveValidStructure(expectedStructure: any): R;
            toBeWithinRange(min: number, max: number): R;
        }
    }
}
export declare const measurePerformance: (name: string) => () => number;
export declare const getMemoryUsage: () => {
    rss: number;
    heapTotal: number;
    heapUsed: number;
    external: number;
};
export declare const cleanupTestData: () => Promise<void>;
declare const _default: {};
export default _default;
//# sourceMappingURL=jest-setup.d.ts.map