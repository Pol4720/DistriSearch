import React from 'react';
import { Server, Activity, HardDrive, Cpu } from 'lucide-react';
import type { NodeInfo } from '../../types';

interface NodeCardProps {
  node: NodeInfo;
  onClick?: (node: NodeInfo) => void;
  showDetails?: boolean;
}

export const NodeCard: React.FC<NodeCardProps> = ({
  node,
  onClick,
  showDetails = false,
}) => {
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy':
        return 'bg-green-500';
      case 'degraded':
        return 'bg-yellow-500';
      case 'unhealthy':
        return 'bg-red-500';
      default:
        return 'bg-gray-400';
    }
  };

  const getRoleColor = (role: string) => {
    switch (role) {
      case 'master':
        return 'bg-purple-100 text-purple-700';
      case 'slave':
        return 'bg-blue-100 text-blue-700';
      case 'candidate':
        return 'bg-gray-100 text-gray-700';
      default:
        return 'bg-gray-100 text-gray-600';
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'healthy':
        return 'Online';
      case 'degraded':
        return 'Degraded';
      case 'unhealthy':
        return 'Offline';
      default:
        return status;
    }
  };

  return (
    <div
      onClick={() => onClick?.(node)}
      className={`
        p-4 bg-white rounded-lg border border-gray-200 
        transition-all duration-200
        ${onClick ? 'cursor-pointer hover:shadow-md hover:border-gray-300' : ''}
      `}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="relative">
            <Server className="w-6 h-6 text-gray-600" />
            <span
              className={`absolute -bottom-1 -right-1 w-3 h-3 rounded-full border-2 border-white ${getStatusColor(node.status)}`}
            />
          </div>
          <div>
            <h3 className="font-medium text-gray-900">{node.node_id}</h3>
            <p className="text-sm text-gray-500">{node.address}</p>
          </div>
        </div>
        <span
          className={`px-2 py-1 text-xs font-medium rounded-full ${getRoleColor(node.role)}`}
        >
          {node.role}
        </span>
      </div>

      {/* Stats */}
      {showDetails && (
        <div className="grid grid-cols-3 gap-3 pt-3 border-t border-gray-100">
          <div className="text-center">
            <div className="flex items-center justify-center mb-1">
              <HardDrive className="w-4 h-4 text-gray-400" />
            </div>
            <p className="text-lg font-semibold text-gray-900">
              {node.partition_count ?? (node.partitions?.length ?? 0)}
            </p>
            <p className="text-xs text-gray-500">Partitions</p>
          </div>
          <div className="text-center">
            <div className="flex items-center justify-center mb-1">
              <Activity className="w-4 h-4 text-gray-400" />
            </div>
            <p className="text-lg font-semibold text-gray-900">
              {node.load_score?.toFixed(1) ?? 'N/A'}
            </p>
            <p className="text-xs text-gray-500">Load</p>
          </div>
          <div className="text-center">
            <div className="flex items-center justify-center mb-1">
              <Cpu className="w-4 h-4 text-gray-400" />
            </div>
            <p className="text-lg font-semibold text-gray-900">
              {getStatusLabel(node.status)}
            </p>
            <p className="text-xs text-gray-500">Status</p>
          </div>
        </div>
      )}

      {/* Last seen */}
      {node.last_heartbeat && (
        <div className="mt-3 pt-3 border-t border-gray-100">
          <p className="text-xs text-gray-400">
            Last seen: {new Date(node.last_heartbeat).toLocaleTimeString()}
          </p>
        </div>
      )}
    </div>
  );
};
