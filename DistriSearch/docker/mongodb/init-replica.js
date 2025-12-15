// MongoDB Replica Set Initialization Script
// This runs on first start of MongoDB container

print("=== DistriSearch MongoDB Initialization ===");

// Wait a bit for MongoDB to be fully ready
sleep(2000);

// Initialize replica set
try {
    rs.initiate({
        _id: "rs0",
        members: [
            { _id: 0, host: "mongodb:27017", priority: 1 }
        ]
    });
    print("Replica set initialized successfully");
} catch (e) {
    if (e.codeName === "AlreadyInitialized") {
        print("Replica set already initialized");
    } else {
        print("Error initializing replica set: " + e);
    }
}

// Wait for replica set to be ready
sleep(3000);

// Switch to distrisearch database
db = db.getSiblingDB('distrisearch');

// Create collections with validation schemas
print("Creating collections...");

// Documents collection
db.createCollection("documents", {
    validator: {
        $jsonSchema: {
            bsonType: "object",
            required: ["doc_id", "filename", "created_at", "node_id"],
            properties: {
                doc_id: {
                    bsonType: "string",
                    description: "Unique document identifier (UUID)"
                },
                filename: {
                    bsonType: "string",
                    description: "Original filename"
                },
                content_hash: {
                    bsonType: "string",
                    description: "SHA-256 hash of content for deduplication"
                },
                file_path: {
                    bsonType: "string",
                    description: "Path to document on filesystem"
                },
                file_size: {
                    bsonType: "long",
                    description: "File size in bytes"
                },
                mime_type: {
                    bsonType: "string",
                    description: "MIME type of the document"
                },
                node_id: {
                    bsonType: "string",
                    description: "Primary node storing this document"
                },
                replica_nodes: {
                    bsonType: "array",
                    description: "List of nodes with replicas"
                },
                vector: {
                    bsonType: "object",
                    description: "Adaptive document vector"
                },
                metadata: {
                    bsonType: "object",
                    description: "Additional metadata"
                },
                created_at: {
                    bsonType: "date"
                },
                updated_at: {
                    bsonType: "date"
                }
            }
        }
    }
});

// Partitions collection (VP-Tree index)
db.createCollection("partitions", {
    validator: {
        $jsonSchema: {
            bsonType: "object",
            required: ["partition_id", "node_id", "vantage_point"],
            properties: {
                partition_id: {
                    bsonType: "string"
                },
                node_id: {
                    bsonType: "string",
                    description: "Node responsible for this partition"
                },
                vantage_point: {
                    bsonType: "object",
                    description: "VP-Tree vantage point vector"
                },
                radius: {
                    bsonType: "double",
                    description: "Coverage radius"
                },
                document_count: {
                    bsonType: "int",
                    description: "Number of documents in partition"
                },
                left_child: {
                    bsonType: "string"
                },
                right_child: {
                    bsonType: "string"
                }
            }
        }
    }
});

// Nodes collection (cluster membership)
db.createCollection("nodes", {
    validator: {
        $jsonSchema: {
            bsonType: "object",
            required: ["node_id", "role", "status"],
            properties: {
                node_id: {
                    bsonType: "string"
                },
                role: {
                    enum: ["master", "slave"],
                    description: "Node role"
                },
                status: {
                    enum: ["active", "inactive", "draining", "failed"],
                    description: "Node status"
                },
                host: {
                    bsonType: "string"
                },
                port: {
                    bsonType: "int"
                },
                last_heartbeat: {
                    bsonType: "date"
                },
                document_count: {
                    bsonType: "int"
                },
                capacity: {
                    bsonType: "object"
                }
            }
        }
    }
});

// Raft state collection
db.createCollection("raft_state", {
    validator: {
        $jsonSchema: {
            bsonType: "object",
            required: ["node_id"],
            properties: {
                node_id: {
                    bsonType: "string"
                },
                current_term: {
                    bsonType: "int"
                },
                voted_for: {
                    bsonType: ["string", "null"]
                },
                log: {
                    bsonType: "array"
                },
                commit_index: {
                    bsonType: "int"
                },
                last_applied: {
                    bsonType: "int"
                }
            }
        }
    }
});

// Operations log collection
db.createCollection("operations_log", {
    capped: true,
    size: 104857600,  // 100MB
    max: 100000
});

// Create indexes
print("Creating indexes...");

db.documents.createIndex({ "doc_id": 1 }, { unique: true });
db.documents.createIndex({ "content_hash": 1 });
db.documents.createIndex({ "node_id": 1 });
db.documents.createIndex({ "filename": "text" });
db.documents.createIndex({ "created_at": -1 });

db.partitions.createIndex({ "partition_id": 1 }, { unique: true });
db.partitions.createIndex({ "node_id": 1 });

db.nodes.createIndex({ "node_id": 1 }, { unique: true });
db.nodes.createIndex({ "status": 1 });
db.nodes.createIndex({ "last_heartbeat": 1 });

db.raft_state.createIndex({ "node_id": 1 }, { unique: true });

db.operations_log.createIndex({ "timestamp": -1 });
db.operations_log.createIndex({ "operation_type": 1 });

print("=== MongoDB Initialization Complete ===");
