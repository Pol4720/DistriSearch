import React from 'react';

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  size = 'md',
  className = '',
}) => {
  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-8 h-8',
    lg: 'w-12 h-12',
  };

  return (
    <div className={`flex items-center justify-center ${className}`}>
      <div
        className={`
          ${sizeClasses[size]}
          border-2 border-blue-200 border-t-blue-600
          rounded-full animate-spin
        `}
      />
    </div>
  );
};

interface LoadingOverlayProps {
  message?: string;
}

export const LoadingOverlay: React.FC<LoadingOverlayProps> = ({
  message = 'Loading...',
}) => {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
      <div className="bg-white rounded-lg p-6 flex flex-col items-center gap-4">
        <LoadingSpinner size="lg" />
        <p className="text-gray-600">{message}</p>
      </div>
    </div>
  );
};

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon,
  title,
  description,
  action,
}) => {
  return (
    <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
      {icon && (
        <div className="mb-4 text-gray-400">
          {icon}
        </div>
      )}
      <h3 className="text-lg font-medium text-gray-900 mb-2">{title}</h3>
      {description && (
        <p className="text-gray-500 max-w-sm mb-4">{description}</p>
      )}
      {action && <div>{action}</div>}
    </div>
  );
};

interface ErrorMessageProps {
  title?: string;
  message: string;
  onRetry?: () => void;
}

export const ErrorMessage: React.FC<ErrorMessageProps> = ({
  title = 'Error',
  message,
  onRetry,
}) => {
  return (
    <div className="bg-red-50 border border-red-200 rounded-lg p-4">
      <h4 className="text-red-800 font-medium mb-1">{title}</h4>
      <p className="text-red-600 text-sm mb-3">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-3 py-1.5 bg-red-100 text-red-700 rounded-md text-sm hover:bg-red-200 transition-colors"
        >
          Try again
        </button>
      )}
    </div>
  );
};

interface ProgressBarProps {
  value: number;
  max?: number;
  showLabel?: boolean;
  className?: string;
  color?: 'blue' | 'green' | 'yellow' | 'red';
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  value,
  max = 100,
  showLabel = true,
  className = '',
  color = 'blue',
}) => {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100));
  
  const colorClasses = {
    blue: 'bg-blue-600',
    green: 'bg-green-600',
    yellow: 'bg-yellow-500',
    red: 'bg-red-600',
  };

  return (
    <div className={className}>
      <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-300 ${colorClasses[color]}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      {showLabel && (
        <p className="text-xs text-gray-500 mt-1 text-right">
          {percentage.toFixed(0)}%
        </p>
      )}
    </div>
  );
};

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'default' | 'success' | 'warning' | 'error' | 'info';
  size?: 'sm' | 'md';
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'default',
  size = 'md',
}) => {
  const variantClasses = {
    default: 'bg-gray-100 text-gray-700',
    success: 'bg-green-100 text-green-700',
    warning: 'bg-yellow-100 text-yellow-700',
    error: 'bg-red-100 text-red-700',
    info: 'bg-blue-100 text-blue-700',
  };

  const sizeClasses = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-2.5 py-1 text-sm',
  };

  return (
    <span
      className={`
        inline-flex items-center font-medium rounded-full
        ${variantClasses[variant]}
        ${sizeClasses[size]}
      `}
    >
      {children}
    </span>
  );
};
