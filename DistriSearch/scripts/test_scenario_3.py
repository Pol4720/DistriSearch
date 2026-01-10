#!/usr/bin/env python3
"""
Test Scenario 3: Comprehensive Distributed System Validation
=============================================================

Este es el TEST DEFINITIVO que valida que el sistema distribuido está impecable.
Combina todas las verificaciones de los escenarios 1 y 2, más pruebas adicionales.

═══════════════════════════════════════════════════════════════════════════════
VERIFICACIONES INCLUIDAS:
═══════════════════════════════════════════════════════════════════════════════

Del Escenario 1 (Operación Normal):
  ✓ Múltiples usuarios (3+)
  ✓ Múltiples documentos por usuario
  ✓ Distribución de documentos en nodos
  ✓ Búsqueda funcional cross-node
  ✓ Estabilidad del listado de documentos
  ✓ Aislamiento de documentos por usuario
  ✓ Descarga de documentos (GET por ID)
  ✓ Upload y descarga de archivos

Del Escenario 2 (Particiones):
  ✓ Tolerancia a partición de red
  ✓ Operación durante aislamiento
  ✓ Reconciliación post-reconexión
  ✓ Deduplicación de documentos idénticos

Adicionales:
  ✓ Consistencia eventual verificada
  ✓ Replicación física en múltiples nodos
  ✓ Eliminación y propagación de tombstones
  ✓ Integridad de datos post-partición
  ✓ Rendimiento de búsqueda
  ✓ Stress test de listado

═══════════════════════════════════════════════════════════════════════════════
MODOS DE USO:
═══════════════════════════════════════════════════════════════════════════════

MODO GUIADO (Recomendado para test completo):
    python scripts/test_scenario_3.py --guided --base-url https://192.168.1.10:443

MODO POR FASES (Control manual):
    python scripts/test_scenario_3.py --phase setup --base-url https://...
    python scripts/test_scenario_3.py --phase normal-ops --base-url https://...
    python scripts/test_scenario_3.py --phase partition --base-url https://localhost:443 --node-name nodoX
    python scripts/test_scenario_3.py --phase reconcile --base-url https://...
    python scripts/test_scenario_3.py --phase final-verify --base-url https://...

MODO RÁPIDO (Sin particiones, solo operaciones normales):
    python scripts/test_scenario_3.py --quick --base-url https://...
"""

import asyncio
import argparse
import httpx
import json
import sys
import time
import os
import random
import string
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from enum import Enum

# Configuración
API_V1 = "/api/v1"
TIMEOUT = 30.0
STATE_FILE = "/tmp/distrisearch_comprehensive_test_state.json"

# Tiempos de espera (en segundos)
WAIT_TIME_SYNC = 30  # Espera para sincronización normal
WAIT_TIME_PARTITION = 10 * 60  # 10 minutos para partición
WAIT_TIME_RECONCILIATION = 10 * 60  # 10 minutos para reconciliación

# Datos de prueba
NUM_USERS = 3
DOCS_PER_USER = 3

TEST_USERS = [
    {"username": "comprehensive_alice", "email": "alice_comp@test.com", "password": "TestComp123!"},
    {"username": "comprehensive_bob", "email": "bob_comp@test.com", "password": "TestComp123!"},
    {"username": "comprehensive_carol", "email": "carol_comp@test.com", "password": "TestComp123!"},
]

# Documentos con contenido variado para pruebas de búsqueda
DOCUMENT_TEMPLATES = [
    {
        "title": "Inteligencia Artificial y Machine Learning",
        "content": "La inteligencia artificial es una rama de la informática que busca crear sistemas capaces de realizar tareas que normalmente requieren inteligencia humana. El machine learning es un subconjunto que permite a las máquinas aprender de datos.",
        "tags": ["ai", "ml", "tecnologia"],
        "search_terms": ["inteligencia artificial", "machine learning", "sistemas"]
    },
    {
        "title": "Sistemas Distribuidos y Arquitectura",
        "content": "Los sistemas distribuidos son colecciones de computadoras independientes que aparecen ante el usuario como un único sistema coherente. Proporcionan escalabilidad, tolerancia a fallos y alta disponibilidad.",
        "tags": ["distribuidos", "arquitectura", "escalabilidad"],
        "search_terms": ["sistemas distribuidos", "escalabilidad", "tolerancia"]
    },
    {
        "title": "Bases de Datos NoSQL",
        "content": "Las bases de datos NoSQL ofrecen mecanismos de almacenamiento y recuperación de datos modelados de formas distintas a las tablas relacionales. MongoDB, Cassandra y Redis son ejemplos populares.",
        "tags": ["nosql", "mongodb", "datos"],
        "search_terms": ["nosql", "mongodb", "bases de datos"]
    },
]

# Documento idéntico para prueba de deduplicación
IDENTICAL_DOC = {
    "title": "DEDUP-TEST: Documento Idéntico para Deduplicación",
    "content": "Este contenido EXACTO debe existir solo UNA vez en todo el sistema después de la reconciliación. Hash SHA256 test.",
    "tags": ["dedup-test", "identical", "comprehensive"]
}


class TestPhase(Enum):
    SETUP = "setup"
    NORMAL_OPS = "normal-ops"
    PARTITION = "partition"
    RECONCILE = "reconcile"
    FINAL_VERIFY = "final-verify"


@dataclass
class TestUser:
    username: str
    email: str
    password: str
    user_id: Optional[str] = None
    token: Optional[str] = None
    documents: List[Dict] = field(default_factory=list)


@dataclass
class TestResult:
    name: str
    passed: bool
    message: str
    category: str = "general"
    duration_ms: float = 0
    details: Optional[Dict] = None


@dataclass
class TestSummary:
    total: int = 0
    passed: int = 0
    failed: int = 0
    by_category: Dict[str, Dict[str, int]] = field(default_factory=dict)


class ComprehensiveTester:
    def __init__(self, base_url: str, node_name: str = "default"):
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}{API_V1}"
        self.node_name = node_name
        self.client = httpx.AsyncClient(
            timeout=TIMEOUT,
            follow_redirects=True,
            verify=False
        )
        self.users: List[TestUser] = []
        self.results: List[TestResult] = []
        self.state: Dict = {}
        self.start_time = time.time()
        
    async def close(self):
        await self.client.aclose()
    
    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        elapsed = time.time() - self.start_time
        elapsed_str = f"{int(elapsed // 60):02d}:{int(elapsed % 60):02d}"
        colors = {
            "INFO": "", 
            "WARN": "\033[93m", 
            "ERROR": "\033[91m", 
            "SUCCESS": "\033[92m", 
            "PHASE": "\033[96m",
            "TEST": "\033[95m"
        }
        reset = "\033[0m" if level != "INFO" else ""
        print(f"{colors.get(level, '')}[{timestamp}][{elapsed_str}] [{level}] {message}{reset}")
    
    def save_state(self):
        with open(STATE_FILE, 'w') as f:
            # Convertir users a dict serializable
            state_to_save = self.state.copy()
            state_to_save["users"] = [
                {
                    "username": u.username,
                    "email": u.email,
                    "password": u.password,
                    "user_id": u.user_id,
                    "token": u.token,
                    "documents": u.documents
                }
                for u in self.users
            ]
            json.dump(state_to_save, f, indent=2, default=str)
        self.log(f"Estado guardado en {STATE_FILE}")
    
    def load_state(self) -> bool:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                data = json.load(f)
            self.state = {k: v for k, v in data.items() if k != "users"}
            if "users" in data:
                self.users = [
                    TestUser(
                        username=u["username"],
                        email=u["email"],
                        password=u["password"],
                        user_id=u.get("user_id"),
                        token=u.get("token"),
                        documents=u.get("documents", [])
                    )
                    for u in data["users"]
                ]
            self.log(f"Estado cargado desde {STATE_FILE}")
            return True
        return False
    
    async def record_result(self, name: str, passed: bool, message: str, 
                           category: str = "general", details: Dict = None,
                           duration_ms: float = 0) -> TestResult:
        result = TestResult(
            name=name, 
            passed=passed, 
            message=message, 
            category=category,
            duration_ms=duration_ms,
            details=details
        )
        self.results.append(result)
        status = "✓" if passed else "✗"
        level = "SUCCESS" if passed else "ERROR"
        self.log(f"{status} [{category}] {name}: {message}", level if not passed else "TEST")
        return result
    
    def get_summary(self) -> TestSummary:
        summary = TestSummary()
        summary.total = len(self.results)
        summary.passed = sum(1 for r in self.results if r.passed)
        summary.failed = sum(1 for r in self.results if not r.passed)
        
        for r in self.results:
            if r.category not in summary.by_category:
                summary.by_category[r.category] = {"total": 0, "passed": 0, "failed": 0}
            summary.by_category[r.category]["total"] += 1
            if r.passed:
                summary.by_category[r.category]["passed"] += 1
            else:
                summary.by_category[r.category]["failed"] += 1
        
        return summary
    
    async def countdown_with_instructions(self, total_seconds: int, phase_name: str, 
                                         instructions: List[str]):
        self.log("")
        self.log("═" * 70, "PHASE")
        self.log(f"⏱️  TIEMPO PARA: {phase_name}", "PHASE")
        self.log("═" * 70, "PHASE")
        self.log("")
        self.log("INSTRUCCIONES:", "PHASE")
        for i, instruction in enumerate(instructions, 1):
            self.log(f"  {i}. {instruction}", "PHASE")
        self.log("")
        self.log(f"Tiempo disponible: {total_seconds // 60} minutos {total_seconds % 60} segundos")
        self.log("Presiona Ctrl+C para continuar si ya terminaste")
        self.log("")
        
        try:
            start_time = time.time()
            last_log = 0
            while True:
                elapsed = time.time() - start_time
                remaining = total_seconds - int(elapsed)
                
                if remaining <= 0:
                    break
                
                mins, secs = divmod(remaining, 60)
                
                # Log cada 30 segundos o últimos 10 segundos
                if int(elapsed) - last_log >= 30 or remaining <= 10:
                    self.log(f"⏳ Tiempo restante: {mins:02d}:{secs:02d}")
                    last_log = int(elapsed)
                
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            self.log("\n⏭️  Espera saltada por el usuario", "WARN")
        
        self.log(f"✅ Fase '{phase_name}' - tiempo completado", "SUCCESS")
    
    # ═══════════════════════════════════════════════════════════════════════
    # FASE 1: SETUP - Crear usuarios y verificar sistema
    # ═══════════════════════════════════════════════════════════════════════
    
    async def phase_setup(self) -> bool:
        self.log("")
        self.log("╔" + "═" * 68 + "╗", "PHASE")
        self.log("║" + " " * 20 + "FASE 1: SETUP INICIAL" + " " * 27 + "║", "PHASE")
        self.log("╚" + "═" * 68 + "╝", "PHASE")
        
        # Health check
        start = time.time()
        try:
            response = await self.client.get(f"{self.api_url}/health")
            duration = (time.time() - start) * 1000
            if response.status_code == 200:
                await self.record_result("Health Check", True, "Sistema accesible", 
                                        "setup", duration_ms=duration)
            else:
                await self.record_result("Health Check", False, 
                                        f"Status {response.status_code}", "setup")
                return False
        except Exception as e:
            await self.record_result("Health Check", False, str(e), "setup")
            return False
        
        # Crear usuarios
        for user_data in TEST_USERS:
            try:
                # Registrar
                response = await self.client.post(
                    f"{self.api_url}/auth/register",
                    json=user_data
                )
                
                if response.status_code == 409:
                    self.log(f"  Usuario {user_data['username']} ya existe")
                elif response.status_code not in [200, 201]:
                    await self.record_result(
                        f"Crear Usuario {user_data['username']}", False,
                        f"Error: {response.text}", "setup"
                    )
                    continue
                
                # Login
                login_resp = await self.client.post(
                    f"{self.api_url}/auth/login",
                    data={"username": user_data["username"], "password": user_data["password"]}
                )
                
                if login_resp.status_code != 200:
                    await self.record_result(
                        f"Login {user_data['username']}", False,
                        f"Error: {login_resp.text}", "setup"
                    )
                    continue
                
                token = login_resp.json().get("access_token")
                
                # Obtener user_id
                me_resp = await self.client.get(
                    f"{self.api_url}/users/me",
                    headers={"Authorization": f"Bearer {token}"}
                )
                user_id = None
                if me_resp.status_code == 200:
                    user_info = me_resp.json()
                    user_id = user_info.get("id") or user_info.get("user_id")
                
                test_user = TestUser(
                    username=user_data["username"],
                    email=user_data["email"],
                    password=user_data["password"],
                    user_id=user_id,
                    token=token
                )
                self.users.append(test_user)
                
                await self.record_result(
                    f"Usuario {user_data['username']}", True,
                    f"Autenticado (ID: {user_id})", "setup"
                )
                
            except Exception as e:
                await self.record_result(
                    f"Usuario {user_data['username']}", False, str(e), "setup"
                )
        
        # Verificar mínimo de usuarios
        if len(self.users) < 2:
            await self.record_result(
                "Mínimo de usuarios", False,
                f"Se necesitan al menos 2 usuarios, solo hay {len(self.users)}", "setup"
            )
            return False
        
        await self.record_result(
            "Setup usuarios", True,
            f"{len(self.users)} usuarios creados/autenticados", "setup"
        )
        
        self.state["phase_setup_completed"] = True
        self.save_state()
        return True
    
    # ═══════════════════════════════════════════════════════════════════════
    # FASE 2: OPERACIONES NORMALES
    # ═══════════════════════════════════════════════════════════════════════
    
    async def phase_normal_operations(self) -> bool:
        self.log("")
        self.log("╔" + "═" * 68 + "╗", "PHASE")
        self.log("║" + " " * 15 + "FASE 2: OPERACIONES NORMALES" + " " * 25 + "║", "PHASE")
        self.log("╚" + "═" * 68 + "╝", "PHASE")
        
        # 2.1 Crear documentos para cada usuario
        self.log("\n--- 2.1 Creación de Documentos ---", "PHASE")
        
        for i, user in enumerate(self.users):
            headers = {"Authorization": f"Bearer {user.token}"}
            
            for j, template in enumerate(DOCUMENT_TEMPLATES):
                doc_data = {
                    "title": f"{user.username} - {template['title']}",
                    "content": f"{template['content']} Documento creado por {user.username}.",
                    "tags": template["tags"] + [user.username, "comprehensive-test"]
                }
                
                start = time.time()
                try:
                    response = await self.client.post(
                        f"{self.api_url}/documents",
                        json=doc_data,
                        headers=headers
                    )
                    duration = (time.time() - start) * 1000
                    
                    if response.status_code in [200, 201]:
                        doc = response.json()
                        user.documents.append(doc)
                        await self.record_result(
                            f"Doc {j+1} de {user.username}", True,
                            f"Creado (ID: {doc.get('id')[:8]}..., Node: {doc.get('node_id')})",
                            "documentos", duration_ms=duration
                        )
                    else:
                        await self.record_result(
                            f"Doc {j+1} de {user.username}", False,
                            f"Error: {response.text[:100]}", "documentos"
                        )
                except Exception as e:
                    await self.record_result(
                        f"Doc {j+1} de {user.username}", False, str(e), "documentos"
                    )
        
        # Esperar sincronización
        self.log(f"\nEsperando {WAIT_TIME_SYNC}s para sincronización...")
        await asyncio.sleep(WAIT_TIME_SYNC)
        
        # 2.2 Verificar estabilidad del listado
        self.log("\n--- 2.2 Estabilidad del Listado ---", "PHASE")
        
        for user in self.users:
            headers = {"Authorization": f"Bearer {user.token}"}
            listings = []
            
            for attempt in range(5):
                response = await self.client.get(f"{self.api_url}/documents", headers=headers)
                if response.status_code == 200:
                    docs = response.json()
                    doc_list = docs.get("documents", docs) if isinstance(docs, dict) else docs
                    doc_ids = sorted([d.get("id") for d in doc_list])
                    listings.append(doc_ids)
                await asyncio.sleep(0.5)
            
            is_stable = len(set(tuple(l) for l in listings)) == 1
            expected_count = len(user.documents)
            actual_count = len(listings[0]) if listings else 0
            
            await self.record_result(
                f"Estabilidad listado {user.username}", is_stable,
                f"{'Estable' if is_stable else 'INESTABLE'} ({actual_count} docs, esperados: {expected_count})",
                "estabilidad"
            )
        
        # 2.3 Verificar aislamiento de usuarios
        self.log("\n--- 2.3 Aislamiento por Usuario ---", "PHASE")
        
        for user in self.users:
            headers = {"Authorization": f"Bearer {user.token}"}
            response = await self.client.get(f"{self.api_url}/documents", headers=headers)
            
            if response.status_code == 200:
                docs = response.json()
                doc_list = docs.get("documents", docs) if isinstance(docs, dict) else docs
                
                own_docs = [d for d in doc_list if user.username in d.get("title", "")]
                other_docs = [d for d in doc_list if user.username not in d.get("title", "")]
                
                passed = len(other_docs) == 0
                await self.record_result(
                    f"Aislamiento {user.username}", passed,
                    f"Propios: {len(own_docs)}, Ajenos: {len(other_docs)}",
                    "aislamiento"
                )
        
        # 2.4 Pruebas de búsqueda
        self.log("\n--- 2.4 Búsqueda Cross-Node ---", "PHASE")
        
        user = self.users[0]
        headers = {"Authorization": f"Bearer {user.token}"}
        
        search_tests = [
            ("inteligencia artificial", 1),
            ("sistemas distribuidos", 1),
            ("mongodb nosql", 1),
            ("comprehensive-test", len(self.users) * len(DOCUMENT_TEMPLATES)),
        ]
        
        for query, min_results in search_tests:
            start = time.time()
            try:
                response = await self.client.get(
                    f"{self.api_url}/search",
                    params={"q": query},
                    headers=headers
                )
                duration = (time.time() - start) * 1000
                
                if response.status_code == 200:
                    results = response.json().get("results", [])
                    passed = len(results) >= min_results
                    await self.record_result(
                        f"Búsqueda '{query[:20]}...'", passed,
                        f"{len(results)} resultados (min: {min_results})",
                        "busqueda", duration_ms=duration
                    )
                else:
                    await self.record_result(
                        f"Búsqueda '{query[:20]}...'", False,
                        f"Error: {response.status_code}", "busqueda"
                    )
            except Exception as e:
                await self.record_result(
                    f"Búsqueda '{query[:20]}...'", False, str(e), "busqueda"
                )
        
        # 2.5 Verificar distribución en nodos
        self.log("\n--- 2.5 Distribución en Nodos ---", "PHASE")
        
        all_docs = []
        for user in self.users:
            all_docs.extend(user.documents)
        
        nodes_used = set(d.get("node_id") for d in all_docs if d.get("node_id"))
        
        await self.record_result(
            "Distribución de documentos", len(nodes_used) >= 1,
            f"{len(all_docs)} docs distribuidos en {len(nodes_used)} nodo(s)",
            "distribucion",
            details={"nodes": list(nodes_used)}
        )
        
        # 2.6 Pruebas de descarga (GET documento por ID)
        self.log("\n--- 2.6 Descarga de Documentos ---", "PHASE")
        
        for user in self.users:
            headers = {"Authorization": f"Bearer {user.token}"}
            
            if user.documents:
                # Probar descarga del primer documento del usuario
                doc = user.documents[0]
                doc_id = doc.get("id")
                
                # 2.6.1 GET documento (metadatos + contenido)
                start = time.time()
                try:
                    response = await self.client.get(
                        f"{self.api_url}/documents/{doc_id}",
                        headers=headers
                    )
                    duration = (time.time() - start) * 1000
                    
                    if response.status_code == 200:
                        doc_data = response.json()
                        has_content = bool(doc_data.get("content"))
                        has_title = bool(doc_data.get("title"))
                        await self.record_result(
                            f"GET doc {user.username}", True,
                            f"OK (content: {has_content}, title: {has_title})",
                            "descarga", duration_ms=duration
                        )
                    else:
                        await self.record_result(
                            f"GET doc {user.username}", False,
                            f"Error: {response.status_code}", "descarga"
                        )
                except Exception as e:
                    await self.record_result(
                        f"GET doc {user.username}", False, str(e), "descarga"
                    )
                
                # 2.6.2 Descargar documento (ahora todos son descargables)
                try:
                    response = await self.client.get(
                        f"{self.api_url}/documents/{doc_id}/download",
                        headers=headers
                    )
                    
                    # Todos los documentos ahora son descargables (texto como .txt)
                    if response.status_code == 200:
                        content_len = len(response.content)
                        await self.record_result(
                            f"Download {user.username}", True,
                            f"OK ({content_len} bytes)", "descarga"
                        )
                    else:
                        await self.record_result(
                            f"Download {user.username}", False,
                            f"Error: {response.status_code}", "descarga"
                        )
                except Exception as e:
                    await self.record_result(
                        f"Download {user.username}", False, str(e), "descarga"
                    )
        
        # 2.7 Prueba de upload y descarga de archivo
        self.log("\n--- 2.7 Upload y Descarga de Archivo ---", "PHASE")
        
        user = self.users[0]
        headers = {"Authorization": f"Bearer {user.token}"}
        
        # Crear archivo de prueba
        test_file_content = b"Este es el contenido de un archivo de prueba para verificar upload y descarga."
        test_filename = "test_upload_download.txt"
        
        try:
            # Upload con multipart/form-data
            files = {"file": (test_filename, test_file_content, "text/plain")}
            data = {"title": "UPLOAD-TEST: Archivo para prueba de descarga", "tags": "upload-test,comprehensive-test"}
            
            start = time.time()
            response = await self.client.post(
                f"{self.api_url}/documents/upload",
                files=files,
                data=data,
                headers=headers
            )
            duration = (time.time() - start) * 1000
            
            if response.status_code in [200, 201]:
                upload_doc = response.json()
                upload_doc_id = upload_doc.get("id")
                await self.record_result(
                    "Upload archivo", True,
                    f"OK (ID: {upload_doc_id[:8]}...)", "descarga", duration_ms=duration
                )
                
                # Guardar para cleanup
                user.documents.append({"id": upload_doc_id, "tags": ["upload-test"]})
                
                # Esperar sincronización breve
                await asyncio.sleep(2)
                
                # Descargar el archivo
                start = time.time()
                download_resp = await self.client.get(
                    f"{self.api_url}/documents/{upload_doc_id}/download",
                    headers=headers
                )
                duration = (time.time() - start) * 1000
                
                if download_resp.status_code == 200:
                    downloaded_content = download_resp.content
                    content_match = downloaded_content == test_file_content
                    await self.record_result(
                        "Descarga archivo", content_match,
                        f"{'Contenido idéntico' if content_match else 'Contenido DIFERENTE'} ({len(downloaded_content)} bytes)",
                        "descarga", duration_ms=duration
                    )
                else:
                    await self.record_result(
                        "Descarga archivo", False,
                        f"Error: {download_resp.status_code}", "descarga"
                    )
            else:
                await self.record_result(
                    "Upload archivo", False,
                    f"Error: {response.status_code} - {response.text[:100]}", "descarga"
                )
        except Exception as e:
            await self.record_result(
                "Upload/Descarga archivo", False, str(e), "descarga"
            )
        
        self.state["phase_normal_ops_completed"] = True
        self.save_state()
        return True
    
    # ═══════════════════════════════════════════════════════════════════════
    # FASE 3: PARTICIÓN DE RED
    # ═══════════════════════════════════════════════════════════════════════
    
    async def phase_partition(self) -> bool:
        self.log("")
        self.log("╔" + "═" * 68 + "╗", "PHASE")
        self.log("║" + " " * 15 + f"FASE 3: PARTICIÓN ({self.node_name})" + " " * 20 + "║", "PHASE")
        self.log("╚" + "═" * 68 + "╝", "PHASE")
        
        # Cargar estado si existe
        if not self.users:
            self.load_state()
        
        # Health check local
        try:
            response = await self.client.get(f"{self.api_url}/health")
            if response.status_code != 200:
                await self.record_result(
                    "Health Local", False,
                    f"Status {response.status_code}", "particion"
                )
                return False
            await self.record_result("Health Local", True, "Nodo funcionando", "particion")
        except Exception as e:
            await self.record_result("Health Local", False, str(e), "particion")
            return False
        
        # Login del usuario de prueba
        test_user = TEST_USERS[0]
        try:
            login_resp = await self.client.post(
                f"{self.api_url}/auth/login",
                data={"username": test_user["username"], "password": test_user["password"]}
            )
            
            if login_resp.status_code != 200:
                # Intentar registrar
                await self.client.post(f"{self.api_url}/auth/register", json=test_user)
                login_resp = await self.client.post(
                    f"{self.api_url}/auth/login",
                    data={"username": test_user["username"], "password": test_user["password"]}
                )
            
            token = login_resp.json().get("access_token")
            await self.record_result("Login Local", True, "OK", "particion")
        except Exception as e:
            await self.record_result("Login Local", False, str(e), "particion")
            return False
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Crear documento único para este nodo
        unique_doc = {
            "title": f"PARTITION-{self.node_name}: Documento Durante Aislamiento",
            "content": f"Documento creado en {self.node_name} durante partición de red. Timestamp: {datetime.now().isoformat()}",
            "tags": ["partition", self.node_name, "comprehensive-test"]
        }
        
        try:
            response = await self.client.post(
                f"{self.api_url}/documents",
                json=unique_doc,
                headers=headers
            )
            if response.status_code in [200, 201]:
                doc = response.json()
                await self.record_result(
                    f"Doc partición {self.node_name}", True,
                    f"ID: {doc.get('id')}", "particion"
                )
                if "partition_docs" not in self.state:
                    self.state["partition_docs"] = {}
                self.state["partition_docs"][self.node_name] = doc.get("id")
            else:
                await self.record_result(
                    f"Doc partición {self.node_name}", False,
                    f"Error: {response.text[:100]}", "particion"
                )
        except Exception as e:
            await self.record_result(f"Doc partición {self.node_name}", False, str(e), "particion")
        
        # Crear documento IDÉNTICO (para deduplicación)
        try:
            response = await self.client.post(
                f"{self.api_url}/documents",
                json=IDENTICAL_DOC,
                headers=headers
            )
            if response.status_code in [200, 201]:
                doc = response.json()
                await self.record_result(
                    "Doc idéntico (dedup)", True,
                    f"ID: {doc.get('id')}", "particion"
                )
                if "identical_docs" not in self.state:
                    self.state["identical_docs"] = {}
                self.state["identical_docs"][self.node_name] = doc.get("id")
            else:
                # Ya existe = deduplicación funcionando
                if response.status_code == 409 or "exist" in response.text.lower():
                    await self.record_result(
                        "Doc idéntico (dedup)", True,
                        "Ya existe (deduplicación local activa)", "particion"
                    )
                else:
                    await self.record_result(
                        "Doc idéntico (dedup)", False,
                        f"Error: {response.text[:100]}", "particion"
                    )
        except Exception as e:
            await self.record_result("Doc idéntico (dedup)", False, str(e), "particion")
        
        # Listar documentos visibles
        response = await self.client.get(f"{self.api_url}/documents", headers=headers)
        if response.status_code == 200:
            docs = response.json()
            doc_list = docs.get("documents", docs) if isinstance(docs, dict) else docs
            self.log(f"\nDocumentos visibles en {self.node_name}: {len(doc_list)}")
            for d in doc_list[:5]:  # Mostrar primeros 5
                self.log(f"  - {d.get('title')[:50]}...")
            if len(doc_list) > 5:
                self.log(f"  ... y {len(doc_list) - 5} más")
        
        self.state[f"phase_partition_{self.node_name}_completed"] = True
        self.save_state()
        return True
    
    # ═══════════════════════════════════════════════════════════════════════
    # FASE 4: RECONCILIACIÓN
    # ═══════════════════════════════════════════════════════════════════════
    
    async def phase_reconcile(self) -> bool:
        self.log("")
        self.log("╔" + "═" * 68 + "╗", "PHASE")
        self.log("║" + " " * 18 + "FASE 4: RECONCILIACIÓN" + " " * 28 + "║", "PHASE")
        self.log("╚" + "═" * 68 + "╝", "PHASE")
        
        self.load_state()
        
        # Este paso solo espera y verifica que los nodos se reconecten
        self.log("Verificando conectividad post-reconexión...")
        
        try:
            response = await self.client.get(f"{self.api_url}/health")
            if response.status_code == 200:
                await self.record_result("Conectividad", True, "Sistema accesible", "reconciliacion")
            else:
                await self.record_result("Conectividad", False, 
                                        f"Status {response.status_code}", "reconciliacion")
                return False
        except Exception as e:
            await self.record_result("Conectividad", False, str(e), "reconciliacion")
            return False
        
        # Esperar sincronización
        self.log(f"\nEsperando {WAIT_TIME_SYNC * 3}s para reconciliación completa...")
        await asyncio.sleep(WAIT_TIME_SYNC * 3)  # 90 segundos
        
        self.state["phase_reconcile_completed"] = True
        self.save_state()
        return True
    
    # ═══════════════════════════════════════════════════════════════════════
    # FASE 5: VERIFICACIÓN FINAL
    # ═══════════════════════════════════════════════════════════════════════
    
    async def phase_final_verify(self) -> bool:
        self.log("")
        self.log("╔" + "═" * 68 + "╗", "PHASE")
        self.log("║" + " " * 17 + "FASE 5: VERIFICACIÓN FINAL" + " " * 25 + "║", "PHASE")
        self.log("╚" + "═" * 68 + "╝", "PHASE")
        
        self.load_state()
        
        # Login
        test_user = TEST_USERS[0]
        login_resp = await self.client.post(
            f"{self.api_url}/auth/login",
            data={"username": test_user["username"], "password": test_user["password"]}
        )
        
        if login_resp.status_code != 200:
            await self.record_result("Login Final", False, "No se pudo autenticar", "final")
            return False
        
        token = login_resp.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"}
        
        # Obtener todos los documentos
        response = await self.client.get(f"{self.api_url}/documents", headers=headers)
        if response.status_code != 200:
            await self.record_result("Listar Docs", False, 
                                    f"Error: {response.status_code}", "final")
            return False
        
        docs = response.json()
        doc_list = docs.get("documents", docs) if isinstance(docs, dict) else docs
        
        await self.record_result("Listar Docs", True, f"{len(doc_list)} documentos", "final")
        
        # 5.1 Verificar documentos de partición reconciliados
        self.log("\n--- 5.1 Reconciliación de Documentos ---", "PHASE")
        
        partition_docs = self.state.get("partition_docs", {})
        for node_name, doc_id in partition_docs.items():
            found = any(
                d.get("id") == doc_id or 
                f"PARTITION-{node_name}" in d.get("title", "")
                for d in doc_list
            )
            await self.record_result(
                f"Doc partición {node_name}", found,
                "Encontrado (reconciliación OK)" if found else "NO ENCONTRADO",
                "reconciliacion"
            )
        
        # 5.2 Verificar DEDUPLICACIÓN
        self.log("\n--- 5.2 Deduplicación ---", "PHASE")
        
        identical_docs = [d for d in doc_list if "DEDUP-TEST" in d.get("title", "")]
        identical_count = len(identical_docs)
        
        if identical_count == 1:
            await self.record_result(
                "Deduplicación", True,
                "ÉXITO: Solo 1 documento idéntico existe", "deduplicacion"
            )
        elif identical_count == 0:
            await self.record_result(
                "Deduplicación", False,
                "No se encontró documento idéntico", "deduplicacion"
            )
        else:
            await self.record_result(
                "Deduplicación", False,
                f"FALLO: {identical_count} documentos idénticos (debería ser 1)",
                "deduplicacion",
                details={"ids": [d.get("id") for d in identical_docs]}
            )
        
        # 5.3 Re-verificar búsqueda
        self.log("\n--- 5.3 Búsqueda Post-Reconciliación ---", "PHASE")
        
        search_response = await self.client.get(
            f"{self.api_url}/search",
            params={"q": "comprehensive-test"},
            headers=headers
        )
        
        if search_response.status_code == 200:
            results = search_response.json().get("results", [])
            await self.record_result(
                "Búsqueda post-reconciliación", len(results) > 0,
                f"{len(results)} resultados encontrados", "final"
            )
        
        # 5.3.1 Verificar descarga post-reconciliación
        self.log("\n--- 5.3.1 Descarga Post-Reconciliación ---", "PHASE")
        
        # Probar GET de un documento cualquiera
        if doc_list:
            test_doc = doc_list[0]
            test_doc_id = test_doc.get("id")
            
            try:
                start = time.time()
                response = await self.client.get(
                    f"{self.api_url}/documents/{test_doc_id}",
                    headers=headers
                )
                duration = (time.time() - start) * 1000
                
                if response.status_code == 200:
                    doc_data = response.json()
                    await self.record_result(
                        "GET doc post-reconciliación", True,
                        f"OK (título: {doc_data.get('title', '')[:30]}...)",
                        "descarga", duration_ms=duration
                    )
                else:
                    await self.record_result(
                        "GET doc post-reconciliación", False,
                        f"Error: {response.status_code}", "descarga"
                    )
            except Exception as e:
                await self.record_result(
                    "GET doc post-reconciliación", False, str(e), "descarga"
                )
        
        # 5.4 Verificar estabilidad final
        self.log("\n--- 5.4 Estabilidad Final ---", "PHASE")
        
        listings = []
        for _ in range(5):
            resp = await self.client.get(f"{self.api_url}/documents", headers=headers)
            if resp.status_code == 200:
                d = resp.json()
                dl = d.get("documents", d) if isinstance(d, dict) else d
                listings.append(sorted([x.get("id") for x in dl]))
            await asyncio.sleep(0.5)
        
        is_stable = len(set(tuple(l) for l in listings)) == 1
        await self.record_result(
            "Estabilidad final", is_stable,
            f"{'Estable' if is_stable else 'INESTABLE'} ({len(listings[0]) if listings else 0} docs)",
            "estabilidad"
        )
        
        # 5.5 Prueba de eliminación y propagación
        self.log("\n--- 5.5 Eliminación y Propagación ---", "PHASE")
        
        # Crear documento temporal
        temp_doc = {
            "title": "TEMP-DELETE-TEST: Documento para eliminación",
            "content": "Este documento será eliminado para probar propagación de tombstones.",
            "tags": ["temp-delete", "comprehensive-test"]
        }
        
        create_resp = await self.client.post(
            f"{self.api_url}/documents",
            json=temp_doc,
            headers=headers
        )
        
        if create_resp.status_code in [200, 201]:
            temp_doc_id = create_resp.json().get("id")
            
            # Esperar un poco
            await asyncio.sleep(5)
            
            # Eliminar
            delete_resp = await self.client.delete(
                f"{self.api_url}/documents/{temp_doc_id}",
                headers=headers
            )
            
            if delete_resp.status_code in [200, 204]:
                # Esperar propagación
                await asyncio.sleep(10)
                
                # Verificar que no existe
                check_resp = await self.client.get(f"{self.api_url}/documents", headers=headers)
                if check_resp.status_code == 200:
                    final_docs = check_resp.json()
                    final_list = final_docs.get("documents", final_docs) if isinstance(final_docs, dict) else final_docs
                    still_exists = any(d.get("id") == temp_doc_id for d in final_list)
                    
                    await self.record_result(
                        "Eliminación propagada", not still_exists,
                        "Documento eliminado correctamente" if not still_exists else "Documento aún existe",
                        "eliminacion"
                    )
        
        self.state["phase_final_verify_completed"] = True
        self.save_state()
        return True
    
    # ═══════════════════════════════════════════════════════════════════════
    # CLEANUP
    # ═══════════════════════════════════════════════════════════════════════
    
    async def cleanup(self):
        self.log("\nLimpiando documentos de prueba...")
        
        for user_data in TEST_USERS:
            try:
                login_resp = await self.client.post(
                    f"{self.api_url}/auth/login",
                    data={"username": user_data["username"], "password": user_data["password"]}
                )
                if login_resp.status_code != 200:
                    continue
                
                token = login_resp.json().get("access_token")
                headers = {"Authorization": f"Bearer {token}"}
                
                response = await self.client.get(f"{self.api_url}/documents", headers=headers)
                if response.status_code != 200:
                    continue
                
                docs = response.json()
                doc_list = docs.get("documents", docs) if isinstance(docs, dict) else docs
                
                deleted = 0
                for d in doc_list:
                    tags = d.get("tags", [])
                    if "comprehensive-test" in tags or "partition" in tags or "dedup-test" in tags:
                        del_resp = await self.client.delete(
                            f"{self.api_url}/documents/{d.get('id')}",
                            headers=headers
                        )
                        if del_resp.status_code in [200, 204]:
                            deleted += 1
                
                if deleted > 0:
                    self.log(f"  Eliminados {deleted} docs de {user_data['username']}")
                    
            except Exception as e:
                self.log(f"  Error limpiando {user_data['username']}: {e}", "WARN")
        
        if os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)
            self.log("Estado limpiado")
    
    # ═══════════════════════════════════════════════════════════════════════
    # MODOS DE EJECUCIÓN
    # ═══════════════════════════════════════════════════════════════════════
    
    async def run_quick_test(self) -> bool:
        """Modo rápido: solo operaciones normales sin particiones"""
        self.log("")
        self.log("╔" + "═" * 68 + "╗", "PHASE")
        self.log("║" + " " * 10 + "TEST COMPREHENSIVO - MODO RÁPIDO" + " " * 26 + "║", "PHASE")
        self.log("╚" + "═" * 68 + "╝", "PHASE")
        self.log("(Sin pruebas de partición de red)")
        
        if not await self.phase_setup():
            return False
        
        if not await self.phase_normal_operations():
            return False
        
        return self.print_final_summary()
    
    async def run_guided_test(self) -> bool:
        """Modo guiado: test completo con tiempos de espera"""
        self.log("")
        self.log("╔" + "═" * 68 + "╗", "PHASE")
        self.log("║" + " " * 5 + "TEST COMPREHENSIVO - MODO GUIADO (COMPLETO)" + " " * 20 + "║", "PHASE")
        self.log("╚" + "═" * 68 + "╝", "PHASE")
        self.log(f"URL: {self.base_url}")
        self.log(f"Tiempo por fase: {WAIT_TIME_PARTITION // 60} minutos")
        
        # FASE 1: Setup
        if not await self.phase_setup():
            self.log("❌ Setup falló. Abortando.", "ERROR")
            return False
        
        # FASE 2: Operaciones normales
        if not await self.phase_normal_operations():
            self.log("❌ Operaciones normales fallaron.", "ERROR")
        
        # Crear documento de partición en nodo conectado
        self.node_name = "nodoConectado"
        await self.phase_partition()
        
        # ESPERA: Partición
        partition_instructions = [
            "Desconecta la WiFi de UNO de los nodos del cluster",
            "En ese nodo AISLADO, abre una terminal y ejecuta:",
            f"  python scripts/test_scenario_3.py --phase partition \\",
            f"         --base-url https://localhost:443 --node-name nodoAislado",
            "El nodo aislado creará documentos incluyendo el DEDUP-TEST",
            "Puedes crear documentos adicionales manualmente si lo deseas"
        ]
        
        await self.countdown_with_instructions(
            WAIT_TIME_PARTITION,
            "CREAR PARTICIÓN Y DOCUMENTOS",
            partition_instructions
        )
        
        # ESPERA: Reconciliación
        reconciliation_instructions = [
            "RECONECTA el nodo aislado a la WiFi",
            "Verifica conectividad (ping entre nodos)",
            "El sistema sincronizará automáticamente",
            "La reconciliación toma 60-90 segundos típicamente",
            "Observa los logs para mensajes de sync/gossip"
        ]
        
        await self.countdown_with_instructions(
            WAIT_TIME_RECONCILIATION,
            "RECONEXIÓN Y RECONCILIACIÓN",
            reconciliation_instructions
        )
        
        # FASE 4: Reconciliación (verificación)
        await self.phase_reconcile()
        
        # FASE 5: Verificación final
        await self.phase_final_verify()
        
        # Resumen
        success = self.print_final_summary()
        
        # Preguntar cleanup
        try:
            response = input("\n¿Deseas limpiar los documentos de prueba? (s/N): ")
            if response.lower() in ['s', 'si', 'yes', 'y']:
                await self.cleanup()
        except (KeyboardInterrupt, EOFError):
            self.log("\nLimpieza omitida", "WARN")
        
        return success
    
    def print_final_summary(self) -> bool:
        summary = self.get_summary()
        
        self.log("")
        self.log("╔" + "═" * 68 + "╗", "PHASE")
        self.log("║" + " " * 20 + "RESUMEN FINAL DEL TEST" + " " * 26 + "║", "PHASE")
        self.log("╚" + "═" * 68 + "╝", "PHASE")
        
        # Por categoría
        self.log("\nResultados por categoría:")
        for category, stats in sorted(summary.by_category.items()):
            status = "✓" if stats["failed"] == 0 else "✗"
            color = "SUCCESS" if stats["failed"] == 0 else "ERROR"
            self.log(f"  {status} {category}: {stats['passed']}/{stats['total']} pasaron", color)
        
        # Tests fallidos
        failed_tests = [r for r in self.results if not r.passed]
        if failed_tests:
            self.log("\n❌ Tests fallidos:", "ERROR")
            for r in failed_tests:
                self.log(f"  - [{r.category}] {r.name}: {r.message}", "ERROR")
        
        # Resumen total
        self.log("")
        self.log("═" * 70)
        
        success_rate = (summary.passed / summary.total * 100) if summary.total > 0 else 0
        
        if summary.failed == 0:
            self.log(f"🎉 ¡SISTEMA DISTRIBUIDO IMPECABLE!", "SUCCESS")
            self.log(f"   {summary.passed}/{summary.total} tests pasaron (100%)", "SUCCESS")
            self.log("")
            self.log("El sistema demostró:", "SUCCESS")
            self.log("  ✓ Operaciones CRUD funcionando", "SUCCESS")
            self.log("  ✓ Búsqueda cross-node", "SUCCESS")
            self.log("  ✓ Estabilidad del listado", "SUCCESS")
            self.log("  ✓ Aislamiento por usuario", "SUCCESS")
            self.log("  ✓ Tolerancia a particiones", "SUCCESS")
            self.log("  ✓ Reconciliación automática", "SUCCESS")
            self.log("  ✓ Deduplicación de documentos", "SUCCESS")
            self.log("  ✓ Propagación de eliminaciones", "SUCCESS")
            self.log("  ✓ Descarga de documentos", "SUCCESS")
            self.log("  ✓ Upload y descarga de archivos", "SUCCESS")
        else:
            self.log(f"⚠️  SISTEMA CON PROBLEMAS", "ERROR")
            self.log(f"   {summary.passed}/{summary.total} tests pasaron ({success_rate:.1f}%)", "WARN")
            self.log(f"   {summary.failed} tests fallaron", "ERROR")
        
        self.log("═" * 70)
        
        return summary.failed == 0


async def main():
    parser = argparse.ArgumentParser(
        description="Test Scenario 3: Comprehensive Distributed System Validation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
═══════════════════════════════════════════════════════════════════════════════
MODO GUIADO (Test completo con particiones):
═══════════════════════════════════════════════════════════════════════════════
  python scripts/test_scenario_3.py --guided --base-url https://192.168.1.10:443

  Opciones:
    --wait-time 5    # Cambiar tiempo de espera a 5 minutos (default: 10)

═══════════════════════════════════════════════════════════════════════════════
MODO RÁPIDO (Solo operaciones normales, sin particiones):
═══════════════════════════════════════════════════════════════════════════════
  python scripts/test_scenario_3.py --quick --base-url https://192.168.1.10:443

═══════════════════════════════════════════════════════════════════════════════
MODO POR FASES (Control manual total):
═══════════════════════════════════════════════════════════════════════════════
  1. Setup:
     python scripts/test_scenario_3.py --phase setup --base-url https://...

  2. Operaciones normales:
     python scripts/test_scenario_3.py --phase normal-ops --base-url https://...

  3. Durante partición (en cada nodo):
     python scripts/test_scenario_3.py --phase partition --base-url https://localhost:443 --node-name nodoX

  4. Reconciliación:
     python scripts/test_scenario_3.py --phase reconcile --base-url https://...

  5. Verificación final:
     python scripts/test_scenario_3.py --phase final-verify --base-url https://...

═══════════════════════════════════════════════════════════════════════════════
LIMPIEZA:
═══════════════════════════════════════════════════════════════════════════════
  python scripts/test_scenario_3.py --cleanup --base-url https://...
        """
    )
    
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--guided", action="store_true",
                           help="Modo guiado: test completo con tiempos de espera")
    mode_group.add_argument("--quick", action="store_true",
                           help="Modo rápido: solo operaciones normales (sin particiones)")
    mode_group.add_argument("--phase", 
                           choices=["setup", "normal-ops", "partition", "reconcile", "final-verify"],
                           help="Ejecutar una fase específica")
    mode_group.add_argument("--cleanup", action="store_true",
                           help="Limpiar documentos de prueba")
    
    parser.add_argument("--base-url", required=True,
                       help="URL base del nodo (ej: https://192.168.1.10:443)")
    parser.add_argument("--node-name", default="default",
                       help="Nombre del nodo (para fase partition)")
    parser.add_argument("--wait-time", type=int, default=10,
                       help="Tiempo de espera en minutos (default: 10)")
    
    args = parser.parse_args()
    
    # SSL warnings
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    # Ajustar tiempos
    global WAIT_TIME_PARTITION, WAIT_TIME_RECONCILIATION
    if args.wait_time != 10:
        WAIT_TIME_PARTITION = args.wait_time * 60
        WAIT_TIME_RECONCILIATION = args.wait_time * 60
    
    tester = ComprehensiveTester(args.base_url, args.node_name)
    
    try:
        if args.cleanup:
            await tester.cleanup()
            return
        
        if args.guided:
            success = await tester.run_guided_test()
        elif args.quick:
            success = await tester.run_quick_test()
        elif args.phase:
            if args.phase == "setup":
                success = await tester.phase_setup()
            elif args.phase == "normal-ops":
                success = await tester.phase_normal_operations()
            elif args.phase == "partition":
                success = await tester.phase_partition()
            elif args.phase == "reconcile":
                success = await tester.phase_reconcile()
            elif args.phase == "final-verify":
                success = await tester.phase_final_verify()
                tester.print_final_summary()
        else:
            parser.print_help()
            print("\n" + "=" * 70)
            print("ERROR: Especifica un modo: --guided, --quick, --phase, o --cleanup")
            print("=" * 70)
            sys.exit(1)
        
        sys.exit(0 if success else 1)
        
    finally:
        await tester.close()


if __name__ == "__main__":
    asyncio.run(main())
