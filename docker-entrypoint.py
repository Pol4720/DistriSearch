"""
Script de entrada para contenedor Docker.
"""
import asyncio
import os
import sys
import logging
from node import DistributedNode
from network import create_network

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    # Leer configuración desde variables de entorno
    node_id = int(os.getenv('NODE_ID', '0'))
    dimensions = int(os.getenv('DIMENSIONS', '20'))
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', '8000'))
    
    # Bootstrap nodes (formato: "host1:port1,host2:port2,...")
    bootstrap_str = os.getenv('BOOTSTRAP_NODES', '')
    bootstrap_nodes = []
    
    if bootstrap_str:
        # Parsear IDs de bootstrap (asumimos que coinciden con NODE_ID)
        # En producción real, necesitaríamos service discovery
        parts = bootstrap_str.split(',')
        for i, part in enumerate(parts):
            bootstrap_nodes.append(i)
    
    logger.info(f"Iniciando nodo {node_id} en {host}:{port}")
    logger.info(f"Dimensiones del hipercubo: {dimensions}")
    logger.info(f"Bootstrap nodes: {bootstrap_nodes}")
    
    # Crear red HTTP
    network = create_network('http')
    
    # Crear nodo
    node = DistributedNode(
        node_id=node_id,
        dimensions=dimensions,
        host=host,
        port=port,
        network=network
    )
    
    # Inicializar
    await node.initialize(bootstrap_nodes=bootstrap_nodes if bootstrap_nodes else None)
    
    # Iniciar servidor HTTP
    await node.start_http_server()
    
    logger.info(f"Nodo {node_id} listo y escuchando en {host}:{port}")
    
    # Mantener activo
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Recibida señal de interrupción")
    finally:
        await node.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nApagado limpio")
        sys.exit(0)
