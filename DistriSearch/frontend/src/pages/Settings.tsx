import React, { useState } from 'react';
import {
  User,
  Search,
  Bell,
  Save,
  Palette,
  Globe,
  Moon,
  Sun,
  Check,
} from 'lucide-react';

interface SettingsSection {
  id: string;
  label: string;
  icon: React.ReactNode;
  description: string;
}

const sections: SettingsSection[] = [
  { id: 'profile', label: 'Perfil', icon: <User className="w-5 h-5" />, description: 'Tu información personal' },
  { id: 'search', label: 'Búsqueda', icon: <Search className="w-5 h-5" />, description: 'Preferencias de búsqueda' },
  { id: 'appearance', label: 'Apariencia', icon: <Palette className="w-5 h-5" />, description: 'Personaliza la interfaz' },
  { id: 'notifications', label: 'Notificaciones', icon: <Bell className="w-5 h-5" />, description: 'Gestiona tus alertas' },
];

export const Settings: React.FC = () => {
  const [activeSection, setActiveSection] = useState('profile');
  const [saved, setSaved] = useState(false);

  const [settings, setSettings] = useState({
    profile: {
      displayName: '',
      email: '',
      language: 'es',
    },
    search: {
      defaultLimit: 20,
      highlightResults: true,
      showPreviews: true,
    },
    appearance: {
      theme: 'light',
      compactMode: false,
      animationsEnabled: true,
    },
    notifications: {
      emailNotifications: true,
      searchAlerts: false,
    },
  });

  const updateSetting = (section: string, key: string, value: unknown) => {
    setSettings((prev) => ({
      ...prev,
      [section]: {
        ...prev[section as keyof typeof prev],
        [key]: value,
      },
    }));
  };

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-gray-900 to-gray-600 bg-clip-text text-transparent">
            Configuración
          </h1>
          <p className="text-gray-500 mt-1">Personaliza tu experiencia en DistriSearch</p>
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
          {saved ? 'Guardado' : 'Guardar cambios'}
        </button>
      </div>

      <div className="flex gap-6">
        {/* Sidebar */}
        <div className="w-72 flex-shrink-0">
          <nav className="bg-white rounded-2xl border border-gray-100 shadow-sm p-3 space-y-1">
            {sections.map((section) => (
              <button
                key={section.id}
                onClick={() => setActiveSection(section.id)}
                className={`w-full flex items-center gap-4 px-4 py-3.5 rounded-xl text-left transition-all duration-200 group ${
                  activeSection === section.id
                    ? 'bg-gradient-to-r from-blue-50 to-purple-50 text-blue-700 shadow-sm'
                    : 'text-gray-600 hover:bg-gray-50'
                }`}
              >
                <div className={`p-2 rounded-lg transition-colors ${
                  activeSection === section.id 
                    ? 'bg-blue-100 text-blue-600' 
                    : 'bg-gray-100 text-gray-500 group-hover:bg-gray-200'
                }`}>
                  {section.icon}
                </div>
                <div>
                  <span className="font-medium block">{section.label}</span>
                  <span className="text-xs text-gray-400">{section.description}</span>
                </div>
              </button>
            ))}
          </nav>
        </div>

        {/* Content */}
        <div className="flex-1 bg-white rounded-2xl border border-gray-100 shadow-sm p-8 animate-in fade-in duration-300">
          {activeSection === 'profile' && (
            <ProfileSettings settings={settings.profile} onUpdate={(key, value) => updateSetting('profile', key, value)} />
          )}
          {activeSection === 'search' && (
            <SearchSettings settings={settings.search} onUpdate={(key, value) => updateSetting('search', key, value)} />
          )}
          {activeSection === 'appearance' && (
            <AppearanceSettings settings={settings.appearance} onUpdate={(key, value) => updateSetting('appearance', key, value)} />
          )}
          {activeSection === 'notifications' && (
            <NotificationSettings settings={settings.notifications} onUpdate={(key, value) => updateSetting('notifications', key, value)} />
          )}
        </div>
      </div>
    </div>
  );
};

// Profile Settings
const ProfileSettings: React.FC<{ settings: any; onUpdate: (key: string, value: unknown) => void }> = ({ settings, onUpdate }) => (
  <div className="space-y-8">
    <div>
      <h2 className="text-xl font-semibold text-gray-900 mb-1">Perfil de Usuario</h2>
      <p className="text-sm text-gray-500">Administra tu información personal</p>
    </div>

    <div className="flex items-center gap-6 p-6 bg-gradient-to-r from-blue-50 to-purple-50 rounded-2xl">
      <div className="w-20 h-20 bg-gradient-to-br from-blue-500 via-purple-500 to-pink-500 rounded-2xl flex items-center justify-center shadow-lg">
        <User className="w-10 h-10 text-white" />
      </div>
      <div>
        <h3 className="font-semibold text-gray-900">Foto de perfil</h3>
        <p className="text-sm text-gray-500 mb-2">Tu avatar se genera automáticamente</p>
      </div>
    </div>

    <div className="grid gap-6">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Nombre para mostrar</label>
        <input
          type="text"
          value={settings.displayName}
          onChange={(e) => onUpdate('displayName', e.target.value)}
          placeholder="Tu nombre"
          className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          <Globe className="w-4 h-4 inline mr-2" />
          Idioma
        </label>
        <select
          value={settings.language}
          onChange={(e) => onUpdate('language', e.target.value)}
          className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
        >
          <option value="es">Español</option>
          <option value="en">English</option>
        </select>
      </div>
    </div>
  </div>
);

// Search Settings
const SearchSettings: React.FC<{ settings: any; onUpdate: (key: string, value: unknown) => void }> = ({ settings, onUpdate }) => (
  <div className="space-y-8">
    <div>
      <h2 className="text-xl font-semibold text-gray-900 mb-1">Preferencias de Búsqueda</h2>
      <p className="text-sm text-gray-500">Configura cómo funcionan tus búsquedas</p>
    </div>

    <div className="space-y-6">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Resultados por página</label>
        <div className="flex gap-3">
          {[10, 20, 50].map((num) => (
            <button
              key={num}
              onClick={() => onUpdate('defaultLimit', num)}
              className={`px-6 py-3 rounded-xl font-medium transition-all duration-200 ${
                settings.defaultLimit === num
                  ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/25'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {num}
            </button>
          ))}
        </div>
      </div>

      <ToggleOption
        label="Resaltar coincidencias"
        description="Destaca las palabras que coinciden con tu búsqueda"
        checked={settings.highlightResults}
        onChange={(v) => onUpdate('highlightResults', v)}
      />

      <ToggleOption
        label="Mostrar vista previa"
        description="Muestra un fragmento del contenido en los resultados"
        checked={settings.showPreviews}
        onChange={(v) => onUpdate('showPreviews', v)}
      />
    </div>
  </div>
);

// Appearance Settings
const AppearanceSettings: React.FC<{ settings: any; onUpdate: (key: string, value: unknown) => void }> = ({ settings, onUpdate }) => (
  <div className="space-y-8">
    <div>
      <h2 className="text-xl font-semibold text-gray-900 mb-1">Apariencia</h2>
      <p className="text-sm text-gray-500">Personaliza el aspecto de la aplicación</p>
    </div>

    <div className="space-y-6">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-3">Tema</label>
        <div className="grid grid-cols-2 gap-4">
          <button
            onClick={() => onUpdate('theme', 'light')}
            className={`p-6 rounded-2xl border-2 transition-all duration-200 flex flex-col items-center gap-3 ${
              settings.theme === 'light' 
                ? 'border-blue-500 bg-blue-50' 
                : 'border-gray-200 hover:border-gray-300'
            }`}
          >
            <Sun className={`w-8 h-8 ${settings.theme === 'light' ? 'text-blue-600' : 'text-gray-400'}`} />
            <span className={`font-medium ${settings.theme === 'light' ? 'text-blue-600' : 'text-gray-600'}`}>Claro</span>
          </button>
          <button
            onClick={() => onUpdate('theme', 'dark')}
            className={`p-6 rounded-2xl border-2 transition-all duration-200 flex flex-col items-center gap-3 ${
              settings.theme === 'dark' 
                ? 'border-blue-500 bg-blue-50' 
                : 'border-gray-200 hover:border-gray-300'
            }`}
          >
            <Moon className={`w-8 h-8 ${settings.theme === 'dark' ? 'text-blue-600' : 'text-gray-400'}`} />
            <span className={`font-medium ${settings.theme === 'dark' ? 'text-blue-600' : 'text-gray-600'}`}>Oscuro</span>
          </button>
        </div>
      </div>

      <ToggleOption
        label="Modo compacto"
        description="Reduce el espaciado para ver más contenido"
        checked={settings.compactMode}
        onChange={(v) => onUpdate('compactMode', v)}
      />

      <ToggleOption
        label="Animaciones"
        description="Activa transiciones y efectos visuales"
        checked={settings.animationsEnabled}
        onChange={(v) => onUpdate('animationsEnabled', v)}
      />
    </div>
  </div>
);

// Notification Settings
const NotificationSettings: React.FC<{ settings: any; onUpdate: (key: string, value: unknown) => void }> = ({ settings, onUpdate }) => (
  <div className="space-y-8">
    <div>
      <h2 className="text-xl font-semibold text-gray-900 mb-1">Notificaciones</h2>
      <p className="text-sm text-gray-500">Configura cómo quieres recibir alertas</p>
    </div>

    <div className="space-y-6">
      <ToggleOption
        label="Notificaciones por email"
        description="Recibe actualizaciones importantes en tu correo"
        checked={settings.emailNotifications}
        onChange={(v) => onUpdate('emailNotifications', v)}
      />

      <ToggleOption
        label="Alertas de búsqueda"
        description="Notificarte cuando haya nuevos documentos que coincidan con tus búsquedas guardadas"
        checked={settings.searchAlerts}
        onChange={(v) => onUpdate('searchAlerts', v)}
      />
    </div>
  </div>
);

// Toggle Option Component
const ToggleOption: React.FC<{
  label: string;
  description: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}> = ({ label, description, checked, onChange }) => (
  <div className="flex items-center justify-between p-4 bg-gray-50 rounded-xl hover:bg-gray-100 transition-colors">
    <div>
      <p className="font-medium text-gray-900">{label}</p>
      <p className="text-sm text-gray-500">{description}</p>
    </div>
    <button
      onClick={() => onChange(!checked)}
      className={`relative w-14 h-8 rounded-full transition-all duration-300 ${
        checked ? 'bg-blue-600' : 'bg-gray-300'
      }`}
    >
      <span
        className={`absolute top-1 w-6 h-6 bg-white rounded-full shadow-md transition-all duration-300 ${
          checked ? 'left-7' : 'left-1'
        }`}
      />
    </button>
  </div>
);
