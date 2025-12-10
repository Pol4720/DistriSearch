import React, { useState } from 'react';
import {
  Settings as SettingsIcon,
  Server,
  Database,
  Search,
  Shield,
  Bell,
  Save,
  RotateCcw,
} from 'lucide-react';
import { Badge } from '../../components/common';

interface SettingsSection {
  id: string;
  label: string;
  icon: React.ReactNode;
}

const sections: SettingsSection[] = [
  { id: 'general', label: 'General', icon: <SettingsIcon className="w-5 h-5" /> },
  { id: 'cluster', label: 'Cluster', icon: <Server className="w-5 h-5" /> },
  { id: 'search', label: 'Search', icon: <Search className="w-5 h-5" /> },
  { id: 'storage', label: 'Storage', icon: <Database className="w-5 h-5" /> },
  { id: 'security', label: 'Security', icon: <Shield className="w-5 h-5" /> },
  { id: 'notifications', label: 'Notifications', icon: <Bell className="w-5 h-5" /> },
];

export const Settings: React.FC = () => {
  const [activeSection, setActiveSection] = useState('general');
  const [hasChanges, setHasChanges] = useState(false);

  // Settings state
  const [settings, setSettings] = useState({
    general: {
      systemName: 'DistriSearch',
      timezone: 'UTC',
      language: 'en',
      darkMode: false,
    },
    cluster: {
      replicationFactor: 2,
      partitionCount: 16,
      heartbeatInterval: 5000,
      nodeTimeout: 30000,
      autoRebalance: true,
    },
    search: {
      defaultLimit: 20,
      maxLimit: 100,
      useTfIdf: true,
      useMinHash: true,
      useLda: false,
      tfidfWeight: 0.5,
      minhashWeight: 0.3,
      ldaWeight: 0.2,
      highlightEnabled: true,
      highlightPreTag: '<mark>',
      highlightPostTag: '</mark>',
    },
    storage: {
      mongoUri: 'mongodb://localhost:27017',
      redisUri: 'redis://localhost:6379',
      dataPath: '/data/distrisearch',
      maxDocumentSize: 10,
      compressionEnabled: true,
    },
    security: {
      jwtSecret: '********',
      tokenExpiration: 3600,
      rateLimitEnabled: true,
      rateLimitRequests: 100,
      rateLimitWindow: 60,
      corsOrigins: '*',
    },
    notifications: {
      emailEnabled: false,
      emailSmtp: '',
      slackEnabled: false,
      slackWebhook: '',
      alertOnNodeFailure: true,
      alertOnRebalance: true,
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
    setHasChanges(true);
  };

  const handleSave = () => {
    // TODO: Save settings to backend
    console.log('Saving settings:', settings);
    setHasChanges(false);
  };

  const handleReset = () => {
    // TODO: Reset to defaults
    setHasChanges(false);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
          <p className="text-gray-500">Configure your DistriSearch system</p>
        </div>
        <div className="flex items-center gap-3">
          {hasChanges && <Badge variant="warning">Unsaved changes</Badge>}
          <button
            onClick={handleReset}
            disabled={!hasChanges}
            className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50"
          >
            <RotateCcw className="w-5 h-5" />
            Reset
          </button>
          <button
            onClick={handleSave}
            disabled={!hasChanges}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
          >
            <Save className="w-5 h-5" />
            Save Changes
          </button>
        </div>
      </div>

      <div className="flex gap-6">
        {/* Sidebar */}
        <div className="w-64 flex-shrink-0">
          <nav className="bg-white rounded-xl border border-gray-200 p-2">
            {sections.map((section) => (
              <button
                key={section.id}
                onClick={() => setActiveSection(section.id)}
                className={`
                  w-full flex items-center gap-3 px-4 py-3 rounded-lg text-left transition-colors
                  ${
                    activeSection === section.id
                      ? 'bg-blue-50 text-blue-700'
                      : 'text-gray-600 hover:bg-gray-50'
                  }
                `}
              >
                {section.icon}
                <span className="font-medium">{section.label}</span>
              </button>
            ))}
          </nav>
        </div>

        {/* Content */}
        <div className="flex-1 bg-white rounded-xl border border-gray-200 p-6">
          {activeSection === 'general' && (
            <GeneralSettings
              settings={settings.general}
              onUpdate={(key, value) => updateSetting('general', key, value)}
            />
          )}
          {activeSection === 'cluster' && (
            <ClusterSettings
              settings={settings.cluster}
              onUpdate={(key, value) => updateSetting('cluster', key, value)}
            />
          )}
          {activeSection === 'search' && (
            <SearchSettings
              settings={settings.search}
              onUpdate={(key, value) => updateSetting('search', key, value)}
            />
          )}
          {activeSection === 'storage' && (
            <StorageSettings
              settings={settings.storage}
              onUpdate={(key, value) => updateSetting('storage', key, value)}
            />
          )}
          {activeSection === 'security' && (
            <SecuritySettings
              settings={settings.security}
              onUpdate={(key, value) => updateSetting('security', key, value)}
            />
          )}
          {activeSection === 'notifications' && (
            <NotificationSettings
              settings={settings.notifications}
              onUpdate={(key, value) => updateSetting('notifications', key, value)}
            />
          )}
        </div>
      </div>
    </div>
  );
};

// Settings Section Components
interface SettingsProps<T> {
  settings: T;
  onUpdate: (key: string, value: unknown) => void;
}

const GeneralSettings: React.FC<SettingsProps<typeof defaultSettings.general>> = ({
  settings,
  onUpdate,
}) => (
  <div className="space-y-6">
    <h2 className="text-lg font-semibold text-gray-900">General Settings</h2>

    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          System Name
        </label>
        <input
          type="text"
          value={settings.systemName}
          onChange={(e) => onUpdate('systemName', e.target.value)}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Timezone
        </label>
        <select
          value={settings.timezone}
          onChange={(e) => onUpdate('timezone', e.target.value)}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        >
          <option value="UTC">UTC</option>
          <option value="America/New_York">Eastern Time</option>
          <option value="America/Los_Angeles">Pacific Time</option>
          <option value="Europe/London">London</option>
          <option value="Asia/Tokyo">Tokyo</option>
        </select>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Language
        </label>
        <select
          value={settings.language}
          onChange={(e) => onUpdate('language', e.target.value)}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        >
          <option value="en">English</option>
          <option value="es">Spanish</option>
          <option value="fr">French</option>
          <option value="de">German</option>
        </select>
      </div>

      <div className="flex items-center justify-between">
        <div>
          <label className="block text-sm font-medium text-gray-700">
            Dark Mode
          </label>
          <p className="text-sm text-gray-500">Enable dark theme</p>
        </div>
        <button
          onClick={() => onUpdate('darkMode', !settings.darkMode)}
          className={`
            relative inline-flex h-6 w-11 items-center rounded-full transition-colors
            ${settings.darkMode ? 'bg-blue-600' : 'bg-gray-200'}
          `}
        >
          <span
            className={`
              inline-block h-4 w-4 transform rounded-full bg-white transition-transform
              ${settings.darkMode ? 'translate-x-6' : 'translate-x-1'}
            `}
          />
        </button>
      </div>
    </div>
  </div>
);

const ClusterSettings: React.FC<SettingsProps<typeof defaultSettings.cluster>> = ({
  settings,
  onUpdate,
}) => (
  <div className="space-y-6">
    <h2 className="text-lg font-semibold text-gray-900">Cluster Configuration</h2>

    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Replication Factor
          </label>
          <input
            type="number"
            min="1"
            max="5"
            value={settings.replicationFactor}
            onChange={(e) => onUpdate('replicationFactor', parseInt(e.target.value))}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Partition Count
          </label>
          <input
            type="number"
            min="4"
            max="64"
            value={settings.partitionCount}
            onChange={(e) => onUpdate('partitionCount', parseInt(e.target.value))}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Heartbeat Interval (ms)
          </label>
          <input
            type="number"
            min="1000"
            max="30000"
            step="1000"
            value={settings.heartbeatInterval}
            onChange={(e) => onUpdate('heartbeatInterval', parseInt(e.target.value))}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Node Timeout (ms)
          </label>
          <input
            type="number"
            min="10000"
            max="120000"
            step="5000"
            value={settings.nodeTimeout}
            onChange={(e) => onUpdate('nodeTimeout', parseInt(e.target.value))}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
      </div>

      <div className="flex items-center justify-between">
        <div>
          <label className="block text-sm font-medium text-gray-700">
            Auto Rebalance
          </label>
          <p className="text-sm text-gray-500">
            Automatically rebalance when nodes join/leave
          </p>
        </div>
        <button
          onClick={() => onUpdate('autoRebalance', !settings.autoRebalance)}
          className={`
            relative inline-flex h-6 w-11 items-center rounded-full transition-colors
            ${settings.autoRebalance ? 'bg-blue-600' : 'bg-gray-200'}
          `}
        >
          <span
            className={`
              inline-block h-4 w-4 transform rounded-full bg-white transition-transform
              ${settings.autoRebalance ? 'translate-x-6' : 'translate-x-1'}
            `}
          />
        </button>
      </div>
    </div>
  </div>
);

const SearchSettings: React.FC<SettingsProps<typeof defaultSettings.search>> = ({
  settings,
  onUpdate,
}) => (
  <div className="space-y-6">
    <h2 className="text-lg font-semibold text-gray-900">Search Configuration</h2>

    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Default Result Limit
          </label>
          <input
            type="number"
            min="5"
            max="100"
            value={settings.defaultLimit}
            onChange={(e) => onUpdate('defaultLimit', parseInt(e.target.value))}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Max Result Limit
          </label>
          <input
            type="number"
            min="20"
            max="1000"
            value={settings.maxLimit}
            onChange={(e) => onUpdate('maxLimit', parseInt(e.target.value))}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-3">
          Vectorization Methods
        </label>
        <div className="space-y-3">
          <label className="flex items-center gap-3">
            <input
              type="checkbox"
              checked={settings.useTfIdf}
              onChange={(e) => onUpdate('useTfIdf', e.target.checked)}
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span>TF-IDF (Term Frequency-Inverse Document Frequency)</span>
          </label>
          <label className="flex items-center gap-3">
            <input
              type="checkbox"
              checked={settings.useMinHash}
              onChange={(e) => onUpdate('useMinHash', e.target.checked)}
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span>MinHash (Similarity Detection)</span>
          </label>
          <label className="flex items-center gap-3">
            <input
              type="checkbox"
              checked={settings.useLda}
              onChange={(e) => onUpdate('useLda', e.target.checked)}
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span>LDA (Latent Dirichlet Allocation)</span>
          </label>
        </div>
      </div>

      <div className="flex items-center justify-between">
        <div>
          <label className="block text-sm font-medium text-gray-700">
            Highlight Results
          </label>
          <p className="text-sm text-gray-500">
            Highlight matching terms in results
          </p>
        </div>
        <button
          onClick={() => onUpdate('highlightEnabled', !settings.highlightEnabled)}
          className={`
            relative inline-flex h-6 w-11 items-center rounded-full transition-colors
            ${settings.highlightEnabled ? 'bg-blue-600' : 'bg-gray-200'}
          `}
        >
          <span
            className={`
              inline-block h-4 w-4 transform rounded-full bg-white transition-transform
              ${settings.highlightEnabled ? 'translate-x-6' : 'translate-x-1'}
            `}
          />
        </button>
      </div>
    </div>
  </div>
);

const StorageSettings: React.FC<SettingsProps<typeof defaultSettings.storage>> = ({
  settings,
  onUpdate,
}) => (
  <div className="space-y-6">
    <h2 className="text-lg font-semibold text-gray-900">Storage Configuration</h2>

    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          MongoDB URI
        </label>
        <input
          type="text"
          value={settings.mongoUri}
          onChange={(e) => onUpdate('mongoUri', e.target.value)}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Redis URI
        </label>
        <input
          type="text"
          value={settings.redisUri}
          onChange={(e) => onUpdate('redisUri', e.target.value)}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Data Path
        </label>
        <input
          type="text"
          value={settings.dataPath}
          onChange={(e) => onUpdate('dataPath', e.target.value)}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Max Document Size (MB)
        </label>
        <input
          type="number"
          min="1"
          max="100"
          value={settings.maxDocumentSize}
          onChange={(e) => onUpdate('maxDocumentSize', parseInt(e.target.value))}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>

      <div className="flex items-center justify-between">
        <div>
          <label className="block text-sm font-medium text-gray-700">
            Enable Compression
          </label>
          <p className="text-sm text-gray-500">Compress stored documents</p>
        </div>
        <button
          onClick={() => onUpdate('compressionEnabled', !settings.compressionEnabled)}
          className={`
            relative inline-flex h-6 w-11 items-center rounded-full transition-colors
            ${settings.compressionEnabled ? 'bg-blue-600' : 'bg-gray-200'}
          `}
        >
          <span
            className={`
              inline-block h-4 w-4 transform rounded-full bg-white transition-transform
              ${settings.compressionEnabled ? 'translate-x-6' : 'translate-x-1'}
            `}
          />
        </button>
      </div>
    </div>
  </div>
);

const SecuritySettings: React.FC<SettingsProps<typeof defaultSettings.security>> = ({
  settings,
  onUpdate,
}) => (
  <div className="space-y-6">
    <h2 className="text-lg font-semibold text-gray-900">Security Configuration</h2>

    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          JWT Secret
        </label>
        <input
          type="password"
          value={settings.jwtSecret}
          onChange={(e) => onUpdate('jwtSecret', e.target.value)}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Token Expiration (seconds)
        </label>
        <input
          type="number"
          min="300"
          max="86400"
          value={settings.tokenExpiration}
          onChange={(e) => onUpdate('tokenExpiration', parseInt(e.target.value))}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>

      <div className="flex items-center justify-between">
        <div>
          <label className="block text-sm font-medium text-gray-700">
            Rate Limiting
          </label>
          <p className="text-sm text-gray-500">Enable API rate limiting</p>
        </div>
        <button
          onClick={() => onUpdate('rateLimitEnabled', !settings.rateLimitEnabled)}
          className={`
            relative inline-flex h-6 w-11 items-center rounded-full transition-colors
            ${settings.rateLimitEnabled ? 'bg-blue-600' : 'bg-gray-200'}
          `}
        >
          <span
            className={`
              inline-block h-4 w-4 transform rounded-full bg-white transition-transform
              ${settings.rateLimitEnabled ? 'translate-x-6' : 'translate-x-1'}
            `}
          />
        </button>
      </div>

      {settings.rateLimitEnabled && (
        <div className="grid grid-cols-2 gap-4 pl-4 border-l-2 border-gray-200">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Requests per Window
            </label>
            <input
              type="number"
              min="10"
              max="1000"
              value={settings.rateLimitRequests}
              onChange={(e) => onUpdate('rateLimitRequests', parseInt(e.target.value))}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Window Size (seconds)
            </label>
            <input
              type="number"
              min="10"
              max="3600"
              value={settings.rateLimitWindow}
              onChange={(e) => onUpdate('rateLimitWindow', parseInt(e.target.value))}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
        </div>
      )}

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          CORS Origins
        </label>
        <input
          type="text"
          value={settings.corsOrigins}
          onChange={(e) => onUpdate('corsOrigins', e.target.value)}
          placeholder="* for all, or comma-separated origins"
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>
    </div>
  </div>
);

const NotificationSettings: React.FC<SettingsProps<typeof defaultSettings.notifications>> = ({
  settings,
  onUpdate,
}) => (
  <div className="space-y-6">
    <h2 className="text-lg font-semibold text-gray-900">Notification Settings</h2>

    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <label className="block text-sm font-medium text-gray-700">
            Email Notifications
          </label>
          <p className="text-sm text-gray-500">Send alerts via email</p>
        </div>
        <button
          onClick={() => onUpdate('emailEnabled', !settings.emailEnabled)}
          className={`
            relative inline-flex h-6 w-11 items-center rounded-full transition-colors
            ${settings.emailEnabled ? 'bg-blue-600' : 'bg-gray-200'}
          `}
        >
          <span
            className={`
              inline-block h-4 w-4 transform rounded-full bg-white transition-transform
              ${settings.emailEnabled ? 'translate-x-6' : 'translate-x-1'}
            `}
          />
        </button>
      </div>

      {settings.emailEnabled && (
        <div className="pl-4 border-l-2 border-gray-200">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            SMTP Server
          </label>
          <input
            type="text"
            value={settings.emailSmtp}
            onChange={(e) => onUpdate('emailSmtp', e.target.value)}
            placeholder="smtp.example.com:587"
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
      )}

      <div className="flex items-center justify-between">
        <div>
          <label className="block text-sm font-medium text-gray-700">
            Slack Notifications
          </label>
          <p className="text-sm text-gray-500">Send alerts to Slack</p>
        </div>
        <button
          onClick={() => onUpdate('slackEnabled', !settings.slackEnabled)}
          className={`
            relative inline-flex h-6 w-11 items-center rounded-full transition-colors
            ${settings.slackEnabled ? 'bg-blue-600' : 'bg-gray-200'}
          `}
        >
          <span
            className={`
              inline-block h-4 w-4 transform rounded-full bg-white transition-transform
              ${settings.slackEnabled ? 'translate-x-6' : 'translate-x-1'}
            `}
          />
        </button>
      </div>

      {settings.slackEnabled && (
        <div className="pl-4 border-l-2 border-gray-200">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Webhook URL
          </label>
          <input
            type="text"
            value={settings.slackWebhook}
            onChange={(e) => onUpdate('slackWebhook', e.target.value)}
            placeholder="https://hooks.slack.com/..."
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
      )}

      <div className="border-t border-gray-200 pt-4">
        <h3 className="text-sm font-medium text-gray-700 mb-3">Alert Types</h3>
        <div className="space-y-3">
          <label className="flex items-center gap-3">
            <input
              type="checkbox"
              checked={settings.alertOnNodeFailure}
              onChange={(e) => onUpdate('alertOnNodeFailure', e.target.checked)}
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span>Node failure alerts</span>
          </label>
          <label className="flex items-center gap-3">
            <input
              type="checkbox"
              checked={settings.alertOnRebalance}
              onChange={(e) => onUpdate('alertOnRebalance', e.target.checked)}
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span>Rebalance notifications</span>
          </label>
        </div>
      </div>
    </div>
  </div>
);

// Default settings type
const defaultSettings = {
  general: {
    systemName: 'DistriSearch',
    timezone: 'UTC',
    language: 'en',
    darkMode: false,
  },
  cluster: {
    replicationFactor: 2,
    partitionCount: 16,
    heartbeatInterval: 5000,
    nodeTimeout: 30000,
    autoRebalance: true,
  },
  search: {
    defaultLimit: 20,
    maxLimit: 100,
    useTfIdf: true,
    useMinHash: true,
    useLda: false,
    tfidfWeight: 0.5,
    minhashWeight: 0.3,
    ldaWeight: 0.2,
    highlightEnabled: true,
    highlightPreTag: '<mark>',
    highlightPostTag: '</mark>',
  },
  storage: {
    mongoUri: 'mongodb://localhost:27017',
    redisUri: 'redis://localhost:6379',
    dataPath: '/data/distrisearch',
    maxDocumentSize: 10,
    compressionEnabled: true,
  },
  security: {
    jwtSecret: '********',
    tokenExpiration: 3600,
    rateLimitEnabled: true,
    rateLimitRequests: 100,
    rateLimitWindow: 60,
    corsOrigins: '*',
  },
  notifications: {
    emailEnabled: false,
    emailSmtp: '',
    slackEnabled: false,
    slackWebhook: '',
    alertOnNodeFailure: true,
    alertOnRebalance: true,
  },
};
