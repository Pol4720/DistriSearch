// API Types for DistriSearch Frontend

// Document Types
export interface Document {
  id: string;
  title: string;
  content: string;
  metadata: Record<string, unknown>;
  tags: string[];
  node_id?: string;
  partition_id?: string;
  vectors?: DocumentVectors;
  created_at: string;
  updated_at: string;
}

export interface DocumentVectors {
  tfidf: number[];
  minhash: number[];
  lda: number[];
  textrank?: string[];
}

export interface DocumentCreate {
  title: string;
  content: string;
  metadata?: Record<string, unknown>;
  tags?: string[];
}

export interface DocumentUpdate {
  title?: string;
  content?: string;
  metadata?: Record<string, unknown>;
  tags?: string[];
}

export interface DocumentListResponse {
  documents: Document[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface DocumentUploadResponse {
  id: string;
  filename: string;
  title: string;
  content_preview: string;
  file_size: number;
  content_type: string;
  node_id: string;
  partition_id: string;
  created_at: string;
}

// Search Types
export type SearchType = 'keyword' | 'semantic' | 'hybrid';

export interface SearchRequest {
  query: string;
  search_type?: SearchType;
  top_k?: number;
  filters?: SearchFilters;
  include_vectors?: boolean;
  timeout_ms?: number;
}

export interface SearchFilters {
  tags?: string[];
  node_ids?: string[];
  partition_ids?: string[];
  metadata?: Record<string, unknown>;
}

export interface SearchResult {
  document_id: string;
  title: string;
  content_preview: string;
  score: number;
  node_id: string;
  metadata: Record<string, unknown>;
  matched_terms: string[];
  vectors?: DocumentVectors;
}

export interface SearchResponse {
  query: string;
  search_type: SearchType;
  results: SearchResult[];
  total_results: number;
  searched_nodes: number;
  search_time_ms: number;
  query_id: string;
}

export interface SearchHistoryItem {
  query_id: string;
  query: string;
  search_type: SearchType;
  results_count: number;
  search_time_ms: number;
  timestamp: string;
}

// Cluster Types
export type NodeStatus = 'healthy' | 'degraded' | 'unhealthy' | 'unknown';
export type NodeRole = 'master' | 'slave' | 'candidate';

export interface NodeInfo {
  node_id: string;
  address: string;
  port: number;
  role: NodeRole;
  status: NodeStatus;
  document_count: number;
  partition_count: number;
  cpu_usage: number;
  memory_usage: number;
  disk_usage: number;
  last_heartbeat?: string;
  joined_at: string;
  metadata: Record<string, unknown>;
}

export interface ClusterStatus {
  cluster_id: string;
  master_node_id?: string;
  master_address?: string;
  total_nodes: number;
  healthy_nodes: number;
  unhealthy_nodes: number;
  total_documents: number;
  total_partitions: number;
  replication_factor: number;
  status: NodeStatus;
  nodes: NodeInfo[];
  last_rebalance?: string;
  created_at: string;
}

export interface PartitionInfo {
  partition_id: string;
  primary_node_id: string;
  replica_node_ids: string[];
  document_count: number;
  size_bytes: number;
  status: string;
  created_at: string;
  last_modified: string;
}

export interface ClusterPartitions {
  total_partitions: number;
  partitions: PartitionInfo[];
  replication_factor: number;
}

export interface RebalanceRequest {
  force?: boolean;
  target_node_id?: string;
}

export interface RebalanceResponse {
  success: boolean;
  message: string;
  migrations_planned: number;
  estimated_time_seconds: number;
}

// Health Types
export type HealthStatus = 'healthy' | 'degraded' | 'unhealthy';

export interface ComponentHealth {
  name: string;
  status: HealthStatus;
  message?: string;
  latency_ms?: number;
}

export interface HealthResponse {
  status: HealthStatus;
  node_id: string;
  role: NodeRole;
  version: string;
  uptime_seconds: number;
  components: ComponentHealth[];
  timestamp: string;
}

// WebSocket Types
export type WSMessageType = 
  | 'cluster_update'
  | 'node_status'
  | 'search_progress'
  | 'rebalance_progress'
  | 'error'
  | 'heartbeat';

export interface WSMessage {
  type: WSMessageType;
  data: unknown;
  timestamp: string;
}

// Error Types
export interface ApiError {
  error: string;
  message: string;
  details: ErrorDetail[];
  timestamp?: string;
  request_id?: string;
}

export interface ErrorDetail {
  field?: string;
  message: string;
  code: string;
}

// Pagination Types
export interface PaginationParams {
  page: number;
  page_size: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
