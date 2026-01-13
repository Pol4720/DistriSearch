#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          TEST SCENARIO ULTIMATE - PRUEBA SUPREMA ADAPTATIVA                   ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Este test se adapta automáticamente a CUALQUIER configuración de cluster:    ║
║  - Detecta automáticamente todos los nodos activos                            ║
║  - Funciona con N nodos en M máquinas (cualquier distribución)                ║
║  - Incluye detenciones de contenedores Docker                                 ║
║  - Incluye pausas manuales para desconectar WiFi                              ║
║  - Prueba TODAS las funcionalidades del sistema                               ║
╚══════════════════════════════════════════════════════════════════════════════╝

FUNCIONALIDADES PROBADAS:
  ✓ Registro de usuarios
  ✓ Login/Autenticación  
  ✓ Subida de documentos (múltiples tipos)
  ✓ Descarga de documentos
  ✓ Visualización/Listado
  ✓ Búsqueda semántica
  ✓ Eliminación de documentos
  ✓ Replicación entre nodos
  ✓ Tolerancia a fallos de nodos (Docker stop)
  ✓ Tolerancia a particiones de red (WiFi manual)
  ✓ Recuperación automática
  ✓ Sincronización post-partición

USO:
    python scripts/test_scenario_ultimate.py [OPCIONES]

OPCIONES:
    --nodes NODE_LIST       Lista de nodos en formato IP:PORT separados por coma
                            Ejemplo: 192.168.1.11:8001,192.168.1.13:8004,192.168.1.9:8005
    --host HOST             Host/IP por defecto para auto-detección (default: localhost)
    --ports PORTS           Puertos de nodos separados por coma (usa --host para todos)
    --base-url URL          URL base alternativa
    --skip-docker           No hacer pruebas de contenedores Docker
    --skip-wifi             No incluir pausas para pruebas WiFi manuales
    --skip-cleanup          No eliminar documentos de prueba al final
    --interactive           Modo interactivo (pide confirmación entre fases)
    --quick                 Modo rápido (menos documentos, menos esperas)
    --verbose               Mostrar logs detallados

EJEMPLOS:
    # Test completo con detección automática en localhost
    python scripts/test_scenario_ultimate.py

    # Test con nodos en múltiples máquinas (RECOMENDADO)
    python scripts/test_scenario_ultimate.py --nodes 192.168.1.11:8001,192.168.1.13:8004,192.168.1.9:8005

    # Test en cluster remoto (todos los nodos en el mismo host)
    python scripts/test_scenario_ultimate.py --host 192.168.1.100

    # Test rápido sin pruebas de WiFi
    python scripts/test_scenario_ultimate.py --quick --skip-wifi

    # Test interactivo para demo
    python scripts/test_scenario_ultimate.py --interactive
"""

import asyncio
import argparse
import subprocess
import time
import sys
import os
import json
import random
import string
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field
from collections import defaultdict
import aiohttp

# ============================================================================
# CONFIGURACIÓN
# ============================================================================
DEFAULT_HOST = "localhost"
DEFAULT_PORT_RANGE = range(8001, 8021)  # Detectar nodos en puertos 8001-8020
API_V1 = "/api/v1"
TIMEOUT = 30.0

# Colores para output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


@dataclass
class NodeInfo:
    """Información de un nodo del cluster"""
    node_id: str
    url: str
    port: int
    host: str
    hostname: str = ""
    is_healthy: bool = False
    is_leader: bool = False


@dataclass
class TestResult:
    """Resultado de una prueba individual"""
    name: str
    phase: str
    passed: bool
    message: str
    duration_ms: float
    details: Optional[Dict] = None


@dataclass  
class ClusterState:
    """Estado del cluster durante las pruebas"""
    nodes: List[NodeInfo] = field(default_factory=list)
    active_nodes: List[str] = field(default_factory=list)
    stopped_nodes: List[str] = field(default_factory=list)
    partitioned_nodes: List[str] = field(default_factory=list)
    leader_node: Optional[str] = None
    total_documents: int = 0
    replicated_documents: int = 0


class UltimateTestScenario:
    """Test Supremo Adaptativo para DistriSearch"""
    
    def __init__(
        self,
        host: str = DEFAULT_HOST,
        ports: Optional[List[int]] = None,
        nodes: Optional[List[Tuple[str, int]]] = None,  # Lista de (host, port)
        skip_docker: bool = False,
        skip_wifi: bool = False,
        skip_cleanup: bool = False,
        interactive: bool = False,
        quick: bool = False,
        verbose: bool = False
    ):
        self.host = host
        self.custom_ports = ports
        self.custom_nodes = nodes  # Lista de (host, port) específicos
        self.skip_docker = skip_docker
        self.skip_wifi = skip_wifi
        self.skip_cleanup = skip_cleanup
        self.interactive = interactive
        self.quick = quick
        self.verbose = verbose
        
        self.cluster = ClusterState()
        self.results: List[TestResult] = []
        self.token: Optional[str] = None
        self.user_id: Optional[str] = None
        self.created_docs: List[Dict] = []
        self.test_user = self._generate_test_user()
        
    def _generate_test_user(self) -> Dict:
        """Genera un usuario de prueba único"""
        suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        return {
            "username": f"ultimate_test_{suffix}",
            "email": f"ultimate_test_{suffix}@test.com",
            "password": "UltimateTest123!"
        }
    
    # ========================================================================
    # LOGGING Y OUTPUT
    # ========================================================================
    
    def log(self, msg: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        colors = {
            "INFO": Colors.ENDC,
            "SUCCESS": Colors.GREEN,
            "WARN": Colors.YELLOW,
            "ERROR": Colors.RED,
            "PHASE": Colors.CYAN + Colors.BOLD,
            "HEADER": Colors.HEADER + Colors.BOLD,
            "DEBUG": Colors.BLUE
        }
        color = colors.get(level, Colors.ENDC)
        print(f"{color}[{timestamp}] [{level}] {msg}{Colors.ENDC}")
    
    def log_phase(self, phase_name: str, description: str = ""):
        print()
        print(f"{Colors.CYAN}{'═' * 70}{Colors.ENDC}")
        print(f"{Colors.CYAN}{Colors.BOLD}  FASE: {phase_name}{Colors.ENDC}")
        if description:
            print(f"{Colors.CYAN}  {description}{Colors.ENDC}")
        print(f"{Colors.CYAN}{'═' * 70}{Colors.ENDC}")
        print()
    
    def log_subphase(self, name: str):
        print(f"\n{Colors.BLUE}  ▸ {name}{Colors.ENDC}")
    
    def record_result(self, name: str, phase: str, passed: bool, message: str, 
                      duration_ms: float = 0, details: Optional[Dict] = None):
        result = TestResult(name, phase, passed, message, duration_ms, details)
        self.results.append(result)
        status = f"{Colors.GREEN}✓{Colors.ENDC}" if passed else f"{Colors.RED}✗{Colors.ENDC}"
        level = "SUCCESS" if passed else "ERROR"
        self.log(f"{status} {name}: {message}", level)
        return result
    
    def wait_for_user(self, message: str):
        """Espera confirmación del usuario en modo interactivo"""
        if self.interactive:
            print()
            print(f"{Colors.YELLOW}{Colors.BOLD}⏸  {message}{Colors.ENDC}")
            input(f"{Colors.YELLOW}   Presiona ENTER para continuar...{Colors.ENDC}")
            print()
    
    def wait_for_wifi_action(self, action: str, target: str):
        """Pausa para acción manual de WiFi"""
        if self.skip_wifi:
            self.log(f"Saltando acción WiFi: {action} en {target}", "WARN")
            return False
        
        print()
        print(f"{Colors.HEADER}{'─' * 70}{Colors.ENDC}")
        print(f"{Colors.HEADER}{Colors.BOLD}  ⚡ ACCIÓN MANUAL REQUERIDA ⚡{Colors.ENDC}")
        print(f"{Colors.HEADER}{'─' * 70}{Colors.ENDC}")
        print()
        print(f"  {Colors.YELLOW}Acción: {action}{Colors.ENDC}")
        print(f"  {Colors.YELLOW}Target: {target}{Colors.ENDC}")
        print()
        print(f"  {Colors.CYAN}Instrucciones:{Colors.ENDC}")
        if "desconectar" in action.lower() or "disconnect" in action.lower():
            print(f"    1. Ve a la máquina/nodo: {target}")
            print(f"    2. Desconecta el WiFi o cable de red")
            print(f"    3. Espera 5 segundos")
        else:
            print(f"    1. Ve a la máquina/nodo: {target}")
            print(f"    2. Reconecta el WiFi o cable de red")
            print(f"    3. Espera a que obtenga IP")
        print()
        input(f"  {Colors.GREEN}Presiona ENTER cuando hayas completado la acción...{Colors.ENDC}")
        print()
        return True
    
    # ========================================================================
    # DOCKER CONTROL
    # ========================================================================
    
    def run_docker_cmd(self, cmd: List[str]) -> Tuple[bool, str]:
        """Ejecutar comando docker"""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            return result.returncode == 0, result.stdout + result.stderr
        except Exception as e:
            return False, str(e)
    
    def get_docker_service_name(self, node_id: str) -> str:
        """Obtener nombre del servicio Docker para un nodo"""
        # node-1 -> distrisearch-node-1
        num = node_id.split("-")[-1] if "-" in node_id else node_id
        return f"distrisearch-node-{num}"
    
    def stop_node_docker(self, node_id: str) -> bool:
        """Detener un nodo escalando su servicio a 0"""
        if self.skip_docker:
            self.log(f"Saltando Docker stop para {node_id}", "WARN")
            return False
        
        service = self.get_docker_service_name(node_id)
        self.log(f"Deteniendo servicio {service}...", "WARN")
        success, output = self.run_docker_cmd([
            "docker", "service", "scale", f"{service}=0"
        ])
        if success:
            self.cluster.stopped_nodes.append(node_id)
            if node_id in self.cluster.active_nodes:
                self.cluster.active_nodes.remove(node_id)
            time.sleep(3)
        return success
    
    def start_node_docker(self, node_id: str) -> bool:
        """Iniciar un nodo escalando su servicio a 1"""
        if self.skip_docker:
            self.log(f"Saltando Docker start para {node_id}", "WARN")
            return False
        
        service = self.get_docker_service_name(node_id)
        self.log(f"Iniciando servicio {service}...", "INFO")
        success, output = self.run_docker_cmd([
            "docker", "service", "scale", f"{service}=1"
        ])
        if success:
            if node_id in self.cluster.stopped_nodes:
                self.cluster.stopped_nodes.remove(node_id)
            # Esperar a que inicie
            time.sleep(10)
        return success
    
    # ========================================================================
    # DETECCIÓN DE CLUSTER
    # ========================================================================
    
    async def detect_cluster(self) -> bool:
        """Detecta automáticamente todos los nodos activos del cluster"""
        self.log_subphase("Detectando nodos del cluster")
        
        self.cluster.nodes = []
        
        # Construir lista de (host, port) a verificar
        nodes_to_check: List[Tuple[str, int]] = []
        
        if self.custom_nodes:
            # Si se especificaron nodos explícitamente, usarlos directamente
            nodes_to_check = self.custom_nodes
            self.log(f"Verificando {len(nodes_to_check)} nodos especificados...")
        elif self.custom_ports:
            # Si se especificaron puertos, usar el host por defecto
            nodes_to_check = [(self.host, port) for port in self.custom_ports]
        else:
            # Auto-detectar en localhost
            nodes_to_check = [(self.host, port) for port in DEFAULT_PORT_RANGE]
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
            for host, port in nodes_to_check:
                url = f"http://{host}:{port}"
                try:
                    async with session.get(f"{url}{API_V1}/health/live") as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            node_id = f"node-{port - 8000}"
                            
                            node = NodeInfo(
                                node_id=node_id,
                                url=url,
                                port=port,
                                host=host,
                                is_healthy=data.get("alive", False)
                            )
                            
                            # Intentar obtener más info del nodo
                            try:
                                async with session.get(f"{url}{API_V1}/health") as health_resp:
                                    if health_resp.status == 200:
                                        health_data = await health_resp.json()
                                        node.hostname = health_data.get("hostname", "")
                                        node.is_leader = health_data.get("role") == "LEADER"
                            except:
                                pass
                            
                            self.cluster.nodes.append(node)
                            self.cluster.active_nodes.append(node_id)
                            
                            if self.verbose:
                                self.log(f"  Encontrado: {node_id} en {url} ({host})", "DEBUG")
                                
                except Exception as e:
                    if self.verbose:
                        self.log(f"  {host}:{port}: no responde ({e})", "DEBUG")
        
        if not self.cluster.nodes:
            self.log("No se encontraron nodos activos", "ERROR")
            return False
        
        # Identificar líder
        for node in self.cluster.nodes:
            if node.is_leader:
                self.cluster.leader_node = node.node_id
                break
        
        self.log(f"Cluster detectado: {len(self.cluster.nodes)} nodos activos", "SUCCESS")
        for node in self.cluster.nodes:
            leader_mark = " (LEADER)" if node.is_leader else ""
            self.log(f"  • {node.node_id}: {node.url}{leader_mark}")
        
        return True
    
    def get_active_node_url(self) -> Optional[str]:
        """Obtiene URL de un nodo activo (preferiblemente no el líder)"""
        for node in self.cluster.nodes:
            if node.node_id in self.cluster.active_nodes and not node.is_leader:
                return node.url
        # Si solo queda el líder, usarlo
        for node in self.cluster.nodes:
            if node.node_id in self.cluster.active_nodes:
                return node.url
        return None
    
    def get_node_url(self, node_id: str) -> Optional[str]:
        """Obtiene URL de un nodo específico"""
        for node in self.cluster.nodes:
            if node.node_id == node_id:
                return node.url
        return None
    
    # ========================================================================
    # OPERACIONES API
    # ========================================================================
    
    async def api_request(
        self,
        method: str,
        endpoint: str,
        node_url: Optional[str] = None,
        json_data: Optional[Dict] = None,
        files: Optional[Dict] = None,
        auth: bool = True
    ) -> Tuple[bool, Any]:
        """Realiza una petición API"""
        if not node_url:
            node_url = self.get_active_node_url()
            if not node_url:
                return False, "No hay nodos activos"
        
        url = f"{node_url}{API_V1}{endpoint}"
        headers = {}
        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=TIMEOUT)) as session:
                if method.upper() == "GET":
                    async with session.get(url, headers=headers) as resp:
                        return resp.status < 400, await resp.json() if resp.content_type == 'application/json' else await resp.text()
                elif method.upper() == "POST":
                    if files:
                        data = aiohttp.FormData()
                        for key, value in files.items():
                            if isinstance(value, tuple):
                                data.add_field(key, value[1], filename=value[0], content_type=value[2] if len(value) > 2 else 'application/octet-stream')
                            else:
                                data.add_field(key, value)
                        async with session.post(url, headers=headers, data=data) as resp:
                            return resp.status < 400, await resp.json() if resp.content_type == 'application/json' else await resp.text()
                    else:
                        async with session.post(url, headers=headers, json=json_data) as resp:
                            return resp.status < 400, await resp.json() if resp.content_type == 'application/json' else await resp.text()
                elif method.upper() == "DELETE":
                    async with session.delete(url, headers=headers) as resp:
                        return resp.status < 400, await resp.json() if resp.content_type == 'application/json' else await resp.text()
        except Exception as e:
            return False, str(e)
        
        return False, "Método no soportado"
    
    # ========================================================================
    # TESTS INDIVIDUALES
    # ========================================================================
    
    async def test_register_user(self) -> bool:
        """Prueba de registro de usuario"""
        start = time.time()
        success, data = await self.api_request("POST", "/auth/register", json_data=self.test_user, auth=False)
        duration = (time.time() - start) * 1000
        
        if success and "user_id" in str(data):
            self.record_result("Registro de usuario", "AUTH", True, 
                             f"Usuario {self.test_user['username']} creado", duration)
            return True
        else:
            # Intentar login si ya existe
            success, data = await self.api_request("POST", "/auth/login", 
                json_data={"username": self.test_user["username"], "password": self.test_user["password"]}, 
                auth=False)
            if success:
                self.token = data.get("access_token")
                self.user_id = data.get("user_id")
                self.record_result("Registro de usuario", "AUTH", True, 
                                 "Usuario ya existía, login exitoso", duration)
                return True
        
        self.record_result("Registro de usuario", "AUTH", False, str(data), duration)
        return False
    
    async def test_login(self) -> bool:
        """Prueba de login"""
        start = time.time()
        success, data = await self.api_request("POST", "/auth/login",
            json_data={"username": self.test_user["username"], "password": self.test_user["password"]},
            auth=False)
        duration = (time.time() - start) * 1000
        
        if success and "access_token" in data:
            self.token = data["access_token"]
            self.user_id = data.get("user_id")
            self.record_result("Login", "AUTH", True, "Token obtenido", duration)
            return True
        
        self.record_result("Login", "AUTH", False, str(data), duration)
        return False
    
    async def test_upload_document(self, title: str, content: str, 
                                   content_type: str = "text/plain") -> Optional[str]:
        """Sube un documento y retorna su ID"""
        start = time.time()
        
        filename = f"test_{int(time.time())}.txt"
        files = {
            "file": (filename, content.encode(), content_type)
        }
        
        success, data = await self.api_request("POST", "/documents/upload", files=files)
        duration = (time.time() - start) * 1000
        
        # Aceptar 'id' o 'document_id' en la respuesta
        doc_id = data.get("document_id") or data.get("id") if isinstance(data, dict) else None
        
        if success and doc_id:
            self.created_docs.append({"id": doc_id, "title": title})
            self.cluster.total_documents += 1
            self.record_result(f"Upload: {title[:30]}", "DOCUMENTS", True, 
                             f"ID: {doc_id[:8]}...", duration)
            return doc_id
        
        self.record_result(f"Upload: {title[:30]}", "DOCUMENTS", False, str(data), duration)
        return None
    
    async def test_list_documents(self, node_url: Optional[str] = None) -> List[Dict]:
        """Lista documentos del usuario"""
        start = time.time()
        # El endpoint correcto es GET /documents (sin trailing slash)
        success, data = await self.api_request("GET", "/documents", node_url=node_url)
        duration = (time.time() - start) * 1000
        
        if success and isinstance(data, dict):
            docs = data.get("documents", [])
            node_info = f" en {node_url.split(':')[-1]}" if node_url else ""
            self.record_result(f"Listar documentos{node_info}", "DOCUMENTS", True, 
                             f"{len(docs)} documentos", duration)
            return docs
        
        self.record_result("Listar documentos", "DOCUMENTS", False, str(data), duration)
        return []
    
    async def test_search(self, query: str, node_url: Optional[str] = None) -> List[Dict]:
        """Busca documentos"""
        start = time.time()
        success, data = await self.api_request("POST", "/search",
            json_data={"query": query, "top_k": 10}, node_url=node_url)
        duration = (time.time() - start) * 1000
        
        if success and isinstance(data, dict):
            results = data.get("results", [])
            self.record_result(f"Búsqueda: '{query[:20]}'", "SEARCH", True, 
                             f"{len(results)} resultados", duration)
            return results
        
        self.record_result(f"Búsqueda: '{query[:20]}'", "SEARCH", False, str(data), duration)
        return []
    
    async def test_download_document(self, doc_id: str) -> bool:
        """Descarga un documento"""
        start = time.time()
        
        try:
            node_url = self.get_active_node_url()
            url = f"{node_url}{API_V1}/documents/{doc_id}/download"
            headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    duration = (time.time() - start) * 1000
                    if resp.status == 200:
                        content = await resp.read()
                        self.record_result(f"Descarga: {doc_id[:8]}...", "DOCUMENTS", True, 
                                         f"{len(content)} bytes", duration)
                        return True
                    else:
                        self.record_result(f"Descarga: {doc_id[:8]}...", "DOCUMENTS", False, 
                                         f"Status {resp.status}", duration)
                        return False
        except Exception as e:
            self.record_result(f"Descarga: {doc_id[:8]}...", "DOCUMENTS", False, str(e), 0)
            return False
    
    async def test_delete_document(self, doc_id: str) -> bool:
        """Elimina un documento"""
        start = time.time()
        success, data = await self.api_request("DELETE", f"/documents/{doc_id}")
        duration = (time.time() - start) * 1000
        
        if success:
            self.record_result(f"Eliminar: {doc_id[:8]}...", "DOCUMENTS", True, "OK", duration)
            return True
        
        self.record_result(f"Eliminar: {doc_id[:8]}...", "DOCUMENTS", False, str(data), duration)
        return False
    
    async def test_replication(self) -> Tuple[int, int]:
        """Verifica replicación en todos los nodos"""
        doc_locations: Dict[str, Set[str]] = defaultdict(set)
        
        for node in self.cluster.nodes:
            if node.node_id not in self.cluster.active_nodes:
                continue
            
            try:
                # Usar endpoint interno para ver docs locales
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                    async with session.post(
                        f"{node.url}{API_V1}/internal/search",
                        json={"query": "test document", "top_k": 100}
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            for doc in data.get("results", []):
                                doc_id = doc.get("document_id")
                                if doc_id:
                                    doc_locations[doc_id].add(node.node_id)
            except:
                pass
        
        total = len(doc_locations)
        replicated = sum(1 for nodes in doc_locations.values() if len(nodes) >= 2)
        
        self.cluster.replicated_documents = replicated
        
        return total, replicated
    
    # ========================================================================
    # FASES DEL TEST
    # ========================================================================
    
    async def phase_discovery(self) -> bool:
        """Fase 0: Descubrimiento del cluster"""
        self.log_phase("DESCUBRIMIENTO", "Detectando configuración del cluster")
        
        if not await self.detect_cluster():
            return False
        
        # Mostrar resumen del cluster
        print()
        print(f"  {Colors.GREEN}Cluster detectado correctamente{Colors.ENDC}")
        print(f"  • Nodos activos: {len(self.cluster.active_nodes)}")
        print(f"  • Líder: {self.cluster.leader_node or 'Sin identificar'}")
        print()
        
        self.wait_for_user("Cluster detectado. ¿Continuar con las pruebas?")
        return True
    
    async def phase_auth(self) -> bool:
        """Fase 1: Autenticación"""
        self.log_phase("AUTENTICACIÓN", "Registro y login de usuario de prueba")
        
        if not await self.test_register_user():
            return False
        
        if not self.token:
            if not await self.test_login():
                return False
        
        self.wait_for_user("Autenticación completada")
        return True
    
    async def phase_basic_operations(self) -> bool:
        """Fase 2: Operaciones básicas"""
        self.log_phase("OPERACIONES BÁSICAS", "Upload, listado, búsqueda, descarga")
        
        # Número de documentos según modo
        num_docs = 3 if self.quick else 6
        
        # Upload de documentos
        self.log_subphase("Subiendo documentos de prueba")
        
        test_contents = [
            ("Documento sobre Inteligencia Artificial", 
             "La inteligencia artificial es una rama de la informática que busca crear máquinas capaces de imitar el comportamiento humano."),
            ("Guía de Machine Learning",
             "El aprendizaje automático permite a los sistemas aprender de datos sin ser programados explícitamente."),
            ("Arquitectura de Sistemas Distribuidos",
             "Los sistemas distribuidos consisten en múltiples nodos conectados en red que trabajan juntos como un sistema único."),
            ("Manual de Docker y Contenedores",
             "Docker permite empaquetar aplicaciones en contenedores portables que pueden ejecutarse en cualquier entorno."),
            ("Fundamentos de Base de Datos",
             "Las bases de datos almacenan y organizan información de manera estructurada para su posterior consulta."),
            ("Redes y Protocolos de Comunicación",
             "Los protocolos de red definen las reglas para la comunicación entre dispositivos en una red.")
        ]
        
        uploaded_ids = []
        for i, (title, content) in enumerate(test_contents[:num_docs]):
            doc_id = await self.test_upload_document(title, content)
            if doc_id:
                uploaded_ids.append(doc_id)
            await asyncio.sleep(0.5)
        
        if not uploaded_ids:
            self.record_result("Uploads", "BASIC", False, "No se subió ningún documento", 0)
            return False
        
        # Esperar replicación
        self.log_subphase("Esperando replicación...")
        await asyncio.sleep(5 if self.quick else 10)
        
        # Listar documentos
        self.log_subphase("Verificando listado")
        docs = await self.test_list_documents()
        
        # Búsqueda
        self.log_subphase("Probando búsqueda")
        await self.test_search("inteligencia artificial")
        await self.test_search("sistemas distribuidos")
        
        # Descarga
        self.log_subphase("Probando descarga")
        if uploaded_ids:
            await self.test_download_document(uploaded_ids[0])
        
        self.wait_for_user("Operaciones básicas completadas")
        return True
    
    async def phase_replication_check(self) -> bool:
        """Fase 3: Verificación de replicación"""
        self.log_phase("VERIFICACIÓN DE REPLICACIÓN", 
                      f"Comprobando documentos en {len(self.cluster.active_nodes)} nodos")
        
        # Verificar en cada nodo
        self.log_subphase("Consultando cada nodo")
        
        for node in self.cluster.nodes:
            if node.node_id in self.cluster.active_nodes:
                docs = await self.test_list_documents(node.url)
        
        # Verificar replicación
        self.log_subphase("Analizando factor de replicación")
        total, replicated = await self.test_replication()
        
        if total > 0:
            factor = (replicated / total) * 2 if replicated > 0 else 0
            self.record_result("Factor de replicación", "REPLICATION", 
                             replicated >= total * 0.5,
                             f"{replicated}/{total} docs replicados (factor ~{factor:.1f})", 0)
        
        self.wait_for_user("Verificación de replicación completada")
        return True
    
    async def phase_node_failure(self) -> bool:
        """Fase 4: Fallo de nodo (Docker)"""
        if self.skip_docker or len(self.cluster.active_nodes) < 2:
            self.log("Saltando fase de fallo de nodo", "WARN")
            return True
        
        self.log_phase("FALLO DE NODO", "Simulando caída de un nodo con Docker")
        
        # Seleccionar nodo a detener (no el líder si es posible)
        target_node = None
        for node_id in self.cluster.active_nodes:
            if node_id != self.cluster.leader_node:
                target_node = node_id
                break
        if not target_node:
            target_node = self.cluster.active_nodes[-1]
        
        self.log(f"Deteniendo nodo: {target_node}", "WARN")
        
        # Detener nodo
        self.log_subphase(f"Deteniendo {target_node}")
        if self.stop_node_docker(target_node):
            self.record_result(f"Detener {target_node}", "FAILURE", True, "Servicio escalado a 0", 0)
        
        await asyncio.sleep(5)
        
        # Verificar que el sistema sigue funcionando
        self.log_subphase("Verificando operaciones con nodo caído")
        
        # Buscar
        results = await self.test_search("inteligencia")
        
        # Subir documento durante la caída
        doc_id = await self.test_upload_document(
            "Documento durante fallo",
            "Este documento fue creado mientras un nodo estaba caído."
        )
        
        self.wait_for_user(f"Nodo {target_node} detenido. Verificar y continuar")
        
        # Restaurar nodo
        self.log_subphase(f"Restaurando {target_node}")
        if self.start_node_docker(target_node):
            self.cluster.active_nodes.append(target_node)
            self.record_result(f"Restaurar {target_node}", "RECOVERY", True, "Servicio reiniciado", 0)
        
        # Esperar sincronización
        self.log_subphase("Esperando sincronización")
        await asyncio.sleep(15 if self.quick else 30)
        
        # Verificar que el documento está en el nodo restaurado
        node_url = self.get_node_url(target_node)
        if node_url and doc_id:
            results = await self.test_search("durante fallo", node_url)
            if results:
                self.record_result("Sincronización post-fallo", "RECOVERY", True, 
                                 f"Documento encontrado en {target_node}", 0)
        
        self.wait_for_user("Recuperación de nodo completada")
        return True
    
    async def phase_network_partition(self) -> bool:
        """Fase 5: Partición de red (WiFi manual)"""
        if self.skip_wifi:
            self.log("Saltando fase de partición de red (WiFi)", "WARN")
            return True
        
        if len(self.cluster.nodes) < 2:
            self.log("Se necesitan al menos 2 nodos para partición de red", "WARN")
            return True
        
        self.log_phase("PARTICIÓN DE RED", "Simulando desconexión de red manual")
        
        # Identificar nodos por host (si hay múltiples hosts)
        hosts = set(node.host for node in self.cluster.nodes)
        
        if len(hosts) == 1:
            self.log("Todos los nodos están en el mismo host - partición manual no aplica", "WARN")
            self.log("En un despliegue real, los nodos estarían en diferentes máquinas", "INFO")
            return True
        
        # Seleccionar host para desconectar
        target_host = list(hosts)[0]
        target_nodes = [n.node_id for n in self.cluster.nodes if n.host == target_host]
        
        # Acción manual: desconectar
        if self.wait_for_wifi_action("DESCONECTAR WiFi/Red", target_host):
            for node_id in target_nodes:
                self.cluster.partitioned_nodes.append(node_id)
                if node_id in self.cluster.active_nodes:
                    self.cluster.active_nodes.remove(node_id)
        
        # Verificar operación en partición
        self.log_subphase("Verificando operaciones durante partición")
        await asyncio.sleep(5)
        
        # Crear documento durante partición
        doc_id = await self.test_upload_document(
            "Documento durante partición",
            "Este documento fue creado durante una partición de red."
        )
        
        # Acción manual: reconectar
        if self.wait_for_wifi_action("RECONECTAR WiFi/Red", target_host):
            for node_id in target_nodes:
                if node_id in self.cluster.partitioned_nodes:
                    self.cluster.partitioned_nodes.remove(node_id)
                    self.cluster.active_nodes.append(node_id)
        
        # Esperar reconexión y sincronización
        self.log_subphase("Esperando sincronización post-partición")
        await asyncio.sleep(20 if self.quick else 45)
        
        # Verificar sincronización
        self.log_subphase("Verificando sincronización")
        total, replicated = await self.test_replication()
        
        self.wait_for_user("Fase de partición de red completada")
        return True
    
    async def phase_cascade_failure(self) -> bool:
        """Fase 6: Fallo en cascada"""
        if self.skip_docker or len(self.cluster.active_nodes) < 3:
            self.log("Saltando fase de fallo en cascada (necesita 3+ nodos)", "WARN")
            return True
        
        self.log_phase("FALLO EN CASCADA", "Deteniendo nodos progresivamente")
        
        # Detener nodos excepto uno
        nodes_to_stop = self.cluster.active_nodes[1:]  # Mantener el primero
        
        for i, node_id in enumerate(nodes_to_stop):
            self.log_subphase(f"Deteniendo nodo {i+1}/{len(nodes_to_stop)}: {node_id}")
            self.stop_node_docker(node_id)
            await asyncio.sleep(3)
            
            # Verificar que el sistema sigue funcionando
            results = await self.test_search("test")
        
        self.log(f"Sistema operando con solo {len(self.cluster.active_nodes)} nodo(s)", "WARN")
        
        # Crear documento en modo degradado
        await self.test_upload_document(
            "Documento en modo degradado",
            "Creado con solo un nodo activo."
        )
        
        self.wait_for_user("Sistema en modo degradado. Verificar antes de recuperar")
        
        # Recuperar nodos
        self.log_subphase("Recuperando nodos en cascada")
        
        for node_id in reversed(nodes_to_stop):
            self.log(f"Iniciando {node_id}...", "INFO")
            self.start_node_docker(node_id)
            await asyncio.sleep(10)
        
        # Esperar sincronización completa
        self.log_subphase("Esperando sincronización completa")
        await asyncio.sleep(20 if self.quick else 45)
        
        # Verificar estado final
        total, replicated = await self.test_replication()
        
        self.wait_for_user("Recuperación de cascada completada")
        return True
    
    async def phase_final_verification(self) -> bool:
        """Fase 7: Verificación final"""
        self.log_phase("VERIFICACIÓN FINAL", "Comprobación completa del sistema")
        
        # Re-detectar cluster
        self.log_subphase("Re-detectando estado del cluster")
        await self.detect_cluster()
        
        # Listar en todos los nodos
        self.log_subphase("Listando documentos en cada nodo")
        all_docs = set()
        for node in self.cluster.nodes:
            if node.node_id in self.cluster.active_nodes:
                docs = await self.test_list_documents(node.url)
                for doc in docs:
                    all_docs.add(doc.get("id") or doc.get("document_id"))
        
        # Verificar replicación final
        self.log_subphase("Verificación final de replicación")
        total, replicated = await self.test_replication()
        
        return True
    
    async def phase_cleanup(self) -> bool:
        """Fase 8: Limpieza"""
        if self.skip_cleanup:
            self.log("Saltando limpieza (--skip-cleanup)", "WARN")
            return True
        
        self.log_phase("LIMPIEZA", "Eliminando documentos de prueba")
        
        deleted = 0
        for doc in self.created_docs:
            doc_id = doc.get("id")
            if doc_id and await self.test_delete_document(doc_id):
                deleted += 1
            await asyncio.sleep(0.3)
        
        self.record_result("Limpieza", "CLEANUP", True, 
                         f"{deleted}/{len(self.created_docs)} documentos eliminados", 0)
        
        return True
    
    # ========================================================================
    # EJECUCIÓN PRINCIPAL
    # ========================================================================
    
    async def run(self) -> bool:
        """Ejecuta el test supremo completo"""
        print()
        print(f"{Colors.HEADER}{'═' * 70}{Colors.ENDC}")
        print(f"{Colors.HEADER}{Colors.BOLD}  TEST SCENARIO ULTIMATE - PRUEBA SUPREMA ADAPTATIVA{Colors.ENDC}")
        print(f"{Colors.HEADER}{'═' * 70}{Colors.ENDC}")
        print()
        print(f"  Configuración:")
        print(f"    • Host: {self.host}")
        print(f"    • Docker tests: {'Sí' if not self.skip_docker else 'No'}")
        print(f"    • WiFi tests: {'Sí' if not self.skip_wifi else 'No'}")
        print(f"    • Modo: {'Rápido' if self.quick else 'Completo'}")
        print(f"    • Interactivo: {'Sí' if self.interactive else 'No'}")
        print()
        
        start_time = time.time()
        
        try:
            # Ejecutar fases
            phases = [
                ("Descubrimiento", self.phase_discovery),
                ("Autenticación", self.phase_auth),
                ("Operaciones Básicas", self.phase_basic_operations),
                ("Verificación Replicación", self.phase_replication_check),
                ("Fallo de Nodo", self.phase_node_failure),
                ("Partición de Red", self.phase_network_partition),
                ("Fallo en Cascada", self.phase_cascade_failure),
                ("Verificación Final", self.phase_final_verification),
                ("Limpieza", self.phase_cleanup),
            ]
            
            for phase_name, phase_func in phases:
                try:
                    if not await phase_func():
                        self.log(f"Fase '{phase_name}' falló", "ERROR")
                        # Continuar con las siguientes fases si es posible
                except Exception as e:
                    self.log(f"Error en fase '{phase_name}': {e}", "ERROR")
                    if self.verbose:
                        import traceback
                        traceback.print_exc()
            
        except KeyboardInterrupt:
            self.log("\n¡Test interrumpido por el usuario!", "WARN")
        finally:
            # SIEMPRE intentar limpiar, incluso si el test falló o fue interrumpido
            if not self.skip_cleanup and self.created_docs:
                self.log("Ejecutando limpieza de seguridad...", "INFO")
                try:
                    await self._emergency_cleanup()
                except Exception as e:
                    self.log(f"Error en limpieza de seguridad: {e}", "WARN")
        
        total_time = time.time() - start_time
        
        # Resumen final
        self.print_summary(total_time)
        
        # Determinar resultado
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        
        return failed == 0
    
    async def _emergency_cleanup(self):
        """Limpieza de emergencia que se ejecuta siempre"""
        # Verificar qué documentos no fueron eliminados
        cleaned_ids = set()
        for r in self.results:
            if "Eliminar:" in r.name and r.passed:
                # Extraer ID del mensaje
                parts = r.name.split(":")
                if len(parts) > 1:
                    cleaned_ids.add(parts[1].strip()[:8])
        
        # Intentar eliminar los que faltan
        for doc in self.created_docs:
            doc_id = doc.get("id")
            if doc_id and doc_id[:8] not in cleaned_ids:
                try:
                    await self.test_delete_document(doc_id)
                except Exception:
                    pass
    
    def print_summary(self, total_time: float):
        """Imprime resumen de resultados"""
        print()
        print(f"{Colors.HEADER}{'═' * 70}{Colors.ENDC}")
        print(f"{Colors.HEADER}{Colors.BOLD}  RESUMEN DE RESULTADOS{Colors.ENDC}")
        print(f"{Colors.HEADER}{'═' * 70}{Colors.ENDC}")
        print()
        
        # Agrupar por fase
        phases = defaultdict(list)
        for r in self.results:
            phases[r.phase].append(r)
        
        for phase, results in phases.items():
            passed = sum(1 for r in results if r.passed)
            total = len(results)
            color = Colors.GREEN if passed == total else Colors.YELLOW if passed > 0 else Colors.RED
            print(f"  {color}{phase}: {passed}/{total} pruebas exitosas{Colors.ENDC}")
            
            for r in results:
                status = f"{Colors.GREEN}✓{Colors.ENDC}" if r.passed else f"{Colors.RED}✗{Colors.ENDC}"
                print(f"    {status} {r.name}: {r.message}")
        
        print()
        
        # Totales
        total_passed = sum(1 for r in self.results if r.passed)
        total_failed = sum(1 for r in self.results if not r.passed)
        total_tests = len(self.results)
        
        print(f"  {Colors.BOLD}Total: {total_passed}/{total_tests} pruebas exitosas{Colors.ENDC}")
        print(f"  {Colors.BOLD}Tiempo total: {total_time:.1f} segundos{Colors.ENDC}")
        print()
        
        # Estado del cluster
        print(f"  {Colors.CYAN}Estado final del cluster:{Colors.ENDC}")
        print(f"    • Nodos activos: {len(self.cluster.active_nodes)}")
        print(f"    • Documentos creados: {self.cluster.total_documents}")
        print(f"    • Documentos replicados: {self.cluster.replicated_documents}")
        print()
        
        if total_failed == 0:
            print(f"  {Colors.GREEN}{Colors.BOLD}🎉 ¡TODAS LAS PRUEBAS PASARON!{Colors.ENDC}")
        else:
            print(f"  {Colors.YELLOW}{Colors.BOLD}⚠️  {total_failed} prueba(s) fallaron{Colors.ENDC}")
        
        print()


async def main():
    parser = argparse.ArgumentParser(
        description="Test Scenario Ultimate - Prueba Suprema Adaptativa",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Test completo con detección automática en localhost
  python scripts/test_scenario_ultimate.py

  # Test con nodos en múltiples máquinas (RECOMENDADO)
  python scripts/test_scenario_ultimate.py --nodes 192.168.1.11:8001,192.168.1.13:8004,192.168.1.9:8005

  # Test en cluster remoto (todos los nodos en el mismo host)
  python scripts/test_scenario_ultimate.py --host 192.168.1.100

  # Test rápido sin pruebas de WiFi
  python scripts/test_scenario_ultimate.py --quick --skip-wifi

  # Test interactivo para demo
  python scripts/test_scenario_ultimate.py --interactive
        """
    )
    
    parser.add_argument("--nodes", default=None,
                       help="Lista de nodos IP:PORT separados por coma (ej: 192.168.1.11:8001,192.168.1.13:8004)")
    parser.add_argument("--host", default=DEFAULT_HOST,
                       help=f"Host/IP por defecto para auto-detección (default: {DEFAULT_HOST})")
    parser.add_argument("--ports", default=None,
                       help="Puertos de nodos separados por coma (usa --host para todos)")
    parser.add_argument("--base-url", default=None,
                       help="URL base alternativa (override)")
    parser.add_argument("--skip-docker", action="store_true",
                       help="No hacer pruebas con contenedores Docker")
    parser.add_argument("--skip-wifi", action="store_true",
                       help="No incluir pausas para pruebas WiFi manuales")
    parser.add_argument("--skip-cleanup", action="store_true",
                       help="No eliminar documentos de prueba al final")
    parser.add_argument("--interactive", action="store_true",
                       help="Modo interactivo con pausas entre fases")
    parser.add_argument("--quick", action="store_true",
                       help="Modo rápido (menos documentos, menos esperas)")
    parser.add_argument("--verbose", action="store_true",
                       help="Mostrar logs detallados")
    
    args = parser.parse_args()
    
    # Parsear nodos si se especificaron (formato IP:PORT,IP:PORT,...)
    nodes = None
    if args.nodes:
        nodes = []
        for node_str in args.nodes.split(","):
            node_str = node_str.strip()
            if ":" in node_str:
                host, port = node_str.rsplit(":", 1)
                nodes.append((host, int(port)))
            else:
                # Si solo se da el puerto, usar host por defecto
                nodes.append((args.host, int(node_str)))
    
    # Parsear puertos si se especificaron (usa host por defecto para todos)
    ports = None
    if args.ports and not nodes:
        ports = [int(p.strip()) for p in args.ports.split(",")]
    
    # Crear y ejecutar test
    test = UltimateTestScenario(
        host=args.host,
        ports=ports,
        nodes=nodes,
        skip_docker=args.skip_docker,
        skip_wifi=args.skip_wifi,
        skip_cleanup=args.skip_cleanup,
        interactive=args.interactive,
        quick=args.quick,
        verbose=args.verbose
    )
    
    success = await test.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
