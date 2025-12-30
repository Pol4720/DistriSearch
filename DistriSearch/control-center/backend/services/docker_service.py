"""
Docker Service - Control de contenedores Docker
"""

import docker
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)


class DockerService:
    """
    Servicio para controlar contenedores Docker del cluster DistriSearch.
    Permite simular fallos, reiniciar nodos, etc.
    """
    
    def __init__(self):
        """Inicializa el cliente Docker."""
        try:
            self.client = docker.from_env()
            self._available = True
            logger.info("DockerService: Conectado al daemon Docker")
        except docker.errors.DockerException as e:
            logger.warning(f"DockerService: Docker no disponible - {e}")
            self.client = None
            self._available = False
    
    @property
    def available(self) -> bool:
        """Indica si Docker está disponible."""
        return self._available
    
    def get_distrisearch_containers(self) -> List[Dict[str, Any]]:
        """
        Obtiene todos los contenedores de DistriSearch.
        
        Returns:
            Lista de contenedores con su información
        """
        if not self._available:
            return []
        
        try:
            containers = self.client.containers.list(all=True)
            distrisearch_containers = []
            
            for container in containers:
                name = container.name.lower()
                # Filtrar contenedores de DistriSearch
                if 'distrisearch' in name or 'master' in name or 'slave' in name:
                    distrisearch_containers.append({
                        "id": container.id[:12],
                        "name": container.name,
                        "status": container.status,
                        "image": container.image.tags[0] if container.image.tags else "unknown",
                        "created": container.attrs.get("Created", ""),
                        "ports": self._parse_ports(container.ports),
                        "is_master": "master" in name.lower(),
                        "is_slave": "slave" in name.lower()
                    })
            
            return distrisearch_containers
            
        except Exception as e:
            logger.error(f"Error obteniendo contenedores: {e}")
            return []
    
    def _parse_ports(self, ports: Dict) -> List[str]:
        """Parsea los puertos del contenedor."""
        result = []
        for port, bindings in ports.items():
            if bindings:
                for binding in bindings:
                    result.append(f"{binding['HostPort']}:{port}")
        return result
    
    async def stop_container(self, container_id_or_name: str) -> Dict[str, Any]:
        """
        Detiene un contenedor (simula fallo de nodo).
        
        Args:
            container_id_or_name: ID o nombre del contenedor
            
        Returns:
            Resultado de la operación
        """
        if not self._available:
            return {"success": False, "error": "Docker no disponible"}
        
        try:
            container = self.client.containers.get(container_id_or_name)
            container.stop(timeout=10)
            
            logger.info(f"Contenedor detenido: {container_id_or_name}")
            
            return {
                "success": True,
                "container_id": container.id[:12],
                "container_name": container.name,
                "action": "stopped",
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except docker.errors.NotFound:
            return {"success": False, "error": f"Contenedor no encontrado: {container_id_or_name}"}
        except Exception as e:
            logger.error(f"Error deteniendo contenedor: {e}")
            return {"success": False, "error": str(e)}
    
    async def start_container(self, container_id_or_name: str) -> Dict[str, Any]:
        """
        Inicia un contenedor (recuperación de nodo).
        
        Args:
            container_id_or_name: ID o nombre del contenedor
            
        Returns:
            Resultado de la operación
        """
        if not self._available:
            return {"success": False, "error": "Docker no disponible"}
        
        try:
            container = self.client.containers.get(container_id_or_name)
            container.start()
            
            logger.info(f"Contenedor iniciado: {container_id_or_name}")
            
            return {
                "success": True,
                "container_id": container.id[:12],
                "container_name": container.name,
                "action": "started",
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except docker.errors.NotFound:
            return {"success": False, "error": f"Contenedor no encontrado: {container_id_or_name}"}
        except Exception as e:
            logger.error(f"Error iniciando contenedor: {e}")
            return {"success": False, "error": str(e)}
    
    async def restart_container(self, container_id_or_name: str) -> Dict[str, Any]:
        """
        Reinicia un contenedor.
        
        Args:
            container_id_or_name: ID o nombre del contenedor
            
        Returns:
            Resultado de la operación
        """
        if not self._available:
            return {"success": False, "error": "Docker no disponible"}
        
        try:
            container = self.client.containers.get(container_id_or_name)
            container.restart(timeout=10)
            
            logger.info(f"Contenedor reiniciado: {container_id_or_name}")
            
            return {
                "success": True,
                "container_id": container.id[:12],
                "container_name": container.name,
                "action": "restarted",
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except docker.errors.NotFound:
            return {"success": False, "error": f"Contenedor no encontrado: {container_id_or_name}"}
        except Exception as e:
            logger.error(f"Error reiniciando contenedor: {e}")
            return {"success": False, "error": str(e)}
    
    async def kill_container(self, container_id_or_name: str, signal: str = "SIGKILL") -> Dict[str, Any]:
        """
        Mata un contenedor bruscamente (simula fallo catastrófico).
        
        Args:
            container_id_or_name: ID o nombre del contenedor
            signal: Señal a enviar (default: SIGKILL)
            
        Returns:
            Resultado de la operación
        """
        if not self._available:
            return {"success": False, "error": "Docker no disponible"}
        
        try:
            container = self.client.containers.get(container_id_or_name)
            container.kill(signal=signal)
            
            logger.warning(f"Contenedor terminado con {signal}: {container_id_or_name}")
            
            return {
                "success": True,
                "container_id": container.id[:12],
                "container_name": container.name,
                "action": "killed",
                "signal": signal,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except docker.errors.NotFound:
            return {"success": False, "error": f"Contenedor no encontrado: {container_id_or_name}"}
        except Exception as e:
            logger.error(f"Error matando contenedor: {e}")
            return {"success": False, "error": str(e)}
    
    async def pause_container(self, container_id_or_name: str) -> Dict[str, Any]:
        """
        Pausa un contenedor (simula partición de red).
        
        Args:
            container_id_or_name: ID o nombre del contenedor
            
        Returns:
            Resultado de la operación
        """
        if not self._available:
            return {"success": False, "error": "Docker no disponible"}
        
        try:
            container = self.client.containers.get(container_id_or_name)
            container.pause()
            
            logger.info(f"Contenedor pausado: {container_id_or_name}")
            
            return {
                "success": True,
                "container_id": container.id[:12],
                "container_name": container.name,
                "action": "paused",
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except docker.errors.NotFound:
            return {"success": False, "error": f"Contenedor no encontrado: {container_id_or_name}"}
        except Exception as e:
            logger.error(f"Error pausando contenedor: {e}")
            return {"success": False, "error": str(e)}
    
    async def unpause_container(self, container_id_or_name: str) -> Dict[str, Any]:
        """
        Reanuda un contenedor pausado.
        
        Args:
            container_id_or_name: ID o nombre del contenedor
            
        Returns:
            Resultado de la operación
        """
        if not self._available:
            return {"success": False, "error": "Docker no disponible"}
        
        try:
            container = self.client.containers.get(container_id_or_name)
            container.unpause()
            
            logger.info(f"Contenedor reanudado: {container_id_or_name}")
            
            return {
                "success": True,
                "container_id": container.id[:12],
                "container_name": container.name,
                "action": "unpaused",
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except docker.errors.NotFound:
            return {"success": False, "error": f"Contenedor no encontrado: {container_id_or_name}"}
        except Exception as e:
            logger.error(f"Error reanudando contenedor: {e}")
            return {"success": False, "error": str(e)}
    
    def get_container_stats(self, container_id_or_name: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene estadísticas de un contenedor.
        
        Args:
            container_id_or_name: ID o nombre del contenedor
            
        Returns:
            Estadísticas del contenedor
        """
        if not self._available:
            return None
        
        try:
            container = self.client.containers.get(container_id_or_name)
            stats = container.stats(stream=False)
            
            # Calcular uso de CPU
            cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                       stats['precpu_stats']['cpu_usage']['total_usage']
            system_delta = stats['cpu_stats']['system_cpu_usage'] - \
                          stats['precpu_stats']['system_cpu_usage']
            cpu_usage = (cpu_delta / system_delta) * 100 if system_delta > 0 else 0
            
            # Calcular uso de memoria
            memory_usage = stats['memory_stats'].get('usage', 0)
            memory_limit = stats['memory_stats'].get('limit', 1)
            memory_percent = (memory_usage / memory_limit) * 100 if memory_limit > 0 else 0
            
            return {
                "container_id": container.id[:12],
                "container_name": container.name,
                "status": container.status,
                "cpu_percent": round(cpu_usage, 2),
                "memory_usage_mb": round(memory_usage / (1024 * 1024), 2),
                "memory_limit_mb": round(memory_limit / (1024 * 1024), 2),
                "memory_percent": round(memory_percent, 2),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except docker.errors.NotFound:
            return None
        except Exception as e:
            logger.error(f"Error obteniendo stats: {e}")
            return None
    
    def get_container_logs(self, container_id_or_name: str, tail: int = 100) -> Optional[str]:
        """
        Obtiene los logs de un contenedor.
        
        Args:
            container_id_or_name: ID o nombre del contenedor
            tail: Número de líneas a obtener
            
        Returns:
            Logs del contenedor
        """
        if not self._available:
            return None
        
        try:
            container = self.client.containers.get(container_id_or_name)
            logs = container.logs(tail=tail, timestamps=True).decode('utf-8')
            return logs
            
        except docker.errors.NotFound:
            return None
        except Exception as e:
            logger.error(f"Error obteniendo logs: {e}")
            return None
