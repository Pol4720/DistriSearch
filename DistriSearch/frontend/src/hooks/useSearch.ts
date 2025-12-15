import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { searchService } from '../services';
import type { SearchRequest } from '../types';

// Query keys
export const searchKeys = {
  all: ['search'] as const,
  results: () => [...searchKeys.all, 'results'] as const,
  result: (query: string, filters?: Record<string, unknown>) =>
    [...searchKeys.results(), query, filters] as const,
  history: () => [...searchKeys.all, 'history'] as const,
  suggestions: (prefix: string) =>
    [...searchKeys.all, 'suggestions', prefix] as const,
};

interface UseSearchOptions {
  enabled?: boolean;
  staleTime?: number;
}

/**
 * Hook to perform a search
 */
export function useSearch(
  request: SearchRequest | null,
  options: UseSearchOptions = {}
) {
  const { enabled = true, staleTime = 60000 } = options;

  return useQuery({
    queryKey: searchKeys.result(request?.query || '', {
      filters: request?.filters,
      limit: request?.limit,
      offset: request?.offset,
    }),
    queryFn: () => searchService.search(request!),
    enabled: enabled && !!request?.query,
    staleTime,
  });
}

/**
 * Hook to perform an advanced search
 */
export function useAdvancedSearch(
  request: SearchRequest | null,
  options: UseSearchOptions = {}
) {
  const { enabled = true, staleTime = 60000 } = options;

  return useQuery({
    queryKey: [
      ...searchKeys.result(request?.query || ''),
      'advanced',
      {
        filters: request?.filters,
        semantic_options: request?.semantic_options,
        highlight_options: request?.highlight_options,
      },
    ],
    queryFn: () => searchService.search(request!),
    enabled: enabled && !!request?.query,
    staleTime,
  });
}

/**
 * Hook for imperative search (mutation-style)
 */
export function useSearchMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: SearchRequest) => searchService.search(request),
    onSuccess: (data, variables) => {
      // Cache the results
      queryClient.setQueryData(
        searchKeys.result(variables.query, {
          filters: variables.filters,
          limit: variables.limit,
          offset: variables.offset,
        }),
        data
      );
    },
  });
}

/**
 * Hook for advanced search mutation
 */
export function useAdvancedSearchMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: SearchRequest) => searchService.search(request),
    onSuccess: (data, variables) => {
      // Cache the results
      queryClient.setQueryData(
        [
          ...searchKeys.result(variables.query),
          'advanced',
          {
            filters: variables.filters,
            semantic_options: variables.semantic_options,
            highlight_options: variables.highlight_options,
          },
        ],
        data
      );
    },
  });
}

/**
 * Hook to fetch search history
 */
export function useSearchHistory(options: { limit?: number; enabled?: boolean } = {}) {
  const { limit = 50, enabled = true } = options;

  return useQuery({
    queryKey: [...searchKeys.history(), limit],
    queryFn: () => searchService.getHistory(1, limit),
    enabled,
    staleTime: 30000, // 30 seconds
  });
}

/**
 * Hook to clear search history
 */
export function useClearSearchHistory() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => searchService.clearHistory(),
    onSuccess: () => {
      // Invalidate history queries
      queryClient.invalidateQueries({ queryKey: searchKeys.history() });
    },
  });
}

/**
 * Hook to fetch search suggestions
 */
export function useSearchSuggestions(
  prefix: string,
  options: { limit?: number; enabled?: boolean } = {}
) {
  const { limit = 10, enabled = true } = options;

  return useQuery({
    queryKey: searchKeys.suggestions(prefix),
    queryFn: () => searchService.getSuggestions(prefix, limit),
    enabled: enabled && prefix.length >= 2,
    staleTime: 120000, // 2 minutes
    placeholderData: (previousData) => previousData,
  });
}

/**
 * Hook to invalidate all search caches
 */
export function useInvalidateSearch() {
  const queryClient = useQueryClient();

  return () => {
    queryClient.invalidateQueries({ queryKey: searchKeys.all });
  };
}
