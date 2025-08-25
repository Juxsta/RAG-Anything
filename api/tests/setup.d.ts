import { StartedTestContainer } from 'testcontainers';
import { PrismaClient } from '@prisma/client';
import { RedisClientType } from 'redis';
export interface TestEnvironment {
    postgres: StartedTestContainer;
    redis: StartedTestContainer;
    prisma: PrismaClient;
    redisClient: RedisClientType;
}
declare global {
    var testEnv: TestEnvironment;
}
export declare function setupTestEnvironment(): Promise<TestEnvironment>;
export declare function teardownTestEnvironment(): Promise<void>;
declare global {
    namespace jest {
        interface Matchers<R> {
            toBeUUID(): R;
            toBeISODate(): R;
        }
    }
}
//# sourceMappingURL=setup.d.ts.map