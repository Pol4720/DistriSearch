#!/usr/bin/env python3
"""
Test Scenario 2 (Container Mode): Network Partition Simulation
==============================================================

Simula particiones de red parando/iniciando contenedores Docker.
NO requiere múltiples máquinas ni desconectar WiFi.

Uso:
    python scripts/test_scenario_2_containers.py [--base-url URL | --host HOST --port PORT]

Ejemplos:
    python scripts/test_scenario_2_containers.py
    python scripts/test_scenario_2_containers.py --host 192.168.1.11 --port 8001
    python scripts/test_scenario_2_containers.py --base-url http://192.168.1.11:8001

Fases:
1. Setup: Crear usuario y documentos iniciales
2. Partition: Detener un nodo y crear documentos en los nodos activos
3. Recovery: Reiniciar el nodo y verificar sincronización
4. Verify: Comprobar que todos los documentos están disponibles
"""

import asyncio
import argparse
import subprocess
import time
import sys
from datetime import datetime
from typing import Dict, List, Optional
import aiohttp


# Valores por defecto
DEFAULT_HOST = "localhost"
DEFAULT_PORT = "8001"
API_V1 = "/api/v1"
TIMEOUT = 30.0

TEST_USER = {
    "username": "partition_container_test",
    "email": "partition_container@test.com",
    "password": "TestPartition123!"
}


class ContainerPartitionTester:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}{API_V1}"
        self.results: List[Dict] = []
        self.token: Optional[str] = None
        self.user_id: Optional[str] = None
        self.created_docs: List[Dict] = []
        
    def log(self, msg: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        colors = {
            "INFO": "\033[0m",
            "SUCCESS": "\033[92m",
            "WARN": "\033[93m",
            "ERROR": "\033[91m",
            "PHASE": "\033[96m"
        }
        color = colors.get(level, "\033[0m")
        print(f"{color}[{timestamp}] [{level}] {msg}\033[0m")
    
    def record_result(self, name: str, passed: bool, message: str):
        self.results.append({"name": name, "passed": passed, "message": message})
        status = "✓" if passed else "✗"
        level = "SUCCESS" if passed else "ERROR"
        self.log(f"{status} {name}: {message}", level)
    
    def run_docker_cmd(self, cmd: List[str]) -> tuple:
        """Ejecutar comando docker y retornar (success, output)"""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
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
    
    def get_node_containers(self) -> Dict[str, str]:
        """Obtener mapeo de nodo -> nombre de servicio (para compatibilidad)"""
        return self.get_service_names()
    
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
        
        self.log(f"Escalando servicio {service} a 0 réplicas", "WARN")
        success, output = self.run_docker_cmd([
            "docker", "service", "scale", f"{service}=0"
        ])
        if success:
            self.log(f"  ✓ Servicio detenido", "SUCCESS")
            time.sleep(3)  # Esperar a que se detenga
        else:
            self.log(f"  ✗ Error: {output}", "ERROR")
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
            
        self.log(f"Escalando servicio {service} a 1 réplica")
        success, output = self.run_docker_cmd([
            "docker", "service", "scale", f"{service}=1"
        ])
        if success:
            self.log(f"  ✓ Servicio iniciado", "SUCCESS")
            # Esperar a que el contenedor esté listo
            self.log(f"  Esperando a que el servicio esté listo...")
            time.sleep(15)
        else:
            self.log(f"  ✗ Error: {output}", "ERROR")
        return success
    
    async def authenticate(self, session: aiohttp.ClientSession) -> bool:
        """Autenticar usuario (crear si no existe)"""
        # Intentar registrar
        try:
            async with session.post(f"{self.api_url}/auth/register", json=TEST_USER) as resp:
                if resp.status == 409:
                    self.log("Usuario ya existe, haciendo login...")
                elif resp.status not in [200, 201]:
                    self.log(f"Error registrando: {await resp.text()}", "WARN")
        except Exception as e:
            self.log(f"Error en registro: {e}", "WARN")
        
        # Login
        try:
            async with session.post(
                f"{self.api_url}/auth/login",
                json={"username": TEST_USER["username"], "password": TEST_USER["password"]}
            ) as resp:
                if resp.status != 200:
                    return False
                data = await resp.json()
                self.token = data.get("access_token")
            
            # Obtener user_id
            headers = {"Authorization": f"Bearer {self.token}"}
            async with session.get(f"{self.api_url}/auth/me", headers=headers) as resp:
                if resp.status == 200:
                    me = await resp.json()
                    self.user_id = me.get("id") or me.get("user_id")
            
            return True
        except Exception as e:
            self.log(f"Error en login: {e}", "ERROR")
            return False
    
    async def create_document(self, session: aiohttp.ClientSession, title: str, content: str, tags: List[str]) -> Optional[Dict]:
        """Crear un documento"""
        headers = {"Authorization": f"Bearer {self.token}"}
        doc_data = {"title": title, "content": content, "tags": tags}
        
        try:
            async with session.post(f"{self.api_url}/documents", json=doc_data, headers=headers) as resp:
                if resp.status in [200, 201]:
                    doc = await resp.json()
                    self.created_docs.append(doc)
                    return doc
                else:
                    self.log(f"Error creando doc: {await resp.text()}", "ERROR")
                    return None
        except Exception as e:
            self.log(f"Error creando doc: {e}", "ERROR")
            return None
    
    async def list_documents(self, session: aiohttp.ClientSession) -> List[Dict]:
        """Listar documentos del usuario"""
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            async with session.get(f"{self.api_url}/documents", headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("documents", data) if isinstance(data, dict) else data
                return []
        except:
            return []
    
    async def delete_document(self, session: aiohttp.ClientSession, doc_id: str) -> bool:
        """Eliminar un documento"""
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            async with session.delete(f"{self.api_url}/documents/{doc_id}", headers=headers) as resp:
                return resp.status in [200, 204]
        except:
            return False
    
    async def run_test(self):
        """Ejecutar el test completo"""
        self.log("=" * 70, "PHASE")
        self.log("TEST SCENARIO 2: PARTITION SIMULATION (CONTAINER MODE)", "PHASE")
        self.log("=" * 70, "PHASE")
        self.log(f"Base URL: {self.base_url}")
        
        # Verificar servicios disponibles
        services = self.get_service_names()
        if len(services) < 3:
            self.log(f"Se necesitan 3 nodos, configurados: {len(services)}", "ERROR")
            return False
        
        self.log(f"Servicios configurados: {list(services.keys())}")
        
        # Elegir el nodo a "particionar" (node-3)
        partition_node = "node-3"
        partition_service = services.get(partition_node)
        if not partition_service:
            self.log(f"No se encontró servicio para {partition_node}", "ERROR")
            return False
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=TIMEOUT)) as session:
            
            # ========== FASE 1: SETUP ==========
            self.log("\n" + "=" * 70, "PHASE")
            self.log("FASE 1: SETUP INICIAL", "PHASE")
            self.log("=" * 70, "PHASE")
            
            # Autenticar
            if not await self.authenticate(session):
                self.record_result("Autenticación", False, "No se pudo autenticar")
                return False
            self.record_result("Autenticación", True, f"User ID: {self.user_id}")
            
            # Crear documentos iniciales
            pre_partition_docs = []
            for i in range(2):
                doc = await self.create_document(
                    session,
                    f"Pre-Partition Doc {i+1}",
                    f"Este documento fue creado ANTES de la partición. Índice: {i+1}",
                    ["pre-partition", "test"]
                )
                if doc:
                    pre_partition_docs.append(doc)
                    self.log(f"  ✓ Creado: {doc.get('title')} (Node: {doc.get('node_id')})")
            
            self.record_result(
                "Documentos pre-partición", 
                len(pre_partition_docs) == 2,
                f"{len(pre_partition_docs)}/2 documentos creados"
            )
            
            # Esperar replicación
            self.log("\nEsperando 5s para replicación inicial...")
            await asyncio.sleep(5)
            
            # ========== FASE 2: PARTITION ==========
            self.log("\n" + "=" * 70, "PHASE")
            self.log(f"FASE 2: SIMULAR PARTICIÓN (Detener {partition_node})", "PHASE")
            self.log("=" * 70, "PHASE")
            
            # Detener nodo
            if not self.stop_container(partition_service):
                self.record_result("Detener nodo", False, f"No se pudo detener {partition_node}")
                return False
            self.record_result("Detener nodo", True, f"{partition_node} detenido")
            
            # Esperar a que el cluster detecte la pérdida
            self.log("\nEsperando 10s para que el cluster detecte la pérdida...")
            await asyncio.sleep(10)
            
            # Crear documentos durante la "partición"
            during_partition_docs = []
            for i in range(2):
                doc = await self.create_document(
                    session,
                    f"During-Partition Doc {i+1}",
                    f"Este documento fue creado DURANTE la partición (con {partition_node} caído). Índice: {i+1}",
                    ["during-partition", "test"]
                )
                if doc:
                    during_partition_docs.append(doc)
                    self.log(f"  ✓ Creado: {doc.get('title')} (Node: {doc.get('node_id')})")
            
            self.record_result(
                "Documentos durante partición",
                len(during_partition_docs) >= 1,
                f"{len(during_partition_docs)}/2 documentos creados con nodo caído"
            )
            
            # Verificar que podemos listar documentos
            docs_during = await self.list_documents(session)
            expected_count = len(pre_partition_docs) + len(during_partition_docs)
            self.record_result(
                "Listado durante partición",
                len(docs_during) >= expected_count,
                f"{len(docs_during)} documentos visibles (esperados: {expected_count})"
            )
            
            # ========== FASE 3: RECOVERY ==========
            self.log("\n" + "=" * 70, "PHASE")
            self.log(f"FASE 3: RECUPERACIÓN (Reiniciar {partition_node})", "PHASE")
            self.log("=" * 70, "PHASE")
            
            # Reiniciar nodo
            if not self.start_container(partition_service):
                self.record_result("Reiniciar nodo", False, f"No se pudo reiniciar {partition_node}")
                # Intentar de todos modos continuar
            else:
                self.record_result("Reiniciar nodo", True, f"{partition_node} reiniciado")
            
            # Esperar recuperación y sincronización
            self.log("\nEsperando 30s para recuperación y sincronización...")
            await asyncio.sleep(30)
            
            # ========== FASE 4: VERIFICACIÓN ==========
            self.log("\n" + "=" * 70, "PHASE")
            self.log("FASE 4: VERIFICACIÓN POST-RECUPERACIÓN", "PHASE")
            self.log("=" * 70, "PHASE")
            
            # Verificar que todos los documentos están disponibles
            docs_after = await self.list_documents(session)
            self.log(f"\nDocumentos encontrados: {len(docs_after)}")
            
            for doc in docs_after:
                tags = doc.get("tags", [])
                phase = "pre-partition" if "pre-partition" in tags else "during-partition" if "during-partition" in tags else "unknown"
                self.log(f"  - {doc.get('title')} | Fase: {phase} | Node: {doc.get('node_id')}")
            
            # Verificar conteo
            all_expected = len(pre_partition_docs) + len(during_partition_docs)
            self.record_result(
                "Documentos post-recuperación",
                len(docs_after) >= all_expected,
                f"{len(docs_after)}/{all_expected} documentos recuperados"
            )
            
            # Crear documento post-recuperación para verificar que el sistema funciona
            post_doc = await self.create_document(
                session,
                "Post-Recovery Doc",
                "Este documento fue creado DESPUÉS de la recuperación del nodo.",
                ["post-recovery", "test"]
            )
            self.record_result(
                "Documento post-recuperación",
                post_doc is not None,
                f"Creado: {post_doc.get('title') if post_doc else 'FALLIDO'}"
            )
            
            # ========== CLEANUP ==========
            self.log("\n" + "=" * 70, "PHASE")
            self.log("CLEANUP", "PHASE")
            self.log("=" * 70, "PHASE")
            
            deleted = 0
            for doc in self.created_docs:
                if await self.delete_document(session, doc.get("id")):
                    deleted += 1
            
            self.record_result("Cleanup", deleted > 0, f"{deleted}/{len(self.created_docs)} documentos eliminados")
        
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
            self.log("\n🎉 ¡TEST DE PARTICIÓN EXITOSO!", "SUCCESS")
            self.log("El sistema demostró:", "SUCCESS")
            self.log("  ✓ Operación continua con nodo caído", "SUCCESS")
            self.log("  ✓ Creación de documentos durante partición", "SUCCESS")
            self.log("  ✓ Recuperación automática al reiniciar nodo", "SUCCESS")
            self.log("  ✓ Sincronización post-recuperación", "SUCCESS")
        else:
            self.log("\n⚠️ TEST COMPLETADO CON ERRORES", "WARN")
        
        return failed == 0


async def main():
    parser = argparse.ArgumentParser(
        description="Test Scenario 2: Partition Simulation using Docker containers"
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
    
    tester = ContainerPartitionTester(base_url)
    success = await tester.run_test()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
