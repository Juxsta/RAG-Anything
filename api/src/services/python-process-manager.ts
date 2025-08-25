import { spawn, ChildProcess } from 'child_process';
import { EventEmitter } from 'events';
import path from 'path';
import { fileURLToPath } from 'url';

import { config } from '@/config/index.js';
import { logger, logError, logJobEvent } from '@/utils/logger.js';
import { PythonProcessError } from '@/utils/errors.js';
import { encrypt } from '@/utils/crypto.js';

// Get current directory for resolving Python worker script
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Request/Response interfaces
interface PythonRequest {
  id: string;
  method: string;
  params?: Record<string, any>;
}

interface PythonResponse {
  id: string;
  success: boolean;
  result?: any;
  error?: {
    code: string;
    message: string;
    details?: any;
    traceback?: string;
  };
}

// Process state
interface ProcessInfo {
  id: string;
  process: ChildProcess;
  busy: boolean;
  lastUsed: Date;
  requests: Map<string, {
    resolve: (value: any) => void;
    reject: (error: any) => void;
    timeout: NodeJS.Timeout;
  }>;
}

/**
 * Python Process Manager
 * Manages a pool of Python worker processes for RAG-Anything operations
 */
export class PythonProcessManager extends EventEmitter {
  private processes: Map<string, ProcessInfo> = new Map();
  private processQueue: string[] = [];
  private maxProcesses: number = config.PYTHON_MAX_PROCESSES;
  private processTimeout: number = config.PYTHON_PROCESS_TIMEOUT;
  private pythonExecutable: string = config.PYTHON_EXECUTABLE;
  private workerScript: string;
  private initialized: boolean = false;
  private shuttingDown: boolean = false;

  constructor() {
    super();
    
    // Resolve worker script path
    this.workerScript = path.resolve(__dirname, '../../scripts/python_worker.py');
    
    // Setup cleanup on process exit
    process.on('exit', () => this.cleanup());
    process.on('SIGINT', () => this.gracefulShutdown());
    process.on('SIGTERM', () => this.gracefulShutdown());
  }

  /**
   * Initialize the process manager
   */
  async initialize(initConfig?: Record<string, any>): Promise<void> {
    if (this.initialized) {
      return;
    }

    logger.info('Initializing Python process manager', {
      max_processes: this.maxProcesses,
      worker_script: this.workerScript,
      python_executable: this.pythonExecutable,
    });

    try {
      // Create initial process
      const processId = await this.createProcess();
      
      // Initialize RAG-Anything in the first process
      await this.executeMethod('initialize', initConfig || {}, processId);
      
      this.initialized = true;
      this.emit('initialized');
      
      logger.info('Python process manager initialized successfully');
      
    } catch (error) {
      logError(logger, error as Error, 'Failed to initialize Python process manager');
      throw new PythonProcessError('Process manager initialization failed', {
        error: error.message,
      });
    }
  }

  /**
   * Create a new Python worker process
   */
  private async createProcess(): Promise<string> {
    if (this.processes.size >= this.maxProcesses) {
      throw new PythonProcessError('Maximum number of processes reached');
    }

    const processId = encrypt.uuid();
    
    logger.debug('Creating new Python worker process', { process_id: processId });

    try {
      const childProcess = spawn(this.pythonExecutable, [this.workerScript], {
        stdio: ['pipe', 'pipe', 'pipe'],
        env: {
          ...process.env,
          PYTHONPATH: path.join(__dirname, '../../../'),
          PYTHONUNBUFFERED: '1',
        },
      });

      const processInfo: ProcessInfo = {
        id: processId,
        process: childProcess,
        busy: false,
        lastUsed: new Date(),
        requests: new Map(),
      };

      this.processes.set(processId, processInfo);
      this.processQueue.push(processId);

      // Setup process event handlers
      this.setupProcessHandlers(processInfo);

      // Wait for process to be ready
      await this.waitForProcessReady(processInfo);

      logger.info('Python worker process created successfully', { process_id: processId });
      
      return processId;

    } catch (error) {
      logError(logger, error as Error, 'Failed to create Python worker process');
      throw new PythonProcessError('Process creation failed', {
        process_id: processId,
        error: error.message,
      });
    }
  }

  /**
   * Setup event handlers for a process
   */
  private setupProcessHandlers(processInfo: ProcessInfo): void {
    const { id, process: childProcess } = processInfo;

    // Handle stdout messages (responses)
    let buffer = '';
    childProcess.stdout?.on('data', (data: Buffer) => {
      buffer += data.toString();
      
      // Process complete lines
      const lines = buffer.split('\n');
      buffer = lines.pop() || ''; // Keep incomplete line in buffer
      
      for (const line of lines) {
        if (line.trim()) {
          try {
            const response: PythonResponse = JSON.parse(line);
            this.handleProcessResponse(id, response);
          } catch (error) {
            logger.warn('Failed to parse Python process response', {
              process_id: id,
              line,
              error: error.message,
            });
          }
        }
      }
    });

    // Handle stderr messages (logs)
    childProcess.stderr?.on('data', (data: Buffer) => {
      const message = data.toString().trim();
      logger.debug('Python process stderr', {
        process_id: id,
        message,
      });
    });

    // Handle process exit
    childProcess.on('exit', (code, signal) => {
      logger.warn('Python process exited', {
        process_id: id,
        exit_code: code,
        signal,
      });
      
      this.handleProcessExit(id, code, signal);
    });

    // Handle process errors
    childProcess.on('error', (error) => {
      logError(logger, error, 'Python process error', { process_id: id });
      this.handleProcessError(id, error);
    });
  }

  /**
   * Wait for process to be ready
   */
  private async waitForProcessReady(processInfo: ProcessInfo): Promise<void> {
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new PythonProcessError('Process startup timeout'));
      }, 10000); // 10 second timeout

      // Send a simple health check
      const healthRequest: PythonRequest = {
        id: encrypt.uuid(),
        method: 'health_check',
      };

      const requestInfo = {
        resolve: () => {
          clearTimeout(timeout);
          resolve();
        },
        reject: (error: any) => {
          clearTimeout(timeout);
          reject(error);
        },
        timeout,
      };

      processInfo.requests.set(healthRequest.id, requestInfo);
      
      const message = JSON.stringify(healthRequest) + '\n';
      processInfo.process.stdin?.write(message);
    });
  }

  /**
   * Handle response from Python process
   */
  private handleProcessResponse(processId: string, response: PythonResponse): void {
    const processInfo = this.processes.get(processId);
    if (!processInfo) {
      return;
    }

    const requestInfo = processInfo.requests.get(response.id);
    if (!requestInfo) {
      logger.warn('Received response for unknown request', {
        process_id: processId,
        request_id: response.id,
      });
      return;
    }

    // Clean up request tracking
    processInfo.requests.delete(response.id);
    clearTimeout(requestInfo.timeout);

    // Mark process as not busy
    processInfo.busy = false;
    processInfo.lastUsed = new Date();

    // Resolve or reject the promise
    if (response.success) {
      requestInfo.resolve(response.result || response);
    } else {
      const error = new PythonProcessError(
        response.error?.message || 'Python process error',
        {
          code: response.error?.code,
          details: response.error?.details,
          traceback: response.error?.traceback,
        }
      );
      requestInfo.reject(error);
    }
  }

  /**
   * Handle process exit
   */
  private handleProcessExit(processId: string, code: number | null, signal: NodeJS.Signals | null): void {
    const processInfo = this.processes.get(processId);
    if (!processInfo) {
      return;
    }

    // Reject all pending requests
    for (const [requestId, requestInfo] of processInfo.requests) {
      clearTimeout(requestInfo.timeout);
      requestInfo.reject(new PythonProcessError('Process exited unexpectedly', {
        exit_code: code,
        signal,
      }));
    }

    // Remove process from pool
    this.processes.delete(processId);
    const queueIndex = this.processQueue.indexOf(processId);
    if (queueIndex > -1) {
      this.processQueue.splice(queueIndex, 1);
    }

    this.emit('processExit', { processId, code, signal });

    // Create replacement process if not shutting down
    if (!this.shuttingDown && this.initialized) {
      setTimeout(() => {
        this.createProcess().catch(error => {
          logError(logger, error, 'Failed to create replacement process');
        });
      }, 1000); // Wait 1 second before recreating
    }
  }

  /**
   * Handle process error
   */
  private handleProcessError(processId: string, error: Error): void {
    const processInfo = this.processes.get(processId);
    if (!processInfo) {
      return;
    }

    // Reject all pending requests
    for (const [requestId, requestInfo] of processInfo.requests) {
      clearTimeout(requestInfo.timeout);
      requestInfo.reject(new PythonProcessError('Process error', { originalError: error.message }));
    }

    this.emit('processError', { processId, error });
  }

  /**
   * Get available process for execution
   */
  private getAvailableProcess(): string | null {
    // Find non-busy process
    for (const processId of this.processQueue) {
      const processInfo = this.processes.get(processId);
      if (processInfo && !processInfo.busy) {
        return processId;
      }
    }

    // All processes are busy
    return null;
  }

  /**
   * Execute a method on a Python process
   */
  async executeMethod(
    method: string,
    params: Record<string, any> = {},
    preferredProcessId?: string
  ): Promise<any> {
    if (!this.initialized) {
      throw new PythonProcessError('Process manager not initialized');
    }

    if (this.shuttingDown) {
      throw new PythonProcessError('Process manager is shutting down');
    }

    // Get process ID
    let processId = preferredProcessId;
    if (!processId || !this.processes.has(processId)) {
      processId = this.getAvailableProcess();
    }

    // Create new process if none available
    if (!processId) {
      if (this.processes.size < this.maxProcesses) {
        processId = await this.createProcess();
        // Initialize the new process
        await this.executeMethod('initialize', {}, processId);
      } else {
        throw new PythonProcessError('No available processes and maximum limit reached');
      }
    }

    const processInfo = this.processes.get(processId);
    if (!processInfo) {
      throw new PythonProcessError('Process not found');
    }

    // Mark process as busy
    processInfo.busy = true;

    const requestId = encrypt.uuid();
    const request: PythonRequest = {
      id: requestId,
      method,
      params,
    };

    logger.debug('Executing Python method', {
      process_id: processId,
      request_id: requestId,
      method,
      params: Object.keys(params),
    });

    return new Promise((resolve, reject) => {
      // Setup timeout
      const timeout = setTimeout(() => {
        processInfo.requests.delete(requestId);
        processInfo.busy = false;
        reject(new PythonProcessError(`Method ${method} timed out`, {
          timeout_ms: this.processTimeout,
        }));
      }, this.processTimeout);

      // Store request info
      processInfo.requests.set(requestId, {
        resolve,
        reject,
        timeout,
      });

      // Send request to process
      const message = JSON.stringify(request) + '\n';
      processInfo.process.stdin?.write(message, (error) => {
        if (error) {
          processInfo.requests.delete(requestId);
          clearTimeout(timeout);
          processInfo.busy = false;
          reject(new PythonProcessError('Failed to send request to process', {
            error: error.message,
          }));
        }
      });
    });
  }

  /**
   * Process a document
   */
  async processDocument(filePath: string, docId: string, options: Record<string, any> = {}): Promise<any> {
    const startTime = Date.now();
    
    try {
      const result = await this.executeMethod('process_document', {
        file_path: filePath,
        doc_id: docId,
        options,
      });
      
      const duration = Date.now() - startTime;
      logJobEvent(logger, 'completed', docId, 'document_processing', duration);
      
      return result;
      
    } catch (error) {
      const duration = Date.now() - startTime;
      logJobEvent(logger, 'failed', docId, 'document_processing', duration, error as Error);
      throw error;
    }
  }

  /**
   * Process content list
   */
  async processContentList(
    contentList: any[],
    filePath: string = '',
    docId: string,
    displayStats: boolean = true
  ): Promise<any> {
    return await this.executeMethod('process_content_list', {
      content_list: contentList,
      file_path: filePath,
      doc_id: docId,
      display_stats: displayStats,
    });
  }

  /**
   * Execute text query
   */
  async executeQuery(query: string, mode: string = 'mix', vlmEnhanced: boolean = false): Promise<any> {
    return await this.executeMethod('execute_query', {
      query,
      mode,
      vlm_enhanced: vlmEnhanced,
    });
  }

  /**
   * Execute multimodal query
   */
  async executeMultimodalQuery(
    query: string,
    multimodalContent: any[] = [],
    mode: string = 'mix'
  ): Promise<any> {
    return await this.executeMethod('execute_multimodal_query', {
      query,
      multimodal_content: multimodalContent,
      mode,
    });
  }

  /**
   * Get system status
   */
  async getStatus(): Promise<any> {
    return await this.executeMethod('get_status');
  }

  /**
   * Perform health check
   */
  async healthCheck(): Promise<any> {
    return await this.executeMethod('health_check');
  }

  /**
   * Graceful shutdown
   */
  async gracefulShutdown(): Promise<void> {
    if (this.shuttingDown) {
      return;
    }

    this.shuttingDown = true;
    logger.info('Starting Python process manager shutdown');

    const shutdownPromises: Promise<any>[] = [];

    // Send shutdown to all processes
    for (const [processId, processInfo] of this.processes) {
      shutdownPromises.push(
        this.executeMethod('shutdown', {}, processId).catch(error => {
          logger.warn('Failed to shutdown process gracefully', {
            process_id: processId,
            error: error.message,
          });
        })
      );
    }

    // Wait for all shutdowns to complete or timeout
    try {
      await Promise.race([
        Promise.all(shutdownPromises),
        new Promise(resolve => setTimeout(resolve, 5000)), // 5 second timeout
      ]);
    } catch (error) {
      logger.warn('Some processes failed to shutdown gracefully');
    }

    // Force kill remaining processes
    this.cleanup();
    
    this.initialized = false;
    this.emit('shutdown');
    
    logger.info('Python process manager shutdown completed');
  }

  /**
   * Cleanup processes
   */
  private cleanup(): void {
    for (const [processId, processInfo] of this.processes) {
      try {
        if (!processInfo.process.killed) {
          processInfo.process.kill('SIGTERM');
        }
      } catch (error) {
        // Process might already be dead
      }
    }
    
    this.processes.clear();
    this.processQueue.length = 0;
  }
}

// Singleton instance
export const pythonProcessManager = new PythonProcessManager();