# DistriSearch

<div align="center">

**Distributed Document Search Engine with Raft Consensus**

A fault-tolerant distributed search system built with a Master-Slave architecture, Raft-based consensus, and advanced information retrieval techniques.

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black)](https://reactjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![gRPC](https://img.shields.io/badge/gRPC-244c5a?style=flat-square&logo=google&logoColor=white)](https://grpc.io)
[![MongoDB](https://img.shields.io/badge/MongoDB-47A248?style=flat-square&logo=mongodb&logoColor=white)](https://www.mongodb.com)

</div>

---

## Overview

DistriSearch is a distributed document search engine that combines classical information retrieval algorithms with a robust distributed systems architecture. The system uses a **Master-Slave topology** where the master node coordinates search queries across slave nodes, with **Raft consensus** ensuring fault tolerance and consistency across the cluster.

## Features

- **Distributed Architecture**: Master-Slave topology with automatic node discovery and coordination
- **Raft Consensus Protocol**: Leader election, log replication, and fault tolerance
- **gRPC Communication**: High-performance inter-node communication using Protocol Buffers
- **TF-IDF Ranking**: Classic term frequency-inverse document frequency for relevance scoring
- **MinHash Near-Duplicate Detection**: Locality-Sensitive Hashing for identifying similar documents
- **LDA Topic Modeling**: Latent Dirichlet Allocation for discovering document topics
- **React Frontend**: Modern web interface for querying and exploring search results
- **MongoDB Storage**: Document persistence with efficient indexing

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  React Frontend                  │
│              (Search UI + Results)               │
└────────────────────┬────────────────────────────┘
                     │ REST API
┌────────────────────▼────────────────────────────┐
│              FastAPI Master Node                 │
│     (Query Coordination + Result Merging)        │
└──────┬─────────────┬──────────────┬─────────────┘
       │ gRPC        │ gRPC         │ gRPC
┌──────▼──────┐ ┌────▼──────┐ ┌────▼──────┐
│  Slave Node │ │ Slave Node│ │ Slave Node│
│  (TF-IDF)   │ │ (MinHash) │ │   (LDA)   │
└──────┬──────┘ └─────┬─────┘ └─────┬─────┘
       │              │              │
       └──────────────┼──────────────┘
                      │
              ┌───────▼───────┐
              │    MongoDB    │
              │  (Documents)  │
              └───────────────┘
         Raft Consensus Layer
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React, JavaScript |
| **API Gateway** | FastAPI, Python |
| **Communication** | gRPC, Protocol Buffers |
| **Search Algorithms** | TF-IDF, MinHash (LSH), LDA |
| **Consensus** | Raft (custom implementation) |
| **Database** | MongoDB |
| **NLP** | scikit-learn, Gensim |

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- MongoDB running locally or remotely
- pip / virtualenv

### Installation

```bash
# Clone the repository
git clone https://github.com/Pol4720/DistriSearch.git
cd DistriSearch

# Backend setup
pip install -r requirements.txt

# Frontend setup
cd frontend
npm install
```

### Running the System

```bash
# Start the master node
python master.py

# Start slave nodes (in separate terminals)
python slave.py --port 50051
python slave.py --port 50052
python slave.py --port 50053

# Start the frontend
cd frontend
npm start
```

## Information Retrieval Methods

### TF-IDF (Term Frequency-Inverse Document Frequency)
Classic vector space model that ranks documents by term relevance, weighting terms that are frequent in a document but rare across the corpus.

### MinHash + LSH (Locality-Sensitive Hashing)
Probabilistic technique for near-duplicate detection. Estimates Jaccard similarity between document shingle sets efficiently using hash signatures.

### LDA (Latent Dirichlet Allocation)
Generative probabilistic model that discovers latent topic distributions across the document corpus, enabling topic-based search and clustering.

## Academic Context

Developed as a **Distributed Systems** course project at the University of Havana, Faculty of Mathematics and Computer Science (MATCOM).

## License

This project is licensed under the MIT License.
