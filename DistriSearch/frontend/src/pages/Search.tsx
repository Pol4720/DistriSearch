import React, { useState, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Search as SearchIcon,
  Clock,
  FileText,
  X,
  Download,
  Eye,
  Zap,
  Brain,
  Sparkles,
} from 'lucide-react';
import { documentService } from '../services';
import {
  useSearchMutation,
  useSearchHistory,
  useClearSearchHistory,
} from '../hooks';
import {
  SearchBar,
  LoadingSpinner,
  EmptyState,
  ErrorMessage,
} from '../components/common';
import type { SearchRequest, SearchResult } from '../types';

type SearchType = 'hybrid' | 'keyword' | 'semantic';

export const SearchPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  
  const [query, setQuery] = useState(searchParams.get('q') || '');
  const [showHistory, setShowHistory] = useState(false);
  const [searchType, setSearchType] = useState<SearchType>('hybrid');
  const [viewingDocument, setViewingDocument] = useState<{ id: string; title: string; content: string } | null>(null);
  const [loadingDocument, setLoadingDocument] = useState(false);

  const searchMutation = useSearchMutation();
  const { data: history } = useSearchHistory({ limit: 10 });
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
        search_type: searchType,
      };

      searchMutation.mutate(request);
    },
    [searchType, setSearchParams, searchMutation]
  );

  const handleDocumentClick = async (result: SearchResult) => {
    try {
      setLoadingDocument(true);
      const doc = await documentService.get(result.document_id);
      setViewingDocument({
        id: result.document_id,
        title: doc.title || result.title || 'Documento',
        content: doc.content || 'Sin contenido disponible'
      });
    } catch (error) {
      console.error('Error loading document:', error);
    } finally {
      setLoadingDocument(false);
    }
  };

  const handleDownload = async (result: SearchResult) => {
    try {
      const { blob, filename } = await documentService.download(result.document_id);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename || result.title || result.document?.title || 'document';
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Download failed:', error);
    }
  };

  const handleHistoryClick = (historyQuery: string) => {
    setQuery(historyQuery);
    handleSearch(historyQuery);
  };

  const searchTypeOptions = [
    { value: 'hybrid', label: 'Híbrida', icon: <Sparkles className="w-4 h-4" />, desc: 'Combina todas las técnicas' },
    { value: 'keyword', label: 'Palabras clave', icon: <Zap className="w-4 h-4" />, desc: 'Búsqueda exacta de términos' },
    { value: 'semantic', label: 'Semántica', icon: <Brain className="w-4 h-4" />, desc: 'Por significado y contexto' },
  ];

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="text-center mb-8">
        <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-600 via-purple-600 to-blue-600 bg-clip-text text-transparent mb-3">
          <SearchIcon className="inline-block w-10 h-10 mr-3 text-blue-600" />
          DistriSearch
        </h1>
        <p className="text-gray-500 text-lg">
          Búsqueda inteligente en tu colección de documentos
        </p>
      </div>

      {/* Search Bar */}
      <div className="relative">
        <SearchBar
          value={query}
          onChange={setQuery}
          onSearch={handleSearch}
          placeholder="Buscar documentos..."
          autoFocus
          loading={searchMutation.isPending}
          className="w-full"
        />

        {/* Search Type Selector */}
        <div className="flex items-center gap-2 mt-4 flex-wrap">
          {searchTypeOptions.map((option) => (
            <button
              key={option.value}
              onClick={() => setSearchType(option.value as SearchType)}
              className={`
                flex items-center gap-2 px-4 py-2.5 rounded-xl border-2 transition-all duration-200
                ${searchType === option.value 
                  ? 'border-blue-500 bg-blue-50 text-blue-700 shadow-sm' 
                  : 'border-gray-200 text-gray-600 hover:border-gray-300 hover:bg-gray-50'
                }
              `}
            >
              {option.icon}
              <span className="font-medium">{option.label}</span>
            </button>
          ))}

          <button
            onClick={() => setShowHistory(!showHistory)}
            className={`
              flex items-center gap-2 px-4 py-2.5 rounded-xl border-2 transition-all duration-200 ml-auto
              ${showHistory 
                ? 'border-purple-500 bg-purple-50 text-purple-700' 
                : 'border-gray-200 text-gray-600 hover:border-gray-300'
              }
            `}
          >
            <Clock className="w-4 h-4" />
            Historial
          </button>
        </div>
      </div>

      {/* History Panel */}
      {showHistory && (
        <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm animate-in fade-in slide-in-from-top-2 duration-300">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-900 flex items-center gap-2">
              <Clock className="w-5 h-5 text-gray-400" />
              Búsquedas recientes
            </h3>
            <button
              onClick={() => clearHistory.mutate()}
              className="text-sm text-red-600 hover:text-red-700 hover:underline"
            >
              Limpiar
            </button>
          </div>
          {history?.history?.length ? (
            <div className="space-y-2">
              {history.history.map((item: { query: string; results_count: number }, index: number) => (
                <button
                  key={index}
                  onClick={() => handleHistoryClick(item.query)}
                  className="w-full flex items-center gap-3 p-3 text-left hover:bg-gray-50 rounded-xl transition-colors group"
                >
                  <SearchIcon className="w-4 h-4 text-gray-400 group-hover:text-blue-500" />
                  <span className="text-gray-700 group-hover:text-gray-900">{item.query}</span>
                  <span className="ml-auto text-xs text-gray-400 bg-gray-100 px-2 py-1 rounded-full">
                    {item.results_count} resultados
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-center py-4">No hay búsquedas recientes</p>
          )}
        </div>
      )}

      {/* Results */}
      <div className="space-y-4">
        {searchMutation.isPending && (
          <div className="flex flex-col items-center justify-center py-16">
            <div className="relative">
              <div className="absolute inset-0 bg-blue-500 blur-xl opacity-20 animate-pulse" />
              <LoadingSpinner size="lg" />
            </div>
            <span className="mt-4 text-gray-500 font-medium">Buscando documentos...</span>
          </div>
        )}

        {searchMutation.isError && (
          <ErrorMessage
            title="Error en la búsqueda"
            message={searchMutation.error?.message || 'Ocurrió un error al buscar'}
            onRetry={() => handleSearch(query)}
          />
        )}

        {searchMutation.isSuccess && searchMutation.data && (
          <>
            {/* Results header */}
            <div className="flex items-center justify-between bg-gradient-to-r from-blue-50 to-purple-50 p-4 rounded-xl">
              <p className="text-gray-700">
                <strong className="text-blue-600">{searchMutation.data.total_results}</strong> resultados encontrados en{' '}
                <strong className="text-purple-600">{searchMutation.data.search_time_ms?.toFixed(0)}ms</strong>
              </p>
            </div>

            {/* Results list */}
            {searchMutation.data.results.length > 0 ? (
              <div className="space-y-4">
                {searchMutation.data.results.map((result, index) => (
                  <SearchResultCard
                    key={result.document_id}
                    result={result}
                    index={index}
                    onClick={() => handleDocumentClick(result)}
                    onDownload={() => handleDownload(result)}
                  />
                ))}
              </div>
            ) : (
              <EmptyState
                icon={<SearchIcon className="w-12 h-12" />}
                title="Sin resultados"
                description={`No encontramos documentos para "${query}". Prueba con otras palabras.`}
              />
            )}
          </>
        )}

        {!searchMutation.isPending && !searchMutation.isSuccess && !searchMutation.isError && (
          <div className="text-center py-16">
            <div className="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-blue-100 to-purple-100 rounded-2xl mb-4">
              <FileText className="w-10 h-10 text-blue-500" />
            </div>
            <h3 className="text-xl font-semibold text-gray-900 mb-2">Comienza a buscar</h3>
            <p className="text-gray-500 max-w-md mx-auto">
              Escribe una consulta para buscar en tu colección de documentos distribuidos.
            </p>
          </div>
        )}
      </div>

      {/* Document Viewer Modal */}
      {viewingDocument && (
        <DocumentViewerModal
          document={viewingDocument}
          onClose={() => setViewingDocument(null)}
          onDownload={async () => {
            try {
              const { blob, filename } = await documentService.download(viewingDocument.id);
              const url = window.URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = filename || viewingDocument.title || 'document';
              a.click();
              window.URL.revokeObjectURL(url);
            } catch (error) {
              console.error('Download failed:', error);
            }
          }}
        />
      )}

      {/* Loading overlay */}
      {loadingDocument && (
        <div className="fixed inset-0 bg-black/30 backdrop-blur-sm flex items-center justify-center z-[60]">
          <div className="bg-white p-6 rounded-2xl shadow-2xl flex items-center gap-4">
            <LoadingSpinner size="sm" />
            <span className="font-medium text-gray-700">Cargando documento...</span>
          </div>
        </div>
      )}
    </div>
  );
};

// Search Result Card Component
interface SearchResultCardProps {
  result: SearchResult;
  index: number;
  onClick: () => void;
  onDownload: () => void;
}

const SearchResultCard: React.FC<SearchResultCardProps> = ({ result, index, onClick, onDownload }) => {
  return (
    <div 
      className="bg-white rounded-2xl border border-gray-100 p-5 hover:shadow-xl hover:shadow-gray-200/50 hover:border-gray-200 transition-all duration-300 transform hover:-translate-y-0.5 group"
      style={{ animationDelay: `${index * 50}ms` }}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl text-white group-hover:scale-110 transition-transform duration-300">
            <FileText className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 group-hover:text-blue-600 transition-colors">
              {result.title || result.document?.title || 'Sin título'}
            </h3>
            {result.content_preview && (
              <p className="text-sm text-gray-500 line-clamp-2 mt-1">{result.content_preview}</p>
            )}
          </div>
        </div>
        <div className="px-3 py-1.5 bg-gradient-to-r from-blue-500 to-purple-500 text-white text-sm font-medium rounded-full">
          {(result.score * 100).toFixed(0)}%
        </div>
      </div>

      {/* Action buttons */}
      <div className="mt-4 pt-4 border-t border-gray-100 flex gap-3">
        <button
          onClick={(e) => { e.stopPropagation(); onClick(); }}
          className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-xl hover:from-blue-600 hover:to-blue-700 transition-all shadow-sm hover:shadow-md"
        >
          <Eye className="w-4 h-4" />
          Ver documento
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); onDownload(); }}
          className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium bg-gradient-to-r from-green-500 to-green-600 text-white rounded-xl hover:from-green-600 hover:to-green-700 transition-all shadow-sm hover:shadow-md"
        >
          <Download className="w-4 h-4" />
          Descargar
        </button>
      </div>
    </div>
  );
};

// Document Viewer Modal Component
interface DocumentViewerModalProps {
  document: { id: string; title: string; content: string };
  onClose: () => void;
  onDownload: () => void;
}

const DocumentViewerModal: React.FC<DocumentViewerModalProps> = ({ document, onClose, onDownload }) => {
  return (
    <div 
      className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-[100] p-4"
      onClick={onClose}
    >
      <div 
        className="bg-white rounded-2xl max-w-4xl w-full max-h-[85vh] flex flex-col shadow-2xl animate-in fade-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-gray-100 bg-gradient-to-r from-gray-50 to-white rounded-t-2xl">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl text-white">
              <FileText className="w-5 h-5" />
            </div>
            <h2 className="text-xl font-bold text-gray-900">{document.title}</h2>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={onDownload}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-gradient-to-r from-green-500 to-green-600 text-white rounded-xl hover:from-green-600 hover:to-green-700 transition-all shadow-sm"
            >
              <Download className="w-4 h-4" />
              Descargar
            </button>
            <button
              onClick={onClose}
              className="p-2.5 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-xl transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>
        
        {/* Content */}
        <div className="flex-1 overflow-auto p-6">
          <div className="bg-gray-50 rounded-xl p-6 min-h-[300px]">
            <pre className="whitespace-pre-wrap font-mono text-sm text-gray-700 leading-relaxed">
              {document.content}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
};
