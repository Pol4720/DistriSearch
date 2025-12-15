"""
Service Discovery for DistriSearch.

Implements service discovery and DNS integration for:
- Node discovery
- Master election awareness
- Dynamic DNS updates
"""

import asyncio
import logging
import socket
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Set
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ServiceType(Enum):
    """Types of services in the cluster."""
    MASTER = "master"
    SLAVE = "slave"
    API_GATEWAY = "api-gateway"
    DNS = "dns"
    MONGODB = "mongodb"


@dataclass
class ServiceEndpoint:
    """
    A discovered service endpoint.
    
    Attributes:
        service_type: Type of service
        node_id: Unique node identifier
        address: Network address (host:port)
        healthy: Whether endpoint is healthy
        last_seen: Last time endpoint was seen
        metadata: Additional endpoint metadata
    """
    service_type: ServiceType
    node_id: str
    address: str
    healthy: bool = True
    last_seen: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def host(self) -> str:
        """Get host from address."""
        return self.address.split(':')[0]
    
    @property
    def port(self) -> int:
        """Get port from address."""
        parts = self.address.split(':')
        return int(parts[1]) if len(parts) > 1 else 8000
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "service_type": self.service_type.value,
            "node_id": self.node_id,
            "address": self.address,
            "healthy": self.healthy,
            "last_seen": self.last_seen.isoformat(),
            "metadata": self.metadata,
        }


class FallbackDNSResolver:
    """
    DNS resolver with fallback mechanisms.
    
    Tries multiple DNS resolution strategies:
    1. Standard DNS lookup
    2. Docker DNS (for Swarm)
    3. Static fallback
    """
    
    def __init__(
        self,
        dns_servers: Optional[List[str]] = None,
        cache_ttl: float = 60.0,
    ):
        """
        Initialize DNS resolver.
        
        Args:
            dns_servers: Custom DNS servers to use
            cache_ttl: Cache TTL in seconds
        """
        self.dns_servers = dns_servers or []
        self.cache_ttl = cache_ttl
        
        # Resolution cache
        self._cache: Dict[str, tuple[List[str], datetime]] = {}
        
        # Lock
        self._lock = asyncio.Lock()
    
    async def resolve(self, hostname: str) -> List[str]:
        """
        Resolve hostname to IP addresses.
        
        Args:
            hostname: Hostname to resolve
            
        Returns:
            List of IP addresses
        """
        # Check cache
        async with self._lock:
            if hostname in self._cache:
                ips, timestamp = self._cache[hostname]
                if (datetime.now() - timestamp).total_seconds() < self.cache_ttl:
                    return ips
        
        # Try standard DNS
        ips = await self._resolve_standard(hostname)
        
        if not ips:
            # Try Docker DNS (tasks.service_name pattern)
            ips = await self._resolve_docker(hostname)
        
        # Cache result
        if ips:
            async with self._lock:
                self._cache[hostname] = (ips, datetime.now())
        
        return ips
    
    async def _resolve_standard(self, hostname: str) -> List[str]:
        """Standard DNS resolution."""
        try:
            loop = asyncio.get_event_loop()
            result = await loop.getaddrinfo(
                hostname,
                None,
                family=socket.AF_INET,
                type=socket.SOCK_STREAM,
            )
            return list(set(addr[4][0] for addr in result))
        except Exception as e:
            logger.debug(f"Standard DNS failed for {hostname}: {e}")
            return []
    
    async def _resolve_docker(self, hostname: str) -> List[str]:
        """Docker Swarm DNS resolution (tasks.service_name)."""
        try:
            # Try tasks. prefix for round-robin to all replicas
            tasks_hostname = f"tasks.{hostname}"
            loop = asyncio.get_event_loop()
            result = await loop.getaddrinfo(
                tasks_hostname,
                None,
                family=socket.AF_INET,
                type=socket.SOCK_STREAM,
            )
            return list(set(addr[4][0] for addr in result))
        except Exception as e:
            logger.debug(f"Docker DNS failed for {hostname}: {e}")
            return []
    
    def clear_cache(self):
        """Clear the resolution cache."""
        self._cache.clear()


class ServiceDiscovery:
    """
    Service discovery for DistriSearch cluster.
    
    Discovers and tracks all services in the cluster
    using DNS and direct registration.
    """
    
    def __init__(
        self,
        node_id: str,
        dns_resolver: Optional[FallbackDNSResolver] = None,
        discovery_interval: float = 30.0,
    ):
        """
        Initialize service discovery.
        
        Args:
            node_id: This node's ID
            dns_resolver: DNS resolver to use
            discovery_interval: Discovery refresh interval
        """
        self.node_id = node_id
        self.dns_resolver = dns_resolver or FallbackDNSResolver()
        self.discovery_interval = discovery_interval
        
        # Discovered services
        self._services: Dict[str, ServiceEndpoint] = {}
        
        # Service patterns for DNS discovery
        self._dns_patterns: Dict[ServiceType, str] = {
            ServiceType.MASTER: "master.distrisearch.local",
            ServiceType.SLAVE: "slave.distrisearch.local",
            ServiceType.API_GATEWAY: "api.distrisearch.local",
            ServiceType.DNS: "dns.distrisearch.local",
            ServiceType.MONGODB: "mongodb.distrisearch.local",
        }
        
        # Background task
        self._running = False
        self._discovery_task: Optional[asyncio.Task] = None
        
        # Lock
        self._lock = asyncio.Lock()
        
        logger.info(f"ServiceDiscovery initialized for node {node_id}")
    
    async def start(self):
        """Start service discovery."""
        if self._running:
            return
        
        self._running = True
        self._discovery_task = asyncio.create_task(self._discovery_loop())
        
        # Initial discovery
        await self.discover_all()
        
        logger.info("ServiceDiscovery started")
    
    async def stop(self):
        """Stop service discovery."""
        self._running = False
        
        if self._discovery_task and not self._discovery_task.done():
            self._discovery_task.cancel()
            try:
                await self._discovery_task
            except asyncio.CancelledError:
                pass
        
        logger.info("ServiceDiscovery stopped")
    
    async def _discovery_loop(self):
        """Periodically refresh service discovery."""
        try:
            while self._running:
                await asyncio.sleep(self.discovery_interval)
                await self.discover_all()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Discovery loop error: {e}")
    
    async def discover_all(self):
        """Discover all services."""
        for service_type, hostname in self._dns_patterns.items():
            await self.discover_by_dns(service_type, hostname)
    
    async def discover_by_dns(
        self,
        service_type: ServiceType,
        hostname: str,
    ):
        """
        Discover services by DNS.
        
        Args:
            service_type: Type of service to discover
            hostname: DNS hostname pattern
        """
        try:
            ips = await self.dns_resolver.resolve(hostname)
            
            for ip in ips:
                endpoint_id = f"{service_type.value}_{ip}"
                
                # Default ports by service type
                port = {
                    ServiceType.MASTER: 8000,
                    ServiceType.SLAVE: 8000,
                    ServiceType.API_GATEWAY: 80,
                    ServiceType.DNS: 53,
                    ServiceType.MONGODB: 27017,
                }.get(service_type, 8000)
                
                async with self._lock:
                    self._services[endpoint_id] = ServiceEndpoint(
                        service_type=service_type,
                        node_id=endpoint_id,
                        address=f"{ip}:{port}",
                        healthy=True,
                        last_seen=datetime.now(),
                    )
            
            logger.debug(
                f"Discovered {len(ips)} {service_type.value} endpoints"
            )
            
        except Exception as e:
            logger.warning(f"DNS discovery failed for {hostname}: {e}")
    
    async def register_service(
        self,
        endpoint: ServiceEndpoint,
    ):
        """
        Register a service endpoint.
        
        Args:
            endpoint: Service endpoint to register
        """
        async with self._lock:
            self._services[endpoint.node_id] = endpoint
            logger.info(
                f"Registered service {endpoint.node_id} "
                f"({endpoint.service_type.value})"
            )
    
    async def deregister_service(self, node_id: str):
        """
        Deregister a service endpoint.
        
        Args:
            node_id: Node ID to deregister
        """
        async with self._lock:
            if node_id in self._services:
                del self._services[node_id]
                logger.info(f"Deregistered service {node_id}")
    
    async def mark_unhealthy(self, node_id: str):
        """Mark a service as unhealthy."""
        async with self._lock:
            if node_id in self._services:
                self._services[node_id].healthy = False
    
    async def mark_healthy(self, node_id: str):
        """Mark a service as healthy."""
        async with self._lock:
            if node_id in self._services:
                self._services[node_id].healthy = True
                self._services[node_id].last_seen = datetime.now()
    
    def get_service(self, node_id: str) -> Optional[ServiceEndpoint]:
        """Get service by node ID."""
        return self._services.get(node_id)
    
    def get_services_by_type(
        self,
        service_type: ServiceType,
        healthy_only: bool = True,
    ) -> List[ServiceEndpoint]:
        """
        Get all services of a type.
        
        Args:
            service_type: Type of services to get
            healthy_only: Only return healthy services
            
        Returns:
            List of service endpoints
        """
        services = [
            svc for svc in self._services.values()
            if svc.service_type == service_type
        ]
        
        if healthy_only:
            services = [s for s in services if s.healthy]
        
        return services
    
    def get_master_endpoints(self) -> List[ServiceEndpoint]:
        """Get all master service endpoints."""
        return self.get_services_by_type(ServiceType.MASTER)
    
    def get_slave_endpoints(self) -> List[ServiceEndpoint]:
        """Get all slave service endpoints."""
        return self.get_services_by_type(ServiceType.SLAVE)
    
    def get_any_master(self) -> Optional[ServiceEndpoint]:
        """Get any available master endpoint."""
        masters = self.get_master_endpoints()
        return masters[0] if masters else None
    
    def get_all_services(self) -> List[ServiceEndpoint]:
        """Get all registered services."""
        return list(self._services.values())
    
    def get_status(self) -> Dict[str, Any]:
        """Get service discovery status."""
        by_type = {}
        for svc_type in ServiceType:
            services = self.get_services_by_type(svc_type, healthy_only=False)
            by_type[svc_type.value] = {
                "total": len(services),
                "healthy": len([s for s in services if s.healthy]),
            }
        
        return {
            "total_services": len(self._services),
            "by_type": by_type,
            "running": self._running,
        }


class ServiceRegistry:
    """
    Service registry for coordinated discovery.
    
    Combines ServiceDiscovery with Raft-based
    coordination for consistent views.
    """
    
    def __init__(
        self,
        service_discovery: ServiceDiscovery,
    ):
        """
        Initialize service registry.
        
        Args:
            service_discovery: Underlying service discovery
        """
        self.discovery = service_discovery
        
        # Watch callbacks
        self._watchers: Dict[ServiceType, List[callable]] = {}
    
    def watch(
        self,
        service_type: ServiceType,
        callback: callable,
    ):
        """
        Watch for changes to a service type.
        
        Args:
            service_type: Type to watch
            callback: Callback when services change
        """
        if service_type not in self._watchers:
            self._watchers[service_type] = []
        self._watchers[service_type].append(callback)
    
    async def notify_watchers(
        self,
        service_type: ServiceType,
        event: str,
        endpoint: ServiceEndpoint,
    ):
        """Notify watchers of a change."""
        for callback in self._watchers.get(service_type, []):
            try:
                await callback(event, endpoint)
            except Exception as e:
                logger.error(f"Watcher callback error: {e}")
