import api from './api';
import type {
  ClusterStatus,
  NodeInfo,
  ClusterPartitions,
  RebalanceRequest,
  RebalanceResponse,
  HealthResponse,
} from '../types';

const CLUSTER_ENDPOINT = '/cluster';
const HEALTH_ENDPOINT = '/health';

export const clusterService = {
  /**
   * Get cluster status
   */
  async getStatus(): Promise<ClusterStatus> {
    const response = await api.get<ClusterStatus>(`${CLUSTER_ENDPOINT}/status`);
    return response.data;
  },

  /**
   * List all nodes
   */
  async listNodes(filters?: {
    status?: string;
    role?: string;
  }): Promise<NodeInfo[]> {
    const response = await api.get<NodeInfo[]>(`${CLUSTER_ENDPOINT}/nodes`, {
      params: filters,
    });
    return response.data;
  },

  /**
   * Get a specific node
   */
  async getNode(nodeId: string): Promise<NodeInfo> {
    const response = await api.get<NodeInfo>(
      `${CLUSTER_ENDPOINT}/nodes/${nodeId}`
    );
    return response.data;
  },

  /**
   * Get master node
   */
  async getMaster(): Promise<NodeInfo> {
    const response = await api.get<NodeInfo>(`${CLUSTER_ENDPOINT}/master`);
    return response.data;
  },

  /**
   * Get partitions
   */
  async getPartitions(nodeId?: string): Promise<ClusterPartitions> {
    const response = await api.get<ClusterPartitions>(
      `${CLUSTER_ENDPOINT}/partitions`,
      { params: nodeId ? { node_id: nodeId } : {} }
    );
    return response.data;
  },

  /**
   * Trigger rebalance
   */
  async triggerRebalance(
    request: RebalanceRequest = {}
  ): Promise<RebalanceResponse> {
    const response = await api.post<RebalanceResponse>(
      `${CLUSTER_ENDPOINT}/rebalance`,
      request
    );
    return response.data;
  },

  /**
   * Remove a node from the cluster
   */
  async removeNode(nodeId: string): Promise<void> {
    await api.delete(`${CLUSTER_ENDPOINT}/nodes/${nodeId}`);
  },
};

export const healthService = {
  /**
   * Get health status
   */
  async getHealth(): Promise<HealthResponse> {
    const response = await api.get<HealthResponse>(HEALTH_ENDPOINT);
    return response.data;
  },

  /**
   * Check readiness
   */
  async checkReady(): Promise<{ ready: boolean; message: string; checks: Record<string, boolean> }> {
    const response = await api.get<{ ready: boolean; message: string; checks: Record<string, boolean> }>(
      `${HEALTH_ENDPOINT}/ready`
    );
    return response.data;
  },

  /**
   * Check liveness
   */
  async checkLive(): Promise<{ alive: boolean; timestamp: string }> {
    const response = await api.get<{ alive: boolean; timestamp: string }>(
      `${HEALTH_ENDPOINT}/live`
    );
    return response.data;
  },

  /**
   * Get metrics
   */
  async getMetrics(): Promise<Record<string, unknown>> {
    const response = await api.get<Record<string, unknown>>(
      `${HEALTH_ENDPOINT}/metrics`
    );
    return response.data;
  },
};
