#!/usr/bin/env python3
"""
Configuración para despliegue Standalone de DistriSearch
========================================================

Este módulo proporciona la configuración centralizada para todos los scripts
de test y diagnóstico del sistema standalone.

Arquitectura:
  - Máquina A (192.168.1.11): Node-1 (:8001), Node-2 (:8002)
  - Máquina B (192.168.1.13): Node-3 (:8003)
  - Cada máquina tiene: CoreDNS (:5353), Load Balancer (:443)

Uso:
    from config_standalone import STANDALONE_CONFIG, get_all_node_urls
    
    for node in STANDALONE_CONFIG["nodes"]:
        print(f"{node['id']}: {node['api_url']}")
"""

# ============================================================================
# CONFIGURACIÓN DE MÁQUINAS
# ============================================================================

MACHINE_A_IP = "192.168.61.32"  # richard-VirtualBox (actual)
MACHINE_B_IP = "192.168.61.33"  # abel-VirtualBox (pendiente)

# ============================================================================
# CONFIGURACIÓN DE NODOS
# ============================================================================

STANDALONE_CONFIG = {
    "machines": {
        "A": {
            "ip": MACHINE_A_IP,
            "name": "richard-VirtualBox",
            "load_balancer_port": 443,
            "coredns_port": 5353,
        },
        "B": {
            "ip": MACHINE_B_IP, 
            "name": "abel-VirtualBox",
            "load_balancer_port": 443,
            "coredns_port": 5353,
        }
    },
    "nodes": [
        {
            "id": "node-1",
            "machine": "A",
            "ip": MACHINE_A_IP,
            "api_port": 8001,
            "http_port": 8081,
            "https_port": 4431,
            "api_url": f"http://{MACHINE_A_IP}:8001",
            "frontend_url": f"http://{MACHINE_A_IP}:8081",
        },
        {
            "id": "node-2",
            "machine": "A",
            "ip": MACHINE_A_IP,
            "api_port": 8002,
            "http_port": 8082,
            "https_port": 4432,
            "api_url": f"http://{MACHINE_A_IP}:8002",
            "frontend_url": f"http://{MACHINE_A_IP}:8082",
        },
        {
            "id": "node-3",
            "machine": "B",
            "ip": MACHINE_B_IP,
            "api_port": 8003,
            "http_port": 8083,
            "https_port": 4433,
            "api_url": f"http://{MACHINE_B_IP}:8003",
            "frontend_url": f"http://{MACHINE_B_IP}:8083",
        },
    ],
    "load_balancers": [
        {"machine": "A", "url": f"https://{MACHINE_A_IP}:443"},
        {"machine": "B", "url": f"https://{MACHINE_B_IP}:443"},
    ],
    "default_entry_point": f"https://{MACHINE_A_IP}:443",
}

# ============================================================================
# FUNCIONES DE UTILIDAD
# ============================================================================

def get_all_node_urls():
    """Obtiene todas las URLs de API de los nodos."""
    return [node["api_url"] for node in STANDALONE_CONFIG["nodes"]]

def get_all_node_ports():
    """Obtiene todos los puertos de API."""
    return [node["api_port"] for node in STANDALONE_CONFIG["nodes"]]

def get_nodes_by_machine(machine: str):
    """Obtiene nodos filtrados por máquina (A o B)."""
    return [n for n in STANDALONE_CONFIG["nodes"] if n["machine"] == machine]

def get_node_by_id(node_id: str):
    """Obtiene configuración de un nodo por su ID."""
    for node in STANDALONE_CONFIG["nodes"]:
        if node["id"] == node_id:
            return node
    return None

def get_default_host():
    """Retorna el host por defecto (Load Balancer de Máquina A)."""
    return MACHINE_A_IP

def get_default_ports_string():
    """Retorna los puertos como string separado por comas."""
    return ",".join(str(n["api_port"]) for n in STANDALONE_CONFIG["nodes"])

# ============================================================================
# CONSTANTES ÚTILES
# ============================================================================

# Para scripts que usan --host y --ports
DEFAULT_HOST = MACHINE_A_IP
DEFAULT_PORTS = ["8001", "8002", "8003"]
DEFAULT_PORTS_STRING = ",".join(DEFAULT_PORTS)

# Para scripts que usan --base-url
DEFAULT_BASE_URL = f"http://{MACHINE_A_IP}:8001"
DEFAULT_LB_URL = f"https://{MACHINE_A_IP}:443"

# Puertos individuales
NODE_PORTS = {
    "node-1": 8001,
    "node-2": 8002,
    "node-3": 8003,
}

# ============================================================================
# INFO
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  CONFIGURACIÓN STANDALONE - DistriSearch")
    print("="*60)
    
    print(f"\n  Máquina A ({MACHINE_A_IP}):")
    for node in get_nodes_by_machine("A"):
        print(f"    - {node['id']}: {node['api_url']}")
    
    print(f"\n  Máquina B ({MACHINE_B_IP}):")
    for node in get_nodes_by_machine("B"):
        print(f"    - {node['id']}: {node['api_url']}")
    
    print(f"\n  Load Balancers:")
    for lb in STANDALONE_CONFIG["load_balancers"]:
        print(f"    - Máquina {lb['machine']}: {lb['url']}")
    
    print(f"\n  Punto de entrada por defecto: {DEFAULT_BASE_URL}")
    print(f"  Via Load Balancer: {DEFAULT_LB_URL}")
    print("\n" + "="*60 + "\n")
