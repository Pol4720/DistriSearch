import React, { useState } from 'react';
import {
  Server,
  Activity,
  HardDrive,
  RefreshCw,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Trash2,
} from 'lucide-react';
import {
  useClusterStatus,
  useNodes,
  usePartitions,
  useRebalance,
  useRemoveNode,
  useClusterUpdates,
} from '../hooks';
import {
  NodeCard,
  LoadingSpinner,
  EmptyState,
  ErrorMessage,
  Badge,
  ProgressBar,
} from '../components/common';
import type { NodeInfo } from '../types';

export const Cluster: React.FC = () => {
  const [selectedNode, setSelectedNode] = useState<NodeInfo | null>(null);
  const [showRebalanceModal, setShowRebalanceModal] = useState(false);

  const {
    data: clusterStatus,
    isLoading: statusLoading,
    error: statusError,
    refetch: refetchStatus,
  } = useClusterStatus();
  
  const { data: nodes, isLoading: nodesLoading, refetch: refetchNodes } = useNodes();
  const { data: partitions, isLoading: partitionsLoading } = usePartitions();
  const rebalanceMutation = useRebalance();
  const removeNodeMutation = useRemoveNode();

  // Real-time updates via WebSocket
  useClusterUpdates({
    onStatusUpdate: () => {
      refetchStatus();
      refetchNodes();
    },
    onNodeJoined: (nodeId) => {
      console.log('Node joined:', nodeId);
      refetchNodes();
    },
    onNodeLeft: (nodeId) => {
      console.log('Node left:', nodeId);
      refetchNodes();
    },
    enabled: true,
  });

  const handleRebalance = async () => {
    try {
      await rebalanceMutation.mutateAsync({});
      setShowRebalanceModal(false);
    } catch (error) {
      console.error('Rebalance failed:', error);
    }
  };

  const handleRemoveNode = async (node: NodeInfo) => {
    if (!window.confirm(`Remove node "${node.node_id}" from the cluster?`)) return;
    
    try {
      await removeNodeMutation.mutateAsync(node.node_id);
      setSelectedNode(null);
    } catch (error) {
      console.error('Remove node failed:', error);
    }
  };

  const isLoading = statusLoading || nodesLoading;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (statusError) {
    return (
      <ErrorMessage
        title="Failed to load cluster status"
        message="Could not connect to the cluster. Please check your connection."
        onRetry={() => refetchStatus()}
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Cluster Management</h1>
          <p className="text-gray-500">
            Monitor and manage your distributed search cluster
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowRebalanceModal(true)}
            disabled={rebalanceMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <RefreshCw className={`w-5 h-5 ${rebalanceMutation.isPending ? 'animate-spin' : ''}`} />
            Rebalance
          </button>
        </div>
      </div>

      {/* Cluster Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <ClusterStatCard
          title="Total Nodes"
          value={clusterStatus?.total_nodes || 0}
          subtitle={`${clusterStatus?.active_nodes || 0} active`}
          icon={<Server className="w-6 h-6" />}
          status={clusterStatus?.active_nodes === clusterStatus?.total_nodes ? 'success' : 'warning'}
        />
        <ClusterStatCard
          title="Partitions"
          value={clusterStatus?.total_partitions || 0}
          subtitle="Distributed across nodes"
          icon={<HardDrive className="w-6 h-6" />}
          status="default"
        />
        <ClusterStatCard
          title="Replication Factor"
          value={clusterStatus?.replication_factor || 0}
          subtitle="Copies per partition"
          icon={<Activity className="w-6 h-6" />}
          status="default"
        />
        <ClusterStatCard
          title="Cluster Health"
          value={clusterStatus?.healthy ? 'Healthy' : 'Degraded'}
          icon={
            clusterStatus?.healthy ? (
              <CheckCircle className="w-6 h-6" />
            ) : (
              <AlertTriangle className="w-6 h-6" />
            )
          }
          status={clusterStatus?.healthy ? 'success' : 'error'}
        />
      </div>

      {/* Nodes Grid */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-gray-900">Cluster Nodes</h2>
          <div className="flex items-center gap-2">
            <Badge variant="success">{nodes?.filter(n => n.status === 'healthy').length || 0} Healthy</Badge>
            <Badge variant="warning">{nodes?.filter(n => n.status === 'degraded').length || 0} Degraded</Badge>
            <Badge variant="error">{nodes?.filter(n => n.status === 'unhealthy').length || 0} Unhealthy</Badge>
          </div>
        </div>

        {nodes && nodes.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {nodes.map((node) => (
              <NodeCard
                key={node.node_id}
                node={node}
                onClick={() => setSelectedNode(node)}
                showDetails
              />
            ))}
          </div>
        ) : (
          <EmptyState
            icon={<Server className="w-12 h-12" />}
            title="No nodes"
            description="No nodes are currently registered in the cluster."
          />
        )}
      </div>

      {/* Partitions Overview */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-gray-900">Partition Distribution</h2>
        </div>

        {partitionsLoading ? (
          <LoadingSpinner />
        ) : partitions?.partitions && partitions.partitions.length > 0 ? (
          <div className="space-y-4">
            {/* Group partitions by primary_node_id */}
            {(() => {
              const nodePartitionCounts: Record<string, number> = {};
              partitions.partitions.forEach((p) => {
                nodePartitionCounts[p.primary_node_id] = (nodePartitionCounts[p.primary_node_id] || 0) + 1;
              });
              return Object.entries(nodePartitionCounts).map(([nodeId, count]) => (
                <div key={nodeId} className="flex items-center gap-4">
                  <div className="w-32 text-sm font-medium text-gray-700 truncate">
                    {nodeId}
                  </div>
                  <div className="flex-1">
                    <ProgressBar
                      value={count}
                      max={clusterStatus?.total_partitions || 1}
                      showLabel={false}
                      color="blue"
                    />
                  </div>
                  <div className="w-20 text-sm text-gray-500 text-right">
                    {count} partitions
                  </div>
                </div>
              ));
            })()}
          </div>
        ) : (
          <p className="text-gray-500 text-center py-4">No partition data available</p>
        )}
      </div>

      {/* Node Detail Modal */}
      {selectedNode && (
        <NodeDetailModal
          node={selectedNode}
          onClose={() => setSelectedNode(null)}
          onRemove={handleRemoveNode}
          isRemoving={removeNodeMutation.isPending}
        />
      )}

      {/* Rebalance Modal */}
      {showRebalanceModal && (
        <RebalanceModal
          onClose={() => setShowRebalanceModal(false)}
          onConfirm={handleRebalance}
          isLoading={rebalanceMutation.isPending}
        />
      )}
    </div>
  );
};

// Cluster Stat Card Component
interface ClusterStatCardProps {
  title: string;
  value: number | string;
  subtitle?: string;
  icon: React.ReactNode;
  status: 'default' | 'success' | 'warning' | 'error';
}

const ClusterStatCard: React.FC<ClusterStatCardProps> = ({
  title,
  value,
  subtitle,
  icon,
  status,
}) => {
  const statusColors = {
    default: 'bg-gray-50 text-gray-600',
    success: 'bg-green-50 text-green-600',
    warning: 'bg-yellow-50 text-yellow-600',
    error: 'bg-red-50 text-red-600',
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <div className={`inline-flex p-3 rounded-lg ${statusColors[status]} mb-4`}>
        {icon}
      </div>
      <h3 className="text-2xl font-bold text-gray-900">{value}</h3>
      <p className="text-sm text-gray-500">{title}</p>
      {subtitle && <p className="text-xs text-gray-400 mt-1">{subtitle}</p>}
    </div>
  );
};

// Node Detail Modal Component
interface NodeDetailModalProps {
  node: NodeInfo;
  onClose: () => void;
  onRemove: (node: NodeInfo) => void;
  isRemoving: boolean;
}

const NodeDetailModal: React.FC<NodeDetailModalProps> = ({
  node,
  onClose,
  onRemove,
  isRemoving,
}) => {
  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'healthy':
        return <Badge variant="success">Healthy</Badge>;
      case 'degraded':
        return <Badge variant="warning">Degraded</Badge>;
      case 'unhealthy':
        return <Badge variant="error">Unhealthy</Badge>;
      default:
        return <Badge variant="default">{status}</Badge>;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
      <div className="bg-white rounded-xl p-6 w-full max-w-lg mx-4">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold text-gray-900">Node Details</h2>
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-100 rounded transition-colors"
          >
            <XCircle className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        <div className="space-y-4">
          <div className="flex items-center justify-between py-2 border-b border-gray-100">
            <span className="text-gray-500">Node ID</span>
            <span className="font-medium text-gray-900">{node.node_id}</span>
          </div>
          <div className="flex items-center justify-between py-2 border-b border-gray-100">
            <span className="text-gray-500">Address</span>
            <span className="font-medium text-gray-900">{node.address}</span>
          </div>
          <div className="flex items-center justify-between py-2 border-b border-gray-100">
            <span className="text-gray-500">Status</span>
            {getStatusBadge(node.status)}
          </div>
          <div className="flex items-center justify-between py-2 border-b border-gray-100">
            <span className="text-gray-500">Role</span>
            <Badge variant={node.role === 'master' ? 'info' : 'default'}>
              {node.role}
            </Badge>
          </div>
          <div className="flex items-center justify-between py-2 border-b border-gray-100">
            <span className="text-gray-500">Partitions</span>
            <span className="font-medium text-gray-900">
              {node.partitions?.length || 0}
            </span>
          </div>
          <div className="flex items-center justify-between py-2 border-b border-gray-100">
            <span className="text-gray-500">Load Score</span>
            <span className="font-medium text-gray-900">
              {node.load_score?.toFixed(2) || 'N/A'}
            </span>
          </div>
          {node.last_heartbeat && (
            <div className="flex items-center justify-between py-2 border-b border-gray-100">
              <span className="text-gray-500">Last Heartbeat</span>
              <span className="font-medium text-gray-900">
                {new Date(node.last_heartbeat).toLocaleString()}
              </span>
            </div>
          )}
        </div>

        {node.partitions && node.partitions.length > 0 && (
          <div className="mt-6">
            <h3 className="text-sm font-medium text-gray-700 mb-2">Assigned Partitions</h3>
            <div className="flex flex-wrap gap-2">
              {node.partitions.map((p) => (
                <Badge key={p.partition_id} variant="default">
                  P{p.partition_id}
                </Badge>
              ))}
            </div>
          </div>
        )}

        <div className="flex justify-between mt-6 pt-4 border-t border-gray-100">
          <button
            onClick={() => onRemove(node)}
            disabled={isRemoving || node.role === 'master'}
            className="flex items-center gap-2 px-4 py-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Trash2 className="w-4 h-4" />
            Remove Node
          </button>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

// Rebalance Modal Component
interface RebalanceModalProps {
  onClose: () => void;
  onConfirm: () => void;
  isLoading: boolean;
}

const RebalanceModal: React.FC<RebalanceModalProps> = ({
  onClose,
  onConfirm,
  isLoading,
}) => {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
      <div className="bg-white rounded-xl p-6 w-full max-w-md mx-4">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-3 bg-blue-50 rounded-lg">
            <RefreshCw className="w-6 h-6 text-blue-600" />
          </div>
          <h2 className="text-xl font-semibold text-gray-900">Rebalance Cluster</h2>
        </div>

        <p className="text-gray-600 mb-6">
          This will redistribute partitions across all active nodes to ensure
          optimal load balancing. This operation may take some time depending on
          the amount of data.
        </p>

        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6">
          <div className="flex items-center gap-2 text-yellow-800">
            <AlertTriangle className="w-5 h-5" />
            <span className="font-medium">Warning</span>
          </div>
          <p className="text-sm text-yellow-700 mt-1">
            Some search queries may experience temporary latency during rebalancing.
          </p>
        </div>

        <div className="flex justify-end gap-3">
          <button
            onClick={onClose}
            disabled={isLoading}
            className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={isLoading}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {isLoading && <RefreshCw className="w-4 h-4 animate-spin" />}
            {isLoading ? 'Rebalancing...' : 'Start Rebalance'}
          </button>
        </div>
      </div>
    </div>
  );
};
