import React, { useState } from 'react';
import { Bell, User, Menu, LogOut, ChevronDown, Sparkles } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useHealth, useAuth } from '../../hooks';

interface HeaderProps {
  onMenuClick?: () => void;
  showMenuButton?: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  onMenuClick,
  showMenuButton = false,
}) => {
  const navigate = useNavigate();
  const { data: health } = useHealth();
  const { user, logout } = useAuth();
  const [showUserMenu, setShowUserMenu] = useState(false);

  const getStatusColor = () => {
    if (!health) return 'bg-gray-400';
    if (health.status === 'healthy') return 'bg-green-500';
    if (health.status === 'degraded') return 'bg-yellow-500';
    return 'bg-red-500';
  };

  const getStatusText = () => {
    if (!health) return 'Conectando...';
    if (health.status === 'healthy') return 'Sistema operativo';
    if (health.status === 'degraded') return 'Rendimiento reducido';
    return 'Sistema inactivo';
  };

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <header className="sticky top-0 z-30 bg-white/80 backdrop-blur-lg border-b border-gray-200/50 shadow-sm">
      <div className="flex items-center justify-between h-16 px-4">
        {/* Left side */}
        <div className="flex items-center gap-4">
          {showMenuButton && (
            <button
              onClick={onMenuClick}
              className="p-2 rounded-lg hover:bg-gray-100 transition-all duration-200 hover:scale-105 lg:hidden"
              aria-label="Toggle menu"
            >
              <Menu className="w-5 h-5 text-gray-600" />
            </button>
          )}

          {/* System Status - Simplified */}
          <div className="flex items-center gap-2 px-3 py-1.5 bg-gradient-to-r from-gray-50 to-gray-100 rounded-full">
            <span className={`w-2 h-2 rounded-full ${getStatusColor()} animate-pulse`} />
            <span className="text-sm text-gray-600 font-medium">
              {getStatusText()}
            </span>
          </div>
        </div>

        {/* Right side */}
        <div className="flex items-center gap-3">
          {/* Welcome message */}
          <div className="hidden md:flex items-center gap-2 px-3 py-1.5">
            <Sparkles className="w-4 h-4 text-amber-500" />
            <span className="text-sm text-gray-600">
              Bienvenido, <span className="font-semibold text-gray-800">{user?.username || 'Usuario'}</span>
            </span>
          </div>

          {/* Notifications */}
          <button
            className="relative p-2 rounded-full hover:bg-gray-100 transition-all duration-200 hover:scale-105 group"
            aria-label="Notifications"
          >
            <Bell className="w-5 h-5 text-gray-600 group-hover:text-blue-600 transition-colors" />
            <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full animate-pulse" />
          </button>

          {/* User menu */}
          <div className="relative">
            <button
              onClick={() => setShowUserMenu(!showUserMenu)}
              className="flex items-center gap-2 p-2 rounded-full hover:bg-gray-100 transition-all duration-200 group"
              aria-label="User menu"
            >
              <div className="w-9 h-9 bg-gradient-to-br from-blue-500 via-purple-500 to-pink-500 rounded-full flex items-center justify-center shadow-lg group-hover:shadow-xl transition-shadow">
                <User className="w-5 h-5 text-white" />
              </div>
              <ChevronDown className={`w-4 h-4 text-gray-500 transition-transform duration-200 ${showUserMenu ? 'rotate-180' : ''}`} />
            </button>

            {/* Dropdown menu with animation */}
            {showUserMenu && (
              <div className="absolute right-0 mt-2 w-56 bg-white rounded-2xl shadow-xl border border-gray-100 py-2 z-50 animate-in fade-in slide-in-from-top-2 duration-200">
                <div className="px-4 py-3 border-b border-gray-100">
                  <p className="text-sm font-semibold text-gray-900">{user?.username}</p>
                  <p className="text-xs text-gray-500 truncate">{user?.email}</p>
                </div>
                <div className="py-1">
                  <button
                    onClick={() => { navigate('/settings'); setShowUserMenu(false); }}
                    className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                  >
                    <div className="w-8 h-8 bg-gray-100 rounded-lg flex items-center justify-center">
                      <User className="w-4 h-4 text-gray-600" />
                    </div>
                    Mi perfil
                  </button>
                </div>
                <div className="border-t border-gray-100 pt-1">
                  <button
                    onClick={handleLogout}
                    className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-red-600 hover:bg-red-50 transition-colors"
                  >
                    <div className="w-8 h-8 bg-red-50 rounded-lg flex items-center justify-center">
                      <LogOut className="w-4 h-4 text-red-500" />
                    </div>
                    Cerrar sesión
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};
