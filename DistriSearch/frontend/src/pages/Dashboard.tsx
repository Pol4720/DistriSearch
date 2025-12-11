import React from 'react';
import { Link } from 'react-router-dom';
import {
  Search,
  FileText,
  Server,
  Activity,
  TrendingUp,
  Clock,
  CheckCircle,
  AlertCircle,
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import { useClusterStatus, useDocuments, useHealth, useNodes } from '../hooks';
import { LoadingSpinner, ErrorMessage, Badge } from '../components/common';

// Mock data for charts (replace with real metrics)
const searchMetricsData = [
  { time: '00:00', searches: 45 },
  { time: '04:00', searches: 23 },
  { time: '08:00', searches: 156 },
  { time: '12:00', searches: 289 },
  { time: '16:00', searches: 198 },
  { time: '20:00', searches: 87 },
];

const COLORS = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444'];

export const Dashboard: React.FC = () => {
  const { data: clusterStatus, isLoading: clusterLoading, error: clusterError } = useClusterStatus();
  const { data: documents, isLoading: docsLoading } = useDocuments({ limit: 5 });
  const { data: health } = useHealth();
  const { data: nodes } = useNodes();

  const getStatusIcon = (status?: string) => {
    if (status === 'healthy') return <CheckCircle className="w-5 h-5 text-green-500" />;
    if (status === 'degraded') return <AlertCircle className="w-5 h-5 text-yellow-500" />;
    return <AlertCircle className="w-5 h-5 text-red-500" />;
  };

  // Calculate partition distribution for pie chart
  const partitionData = nodes?.reduce((acc, node) => {
    const existing = acc.find(a => a.name === node.role);
    if (existing) {
      existing.value += node.partitions?.length || 0;
    } else {
      acc.push({ name: node.role, value: node.partitions?.length || 0 });
    }
    return acc;
  }, [] as { name: string; value: number }[]) || [];

  if (clusterLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (clusterError) {
    return (
      <ErrorMessage
        title="Failed to load dashboard"
        message="Could not connect to the cluster. Please check your connection."
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-500">Welcome to DistriSearch distributed search system</p>
        </div>
        <Badge variant={health?.status === 'healthy' ? 'success' : 'warning'}>
          {getStatusIcon(health?.status)}
          <span className="ml-1">{health?.status || 'Unknown'}</span>
        </Badge>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          title="Total Documents"
          value={documents?.total || 0}
          icon={<FileText className="w-6 h-6" />}
          color="blue"
          link="/documents"
        />
        <StatCard
          title="Active Nodes"
          value={clusterStatus?.active_nodes || 0}
          subtitle={`of ${clusterStatus?.total_nodes || 0} total`}
          icon={<Server className="w-6 h-6" />}
          color="green"
          link="/cluster"
        />
        <StatCard
          title="Partitions"
          value={clusterStatus?.total_partitions || 0}
          icon={<Activity className="w-6 h-6" />}
          color="purple"
          link="/cluster"
        />
        <StatCard
          title="Searches Today"
          value={1247}
          trend={{ value: 12, positive: true }}
          icon={<Search className="w-6 h-6" />}
          color="orange"
          link="/search"
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Search Activity Chart */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-gray-900">Search Activity</h2>
            <select className="text-sm border border-gray-200 rounded-lg px-3 py-1.5">
              <option>Last 24 hours</option>
              <option>Last 7 days</option>
              <option>Last 30 days</option>
            </select>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={searchMetricsData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="time" stroke="#9ca3af" fontSize={12} />
                <YAxis stroke="#9ca3af" fontSize={12} />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="searches"
                  stroke="#3B82F6"
                  strokeWidth={2}
                  dot={{ r: 4 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Partition Distribution Chart */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-gray-900">Partition Distribution</h2>
            <Link to="/cluster" className="text-sm text-blue-600 hover:underline">
              View details
            </Link>
          </div>
          <div className="h-64 flex items-center justify-center">
            {partitionData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={partitionData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={80}
                    paddingAngle={5}
                    dataKey="value"
                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  >
                    {partitionData.map((_, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-gray-500">No partition data available</p>
            )}
          </div>
        </div>
      </div>

      {/* Recent Activity and Quick Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Documents */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">Recent Documents</h2>
            <Link to="/documents" className="text-sm text-blue-600 hover:underline">
              View all
            </Link>
          </div>
          <div className="space-y-3">
            {docsLoading ? (
              <LoadingSpinner size="sm" />
            ) : documents?.items?.length ? (
              documents.items.slice(0, 5).map((doc) => (
                <div
                  key={doc.id}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                >
                  <div className="flex items-center gap-3">
                    <FileText className="w-5 h-5 text-gray-400" />
                    <div>
                      <p className="font-medium text-gray-900">{doc.title || doc.filename}</p>
                      <p className="text-sm text-gray-500">
                        Partition {doc.partition_id}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-gray-500">
                    <Clock className="w-4 h-4" />
                    {new Date(doc.created_at).toLocaleDateString()}
                  </div>
                </div>
              ))
            ) : (
              <p className="text-gray-500 text-center py-4">No documents yet</p>
            )}
          </div>
        </div>

        {/* Quick Actions */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Quick Actions</h2>
          <div className="space-y-3">
            <Link
              to="/search"
              className="flex items-center gap-3 p-3 bg-blue-50 text-blue-700 rounded-lg hover:bg-blue-100 transition-colors"
            >
              <Search className="w-5 h-5" />
              <span>New Search</span>
            </Link>
            <Link
              to="/documents?action=upload"
              className="flex items-center gap-3 p-3 bg-green-50 text-green-700 rounded-lg hover:bg-green-100 transition-colors"
            >
              <FileText className="w-5 h-5" />
              <span>Upload Document</span>
            </Link>
            <Link
              to="/cluster"
              className="flex items-center gap-3 p-3 bg-purple-50 text-purple-700 rounded-lg hover:bg-purple-100 transition-colors"
            >
              <Server className="w-5 h-5" />
              <span>Manage Cluster</span>
            </Link>
            <Link
              to="/monitoring"
              className="flex items-center gap-3 p-3 bg-orange-50 text-orange-700 rounded-lg hover:bg-orange-100 transition-colors"
            >
              <Activity className="w-5 h-5" />
              <span>View Metrics</span>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};

// Stat Card Component
interface StatCardProps {
  title: string;
  value: number | string;
  subtitle?: string;
  icon: React.ReactNode;
  color: 'blue' | 'green' | 'purple' | 'orange';
  link?: string;
  trend?: { value: number; positive: boolean };
}

const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  subtitle,
  icon,
  color,
  link,
  trend,
}) => {
  const colorClasses = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    purple: 'bg-purple-50 text-purple-600',
    orange: 'bg-orange-50 text-orange-600',
  };

  const content = (
    <div className="bg-white rounded-xl border border-gray-200 p-6 hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between mb-4">
        <div className={`p-3 rounded-lg ${colorClasses[color]}`}>{icon}</div>
        {trend && (
          <div
            className={`flex items-center text-sm ${
              trend.positive ? 'text-green-600' : 'text-red-600'
            }`}
          >
            <TrendingUp className={`w-4 h-4 mr-1 ${!trend.positive && 'rotate-180'}`} />
            {trend.value}%
          </div>
        )}
      </div>
      <h3 className="text-2xl font-bold text-gray-900">{value}</h3>
      <p className="text-sm text-gray-500">{title}</p>
      {subtitle && <p className="text-xs text-gray-400 mt-1">{subtitle}</p>}
    </div>
  );

  if (link) {
    return <Link to={link}>{content}</Link>;
  }

  return content;
};
