"""
Application Configuration

Loads configuration from environment variables and provides
type-safe access to settings.
"""

import os
from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    app_name: str = "DistriSearch"
    app_version: str = "1.0.0"
    debug: bool = Field(default=False, alias="DEBUG")
    
    # Node Configuration
    node_id: str = Field(default="node-1", alias="NODE_ID")
    node_role: str = Field(default="slave", alias="NODE_ROLE")
    cluster_id: str = Field(default="distrisearch-cluster", alias="CLUSTER_ID")
    node_address: str = Field(default="localhost", alias="NODE_ADDRESS")
    node_port: int = Field(default=8000, alias="NODE_PORT")
    
    # API Server
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    workers: int = Field(default=4, alias="WORKERS")
    
    # Master Connection (for slaves)
    master_host: str = Field(default="master", alias="MASTER_HOST")
    master_port: int = Field(default=8001, alias="MASTER_PORT")
    
    # MongoDB
    mongodb_uri: str = Field(
        default="mongodb://mongodb:27017/distrisearch?replicaSet=rs0",
        alias="MONGODB_URI"
    )
    mongodb_database: str = Field(default="distrisearch", alias="MONGODB_DATABASE")
    mongodb_max_pool_size: int = Field(default=50, alias="MONGODB_MAX_POOL_SIZE")
    
    # Redis
    redis_url: str = Field(default="redis://redis:6379", alias="REDIS_URL")
    redis_max_connections: int = Field(default=20, alias="REDIS_MAX_CONNECTIONS")
    
    # gRPC
    grpc_port: int = Field(default=50051, alias="GRPC_PORT")
    grpc_max_workers: int = Field(default=10, alias="GRPC_MAX_WORKERS")
    
    # Replication
    replication_factor: int = Field(default=2, alias="REPLICATION_FACTOR")
    min_replicas_for_write: int = Field(default=1, alias="MIN_REPLICAS_FOR_WRITE")
    
    # Raft Consensus (milliseconds)
    raft_election_timeout_min: int = Field(default=150, alias="RAFT_ELECTION_TIMEOUT_MIN")
    raft_election_timeout_max: int = Field(default=300, alias="RAFT_ELECTION_TIMEOUT_MAX")
    raft_heartbeat_interval: int = Field(default=50, alias="RAFT_HEARTBEAT_INTERVAL")
    
    # Heartbeat (seconds)
    heartbeat_interval: int = Field(default=5, alias="HEARTBEAT_INTERVAL")
    heartbeat_timeout: int = Field(default=15, alias="HEARTBEAT_TIMEOUT")
    max_heartbeat_failures: int = Field(default=3, alias="MAX_HEARTBEAT_FAILURES")
    
    # Rebalancing
    rebalance_threshold: float = Field(default=0.8, alias="REBALANCE_THRESHOLD")
    rebalance_batch_size: int = Field(default=50, alias="REBALANCE_BATCH_SIZE")
    rebalance_delay_seconds: float = Field(default=1.0, alias="REBALANCE_DELAY_SECONDS")
    
    # Search
    search_timeout: int = Field(default=30, alias="SEARCH_TIMEOUT")
    max_results_per_node: int = Field(default=100, alias="MAX_RESULTS_PER_NODE")
    default_max_results: int = Field(default=10, alias="DEFAULT_MAX_RESULTS")
    
    # Vectorization
    minhash_num_perm: int = Field(default=128, alias="MINHASH_NUM_PERM")
    lda_num_topics: int = Field(default=20, alias="LDA_NUM_TOPICS")
    tfidf_max_features: int = Field(default=5000, alias="TFIDF_MAX_FEATURES")
    textrank_top_keywords: int = Field(default=10, alias="TEXTRANK_TOP_KEYWORDS")
    
    # Similarity Weights
    name_similarity_weight: float = Field(default=0.4, alias="NAME_SIMILARITY_WEIGHT")
    content_similarity_weight: float = Field(default=0.4, alias="CONTENT_SIMILARITY_WEIGHT")
    topic_similarity_weight: float = Field(default=0.2, alias="TOPIC_SIMILARITY_WEIGHT")
    
    # DNS
    dns_fallback_enabled: bool = Field(default=True, alias="DNS_FALLBACK_ENABLED")
    coredns_host: str = Field(default="coredns", alias="COREDNS_HOST")
    coredns_port: int = Field(default=53, alias="COREDNS_PORT")
    dns_cache_ttl: int = Field(default=30, alias="DNS_CACHE_TTL")
    
    # File Storage
    data_dir: str = Field(default="/app/data", alias="DATA_DIR")
    documents_dir: str = Field(default="/app/data/documents", alias="DOCUMENTS_DIR")
    max_upload_size_mb: int = Field(default=500, alias="MAX_UPLOAD_SIZE_MB")
    
    # Security
    jwt_secret: Optional[str] = Field(default=None, alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expiration_hours: int = Field(default=24, alias="JWT_EXPIRATION_HOURS")
    
    # CORS
    cors_origins: str = Field(default="*", alias="CORS_ORIGINS")
    
    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="json", alias="LOG_FORMAT")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    @property
    def master_address(self) -> str:
        """Full HTTP address of master node."""
        return f"http://{self.master_host}:{self.master_port}"
    
    @property
    def is_master(self) -> bool:
        """Check if this node is configured as master."""
        return self.node_role.lower() == "master"
    
    @property
    def is_slave(self) -> bool:
        """Check if this node is configured as slave."""
        return self.node_role.lower() == "slave"
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins string into list."""
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    @property
    def max_upload_size_bytes(self) -> int:
        """Max upload size in bytes."""
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
