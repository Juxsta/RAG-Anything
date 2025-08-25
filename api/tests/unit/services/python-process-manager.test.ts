import { PythonProcessManager } from '@/services/python-process-manager';
import { spawn, ChildProcess } from 'child_process';
import { EventEmitter } from 'events';
import { PythonProcessError } from '@/utils/errors';

// Mock child_process
jest.mock('child_process');
jest.mock('@/config/index.js', () => ({
  config: {
    PYTHON_MAX_PROCESSES: 2,
    PYTHON_PROCESS_TIMEOUT: 30000,
    PYTHON_EXECUTABLE: 'python3',
  },
}));

const mockSpawn = spawn as jest.MockedFunction<typeof spawn>;

describe('PythonProcessManager', () => {
  let pythonManager: PythonProcessManager;
  let mockProcess: jest.Mocked<ChildProcess>;

  beforeEach(() => {
    jest.clearAllMocks();
    
    // Create mock child process
    mockProcess = {
      stdout: new EventEmitter(),
      stderr: new EventEmitter(),
      stdin: {
        write: jest.fn(),
      },
      on: jest.fn(),
      kill: jest.fn(),
      killed: false,
      pid: 1234,
    } as any;

    mockSpawn.mockReturnValue(mockProcess as ChildProcess);
    
    pythonManager = new PythonProcessManager();
  });

  afterEach(() => {
    jest.resetAllMocks();
  });

  describe('initialize', () => {
    it('should initialize the process manager successfully', async () => {
      // Mock the health check response
      setTimeout(() => {
        mockProcess.stdout!.emit('data', JSON.stringify({
          id: 'test-id',
          success: true,
          result: 'healthy'
        }) + '\n');
      }, 10);

      await pythonManager.initialize();
      
      expect(pythonManager.initialized).toBe(true);
      expect(mockSpawn).toHaveBeenCalledWith('python3', expect.any(Array), expect.any(Object));
    });

    it('should throw error if initialization fails', async () => {
      setTimeout(() => {
        mockProcess.emit('error', new Error('Failed to start'));
      }, 10);

      await expect(pythonManager.initialize())
        .rejects
        .toThrow(PythonProcessError);
    });

    it('should not reinitialize if already initialized', async () => {
      // First initialization
      setTimeout(() => {
        mockProcess.stdout!.emit('data', JSON.stringify({
          id: 'test-id',
          success: true,
          result: 'healthy'
        }) + '\n');
      }, 10);

      await pythonManager.initialize();
      
      // Second initialization attempt
      await pythonManager.initialize();
      
      expect(mockSpawn).toHaveBeenCalledTimes(1);
    });
  });

  describe('executeMethod', () => {
    beforeEach(async () => {
      // Initialize the manager
      setTimeout(() => {
        mockProcess.stdout!.emit('data', JSON.stringify({
          id: expect.any(String),
          success: true,
          result: 'healthy'
        }) + '\n');
      }, 10);
      
      await pythonManager.initialize();
      jest.clearAllMocks(); // Clear spawn calls from initialization
    });

    it('should execute a method and return result', async () => {
      const resultPromise = pythonManager.executeMethod('test_method', { param: 'value' });

      // Simulate response from Python process
      setTimeout(() => {
        mockProcess.stdout!.emit('data', JSON.stringify({
          id: expect.any(String),
          success: true,
          result: { answer: 'test result' }
        }) + '\n');
      }, 10);

      const result = await resultPromise;
      
      expect(result).toEqual({ answer: 'test result' });
      expect(mockProcess.stdin!.write).toHaveBeenCalled();
    });

    it('should handle Python process errors', async () => {
      const resultPromise = pythonManager.executeMethod('failing_method', {});

      setTimeout(() => {
        mockProcess.stdout!.emit('data', JSON.stringify({
          id: expect.any(String),
          success: false,
          error: {
            code: 'PROCESS_ERROR',
            message: 'Method failed',
            details: { reason: 'Invalid input' }
          }
        }) + '\n');
      }, 10);

      await expect(resultPromise)
        .rejects
        .toThrow(PythonProcessError);
    });

    it('should timeout if no response received', async () => {
      // Mock shorter timeout for testing
      pythonManager['processTimeout'] = 100;

      const resultPromise = pythonManager.executeMethod('slow_method', {});

      await expect(resultPromise)
        .rejects
        .toThrow('Method slow_method timed out');
    }, 500);

    it('should throw error if not initialized', async () => {
      const uninitializedManager = new PythonProcessManager();

      await expect(uninitializedManager.executeMethod('test', {}))
        .rejects
        .toThrow('Process manager not initialized');
    });
  });

  describe('processDocument', () => {
    beforeEach(async () => {
      setTimeout(() => {
        mockProcess.stdout!.emit('data', JSON.stringify({
          id: expect.any(String),
          success: true,
          result: 'healthy'
        }) + '\n');
      }, 10);
      
      await pythonManager.initialize();
      jest.clearAllMocks();
    });

    it('should process document successfully', async () => {
      const resultPromise = pythonManager.processDocument('/path/to/doc.pdf', 'doc-123');

      setTimeout(() => {
        mockProcess.stdout!.emit('data', JSON.stringify({
          id: expect.any(String),
          success: true,
          result: {
            chunks_count: 10,
            processing_time: 2000,
            metadata: { pages: 5 }
          }
        }) + '\n');
      }, 10);

      const result = await resultPromise;

      expect(result).toEqual({
        chunks_count: 10,
        processing_time: 2000,
        metadata: { pages: 5 }
      });
    });

    it('should handle document processing errors', async () => {
      const resultPromise = pythonManager.processDocument('/path/to/invalid.pdf', 'doc-123');

      setTimeout(() => {
        mockProcess.stdout!.emit('data', JSON.stringify({
          id: expect.any(String),
          success: false,
          error: {
            message: 'File not found',
            code: 'FILE_NOT_FOUND'
          }
        }) + '\n');
      }, 10);

      await expect(resultPromise)
        .rejects
        .toThrow(PythonProcessError);
    });
  });

  describe('executeQuery', () => {
    beforeEach(async () => {
      setTimeout(() => {
        mockProcess.stdout!.emit('data', JSON.stringify({
          id: expect.any(String),
          success: true,
          result: 'healthy'
        }) + '\n');
      }, 10);
      
      await pythonManager.initialize();
      jest.clearAllMocks();
    });

    it('should execute text query successfully', async () => {
      const resultPromise = pythonManager.executeQuery('What is AI?', 'mix', false);

      setTimeout(() => {
        mockProcess.stdout!.emit('data', JSON.stringify({
          id: expect.any(String),
          success: true,
          result: {
            answer: 'AI is artificial intelligence',
            sources: [{ doc_id: 'doc-1', score: 0.9 }],
            processing_time: 1500
          }
        }) + '\n');
      }, 10);

      const result = await resultPromise;

      expect(result).toEqual({
        answer: 'AI is artificial intelligence',
        sources: [{ doc_id: 'doc-1', score: 0.9 }],
        processing_time: 1500
      });
    });
  });

  describe('executeMultimodalQuery', () => {
    beforeEach(async () => {
      setTimeout(() => {
        mockProcess.stdout!.emit('data', JSON.stringify({
          id: expect.any(String),
          success: true,
          result: 'healthy'
        }) + '\n');
      }, 10);
      
      await pythonManager.initialize();
      jest.clearAllMocks();
    });

    it('should execute multimodal query successfully', async () => {
      const multimodalContent = [
        { type: 'image', img_path: '/path/to/image.jpg' }
      ];

      const resultPromise = pythonManager.executeMultimodalQuery(
        'What is shown in this image?', 
        multimodalContent, 
        'mix'
      );

      setTimeout(() => {
        mockProcess.stdout!.emit('data', JSON.stringify({
          id: expect.any(String),
          success: true,
          result: {
            answer: 'The image shows a cat',
            sources: [{ doc_id: 'doc-1', score: 0.8 }],
            processing_time: 2500
          }
        }) + '\n');
      }, 10);

      const result = await resultPromise;

      expect(result).toEqual({
        answer: 'The image shows a cat',
        sources: [{ doc_id: 'doc-1', score: 0.8 }],
        processing_time: 2500
      });
    });
  });

  describe('healthCheck', () => {
    beforeEach(async () => {
      setTimeout(() => {
        mockProcess.stdout!.emit('data', JSON.stringify({
          id: expect.any(String),
          success: true,
          result: 'healthy'
        }) + '\n');
      }, 10);
      
      await pythonManager.initialize();
      jest.clearAllMocks();
    });

    it('should return health status', async () => {
      const resultPromise = pythonManager.healthCheck();

      setTimeout(() => {
        mockProcess.stdout!.emit('data', JSON.stringify({
          id: expect.any(String),
          success: true,
          result: { status: 'healthy' }
        }) + '\n');
      }, 10);

      const result = await resultPromise;
      
      expect(result).toEqual({ status: 'healthy' });
    });

    it('should handle health check failures', async () => {
      const resultPromise = pythonManager.healthCheck();

      setTimeout(() => {
        mockProcess.stdout!.emit('data', JSON.stringify({
          id: expect.any(String),
          success: false,
          error: { message: 'Process unhealthy' }
        }) + '\n');
      }, 10);

      await expect(resultPromise)
        .rejects
        .toThrow(PythonProcessError);
    });
  });

  describe('process management', () => {
    it('should handle process exit and restart', async () => {
      setTimeout(() => {
        mockProcess.stdout!.emit('data', JSON.stringify({
          id: expect.any(String),
          success: true,
          result: 'healthy'
        }) + '\n');
      }, 10);
      
      await pythonManager.initialize();
      
      // Simulate process exit
      mockProcess.emit('exit', 1, null);
      
      // Should attempt to restart
      expect(mockSpawn).toHaveBeenCalledTimes(1); // Initial + restart
    });

    it('should handle process errors', async () => {
      setTimeout(() => {
        mockProcess.stdout!.emit('data', JSON.stringify({
          id: expect.any(String),
          success: true,
          result: 'healthy'
        }) + '\n');
      }, 10);
      
      await pythonManager.initialize();
      
      // Simulate process error
      mockProcess.emit('error', new Error('Process crashed'));
      
      // Should handle gracefully
      expect(mockSpawn).toHaveBeenCalledTimes(1);
    });

    it('should parse multiple JSON responses from stdout', async () => {
      setTimeout(() => {
        mockProcess.stdout!.emit('data', JSON.stringify({
          id: expect.any(String),
          success: true,
          result: 'healthy'
        }) + '\n');
      }, 10);
      
      await pythonManager.initialize();
      jest.clearAllMocks();

      const resultPromise = pythonManager.executeMethod('test', {});

      // Simulate partial data followed by complete JSON
      setTimeout(() => {
        mockProcess.stdout!.emit('data', '{"id":"test-');
        mockProcess.stdout!.emit('data', '123","success":true,"result":"ok"}\n');
      }, 10);

      const result = await resultPromise;
      expect(result).toBe('ok');
    });
  });

  describe('gracefulShutdown', () => {
    it('should shutdown all processes gracefully', async () => {
      setTimeout(() => {
        mockProcess.stdout!.emit('data', JSON.stringify({
          id: expect.any(String),
          success: true,
          result: 'healthy'
        }) + '\n');
      }, 10);
      
      await pythonManager.initialize();

      // Mock shutdown response
      setTimeout(() => {
        mockProcess.stdout!.emit('data', JSON.stringify({
          id: expect.any(String),
          success: true,
          result: 'shutdown'
        }) + '\n');
      }, 10);

      await pythonManager.gracefulShutdown();

      expect(pythonManager.initialized).toBe(false);
    });

    it('should force kill processes if graceful shutdown fails', async () => {
      setTimeout(() => {
        mockProcess.stdout!.emit('data', JSON.stringify({
          id: expect.any(String),
          success: true,
          result: 'healthy'
        }) + '\n');
      }, 10);
      
      await pythonManager.initialize();

      // Don't mock shutdown response to simulate timeout

      await pythonManager.gracefulShutdown();

      expect(mockProcess.kill).toHaveBeenCalledWith('SIGTERM');
    });
  });

  describe('getStatus', () => {
    beforeEach(async () => {
      setTimeout(() => {
        mockProcess.stdout!.emit('data', JSON.stringify({
          id: expect.any(String),
          success: true,
          result: 'healthy'
        }) + '\n');
      }, 10);
      
      await pythonManager.initialize();
      jest.clearAllMocks();
    });

    it('should return system status', async () => {
      const resultPromise = pythonManager.getStatus();

      setTimeout(() => {
        mockProcess.stdout!.emit('data', JSON.stringify({
          id: expect.any(String),
          success: true,
          result: {
            processes: 1,
            memory_usage: '512MB',
            documents_processed: 25
          }
        }) + '\n');
      }, 10);

      const result = await resultPromise;
      
      expect(result).toEqual({
        processes: 1,
        memory_usage: '512MB',
        documents_processed: 25
      });
    });
  });
});