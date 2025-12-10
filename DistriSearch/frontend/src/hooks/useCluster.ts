import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { clusterService, healthService } from '../services';
import type { ClusterStatus, NodeInfo, RebalanceRequest, RebalanceResponse } from '../types';

// Query keys
export const clusterKeys = {
  all: ['cluster'] as const,
  status: () => [...clusterKeys.all, 'status'] as const,
  nodes: () => [...clusterKeys.all, 'nodes'] as const,
  nodesList: (filters?: Record<string, unknown>) =>
    [...clusterKeys.nodes(), 'list', filters] as const,
  node: (id: string) => [...clusterKeys.nodes(), id] as const,
  master: () => [...clusterKeys.all, 'master'] as const,
  partitions: (nodeId?: string) =>
    [...clusterKeys.all, 'partitions', nodeId] as const,
};

export const healthKeys = {
  all: ['health'] as const,
  status: () => [...healthKeys.all, 'status'] as const,
  ready: () => [...healthKeys.all, 'ready'] as const,
  live: () => [...healthKeys.all, 'live'] as const,
  metrics: () => [...healthKeys.all, 'metrics'] as const,
};

interface UseClusterStatusOptions {
  enabled?: boolean;
  refetchInterval?: number | false;
}

/**
 * Hook to fetch cluster status
 */
export function useClusterStatus(options: UseClusterStatusOptions = {}) {
  const { enabled = true, refetchInterval = 10000 } = options;

  return useQuery({
    queryKey: clusterKeys.status(),
    queryFn: () => clusterService.getStatus(),
    enabled,
    staleTime: 5000, // 5 seconds
    refetchInterval,
  });
}

/**
 * Hook to fetch all nodes
 */
export function useNodes(
  filters?: { status?: string; role?: string },
  options: { enabled?: boolean; refetchInterval?: number | false } = {}
) {
  const { enabled = true, refetchInterval = 10000 } = options;

  return useQuery({
    queryKey: clusterKeys.nodesList(filters),
    queryFn: () => clusterService.listNodes(filters),
    enabled,
    staleTime: 5000,
    refetchInterval,
  });
}

/**
 * Hook to fetch a specific node
 */
export function useNode(
  nodeId: string,
  options: { enabled?: boolean } = {}
) {
  const { enabled = true } = options;

  return useQuery({
    queryKey: clusterKeys.node(nodeId),
    queryFn: () => clusterService.getNode(nodeId),
    enabled: enabled && !!nodeId,
    staleTime: 5000,
  });
}

/**
 * Hook to fetch master node
 */
export function useMasterNode(options: { enabled?: boolean } = {}) {
  const { enabled = true } = options;

  return useQuery({
    queryKey: clusterKeys.master(),
    queryFn: () => clusterService.getMaster(),
    enabled,
    staleTime: 10000,
  });
}

/**
 * Hook to fetch partitions
 */
export function usePartitions(
  nodeId?: string,
  options: { enabled?: boolean } = {}
) {
  const { enabled = true } = options;

  return useQuery({
    queryKey: clusterKeys.partitions(nodeId),
    queryFn: () => clusterService.getPartitions(nodeId),
    enabled,
    staleTime: 30000,
  });
}

/**
 * Hook to trigger rebalance
 */
export function useRebalance() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: RebalanceRequest = {}) =>
      clusterService.triggerRebalance(request),
    onSuccess: () => {
      // Invalidate cluster-related queries
      queryClient.invalidateQueries({ queryKey: clusterKeys.all });
    },
  });
}

/**
 * Hook to remove a node
 */
export function useRemoveNode() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (nodeId: string) => clusterService.removeNode(nodeId),
    onSuccess: (_, nodeId) => {
      // Remove from cache
      queryClient.removeQueries({ queryKey: clusterKeys.node(nodeId) });
      // Invalidate node lists
      queryClient.invalidateQueries({ queryKey: clusterKeys.nodes() });
      // Invalidate cluster status
      queryClient.invalidateQueries({ queryKey: clusterKeys.status() });
    },
  });
}

/**
 * Hook to fetch health status
 */
export function useHealth(options: { enabled?: boolean; refetchInterval?: number | false } = {}) {
  const { enabled = true, refetchInterval = 30000 } = options;

  return useQuery({
    queryKey: healthKeys.status(),
    queryFn: () => healthService.getHealth(),
    enabled,
    staleTime: 10000,
    refetchInterval,
  });
}

/**
 * Hook to check readiness
 */
export function useReadiness(options: { enabled?: boolean } = {}) {
  const { enabled = true } = options;

  return useQuery({
    queryKey: healthKeys.ready(),
    queryFn: () => healthService.checkReady(),
    enabled,
    staleTime: 5000,
  });
}

/**
 * Hook to check liveness
 */
export function useLiveness(options: { enabled?: boolean } = {}) {
  const { enabled = true } = options;

  return useQuery({
    queryKey: healthKeys.live(),
    queryFn: () => healthService.checkLive(),
    enabled,
    staleTime: 5000,
  });
}

/**
 * Hook to fetch metrics
 */
export function useMetrics(options: { enabled?: boolean; refetchInterval?: number | false } = {}) {
  const { enabled = true, refetchInterval = 15000 } = options;

  return useQuery({
    queryKey: healthKeys.metrics(),
    queryFn: () => healthService.getMetrics(),
    enabled,
    staleTime: 10000,
    refetchInterval,
  });
}

/**
 * Hook to invalidate all cluster caches
 */
export function useInvalidateCluster() {
  const queryClient = useQueryClient();

  return () => {
    queryClient.invalidateQueries({ queryKey: clusterKeys.all });
  };
}
