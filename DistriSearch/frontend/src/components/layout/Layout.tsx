import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';

export const Layout: React.FC = () => {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Sidebar */}
      <Sidebar
        collapsed={sidebarCollapsed}
        onCollapsedChange={setSidebarCollapsed}
      />

      {/* Mobile overlay */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 z-30 bg-black bg-opacity-50 lg:hidden"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* Main content */}
      <div
        className={`
          transition-all duration-300 ease-in-out
          ${sidebarCollapsed ? 'lg:ml-16' : 'lg:ml-64'}
        `}
      >
        <Header
          onMenuClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          showMenuButton={true}
        />

        <main className="p-4 md:p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
