#!/usr/bin/env python3
"""
Test Scenario 2: Network Partition and Reconciliation
=====================================================

Este script está diseñado para probar particiones de red REALES donde
se desconecta físicamente una máquina de la WiFi.

HAY DOS MODOS DE USO:

═══════════════════════════════════════════════════════════════════════════════
MODO 1: GUIADO (--guided) - RECOMENDADO
═══════════════════════════════════════════════════════════════════════════════
Ejecuta todo el test de forma interactiva con tiempos de espera para que
el usuario realice las acciones manuales (desconectar WiFi, etc.)

    python scripts/test_scenario_2.py --guided --base-url https://192.168.1.10:443

El script:
1. Crea usuario y documento inicial
2. Espera 10 minutos para que desconectes un nodo y crees documentos
3. Espera otros 10 minutos para reconexión y reconciliación
4. Verifica los resultados

═══════════════════════════════════════════════════════════════════════════════
MODO 2: FASES MANUALES (--phase)
═══════════════════════════════════════════════════════════════════════════════
Para control total, ejecuta cada fase por separado:

Fase 1 (PREPARE): Ejecutar desde cualquier máquina CON conectividad
  - Crea usuarios y documentos iniciales
  - Espera sincronización
  
Fase 2 (PARTITION): Ejecutar LOCALMENTE en cada nodo aislado
  - Cada nodo crea documentos localmente (via localhost)
  - Incluye documentos "idénticos" para probar deduplicación
  
Fase 3 (VERIFY): Ejecutar después de restaurar conectividad
  - Verifica que todos los documentos se sincronizaron
  - Verifica que documentos idénticos fueron deduplicados

Uso:
    # Fase 1: Preparación (desde máquina con acceso a swarm)
    python scripts/test_scenario_2.py --phase prepare --base-url https://192.168.1.10:443
    
    # Fase 2: Durante partición - EN CADA NODO AISLADO
    # En nodo A (con acceso): 
    python scripts/test_scenario_2.py --phase partition --base-url https://192.168.1.10:443 --node-name nodoA
    # En nodo B (aislado, acceder via localhost):
    python scripts/test_scenario_2.py --phase partition --base-url https://localhost:443 --node-name nodoB
    
    # Fase 3: Verificación post-reconexión
    python scripts/test_scenario_2.py --phase verify --base-url https://192.168.1.10:443
"""

import asyncio
import argparse
import httpx
import json
import sys
import time
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Configuración
API_V1 = "/api/v1"
TIMEOUT = 30.0
STATE_FILE = "/tmp/distrisearch_partition_test_state.json"

# Tiempos de espera en modo guiado (en segundos)
WAIT_TIME_PARTITION = 10 * 60  # 10 minutos para crear partición y documentos
WAIT_TIME_RECONCILIATION = 10 * 60  # 10 minutos para reconexión y reconciliación

# Datos de prueba
TEST_USER = {
    "username": "partition_test_user",
    "email": "partition@test.com", 
    "password": "TestPartition123!"
}

# Documento IDÉNTICO que se creará en ambos nodos durante partición
IDENTICAL_DOC = {
    "title": "IDENTICAL - Documento de Prueba Deduplicación",
    "content": "Este contenido exacto debe existir solo UNA vez después de la reconciliación. Hash test.",
    "tags": ["identical", "dedup-test", "partition"]
}


@dataclass
class TestResult:
    name: str
    passed: bool
    message: str
    details: Optional[Dict] = None


class PartitionTester:
    def __init__(self, base_url: str, node_name: str = "default"):
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}{API_V1}"
        self.node_name = node_name
        self.client = httpx.AsyncClient(
            timeout=TIMEOUT, 
            follow_redirects=True,
            verify=False  # Para certificados self-signed
        )
        self.results: List[TestResult] = []
        self.state: Dict = {}
        
    async def close(self):
        await self.client.aclose()
    
    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        colors = {"INFO": "", "WARN": "\033[93m", "ERROR": "\033[91m", "SUCCESS": "\033[92m", "PHASE": "\033[96m"}
        reset = "\033[0m" if level != "INFO" else ""
        print(f"{colors.get(level, '')}[{timestamp}] [{level}] {message}{reset}")
    
    def save_state(self):
        """Guardar estado para compartir entre fases"""
        with open(STATE_FILE, 'w') as f:
            json.dump(self.state, f, indent=2, default=str)
        self.log(f"Estado guardado en {STATE_FILE}")
    
    def load_state(self):
        """Cargar estado de fase anterior"""
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                self.state = json.load(f)
            self.log(f"Estado cargado desde {STATE_FILE}")
            return True
        return False
    
    async def record_result(self, name: str, passed: bool, message: str, details: Dict = None):
        result = TestResult(name=name, passed=passed, message=message, details=details)
        self.results.append(result)
        status = "✓" if passed else "✗"
        self.log(f"{status} {name}: {message}")
        return result
    
    # ==================== FASE 1: PREPARE ====================
    
    async def phase_prepare(self):
        """Fase de preparación: crear usuario y documentos iniciales"""
        self.log("=" * 60, "PHASE")
        self.log("FASE 1: PREPARACIÓN", "PHASE")
        self.log("=" * 60, "PHASE")
        self.log(f"URL: {self.base_url}")
        
        # Health check
        try:
            response = await self.client.get(f"{self.api_url}/health")
            if response.status_code != 200:
                await self.record_result("Health Check", False, f"Status {response.status_code}")
                return False
            await self.record_result("Health Check", True, "OK")
        except Exception as e:
            await self.record_result("Health Check", False, str(e))
            return False
        
        # Crear o login usuario
        token = None
        try:
            # Intentar registrar
            response = await self.client.post(
                f"{self.api_url}/auth/register",
                json=TEST_USER
            )
            if response.status_code == 409:
                self.log("Usuario ya existe, haciendo login...")
            elif response.status_code not in [200, 201]:
                await self.record_result("Crear Usuario", False, f"Error: {response.text}")
                return False
            
            # Login
            login_resp = await self.client.post(
                f"{self.api_url}/auth/login",
                data={"username": TEST_USER["username"], "password": TEST_USER["password"]}
            )
            if login_resp.status_code != 200:
                await self.record_result("Login", False, f"Error: {login_resp.text}")
                return False
            
            token = login_resp.json().get("access_token")
            self.state["token"] = token
            self.state["username"] = TEST_USER["username"]
            await self.record_result("Autenticación", True, f"Usuario: {TEST_USER['username']}")
        except Exception as e:
            await self.record_result("Autenticación", False, str(e))
            return False
        
        # Crear documento inicial (pre-partición)
        headers = {"Authorization": f"Bearer {token}"}
        try:
            doc_data = {
                "title": "Documento Pre-Partición",
                "content": "Este documento fue creado ANTES de la partición de red.",
                "tags": ["pre-partition", "initial"]
            }
            response = await self.client.post(
                f"{self.api_url}/documents",
                json=doc_data,
                headers=headers
            )
            if response.status_code in [200, 201]:
                doc = response.json()
                self.state["pre_partition_doc"] = doc.get("id")
                await self.record_result("Documento Inicial", True, f"ID: {doc.get('id')}")
            else:
                await self.record_result("Documento Inicial", False, f"Error: {response.text}")
        except Exception as e:
            await self.record_result("Documento Inicial", False, str(e))
        
        # Esperar sincronización
        self.log("Esperando 15 segundos para sincronización inicial...")
        await asyncio.sleep(15)
        
        # Guardar estado
        self.state["phase_prepare_completed"] = True
        self.state["prepare_time"] = datetime.now().isoformat()
        self.save_state()
        
        self.log("")
        self.log("=" * 60, "SUCCESS")
        self.log("FASE 1 COMPLETADA", "SUCCESS")
        self.log("=" * 60, "SUCCESS")
        self.log("")
        self.log("PRÓXIMOS PASOS:", "PHASE")
        self.log("1. Desconecta uno de los nodos de la WiFi")
        self.log("2. En el nodo CON conexión, ejecuta:")
        self.log(f"   python scripts/test_scenario_2.py --phase partition --base-url {self.base_url} --node-name nodoConectado")
        self.log("3. En el nodo SIN conexión (via localhost), ejecuta:")
        self.log("   python scripts/test_scenario_2.py --phase partition --base-url https://localhost:443 --node-name nodoAislado")
        self.log("4. Reconecta el nodo a la WiFi")
        self.log("5. Espera 90-120 segundos para reconciliación")
        self.log(f"6. Ejecuta: python scripts/test_scenario_2.py --phase verify --base-url {self.base_url}")
        
        return True
    
    # ==================== FASE 2: PARTITION ====================
    
    async def phase_partition(self):
        """Fase durante partición: crear documentos localmente"""
        self.log("=" * 60, "PHASE")
        self.log(f"FASE 2: DURANTE PARTICIÓN (Nodo: {self.node_name})", "PHASE")
        self.log("=" * 60, "PHASE")
        self.log(f"URL: {self.base_url}")
        
        # Cargar estado
        if not self.load_state():
            self.log("ADVERTENCIA: No se encontró estado de fase 1. Intentando login directo...", "WARN")
            self.state = {}
        
        # Health check local
        try:
            response = await self.client.get(f"{self.api_url}/health")
            if response.status_code != 200:
                await self.record_result("Health Check Local", False, f"Status {response.status_code}")
                return False
            await self.record_result("Health Check Local", True, "Nodo funcionando")
        except Exception as e:
            await self.record_result("Health Check Local", False, str(e))
            return False
        
        # Login
        try:
            login_resp = await self.client.post(
                f"{self.api_url}/auth/login",
                data={"username": TEST_USER["username"], "password": TEST_USER["password"]}
            )
            if login_resp.status_code != 200:
                # Si el usuario no existe en este nodo (partición), crear
                self.log("Usuario no encontrado, intentando registrar...", "WARN")
                reg_resp = await self.client.post(
                    f"{self.api_url}/auth/register",
                    json=TEST_USER
                )
                login_resp = await self.client.post(
                    f"{self.api_url}/auth/login",
                    data={"username": TEST_USER["username"], "password": TEST_USER["password"]}
                )
            
            token = login_resp.json().get("access_token")
            await self.record_result("Login Local", True, "OK")
        except Exception as e:
            await self.record_result("Login Local", False, str(e))
            return False
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Crear documento único para este nodo
        try:
            unique_doc = {
                "title": f"Documento Durante Partición - {self.node_name}",
                "content": f"Este documento fue creado en {self.node_name} DURANTE la partición de red. Timestamp: {datetime.now().isoformat()}",
                "tags": ["partition", self.node_name, "unique"]
            }
            response = await self.client.post(
                f"{self.api_url}/documents",
                json=unique_doc,
                headers=headers
            )
            if response.status_code in [200, 201]:
                doc = response.json()
                await self.record_result(f"Documento Único ({self.node_name})", True, f"ID: {doc.get('id')}")
                
                # Guardar en estado
                if "partition_docs" not in self.state:
                    self.state["partition_docs"] = {}
                self.state["partition_docs"][self.node_name] = doc.get("id")
            else:
                await self.record_result(f"Documento Único ({self.node_name})", False, f"Error: {response.text}")
        except Exception as e:
            await self.record_result(f"Documento Único ({self.node_name})", False, str(e))
        
        # Crear documento IDÉNTICO (para probar deduplicación)
        try:
            response = await self.client.post(
                f"{self.api_url}/documents",
                json=IDENTICAL_DOC,
                headers=headers
            )
            if response.status_code in [200, 201]:
                doc = response.json()
                await self.record_result("Documento Idéntico", True, f"ID: {doc.get('id')}")
                
                if "identical_docs" not in self.state:
                    self.state["identical_docs"] = {}
                self.state["identical_docs"][self.node_name] = doc.get("id")
            else:
                # Puede fallar si ya existe (deduplicación funcionando)
                if "already exists" in response.text.lower() or response.status_code == 409:
                    await self.record_result("Documento Idéntico", True, "Ya existe (deduplicación activa)")
                else:
                    await self.record_result("Documento Idéntico", False, f"Error: {response.text}")
        except Exception as e:
            await self.record_result("Documento Idéntico", False, str(e))
        
        # Listar documentos actuales en este nodo
        try:
            response = await self.client.get(f"{self.api_url}/documents", headers=headers)
            if response.status_code == 200:
                docs = response.json()
                doc_list = docs.get("documents", docs) if isinstance(docs, dict) else docs
                self.log(f"Documentos visibles en {self.node_name}: {len(doc_list)}")
                for d in doc_list:
                    self.log(f"  - {d.get('title')} (ID: {d.get('id')[:8]}...)")
        except Exception as e:
            self.log(f"Error listando documentos: {e}", "WARN")
        
        # Guardar estado
        self.state[f"phase_partition_{self.node_name}_completed"] = True
        self.state[f"partition_time_{self.node_name}"] = datetime.now().isoformat()
        self.save_state()
        
        self.log("")
        self.log("=" * 60, "SUCCESS")
        self.log(f"FASE 2 COMPLETADA (Nodo: {self.node_name})", "SUCCESS")
        self.log("=" * 60, "SUCCESS")
        self.log("")
        self.log("PRÓXIMOS PASOS:", "PHASE")
        self.log("1. Si hay otros nodos aislados, ejecuta este script en cada uno")
        self.log("2. Reconecta todos los nodos a la WiFi")
        self.log("3. Espera 90-120 segundos para reconciliación")
        self.log("4. Ejecuta la fase verify")
        
        return True
    
    # ==================== FASE 3: VERIFY ====================
    
    async def phase_verify(self):
        """Fase de verificación post-reconciliación"""
        self.log("=" * 60, "PHASE")
        self.log("FASE 3: VERIFICACIÓN POST-RECONCILIACIÓN", "PHASE")
        self.log("=" * 60, "PHASE")
        self.log(f"URL: {self.base_url}")
        
        # Cargar estado
        if not self.load_state():
            self.log("No se encontró estado previo. Ejecuta las fases anteriores primero.", "ERROR")
            return False
        
        # Health check
        try:
            response = await self.client.get(f"{self.api_url}/health")
            await self.record_result("Health Check", response.status_code == 200, 
                                    "OK" if response.status_code == 200 else f"Status {response.status_code}")
        except Exception as e:
            await self.record_result("Health Check", False, str(e))
            return False
        
        # Login
        try:
            login_resp = await self.client.post(
                f"{self.api_url}/auth/login",
                data={"username": TEST_USER["username"], "password": TEST_USER["password"]}
            )
            token = login_resp.json().get("access_token")
            await self.record_result("Login", True, "OK")
        except Exception as e:
            await self.record_result("Login", False, str(e))
            return False
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Obtener todos los documentos
        try:
            response = await self.client.get(f"{self.api_url}/documents", headers=headers)
            if response.status_code != 200:
                await self.record_result("Listar Documentos", False, f"Error: {response.text}")
                return False
            
            docs = response.json()
            doc_list = docs.get("documents", docs) if isinstance(docs, dict) else docs
            await self.record_result("Listar Documentos", True, f"Total: {len(doc_list)}")
        except Exception as e:
            await self.record_result("Listar Documentos", False, str(e))
            return False
        
        # Verificar documentos de cada fase
        self.log("\nAnálisis de documentos:")
        
        # Documento pre-partición
        pre_partition_found = any(
            "Pre-Partición" in d.get("title", "") or 
            d.get("id") == self.state.get("pre_partition_doc")
            for d in doc_list
        )
        await self.record_result("Doc Pre-Partición", pre_partition_found, 
                                "Encontrado" if pre_partition_found else "NO ENCONTRADO")
        
        # Documentos de partición de cada nodo
        partition_docs = self.state.get("partition_docs", {})
        for node_name, doc_id in partition_docs.items():
            found = any(d.get("id") == doc_id or node_name in d.get("title", "") for d in doc_list)
            await self.record_result(f"Doc Partición ({node_name})", found,
                                    "Encontrado (reconciliación OK)" if found else "NO ENCONTRADO")
        
        # Verificar descarga de documentos (GET por ID)
        self.log("\nVerificando descarga de documentos:")
        if doc_list:
            test_doc = doc_list[0]
            test_doc_id = test_doc.get("id")
            
            try:
                response = await self.client.get(
                    f"{self.api_url}/documents/{test_doc_id}",
                    headers=headers
                )
                if response.status_code == 200:
                    doc_data = response.json()
                    has_content = bool(doc_data.get("content") or doc_data.get("title"))
                    await self.record_result("GET documento", True, 
                                            f"OK ({doc_data.get('title', '')[:30]}...)")
                else:
                    await self.record_result("GET documento", False, f"Error: {response.status_code}")
            except Exception as e:
                await self.record_result("GET documento", False, str(e))
            
            # Probar download endpoint (todos los docs ahora son descargables)
            try:
                download_resp = await self.client.get(
                    f"{self.api_url}/documents/{test_doc_id}/download",
                    headers=headers
                )
                if download_resp.status_code == 200:
                    await self.record_result("Download archivo", True, 
                                            f"OK ({len(download_resp.content)} bytes)")
                else:
                    await self.record_result("Download archivo", False, 
                                            f"Error: {download_resp.status_code}")
            except Exception as e:
                await self.record_result("Download archivo", False, str(e))
        
        # Verificar DEDUPLICACIÓN
        identical_docs_found = [d for d in doc_list if "IDENTICAL" in d.get("title", "")]
        identical_count = len(identical_docs_found)
        
        if identical_count == 1:
            await self.record_result("Deduplicación", True, 
                                    "ÉXITO: Solo existe 1 documento idéntico")
        elif identical_count == 0:
            await self.record_result("Deduplicación", False, 
                                    "No se encontró el documento idéntico")
        else:
            await self.record_result("Deduplicación", False, 
                                    f"FALLO: Existen {identical_count} documentos idénticos (deberían ser 1)")
            self.log("Documentos idénticos encontrados:", "WARN")
            for d in identical_docs_found:
                self.log(f"  - ID: {d.get('id')}", "WARN")
        
        # Mostrar todos los documentos
        self.log("\nListado completo de documentos:")
        for d in doc_list:
            tags = d.get("tags", [])
            self.log(f"  - {d.get('title')}")
            self.log(f"    ID: {d.get('id')}, Tags: {tags}")
        
        # Resumen
        self.log("")
        self.log("=" * 60)
        self.log("RESUMEN DE RESULTADOS")
        self.log("=" * 60)
        
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        
        for r in self.results:
            status = "✓" if r.passed else "✗"
            self.log(f"  {status} {r.name}: {r.message}")
        
        self.log("")
        self.log(f"Total: {passed} pasaron, {failed} fallaron")
        
        # Limpiar estado si todo OK
        if failed == 0:
            self.log("\n¡Todas las verificaciones pasaron! Limpiando estado...", "SUCCESS")
            if os.path.exists(STATE_FILE):
                os.remove(STATE_FILE)
        
        return failed == 0
    
    # ==================== CLEANUP ====================
    
    async def cleanup(self):
        """Limpiar documentos de prueba"""
        self.log("Limpiando documentos de prueba...")
        
        try:
            login_resp = await self.client.post(
                f"{self.api_url}/auth/login",
                data={"username": TEST_USER["username"], "password": TEST_USER["password"]}
            )
            if login_resp.status_code != 200:
                self.log("No se pudo hacer login para cleanup", "WARN")
                return
            
            token = login_resp.json().get("access_token")
            headers = {"Authorization": f"Bearer {token}"}
            
            # Obtener documentos
            response = await self.client.get(f"{self.api_url}/documents", headers=headers)
            if response.status_code != 200:
                return
            
            docs = response.json()
            doc_list = docs.get("documents", docs) if isinstance(docs, dict) else docs
            
            # Eliminar documentos de prueba
            deleted = 0
            for d in doc_list:
                tags = d.get("tags", [])
                if any(t in ["partition", "pre-partition", "dedup-test", "identical"] for t in tags):
                    del_resp = await self.client.delete(
                        f"{self.api_url}/documents/{d.get('id')}",
                        headers=headers
                    )
                    if del_resp.status_code in [200, 204]:
                        deleted += 1
            
            self.log(f"Eliminados {deleted} documentos de prueba")
            
            # Limpiar estado
            if os.path.exists(STATE_FILE):
                os.remove(STATE_FILE)
                self.log("Estado limpiado")
                
        except Exception as e:
            self.log(f"Error durante cleanup: {e}", "WARN")
    
    # ==================== MODO GUIADO ====================
    
    async def countdown_with_instructions(self, total_seconds: int, phase_name: str, instructions: List[str]):
        """Muestra cuenta regresiva con instrucciones"""
        self.log("")
        self.log("=" * 70, "PHASE")
        self.log(f"⏱️  TIEMPO PARA: {phase_name}", "PHASE")
        self.log("=" * 70, "PHASE")
        self.log("")
        self.log("INSTRUCCIONES:", "PHASE")
        for i, instruction in enumerate(instructions, 1):
            self.log(f"  {i}. {instruction}", "PHASE")
        self.log("")
        self.log(f"Tiempo disponible: {total_seconds // 60} minutos")
        self.log("Presiona Ctrl+C para saltar la espera si ya terminaste")
        self.log("")
        
        try:
            start_time = time.time()
            while True:
                elapsed = time.time() - start_time
                remaining = total_seconds - int(elapsed)
                
                if remaining <= 0:
                    break
                
                mins, secs = divmod(remaining, 60)
                
                # Mostrar progreso cada 30 segundos o en momentos clave
                if remaining % 30 == 0 or remaining <= 10:
                    self.log(f"⏳ Tiempo restante: {mins:02d}:{secs:02d}")
                
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            self.log("\n⏭️  Espera saltada por el usuario", "WARN")
        
        self.log("")
        self.log(f"✅ Tiempo para '{phase_name}' completado", "SUCCESS")
        self.log("")
    
    async def run_guided_test(self):
        """
        Ejecuta el test completo de forma guiada con tiempos de espera.
        """
        self.log("")
        self.log("╔" + "═" * 68 + "╗", "PHASE")
        self.log("║" + " " * 15 + "TEST DE PARTICIÓN DE RED - MODO GUIADO" + " " * 14 + "║", "PHASE")
        self.log("╚" + "═" * 68 + "╝", "PHASE")
        self.log("")
        self.log(f"URL Base: {self.base_url}")
        self.log(f"Tiempo por fase: {WAIT_TIME_PARTITION // 60} minutos")
        self.log("")
        
        # ============ FASE 1: PREPARACIÓN ============
        self.log("━" * 70, "PHASE")
        self.log("INICIANDO FASE 1: PREPARACIÓN", "PHASE")
        self.log("━" * 70, "PHASE")
        
        # Ejecutar preparación
        prepare_success = await self.phase_prepare()
        if not prepare_success:
            self.log("❌ Fase de preparación falló. Abortando test.", "ERROR")
            return False
        
        # También crear documento desde este nodo (nodo conectado)
        self.node_name = "nodoConectado"
        
        # ============ ESPERA PARA PARTICIÓN ============
        partition_instructions = [
            "Desconecta la WiFi de UNO de los nodos del cluster",
            "En ese nodo AISLADO, abre una terminal",
            "Ejecuta el siguiente comando EN EL NODO AISLADO:",
            f"   python scripts/test_scenario_2.py --phase partition --base-url https://localhost:443 --node-name nodoAislado",
            "El nodo aislado creará documentos localmente (incluyendo el doc IDENTICAL)",
            "Mientras tanto, este script creará documentos en el nodo conectado"
        ]
        
        # Crear documentos en paralelo mientras esperamos
        self.log("")
        self.log("Creando documentos en el nodo CONECTADO...", "PHASE")
        await self.phase_partition()  # Crear docs en este nodo
        
        await self.countdown_with_instructions(
            WAIT_TIME_PARTITION, 
            "CREAR PARTICIÓN Y DOCUMENTOS",
            partition_instructions
        )
        
        # ============ ESPERA PARA RECONCILIACIÓN ============
        reconciliation_instructions = [
            "RECONECTA el nodo aislado a la WiFi",
            "Verifica que el nodo puede hacer ping a los otros nodos",
            "El sistema comenzará a sincronizar automáticamente",
            "Espera a que los logs muestren mensajes de gossip/sync",
            "La reconciliación toma aproximadamente 60-90 segundos después de reconectar"
        ]
        
        await self.countdown_with_instructions(
            WAIT_TIME_RECONCILIATION,
            "RECONEXIÓN Y RECONCILIACIÓN", 
            reconciliation_instructions
        )
        
        # ============ FASE 3: VERIFICACIÓN ============
        self.log("━" * 70, "PHASE")
        self.log("INICIANDO FASE 3: VERIFICACIÓN", "PHASE")
        self.log("━" * 70, "PHASE")
        
        # Limpiar resultados previos para la verificación
        self.results = []
        
        verify_success = await self.phase_verify()
        
        # ============ RESUMEN FINAL ============
        self.log("")
        self.log("╔" + "═" * 68 + "╗", "PHASE")
        self.log("║" + " " * 20 + "RESUMEN FINAL DEL TEST" + " " * 26 + "║", "PHASE")
        self.log("╚" + "═" * 68 + "╝", "PHASE")
        self.log("")
        
        if verify_success:
            self.log("🎉 ¡TEST COMPLETADO EXITOSAMENTE!", "SUCCESS")
            self.log("")
            self.log("El sistema demostró:", "SUCCESS")
            self.log("  ✓ Tolerancia a particiones de red", "SUCCESS")
            self.log("  ✓ Operación independiente durante aislamiento", "SUCCESS")
            self.log("  ✓ Reconciliación automática post-reconexión", "SUCCESS")
            self.log("  ✓ Deduplicación de documentos idénticos", "SUCCESS")
            self.log("  ✓ Descarga de documentos funcional", "SUCCESS")
        else:
            self.log("❌ TEST COMPLETADO CON ERRORES", "ERROR")
            self.log("")
            self.log("Revisa los resultados anteriores para identificar los problemas.", "ERROR")
            self.log("Posibles causas:", "WARN")
            self.log("  - El nodo aislado no ejecutó la fase partition", "WARN")
            self.log("  - No se esperó suficiente tiempo para reconciliación", "WARN")
            self.log("  - Problemas de conectividad post-reconexión", "WARN")
        
        # Preguntar si limpiar
        self.log("")
        try:
            response = input("¿Deseas limpiar los documentos de prueba? (s/N): ")
            if response.lower() in ['s', 'si', 'yes', 'y']:
                await self.cleanup()
        except (KeyboardInterrupt, EOFError):
            self.log("\nLimpieza omitida", "WARN")
        
        return verify_success


async def main():
    parser = argparse.ArgumentParser(
        description="Test Scenario 2: Network Partition and Reconciliation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
═══════════════════════════════════════════════════════════════════════════════
MODO GUIADO (RECOMENDADO):
═══════════════════════════════════════════════════════════════════════════════

  python scripts/test_scenario_2.py --guided --base-url https://192.168.1.10:443

  Opciones adicionales para modo guiado:
    --wait-time 5    # Cambiar tiempo de espera a 5 minutos (default: 10)

═══════════════════════════════════════════════════════════════════════════════
MODO MANUAL (FASES SEPARADAS):
═══════════════════════════════════════════════════════════════════════════════

  1. Preparación (desde máquina con acceso):
     python scripts/test_scenario_2.py --phase prepare --base-url https://192.168.1.10:443

  2. Durante partición - en cada nodo:
     # Nodo conectado:
     python scripts/test_scenario_2.py --phase partition --base-url https://192.168.1.10:443 --node-name nodoA
     # Nodo aislado (acceder via localhost):
     python scripts/test_scenario_2.py --phase partition --base-url https://localhost:443 --node-name nodoB

  3. Verificación (después de reconectar):
     python scripts/test_scenario_2.py --phase verify --base-url https://192.168.1.10:443

  4. Limpieza (opcional):
     python scripts/test_scenario_2.py --cleanup --base-url https://192.168.1.10:443
        """
    )
    
    # Modos de ejecución
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--guided", action="store_true", 
                           help="Modo guiado: ejecuta todo el test con tiempos de espera interactivos")
    mode_group.add_argument("--phase", choices=["prepare", "partition", "verify"], 
                           help="Modo manual: ejecutar una fase específica")
    mode_group.add_argument("--cleanup", action="store_true", 
                           help="Limpiar documentos de prueba")
    
    # Parámetros comunes
    parser.add_argument("--base-url", required=True, 
                       help="URL base del nodo (ej: https://192.168.1.10:443)")
    parser.add_argument("--node-name", default="default", 
                       help="Nombre identificador del nodo (para fase partition)")
    parser.add_argument("--wait-time", type=int, default=10,
                       help="Tiempo de espera en minutos para cada fase (default: 10)")
    
    args = parser.parse_args()
    
    # Desactivar warnings de SSL para certificados self-signed
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    # Ajustar tiempos de espera si se especificó
    global WAIT_TIME_PARTITION, WAIT_TIME_RECONCILIATION
    if args.wait_time != 10:
        WAIT_TIME_PARTITION = args.wait_time * 60
        WAIT_TIME_RECONCILIATION = args.wait_time * 60
    
    tester = PartitionTester(args.base_url, args.node_name)
    
    try:
        if args.cleanup:
            await tester.cleanup()
            return
        
        if args.guided:
            # Modo guiado
            success = await tester.run_guided_test()
            sys.exit(0 if success else 1)
        
        elif args.phase:
            # Modo manual por fases
            if args.phase == "prepare":
                success = await tester.phase_prepare()
            elif args.phase == "partition":
                success = await tester.phase_partition()
            elif args.phase == "verify":
                success = await tester.phase_verify()
            sys.exit(0 if success else 1)
        
        else:
            parser.print_help()
            print("\n" + "=" * 70)
            print("ERROR: Debes especificar un modo de ejecución:")
            print("  --guided     Para test guiado con tiempos de espera")
            print("  --phase X    Para ejecutar una fase específica")
            print("  --cleanup    Para limpiar documentos de prueba")
            print("=" * 70)
            sys.exit(1)
        
    finally:
        await tester.close()


if __name__ == "__main__":
    asyncio.run(main())
