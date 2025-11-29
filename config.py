"""
Configuración del sistema DistriSearch.
"""

# Configuración del hipercubo
HYPERCUBE_DIMENSIONS = 20  # Bits del ID (2^20 = ~1M nodos posibles)

# Configuración de red
NETWORK_MODE = "simulated"  # "simulated" o "http"
SIMULATED_LATENCY_MS = 10
SIMULATED_FAILURE_RATE = 0.0

# Configuración de elección de líder
ELECTION_TIMEOUT = 3.0  # segundos
ELECTION_ALGORITHM = "bully"  # Por ahora solo bully

# Configuración del Data Balancer
HEARTBEAT_INTERVAL = 2.0  # segundos
HEARTBEAT_TIMEOUT = 6.0  # segundos
SNAPSHOT_INTERVAL = 30.0  # segundos

# Configuración de almacenamiento
STORAGE_PERSIST = True
STORAGE_BASE_PATH = "data"

# Configuración de logging
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR
LOG_FILE = "distrisearch.log"

# Configuración de búsqueda
SEARCH_TOP_K = 10  # Número de resultados por defecto
SEARCH_MAX_NODES = 10  # Máximo de nodos a consultar

# Configuración HTTP
HTTP_TIMEOUT = 10  # segundos
HTTP_MAX_RETRIES = 3

# Stopwords adicionales (se suman a las por defecto)
CUSTOM_STOPWORDS = set()

# Configuración de ruteo
MAX_HOPS = 32  # Máximo de saltos en ruteo
ROUTING_STRATEGY = "bitflip"  # "bitflip" o "greedy"

import logging
import sys

# Configurar el handler con codificación UTF-8
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
handler.stream.reconfigure(encoding='utf-8')  # Agregar esta línea

logging.basicConfig(
    level=logging.INFO,
    handlers=[handler]
)
