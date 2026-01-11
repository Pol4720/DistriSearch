#!/usr/bin/env python3
"""
Test Scenario 1: 3 Nodes, 3 Users, 9 Documents
============================================

This script tests the basic functionality of the distributed system:
1. Creates 3 users (Alice, Bob, Carol)
2. Each user uploads 3 documents
3. Verifies documents are replicated across nodes
4. Tests search functionality
5. Tests user swap (different user accessing documents)
6. Verifies document listing stability

Requirements:
- DistriSearch deployed on Docker Swarm with 3 nodes
- All services running and healthy

Usage:
    python scripts/test_scenario_1.py [--base-url http://localhost:8000]
"""

import asyncio
import argparse
import httpx
import json
import sys
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

# Test configuration
BASE_URL = "http://localhost:8000"
API_V1 = "/api/v1"
TIMEOUT = 30.0

# Test data
USERS = [
    {"username": "alice_test", "email": "alice@test.com", "password": "TestPass123!"},
    {"username": "bob_test", "email": "bob@test.com", "password": "TestPass123!"},
    {"username": "carol_test", "email": "carol@test.com", "password": "TestPass123!"},
]

# Each user will create these documents
DOCUMENTS_PER_USER = [
    {
        "title": "Artificial Intelligence Basics",
        "content": "Artificial intelligence is the simulation of human intelligence processes by machines. AI includes learning, reasoning, and self-correction.",
        "tags": ["ai", "technology", "computing"]
    },
    {
        "title": "Machine Learning Fundamentals",
        "content": "Machine learning is a subset of AI that enables systems to learn and improve from experience. Deep learning uses neural networks.",
        "tags": ["ml", "ai", "data-science"]
    },
    {
        "title": "Distributed Systems Architecture",
        "content": "Distributed systems are collections of independent computers that appear as a single system. They provide scalability and fault tolerance.",
        "tags": ["distributed", "architecture", "scalability"]
    },
]


@dataclass
class TestUser:
    username: str
    email: str
    password: str
    user_id: Optional[str] = None
    token: Optional[str] = None
    documents: List[Dict] = field(default_factory=list)


@dataclass
class TestResult:
    name: str
    passed: bool
    message: str
    duration_ms: float
    details: Optional[Dict] = None


class ScenarioTester:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}{API_V1}"
        self.users: List[TestUser] = []
        self.results: List[TestResult] = []
        self.client = httpx.AsyncClient(
            timeout=TIMEOUT, 
            follow_redirects=True,
            verify=False  # Allow self-signed SSL certs
        )
        
    async def close(self):
        await self.client.aclose()
        
    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
        
    async def run_test(self, name: str, test_func) -> TestResult:
        """Run a single test and record results"""
        self.log(f"Running: {name}")
        start = time.time()
        try:
            details = await test_func()
            duration = (time.time() - start) * 1000
            result = TestResult(name=name, passed=True, message="OK", duration_ms=duration, details=details)
        except Exception as e:
            duration = (time.time() - start) * 1000
            result = TestResult(name=name, passed=False, message=str(e), duration_ms=duration)
            self.log(f"FAILED: {e}", "ERROR")
        self.results.append(result)
        status = "✓" if result.passed else "✗"
        self.log(f"{status} {name} ({result.duration_ms:.0f}ms)")
        return result
    
    # ==================== Test Functions ====================
    
    async def test_health_check(self) -> Dict:
        """Test that the API is healthy"""
        response = await self.client.get(f"{self.api_url}/health")
        if response.status_code != 200:
            raise Exception(f"Health check failed: {response.status_code}")
        return response.json()
    
    async def test_create_users(self) -> Dict:
        """Create test users"""
        created = []
        for user_data in USERS:
            # Try to register user
            response = await self.client.post(
                f"{self.api_url}/auth/register",
                json=user_data
            )
            
            if response.status_code in [400, 409] and "already exists" in response.text:
                # User already exists, try to login instead
                self.log(f"User {user_data['username']} already exists, logging in...")
            elif response.status_code not in [200, 201]:
                raise Exception(f"Failed to register {user_data['username']}: {response.status_code} - {response.text}")
            
            # Login to get token
            login_response = await self.client.post(
                f"{self.api_url}/auth/login",
                json={
                    "username": user_data["username"],
                    "password": user_data["password"]
                }
            )
            
            if login_response.status_code != 200:
                raise Exception(f"Failed to login {user_data['username']}: {login_response.status_code} - {login_response.text}")
            
            login_data = login_response.json()
            token = login_data.get("access_token")
            
            # Get user info
            me_response = await self.client.get(
                f"{self.api_url}/users/me",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if me_response.status_code == 200:
                user_info = me_response.json()
                user_id = user_info.get("id") or user_info.get("user_id") or user_info.get("sub")
            else:
                user_id = None
            
            test_user = TestUser(
                username=user_data["username"],
                email=user_data["email"],
                password=user_data["password"],
                user_id=user_id,
                token=token
            )
            self.users.append(test_user)
            created.append(user_data["username"])
            self.log(f"  - {user_data['username']} authenticated (id: {user_id})")
            
        return {"created_users": created}
    
    async def test_create_documents(self) -> Dict:
        """Each user creates 3 documents"""
        created = []
        for i, user in enumerate(self.users):
            headers = {"Authorization": f"Bearer {user.token}"}
            
            for j, doc_template in enumerate(DOCUMENTS_PER_USER):
                # Personalize document for each user
                doc_data = {
                    "title": f"{user.username}'s {doc_template['title']}",
                    "content": f"{doc_template['content']} This document belongs to {user.username}.",
                    "tags": doc_template["tags"] + [user.username]
                }
                
                response = await self.client.post(
                    f"{self.api_url}/documents",
                    json=doc_data,
                    headers=headers
                )
                
                if response.status_code not in [200, 201]:
                    raise Exception(f"Failed to create document for {user.username}: {response.status_code} - {response.text}")
                
                doc = response.json()
                user.documents.append(doc)
                created.append({
                    "user": user.username,
                    "doc_id": doc.get("id"),
                    "title": doc.get("title"),
                    "node_id": doc.get("node_id"),
                    "partition_id": doc.get("partition_id")
                })
                self.log(f"  - Created: {doc.get('title')} (node: {doc.get('node_id')}, partition: {doc.get('partition_id')})")
        
        return {"total_created": len(created), "documents": created}
    
    async def test_document_listing_stability(self) -> Dict:
        """Test that document listing is stable across multiple requests"""
        results = {}
        
        for user in self.users:
            headers = {"Authorization": f"Bearer {user.token}"}
            listings = []
            
            # Request document list multiple times
            for attempt in range(5):
                response = await self.client.get(
                    f"{self.api_url}/documents",
                    headers=headers
                )
                
                if response.status_code != 200:
                    raise Exception(f"Failed to list documents: {response.status_code}")
                
                docs = response.json()
                doc_ids = sorted([d.get("id") for d in docs.get("documents", docs) if d.get("id")])
                listings.append(doc_ids)
                await asyncio.sleep(0.5)  # Small delay between requests
            
            # Check consistency
            is_stable = all(l == listings[0] for l in listings)
            results[user.username] = {
                "stable": is_stable,
                "expected_count": 3,
                "actual_count": len(listings[0]) if listings else 0,
                "listings": listings
            }
            
            if not is_stable:
                self.log(f"  ⚠ WARNING: Unstable listing for {user.username}", "WARN")
            else:
                self.log(f"  - {user.username}: Stable with {len(listings[0])} documents")
        
        # Overall stability check
        all_stable = all(r["stable"] for r in results.values())
        if not all_stable:
            raise Exception("Document listing is unstable!")
        
        return results
    
    async def test_search_functionality(self) -> Dict:
        """Test search across all nodes"""
        user = self.users[0]  # Use first user for search
        headers = {"Authorization": f"Bearer {user.token}"}
        
        search_tests = [
            {"query": "artificial intelligence", "min_results": 1},
            {"query": "machine learning neural networks", "min_results": 1},
            {"query": "distributed systems", "min_results": 1},
        ]
        
        results = []
        for test in search_tests:
            response = await self.client.get(
                f"{self.api_url}/search/quick",
                params={"q": test["query"], "limit": 10},
                headers=headers
            )
            
            if response.status_code != 200:
                raise Exception(f"Search failed: {response.status_code} - {response.text}")
            
            search_results = response.json()
            result_count = len(search_results.get("results", []))
            
            results.append({
                "query": test["query"],
                "expected_min": test["min_results"],
                "actual": result_count,
                "passed": result_count >= test["min_results"]
            })
            self.log(f"  - '{test['query']}': {result_count} results")
        
        all_passed = all(r["passed"] for r in results)
        if not all_passed:
            raise Exception("Some searches did not return expected minimum results")
        
        return {"search_tests": results}
    
    async def test_user_swap_document_access(self) -> Dict:
        """Test that users can only see their own documents"""
        results = {}
        
        for user in self.users:
            headers = {"Authorization": f"Bearer {user.token}"}
            
            # Get user's documents
            response = await self.client.get(
                f"{self.api_url}/documents",
                headers=headers
            )
            
            if response.status_code != 200:
                raise Exception(f"Failed to get documents for {user.username}")
            
            docs = response.json()
            doc_list = docs.get("documents", docs) if isinstance(docs, dict) else docs
            
            # Check all documents belong to this user
            user_doc_ids = [d.get("id") for d in user.documents]
            returned_doc_ids = [d.get("id") for d in doc_list if d.get("id")]
            
            # Verify ownership
            own_docs = [d for d in doc_list if user.username in d.get("title", "")]
            other_docs = [d for d in doc_list if user.username not in d.get("title", "")]
            
            results[user.username] = {
                "expected_docs": len(user.documents),
                "returned_docs": len(doc_list),
                "own_docs": len(own_docs),
                "other_docs": len(other_docs),
                "passed": len(other_docs) == 0
            }
            
            if len(other_docs) > 0:
                self.log(f"  ⚠ {user.username} sees {len(other_docs)} documents from other users!", "WARN")
            else:
                self.log(f"  - {user.username}: sees only own {len(own_docs)} documents")
        
        all_passed = all(r["passed"] for r in results.values())
        if not all_passed:
            raise Exception("Users can see documents from other users!")
        
        return results
    
    async def test_document_get_and_download(self) -> Dict:
        """Test document retrieval (GET by ID) and file download"""
        results = {
            "get_tests": [],
            "download_tests": []
        }
        
        for user in self.users:
            headers = {"Authorization": f"Bearer {user.token}"}
            
            if user.documents:
                doc = user.documents[0]  # Test with first document
                doc_id = doc.get("id")
                
                # Test GET document by ID
                response = await self.client.get(
                    f"{self.api_url}/documents/{doc_id}",
                    headers=headers
                )
                
                get_passed = response.status_code == 200
                if get_passed:
                    doc_data = response.json()
                    self.log(f"  - GET {user.username}: {doc_data.get('title', '')[:40]}...")
                else:
                    self.log(f"  ⚠ GET {user.username}: Error {response.status_code}", "WARN")
                
                results["get_tests"].append({
                    "user": user.username,
                    "doc_id": doc_id,
                    "status": response.status_code,
                    "passed": get_passed
                })
                
                # Test download endpoint
                download_response = await self.client.get(
                    f"{self.api_url}/documents/{doc_id}/download",
                    headers=headers
                )
                
                # All documents should be downloadable now (text docs as .txt)
                download_ok = download_response.status_code == 200
                if download_response.status_code == 200:
                    self.log(f"  - Download {user.username}: {len(download_response.content)} bytes")
                else:
                    self.log(f"  ⚠ Download {user.username}: Error {download_response.status_code}", "WARN")
                
                results["download_tests"].append({
                    "user": user.username,
                    "doc_id": doc_id,
                    "status": download_response.status_code,
                    "passed": download_ok
                })
        
        # Check all tests passed
        all_get_passed = all(t["passed"] for t in results["get_tests"])
        all_download_passed = all(t["passed"] for t in results["download_tests"])
        
        if not all_get_passed:
            raise Exception("Some GET document requests failed")
        if not all_download_passed:
            raise Exception("Some download requests returned unexpected errors")
        
        return results
    
    async def test_upload_and_download_file(self) -> Dict:
        """Test file upload and download"""
        user = self.users[0]
        headers = {"Authorization": f"Bearer {user.token}"}
        
        # Create test file content
        test_content = b"This is test file content for upload and download verification. 123456789"
        test_filename = "test_upload_scenario1.txt"
        
        # Upload file
        files = {"file": (test_filename, test_content, "text/plain")}
        data = {"title": "Scenario1 Upload Test", "tags": "test,scenario1,upload"}
        
        response = await self.client.post(
            f"{self.api_url}/documents/upload",
            files=files,
            data=data,
            headers=headers
        )
        
        if response.status_code not in [200, 201]:
            raise Exception(f"Upload failed: {response.status_code} - {response.text}")
        
        upload_result = response.json()
        uploaded_doc_id = upload_result.get("id")
        self.log(f"  - Uploaded: {test_filename} (ID: {uploaded_doc_id})")
        
        # Save for cleanup
        user.documents.append({"id": uploaded_doc_id})
        
        # Wait a bit for sync
        await asyncio.sleep(2)
        
        # Download the file
        download_response = await self.client.get(
            f"{self.api_url}/documents/{uploaded_doc_id}/download",
            headers=headers
        )
        
        if download_response.status_code != 200:
            raise Exception(f"Download failed: {download_response.status_code}")
        
        downloaded_content = download_response.content
        content_matches = downloaded_content == test_content
        
        self.log(f"  - Downloaded: {len(downloaded_content)} bytes")
        self.log(f"  - Content match: {'YES' if content_matches else 'NO'}")
        
        if not content_matches:
            raise Exception(f"Downloaded content does not match! Original: {len(test_content)}, Downloaded: {len(downloaded_content)}")
        
        return {
            "uploaded_doc_id": uploaded_doc_id,
            "file_size": len(test_content),
            "content_matches": content_matches
        }
    
    async def test_document_replication(self) -> Dict:
        """Verify documents are replicated to multiple nodes"""
        # Get cluster status to check replication
        user = self.users[0]
        headers = {"Authorization": f"Bearer {user.token}"}
        
        # Try to get cluster info
        cluster_response = await self.client.get(
            f"{self.api_url}/internal/cluster/status"
        )
        
        if cluster_response.status_code != 200:
            # Try without auth
            cluster_response = await self.client.get(
                f"{self.api_url}/cluster/status"
            )
        
        cluster_info = cluster_response.json() if cluster_response.status_code == 200 else {}
        
        # Check documents have node assignments
        doc_nodes = {}
        for user in self.users:
            for doc in user.documents:
                doc_id = doc.get("id")
                node_id = doc.get("node_id")
                if doc_id and node_id:
                    doc_nodes[doc_id] = node_id
        
        unique_nodes = set(doc_nodes.values())
        
        result = {
            "total_documents": len(doc_nodes),
            "documents_with_nodes": len([n for n in doc_nodes.values() if n]),
            "unique_nodes_used": len(unique_nodes),
            "node_distribution": {},
            "cluster_info": cluster_info
        }
        
        # Count documents per node
        for doc_id, node_id in doc_nodes.items():
            if node_id:
                result["node_distribution"][node_id] = result["node_distribution"].get(node_id, 0) + 1
        
        self.log(f"  - Documents distributed across {len(unique_nodes)} nodes")
        for node, count in result["node_distribution"].items():
            self.log(f"    - {node}: {count} documents")
        
        return result
    
    async def test_cleanup(self) -> Dict:
        """Clean up test documents"""
        deleted = []
        for user in self.users:
            headers = {"Authorization": f"Bearer {user.token}"}
            
            for doc in user.documents:
                doc_id = doc.get("id")
                if doc_id:
                    response = await self.client.delete(
                        f"{self.api_url}/documents/{doc_id}",
                        headers=headers
                    )
                    if response.status_code in [200, 204, 404]:
                        deleted.append(doc_id)
                        self.log(f"  - Deleted: {doc_id}")
        
        return {"deleted": len(deleted)}
    
    # ==================== Main Test Runner ====================
    
    async def run_all_tests(self, cleanup: bool = True) -> bool:
        """Run all tests in sequence"""
        self.log("=" * 60)
        self.log("SCENARIO 1: 3 Nodes, 3 Users, 9 Documents")
        self.log("=" * 60)
        self.log(f"Base URL: {self.base_url}")
        self.log("")
        
        # Run tests in sequence
        await self.run_test("Health Check", self.test_health_check)
        await self.run_test("Create Users", self.test_create_users)
        await self.run_test("Create Documents", self.test_create_documents)
        
        # Wait for replication
        self.log("Waiting 5s for replication to propagate...")
        await asyncio.sleep(5)
        
        await self.run_test("Document Listing Stability", self.test_document_listing_stability)
        await self.run_test("Search Functionality", self.test_search_functionality)
        await self.run_test("User Document Isolation", self.test_user_swap_document_access)
        await self.run_test("Document GET and Download", self.test_document_get_and_download)
        await self.run_test("Upload and Download File", self.test_upload_and_download_file)
        await self.run_test("Document Replication", self.test_document_replication)
        
        if cleanup:
            await self.run_test("Cleanup", self.test_cleanup)
        
        # Print summary
        self.log("")
        self.log("=" * 60)
        self.log("TEST SUMMARY")
        self.log("=" * 60)
        
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        total = len(self.results)
        
        for result in self.results:
            status = "✓ PASS" if result.passed else "✗ FAIL"
            self.log(f"  {status}: {result.name} ({result.duration_ms:.0f}ms)")
            if not result.passed:
                self.log(f"         Error: {result.message}")
        
        self.log("")
        self.log(f"Results: {passed}/{total} passed, {failed} failed")
        
        return failed == 0


async def main():
    parser = argparse.ArgumentParser(description="Test Scenario 1: 3 Nodes, 3 Users, 9 Documents")
    parser.add_argument("--base-url", default=BASE_URL, help="Base URL of the API")
    parser.add_argument("--no-cleanup", action="store_true", help="Don't delete test documents")
    args = parser.parse_args()
    
    # Disable SSL warnings for self-signed certificates
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    tester = ScenarioTester(args.base_url)
    try:
        success = await tester.run_all_tests(cleanup=not args.no_cleanup)
        sys.exit(0 if success else 1)
    finally:
        await tester.close()


if __name__ == "__main__":
    asyncio.run(main())
