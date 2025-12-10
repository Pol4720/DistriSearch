import type { ClusterStatus, SearchResult } from '../types';

type MessageHandler<T = unknown> = (data: T) => void;
type ConnectionHandler = () => void;
type ErrorHandler = (error: Event) => void;

interface WebSocketMessage {
  type: string;
  data: unknown;
}

interface ClusterUpdateMessage {
  type: 'cluster_status' | 'node_joined' | 'node_left' | 'rebalance_progress';
  data: ClusterStatus | { node_id: string } | { progress: number; message: string };
}

interface SearchUpdateMessage {
  type: 'search_progress' | 'search_result' | 'search_complete';
  data: { progress: number; nodes_queried: number } | SearchResult | { total_results: number; search_time: number };
}

class WebSocketService {
  private socket: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private pingInterval: number | null = null;
  private messageHandlers: Map<string, Set<MessageHandler>> = new Map();
  private connectionHandlers: Set<ConnectionHandler> = new Set();
  private disconnectionHandlers: Set<ConnectionHandler> = new Set();
  private errorHandlers: Set<ErrorHandler> = new Set();
  private clientId: string | null = null;
  private baseUrl: string;

  constructor() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = import.meta.env.VITE_API_HOST || window.location.host;
    this.baseUrl = `${protocol}//${host}/api/v1/ws`;
  }

  /**
   * Connect to cluster updates WebSocket
   */
  connectCluster(): void {
    this.connect(`${this.baseUrl}/cluster`);
  }

  /**
   * Connect to search updates WebSocket
   */
  connectSearch(searchId: string): void {
    this.connect(`${this.baseUrl}/search/${searchId}`);
  }

  /**
   * Connect to general updates WebSocket
   */
  connect(url?: string): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      console.warn('WebSocket already connected');
      return;
    }

    const wsUrl = url || `${this.baseUrl}/cluster`;
    
    try {
      this.socket = new WebSocket(wsUrl);
      this.setupEventListeners();
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
      this.handleReconnect();
    }
  }

  private setupEventListeners(): void {
    if (!this.socket) return;

    this.socket.onopen = () => {
      console.log('WebSocket connected');
      this.reconnectAttempts = 0;
      this.startPingInterval();
      this.connectionHandlers.forEach((handler) => handler());
    };

    this.socket.onmessage = (event: MessageEvent) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data);
        this.handleMessage(message);
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };

    this.socket.onclose = (event: CloseEvent) => {
      console.log('WebSocket disconnected:', event.code, event.reason);
      this.stopPingInterval();
      this.disconnectionHandlers.forEach((handler) => handler());
      
      if (!event.wasClean) {
        this.handleReconnect();
      }
    };

    this.socket.onerror = (error: Event) => {
      console.error('WebSocket error:', error);
      this.errorHandlers.forEach((handler) => handler(error));
    };
  }

  private handleMessage(message: WebSocketMessage): void {
    // Handle connection acknowledgment
    if (message.type === 'connected') {
      this.clientId = (message.data as { client_id: string }).client_id;
      console.log('WebSocket client ID:', this.clientId);
      return;
    }

    // Handle pong response
    if (message.type === 'pong') {
      return;
    }

    // Dispatch to registered handlers
    const handlers = this.messageHandlers.get(message.type);
    if (handlers) {
      handlers.forEach((handler) => handler(message.data));
    }

    // Also dispatch to wildcard handlers
    const wildcardHandlers = this.messageHandlers.get('*');
    if (wildcardHandlers) {
      wildcardHandlers.forEach((handler) => handler(message));
    }
  }

  private handleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnect attempts reached');
      return;
    }

    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
    
    console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
    
    setTimeout(() => {
      this.connect();
    }, delay);
  }

  private startPingInterval(): void {
    this.pingInterval = window.setInterval(() => {
      this.send({ type: 'ping' });
    }, 30000);
  }

  private stopPingInterval(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  /**
   * Send a message through the WebSocket
   */
  send(data: unknown): boolean {
    if (this.socket?.readyState !== WebSocket.OPEN) {
      console.warn('WebSocket not connected');
      return false;
    }

    try {
      this.socket.send(JSON.stringify(data));
      return true;
    } catch (error) {
      console.error('Failed to send WebSocket message:', error);
      return false;
    }
  }

  /**
   * Subscribe to a search
   */
  subscribeToSearch(searchId: string): void {
    this.send({
      type: 'subscribe',
      channel: 'search',
      search_id: searchId,
    });
  }

  /**
   * Unsubscribe from a search
   */
  unsubscribeFromSearch(searchId: string): void {
    this.send({
      type: 'unsubscribe',
      channel: 'search',
      search_id: searchId,
    });
  }

  /**
   * Subscribe to cluster updates
   */
  subscribeToCluster(): void {
    this.send({
      type: 'subscribe',
      channel: 'cluster',
    });
  }

  /**
   * Register a message handler
   */
  onMessage<T = unknown>(type: string, handler: MessageHandler<T>): () => void {
    if (!this.messageHandlers.has(type)) {
      this.messageHandlers.set(type, new Set());
    }
    this.messageHandlers.get(type)!.add(handler as MessageHandler);

    // Return unsubscribe function
    return () => {
      this.messageHandlers.get(type)?.delete(handler as MessageHandler);
    };
  }

  /**
   * Register a cluster update handler
   */
  onClusterUpdate(handler: MessageHandler<ClusterUpdateMessage['data']>): () => void {
    const types = ['cluster_status', 'node_joined', 'node_left', 'rebalance_progress'];
    const unsubscribers = types.map((type) => this.onMessage(type, handler));
    
    return () => {
      unsubscribers.forEach((unsub) => unsub());
    };
  }

  /**
   * Register a search update handler
   */
  onSearchUpdate(handler: MessageHandler<SearchUpdateMessage['data']>): () => void {
    const types = ['search_progress', 'search_result', 'search_complete'];
    const unsubscribers = types.map((type) => this.onMessage(type, handler));
    
    return () => {
      unsubscribers.forEach((unsub) => unsub());
    };
  }

  /**
   * Register a connection handler
   */
  onConnect(handler: ConnectionHandler): () => void {
    this.connectionHandlers.add(handler);
    return () => {
      this.connectionHandlers.delete(handler);
    };
  }

  /**
   * Register a disconnection handler
   */
  onDisconnect(handler: ConnectionHandler): () => void {
    this.disconnectionHandlers.add(handler);
    return () => {
      this.disconnectionHandlers.delete(handler);
    };
  }

  /**
   * Register an error handler
   */
  onError(handler: ErrorHandler): () => void {
    this.errorHandlers.add(handler);
    return () => {
      this.errorHandlers.delete(handler);
    };
  }

  /**
   * Disconnect WebSocket
   */
  disconnect(): void {
    this.stopPingInterval();
    
    if (this.socket) {
      this.socket.close(1000, 'Client disconnected');
      this.socket = null;
    }
    
    this.clientId = null;
    this.reconnectAttempts = 0;
  }

  /**
   * Get connection state
   */
  get isConnected(): boolean {
    return this.socket?.readyState === WebSocket.OPEN;
  }

  /**
   * Get client ID
   */
  getClientId(): string | null {
    return this.clientId;
  }
}

// Export singleton instance
export const websocketService = new WebSocketService();

// Export class for testing
export { WebSocketService };
