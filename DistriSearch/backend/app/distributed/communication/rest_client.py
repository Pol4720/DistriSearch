"""
REST Client for inter-node communication.

Provides HTTP/REST client implementations for:
- Client to slave communication
- Slave to master communication
- General node-to-node REST calls
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
import aiohttp
from aiohttp import ClientTimeout, ClientSession

logger = logging.getLogger(__name__)


@dataclass
class RESTResponse:
    """Response from a REST call."""
    status: int
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    latency_ms: float = 0.0
    
    @property
    def success(self) -> bool:
        """Check if request was successful."""
        return 200 <= self.status < 300


class RESTClient:
    """
    Generic REST client for inter-node communication.
    
    Features:
    - Connection pooling
    - Automatic retries
    - Timeout handling
    - Circuit breaker pattern
    """
    
    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """
        Initialize REST client.
        
        Args:
            base_url: Base URL for all requests
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries
            retry_delay: Delay between retries in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = ClientTimeout(total=timeout)
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Session (created lazily)
        self._session: Optional[ClientSession] = None
        
        # Circuit breaker state
        self._failure_count = 0
        self._circuit_open = False
        self._circuit_open_until: Optional[datetime] = None
        self._failure_threshold = 5
        self._circuit_timeout = 30.0  # seconds
        
        # Statistics
        self._request_count = 0
        self._error_count = 0
    
    async def _get_session(self) -> ClientSession:
        """Get or create the HTTP session."""
        if self._session is None or self._session.closed:
            self._session = ClientSession(timeout=self.timeout)
        return self._session
    
    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def _check_circuit(self) -> bool:
        """Check if circuit breaker allows request."""
        if not self._circuit_open:
            return True
        
        if self._circuit_open_until and datetime.now() > self._circuit_open_until:
            # Try to reset circuit
            self._circuit_open = False
            self._failure_count = 0
            return True
        
        return False
    
    def _record_success(self):
        """Record successful request."""
        self._failure_count = 0
        self._circuit_open = False
    
    def _record_failure(self):
        """Record failed request."""
        self._failure_count += 1
        self._error_count += 1
        
        if self._failure_count >= self._failure_threshold:
            self._circuit_open = True
            self._circuit_open_until = datetime.now()
            logger.warning(
                f"Circuit breaker opened for {self.base_url}"
            )
    
    async def request(
        self,
        method: str,
        path: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> RESTResponse:
        """
        Make an HTTP request with retries.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            path: URL path
            data: Request body (for POST/PUT)
            params: Query parameters
            headers: Additional headers
            
        Returns:
            RESTResponse object
        """
        # Check circuit breaker
        if not self._check_circuit():
            return RESTResponse(
                status=503,
                error="Circuit breaker open",
            )
        
        url = f"{self.base_url}/{path.lstrip('/')}"
        self._request_count += 1
        
        for attempt in range(self.max_retries + 1):
            start_time = datetime.now()
            
            try:
                session = await self._get_session()
                
                async with session.request(
                    method=method,
                    url=url,
                    json=data,
                    params=params,
                    headers=headers,
                ) as response:
                    latency = (datetime.now() - start_time).total_seconds() * 1000
                    
                    try:
                        response_data = await response.json()
                    except:
                        response_data = None
                    
                    self._record_success()
                    
                    return RESTResponse(
                        status=response.status,
                        data=response_data,
                        latency_ms=latency,
                    )
                    
            except asyncio.TimeoutError:
                self._record_failure()
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue
                    
                return RESTResponse(
                    status=408,
                    error="Request timeout",
                )
                
            except aiohttp.ClientError as e:
                self._record_failure()
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue
                    
                return RESTResponse(
                    status=503,
                    error=f"Connection error: {str(e)}",
                )
                
            except Exception as e:
                self._record_failure()
                logger.error(f"Request error: {e}")
                return RESTResponse(
                    status=500,
                    error=str(e),
                )
        
        return RESTResponse(
            status=503,
            error="Max retries exceeded",
        )
    
    async def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> RESTResponse:
        """Make GET request."""
        return await self.request("GET", path, params=params, headers=headers)
    
    async def post(
        self,
        path: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> RESTResponse:
        """Make POST request."""
        return await self.request("POST", path, data=data, headers=headers)
    
    async def put(
        self,
        path: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> RESTResponse:
        """Make PUT request."""
        return await self.request("PUT", path, data=data, headers=headers)
    
    async def delete(
        self,
        path: str,
        headers: Optional[Dict[str, str]] = None,
    ) -> RESTResponse:
        """Make DELETE request."""
        return await self.request("DELETE", path, headers=headers)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics."""
        return {
            "base_url": self.base_url,
            "request_count": self._request_count,
            "error_count": self._error_count,
            "circuit_open": self._circuit_open,
            "failure_count": self._failure_count,
        }


class NodeClient(RESTClient):
    """
    REST client for communication with slave nodes.
    
    Used by clients and masters to communicate with slaves.
    """
    
    def __init__(self, node_address: str, **kwargs):
        """
        Initialize node client.
        
        Args:
            node_address: Address of the target node
            **kwargs: Additional RESTClient arguments
        """
        super().__init__(base_url=f"http://{node_address}", **kwargs)
        self.node_address = node_address
    
    async def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> RESTResponse:
        """
        Search documents on this node.
        
        Args:
            query: Search query
            limit: Maximum results
            filters: Search filters
            
        Returns:
            Search results
        """
        return await self.post(
            "/api/search",
            data={
                "query": query,
                "limit": limit,
                "filters": filters or {},
            },
        )
    
    async def get_document(self, doc_id: str) -> RESTResponse:
        """Get document by ID."""
        return await self.get(f"/api/documents/{doc_id}")
    
    async def index_document(
        self,
        doc_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> RESTResponse:
        """Index a document on this node."""
        return await self.post(
            "/api/documents",
            data={
                "id": doc_id,
                "content": content,
                "metadata": metadata or {},
            },
        )
    
    async def delete_document(self, doc_id: str) -> RESTResponse:
        """Delete a document from this node."""
        return await self.delete(f"/api/documents/{doc_id}")
    
    async def get_health(self) -> RESTResponse:
        """Get node health status."""
        return await self.get("/api/health")
    
    async def get_stats(self) -> RESTResponse:
        """Get node statistics."""
        return await self.get("/api/stats")


class MasterClient(RESTClient):
    """
    REST client for communication with master node.
    
    Used by slaves to communicate with their master.
    """
    
    def __init__(self, master_address: str, **kwargs):
        """
        Initialize master client.
        
        Args:
            master_address: Address of the master node
            **kwargs: Additional RESTClient arguments
        """
        super().__init__(base_url=f"http://{master_address}", **kwargs)
        self.master_address = master_address
    
    async def register_node(
        self,
        node_id: str,
        node_address: str,
        capabilities: Optional[Dict[str, Any]] = None,
    ) -> RESTResponse:
        """
        Register this node with the master.
        
        Args:
            node_id: This node's ID
            node_address: This node's address
            capabilities: Node capabilities
            
        Returns:
            Registration response
        """
        return await self.post(
            "/api/cluster/register",
            data={
                "node_id": node_id,
                "address": node_address,
                "capabilities": capabilities or {},
            },
        )
    
    async def deregister_node(self, node_id: str) -> RESTResponse:
        """Deregister this node from the master."""
        return await self.delete(f"/api/cluster/nodes/{node_id}")
    
    async def report_stats(
        self,
        node_id: str,
        stats: Dict[str, Any],
    ) -> RESTResponse:
        """
        Report node statistics to master.
        
        Args:
            node_id: This node's ID
            stats: Statistics to report
            
        Returns:
            Response
        """
        return await self.post(
            f"/api/cluster/nodes/{node_id}/stats",
            data=stats,
        )
    
    async def get_cluster_config(self) -> RESTResponse:
        """Get cluster configuration from master."""
        return await self.get("/api/cluster/config")
    
    async def get_partition_assignment(self, node_id: str) -> RESTResponse:
        """Get partition assignment for this node."""
        return await self.get(f"/api/cluster/nodes/{node_id}/partitions")
    
    async def request_rebalance(self) -> RESTResponse:
        """Request cluster rebalancing."""
        return await self.post("/api/cluster/rebalance")
    
    async def forward_raft_rpc(
        self,
        target_id: str,
        rpc_data: Dict[str, Any],
    ) -> RESTResponse:
        """
        Forward Raft RPC to another master.
        
        Args:
            target_id: Target master ID
            rpc_data: RPC data to forward
            
        Returns:
            RPC response
        """
        return await self.post(
            f"/api/raft/rpc/{target_id}",
            data=rpc_data,
        )


class NodeClientPool:
    """
    Pool of NodeClient instances for multiple nodes.
    
    Manages connections to multiple nodes efficiently.
    """
    
    def __init__(
        self,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        """
        Initialize client pool.
        
        Args:
            timeout: Default timeout for all clients
            max_retries: Default max retries for all clients
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self._clients: Dict[str, NodeClient] = {}
        self._lock = asyncio.Lock()
    
    async def get_client(self, node_address: str) -> NodeClient:
        """
        Get or create client for a node.
        
        Args:
            node_address: Target node address
            
        Returns:
            NodeClient instance
        """
        async with self._lock:
            if node_address not in self._clients:
                self._clients[node_address] = NodeClient(
                    node_address=node_address,
                    timeout=self.timeout,
                    max_retries=self.max_retries,
                )
            return self._clients[node_address]
    
    async def remove_client(self, node_address: str):
        """Remove and close client for a node."""
        async with self._lock:
            if node_address in self._clients:
                await self._clients[node_address].close()
                del self._clients[node_address]
    
    async def close_all(self):
        """Close all clients."""
        async with self._lock:
            for client in self._clients.values():
                await client.close()
            self._clients.clear()
    
    async def broadcast(
        self,
        method: str,
        path: str,
        node_addresses: List[str],
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, RESTResponse]:
        """
        Broadcast request to multiple nodes.
        
        Args:
            method: HTTP method
            path: URL path
            node_addresses: Target node addresses
            data: Request data
            
        Returns:
            Dict mapping node address to response
        """
        async def make_request(address: str) -> tuple[str, RESTResponse]:
            client = await self.get_client(address)
            response = await client.request(method, path, data=data)
            return address, response
        
        tasks = [make_request(addr) for addr in node_addresses]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        responses = {}
        for result in results:
            if isinstance(result, tuple):
                addr, response = result
                responses[addr] = response
            else:
                logger.error(f"Broadcast error: {result}")
        
        return responses
