export default {
  preset: 'ts-jest/presets/default-esm',
  testEnvironment: 'node',
  extensionsToTreatAsEsm: ['.ts'],
  moduleNameMapping: {
    '^@/(.*)$': '<rootDir>/src/$1',
  },
  transform: {
    '^.+\\.ts$': [
      'ts-jest',
      {
        useESM: true,
        tsconfig: {
          module: 'ESNext',
        },
      },
    ],
  },
  collectCoverageFrom: [
    'src/**/*.{ts,js}',
    '!src/**/*.test.{ts,js}',
    '!src/**/*.spec.{ts,js}',
    '!src/types/**/*',
    '!src/server.ts',
  ],
  coverageDirectory: 'coverage',
  coverageReporters: ['text', 'lcov', 'html', 'json-summary'],
  coverageThreshold: {
    global: {
      branches: 85,
      functions: 85,
      lines: 85,
      statements: 85,
    },
    // Specific thresholds for critical modules
    './src/services/': {
      branches: 90,
      functions: 90,
      lines: 90,
      statements: 90,
    },
    './src/routes/': {
      branches: 80,
      functions: 80,
      lines: 80,
      statements: 80,
    },
  },
  testMatch: ['**/__tests__/**/*.{ts,js}', '**/?(*.)+(spec|test).{ts,js}'],
  testPathIgnorePatterns: ['/node_modules/', '/dist/', '/test-results/'],
  setupFilesAfterEnv: ['<rootDir>/tests/setup.ts'],
  testTimeout: 60000, // Increased for E2E tests
  maxWorkers: process.env.CI ? 1 : '50%',
  
  // Test environments for different test types
  projects: [
    {
      displayName: 'unit',
      testMatch: ['<rootDir>/tests/unit/**/*.test.ts'],
      testTimeout: 10000,
    },
    {
      displayName: 'integration', 
      testMatch: ['<rootDir>/tests/integration/**/*.test.ts'],
      testTimeout: 30000,
    },
    {
      displayName: 'e2e',
      testMatch: ['<rootDir>/tests/e2e/**/*.test.ts'],
      testTimeout: 60000,
      maxWorkers: 1, // E2E tests should run sequentially
    },
    {
      displayName: 'security',
      testMatch: ['<rootDir>/tests/security/**/*.test.ts'], 
      testTimeout: 30000,
    },
  ],

  // Global setup and teardown
  globalSetup: '<rootDir>/tests/global-setup.ts',
  globalTeardown: '<rootDir>/tests/global-teardown.ts',

  // Test result processors
  reporters: [
    'default',
    ['jest-html-reporters', {
      publicPath: './test-results',
      filename: 'jest-report.html',
      expand: true,
      hideIcon: false,
      pageTitle: 'RAG-Anything API Test Report'
    }],
    ['jest-junit', {
      outputDirectory: './test-results',
      outputName: 'junit.xml',
      ancestorSeparator: ' › ',
      uniqueOutputName: 'false',
      suiteNameTemplate: '{displayName} › {filepath}',
      classNameTemplate: '{classname}',
      titleTemplate: '{title}'
    }],
  ],

  // Performance monitoring
  slowTestThreshold: 5,
  
  // Error handling
  errorOnDeprecated: true,
  
  // Verbose output for debugging
  verbose: process.env.CI ? false : true,
  
  // Module resolution
  moduleDirectories: ['node_modules', '<rootDir>/src', '<rootDir>/tests'],
  
  // File watching
  watchPathIgnorePatterns: ['/node_modules/', '/dist/', '/coverage/', '/test-results/'],
  
  // Clear mocks between tests
  clearMocks: true,
  
  // Restore mocks after each test
  restoreMocks: true,
  
  // Fail fast in CI
  bail: process.env.CI ? 1 : 0,

  // Additional Jest configuration for better error reporting
  testLocationInResults: true,
  
  // Custom matchers and utilities
  setupFiles: ['<rootDir>/tests/jest-setup.ts'],
};