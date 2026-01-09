# -*- coding: utf-8 -*-
"""
Bully Algorithm for Leader Election.

A simpler, more deterministic leader election algorithm.
The node with the highest ID always becomes the leader.

Algorithm:
1. When a node needs a leader, it sends ELECTION to all nodes with higher IDs
2. If it receives OK from any higher node, it waits for COORDINATOR
3. If no OK received (timeout), it becomes leader and sends COORDINATOR to all
4. On receiving COORDINATOR, accept that node as leader
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any, Callable, Awaitable, List, Set
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class BullyMessageType(Enum):
    """Types of messages in Bully algorithm."""
    ELECTION = "election"      # "I'm starting an election"
    OK = "ok"                  # "I have higher priority, stand down"
    COORDINATOR = "coordinator"  # "I am the leader"
    HEARTBEAT = "heartbeat"    # Leader heartbeat


@dataclass
class BullyMessage:
    """A message in the Bully algorithm."""
    type: BullyMessageType
    sender_id: str
    timestamp: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "sender_id": self.sender_id,
            "timestamp": self.timestamp,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BullyMessage":
        return cls(
            type=BullyMessageType(data["type"]),
            sender_id=data["sender_id"],
            timestamp=data.get("timestamp", datetime.now().timestamp()),
        )


# Type for sending messages to other nodes
MessageSender = Callable[[str, Dict[str, Any]], Awaitable[Optional[Dict[str, Any]]]]


class BullyElection:
    """
    Bully algorithm implementation for leader election.
    
    Simple and deterministic: highest ID always wins.
    """
    
    def __init__(
        self,
        node_id: str,
        peers: Dict[str, str],  # peer_id -> address
        send_message: MessageSender,
        on_become_leader: Optional[Callable[[], Awaitable[None]]] = None,
        on_leader_change: Optional[Callable[[str], Awaitable[None]]] = None,
        election_timeout: float = 5.0,
        heartbeat_interval: float = 2.0,
    ):
        """
        Initialize Bully election.
        
        Args:
            node_id: This node's unique ID
            peers: Dictionary of peer_id -> address
            send_message: Function to send messages to peers
            on_become_leader: Callback when this node becomes leader
            on_leader_change: Callback when leader changes
            election_timeout: Timeout waiting for OK responses
            heartbeat_interval: Interval for leader heartbeats
        """
        self.node_id = node_id
        self._peers = peers.copy()
        self._send_message = send_message
        self._on_become_leader = on_become_leader
        self._on_leader_change = on_leader_change
        self._election_timeout = election_timeout
        self._heartbeat_interval = heartbeat_interval
        
        # State
        self._leader_id: Optional[str] = None
        self._is_leader = False
        self._election_in_progress = False
        self._last_heartbeat = datetime.now()
        
        # Tasks
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Lock for state changes
        self._lock = asyncio.Lock()
        
        logger.info(f"BullyElection initialized for node {node_id} with peers: {list(peers.keys())}")
    
    @property
    def is_leader(self) -> bool:
        """Check if this node is the leader."""
        return self._is_leader
    
    @property
    def leader_id(self) -> Optional[str]:
        """Get current leader ID."""
        return self._leader_id
    
    def add_peer(self, peer_id: str, address: str):
        """Add a peer node."""
        self._peers[peer_id] = address
        logger.info(f"Added peer {peer_id} at {address}")
    
    def remove_peer(self, peer_id: str):
        """Remove a peer node."""
        self._peers.pop(peer_id, None)
    
    async def start(self):
        """Start the Bully election system."""
        async with self._lock:
            if self._running:
                return
            self._running = True
        
        logger.info(f"Starting Bully election for node {self.node_id}")
        
        # Start leader monitor
        self._monitor_task = asyncio.create_task(self._leader_monitor())
        
        # Start initial election after a short delay
        await asyncio.sleep(1.0)
        await self.start_election()
    
    async def stop(self):
        """Stop the Bully election system."""
        async with self._lock:
            self._running = False
        
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info(f"Bully election stopped for node {self.node_id}")
    
    async def start_election(self):
        """
        Start a new election.
        
        Send ELECTION to all nodes with higher IDs.
        If no OK received, become leader.
        """
        async with self._lock:
            if self._election_in_progress:
                logger.debug("Election already in progress")
                return
            self._election_in_progress = True
        
        try:
            logger.info(f"Node {self.node_id} starting election")
            
            # Find nodes with higher IDs
            higher_nodes = [
                (pid, addr) for pid, addr in self._peers.items()
                if self._compare_ids(pid, self.node_id) > 0
            ]
            
            if not higher_nodes:
                # No higher nodes, we are the leader
                logger.info(f"Node {self.node_id} has highest ID, becoming leader")
                await self._become_leader()
                return
            
            # Send ELECTION to all higher nodes
            logger.info(f"Sending ELECTION to {len(higher_nodes)} higher nodes")
            
            message = BullyMessage(
                type=BullyMessageType.ELECTION,
                sender_id=self.node_id,
                timestamp=datetime.now().timestamp(),
            )
            
            # Send to all higher nodes and wait for any OK
            ok_received = False
            tasks = []
            
            for peer_id, address in higher_nodes:
                task = asyncio.create_task(
                    self._send_election(peer_id, address, message)
                )
                tasks.append(task)
            
            # Wait for responses with timeout
            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=self._election_timeout
                )
                
                for result in results:
                    if isinstance(result, dict) and result.get("type") == "ok":
                        ok_received = True
                        logger.info(f"Received OK from higher node")
                        break
                        
            except asyncio.TimeoutError:
                logger.info("Election timeout - no OK received")
            
            if not ok_received:
                # No higher node responded, we become leader
                logger.info(f"No OK from higher nodes, {self.node_id} becoming leader")
                await self._become_leader()
            else:
                # Wait for COORDINATOR from higher node
                logger.info("Waiting for COORDINATOR from higher node")
                # The monitor task will handle leader timeout
                
        finally:
            async with self._lock:
                self._election_in_progress = False
    
    async def _send_election(
        self,
        peer_id: str,
        address: str,
        message: BullyMessage
    ) -> Optional[Dict[str, Any]]:
        """Send ELECTION message to a peer."""
        try:
            response = await self._send_message(address, {
                "bully_type": message.type.value,
                "bully_data": message.to_dict(),
            })
            return response
        except Exception as e:
            logger.debug(f"Failed to send ELECTION to {peer_id}: {e}")
            return None
    
    async def _become_leader(self):
        """Become the leader and notify all nodes."""
        async with self._lock:
            self._is_leader = True
            self._leader_id = self.node_id
        
        logger.info(f"Node {self.node_id} is now LEADER")
        
        # Notify callback
        if self._on_become_leader:
            try:
                await self._on_become_leader()
            except Exception as e:
                logger.error(f"Error in on_become_leader callback: {e}")
        
        # Send COORDINATOR to all peers
        await self._broadcast_coordinator()
        
        # Start heartbeat task
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
    
    async def _broadcast_coordinator(self):
        """Send COORDINATOR message to all peers."""
        message = BullyMessage(
            type=BullyMessageType.COORDINATOR,
            sender_id=self.node_id,
            timestamp=datetime.now().timestamp(),
        )
        
        tasks = []
        for peer_id, address in self._peers.items():
            task = asyncio.create_task(
                self._send_message(address, {
                    "bully_type": message.type.value,
                    "bully_data": message.to_dict(),
                })
            )
            tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info(f"Sent COORDINATOR to {len(self._peers)} peers")
    
    async def _heartbeat_loop(self):
        """Send periodic heartbeats as leader."""
        try:
            while self._running and self._is_leader:
                await asyncio.sleep(self._heartbeat_interval)
                
                if not self._is_leader:
                    break
                
                message = BullyMessage(
                    type=BullyMessageType.HEARTBEAT,
                    sender_id=self.node_id,
                    timestamp=datetime.now().timestamp(),
                )
                
                tasks = []
                for peer_id, address in self._peers.items():
                    task = asyncio.create_task(
                        self._send_message(address, {
                            "bully_type": message.type.value,
                            "bully_data": message.to_dict(),
                        })
                    )
                    tasks.append(task)
                
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in heartbeat loop: {e}")
    
    async def _leader_monitor(self):
        """Monitor leader health and start election if needed."""
        try:
            while self._running:
                await asyncio.sleep(self._heartbeat_interval)
                
                if self._is_leader:
                    continue
                
                # Check if we've heard from leader recently
                time_since_heartbeat = (datetime.now() - self._last_heartbeat).total_seconds()
                
                if time_since_heartbeat > self._election_timeout:
                    if self._leader_id:
                        logger.warning(
                            f"Leader {self._leader_id} timeout "
                            f"({time_since_heartbeat:.1f}s), starting election"
                        )
                    else:
                        logger.info("No leader known, starting election")
                    
                    await self.start_election()
                    
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in leader monitor: {e}")
    
    async def handle_message(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming Bully message.
        
        Args:
            data: Message data with bully_type and bully_data
            
        Returns:
            Response message
        """
        bully_type = data.get("bully_type")
        bully_data = data.get("bully_data", {})
        
        if not bully_type:
            return {"error": "Missing bully_type"}
        
        try:
            msg_type = BullyMessageType(bully_type)
            message = BullyMessage.from_dict(bully_data)
        except (ValueError, KeyError) as e:
            return {"error": f"Invalid message: {e}"}
        
        if msg_type == BullyMessageType.ELECTION:
            return await self._handle_election(message)
        elif msg_type == BullyMessageType.COORDINATOR:
            return await self._handle_coordinator(message)
        elif msg_type == BullyMessageType.HEARTBEAT:
            return await self._handle_heartbeat(message)
        elif msg_type == BullyMessageType.OK:
            return {"type": "ack"}
        else:
            return {"error": f"Unknown message type: {msg_type}"}
    
    async def _handle_election(self, message: BullyMessage) -> Dict[str, Any]:
        """
        Handle ELECTION message.
        
        If we have higher ID, send OK and start our own election.
        """
        sender_id = message.sender_id
        
        if self._compare_ids(self.node_id, sender_id) > 0:
            # We have higher ID, send OK and start election
            logger.info(f"Received ELECTION from {sender_id}, sending OK (we have higher ID)")
            
            # Start our own election (async, don't wait)
            asyncio.create_task(self.start_election())
            
            return {"type": "ok", "node_id": self.node_id}
        else:
            # Lower ID, just acknowledge
            return {"type": "ack", "node_id": self.node_id}
    
    async def _handle_coordinator(self, message: BullyMessage) -> Dict[str, Any]:
        """
        Handle COORDINATOR message.
        
        Accept the sender as the new leader.
        """
        sender_id = message.sender_id
        
        async with self._lock:
            old_leader = self._leader_id
            self._leader_id = sender_id
            self._is_leader = (sender_id == self.node_id)
            self._last_heartbeat = datetime.now()
        
        if old_leader != sender_id:
            logger.info(f"New leader: {sender_id}")
            
            if self._on_leader_change:
                try:
                    await self._on_leader_change(sender_id)
                except Exception as e:
                    logger.error(f"Error in on_leader_change callback: {e}")
        
        return {"type": "ack", "node_id": self.node_id}
    
    async def _handle_heartbeat(self, message: BullyMessage) -> Dict[str, Any]:
        """
        Handle HEARTBEAT from leader.
        
        Update last heartbeat time.
        """
        sender_id = message.sender_id
        
        async with self._lock:
            self._last_heartbeat = datetime.now()
            
            if self._leader_id != sender_id:
                # Leader changed
                self._leader_id = sender_id
                self._is_leader = False
                logger.info(f"Heartbeat from new leader: {sender_id}")
        
        return {"type": "ack", "node_id": self.node_id}
    
    def _compare_ids(self, id1: str, id2: str) -> int:
        """
        Compare two node IDs for priority.
        
        Higher ID = higher priority.
        Returns: positive if id1 > id2, negative if id1 < id2, 0 if equal
        """
        # Extract numeric part if present (e.g., "node-3" -> 3)
        def extract_number(node_id: str) -> int:
            try:
                # Try to extract number from end of ID
                parts = node_id.replace("-", " ").replace("_", " ").split()
                for part in reversed(parts):
                    if part.isdigit():
                        return int(part)
                # Fallback to hash
                return hash(node_id)
            except:
                return hash(node_id)
        
        num1 = extract_number(id1)
        num2 = extract_number(id2)
        
        return num1 - num2
    
    def get_status(self) -> Dict[str, Any]:
        """Get election status."""
        return {
            "node_id": self.node_id,
            "is_leader": self._is_leader,
            "leader_id": self._leader_id,
            "peers": list(self._peers.keys()),
            "election_in_progress": self._election_in_progress,
            "time_since_heartbeat": (datetime.now() - self._last_heartbeat).total_seconds(),
        }
