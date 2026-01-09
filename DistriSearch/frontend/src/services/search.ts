import api from './api';
import type {
  SearchRequest,
  SearchResponse,
  SearchHistoryItem,
} from '../types';

const SEARCH_ENDPOINT = '/search';

export const searchService = {
  /**
   * Perform a search
   */
  async search(request: SearchRequest): Promise<SearchResponse> {
    const response = await api.post<SearchResponse>(SEARCH_ENDPOINT, request);
    return response.data;
  },

  /**
   * Quick search (GET endpoint)
   */
  async quickSearch(
    query: string,
    type: 'keyword' | 'semantic' | 'hybrid' = 'hybrid',
    limit: number = 10
  ): Promise<SearchResponse> {
    const response = await api.get<SearchResponse>(`${SEARCH_ENDPOINT}/quick`, {
      params: { q: query, type, limit },
    });
    return response.data;
  },

  /**
   * Get search suggestions
   */
  async getSuggestions(query: string, limit: number = 5): Promise<string[]> {
    const response = await api.get<string[]>(`${SEARCH_ENDPOINT}/suggest`, {
      params: { q: query, limit },
    });
    return response.data;
  },

  /**
   * Find similar documents
   */
  async findSimilar(
    documentId: string,
    limit: number = 10
  ): Promise<SearchResponse> {
    const response = await api.get<SearchResponse>(
      `${SEARCH_ENDPOINT}/similar/${documentId}`,
      { params: { limit } }
    );
    return response.data;
  },

  /**
   * Get search history
   */
  async getHistory(
    page: number = 1,
    pageSize: number = 20
  ): Promise<{ history: SearchHistoryItem[]; total: number }> {
    const response = await api.get<{ history: SearchHistoryItem[]; total: number }>(
      `${SEARCH_ENDPOINT}/history`,
      { params: { page, page_size: pageSize } }
    );
    return response.data;
  },

  /**
   * Clear search history
   */
  async clearHistory(): Promise<void> {
    await api.delete(`${SEARCH_ENDPOINT}/history`);
  },

  /**
   * Batch search
   */
  async batchSearch(requests: SearchRequest[]): Promise<SearchResponse[]> {
    const response = await api.post<SearchResponse[]>(
      `${SEARCH_ENDPOINT}/batch`,
      requests
    );
    return response.data;
  },
};
