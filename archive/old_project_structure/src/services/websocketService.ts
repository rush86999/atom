#!/usr/bin/env node

/**
 * Atom Project - Phase 1: Chat Interface Foundation
 * Chat WebSocket Client Service

 * CRITICAL IMPLEMENTATION - Week 1
 * Priority: 🔴 HIGH
 * Objective: Build WebSocket client for real-time chat communication
 * Timeline: 32 hours development + 8 hours testing

 * This service provides WebSocket client functionality for the Atom chat interface.
 * It handles real-time messaging, connection management, typing indicators,
 * and integrates with the existing backend WebSocket server.
 */

import { EventEmitter } from 'events';

export interface ChatMessage {
  id: string;
  content: string;
  sender: 'user' | 'ai' | 'system';
  timestamp: Date;
  status: 'sending' | 'sent' | 'delivered' | 'read' | 'error';
  metadata?: {
    intent?: string;
    entities?: any[];
    agent?: string;
    processing_time?: number;
    error?: string;
  };
  userId?: string;
  agentId?: string;
}

export interface TypingIndicator {
  userId: string;
  agentId?: string;
  isTyping: boolean;
  timestamp: Date;
}

export interface AgentStatus {
  agentId: string;
  status: 'online' | 'offline' | 'busy';
  timestamp: Date;
}

export interface ConnectionStatus {
  connected: boolean;
  reconnecting: boolean;
  lastConnected?: Date;
  lastDisconnected?: Date;
  reconnectAttempts: number;
  maxReconnectAttempts: number;
}

export interface ChatWebSocketClientConfig {
  websocketUrl: string;
  userId: string;
  agentId?: string;
  reconnectAttempts?: number;
  reconnectDelay?: number;
  heartbeatInterval?: number;
  connectionTimeout?: number;
  messageTimeout?: number;
}

/**
 * Chat WebSocket Client Service
 * 
 * Provides WebSocket client functionality for real-time chat communication
 * with automatic reconnection, message queuing, and event handling.
 */
export class ChatWebSocketClient extends EventEmitter {
  private ws: WebSocket | null = null;
  private config: Required<ChatWebSocketClientConfig>;
  private connectionStatus: ConnectionStatus = {
    connected: false,
    reconnecting: false,
    reconnectAttempts: 0,
    maxReconnectAttempts: 5
  };
  private messageQueue: ChatMessage[] = [];
  private heartbeatInterval: NodeJS.Timeout | null = null;
  private reconnectTimeout: NodeJS.Timeout | null = null;
  private connectionTimeout: NodeJS.Timeout | null = null;
  private pendingMessages: Map<string, NodeJS.Timeout> = new Map();

  constructor(config: ChatWebSocketClientConfig) {
    super();
    
    // Set default configuration
    this.config = {
      websocketUrl: config.websocketUrl,
      userId: config.userId,
      agentId: config.agentId || 'default-ai-agent',
      reconnectAttempts: config.reconnectAttempts || 5,
      reconnectDelay: config.reconnectDelay || 3000,
      heartbeatInterval: config.heartbeatInterval || 30000,
      connectionTimeout: config.connectionTimeout || 10000,
      messageTimeout: config.messageTimeout || 30000,
      ...config
    };

    // Update connection status
    this.connectionStatus = {
      ...this.connectionStatus,
      maxReconnectAttempts: this.config.reconnectAttempts
    };

    // Bind event handlers
    this.onMessage = this.onMessage.bind(this);
    this.onOpen = this.onOpen.bind(this);
    this.onClose = this.onClose.bind(this);
    this.onError = this.onError.bind(this);

    // Auto-connect on initialization
    this.connect();
  }

  /**
   * Connect to WebSocket server
   */
  public async connect(): Promise<void> {
    try {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        console.log('WebSocket already connected');
        return;
      }

      console.log(`Connecting to WebSocket: ${this.config.websocketUrl}`);
      
      // Create WebSocket with connection parameters
      const wsUrl = new URL(this.config.websocketUrl);
      wsUrl.searchParams.set('userId', this.config.userId);
      wsUrl.searchParams.set('agentId', this.config.agentId);

      this.ws = new WebSocket(wsUrl.toString());
      
      // Set up event handlers
      this.ws.onopen = this.onOpen;
      this.ws.onmessage = this.onMessage;
      this.ws.onclose = this.onClose;
      this.ws.onerror = this.onError;

      // Set connection timeout
      this.connectionTimeout = setTimeout(() => {
        if (this.ws && this.ws.readyState === WebSocket.CONNECTING) {
          console.log('WebSocket connection timeout');
          this.ws.close();
        }
      }, this.config.connectionTimeout);

    } catch (error) {
      console.error('Failed to connect WebSocket:', error);
      this.handleConnectionError(error);
    }
  }

  /**
   * Disconnect from WebSocket server
   */
  public disconnect(): void {
    console.log('Disconnecting WebSocket');
    
    // Clear timeouts
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
    
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    
    if (this.connectionTimeout) {
      clearTimeout(this.connectionTimeout);
      this.connectionTimeout = null;
    }
    
    // Close WebSocket
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    
    // Update connection status
    this.connectionStatus = {
      ...this.connectionStatus,
      connected: false,
      reconnecting: false,
      lastDisconnected: new Date()
    };

    this.emit('connection-status-changed', this.connectionStatus);
  }

  /**
   * Send a message
   */
  public sendMessage(message: Omit<ChatMessage, 'status' | 'timestamp'>): Promise<void> {
    return new Promise((resolve, reject) => {
      const chatMessage: ChatMessage = {
        ...message,
        status: 'sending',
        timestamp: new Date(),
        userId: this.config.userId,
        agentId: this.config.agentId
      };

      // Check connection status
      if (!this.isConnected()) {
        // Queue message for later sending
        this.messageQueue.push(chatMessage);
        console.log('WebSocket not connected, message queued');
        reject(new Error('WebSocket not connected'));
        return;
      }

      // Send message
      this.sendMessageDirect(chatMessage)
        .then(() => {
          // Update message status
          chatMessage.status = 'sent';
          this.emit('message-updated', chatMessage);
          resolve();
        })
        .catch((error) => {
          // Update message status
          chatMessage.status = 'error';
          chatMessage.metadata = {
            ...chatMessage.metadata,
            error: error.message
          };
          this.emit('message-updated', chatMessage);
          reject(error);
        });

      // Set message timeout
      const messageTimeout = setTimeout(() => {
        if (chatMessage.status === 'sending') {
          chatMessage.status = 'error';
          chatMessage.metadata = {
            ...chatMessage.metadata,
            error: 'Message timeout'
          };
          this.emit('message-updated', chatMessage);
        }
      }, this.config.messageTimeout);

      this.pendingMessages.set(chatMessage.id, messageTimeout);
    });
  }

  /**
   * Send typing indicator
   */
  public sendTypingIndicator(isTyping: boolean): void {
    if (!this.isConnected()) {
      console.log('Cannot send typing indicator: not connected');
      return;
    }

    const typingIndicator: TypingIndicator = {
      userId: this.config.userId,
      agentId: this.config.agentId,
      isTyping,
      timestamp: new Date()
    };

    this.sendMessageDirect({
      type: 'typing_indicator',
      data: typingIndicator
    });
  }

  /**
   * Request message history
   */
  public requestHistory(limit: number = 50): void {
    if (!this.isConnected()) {
      console.log('Cannot request history: not connected');
      return;
    }

    this.sendMessageDirect({
      type: 'history_request',
      data: {
        userId: this.config.userId,
        agentId: this.config.agentId,
        limit
      }
    });
  }

  /**
   * Get connection status
   */
  public getConnectionStatus(): ConnectionStatus {
    return { ...this.connectionStatus };
  }

  /**
   * Check if connected
   */
  public isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN && this.connectionStatus.connected;
  }

  /**
   * Get queued messages
   */
  public getQueuedMessages(): ChatMessage[] {
    return [...this.messageQueue];
  }

  /**
   * Clear queued messages
   */
  public clearQueuedMessages(): void {
    this.messageQueue = [];
  }

  /**
   * WebSocket event handlers
   */
  private onOpen(): void {
    console.log('WebSocket connected');
    
    // Clear connection timeout
    if (this.connectionTimeout) {
      clearTimeout(this.connectionTimeout);
      this.connectionTimeout = null;
    }

    // Update connection status
    this.connectionStatus = {
      ...this.connectionStatus,
      connected: true,
      reconnecting: false,
      lastConnected: new Date(),
      reconnectAttempts: 0
    };

    this.emit('connection-status-changed', this.connectionStatus);
    this.emit('connected');

    // Start heartbeat
    this.startHeartbeat();

    // Send queued messages
    this.flushMessageQueue();

    // Request message history
    this.requestHistory();
  }

  private onMessage(event: MessageEvent): void {
    try {
      const data = JSON.parse(event.data);
      
      switch (data.type) {
        case 'message':
          this.handleReceivedMessage(data.message);
          break;
        case 'typing_indicator':
          this.handleTypingIndicator(data.data);
          break;
        case 'agent_status':
          this.handleAgentStatus(data.data);
          break;
        case 'history_response':
          this.handleHistoryResponse(data.messages);
          break;
        case 'heartbeat':
          this.handleHeartbeat();
          break;
        case 'connection_status':
          this.handleConnectionStatus(data.connected);
          break;
        case 'message_delivered':
          this.handleMessageDelivered(data.messageId);
          break;
        case 'message_read':
          this.handleMessageRead(data.messageId);
          break;
        default:
          console.log('Unknown message type:', data.type);
      }
    } catch (error) {
      console.error('Error parsing WebSocket message:', error);
    }
  }

  private onClose(event: CloseEvent): void {
    console.log('WebSocket closed:', event.code, event.reason);
    
    // Update connection status
    this.connectionStatus = {
      ...this.connectionStatus,
      connected: false,
      reconnecting: false,
      lastDisconnected: new Date()
    };

    this.emit('connection-status-changed', this.connectionStatus);
    this.emit('disconnected');

    // Clear heartbeat
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }

    // Attempt reconnection if not intentional
    if (event.code !== 1000 && !this.connectionStatus.reconnecting) {
      this.attemptReconnection();
    }
  }

  private onError(error: Event): void {
    console.error('WebSocket error:', error);
    this.emit('error', error);
  }

  /**
   * Message handlers
   */
  private handleReceivedMessage(message: ChatMessage): void {
    // Convert timestamp
    message.timestamp = new Date(message.timestamp);
    
    this.emit('message-received', message);
  }

  private handleTypingIndicator(typingIndicator: TypingIndicator): void {
    typingIndicator.timestamp = new Date(typingIndicator.timestamp);
    this.emit('typing-indicator', typingIndicator);
  }

  private handleAgentStatus(agentStatus: AgentStatus): void {
    agentStatus.timestamp = new Date(agentStatus.timestamp);
    this.emit('agent-status', agentStatus);
  }

  private handleHistoryResponse(messages: ChatMessage[]): void {
    // Convert timestamps
    messages.forEach(msg => {
      msg.timestamp = new Date(msg.timestamp);
    });
    
    this.emit('history-response', messages);
  }

  private handleHeartbeat(): void {
    // Respond to heartbeat
    this.sendMessageDirect({
      type: 'heartbeat_response',
      timestamp: new Date().toISOString()
    });
  }

  private handleConnectionStatus(connected: boolean): void {
    this.connectionStatus.connected = connected;
    this.emit('connection-status-changed', this.connectionStatus);
  }

  private handleMessageDelivered(messageId: string): void {
    this.emit('message-delivered', messageId);
  }

  private handleMessageRead(messageId: string): void {
    this.emit('message-read', messageId);
  }

  /**
   * Connection management
   */
  private attemptReconnection(): void {
    if (this.connectionStatus.reconnectAttempts >= this.connectionStatus.maxReconnectAttempts) {
      console.log('Max reconnection attempts reached');
      this.connectionStatus.reconnecting = false;
      this.emit('connection-failed');
      return;
    }

    console.log(`Attempting reconnection (${this.connectionStatus.reconnectAttempts + 1}/${this.connectionStatus.maxReconnectAttempts})`);
    
    this.connectionStatus.reconnecting = true;
    this.connectionStatus.reconnectAttempts++;
    
    this.emit('reconnection-attempt', this.connectionStatus);

    // Schedule reconnection
    this.reconnectTimeout = setTimeout(() => {
      this.connect();
    }, this.config.reconnectDelay * this.connectionStatus.reconnectAttempts);
  }

  private handleConnectionError(error: any): void {
    console.error('Connection error:', error);
    this.emit('connection-error', error);
    this.attemptReconnection();
  }

  /**
   * Message management
   */
  private sendMessageDirect(data: any): Promise<void> {
    return new Promise((resolve, reject) => {
      if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
        reject(new Error('WebSocket not connected'));
        return;
      }

      try {
        this.ws.send(JSON.stringify(data));
        resolve();
      } catch (error) {
        console.error('Failed to send message:', error);
        reject(error);
      }
    });
  }

  private flushMessageQueue(): void {
    if (this.messageQueue.length === 0) {
      return;
    }

    console.log(`Flushing ${this.messageQueue.length} queued messages`);
    
    const queuedMessages = [...this.messageQueue];
    this.messageQueue = [];

    queuedMessages.forEach(async (message) => {
      try {
        await this.sendMessageDirect(message);
        message.status = 'sent';
        this.emit('message-updated', message);
      } catch (error) {
        message.status = 'error';
        message.metadata = {
          ...message.metadata,
          error: error.message
        };
        this.emit('message-updated', message);
      }
    });
  }

  /**
   * Heartbeat management
   */
  private startHeartbeat(): void {
    this.heartbeatInterval = setInterval(() => {
      if (this.isConnected()) {
        this.sendMessageDirect({
          type: 'heartbeat',
          timestamp: new Date().toISOString()
        });
      }
    }, this.config.heartbeatInterval);
  }

  /**
   * Cleanup
   */
  public destroy(): void {
    this.disconnect();
    
    // Clear pending message timeouts
    this.pendingMessages.forEach(timeout => clearTimeout(timeout));
    this.pendingMessages.clear();
    
    // Remove all event listeners
    this.removeAllListeners();
  }
}

/**
 * Chat WebSocket Manager
 * 
 * Singleton manager for WebSocket connections with automatic reconnection
 * and connection pooling for multiple chat instances.
 */
export class ChatWebSocketManager {
  private static instance: ChatWebSocketManager;
  private connections: Map<string, ChatWebSocketClient> = new Map();

  private constructor() {}

  public static getInstance(): ChatWebSocketManager {
    if (!ChatWebSocketManager.instance) {
      ChatWebSocketManager.instance = new ChatWebSocketManager();
    }
    return ChatWebSocketManager.instance;
  }

  /**
   * Get or create WebSocket client for a user
   */
  public getClient(config: ChatWebSocketClientConfig): ChatWebSocketClient {
    const connectionKey = `${config.userId}-${config.agentId}`;
    
    let client = this.connections.get(connectionKey);
    
    if (!client) {
      client = new ChatWebSocketClient(config);
      this.connections.set(connectionKey, client);
    }
    
    return client;
  }

  /**
   * Disconnect client for a user
   */
  public disconnectClient(userId: string, agentId: string): void {
    const connectionKey = `${userId}-${agentId}`;
    const client = this.connections.get(connectionKey);
    
    if (client) {
      client.disconnect();
      client.destroy();
      this.connections.delete(connectionKey);
    }
  }

  /**
   * Disconnect all clients
   */
  public disconnectAll(): void {
    this.connections.forEach((client, key) => {
      client.disconnect();
      client.destroy();
    });
    this.connections.clear();
  }

  /**
   * Get all active connections
   */
  public getActiveConnections(): Map<string, ChatWebSocketClient> {
    return new Map(this.connections);
  }

  /**
   * Get connection count
   */
  public getConnectionCount(): number {
    return this.connections.size;
  }
}

export default ChatWebSocketClient;