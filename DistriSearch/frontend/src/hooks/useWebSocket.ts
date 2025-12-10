import { useState, useEffect, useCallback, useRef } from 'react';
import { websocketService } from '../services';
import type { ClusterStatus } from '../types';

interface UseWebSocketOptions {
  autoConnect?: boolean;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
}

interface ClusterUpdate {
  type: 'cluster_status' | 'node_joined' | 'node_left' | 'rebalance_progress';
  data: unknown;
}

interface SearchUpdate {
  type: 'search_progress' | 'search_result' | 'search_complete';
  data: unknown;
}

/**
 * Hook for WebSocket connection management
 */
export function useWebSocket(options: UseWebSocketOptions = {}) {
  const { autoConnect = false, onConnect, onDisconnect, onError } = options;
  const [isConnected, setIsConnected] = useState(websocketService.isConnected);
  const [clientId, setClientId] = useState<string | null>(
    websocketService.getClientId()
  );

  useEffect(() => {
    const unsubConnect = websocketService.onConnect(() => {
      setIsConnected(true);
      setClientId(websocketService.getClientId());
      onConnect?.();
    });

    const unsubDisconnect = websocketService.onDisconnect(() => {
      setIsConnected(false);
      setClientId(null);
      onDisconnect?.();
    });

    const unsubError = onError
      ? websocketService.onError(onError)
      : () => {};

    if (autoConnect && !websocketService.isConnected) {
      websocketService.connectCluster();
    }

    return () => {
      unsubConnect();
      unsubDisconnect();
      unsubError();
    };
  }, [autoConnect, onConnect, onDisconnect, onError]);

  const connect = useCallback(() => {
    websocketService.connectCluster();
  }, []);

  const disconnect = useCallback(() => {
    websocketService.disconnect();
  }, []);

  const send = useCallback((data: unknown) => {
    return websocketService.send(data);
  }, []);

  return {
    isConnected,
    clientId,
    connect,
    disconnect,
    send,
  };
}

/**
 * Hook for cluster updates via WebSocket
 */
export function useClusterUpdates(options: {
  onStatusUpdate?: (status: ClusterStatus) => void;
  onNodeJoined?: (nodeId: string) => void;
  onNodeLeft?: (nodeId: string) => void;
  onRebalanceProgress?: (progress: number, message: string) => void;
  enabled?: boolean;
} = {}) {
  const {
    onStatusUpdate,
    onNodeJoined,
    onNodeLeft,
    onRebalanceProgress,
    enabled = true,
  } = options;

  const [lastUpdate, setLastUpdate] = useState<ClusterUpdate | null>(null);
  const handlersRef = useRef({
    onStatusUpdate,
    onNodeJoined,
    onNodeLeft,
    onRebalanceProgress,
  });

  // Update handlers ref when they change
  useEffect(() => {
    handlersRef.current = {
      onStatusUpdate,
      onNodeJoined,
      onNodeLeft,
      onRebalanceProgress,
    };
  }, [onStatusUpdate, onNodeJoined, onNodeLeft, onRebalanceProgress]);

  useEffect(() => {
    if (!enabled) return;

    // Connect if not already connected
    if (!websocketService.isConnected) {
      websocketService.connectCluster();
    }

    // Subscribe to cluster updates
    websocketService.subscribeToCluster();

    // Register handlers
    const unsubStatus = websocketService.onMessage<ClusterStatus>(
      'cluster_status',
      (data) => {
        setLastUpdate({ type: 'cluster_status', data });
        handlersRef.current.onStatusUpdate?.(data);
      }
    );

    const unsubJoined = websocketService.onMessage<{ node_id: string }>(
      'node_joined',
      (data) => {
        setLastUpdate({ type: 'node_joined', data });
        handlersRef.current.onNodeJoined?.(data.node_id);
      }
    );

    const unsubLeft = websocketService.onMessage<{ node_id: string }>(
      'node_left',
      (data) => {
        setLastUpdate({ type: 'node_left', data });
        handlersRef.current.onNodeLeft?.(data.node_id);
      }
    );

    const unsubProgress = websocketService.onMessage<{
      progress: number;
      message: string;
    }>('rebalance_progress', (data) => {
      setLastUpdate({ type: 'rebalance_progress', data });
      handlersRef.current.onRebalanceProgress?.(data.progress, data.message);
    });

    return () => {
      unsubStatus();
      unsubJoined();
      unsubLeft();
      unsubProgress();
    };
  }, [enabled]);

  return { lastUpdate };
}

/**
 * Hook for search updates via WebSocket
 */
export function useSearchUpdates(
  searchId: string | null,
  options: {
    onProgress?: (progress: number, nodesQueried: number) => void;
    onResult?: (result: unknown) => void;
    onComplete?: (totalResults: number, searchTime: number) => void;
    enabled?: boolean;
  } = {}
) {
  const { onProgress, onResult, onComplete, enabled = true } = options;

  const [lastUpdate, setLastUpdate] = useState<SearchUpdate | null>(null);
  const [progress, setProgress] = useState(0);
  const [isComplete, setIsComplete] = useState(false);

  const handlersRef = useRef({ onProgress, onResult, onComplete });

  // Update handlers ref when they change
  useEffect(() => {
    handlersRef.current = { onProgress, onResult, onComplete };
  }, [onProgress, onResult, onComplete]);

  useEffect(() => {
    if (!enabled || !searchId) return;

    // Reset state
    setProgress(0);
    setIsComplete(false);

    // Subscribe to search updates
    websocketService.subscribeToSearch(searchId);

    // Register handlers
    const unsubProgress = websocketService.onMessage<{
      progress: number;
      nodes_queried: number;
    }>('search_progress', (data) => {
      setLastUpdate({ type: 'search_progress', data });
      setProgress(data.progress);
      handlersRef.current.onProgress?.(data.progress, data.nodes_queried);
    });

    const unsubResult = websocketService.onMessage<unknown>(
      'search_result',
      (data) => {
        setLastUpdate({ type: 'search_result', data });
        handlersRef.current.onResult?.(data);
      }
    );

    const unsubComplete = websocketService.onMessage<{
      total_results: number;
      search_time: number;
    }>('search_complete', (data) => {
      setLastUpdate({ type: 'search_complete', data });
      setProgress(100);
      setIsComplete(true);
      handlersRef.current.onComplete?.(data.total_results, data.search_time);
    });

    return () => {
      websocketService.unsubscribeFromSearch(searchId);
      unsubProgress();
      unsubResult();
      unsubComplete();
    };
  }, [enabled, searchId]);

  return { lastUpdate, progress, isComplete };
}
