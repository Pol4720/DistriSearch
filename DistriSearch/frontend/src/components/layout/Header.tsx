import React from 'react';
import { Bell, User, Menu } from 'lucide-react';
import { useClusterStatus, useHealth } from '../../hooks';

interface HeaderProps {
  onMenuClick?: () => void;
  showMenuButton?: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  onMenuClick,
  showMenuButton = false,
}) => {
  const { data: clusterStatus } = useClusterStatus();
  const { data: health } = useHealth();

  const getStatusColor = () => {
    if (!health) return 'bg-gray-400';
    if (health.status === 'healthy') return 'bg-green-500';
    if (health.status === 'degraded') return 'bg-yellow-500';
    return 'bg-red-500';
  };

  return (
    <header className="sticky top-0 z-30 bg-white border-b border-gray-200 shadow-sm">
      <div className="flex items-center justify-between h-16 px-4">
        {/* Left side */}
        <div className="flex items-center gap-4">
          {showMenuButton && (
            <button
              onClick={onMenuClick}
              className="p-2 rounded-lg hover:bg-gray-100 transition-colors lg:hidden"
              aria-label="Toggle menu"
            >
              <Menu className="w-5 h-5 text-gray-600" />
            </button>
          )}

          {/* Cluster Status */}
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${getStatusColor()}`} />
            <span className="text-sm text-gray-600">
              {clusterStatus
                ? `${clusterStatus.total_nodes} nodes`
                : 'Loading...'}
            </span>
          </div>
        </div>

        {/* Right side */}
        <div className="flex items-center gap-3">
          {/* Health indicator */}
          <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-gray-100 rounded-lg">
            <span className={`w-2 h-2 rounded-full ${getStatusColor()}`} />
            <span className="text-sm text-gray-700">
              {health?.status || 'Unknown'}
            </span>
          </div>

          {/* Notifications */}
          <button
            className="relative p-2 rounded-lg hover:bg-gray-100 transition-colors"
            aria-label="Notifications"
          >
            <Bell className="w-5 h-5 text-gray-600" />
            <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full" />
          </button>

          {/* User menu */}
          <button
            className="flex items-center gap-2 p-2 rounded-lg hover:bg-gray-100 transition-colors"
            aria-label="User menu"
          >
            <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center">
              <User className="w-5 h-5 text-white" />
            </div>
          </button>
        </div>
      </div>
    </header>
  );
};
