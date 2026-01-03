import React, { useState, useEffect } from 'react';
import {
  User,
  Search,
  Save,
  Check,
  LogOut,
} from 'lucide-react';
import { useAuth } from '../hooks/useAuth';

export const Settings: React.FC = () => {
  const { user, logout } = useAuth();
  const [saved, setSaved] = useState(false);

  const [settings, setSettings] = useState({
    displayName: '',
    resultsPerPage: 20,
    showPreviews: true,
  });

  // Cargar nombre del usuario
  useEffect(() => {
    if (user) {
      setSettings(prev => ({
        ...prev,
        displayName: user.username || user.email || '',
      }));
    }
  }, [user]);

  const handleSave = () => {
    // Guardar en localStorage
    localStorage.setItem('distrisearch_settings', JSON.stringify(settings));
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const handleLogout = () => {
    logout();
  };

  return (
    <div className="max-w-3xl mx-auto space-y-8 animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-gray-900 to-gray-600 bg-clip-text text-transparent">
            Configuración
          </h1>
          <p className="text-gray-500 mt-1">Personaliza tu experiencia</p>
        </div>
        <button
          onClick={handleSave}
          className={`flex items-center gap-2 px-5 py-2.5 rounded-xl font-medium transition-all duration-300 transform hover:scale-105 ${
            saved 
              ? 'bg-green-500 text-white' 
              : 'bg-gradient-to-r from-blue-600 to-purple-600 text-white hover:shadow-lg hover:shadow-blue-500/25'
          }`}
        >
          {saved ? <Check className="w-5 h-5" /> : <Save className="w-5 h-5" />}
          {saved ? 'Guardado' : 'Guardar'}
        </button>
      </div>

      {/* Profile Section */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-6">
        <div className="flex items-center gap-4 pb-6 border-b border-gray-100">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white text-2xl font-bold shadow-lg">
            {(settings.displayName || 'U').charAt(0).toUpperCase()}
          </div>
          <div>
            <h2 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
              <User className="w-5 h-5 text-gray-400" />
              Perfil
            </h2>
            <p className="text-sm text-gray-500">{user?.email || 'usuario@ejemplo.com'}</p>
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Nombre para mostrar
            </label>
            <input
              type="text"
              value={settings.displayName}
              onChange={(e) => setSettings({ ...settings, displayName: e.target.value })}
              className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
              placeholder="Tu nombre"
            />
          </div>
        </div>
      </div>

      {/* Search Preferences */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-6">
        <div className="flex items-center gap-3 pb-4 border-b border-gray-100">
          <div className="p-2 bg-blue-50 rounded-lg">
            <Search className="w-5 h-5 text-blue-600" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Preferencias de Búsqueda</h2>
            <p className="text-sm text-gray-500">Configura cómo funcionan tus búsquedas</p>
          </div>
        </div>

        <div className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Resultados por página
            </label>
            <select
              value={settings.resultsPerPage}
              onChange={(e) => setSettings({ ...settings, resultsPerPage: parseInt(e.target.value) })}
              className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all bg-white"
            >
              <option value={10}>10 resultados</option>
              <option value={20}>20 resultados</option>
              <option value={50}>50 resultados</option>
            </select>
          </div>

          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-xl">
            <div>
              <p className="font-medium text-gray-900">Mostrar vista previa</p>
              <p className="text-sm text-gray-500">Ver un fragmento del contenido en los resultados</p>
            </div>
            <button
              onClick={() => setSettings({ ...settings, showPreviews: !settings.showPreviews })}
              className={`relative w-12 h-6 rounded-full transition-colors duration-200 ${
                settings.showPreviews ? 'bg-blue-600' : 'bg-gray-300'
              }`}
            >
              <div className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-transform duration-200 ${
                settings.showPreviews ? 'translate-x-7' : 'translate-x-1'
              }`} />
            </button>
          </div>
        </div>
      </div>

      {/* Logout */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <button
          onClick={handleLogout}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 text-red-600 hover:bg-red-50 rounded-xl transition-colors font-medium"
        >
          <LogOut className="w-5 h-5" />
          Cerrar sesión
        </button>
      </div>
    </div>
  );
};
