#!/usr/bin/env python3
"""
Test Scenario 3 (Container Mode): Cascade Failure & Recovery
============================================================

Simula múltiples fallos en cascada parando/iniciando contenedores Docker.
NO requiere múltiples máquinas ni desconectar WiFi.

Uso:
    python scripts/test_scenario_3_containers.py [--base-url URL | --host HOST --port PORT]

Ejemplos:
    python scripts/test_scenario_3_containers.py
    python scripts/test_scenario_3_containers.py --host 192.168.1.11 --port 8001
    python scripts/test_scenario_3_containers.py --base-url http://192.168.1.11:8001

Fases:
1. Setup: Crear documentos iniciales con replicación
2. Cascade Down: Detener nodos progresivamente (node-3 → node-2)
3. Minimal Operation: Operar con solo 1 nodo
4. Cascade Up: Recuperar nodos progresivamente
5. Verify: Verificar sincronización completa
"""

import asyncio
import argparse
import subprocess
import time
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import aiohttp


# Valores por defecto
DEFAULT_HOST = "localhost"
DEFAULT_PORT = "8001"
API_V1 = "/api/v1"
TIMEOUT = 30.0

TEST_USER = {
    "username": "cascade_container_test",
    "email": "cascade_container@test.com", 
    "password": "TestCascade123!"
}


class CascadeFailureTester:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}{API_V1}"
        self.results: List[Dict] = []
        self.token: Optional[str] = None
        self.user_id: Optional[str] = None
        self.created_docs: List[Dict] = []
        self.stopped_containers: List[str] = []
        
    def log(self, msg: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        colors = {
            "INFO": "\033[0m",
            "SUCCESS": "\033[92m",
            "WARN": "\033[93m",
            "ERROR": "\033[91m",
            "PHASE": "\033[96m",
            "CRITICAL": "\033[95m"
        }
        color = colors.get(level, "\033[0m")
        print(f"{color}[{timestamp}] [{level}] {msg}\033[0m")
    
    def record_result(self, name: str, passed: bool, message: str):
        self.results.append({"name": name, "passed": passed, "message": message})
        status = "✓" if passed else "✗"
        level = "SUCCESS" if passed else "ERROR"
        self.log(f"{status} {name}: {message}", level)
    
    def run_docker_cmd(self, cmd: List[str]) -> Tuple[bool, str]:
        """Ejecutar comando docker y retornar (success, output)"""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            return result.returncode == 0, result.stdout + result.stderr
        except Exception as e:
            return False, str(e)
    
    def get_service_names(self) -> Dict[str, str]:
        """Obtener mapeo de nodo -> nombre de servicio Docker Swarm"""
        return {
            "node-1": "distrisearch-node-1",
            "node-2": "distrisearch-node-2",
            "node-3": "distrisearch-node-3"
        }
    
    def stop_container(self, service_or_container: str) -> bool:
        """Detener un servicio escalando a 0 réplicas"""
        # Extraer nombre del servicio
        if "node-1" in service_or_container:
            service = "distrisearch-node-1"
        elif "node-2" in service_or_container:
            service = "distrisearch-node-2"
        elif "node-3" in service_or_container:
            service = "distrisearch-node-3"
        else:
            service = service_or_container
            
        self.log(f"  Deteniendo servicio: {service}", "WARN")
        success, output = self.run_docker_cmd([
            "docker", "service", "scale", f"{service}=0"
        ])
        if success:
            self.stopped_containers.append(service)
            time.sleep(3)
        return success
    
    def start_container(self, service_or_container: str) -> bool:
        """Iniciar un servicio escalando a 1 réplica"""
        # Extraer nombre del servicio
        if "node-1" in service_or_container:
            service = "distrisearch-node-1"
        elif "node-2" in service_or_container:
            service = "distrisearch-node-2"
        elif "node-3" in service_or_container:
            service = "distrisearch-node-3"
        else:
            service = service_or_container
            
        self.log(f"  Iniciando servicio: {service}")
        success, output = self.run_docker_cmd([
            "docker", "service", "scale", f"{service}=1"
        ])
        if success and service in self.stopped_containers:
            self.stopped_containers.remove(service)
            # Esperar a que el contenedor esté listo
            self.log(f"  Esperando a que el servicio esté listo...")
            time.sleep(15)
        return success
    
    async def check_system_health(self, session: aiohttp.ClientSession) -> Dict:
        """Verificar estado de salud del sistema"""
        try:
            async with session.get(f"{self.api_url}/health/live") as resp:
                if resp.status == 200:
                    return await resp.json()
        except:
            pass
        return {}
    
    async def authenticate(self, session: aiohttp.ClientSession) -> bool:
        """Autenticar usuario"""
        try:
            async with session.post(f"{self.api_url}/auth/register", json=TEST_USER) as resp:
                pass  # Ignorar si ya existe
        except:
            pass
        
        try:
            async with session.post(
                f"{self.api_url}/auth/login",
                json={"username": TEST_USER["username"], "password": TEST_USER["password"]}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.token = data.get("access_token")
                    
            headers = {"Authorization": f"Bearer {self.token}"}
            async with session.get(f"{self.api_url}/auth/me", headers=headers) as resp:
                if resp.status == 200:
                    me = await resp.json()
                    self.user_id = me.get("id") or me.get("user_id")
            
            return True
        except:
            return False
    
    async def create_document(self, session: aiohttp.ClientSession, title: str, content: str, tags: List[str]) -> Optional[Dict]:
        """Crear documento"""
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            async with session.post(
                f"{self.api_url}/documents", 
                json={"title": title, "content": content, "tags": tags},
                headers=headers
            ) as resp:
                if resp.status in [200, 201]:
                    doc = await resp.json()
                    self.created_docs.append(doc)
                    return doc
        except:
            pass
        return None
    
    async def list_documents(self, session: aiohttp.ClientSession) -> List[Dict]:
        """Listar documentos"""
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            async with session.get(f"{self.api_url}/documents", headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("documents", data) if isinstance(data, dict) else data
        except:
            pass
        return []
    
    async def search_documents(self, session: aiohttp.ClientSession, query: str) -> List[Dict]:
        """Buscar documentos"""
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            async with session.get(
                f"{self.api_url}/search", 
                params={"q": query, "page": 1, "page_size": 50},
                headers=headers
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("results", [])
        except:
            pass
        return []
    
    async def delete_document(self, session: aiohttp.ClientSession, doc_id: str) -> bool:
        """Eliminar documento"""
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            async with session.delete(f"{self.api_url}/documents/{doc_id}", headers=headers) as resp:
                return resp.status in [200, 204]
        except:
            return False
    
    async def run_test(self):
        """Ejecutar el test completo"""
        self.log("=" * 70, "PHASE")
        self.log("TEST SCENARIO 3: CASCADE FAILURE & RECOVERY (CONTAINER MODE)", "PHASE")
        self.log("=" * 70, "PHASE")
        self.log(f"Base URL: {self.base_url}")
        
        services = self.get_service_names()
        if len(services) < 3:
            self.log(f"Se necesitan 3 nodos, configurados: {len(services)}", "ERROR")
            return False
        
        self.log(f"Servicios configurados: {list(services.keys())}")
        
        # Orden de fallo: node-3 primero, luego node-2 (dejar node-1 como único activo)
        cascade_order = ["node-3", "node-2"]
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=TIMEOUT)) as session:
            
            # ========== FASE 1: SETUP ==========
            self.log("\n" + "=" * 70, "PHASE")
            self.log("FASE 1: SETUP INICIAL (3 nodos activos)", "PHASE")
            self.log("=" * 70, "PHASE")
            
            if not await self.authenticate(session):
                self.record_result("Autenticación", False, "No se pudo autenticar")
                return False
            self.record_result("Autenticación", True, f"User ID: {self.user_id}")
            
            # Crear documentos iniciales
            initial_docs = []
            for i in range(3):
                doc = await self.create_document(
                    session,
                    f"Initial Doc {i+1}",
                    f"Documento inicial creado con cluster completo. Índice: {i+1}",
                    ["initial", "cascade-test"]
                )
                if doc:
                    initial_docs.append(doc)
                    self.log(f"  ✓ Creado: {doc.get('title')} → Node: {doc.get('node_id')}")
            
            self.record_result("Documentos iniciales", len(initial_docs) == 3, f"{len(initial_docs)}/3")
            
            self.log("\nEsperando 5s para replicación...")
            await asyncio.sleep(5)
            
            # ========== FASE 2: CASCADE DOWN ==========
            self.log("\n" + "=" * 70, "PHASE")
            self.log("FASE 2: FALLO EN CASCADA (node-3 → node-2)", "PHASE")
            self.log("=" * 70, "PHASE")
            
            docs_per_phase = {"2-nodes": [], "1-node": []}
            
            # Paso 2a: Detener node-3
            self.log("\n--- Paso 2a: Detener node-3 ---", "CRITICAL")
            if self.stop_container(services["node-3"]):
                self.log("  ✓ node-3 detenido", "SUCCESS")
            else:
                self.log("  ✗ Error deteniendo node-3", "ERROR")
            
            await asyncio.sleep(10)
            
            # Crear documentos con 2 nodos
            doc = await self.create_document(
                session,
                "Doc with 2 Nodes",
                "Creado mientras node-3 está caído. Solo 2 nodos disponibles.",
                ["2-nodes", "cascade-test"]
            )
            if doc:
                docs_per_phase["2-nodes"].append(doc)
                self.log(f"  ✓ Creado con 2 nodos: {doc.get('title')} → Node: {doc.get('node_id')}")
            
            # Paso 2b: Detener node-2
            self.log("\n--- Paso 2b: Detener node-2 ---", "CRITICAL")
            if self.stop_container(services["node-2"]):
                self.log("  ✓ node-2 detenido", "SUCCESS")
            else:
                self.log("  ✗ Error deteniendo node-2", "ERROR")
            
            await asyncio.sleep(10)
            
            self.record_result(
                "Cascade Down", 
                len(self.stopped_containers) == 2,
                f"{len(self.stopped_containers)}/2 nodos detenidos"
            )
            
            # ========== FASE 3: OPERACIÓN MÍNIMA ==========
            self.log("\n" + "=" * 70, "PHASE")
            self.log("FASE 3: OPERACIÓN CON UN SOLO NODO", "PHASE")
            self.log("=" * 70, "PHASE")
            
            # Verificar que el sistema sigue operativo
            health = await self.check_system_health(session)
            system_up = health.get("alive", False) == True
            
            # Crear documento con solo 1 nodo
            doc = await self.create_document(
                session,
                "Doc with 1 Node Only",
                "Creado con SOLO node-1 activo. Máxima degradación sin pérdida total.",
                ["1-node", "cascade-test"]
            )
            if doc:
                docs_per_phase["1-node"].append(doc)
                self.log(f"  ✓ Creado con 1 nodo: {doc.get('title')} → Node: {doc.get('node_id')}")
            
            # Listar documentos
            docs_minimal = await self.list_documents(session)
            self.log(f"\n  Documentos visibles con 1 nodo: {len(docs_minimal)}")
            
            # Búsqueda
            search_results = await self.search_documents(session, "cascade-test")
            self.log(f"  Búsqueda 'cascade-test': {len(search_results)} resultados")
            
            self.record_result(
                "Operación mínima",
                len(docs_minimal) > 0 and doc is not None,
                f"Sistema operativo con 1 nodo ({len(docs_minimal)} docs visibles)"
            )
            
            # ========== FASE 4: CASCADE UP ==========
            self.log("\n" + "=" * 70, "PHASE")
            self.log("FASE 4: RECUPERACIÓN EN CASCADA (node-2 → node-3)", "PHASE")
            self.log("=" * 70, "PHASE")
            
            # Paso 4a: Iniciar node-2
            self.log("\n--- Paso 4a: Iniciar node-2 ---")
            if self.start_container(services["node-2"]):
                self.log("  ✓ node-2 iniciado", "SUCCESS")
            else:
                self.log("  ✗ Error iniciando node-2", "ERROR")
            
            self.log("  Esperando 20s para sincronización...")
            await asyncio.sleep(20)
            
            docs_2nodes = await self.list_documents(session)
            self.log(f"  Documentos visibles con 2 nodos: {len(docs_2nodes)}")
            
            # Paso 4b: Iniciar node-3
            self.log("\n--- Paso 4b: Iniciar node-3 ---")
            if self.start_container(services["node-3"]):
                self.log("  ✓ node-3 iniciado", "SUCCESS")
            else:
                self.log("  ✗ Error iniciando node-3", "ERROR")
            
            self.log("  Esperando 30s para sincronización completa...")
            await asyncio.sleep(30)
            
            self.record_result(
                "Cascade Up",
                len(self.stopped_containers) == 0,
                f"Todos los nodos recuperados ({len(self.stopped_containers)} pendientes)"
            )
            
            # ========== FASE 5: VERIFICACIÓN ==========
            self.log("\n" + "=" * 70, "PHASE")
            self.log("FASE 5: VERIFICACIÓN FINAL", "PHASE")
            self.log("=" * 70, "PHASE")
            
            # Listar todos los documentos
            final_docs = await self.list_documents(session)
            expected_count = len(initial_docs) + len(docs_per_phase["2-nodes"]) + len(docs_per_phase["1-node"])
            
            self.log(f"\nDocumentos esperados: {expected_count}")
            self.log(f"Documentos encontrados: {len(final_docs)}")
            
            # Categorizar documentos
            categories = {"initial": 0, "2-nodes": 0, "1-node": 0, "other": 0}
            for doc in final_docs:
                tags = doc.get("tags", [])
                if "initial" in tags:
                    categories["initial"] += 1
                elif "2-nodes" in tags:
                    categories["2-nodes"] += 1
                elif "1-node" in tags:
                    categories["1-node"] += 1
                else:
                    categories["other"] += 1
            
            self.log(f"\nDistribución por fase:")
            self.log(f"  - Initial (3 nodos): {categories['initial']}")
            self.log(f"  - 2-nodes: {categories['2-nodes']}")
            self.log(f"  - 1-node: {categories['1-node']}")
            
            # Búsqueda final
            search_final = await self.search_documents(session, "cascade-test")
            self.log(f"\nBúsqueda 'cascade-test': {len(search_final)} resultados")
            
            self.record_result(
                "Sincronización completa",
                len(final_docs) >= expected_count,
                f"{len(final_docs)}/{expected_count} documentos"
            )
            
            # Health check final
            health_final = await self.check_system_health(session)
            self.record_result(
                "Health final",
                health_final.get("alive", False) == True,
                f"Alive: {health_final.get('alive', False)}"
            )
            
            # ========== CLEANUP ==========
            self.log("\n" + "=" * 70, "PHASE")
            self.log("CLEANUP", "PHASE")
            self.log("=" * 70, "PHASE")
            
            deleted = 0
            for doc in self.created_docs:
                if await self.delete_document(session, doc.get("id")):
                    deleted += 1
            
            self.record_result("Cleanup", deleted > 0, f"{deleted}/{len(self.created_docs)} eliminados")
        
        # Asegurar que todos los contenedores estén activos al finalizar
        if self.stopped_containers:
            self.log("\n⚠️ Reiniciando contenedores pendientes...", "WARN")
            for container in list(self.stopped_containers):
                self.start_container(container)
        
        # ========== RESUMEN ==========
        self.log("\n" + "=" * 70, "PHASE")
        self.log("RESUMEN FINAL", "PHASE")
        self.log("=" * 70, "PHASE")
        
        passed = sum(1 for r in self.results if r["passed"])
        failed = sum(1 for r in self.results if not r["passed"])
        
        for r in self.results:
            status = "✓" if r["passed"] else "✗"
            self.log(f"  {status} {r['name']}: {r['message']}")
        
        self.log(f"\nResults: {passed}/{passed+failed} passed, {failed} failed")
        
        if failed == 0:
            self.log("\n🎉 ¡TEST DE FALLO EN CASCADA EXITOSO!", "SUCCESS")
            self.log("El sistema demostró:", "SUCCESS")
            self.log("  ✓ Tolerancia a fallos múltiples en secuencia", "SUCCESS")
            self.log("  ✓ Operación con cluster degradado (1 nodo)", "SUCCESS")
            self.log("  ✓ Recuperación gradual sin pérdida de datos", "SUCCESS")
            self.log("  ✓ Sincronización completa post-recuperación", "SUCCESS")
        else:
            self.log("\n⚠️ TEST COMPLETADO CON ERRORES", "WARN")
        
        return failed == 0


async def main():
    parser = argparse.ArgumentParser(
        description="Test Scenario 3: Cascade Failure & Recovery using Docker containers"
    )
    parser.add_argument("--base-url", default=None, help="Base URL (e.g., http://192.168.1.11:8001)")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Host/IP del nodo (default: {DEFAULT_HOST})")
    parser.add_argument("--port", default=DEFAULT_PORT, help=f"Puerto del nodo (default: {DEFAULT_PORT})")
    
    args = parser.parse_args()
    
    # Construir URL base
    if args.base_url:
        base_url = args.base_url
    else:
        base_url = f"http://{args.host}:{args.port}"
    
    tester = CascadeFailureTester(base_url)
    success = await tester.run_test()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
