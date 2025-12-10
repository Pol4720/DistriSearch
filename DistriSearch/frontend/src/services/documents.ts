import api from './api';
import type {
  Document,
  DocumentCreate,
  DocumentUpdate,
  DocumentListResponse,
  DocumentUploadResponse,
  DocumentVectors,
} from '../types';

const DOCUMENTS_ENDPOINT = '/documents';

export const documentService = {
  /**
   * List documents with pagination
   */
  async list(params: {
    page?: number;
    page_size?: number;
    tag?: string;
    node_id?: string;
  } = {}): Promise<DocumentListResponse> {
    const response = await api.get<DocumentListResponse>(DOCUMENTS_ENDPOINT, {
      params: {
        page: params.page || 1,
        page_size: params.page_size || 20,
        ...(params.tag && { tag: params.tag }),
        ...(params.node_id && { node_id: params.node_id }),
      },
    });
    return response.data;
  },

  /**
   * Get a document by ID
   */
  async get(id: string, includeVectors: boolean = false): Promise<Document> {
    const response = await api.get<Document>(`${DOCUMENTS_ENDPOINT}/${id}`, {
      params: { include_vectors: includeVectors },
    });
    return response.data;
  },

  /**
   * Create a new document
   */
  async create(document: DocumentCreate): Promise<Document> {
    const response = await api.post<Document>(DOCUMENTS_ENDPOINT, document);
    return response.data;
  },

  /**
   * Update an existing document
   */
  async update(id: string, update: DocumentUpdate): Promise<Document> {
    const response = await api.put<Document>(
      `${DOCUMENTS_ENDPOINT}/${id}`,
      update
    );
    return response.data;
  },

  /**
   * Delete a document
   */
  async delete(id: string): Promise<void> {
    await api.delete(`${DOCUMENTS_ENDPOINT}/${id}`);
  },

  /**
   * Upload a file
   */
  async upload(
    file: File,
    title?: string,
    tags?: string[]
  ): Promise<DocumentUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    if (title) formData.append('title', title);
    if (tags && tags.length > 0) formData.append('tags', tags.join(','));

    const response = await api.post<DocumentUploadResponse>(
      `${DOCUMENTS_ENDPOINT}/upload`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return response.data;
  },

  /**
   * Get document vectors
   */
  async getVectors(id: string): Promise<DocumentVectors> {
    const response = await api.get<DocumentVectors>(
      `${DOCUMENTS_ENDPOINT}/${id}/vectors`
    );
    return response.data;
  },
};
