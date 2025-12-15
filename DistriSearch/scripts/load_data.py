#!/usr/bin/env python3
"""
DistriSearch Data Loader Script
Load sample documents into the system for testing and demos
"""

import asyncio
import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any
import aiohttp
import hashlib

# Sample documents for testing
SAMPLE_DOCUMENTS = [
    {
        "title": "Introduction to Distributed Systems",
        "content": """
Distributed systems are a collection of independent computers that appear to users as a single coherent system. 
They are characterized by concurrency of components, lack of a global clock, and independent failure of components.

Key concepts in distributed systems include:
- Scalability: The ability to handle growing amounts of work
- Fault tolerance: The ability to continue operating despite failures
- Consistency: Ensuring all nodes see the same data at the same time
- Availability: Ensuring the system remains operational
- Partition tolerance: Handling network partitions gracefully

The CAP theorem states that a distributed system can only guarantee two of these three properties: 
Consistency, Availability, and Partition tolerance. This fundamental limitation shapes the design 
of all distributed systems.
        """,
        "metadata": {"category": "technology", "tags": ["distributed-systems", "scalability", "architecture"]}
    },
    {
        "title": "Machine Learning Fundamentals",
        "content": """
Machine learning is a subset of artificial intelligence that enables systems to learn and improve 
from experience without being explicitly programmed. It focuses on developing algorithms that can 
access data and use it to learn for themselves.

Types of machine learning:
1. Supervised Learning: Learning from labeled data to make predictions
2. Unsupervised Learning: Finding patterns in unlabeled data
3. Reinforcement Learning: Learning through trial and error with rewards

Common algorithms include:
- Linear Regression for continuous predictions
- Logistic Regression for classification
- Decision Trees for interpretable models
- Neural Networks for complex pattern recognition
- K-means for clustering
- Support Vector Machines for classification

The machine learning workflow typically involves data collection, preprocessing, feature engineering,
model selection, training, evaluation, and deployment.
        """,
        "metadata": {"category": "technology", "tags": ["machine-learning", "AI", "algorithms"]}
    },
    {
        "title": "Database Design Principles",
        "content": """
Good database design is fundamental to building efficient and maintainable applications. 
The process involves understanding requirements, modeling entities and relationships, 
and implementing proper normalization.

Normalization forms:
- First Normal Form (1NF): Eliminate repeating groups
- Second Normal Form (2NF): Remove partial dependencies
- Third Normal Form (3NF): Remove transitive dependencies
- Boyce-Codd Normal Form (BCNF): Stricter 3NF

Key concepts:
- Primary keys uniquely identify records
- Foreign keys establish relationships between tables
- Indexes improve query performance
- ACID properties ensure transaction reliability

NoSQL databases offer alternatives for specific use cases:
- Document stores (MongoDB) for flexible schemas
- Key-value stores (Redis) for caching
- Graph databases (Neo4j) for connected data
- Column stores (Cassandra) for analytical workloads
        """,
        "metadata": {"category": "technology", "tags": ["database", "SQL", "normalization"]}
    },
    {
        "title": "Cloud Computing Overview",
        "content": """
Cloud computing delivers computing services over the internet, offering flexible resources, 
faster innovation, and economies of scale. Major providers include AWS, Azure, and Google Cloud.

Service models:
- IaaS (Infrastructure as a Service): Virtual machines and storage
- PaaS (Platform as a Service): Application development platforms
- SaaS (Software as a Service): Ready-to-use applications

Deployment models:
- Public cloud: Shared infrastructure
- Private cloud: Dedicated infrastructure
- Hybrid cloud: Combination of public and private
- Multi-cloud: Using multiple cloud providers

Key benefits:
- Scalability and elasticity
- Pay-per-use pricing
- Global availability
- Reduced capital expenditure
- Automatic updates and patches

Security considerations include data encryption, identity management, compliance requirements,
and network security configurations.
        """,
        "metadata": {"category": "technology", "tags": ["cloud", "AWS", "infrastructure"]}
    },
    {
        "title": "Software Testing Best Practices",
        "content": """
Software testing is crucial for ensuring quality and reliability. A comprehensive testing strategy 
includes multiple levels and types of tests working together.

Testing pyramid:
1. Unit tests: Test individual components in isolation
2. Integration tests: Test interactions between components
3. End-to-end tests: Test complete user workflows

Types of testing:
- Functional testing: Verify features work correctly
- Performance testing: Measure response times and throughput
- Security testing: Identify vulnerabilities
- Usability testing: Evaluate user experience
- Regression testing: Ensure changes don't break existing functionality

Best practices:
- Write tests before code (TDD)
- Aim for high code coverage
- Use meaningful test names
- Keep tests independent and repeatable
- Mock external dependencies
- Run tests in CI/CD pipelines

Tools include JUnit, pytest, Jest, Selenium, and various mocking frameworks.
        """,
        "metadata": {"category": "technology", "tags": ["testing", "quality", "TDD"]}
    },
    {
        "title": "API Design Guidelines",
        "content": """
Well-designed APIs are essential for building scalable and maintainable systems. 
REST and GraphQL are the most common API paradigms.

REST principles:
- Use HTTP methods appropriately (GET, POST, PUT, DELETE)
- Design resource-oriented URLs
- Return appropriate status codes
- Support pagination for collections
- Version your API

GraphQL advantages:
- Clients request exactly what they need
- Single endpoint for all operations
- Strong typing with schema
- Real-time updates with subscriptions

Best practices:
- Use consistent naming conventions
- Provide comprehensive documentation
- Implement proper error handling
- Support filtering, sorting, and pagination
- Use HTTPS and authentication
- Rate limit to prevent abuse
- Version your API to manage changes

OpenAPI (Swagger) specification is widely used for documenting REST APIs.
        """,
        "metadata": {"category": "technology", "tags": ["API", "REST", "GraphQL"]}
    },
    {
        "title": "Microservices Architecture",
        "content": """
Microservices architecture structures an application as a collection of loosely coupled services.
Each service is independently deployable, scalable, and maintainable.

Characteristics:
- Single responsibility per service
- Independent deployment and scaling
- Decentralized data management
- Fault isolation
- Technology diversity

Communication patterns:
- Synchronous: REST, gRPC
- Asynchronous: Message queues, event streaming

Challenges:
- Distributed system complexity
- Data consistency across services
- Service discovery and load balancing
- Monitoring and debugging
- Network latency

Supporting technologies:
- Containers (Docker) for packaging
- Orchestration (Kubernetes) for management
- Service mesh (Istio) for networking
- API Gateway for routing
- Circuit breakers for resilience
        """,
        "metadata": {"category": "technology", "tags": ["microservices", "architecture", "docker"]}
    },
    {
        "title": "Cybersecurity Fundamentals",
        "content": """
Cybersecurity protects systems, networks, and data from digital attacks. 
Understanding common threats and defenses is essential for all technology professionals.

Common threats:
- Malware: Viruses, ransomware, trojans
- Phishing: Social engineering attacks
- SQL injection: Database attacks
- XSS: Cross-site scripting
- DDoS: Denial of service attacks

Defense strategies:
- Defense in depth: Multiple security layers
- Least privilege: Minimal access rights
- Zero trust: Verify everything
- Security by design: Build security in

Key practices:
- Regular security audits
- Penetration testing
- Employee training
- Incident response planning
- Backup and recovery
- Patch management

Compliance frameworks include GDPR, HIPAA, PCI-DSS, and SOC 2.
        """,
        "metadata": {"category": "technology", "tags": ["security", "cybersecurity", "compliance"]}
    },
    {
        "title": "DevOps Practices",
        "content": """
DevOps combines development and operations to shorten the development lifecycle 
while delivering features, fixes, and updates frequently and reliably.

Key practices:
- Continuous Integration (CI): Frequent code integration
- Continuous Delivery (CD): Automated deployment pipeline
- Infrastructure as Code (IaC): Managing infrastructure through code
- Monitoring and logging: Observability at all levels
- Automated testing: Quality gates in the pipeline

Tools ecosystem:
- Version control: Git, GitHub, GitLab
- CI/CD: Jenkins, GitHub Actions, CircleCI
- Containers: Docker, Podman
- Orchestration: Kubernetes, Docker Swarm
- IaC: Terraform, Ansible, CloudFormation
- Monitoring: Prometheus, Grafana, ELK Stack

Cultural aspects:
- Collaboration between teams
- Shared responsibility
- Continuous improvement
- Blameless postmortems
- Automation mindset
        """,
        "metadata": {"category": "technology", "tags": ["devops", "CI/CD", "automation"]}
    },
    {
        "title": "Data Structures and Algorithms",
        "content": """
Understanding data structures and algorithms is fundamental to writing efficient code.
The choice of data structure impacts the time and space complexity of operations.

Common data structures:
- Arrays: Contiguous memory, O(1) access
- Linked Lists: Dynamic size, O(n) access
- Hash Tables: O(1) average lookup
- Trees: Hierarchical data, O(log n) operations
- Graphs: Networks and relationships
- Stacks and Queues: LIFO and FIFO

Algorithm categories:
- Sorting: Quick sort, merge sort, heap sort
- Searching: Binary search, BFS, DFS
- Dynamic programming: Optimal substructure
- Greedy algorithms: Local optimal choices
- Divide and conquer: Break down problems

Complexity analysis:
- Big O notation for upper bound
- Consider both time and space
- Analyze worst, average, best cases
- Trade-offs between complexity and simplicity

Practice platforms include LeetCode, HackerRank, and CodeSignal.
        """,
        "metadata": {"category": "technology", "tags": ["algorithms", "data-structures", "complexity"]}
    }
]


class DataLoader:
    """Load sample documents into DistriSearch"""
    
    def __init__(self, api_url: str):
        self.api_url = api_url.rstrip('/')
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def check_health(self) -> bool:
        """Check if API is available"""
        try:
            async with self.session.get(
                f"{self.api_url}/api/v1/health",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                return response.status == 200
        except Exception:
            return False
    
    async def upload_document(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Upload a single document"""
        # Generate a consistent ID based on content
        content_hash = hashlib.md5(doc["content"].encode()).hexdigest()[:8]
        
        payload = {
            "title": doc["title"],
            "content": doc["content"].strip(),
            "metadata": doc.get("metadata", {})
        }
        
        try:
            async with self.session.post(
                f"{self.api_url}/api/v1/documents",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status in [200, 201]:
                    result = await response.json()
                    return {"success": True, "id": result.get("id"), "title": doc["title"]}
                else:
                    error = await response.text()
                    return {"success": False, "title": doc["title"], "error": error}
        except Exception as e:
            return {"success": False, "title": doc["title"], "error": str(e)}
    
    async def load_documents(self, documents: List[Dict[str, Any]], parallel: int = 5) -> List[Dict[str, Any]]:
        """Load multiple documents with concurrency control"""
        results = []
        
        for i in range(0, len(documents), parallel):
            batch = documents[i:i + parallel]
            batch_results = await asyncio.gather(
                *[self.upload_document(doc) for doc in batch],
                return_exceptions=True
            )
            
            for result in batch_results:
                if isinstance(result, Exception):
                    results.append({"success": False, "error": str(result)})
                else:
                    results.append(result)
        
        return results
    
    async def load_from_directory(self, directory: str) -> List[Dict[str, Any]]:
        """Load documents from a directory"""
        documents = []
        path = Path(directory)
        
        if not path.exists():
            print(f"Directory not found: {directory}")
            return []
        
        for file_path in path.glob("**/*"):
            if file_path.is_file() and file_path.suffix in [".txt", ".md", ".json"]:
                try:
                    content = file_path.read_text(encoding="utf-8")
                    
                    if file_path.suffix == ".json":
                        data = json.loads(content)
                        if isinstance(data, dict):
                            documents.append(data)
                        elif isinstance(data, list):
                            documents.extend(data)
                    else:
                        documents.append({
                            "title": file_path.stem,
                            "content": content,
                            "metadata": {
                                "source": str(file_path),
                                "type": file_path.suffix[1:]
                            }
                        })
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")
        
        return await self.load_documents(documents)


async def main():
    parser = argparse.ArgumentParser(description="DistriSearch Data Loader")
    parser.add_argument("--api-url", default="http://localhost:8000", help="API server URL")
    parser.add_argument("--sample", action="store_true", help="Load sample documents")
    parser.add_argument("--directory", "-d", help="Load documents from directory")
    parser.add_argument("--file", "-f", help="Load documents from JSON file")
    parser.add_argument("--parallel", "-p", type=int, default=5, help="Number of parallel uploads")
    
    args = parser.parse_args()
    
    async with DataLoader(args.api_url) as loader:
        # Check API health
        print("Checking API availability...")
        if not await loader.check_health():
            print(f"Error: API at {args.api_url} is not available")
            sys.exit(1)
        
        print("API is available")
        
        documents_to_load = []
        
        if args.sample:
            print(f"Loading {len(SAMPLE_DOCUMENTS)} sample documents...")
            documents_to_load = SAMPLE_DOCUMENTS
        
        if args.directory:
            print(f"Loading documents from {args.directory}...")
            results = await loader.load_from_directory(args.directory)
            print_results(results)
            return
        
        if args.file:
            print(f"Loading documents from {args.file}...")
            try:
                with open(args.file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        documents_to_load.extend(data)
                    else:
                        documents_to_load.append(data)
            except Exception as e:
                print(f"Error reading file: {e}")
                sys.exit(1)
        
        if not documents_to_load:
            print("No documents to load. Use --sample, --directory, or --file")
            parser.print_help()
            sys.exit(1)
        
        results = await loader.load_documents(documents_to_load, args.parallel)
        print_results(results)


def print_results(results: List[Dict[str, Any]]):
    """Print loading results"""
    success_count = sum(1 for r in results if r.get("success"))
    fail_count = len(results) - success_count
    
    print(f"\n{'=' * 50}")
    print(f"Loading Results")
    print(f"{'=' * 50}")
    print(f"Total: {len(results)}")
    print(f"Success: {success_count}")
    print(f"Failed: {fail_count}")
    print(f"{'=' * 50}\n")
    
    for result in results:
        if result.get("success"):
            print(f"✓ {result.get('title', 'Unknown')} -> {result.get('id', 'N/A')}")
        else:
            print(f"✗ {result.get('title', 'Unknown')}: {result.get('error', 'Unknown error')}")


if __name__ == "__main__":
    asyncio.run(main())
