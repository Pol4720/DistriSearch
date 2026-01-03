import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  Search,
  FileText,
  LayoutDashboard,
  Settings,
  ChevronLeft,
  ChevronRight,
  Sparkles,
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
  { path: '/search', label: 'Buscar', icon: <Search className="w-5 h-5" /> },
  { path: '/documents', label: 'Documentos', icon: <FileText className="w-5 h-5" /> },
  { path: '/settings', label: 'Configuración', icon: <Settings className="w-5 h-5" /> },
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
        bg-gradient-to-b from-gray-900 via-gray-900 to-gray-950
        text-white shadow-2xl
        transition-all duration-300 ease-in-out
        ${collapsed ? 'w-20' : 'w-72'}
      `}
    >
      {/* Logo */}
      <div className={`flex items-center h-20 px-4 border-b border-gray-800/50 ${collapsed ? 'justify-center' : 'justify-between'}`}>
        {!collapsed && (
          <Link to="/" className="flex items-center gap-3 group">
            <div className="relative">
              <div className="absolute inset-0 bg-blue-500 blur-lg opacity-50 group-hover:opacity-75 transition-opacity" />
              <div className="relative bg-gradient-to-br from-blue-500 to-purple-600 p-2.5 rounded-xl">
                <Sparkles className="w-6 h-6 text-white" />
              </div>
            </div>
            <div>
              <span className="text-xl font-bold bg-gradient-to-r from-white to-gray-300 bg-clip-text text-transparent">
                DistriSearch
              </span>
              <p className="text-[10px] text-gray-500 font-medium tracking-wider uppercase">
                Búsqueda Inteligente
              </p>
            </div>
          </Link>
        )}
        {collapsed && (
          <div className="bg-gradient-to-br from-blue-500 to-purple-600 p-2.5 rounded-xl">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
        )}
      </div>

      {/* Toggle Button */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className={`
          absolute -right-3 top-24 z-50
          w-6 h-6 rounded-full
          bg-gradient-to-r from-blue-500 to-purple-600
          text-white shadow-lg
          flex items-center justify-center
          hover:scale-110 transition-transform duration-200
          border-2 border-gray-900
        `}
        aria-label={collapsed ? 'Expandir menú' : 'Colapsar menú'}
      >
        {collapsed ? (
          <ChevronRight className="w-3.5 h-3.5" />
        ) : (
          <ChevronLeft className="w-3.5 h-3.5" />
        )}
      </button>

      {/* Navigation */}
      <nav className="px-3 py-6 space-y-2">
        {!collapsed && (
          <p className="px-4 text-[10px] font-semibold text-gray-500 uppercase tracking-wider mb-4">
            Menú Principal
          </p>
        )}
        {navItems.map((item, index) => (
          <Link
            key={item.path}
            to={item.path}
            className={`
              relative flex items-center gap-4 px-4 py-3.5 rounded-xl
              transition-all duration-300 group
              ${collapsed ? 'justify-center' : ''}
              ${
                isActive(item.path)
                  ? 'bg-gradient-to-r from-blue-600/90 to-purple-600/90 text-white shadow-lg shadow-blue-500/25'
                  : 'text-gray-400 hover:text-white hover:bg-white/5'
              }
            `}
            style={{ animationDelay: `${index * 50}ms` }}
            title={collapsed ? item.label : undefined}
          >
            {/* Active indicator */}
            {isActive(item.path) && (
              <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-white rounded-r-full" />
            )}
            
            <div className={`
              ${isActive(item.path) ? '' : 'group-hover:scale-110'}
              transition-transform duration-200
            `}>
              {item.icon}
            </div>
            
            {!collapsed && (
              <span className="font-medium">{item.label}</span>
            )}

            {/* Tooltip for collapsed state */}
            {collapsed && (
              <div className="
                absolute left-full ml-3 px-3 py-2
                bg-gray-800 text-white text-sm font-medium
                rounded-lg shadow-xl
                opacity-0 invisible group-hover:opacity-100 group-hover:visible
                transition-all duration-200
                whitespace-nowrap z-50
              ">
                {item.label}
                <div className="absolute left-0 top-1/2 -translate-x-1 -translate-y-1/2 
                  border-4 border-transparent border-r-gray-800" />
              </div>
            )}
          </Link>
        ))}
      </nav>

      {/* Footer */}
      {!collapsed && (
        <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-gray-800/50">
          <div className="bg-gradient-to-r from-blue-500/10 to-purple-500/10 rounded-xl p-4">
            <p className="text-xs text-gray-400 font-medium">
              DistriSearch v1.0.0
            </p>
            <p className="text-[10px] text-gray-500 mt-1">
              Sistema de Búsqueda Distribuida
            </p>
          </div>
        </div>
      )}
    </aside>
  );
};
