"""
Docker Service - Control de contenedores Docker
Usa subprocess como método principal para mayor compatibilidad
"""

import subprocess
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


class DockerService:
    """
    Servicio para controlar contenedores Docker del cluster DistriSearch.
    Usa subprocess para ejecutar comandos docker directamente.
    """
    
    def __init__(self):
        """Inicializa el servicio Docker."""
        self._available = self._check_docker_available()
        if self._available:
            logger.info("DockerService: Docker disponible via CLI")
        else:
            logger.warning("DockerService: Docker no disponible")
    
    def _check_docker_available(self) -> bool:
        """Verifica si Docker está disponible."""
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception as e:
            logger.warning(f"Docker check failed: {e}")
            return False
    
    @property
    def available(self) -> bool:
        """Indica si Docker está disponible."""
        return self._available
    
    def _run_docker_command(self, args: List[str], timeout: int = 30) -> tuple:
        """Ejecuta un comando docker y retorna (success, output, error)."""
        try:
            result = subprocess.run(
                ["docker"] + args,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Timeout"
        except Exception as e:
            return False, "", str(e)
    
    def get_distrisearch_containers(self) -> List[Dict[str, Any]]:
        """Obtiene todos los contenedores de DistriSearch."""
        if not self._available:
            return []
        
        try:
            success, output, _ = self._run_docker_command([
                "ps", "-a", "--format", 
                '{"id":"{{.ID}}","name":"{{.Names}}","status":"{{.Status}}","image":"{{.Image}}","ports":"{{.Ports}}"}'
            ])
            
            if not success:
                return []
            
            containers = []
            for line in output.strip().split('\n'):
                if line:
                    try:
                        c = json.loads(line)
                        name = c.get("name", "").lower()
                        if 'distrisearch' in name or 'master' in name or 'slave' in name or 'mongo' in name or 'redis' in name:
                            # Determinar estado
                            status_str = c.get("status", "").lower()
                            if "up" in status_str:
                                state = "running"
                            elif "exited" in status_str:
                                state = "exited"
                            else:
                                state = "unknown"
                            
                            containers.append({
                                "id": c.get("id", "")[:12],
                                "name": c.get("name", ""),
                                "status": state,
                                "status_text": c.get("status", ""),
                                "image": c.get("image", ""),
                                "ports": c.get("ports", "").split(", ") if c.get("ports") else [],
                                "is_master": "master" in name,
                                "is_slave": "slave" in name,
                                "is_db": "mongo" in name or "redis" in name
                            })
                    except json.JSONDecodeError:
                        continue
            
            return containers
            
        except Exception as e:
            logger.error(f"Error obteniendo contenedores: {e}")
            return []
    
    async def stop_container(self, container_id_or_name: str) -> Dict[str, Any]:
        """Detiene un contenedor (simula fallo de nodo)."""
        if not self._available:
            return {"success": False, "error": "Docker no disponible"}
        
        success, _, error = self._run_docker_command(["stop", container_id_or_name], timeout=15)
        
        if success:
            logger.info(f"Contenedor detenido: {container_id_or_name}")
            return {
                "success": True,
                "container_name": container_id_or_name,
                "action": "stopped",
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            return {"success": False, "error": error}
    
    async def start_container(self, container_id_or_name: str) -> Dict[str, Any]:
        """Inicia un contenedor (recuperación de nodo)."""
        if not self._available:
            return {"success": False, "error": "Docker no disponible"}
        
        success, _, error = self._run_docker_command(["start", container_id_or_name], timeout=15)
        
        if success:
            logger.info(f"Contenedor iniciado: {container_id_or_name}")
            return {
                "success": True,
                "container_name": container_id_or_name,
                "action": "started",
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            return {"success": False, "error": error}
    
    async def restart_container(self, container_id_or_name: str) -> Dict[str, Any]:
        """Reinicia un contenedor."""
        if not self._available:
            return {"success": False, "error": "Docker no disponible"}
        
        success, _, error = self._run_docker_command(["restart", container_id_or_name], timeout=30)
        
        if success:
            logger.info(f"Contenedor reiniciado: {container_id_or_name}")
            return {
                "success": True,
                "container_name": container_id_or_name,
                "action": "restarted",
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            return {"success": False, "error": error}
    
    async def kill_container(self, container_id_or_name: str) -> Dict[str, Any]:
        """Mata un contenedor inmediatamente (simula crash)."""
        if not self._available:
            return {"success": False, "error": "Docker no disponible"}
        
        success, _, error = self._run_docker_command(["kill", container_id_or_name], timeout=10)
        
        if success:
            logger.info(f"Contenedor terminado: {container_id_or_name}")
            return {
                "success": True,
                "container_name": container_id_or_name,
                "action": "killed",
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            return {"success": False, "error": error}
    
    async def pause_container(self, container_id_or_name: str) -> Dict[str, Any]:
        """Pausa un contenedor (simula partición de red)."""
        if not self._available:
            return {"success": False, "error": "Docker no disponible"}
        
        success, _, error = self._run_docker_command(["pause", container_id_or_name], timeout=10)
        
        if success:
            logger.info(f"Contenedor pausado: {container_id_or_name}")
            return {
                "success": True,
                "container_name": container_id_or_name,
                "action": "paused",
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            return {"success": False, "error": error}
    
    async def unpause_container(self, container_id_or_name: str) -> Dict[str, Any]:
        """Reanuda un contenedor pausado."""
        if not self._available:
            return {"success": False, "error": "Docker no disponible"}
        
        success, _, error = self._run_docker_command(["unpause", container_id_or_name], timeout=10)
        
        if success:
            logger.info(f"Contenedor reanudado: {container_id_or_name}")
            return {
                "success": True,
                "container_name": container_id_or_name,
                "action": "unpaused",
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            return {"success": False, "error": error}
    
    async def get_container_stats(self, container_id_or_name: str) -> Dict[str, Any]:
        """Obtiene estadísticas de un contenedor."""
        if not self._available:
            return {"error": "Docker no disponible"}
        
        success, output, _ = self._run_docker_command([
            "stats", container_id_or_name, "--no-stream", "--format",
            '{"cpu":"{{.CPUPerc}}","memory":"{{.MemUsage}}","mem_perc":"{{.MemPerc}}"}'
        ], timeout=10)
        
        if success and output.strip():
            try:
                stats = json.loads(output.strip())
                return {
                    "container": container_id_or_name,
                    "cpu_percent": stats.get("cpu", "0%").replace("%", ""),
                    "memory_usage": stats.get("memory", "0MiB / 0MiB"),
                    "memory_percent": stats.get("mem_perc", "0%").replace("%", "")
                }
            except:
                pass
        
        return {"error": "No stats available"}
    
    async def get_container_logs(self, container_id_or_name: str, tail: int = 50) -> Dict[str, Any]:
        """Obtiene los logs de un contenedor."""
        if not self._available:
            return {"error": "Docker no disponible"}
        
        success, output, error = self._run_docker_command([
            "logs", container_id_or_name, "--tail", str(tail)
        ], timeout=10)
        
        if success:
            return {
                "container": container_id_or_name,
                "logs": output + error,  # logs pueden ir a stderr
                "lines": tail
            }
        else:
            return {"error": error}


# Instancia global
docker_service = DockerService()
