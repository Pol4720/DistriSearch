import React from 'react';
import { FileText, Calendar, HardDrive, Hash } from 'lucide-react';
import type { Document } from '../../types';

interface DocumentCardProps {
  document: Document;
  onClick?: (document: Document) => void;
  onDelete?: (document: Document) => void;
  selected?: boolean;
  showContent?: boolean;
}

export const DocumentCard: React.FC<DocumentCardProps> = ({
  document,
  onClick,
  onDelete,
  selected = false,
  showContent = false,
}) => {
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const displayTitle = document.title || document.filename || 'Untitled';
  const displayFilename = document.filename || document.title || '';

  return (
    <div
      onClick={() => onClick?.(document)}
      className={`
        p-4 bg-white rounded-lg border transition-all duration-200 cursor-pointer
        ${selected ? 'border-blue-500 ring-2 ring-blue-200' : 'border-gray-200 hover:border-gray-300'}
        ${onClick ? 'hover:shadow-md' : ''}
      `}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-50 rounded-lg">
            <FileText className="w-5 h-5 text-blue-600" />
          </div>
          <div>
            <h3 className="font-medium text-gray-900 line-clamp-1">
              {displayTitle}
            </h3>
            {displayFilename && displayFilename !== displayTitle && (
              <p className="text-sm text-gray-500">{displayFilename}</p>
            )}
          </div>
        </div>

        {onDelete && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete(document);
            }}
            className="p-1 text-gray-400 hover:text-red-500 transition-colors"
            aria-label="Delete document"
          >
            <span className="sr-only">Delete</span>
            ×
          </button>
        )}
      </div>

      {/* Content preview */}
      {showContent && document.content && (
        <p className="text-sm text-gray-600 mb-3 line-clamp-3">
          {document.content}
        </p>
      )}

      {/* Metadata */}
      <div className="flex flex-wrap gap-3 text-sm text-gray-500">
        <div className="flex items-center gap-1">
          <Calendar className="w-4 h-4" />
          <span>{formatDate(document.created_at)}</span>
        </div>

        {document.size && (
          <div className="flex items-center gap-1">
            <HardDrive className="w-4 h-4" />
            <span>{formatSize(document.size)}</span>
          </div>
        )}

        {document.partition_id && (
          <div className="flex items-center gap-1">
            <Hash className="w-4 h-4" />
            <span>P{document.partition_id}</span>
          </div>
        )}
      </div>

      {/* Tags */}
      {document.tags && document.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-3">
          {document.tags.slice(0, 3).map((tag: string, index: number) => (
            <span
              key={index}
              className="px-2 py-0.5 text-xs bg-gray-100 text-gray-600 rounded-full"
            >
              {tag}
            </span>
          ))}
          {document.tags.length > 3 && (
            <span className="px-2 py-0.5 text-xs bg-gray-100 text-gray-500 rounded-full">
              +{document.tags.length - 3}
            </span>
          )}
        </div>
      )}
    </div>
  );
};
