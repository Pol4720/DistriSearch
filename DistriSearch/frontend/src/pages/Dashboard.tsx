import React from 'react';
import { Link } from 'react-router-dom';
import {
  Search,
  FileText,
  Clock,
  CheckCircle,
  AlertCircle,
  Server,
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { useClusterStatus, useDocuments, useHealth, useMetrics, useSearchHistory } from '../hooks';
import { LoadingSpinner, ErrorMessage, Badge } from '../components/common';

export const Dashboard: React.FC = () => {
  const { data: clusterStatus, isLoading: clusterLoading, error: clusterError } = useClusterStatus();
  const { data: documents, isLoading: docsLoading } = useDocuments({ limit: 5 });
  const { data: health } = useHealth();
  const { data: metrics } = useMetrics();
  const { data: searchHistory } = useSearchHistory({ limit: 100 });

  // Generate search metrics from REAL historical data with proper timestamps
  const searchMetricsData = React.useMemo(() => {
    const now = new Date();
    const buckets: { time: string; searches: number; startTime: Date }[] = [];
    
    // Create 6 time buckets (4 hours each)
    for (let i = 5; i >= 0; i--) {
      const bucketEnd = new Date(now.getTime() - i * 4 * 3600000);
      const bucketStart = new Date(now.getTime() - (i + 1) * 4 * 3600000);
      buckets.push({
        time: bucketEnd.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' }),
        searches: 0,
        startTime: bucketStart
      });
    }
    
    // Count searches from history with their real timestamps
    if (searchHistory?.history) {
      searchHistory.history.forEach((item: { timestamp?: string }) => {
        if (item.timestamp) {
          const searchTime = new Date(item.timestamp);
          for (let i = 0; i < buckets.length; i++) {
            const bucketStart = buckets[i].startTime;
            const bucketEnd = new Date(bucketStart.getTime() + 4 * 3600000);
            if (searchTime >= bucketStart && searchTime < bucketEnd) {
              buckets[i].searches++;
              break;
            }
          }
        }
      });
    }
    
    return buckets.map(({ time, searches }) => ({ time, searches }));
  }, [searchHistory]);

  const getStatusIcon = (status?: string) => {
    if (status === 'healthy') return <CheckCircle className="w-5 h-5 text-green-500" />;
    if (status === 'degraded') return <AlertCircle className="w-5 h-5 text-yellow-500" />;
    return <AlertCircle className="w-5 h-5 text-red-500" />;
  };

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
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <StatCard
          title="Mis Documentos"
          value={documents?.total || 0}
          icon={<FileText className="w-6 h-6" />}
          color="blue"
          link="/documents"
        />
        <StatCard
          title="Sistema"
          value={health?.status === 'healthy' ? 'Operativo' : 'Degradado'}
          subtitle={`${clusterStatus?.active_nodes ?? clusterStatus?.healthy_nodes ?? 0} nodos activos`}
          icon={<Server className="w-6 h-6" />}
          color="green"
          link="/cluster"
        />
        <StatCard
          title="Búsquedas Realizadas"
          value={Number(metrics?.total_searches || 0)}
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

        {/* System Health Overview */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-gray-900">Estado del Sistema</h2>
          </div>
          <div className="h-64 flex flex-col items-center justify-center space-y-6">
            <div className={`w-24 h-24 rounded-full flex items-center justify-center ${
              health?.status === 'healthy' ? 'bg-green-100' : 
              health?.status === 'degraded' ? 'bg-yellow-100' : 'bg-red-100'
            }`}>
              {health?.status === 'healthy' ? (
                <CheckCircle className="w-12 h-12 text-green-600" />
              ) : health?.status === 'degraded' ? (
                <AlertCircle className="w-12 h-12 text-yellow-600" />
              ) : (
                <AlertCircle className="w-12 h-12 text-red-600" />
              )}
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-gray-900 capitalize">
                {health?.status === 'healthy' ? 'Sistema Operativo' : 
                 health?.status === 'degraded' ? 'Rendimiento Reducido' : 'Sistema Inactivo'}
              </p>
              <p className="text-sm text-gray-500 mt-1">
                {clusterStatus?.active_nodes ?? clusterStatus?.healthy_nodes ?? 0} de {clusterStatus?.total_nodes || 0} nodos activos
              </p>
            </div>
            <div className="flex gap-4 text-sm">
              <div className="text-center">
                <p className="font-semibold text-gray-900">{documents?.total || 0}</p>
                <p className="text-gray-500">Documentos</p>
              </div>
              <div className="text-center">
                <p className="font-semibold text-gray-900">{Number(metrics?.total_searches || 0)}</p>
                <p className="text-gray-500">Búsquedas</p>
              </div>
            </div>
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
            ) : documents?.documents?.length ? (
              documents.documents.slice(0, 5).map((doc: { id: string; title?: string; filename?: string; partition_id?: string; created_at: string }) => (
                <div
                  key={doc.id}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                >
                  <div className="flex items-center gap-3">
                    <FileText className="w-5 h-5 text-gray-400" />
                    <div>
                      <p className="font-medium text-gray-900">{doc.title || doc.filename || 'Untitled'}</p>
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
}

const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  subtitle,
  icon,
  color,
  link,
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
