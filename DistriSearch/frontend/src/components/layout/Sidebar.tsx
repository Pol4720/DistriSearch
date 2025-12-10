import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  Search,
  FileText,
  Server,
  LayoutDashboard,
  Settings,
  ChevronLeft,
  ChevronRight,
  Activity,
} from 'lucide-react';

interface SidebarProps {
  collapsed?: boolean;
  onCollapsedChange?: (collapsed: boolean) => void;
}

interface NavItem {
  path: string;
  label: string;
  icon: React.ReactNode;
}

const navItems: NavItem[] = [
  { path: '/', label: 'Dashboard', icon: <LayoutDashboard className="w-5 h-5" /> },
  { path: '/search', label: 'Search', icon: <Search className="w-5 h-5" /> },
  { path: '/documents', label: 'Documents', icon: <FileText className="w-5 h-5" /> },
  { path: '/cluster', label: 'Cluster', icon: <Server className="w-5 h-5" /> },
  { path: '/monitoring', label: 'Monitoring', icon: <Activity className="w-5 h-5" /> },
  { path: '/settings', label: 'Settings', icon: <Settings className="w-5 h-5" /> },
];

export const Sidebar: React.FC<SidebarProps> = ({
  collapsed: controlledCollapsed,
  onCollapsedChange,
}) => {
  const [internalCollapsed, setInternalCollapsed] = useState(false);
  const collapsed = controlledCollapsed ?? internalCollapsed;
  const setCollapsed = onCollapsedChange ?? setInternalCollapsed;
  
  const location = useLocation();

  const isActive = (path: string) => {
    if (path === '/') {
      return location.pathname === '/';
    }
    return location.pathname.startsWith(path);
  };

  return (
    <aside
      className={`
        fixed left-0 top-0 z-40 h-screen
        bg-gray-900 text-white
        transition-all duration-300 ease-in-out
        ${collapsed ? 'w-16' : 'w-64'}
      `}
    >
      {/* Logo */}
      <div className="flex items-center justify-between h-16 px-4 border-b border-gray-800">
        {!collapsed && (
          <Link to="/" className="flex items-center gap-2">
            <Search className="w-6 h-6 text-blue-400" />
            <span className="text-lg font-bold">DistriSearch</span>
          </Link>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-2 rounded-lg hover:bg-gray-800 transition-colors"
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? (
            <ChevronRight className="w-5 h-5" />
          ) : (
            <ChevronLeft className="w-5 h-5" />
          )}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-2 py-4 space-y-1">
        {navItems.map((item) => (
          <Link
            key={item.path}
            to={item.path}
            className={`
              flex items-center gap-3 px-3 py-2.5 rounded-lg
              transition-colors duration-200
              ${
                isActive(item.path)
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-400 hover:bg-gray-800 hover:text-white'
              }
              ${collapsed ? 'justify-center' : ''}
            `}
            title={collapsed ? item.label : undefined}
          >
            {item.icon}
            {!collapsed && <span>{item.label}</span>}
          </Link>
        ))}
      </nav>

      {/* Footer */}
      {!collapsed && (
        <div className="px-4 py-4 border-t border-gray-800">
          <p className="text-xs text-gray-500">
            DistriSearch v1.0.0
          </p>
          <p className="text-xs text-gray-600 mt-1">
            Distributed Search System
          </p>
        </div>
      )}
    </aside>
  );
};
