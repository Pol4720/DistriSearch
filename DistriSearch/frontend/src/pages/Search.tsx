import React, { useState, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Search as SearchIcon,
  Filter,
  Clock,
  FileText,
  ChevronDown,
  X,
  Sliders,
} from 'lucide-react';
import {
  useSearchMutation,
  useSearchHistory,
  useSearchSuggestions,
  useClearSearchHistory,
} from '../../hooks';
import {
  SearchBar,
  DocumentCard,
  LoadingSpinner,
  EmptyState,
  ErrorMessage,
  Badge,
} from '../../components/common';
import type { SearchRequest, SearchResult } from '../../types';

export const SearchPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  
  const [query, setQuery] = useState(searchParams.get('q') || '');
  const [showFilters, setShowFilters] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [filters, setFilters] = useState<SearchRequest['filters']>({});
  const [semanticOptions, setSemanticOptions] = useState({
    use_tfidf: true,
    use_minhash: true,
    use_lda: false,
    tfidf_weight: 0.5,
    minhash_weight: 0.3,
    lda_weight: 0.2,
  });

  const searchMutation = useSearchMutation();
  const { data: history } = useSearchHistory({ limit: 10 });
  const { data: suggestions } = useSearchSuggestions(query, {
    enabled: query.length >= 2,
  });
  const clearHistory = useClearSearchHistory();

  const handleSearch = useCallback(
    (searchQuery: string) => {
      if (!searchQuery.trim()) return;

      setSearchParams({ q: searchQuery });
      setShowHistory(false);

      const request: SearchRequest = {
        query: searchQuery,
        limit: 20,
        offset: 0,
        filters,
        semantic_options: {
          use_tfidf: semanticOptions.use_tfidf,
          use_minhash: semanticOptions.use_minhash,
          use_lda: semanticOptions.use_lda,
          weights: {
            tfidf: semanticOptions.tfidf_weight,
            minhash: semanticOptions.minhash_weight,
            lda: semanticOptions.lda_weight,
          },
        },
      };

      searchMutation.mutate(request);
    },
    [filters, semanticOptions, setSearchParams, searchMutation]
  );

  const handleDocumentClick = (result: SearchResult) => {
    navigate(`/documents/${result.document.id}`);
  };

  const handleHistoryClick = (historyQuery: string) => {
    setQuery(historyQuery);
    handleSearch(historyQuery);
  };

  const handleSuggestionClick = (suggestion: string) => {
    setQuery(suggestion);
    handleSearch(suggestion);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="text-center mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          <SearchIcon className="inline-block w-8 h-8 mr-2 text-blue-600" />
          DistriSearch
        </h1>
        <p className="text-gray-500">
          Distributed semantic search across your document collection
        </p>
      </div>

      {/* Search Bar */}
      <div className="relative">
        <SearchBar
          value={query}
          onChange={setQuery}
          onSearch={handleSearch}
          placeholder="Search documents..."
          autoFocus
          suggestions={suggestions || []}
          onSuggestionClick={handleSuggestionClick}
          loading={searchMutation.isPending}
          className="w-full"
        />

        {/* Action buttons */}
        <div className="flex items-center gap-2 mt-3">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`
              flex items-center gap-2 px-4 py-2 rounded-lg border transition-colors
              ${showFilters ? 'bg-blue-50 border-blue-300 text-blue-700' : 'border-gray-300 text-gray-600 hover:bg-gray-50'}
            `}
          >
            <Filter className="w-4 h-4" />
            Filters
            <ChevronDown className={`w-4 h-4 transition-transform ${showFilters ? 'rotate-180' : ''}`} />
          </button>

          <button
            onClick={() => setShowHistory(!showHistory)}
            className={`
              flex items-center gap-2 px-4 py-2 rounded-lg border transition-colors
              ${showHistory ? 'bg-blue-50 border-blue-300 text-blue-700' : 'border-gray-300 text-gray-600 hover:bg-gray-50'}
            `}
          >
            <Clock className="w-4 h-4" />
            History
          </button>

          <button
            onClick={() => handleSearch(query)}
            disabled={!query.trim() || searchMutation.isPending}
            className="
              flex items-center gap-2 px-6 py-2 bg-blue-600 text-white rounded-lg
              hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors
            "
          >
            <SearchIcon className="w-4 h-4" />
            Search
          </button>
        </div>
      </div>

      {/* Filters Panel */}
      {showFilters && (
        <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-gray-900 flex items-center gap-2">
              <Sliders className="w-5 h-5" />
              Search Options
            </h3>
            <button
              onClick={() => setShowFilters(false)}
              className="p-1 hover:bg-gray-100 rounded"
            >
              <X className="w-5 h-5 text-gray-500" />
            </button>
          </div>

          {/* Semantic Options */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Vectorization Methods
              </label>
              <div className="space-y-2">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={semanticOptions.use_tfidf}
                    onChange={(e) =>
                      setSemanticOptions({ ...semanticOptions, use_tfidf: e.target.checked })
                    }
                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-600">TF-IDF</span>
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={semanticOptions.use_minhash}
                    onChange={(e) =>
                      setSemanticOptions({ ...semanticOptions, use_minhash: e.target.checked })
                    }
                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-600">MinHash (Similarity)</span>
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={semanticOptions.use_lda}
                    onChange={(e) =>
                      setSemanticOptions({ ...semanticOptions, use_lda: e.target.checked })
                    }
                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-600">LDA (Topic Modeling)</span>
                </label>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Date Range
              </label>
              <div className="flex gap-2">
                <input
                  type="date"
                  value={filters.date_from || ''}
                  onChange={(e) =>
                    setFilters({ ...filters, date_from: e.target.value || undefined })
                  }
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm"
                  placeholder="From"
                />
                <input
                  type="date"
                  value={filters.date_to || ''}
                  onChange={(e) =>
                    setFilters({ ...filters, date_to: e.target.value || undefined })
                  }
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm"
                  placeholder="To"
                />
              </div>
            </div>
          </div>

          {/* Weight Sliders */}
          {(semanticOptions.use_tfidf || semanticOptions.use_minhash || semanticOptions.use_lda) && (
            <div className="pt-4 border-t border-gray-100">
              <label className="block text-sm font-medium text-gray-700 mb-3">
                Method Weights
              </label>
              <div className="space-y-3">
                {semanticOptions.use_tfidf && (
                  <div>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-gray-600">TF-IDF Weight</span>
                      <span className="text-gray-900">{semanticOptions.tfidf_weight.toFixed(2)}</span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.1"
                      value={semanticOptions.tfidf_weight}
                      onChange={(e) =>
                        setSemanticOptions({
                          ...semanticOptions,
                          tfidf_weight: parseFloat(e.target.value),
                        })
                      }
                      className="w-full"
                    />
                  </div>
                )}
                {semanticOptions.use_minhash && (
                  <div>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-gray-600">MinHash Weight</span>
                      <span className="text-gray-900">{semanticOptions.minhash_weight.toFixed(2)}</span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.1"
                      value={semanticOptions.minhash_weight}
                      onChange={(e) =>
                        setSemanticOptions({
                          ...semanticOptions,
                          minhash_weight: parseFloat(e.target.value),
                        })
                      }
                      className="w-full"
                    />
                  </div>
                )}
                {semanticOptions.use_lda && (
                  <div>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-gray-600">LDA Weight</span>
                      <span className="text-gray-900">{semanticOptions.lda_weight.toFixed(2)}</span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.1"
                      value={semanticOptions.lda_weight}
                      onChange={(e) =>
                        setSemanticOptions({
                          ...semanticOptions,
                          lda_weight: parseFloat(e.target.value),
                        })
                      }
                      className="w-full"
                    />
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* History Panel */}
      {showHistory && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-900">Recent Searches</h3>
            <button
              onClick={() => clearHistory.mutate()}
              className="text-sm text-red-600 hover:text-red-700"
            >
              Clear History
            </button>
          </div>
          {history?.length ? (
            <div className="space-y-2">
              {history.map((item, index) => (
                <button
                  key={index}
                  onClick={() => handleHistoryClick(item.query)}
                  className="w-full flex items-center gap-3 p-3 text-left hover:bg-gray-50 rounded-lg transition-colors"
                >
                  <Clock className="w-4 h-4 text-gray-400" />
                  <span className="text-gray-700">{item.query}</span>
                  <span className="ml-auto text-xs text-gray-400">
                    {item.results_count} results
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-center py-4">No search history</p>
          )}
        </div>
      )}

      {/* Results */}
      <div className="space-y-4">
        {searchMutation.isPending && (
          <div className="flex items-center justify-center py-12">
            <LoadingSpinner size="lg" />
            <span className="ml-3 text-gray-500">Searching across nodes...</span>
          </div>
        )}

        {searchMutation.isError && (
          <ErrorMessage
            title="Search failed"
            message={searchMutation.error?.message || 'An error occurred while searching'}
            onRetry={() => handleSearch(query)}
          />
        )}

        {searchMutation.isSuccess && searchMutation.data && (
          <>
            {/* Results header */}
            <div className="flex items-center justify-between">
              <p className="text-gray-600">
                Found <strong>{searchMutation.data.total_results}</strong> results in{' '}
                <strong>{searchMutation.data.search_time_ms?.toFixed(0)}ms</strong>
              </p>
              <div className="flex items-center gap-2">
                {searchMutation.data.nodes_queried && (
                  <Badge variant="info">
                    {searchMutation.data.nodes_queried} nodes queried
                  </Badge>
                )}
              </div>
            </div>

            {/* Results list */}
            {searchMutation.data.results.length > 0 ? (
              <div className="space-y-4">
                {searchMutation.data.results.map((result) => (
                  <SearchResultCard
                    key={result.document.id}
                    result={result}
                    onClick={() => handleDocumentClick(result)}
                  />
                ))}
              </div>
            ) : (
              <EmptyState
                icon={<SearchIcon className="w-12 h-12" />}
                title="No results found"
                description={`We couldn't find any documents matching "${query}". Try different keywords or filters.`}
              />
            )}
          </>
        )}

        {!searchMutation.isPending && !searchMutation.isSuccess && !searchMutation.isError && (
          <EmptyState
            icon={<FileText className="w-12 h-12" />}
            title="Start searching"
            description="Enter a query above to search across your distributed document collection."
          />
        )}
      </div>
    </div>
  );
};

// Search Result Card Component
interface SearchResultCardProps {
  result: SearchResult;
  onClick: () => void;
}

const SearchResultCard: React.FC<SearchResultCardProps> = ({ result, onClick }) => {
  return (
    <div
      onClick={onClick}
      className="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md hover:border-gray-300 cursor-pointer transition-all"
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <FileText className="w-5 h-5 text-blue-600" />
          <div>
            <h3 className="font-semibold text-gray-900 hover:text-blue-600">
              {result.document.title || result.document.filename}
            </h3>
            <p className="text-sm text-gray-500">{result.document.filename}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="info">Score: {result.score.toFixed(3)}</Badge>
          <Badge variant="default">P{result.document.partition_id}</Badge>
        </div>
      </div>

      {/* Highlights */}
      {result.highlights && result.highlights.length > 0 && (
        <div className="mt-3 space-y-2">
          {result.highlights.slice(0, 2).map((highlight, index) => (
            <p
              key={index}
              className="text-sm text-gray-600 line-clamp-2"
              dangerouslySetInnerHTML={{ __html: highlight }}
            />
          ))}
        </div>
      )}

      {/* Score breakdown */}
      {result.score_breakdown && (
        <div className="mt-3 pt-3 border-t border-gray-100 flex gap-4 text-xs text-gray-500">
          {result.score_breakdown.tfidf !== undefined && (
            <span>TF-IDF: {result.score_breakdown.tfidf.toFixed(3)}</span>
          )}
          {result.score_breakdown.minhash !== undefined && (
            <span>MinHash: {result.score_breakdown.minhash.toFixed(3)}</span>
          )}
          {result.score_breakdown.lda !== undefined && (
            <span>LDA: {result.score_breakdown.lda.toFixed(3)}</span>
          )}
        </div>
      )}
    </div>
  );
};
