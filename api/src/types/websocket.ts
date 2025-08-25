import { JobEvent } from './jobs.js';

// WebSocket event types
export type WebSocketEventType = 
  | 'connection'
  | 'disconnect'
  | 'authenticate'
  | 'join_room'
  | 'leave_room'
  | 'job_subscribe'
  | 'job_unsubscribe'
  | 'progress_update'
  | 'error';

// WebSocket message structure
export interface WebSocketMessage<T = any> {
  type: WebSocketEventType;
  data: T;
  timestamp: Date;
  correlationId?: string;
}

// Authentication message
export interface WebSocketAuthMessage {
  token?: string;
  apiKey?: string;
}

// Room subscription message
export interface WebSocketRoomMessage {
  room: string; // jobId, batchId, userId, etc.
}

// Job subscription message
export interface WebSocketJobSubscription {
  jobId: string;
  types?: string[]; // specific event types to subscribe to
}

// Progress update message
export interface WebSocketProgressMessage {
  jobId: string;
  batchId?: string;
  progress: number;
  status: string;
  message?: string;
  currentStep?: string;
  estimatedCompletion?: Date;
}

// Error message
export interface WebSocketErrorMessage {
  code: string;
  message: string;
  details?: any;
}

// WebSocket client info
export interface WebSocketClient {
  id: string;
  userId?: string;
  authenticated: boolean;
  rooms: Set<string>;
  subscriptions: Set<string>;
  connectedAt: Date;
  lastActivity: Date;
}

// WebSocket server events
export type WebSocketServerEvent = 
  | { type: 'client:connected'; clientId: string }
  | { type: 'client:disconnected'; clientId: string }
  | { type: 'client:authenticated'; clientId: string; userId: string }
  | { type: 'room:joined'; clientId: string; room: string }
  | { type: 'room:left'; clientId: string; room: string }
  | { type: 'broadcast'; room: string; message: WebSocketMessage }
  | JobEvent;

// Server-Sent Events data structure
export interface SSEMessage {
  event?: string;
  data: string;
  id?: string;
  retry?: number;
}

// Stream processing events
export type StreamEvent = 
  | { type: 'progress'; data: WebSocketProgressMessage }
  | { type: 'complete'; data: { jobId: string; result: any } }
  | { type: 'error'; data: WebSocketErrorMessage }
  | { type: 'heartbeat'; data: { timestamp: Date } };

// WebSocket connection options
export interface WebSocketConnectionOptions {
  maxConnections?: number;
  pingTimeout?: number;
  pingInterval?: number;
  upgradeTimeout?: number;
  maxHttpBufferSize?: number;
  allowEIO3?: boolean;
  cors?: {
    origin: string | string[];
    methods: string[];
    credentials?: boolean;
  };
}