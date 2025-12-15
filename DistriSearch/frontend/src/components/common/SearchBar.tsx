import React from 'react';
import { Search, X } from 'lucide-react';

interface SearchBarProps {
  value: string;
  onChange: (value: string) => void;
  onSearch?: (query: string) => void;
  placeholder?: string;
  autoFocus?: boolean;
  className?: string;
  suggestions?: string[];
  onSuggestionClick?: (suggestion: string) => void;
  loading?: boolean;
}

export const SearchBar: React.FC<SearchBarProps> = ({
  value,
  onChange,
  onSearch,
  placeholder = 'Search documents...',
  autoFocus = false,
  className = '',
  suggestions = [],
  onSuggestionClick,
  loading = false,
}) => {
  const [showSuggestions, setShowSuggestions] = React.useState(false);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && onSearch) {
      onSearch(value);
      setShowSuggestions(false);
    }
    if (e.key === 'Escape') {
      setShowSuggestions(false);
    }
  };

  const handleClear = () => {
    onChange('');
    setShowSuggestions(false);
  };

  return (
    <div className={`relative ${className}`}>
      <div className="relative">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
        <input
          type="text"
          value={value}
          onChange={(e) => {
            onChange(e.target.value);
            setShowSuggestions(true);
          }}
          onFocus={() => setShowSuggestions(true)}
          onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          autoFocus={autoFocus}
          className={`
            w-full pl-10 pr-10 py-3
            bg-white border border-gray-300 rounded-lg
            text-gray-900 placeholder-gray-500
            focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
            transition-all duration-200
          `}
        />
        {loading && (
          <div className="absolute right-10 top-1/2 transform -translate-y-1/2">
            <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          </div>
        )}
        {value && (
          <button
            onClick={handleClear}
            className="absolute right-3 top-1/2 transform -translate-y-1/2 p-1 rounded-full hover:bg-gray-100"
          >
            <X className="w-4 h-4 text-gray-400" />
          </button>
        )}
      </div>

      {/* Suggestions dropdown */}
      {showSuggestions && suggestions.length > 0 && (
        <div className="absolute z-10 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-auto">
          {suggestions.map((suggestion, index) => (
            <button
              key={index}
              onClick={() => {
                onSuggestionClick?.(suggestion);
                setShowSuggestions(false);
              }}
              className="w-full px-4 py-2 text-left text-gray-700 hover:bg-gray-100 first:rounded-t-lg last:rounded-b-lg"
            >
              <Search className="inline w-4 h-4 mr-2 text-gray-400" />
              {suggestion}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
