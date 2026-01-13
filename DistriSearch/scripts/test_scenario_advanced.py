#!/usr/bin/env python3
"""
Test Scenario Advanced: Diverse Files + Replication Factor 2 Verification
==========================================================================

This script tests:
1. Upload of diverse file types (PDF, Dockerfile, binary files, text files)
2. Verification that documents are replicated with factor 2 (exist on 2 nodes)
3. Document operations: list, get, download, search for all file types
4. Proper cleanup (verify documents are deleted from all nodes)
5. Investigation of potential orphan documents

Requirements:
- DistriSearch deployed with 3 nodes
- All services running and healthy

Usage:
    python scripts/test_scenario_advanced.py [--base-url http://localhost:8000] [--nodes node1_url,node2_url,node3_url]
"""

import asyncio
import argparse
import httpx
import json
import sys
import os
import base64
import tempfile
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


# Default configuration
DEFAULT_BASE_URL = "http://localhost:8001"
DEFAULT_NODES = [
    "http://localhost:8001",
    "http://localhost:8002", 
    "http://localhost:8003"
]
API_V1 = "/api/v1"
TIMEOUT = 60.0

# Test user
TEST_USER = {
    "username": "advanced_test_user",
    "email": "advanced_test@test.com",
    "password": "TestPass123!"
}


@dataclass
class TestFile:
    """Represents a test file to upload"""
    name: str
    content: bytes
    content_type: str
    description: str
    expected_searchable: bool = True  # Whether content should be extractable


@dataclass
class TestResult:
    name: str
    passed: bool
    message: str
    duration_ms: float
    details: Optional[Dict] = None


def create_test_files() -> List[TestFile]:
    """Create diverse test files"""
    files = []
    
    # 1. Plain text file
    files.append(TestFile(
        name="test_document.txt",
        content=b"This is a plain text document for testing search functionality. It contains keywords like distributed systems and replication.",
        content_type="text/plain",
        description="Plain text file",
        expected_searchable=True
    ))
    
    # 2. Dockerfile (no extension, application/octet-stream)
    dockerfile_content = b'''FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \\
    build-essential \\
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
'''
    files.append(TestFile(
        name="Dockerfile",
        content=dockerfile_content,
        content_type="application/octet-stream",
        description="Dockerfile (no extension)",
        expected_searchable=False  # Binary file, searchable by filename only
    ))
    
    # 3. JSON file
    json_content = json.dumps({
        "name": "Test Configuration",
        "version": "1.0.0",
        "settings": {
            "replication_factor": 2,
            "consistency": "eventual",
            "algorithm": "gossip"
        }
    }, indent=2).encode('utf-8')
    files.append(TestFile(
        name="config.json",
        content=json_content,
        content_type="application/json",
        description="JSON configuration file",
        expected_searchable=True
    ))
    
    # 4. Markdown file
    markdown_content = b'''# Distributed Systems Guide

## Introduction
This guide covers the basics of distributed systems architecture.

## Key Concepts
- **Replication**: Storing copies of data on multiple nodes
- **Consistency**: Ensuring all nodes see the same data
- **Partition Tolerance**: Handling network partitions

## Best Practices
1. Use eventual consistency when possible
2. Implement proper retry logic
3. Monitor replication lag
'''
    files.append(TestFile(
        name="README.md",
        content=markdown_content,
        content_type="text/markdown",
        description="Markdown documentation",
        expected_searchable=True
    ))
    
    # 5. Python script
    python_content = b'''#!/usr/bin/env python3
"""
Sample Python Script for Testing
"""

def calculate_hash(data: bytes) -> str:
    """Calculate SHA256 hash of data."""
    import hashlib
    return hashlib.sha256(data).hexdigest()

def main():
    print("Hello from test script!")
    result = calculate_hash(b"test data")
    print(f"Hash: {result}")

if __name__ == "__main__":
    main()
'''
    files.append(TestFile(
        name="script.py",
        content=python_content,
        content_type="text/x-python",
        description="Python script",
        expected_searchable=True
    ))
    
    # 6. Binary file (simulated image header)
    # PNG header + some random bytes
    binary_content = bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,  # 1x1 pixel
        0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
        0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,
        0x54, 0x08, 0xD7, 0x63, 0xF8, 0xFF, 0xFF, 0xFF,
        0x00, 0x05, 0xFE, 0x02, 0xFE, 0xDC, 0xCC, 0x59,
        0xE7, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,
        0x44, 0xAE, 0x42, 0x60, 0x82
    ])
    files.append(TestFile(
        name="test_image.png",
        content=binary_content,
        content_type="image/png",
        description="Binary PNG image",
        expected_searchable=False  # Binary, searchable by filename only
    ))
    
    # 7. YAML file
    yaml_content = b'''version: '3.8'
services:
  app:
    image: distrisearch/app:latest
    ports:
      - "8000:8000"
    environment:
      - REPLICATION_FACTOR=2
      - CONSISTENCY_LEVEL=eventual
    deploy:
      replicas: 3
'''
    files.append(TestFile(
        name="docker-compose.yml",
        content=yaml_content,
        content_type="application/x-yaml",
        description="Docker Compose YAML",
        expected_searchable=True
    ))
    
    return files


class AdvancedTester:
    def __init__(self, base_url: str, node_urls: List[str]):
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}{API_V1}"
        self.node_urls = [url.rstrip("/") for url in node_urls]
        self.results: List[TestResult] = []
        self.uploaded_docs: List[Dict] = []
        self.token: Optional[str] = None
        self.user_id: Optional[str] = None
        self.client = httpx.AsyncClient(
            timeout=TIMEOUT,
            follow_redirects=True,
            verify=False
        )
        
    async def close(self):
        await self.client.aclose()
        
    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        colors = {
            "INFO": "\033[0m",
            "WARN": "\033[93m",
            "ERROR": "\033[91m",
            "SUCCESS": "\033[92m"
        }
        color = colors.get(level, "\033[0m")
        reset = "\033[0m"
        print(f"[{timestamp}] [{level}] {color}{message}{reset}")
        
    async def run_test(self, name: str, test_func, *args, **kwargs) -> TestResult:
        """Run a single test and record result"""
        self.log(f"Running: {name}")
        start = datetime.now()
        
        try:
            details = await test_func(*args, **kwargs)
            duration = (datetime.now() - start).total_seconds() * 1000
            result = TestResult(name=name, passed=True, message="OK", duration_ms=duration, details=details)
            self.log(f"✓ {name} ({duration:.0f}ms)", "SUCCESS")
        except Exception as e:
            duration = (datetime.now() - start).total_seconds() * 1000
            result = TestResult(name=name, passed=False, message=str(e), duration_ms=duration)
            self.log(f"✗ {name}: {e}", "ERROR")
        
        self.results.append(result)
        return result
    
    # =========================================================================
    # Authentication
    # =========================================================================
    
    async def authenticate(self) -> Dict:
        """Authenticate or register test user"""
        # Try to register
        response = await self.client.post(
            f"{self.api_url}/auth/register",
            json=TEST_USER
        )
        
        if response.status_code in [200, 201]:
            data = response.json()
            self.token = data.get("access_token")
            self.user_id = data.get("user_id") or data.get("id")
            self.log(f"  - Registered new user: {TEST_USER['username']}")
        elif response.status_code in [400, 409]:
            # User exists, login
            login_response = await self.client.post(
                f"{self.api_url}/auth/login",
                json={"username": TEST_USER["username"], "password": TEST_USER["password"]}
            )
            if login_response.status_code != 200:
                raise Exception(f"Login failed: {login_response.status_code} - {login_response.text}")
            data = login_response.json()
            self.token = data.get("access_token")
            self.user_id = data.get("user_id") or data.get("id")
            self.log(f"  - Logged in existing user: {TEST_USER['username']}")
        else:
            raise Exception(f"Authentication failed: {response.status_code} - {response.text}")
        
        # Get user_id from /auth/me if not available
        if not self.user_id:
            me_response = await self.client.get(
                f"{self.api_url}/auth/me",
                headers=self.get_headers()
            )
            if me_response.status_code == 200:
                me_data = me_response.json()
                self.user_id = me_data.get("id") or me_data.get("user_id")
                self.log(f"  - Got user_id from /auth/me: {self.user_id}")
        
        if not self.user_id:
            raise Exception("Could not obtain user_id from authentication")
        
        return {"token": self.token, "user_id": self.user_id}
    
    def get_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}
    
    # =========================================================================
    # Test: Upload Diverse Files
    # =========================================================================
    
    async def test_upload_diverse_files(self) -> Dict:
        """Upload various file types and verify they are stored correctly"""
        test_files = create_test_files()
        results = []
        
        for tf in test_files:
            self.log(f"  - Uploading: {tf.name} ({tf.description})")
            
            files = {"file": (tf.name, tf.content, tf.content_type)}
            data = {"title": f"Test: {tf.description}", "tags": "test,advanced,diverse"}
            
            response = await self.client.post(
                f"{self.api_url}/documents/upload",
                files=files,
                data=data,
                headers=self.get_headers()
            )
            
            if response.status_code not in [200, 201]:
                raise Exception(f"Upload failed for {tf.name}: {response.status_code} - {response.text}")
            
            doc = response.json()
            doc_info = {
                "id": doc.get("id"),
                "filename": tf.name,
                "title": doc.get("title"),
                "node_id": doc.get("node_id"),
                "partition_id": doc.get("partition_id"),
                "file_size": len(tf.content),
                "content_type": tf.content_type,
                "original_content": tf.content,
                "expected_searchable": tf.expected_searchable
            }
            self.uploaded_docs.append(doc_info)
            results.append(doc_info)
            
            self.log(f"    ✓ ID: {doc.get('id')}, Node: {doc.get('node_id')}")
        
        return {"uploaded": len(results), "documents": results}
    
    # =========================================================================
    # Test: Verify Replication Factor 2
    # =========================================================================
    
    async def test_replication_factor_2(self) -> Dict:
        """Verify each document exists on exactly 2 nodes"""
        self.log("  - Waiting 5s for replication to complete...")
        await asyncio.sleep(5)
        
        results = []
        all_ok = True
        
        for doc in self.uploaded_docs:
            doc_id = doc["id"]
            nodes_with_doc = []
            
            # Query each node directly
            for node_url in self.node_urls:
                try:
                    # Check MongoDB on each node via internal endpoint
                    response = await self.client.post(
                        f"{node_url}{API_V1}/internal/documents/list",
                        json={"owner_id": self.user_id},
                        timeout=10.0
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        docs = data.get("documents", [])
                        doc_ids = [str(d.get("_id") or d.get("id", "")) for d in docs]
                        
                        if doc_id in doc_ids:
                            nodes_with_doc.append(node_url.split(":")[-1])  # Get port as identifier
                            
                except Exception as e:
                    self.log(f"    ⚠ Could not query {node_url}: {e}", "WARN")
            
            replication_count = len(nodes_with_doc)
            expected = 2  # Replication factor
            
            status = "✓" if replication_count >= expected else "✗"
            is_ok = replication_count >= expected
            if not is_ok:
                all_ok = False
            
            results.append({
                "doc_id": doc_id,
                "filename": doc["filename"],
                "replication_count": replication_count,
                "expected": expected,
                "nodes": nodes_with_doc,
                "passed": is_ok
            })
            
            level = "SUCCESS" if is_ok else "ERROR"
            self.log(f"  {status} {doc['filename']}: replicated to {replication_count} nodes {nodes_with_doc}", level)
        
        if not all_ok:
            failed = [r for r in results if not r["passed"]]
            raise Exception(f"Replication factor not met for {len(failed)} documents")
        
        return {"results": results, "all_replicated": all_ok}
    
    # =========================================================================
    # Test: Document Listing Stability
    # =========================================================================
    
    async def test_listing_all_nodes(self) -> Dict:
        """Test that document listing is consistent across all nodes"""
        results = {}
        expected_count = len(self.uploaded_docs)
        
        for node_url in self.node_urls:
            node_id = node_url.split(":")[-1]
            
            try:
                response = await self.client.get(
                    f"{node_url}{API_V1}/documents",
                    headers=self.get_headers()
                )
                
                if response.status_code == 200:
                    data = response.json()
                    docs = data.get("documents", [])
                    doc_count = len(docs)
                    doc_ids = sorted([d.get("id") for d in docs])
                    
                    results[node_id] = {
                        "count": doc_count,
                        "expected": expected_count,
                        "doc_ids": doc_ids,
                        "passed": doc_count == expected_count
                    }
                    
                    status = "✓" if doc_count == expected_count else "✗"
                    self.log(f"  {status} Node :{node_id}: {doc_count}/{expected_count} documents")
                else:
                    results[node_id] = {"error": f"HTTP {response.status_code}"}
                    self.log(f"  ✗ Node :{node_id}: Error {response.status_code}", "ERROR")
                    
            except Exception as e:
                results[node_id] = {"error": str(e)}
                self.log(f"  ✗ Node :{node_id}: {e}", "ERROR")
        
        # Verify consistency
        counts = [r.get("count", 0) for r in results.values() if "count" in r]
        if not counts or min(counts) != max(counts):
            self.log(f"  ⚠ Inconsistent document counts across nodes!", "WARN")
        
        return results
    
    # =========================================================================
    # Test: Download All Files
    # =========================================================================
    
    async def test_download_all_files(self) -> Dict:
        """Download each uploaded file and verify content matches"""
        results = []
        all_ok = True
        
        for doc in self.uploaded_docs:
            doc_id = doc["id"]
            filename = doc["filename"]
            original_content = doc["original_content"]
            
            try:
                response = await self.client.get(
                    f"{self.api_url}/documents/{doc_id}/download",
                    headers=self.get_headers()
                )
                
                if response.status_code == 200:
                    downloaded_content = response.content
                    matches = downloaded_content == original_content
                    
                    result = {
                        "doc_id": doc_id,
                        "filename": filename,
                        "original_size": len(original_content),
                        "downloaded_size": len(downloaded_content),
                        "content_matches": matches,
                        "passed": matches
                    }
                    
                    if matches:
                        self.log(f"  ✓ {filename}: {len(downloaded_content)} bytes, content matches")
                    else:
                        self.log(f"  ✗ {filename}: Content mismatch! Original: {len(original_content)}, Downloaded: {len(downloaded_content)}", "ERROR")
                        all_ok = False
                else:
                    result = {
                        "doc_id": doc_id,
                        "filename": filename,
                        "error": f"HTTP {response.status_code}: {response.text[:200]}",
                        "passed": False
                    }
                    self.log(f"  ✗ {filename}: Download failed - {response.status_code}", "ERROR")
                    all_ok = False
                    
            except Exception as e:
                result = {
                    "doc_id": doc_id,
                    "filename": filename,
                    "error": str(e),
                    "passed": False
                }
                self.log(f"  ✗ {filename}: {e}", "ERROR")
                all_ok = False
            
            results.append(result)
        
        if not all_ok:
            failed = [r for r in results if not r.get("passed")]
            raise Exception(f"Download failed for {len(failed)} files")
        
        return {"results": results, "all_downloaded": all_ok}
    
    # =========================================================================
    # Test: Get Document by ID
    # =========================================================================
    
    async def test_get_documents_by_id(self) -> Dict:
        """Test GET /documents/{id} for all uploaded documents"""
        results = []
        all_ok = True
        
        for doc in self.uploaded_docs:
            doc_id = doc["id"]
            filename = doc["filename"]
            
            try:
                response = await self.client.get(
                    f"{self.api_url}/documents/{doc_id}",
                    headers=self.get_headers()
                )
                
                if response.status_code == 200:
                    data = response.json()
                    result = {
                        "doc_id": doc_id,
                        "filename": filename,
                        "title": data.get("title"),
                        "has_content": bool(data.get("content")),
                        "has_vectors": bool(data.get("vectors")),
                        "node_id": data.get("node_id"),
                        "passed": True
                    }
                    self.log(f"  ✓ {filename}: GET successful (node: {data.get('node_id')})")
                else:
                    result = {
                        "doc_id": doc_id,
                        "filename": filename,
                        "error": f"HTTP {response.status_code}",
                        "passed": False
                    }
                    self.log(f"  ✗ {filename}: GET failed - {response.status_code}", "ERROR")
                    all_ok = False
                    
            except Exception as e:
                result = {
                    "doc_id": doc_id,
                    "filename": filename,
                    "error": str(e),
                    "passed": False
                }
                self.log(f"  ✗ {filename}: {e}", "ERROR")
                all_ok = False
            
            results.append(result)
        
        if not all_ok:
            raise Exception(f"GET failed for some documents")
        
        return {"results": results}
    
    # =========================================================================
    # Test: Search Functionality for Diverse Files
    # =========================================================================
    
    async def test_search_diverse_files(self) -> Dict:
        """Test search for various file types"""
        search_queries = [
            {"query": "dockerfile python", "description": "Search Dockerfile content"},
            {"query": "distributed systems", "description": "Search text content"},
            {"query": "replication factor", "description": "Search JSON/YAML content"},
            {"query": "docker-compose", "description": "Search by filename"},
            {"query": "config.json", "description": "Search JSON by filename"},
            {"query": "test_image.png", "description": "Search image by filename"},
        ]
        
        results = []
        
        for search in search_queries:
            try:
                response = await self.client.get(
                    f"{self.api_url}/search/quick",
                    params={"q": search["query"], "limit": 20},
                    headers=self.get_headers()
                )
                
                if response.status_code == 200:
                    data = response.json()
                    result_count = len(data.get("results", []))
                    result_titles = [r.get("title", "") for r in data.get("results", [])]
                    
                    result = {
                        "query": search["query"],
                        "description": search["description"],
                        "results_count": result_count,
                        "titles": result_titles[:3],
                        "passed": result_count > 0
                    }
                    
                    status = "✓" if result_count > 0 else "⚠"
                    level = "SUCCESS" if result_count > 0 else "WARN"
                    self.log(f"  {status} '{search['query']}': {result_count} results", level)
                else:
                    result = {
                        "query": search["query"],
                        "error": f"HTTP {response.status_code}",
                        "passed": False
                    }
                    self.log(f"  ✗ '{search['query']}': Search failed", "ERROR")
                    
            except Exception as e:
                result = {
                    "query": search["query"],
                    "error": str(e),
                    "passed": False
                }
                self.log(f"  ✗ '{search['query']}': {e}", "ERROR")
            
            results.append(result)
        
        return {"results": results}
    
    # =========================================================================
    # Test: Cleanup and Verify Deletion
    # =========================================================================
    
    async def test_cleanup_and_verify(self) -> Dict:
        """Delete all uploaded documents and verify they are removed from all nodes"""
        results = []
        
        # Step 1: Delete all documents
        self.log("  - Deleting documents...")
        for doc in self.uploaded_docs:
            doc_id = doc["id"]
            filename = doc["filename"]
            
            try:
                response = await self.client.delete(
                    f"{self.api_url}/documents/{doc_id}",
                    headers=self.get_headers()
                )
                
                if response.status_code in [200, 204]:
                    self.log(f"    ✓ Deleted: {filename}")
                else:
                    self.log(f"    ⚠ Delete returned {response.status_code} for {filename}", "WARN")
                    
            except Exception as e:
                self.log(f"    ✗ Delete failed for {filename}: {e}", "ERROR")
        
        # Step 2: Wait for deletion to propagate
        self.log("  - Waiting 3s for deletion to propagate...")
        await asyncio.sleep(3)
        
        # Step 3: Verify documents are deleted from all nodes
        self.log("  - Verifying deletion on all nodes...")
        orphans_found = []
        
        for node_url in self.node_urls:
            node_id = node_url.split(":")[-1]
            
            try:
                response = await self.client.get(
                    f"{node_url}{API_V1}/documents",
                    headers=self.get_headers()
                )
                
                if response.status_code == 200:
                    data = response.json()
                    remaining_docs = data.get("documents", [])
                    
                    # Check if any of our test documents remain
                    test_doc_ids = [d["id"] for d in self.uploaded_docs]
                    remaining_test_docs = [d for d in remaining_docs if d.get("id") in test_doc_ids]
                    
                    if remaining_test_docs:
                        for d in remaining_test_docs:
                            orphans_found.append({
                                "node": node_id,
                                "doc_id": d.get("id"),
                                "title": d.get("title")
                            })
                        self.log(f"    ⚠ Node :{node_id}: {len(remaining_test_docs)} orphan documents found!", "WARN")
                    else:
                        self.log(f"    ✓ Node :{node_id}: All test documents deleted")
                        
            except Exception as e:
                self.log(f"    ✗ Node :{node_id}: Verification failed - {e}", "ERROR")
        
        # Step 4: Check MongoDB directly via internal endpoint
        self.log("  - Checking MongoDB directly...")
        for node_url in self.node_urls:
            node_id = node_url.split(":")[-1]
            
            try:
                response = await self.client.post(
                    f"{node_url}{API_V1}/internal/documents/list",
                    json={"owner_id": self.user_id},
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    docs = data.get("documents", [])
                    test_doc_ids = [d["id"] for d in self.uploaded_docs]
                    remaining = [d for d in docs if str(d.get("_id") or d.get("id")) in test_doc_ids]
                    
                    if remaining:
                        self.log(f"    ⚠ Node :{node_id} MongoDB: {len(remaining)} documents still in DB!", "WARN")
                        for r in remaining:
                            orphans_found.append({
                                "node": node_id,
                                "source": "mongodb",
                                "doc_id": str(r.get("_id") or r.get("id")),
                                "title": r.get("title")
                            })
                    else:
                        self.log(f"    ✓ Node :{node_id} MongoDB: Clean")
                        
            except Exception as e:
                self.log(f"    ✗ Node :{node_id} MongoDB check failed: {e}", "ERROR")
        
        if orphans_found:
            raise Exception(f"Found {len(orphans_found)} orphan documents after cleanup!")
        
        return {"orphans_found": orphans_found, "cleanup_successful": len(orphans_found) == 0}
    
    # =========================================================================
    # Run All Tests
    # =========================================================================
    
    async def run_all_tests(self):
        """Run all tests in sequence"""
        self.log("=" * 70)
        self.log("ADVANCED TEST SCENARIO: Diverse Files + Replication Verification")
        self.log("=" * 70)
        self.log(f"Base URL: {self.base_url}")
        self.log(f"Nodes: {self.node_urls}")
        self.log("")
        
        # Authenticate first
        await self.run_test("Authentication", self.authenticate)
        if not self.token:
            self.log("Authentication failed, aborting tests", "ERROR")
            return
        
        # Run all tests
        await self.run_test("Upload Diverse Files", self.test_upload_diverse_files)
        await self.run_test("Replication Factor 2 Verification", self.test_replication_factor_2)
        await self.run_test("Document Listing Across Nodes", self.test_listing_all_nodes)
        await self.run_test("Download All Files", self.test_download_all_files)
        await self.run_test("GET Documents by ID", self.test_get_documents_by_id)
        await self.run_test("Search Diverse Files", self.test_search_diverse_files)
        await self.run_test("Cleanup and Verify Deletion", self.test_cleanup_and_verify)
        
        # Print summary
        self.log("")
        self.log("=" * 70)
        self.log("TEST SUMMARY")
        self.log("=" * 70)
        
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        
        for result in self.results:
            status = "✓ PASS" if result.passed else "✗ FAIL"
            self.log(f"  {status}: {result.name} ({result.duration_ms:.0f}ms)")
            if not result.passed:
                self.log(f"         Error: {result.message}")
        
        self.log("")
        self.log(f"Results: {passed}/{len(self.results)} passed, {failed} failed")
        
        return failed == 0


async def main():
    parser = argparse.ArgumentParser(description="Advanced DistriSearch Test Scenario")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Base URL of the API")
    parser.add_argument("--nodes", default=",".join(DEFAULT_NODES), help="Comma-separated list of node URLs")
    args = parser.parse_args()
    
    node_urls = args.nodes.split(",")
    
    tester = AdvancedTester(args.base_url, node_urls)
    
    try:
        success = await tester.run_all_tests()
        sys.exit(0 if success else 1)
    finally:
        await tester.close()


if __name__ == "__main__":
    asyncio.run(main())
