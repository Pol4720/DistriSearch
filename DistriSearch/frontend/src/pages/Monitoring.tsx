import React, { useState } from 'react';
import {
  Activity,
  Cpu,
  HardDrive,
  Clock,
  TrendingUp,
  RefreshCw,
  Zap,
  Database,
  Search,
  FileText,
} from 'lucide-react';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
} from 'recharts';
import { useMetrics, useClusterStatus, useNodes } from '../hooks';
import { LoadingSpinner, ErrorMessage, Badge } from '../components/common';

// Mock metrics data (replace with real metrics from backend)
const generateMockData = () => {
  const now = Date.now();
  return Array.from({ length: 24 }, (_, i) => ({
    time: new Date(now - (23 - i) * 3600000).toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
    }),
    searches: Math.floor(Math.random() * 200) + 50,
    latency: Math.floor(Math.random() * 100) + 20,
    cpu: Math.floor(Math.random() * 40) + 30,
    memory: Math.floor(Math.random() * 30) + 50,
    documents: Math.floor(Math.random() * 50) + 10,
  }));
};

const metricsData = generateMockData();

const nodeMetrics = [
  { name: 'node-1', searches: 1234, avgLatency: 45, cpu: 65, memory: 72 },
  { name: 'node-2', searches: 1156, avgLatency: 52, cpu: 58, memory: 68 },
  { name: 'node-3', searches: 987, avgLatency: 38, cpu: 45, memory: 55 },
  { name: 'node-4', searches: 1089, avgLatency: 48, cpu: 52, memory: 62 },
];

export const Monitoring: React.FC = () => {
  const [timeRange, setTimeRange] = useState('24h');
  const { data: metrics, isLoading, error, refetch } = useMetrics();
  const { data: clusterStatus } = useClusterStatus();
  const { data: nodes } = useNodes();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (error) {
    return (
      <ErrorMessage
        title="Failed to load metrics"
        message="Could not fetch monitoring data. Please try again."
        onRetry={() => refetch()}
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Monitoring</h1>
          <p className="text-gray-500">System performance and metrics</p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700"
          >
            <option value="1h">Last Hour</option>
            <option value="6h">Last 6 Hours</option>
            <option value="24h">Last 24 Hours</option>
            <option value="7d">Last 7 Days</option>
          </select>
          <button
            onClick={() => refetch()}
            className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <RefreshCw className="w-5 h-5" />
            Refresh
          </button>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard
          title="Search Requests"
          value="4,521"
          change={12.5}
          positive={true}
          icon={<Search className="w-6 h-6" />}
          color="blue"
        />
        <MetricCard
          title="Avg Latency"
          value="45ms"
          change={-8.3}
          positive={true}
          icon={<Zap className="w-6 h-6" />}
          color="green"
        />
        <MetricCard
          title="Documents Indexed"
          value="12,847"
          change={3.2}
          positive={true}
          icon={<FileText className="w-6 h-6" />}
          color="purple"
        />
        <MetricCard
          title="Active Connections"
          value="127"
          icon={<Activity className="w-6 h-6" />}
          color="orange"
        />
      </div>

      {/* Charts Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Search Activity */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-6">Search Activity</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={metricsData}>
                <defs>
                  <linearGradient id="searchGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#3B82F6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="time" stroke="#9ca3af" fontSize={12} />
                <YAxis stroke="#9ca3af" fontSize={12} />
                <Tooltip />
                <Area
                  type="monotone"
                  dataKey="searches"
                  stroke="#3B82F6"
                  fill="url(#searchGradient)"
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Response Latency */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-6">Response Latency</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={metricsData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="time" stroke="#9ca3af" fontSize={12} />
                <YAxis stroke="#9ca3af" fontSize={12} unit="ms" />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="latency"
                  stroke="#10B981"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Charts Row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Resource Usage */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-6">Resource Usage</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={metricsData}>
                <defs>
                  <linearGradient id="cpuGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#8B5CF6" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#8B5CF6" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="memGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#F59E0B" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#F59E0B" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="time" stroke="#9ca3af" fontSize={12} />
                <YAxis stroke="#9ca3af" fontSize={12} unit="%" />
                <Tooltip />
                <Area
                  type="monotone"
                  dataKey="cpu"
                  name="CPU"
                  stroke="#8B5CF6"
                  fill="url(#cpuGradient)"
                  strokeWidth={2}
                />
                <Area
                  type="monotone"
                  dataKey="memory"
                  name="Memory"
                  stroke="#F59E0B"
                  fill="url(#memGradient)"
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Node Performance */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-6">Node Performance</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={nodeMetrics} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis type="number" stroke="#9ca3af" fontSize={12} />
                <YAxis type="category" dataKey="name" stroke="#9ca3af" fontSize={12} />
                <Tooltip />
                <Bar dataKey="searches" name="Searches" fill="#3B82F6" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Node Details Table */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-6">Node Details</h2>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-3 px-4 text-sm font-medium text-gray-600">Node</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-gray-600">Status</th>
                <th className="text-right py-3 px-4 text-sm font-medium text-gray-600">Searches</th>
                <th className="text-right py-3 px-4 text-sm font-medium text-gray-600">Avg Latency</th>
                <th className="text-right py-3 px-4 text-sm font-medium text-gray-600">CPU</th>
                <th className="text-right py-3 px-4 text-sm font-medium text-gray-600">Memory</th>
                <th className="text-right py-3 px-4 text-sm font-medium text-gray-600">Partitions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {nodes?.map((node, index) => (
                <tr key={node.node_id} className="hover:bg-gray-50">
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-2">
                      <Database className="w-4 h-4 text-gray-400" />
                      <span className="font-medium text-gray-900">{node.node_id}</span>
                    </div>
                  </td>
                  <td className="py-3 px-4">
                    <Badge
                      variant={
                        node.status === 'active'
                          ? 'success'
                          : node.status === 'syncing'
                          ? 'warning'
                          : 'error'
                      }
                    >
                      {node.status}
                    </Badge>
                  </td>
                  <td className="py-3 px-4 text-right text-gray-700">
                    {nodeMetrics[index]?.searches.toLocaleString() || '-'}
                  </td>
                  <td className="py-3 px-4 text-right text-gray-700">
                    {nodeMetrics[index]?.avgLatency || '-'}ms
                  </td>
                  <td className="py-3 px-4 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <div className="w-16 bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-purple-500 h-2 rounded-full"
                          style={{ width: `${nodeMetrics[index]?.cpu || 0}%` }}
                        />
                      </div>
                      <span className="text-gray-700 text-sm">
                        {nodeMetrics[index]?.cpu || 0}%
                      </span>
                    </div>
                  </td>
                  <td className="py-3 px-4 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <div className="w-16 bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-orange-500 h-2 rounded-full"
                          style={{ width: `${nodeMetrics[index]?.memory || 0}%` }}
                        />
                      </div>
                      <span className="text-gray-700 text-sm">
                        {nodeMetrics[index]?.memory || 0}%
                      </span>
                    </div>
                  </td>
                  <td className="py-3 px-4 text-right text-gray-700">
                    {node.partitions?.length || 0}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

// Metric Card Component
interface MetricCardProps {
  title: string;
  value: string;
  change?: number;
  positive?: boolean;
  icon: React.ReactNode;
  color: 'blue' | 'green' | 'purple' | 'orange';
}

const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  change,
  positive,
  icon,
  color,
}) => {
  const colorClasses = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    purple: 'bg-purple-50 text-purple-600',
    orange: 'bg-orange-50 text-orange-600',
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <div className={`p-3 rounded-lg ${colorClasses[color]}`}>{icon}</div>
        {change !== undefined && (
          <div
            className={`flex items-center text-sm ${
              positive ? 'text-green-600' : 'text-red-600'
            }`}
          >
            <TrendingUp
              className={`w-4 h-4 mr-1 ${change < 0 ? 'rotate-180' : ''}`}
            />
            {Math.abs(change)}%
          </div>
        )}
      </div>
      <h3 className="text-2xl font-bold text-gray-900">{value}</h3>
      <p className="text-sm text-gray-500">{title}</p>
    </div>
  );
};
