<p align="center">
  <img src="DistriSearch/assets/logo.png" alt="DistriSearch Logo" width="200"/>
</p>

# DistriSearch

DistriSearch is a distributed file search system developed as the **final project for the Distributed Systems course (4th year, Computer Science degree)**.  

Unlike traditional search engines, DistriSearch allows every node in the network to both **contribute files** and **query the system**. Each computer that joins the system becomes part of a distributed architecture, enabling collaborative search and access to documents across the network.

## ✨ Key Features
- **Distributed Architecture:** no central server; every node acts as both client and provider.  
- **File Discovery:** search files by name and type across all connected machines.  
- **Resilience:** system tolerates node departures without causing failures or inconsistencies.  
- **Duplication Handling:** manages duplicate files efficiently, selecting the best source for transfer.  
- **Fault-Tolerant Transfers:** supports error handling if a file becomes unavailable during access.  
- **Efficiency:** optimized search mechanisms to minimize response time for users.  
 - **Centralized Mode (NEW):** Quickly run the platform as a single-node indexer to validate core search functionality before deploying a full distributed network.

## 📚 Project Context
This project was designed as part of the *Distributed Systems* course, 4th year of the Computer Science degree.  
It demonstrates practical application of distributed computing concepts such as **fault tolerance, replication, peer-to-peer communication, and efficiency in search algorithms**.

## 🚀 Future Improvements
- Support for richer metadata-based search (e.g., keywords, size, creation date).  
- Enhanced fault tolerance with replication strategies.  
- Integration of semantic search capabilities.  
- Web-based UI for easier interaction.  
 - Unified download proxy for both central and distributed nodes.

---

## Centralized Mode

The project now supports a lightweight "centralized" mode that indexes a single local folder without deploying agents. This is ideal for early demos or validating the core search & download flow.

### How It Works
1. A synthetic node with ID `central` is created automatically when you trigger a scan.
2. Files from a target folder (default: `./central_shared` or environment variable `CENTRAL_SHARED_FOLDER`) are hashed (SHA-256) and indexed.
3. Searches return these files like any distributed result.
4. Downloads for central files are served directly by the backend via `GET /central/file/{file_id}`.

### API Endpoints (Central Mode)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/central/scan` | Scan & (re)index the central folder. Optional body: `{ "folder": "path" }` |
| GET | `/central/mode` | Returns flags: centralized/distributed active |
| GET | `/central/file/{file_id}` | Direct file download (backend serves the file) |

### Frontend Usage
In the Streamlit sidebar select: **Modo de Operación → Centralizado**.
Options:
* Provide a folder path (or leave blank for default).
* Enable auto-scan so switching to the mode triggers indexing.
* Perform a search—results list files under the central node.

### Falling Back to Distributed Mode
Switch the toggle back to "Distribuido"; existing distributed nodes (if any) continue functioning unchanged. Both modes can coexist: if distributed nodes are registered, the system reports both capabilities.

### When to Use Centralized Mode
* Initial milestone demo / academic delivery.
* CI tests (fast, isolated environment).
* Debugging search relevance or UI layout without multi-node noise.

---

## Download Flow
* Distributed file: frontend gets `/download/` POST result pointing to the agent node URL.
* Central file: backend responds with a proxied URL: `/central/file/{file_id}`.

---

## Testing
Added tests in `backend/tests/test_central.py` covering:
* Initial scan and search.
* Re-scan updating counts.
* Coexistence with a simulated distributed node.

Run:
```
cd DistriSearch/backend
pytest -q
```

---

## Environment Variables
| Variable | Purpose | Default |
|----------|---------|---------|
| `CENTRAL_SHARED_FOLDER` | Folder scanned in centralized mode | `./central_shared` |
| `DISTRISEARCH_BACKEND_URL` | Frontend → backend base URL | `http://localhost:8000` |

---

## Roadmap (Next)
* Signed download URLs.
* File deletion & re-sync.
* Elasticsearch integration.
* Auth & ACL per node.
* Streaming / chunked transfers for large files.

---

---
