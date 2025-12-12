import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileText,
  Upload,
  Grid,
  List,
  Plus,
  X,
  Download,
  Trash2,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import {
  useDocuments,
  useUploadDocument,
  useDeleteDocument,
} from '../hooks';
import {
  DocumentCard,
  SearchBar,
  LoadingSpinner,
  EmptyState,
  ErrorMessage,
  Badge,
} from '../components/common';
import { documentService } from '../services';
import type { Document } from '../types';

type ViewMode = 'grid' | 'list';

export const Documents: React.FC = () => {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  const [showUpload, setShowUpload] = useState(false);
  const [page, setPage] = useState(1);
  const [selectedDocs, setSelectedDocs] = useState<Set<string>>(new Set());

  const { data: documents, isLoading, error, refetch } = useDocuments({
    page,
    limit: 20,
  });
  const uploadMutation = useUploadDocument();
  const deleteMutation = useDeleteDocument();

  const handleDocumentClick = (doc: Document) => {
    navigate(`/documents/${doc.id}`);
  };

  const handleUpload = useCallback(
    async (files: FileList) => {
      for (const file of Array.from(files)) {
        await uploadMutation.mutateAsync({ file });
      }
      setShowUpload(false);
    },
    [uploadMutation]
  );

  const handleDelete = useCallback(
    async (doc: Document) => {
      if (window.confirm(`Delete "${doc.title || doc.filename || 'this document'}"?`)) {
        await deleteMutation.mutateAsync(doc.id);
      }
    },
    [deleteMutation]
  );

  const handleBulkDelete = useCallback(async () => {
    if (selectedDocs.size === 0) return;
    if (!window.confirm(`Delete ${selectedDocs.size} documents?`)) return;

    for (const id of selectedDocs) {
      await deleteMutation.mutateAsync(id);
    }
    setSelectedDocs(new Set());
  }, [selectedDocs, deleteMutation]);

  const handleDownload = async (doc: Document) => {
    try {
      const response = await documentService.get(doc.id);
      const blob = new Blob([response.content], { type: 'text/plain' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = doc.filename || doc.title || 'document.txt';
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Download failed:', error);
    }
  };

  const toggleSelection = (docId: string) => {
    const newSelection = new Set(selectedDocs);
    if (newSelection.has(docId)) {
      newSelection.delete(docId);
    } else {
      newSelection.add(docId);
    }
    setSelectedDocs(newSelection);
  };

  const filteredDocs = documents?.documents?.filter(
    (doc: Document) =>
      !searchQuery ||
      doc.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      doc.filename?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  if (error) {
    return (
      <ErrorMessage
        title="Failed to load documents"
        message="Could not fetch documents. Please try again."
        onRetry={() => refetch()}
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Documents</h1>
          <p className="text-gray-500">
            {documents?.total || 0} documents in the system
          </p>
        </div>
        <button
          onClick={() => setShowUpload(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Plus className="w-5 h-5" />
          Upload Document
        </button>
      </div>

      {/* Toolbar */}
      <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
        <SearchBar
          value={searchQuery}
          onChange={setSearchQuery}
          placeholder="Filter documents..."
          className="w-full sm:w-96"
        />

        <div className="flex items-center gap-3">
          {/* Bulk actions */}
          {selectedDocs.size > 0 && (
            <div className="flex items-center gap-2">
              <Badge variant="info">{selectedDocs.size} selected</Badge>
              <button
                onClick={handleBulkDelete}
                className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
              >
                <Trash2 className="w-5 h-5" />
              </button>
              <button
                onClick={() => setSelectedDocs(new Set())}
                className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          )}

          {/* View mode toggle */}
          <div className="flex items-center border border-gray-300 rounded-lg overflow-hidden">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-2 ${viewMode === 'grid' ? 'bg-gray-100' : 'hover:bg-gray-50'}`}
            >
              <Grid className="w-5 h-5 text-gray-600" />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`p-2 ${viewMode === 'list' ? 'bg-gray-100' : 'hover:bg-gray-50'}`}
            >
              <List className="w-5 h-5 text-gray-600" />
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <LoadingSpinner size="lg" />
        </div>
      ) : filteredDocs?.length ? (
        <>
          {/* Documents Grid/List */}
          {viewMode === 'grid' ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {filteredDocs.map((doc) => (
                <DocumentCard
                  key={doc.id}
                  document={doc}
                  onClick={() => handleDocumentClick(doc)}
                  onDelete={() => handleDelete(doc)}
                  selected={selectedDocs.has(doc.id)}
                />
              ))}
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <table className="w-full">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="w-12 px-4 py-3">
                      <input
                        type="checkbox"
                        checked={selectedDocs.size === filteredDocs.length}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedDocs(new Set(filteredDocs.map((d) => d.id)));
                          } else {
                            setSelectedDocs(new Set());
                          }
                        }}
                        className="rounded border-gray-300"
                      />
                    </th>
                    <th className="px-4 py-3 text-left text-sm font-medium text-gray-600">
                      Name
                    </th>
                    <th className="px-4 py-3 text-left text-sm font-medium text-gray-600">
                      Partition
                    </th>
                    <th className="px-4 py-3 text-left text-sm font-medium text-gray-600">
                      Created
                    </th>
                    <th className="px-4 py-3 text-right text-sm font-medium text-gray-600">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {filteredDocs.map((doc) => (
                    <tr
                      key={doc.id}
                      className="hover:bg-gray-50 cursor-pointer"
                      onClick={() => handleDocumentClick(doc)}
                    >
                      <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={selectedDocs.has(doc.id)}
                          onChange={() => toggleSelection(doc.id)}
                          className="rounded border-gray-300"
                        />
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <FileText className="w-5 h-5 text-gray-400" />
                          <div>
                            <p className="font-medium text-gray-900">
                              {doc.title || doc.filename || 'Untitled'}
                            </p>
                            {doc.filename && (
                              <p className="text-sm text-gray-500">{doc.filename}</p>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant="default">P{doc.partition_id}</Badge>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-500">
                        {new Date(doc.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => handleDownload(doc)}
                            className="p-1.5 text-gray-400 hover:text-blue-600 transition-colors"
                          >
                            <Download className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleDelete(doc)}
                            className="p-1.5 text-gray-400 hover:text-red-600 transition-colors"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination */}
          {documents && documents.total > 20 && (
            <div className="flex items-center justify-between">
              <p className="text-sm text-gray-500">
                Showing {(page - 1) * 20 + 1} to{' '}
                {Math.min(page * 20, documents.total)} of {documents.total}
              </p>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage(page - 1)}
                  disabled={page === 1}
                  className="p-2 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <ChevronLeft className="w-5 h-5" />
                </button>
                <span className="px-4 py-2 text-gray-700">Page {page}</span>
                <button
                  onClick={() => setPage(page + 1)}
                  disabled={page * 20 >= documents.total}
                  className="p-2 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <ChevronRight className="w-5 h-5" />
                </button>
              </div>
            </div>
          )}
        </>
      ) : (
        <EmptyState
          icon={<FileText className="w-12 h-12" />}
          title="No documents"
          description={
            searchQuery
              ? `No documents match "${searchQuery}"`
              : "You haven't uploaded any documents yet"
          }
          action={
            !searchQuery && (
              <button
                onClick={() => setShowUpload(true)}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                Upload your first document
              </button>
            )
          }
        />
      )}

      {/* Upload Modal */}
      {showUpload && (
        <UploadModal
          onClose={() => setShowUpload(false)}
          onUpload={handleUpload}
          isUploading={uploadMutation.isPending}
        />
      )}
    </div>
  );
};

// Upload Modal Component
interface UploadModalProps {
  onClose: () => void;
  onUpload: (files: FileList) => void;
  isUploading: boolean;
}

const UploadModal: React.FC<UploadModalProps> = ({ onClose, onUpload, isUploading }) => {
  const [dragActive, setDragActive] = useState(false);
  const inputRef = React.useRef<HTMLInputElement>(null);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      onUpload(e.dataTransfer.files);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      onUpload(e.target.files);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
      <div className="bg-white rounded-xl p-6 w-full max-w-lg mx-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-gray-900">Upload Document</h2>
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-100 rounded transition-colors"
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        <div
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          className={`
            border-2 border-dashed rounded-xl p-8 text-center cursor-pointer
            transition-colors
            ${dragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'}
          `}
        >
          <input
            ref={inputRef}
            type="file"
            multiple
            onChange={handleChange}
            className="hidden"
            accept=".txt,.pdf,.doc,.docx,.md"
          />

          {isUploading ? (
            <div className="flex flex-col items-center">
              <LoadingSpinner size="lg" />
              <p className="mt-4 text-gray-600">Uploading...</p>
            </div>
          ) : (
            <>
              <Upload className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-700 mb-2">
                Drag and drop files here, or click to browse
              </p>
              <p className="text-sm text-gray-500">
                Supports TXT, PDF, DOC, DOCX, MD files
              </p>
            </>
          )}
        </div>

        <div className="flex justify-end gap-3 mt-6">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={() => inputRef.current?.click()}
            disabled={isUploading}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            Select Files
          </button>
        </div>
      </div>
    </div>
  );
};
