"""
Configuration Constants

Default configuration values for the DistriSearch system.
Values can be overridden via environment variables.
"""

import os
from typing import List, Optional
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════════════
# DEFAULT VALUES
# ═══════════════════════════════════════════════════════════════════════════

# Replication
DEFAULT_REPLICATION_FACTOR = 2
MIN_REPLICAS_FOR_WRITE = 1

# Heartbeat (in seconds)
DEFAULT_HEARTBEAT_INTERVAL = 5
DEFAULT_HEARTBEAT_TIMEOUT = 15
MAX_HEARTBEAT_FAILURES = 3

# Raft consensus (in milliseconds)
DEFAULT_ELECTION_TIMEOUT_MIN = 150
DEFAULT_ELECTION_TIMEOUT_MAX = 300
DEFAULT_RAFT_HEARTBEAT_INTERVAL = 50

# Vectorization
MINHASH_SIGNATURE_SIZE = 128
MINHASH_NUM_PERM = 128
LDA_NUM_TOPICS = 20
TEXTRANK_TOP_KEYWORDS = 10
CHAR_NGRAM_SIZES = [2, 3, 4]
TFIDF_MAX_FEATURES = 5000

# VP-Tree
VP_TREE_LEAF_SIZE = 10
VP_TREE_SAMPLE_SIZE = 100

# Similarity weights (must sum to 1.0)
NAME_SIMILARITY_WEIGHT = 0.4
CONTENT_SIMILARITY_WEIGHT = 0.4
TOPIC_SIMILARITY_WEIGHT = 0.2

# Rebalancing
REBALANCE_THRESHOLD = 0.8
REBALANCE_BATCH_SIZE = 50
REBALANCE_DELAY_SECONDS = 1.0

# Search
DEFAULT_SEARCH_TIMEOUT = 30
MAX_RESULTS_PER_NODE = 100
DEFAULT_MAX_RESULTS = 10

# File handling
MAX_UPLOAD_SIZE_MB = 500
ALLOWED_MIME_TYPES = [
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'text/plain',
    'text/csv',
    'text/html',
    'text/markdown',
    'application/json',
    'application/xml',
]

# DNS
DNS_CACHE_TTL = 30
DNS_FALLBACK_ENABLED = True


class Config(BaseModel):
    """
    Application configuration loaded from environment variables.
    """
    # Node identification
    node_id: str = Field(
        default_factory=lambda: os.environ.get('NODE_ID', 'node-1')
    )
    node_role: str = Field(
        default_factory=lambda: os.environ.get('NODE_ROLE', 'slave')
    )
    cluster_id: str = Field(
        default_factory=lambda: os.environ.get('CLUSTER_ID', 'distrisearch-cluster')
    )
    
    # Network
    api_host: str = Field(
        default_factory=lambda: os.environ.get('API_HOST', '0.0.0.0')
    )
    api_port: int = Field(
        default_factory=lambda: int(os.environ.get('API_PORT', '8000'))
    )
    grpc_port: int = Field(
        default_factory=lambda: int(os.environ.get('GRPC_PORT', '50051'))
    )
    
    # Master connection (for slaves)
    master_host: str = Field(
        default_factory=lambda: os.environ.get('MASTER_HOST', 'master')
    )
    master_port: int = Field(
        default_factory=lambda: int(os.environ.get('MASTER_PORT', '8001'))
    )
    
    # Database
    mongodb_uri: str = Field(
        default_factory=lambda: os.environ.get(
            'MONGODB_URI', 
            'mongodb://mongodb:27017/distrisearch?replicaSet=rs0'
        )
    )
    mongodb_database: str = Field(
        default_factory=lambda: os.environ.get('MONGODB_DATABASE', 'distrisearch')
    )
    
    # Cache
    redis_url: str = Field(
        default_factory=lambda: os.environ.get('REDIS_URL', 'redis://redis:6379')
    )
    
    # Replication
    replication_factor: int = Field(
        default_factory=lambda: int(os.environ.get(
            'REPLICATION_FACTOR', str(DEFAULT_REPLICATION_FACTOR)
        ))
    )
    
    # Raft
    raft_election_timeout_min: int = Field(
        default_factory=lambda: int(os.environ.get(
            'RAFT_ELECTION_TIMEOUT_MIN', str(DEFAULT_ELECTION_TIMEOUT_MIN)
        ))
    )
    raft_election_timeout_max: int = Field(
        default_factory=lambda: int(os.environ.get(
            'RAFT_ELECTION_TIMEOUT_MAX', str(DEFAULT_ELECTION_TIMEOUT_MAX)
        ))
    )
    raft_heartbeat_interval: int = Field(
        default_factory=lambda: int(os.environ.get(
            'RAFT_HEARTBEAT_INTERVAL', str(DEFAULT_RAFT_HEARTBEAT_INTERVAL)
        ))
    )
    
    # Heartbeat
    heartbeat_interval: int = Field(
        default_factory=lambda: int(os.environ.get(
            'HEARTBEAT_INTERVAL', str(DEFAULT_HEARTBEAT_INTERVAL)
        ))
    )
    heartbeat_timeout: int = Field(
        default_factory=lambda: int(os.environ.get(
            'HEARTBEAT_TIMEOUT', str(DEFAULT_HEARTBEAT_TIMEOUT)
        ))
    )
    
    # DNS
    dns_fallback_enabled: bool = Field(
        default_factory=lambda: os.environ.get(
            'DNS_FALLBACK_ENABLED', 'true'
        ).lower() == 'true'
    )
    coredns_host: str = Field(
        default_factory=lambda: os.environ.get('COREDNS_HOST', 'coredns')
    )
    
    # Storage
    data_dir: str = Field(
        default_factory=lambda: os.environ.get('DATA_DIR', '/app/data')
    )
    documents_dir: str = Field(
        default_factory=lambda: os.environ.get('DOCUMENTS_DIR', '/app/data/documents')
    )
    
    # Logging
    log_level: str = Field(
        default_factory=lambda: os.environ.get('LOG_LEVEL', 'INFO')
    )
    
    # Security
    jwt_secret: Optional[str] = Field(
        default_factory=lambda: os.environ.get('JWT_SECRET')
    )
    jwt_algorithm: str = Field(
        default_factory=lambda: os.environ.get('JWT_ALGORITHM', 'HS256')
    )
    jwt_expiration_hours: int = Field(
        default_factory=lambda: int(os.environ.get('JWT_EXPIRATION_HOURS', '24'))
    )
    
    @property
    def master_address(self) -> str:
        """Full address of master node."""
        return f"http://{self.master_host}:{self.master_port}"
    
    @property
    def is_master(self) -> bool:
        """Check if this node is a master."""
        return self.node_role == 'master'
    
    @property
    def is_slave(self) -> bool:
        """Check if this node is a slave."""
        return self.node_role == 'slave'


# Global configuration instance
config = Config()
