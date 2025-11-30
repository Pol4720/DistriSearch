"""
Módulo de red para comunicación entre nodos.
Proporciona interfaces abstractas e implementaciones concretas.
"""
from network.network_interface import NetworkInterface
from network.simulated_network import SimulatedNetwork
from network.http_network import HTTPNetwork
from network.message_types import MessageType, Message

__all__ = [
    "NetworkInterface",
    "SimulatedNetwork",
    "HTTPNetwork",
    "MessageType",
    "Message",
]
