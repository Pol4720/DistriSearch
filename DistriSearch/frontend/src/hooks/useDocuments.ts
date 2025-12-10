import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { documentService } from '../services';
import type { Document, DocumentCreate, DocumentUpdate, PaginatedResponse } from '../types';

// Query keys
export const documentKeys = {
  all: ['documents'] as const,
  lists: () => [...documentKeys.all, 'list'] as const,
  list: (filters: Record<string, unknown>) =>
    [...documentKeys.lists(), filters] as const,
  details: () => [...documentKeys.all, 'detail'] as const,
  detail: (id: string) => [...documentKeys.details(), id] as const,
  content: (id: string) => [...documentKeys.all, 'content', id] as const,
  vectors: (id: string) => [...documentKeys.all, 'vectors', id] as const,
};

interface UseDocumentsOptions {
  page?: number;
  limit?: number;
  partition?: number;
  node?: string;
  enabled?: boolean;
}

/**
 * Hook to fetch paginated documents
 */
export function useDocuments(options: UseDocumentsOptions = {}) {
  const { page = 1, limit = 20, partition, node, enabled = true } = options;

  return useQuery({
    queryKey: documentKeys.list({ page, limit, partition, node }),
    queryFn: () => documentService.getAll({ page, limit, partition, node }),
    enabled,
    staleTime: 30000, // 30 seconds
    placeholderData: (previousData) => previousData,
  });
}

/**
 * Hook to fetch a single document
 */
export function useDocument(id: string, options: { enabled?: boolean } = {}) {
  const { enabled = true } = options;

  return useQuery({
    queryKey: documentKeys.detail(id),
    queryFn: () => documentService.getById(id),
    enabled: enabled && !!id,
    staleTime: 60000, // 1 minute
  });
}

/**
 * Hook to fetch document content
 */
export function useDocumentContent(
  id: string,
  options: { enabled?: boolean } = {}
) {
  const { enabled = true } = options;

  return useQuery({
    queryKey: documentKeys.content(id),
    queryFn: () => documentService.getContent(id),
    enabled: enabled && !!id,
    staleTime: 300000, // 5 minutes
  });
}

/**
 * Hook to fetch document vectors
 */
export function useDocumentVectors(
  id: string,
  options: { enabled?: boolean } = {}
) {
  const { enabled = true } = options;

  return useQuery({
    queryKey: documentKeys.vectors(id),
    queryFn: () => documentService.getVectors(id),
    enabled: enabled && !!id,
    staleTime: 300000, // 5 minutes
  });
}

/**
 * Hook to create a document
 */
export function useCreateDocument() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: DocumentCreate) => documentService.create(data),
    onSuccess: () => {
      // Invalidate all document lists
      queryClient.invalidateQueries({ queryKey: documentKeys.lists() });
    },
  });
}

/**
 * Hook to update a document
 */
export function useUpdateDocument() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: DocumentUpdate }) =>
      documentService.update(id, data),
    onSuccess: (data, variables) => {
      // Update the specific document in cache
      queryClient.setQueryData(documentKeys.detail(variables.id), data);
      // Invalidate document lists
      queryClient.invalidateQueries({ queryKey: documentKeys.lists() });
    },
  });
}

/**
 * Hook to delete a document
 */
export function useDeleteDocument() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => documentService.delete(id),
    onSuccess: (_, id) => {
      // Remove from cache
      queryClient.removeQueries({ queryKey: documentKeys.detail(id) });
      // Invalidate document lists
      queryClient.invalidateQueries({ queryKey: documentKeys.lists() });
    },
  });
}

/**
 * Hook to upload a document file
 */
export function useUploadDocument() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      file,
      metadata,
      onProgress,
    }: {
      file: File;
      metadata?: Record<string, string>;
      onProgress?: (progress: number) => void;
    }) => documentService.upload(file, metadata, onProgress),
    onSuccess: () => {
      // Invalidate all document lists
      queryClient.invalidateQueries({ queryKey: documentKeys.lists() });
    },
  });
}

/**
 * Hook to prefetch a document
 */
export function usePrefetchDocument() {
  const queryClient = useQueryClient();

  return (id: string) => {
    queryClient.prefetchQuery({
      queryKey: documentKeys.detail(id),
      queryFn: () => documentService.getById(id),
      staleTime: 60000,
    });
  };
}
