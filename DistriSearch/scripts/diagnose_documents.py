#!/usr/bin/env python3
"""
Diagnóstico de documentos - Verifica estado de documentos y archivos.

Este script ayuda a identificar:
- Documentos huérfanos (sin archivo físico)
- Documentos con file_path pero archivo no existe
- Documentos creados inline vs subidos
- Estado de replicación
"""

import asyncio
import argparse
import sys
from typing import List, Tuple, Optional
import aiohttp

API_V1 = "/api/v1"

class DocumentDiagnostic:
    """Diagnóstico de documentos del sistema."""
    
    def __init__(self, nodes: List[Tuple[str, int]], username: str = "testuser", password: str = "testpass123"):
        self.nodes = nodes
        self.username = username
        self.password = password
        self.token: Optional[str] = None
        
    async def authenticate(self) -> bool:
        """Autenticarse con el sistema."""
        node_url = f"http://{self.nodes[0][0]}:{self.nodes[0][1]}"
        
        try:
            async with aiohttp.ClientSession() as session:
                # Intentar login
                async with session.post(
                    f"{node_url}{API_V1}/auth/login",
                    json={"username": self.username, "password": self.password}
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self.token = data.get("access_token")
                        print(f"✓ Autenticado como {self.username}")
                        return True
                    elif resp.status == 401:
                        # Intentar registrar
                        async with session.post(
                            f"{node_url}{API_V1}/auth/register",
                            json={"username": self.username, "password": self.password}
                        ) as reg_resp:
                            if reg_resp.status == 201:
                                data = await reg_resp.json()
                                self.token = data.get("access_token")
                                print(f"✓ Usuario registrado: {self.username}")
                                return True
        except Exception as e:
            print(f"✗ Error de autenticación: {e}")
        return False
    
    async def get_documents_from_node(self, host: str, port: int) -> List[dict]:
        """Obtiene documentos de un nodo específico."""
        url = f"http://{host}:{port}{API_V1}/documents"
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("documents", [])
        except Exception as e:
            print(f"  Error al obtener docs de {host}:{port}: {e}")
        return []
    
    async def check_document_status(self, host: str, port: int, doc_id: str) -> dict:
        """Verifica estado de un documento específico."""
        url = f"http://{host}:{port}{API_V1}/documents/{doc_id}"
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        
        result = {
            "exists": False,
            "has_file_path": False,
            "can_download": False,
            "has_content": False,
            "is_replica": False,
            "file_size": 0,
            "error": None
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                # Verificar si existe
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        result["exists"] = True
                        result["has_content"] = bool(data.get("content"))
                        result["is_replica"] = data.get("is_replica", False)
                        metadata = data.get("metadata", {})
                        result["has_file_path"] = bool(metadata.get("file_path"))
                        
                # Intentar descargar
                download_url = f"http://{host}:{port}{API_V1}/documents/{doc_id}/download"
                async with session.get(download_url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        result["can_download"] = True
                        result["file_size"] = len(content)
                    else:
                        result["error"] = f"Download status: {resp.status}"
                        
        except Exception as e:
            result["error"] = str(e)
            
        return result
    
    async def diagnose_document(self, doc: dict):
        """Diagnostica un documento en todos los nodos."""
        doc_id = doc.get("id") or doc.get("_id")
        title = doc.get("title", "Sin título")
        
        print(f"\n📄 Documento: {title}")
        print(f"   ID: {doc_id}")
        
        for host, port in self.nodes:
            status = await self.check_document_status(host, port, doc_id)
            
            node_name = f"{host}:{port}"
            if status["exists"]:
                flags = []
                if status["is_replica"]:
                    flags.append("réplica")
                if status["has_file_path"]:
                    flags.append("tiene file_path")
                if status["has_content"]:
                    flags.append("tiene content")
                    
                download_status = "✓ descargable" if status["can_download"] else f"✗ NO descargable ({status['error']})"
                
                print(f"   [{node_name}] Existe ({', '.join(flags)}) - {download_status}")
                if status["can_download"]:
                    print(f"      Tamaño: {status['file_size']} bytes")
            else:
                print(f"   [{node_name}] No existe")
    
    async def run_full_diagnosis(self):
        """Ejecuta diagnóstico completo."""
        print("=" * 70)
        print("DIAGNÓSTICO DE DOCUMENTOS - DistriSearch")
        print("=" * 70)
        
        if not await self.authenticate():
            print("Error: No se pudo autenticar")
            return
        
        # Recopilar todos los documentos únicos de todos los nodos
        all_docs = {}
        
        print(f"\n🔍 Escaneando {len(self.nodes)} nodos...")
        
        for host, port in self.nodes:
            print(f"\n--- Nodo {host}:{port} ---")
            docs = await self.get_documents_from_node(host, port)
            print(f"   Encontrados: {len(docs)} documentos")
            
            for doc in docs:
                doc_id = doc.get("id") or doc.get("_id")
                if doc_id and doc_id not in all_docs:
                    all_docs[doc_id] = doc
        
        print(f"\n📊 Total de documentos únicos: {len(all_docs)}")
        
        # Clasificar documentos
        test_docs = []
        normal_docs = []
        
        for doc_id, doc in all_docs.items():
            title = doc.get("title", "")
            filename = doc.get("metadata", {}).get("filename", "") if isinstance(doc.get("metadata"), dict) else ""
            
            if "test_17" in title.lower() or "test_17" in filename.lower():
                test_docs.append(doc)
            elif "test_" in title.lower() or "test_" in filename.lower():
                test_docs.append(doc)
            else:
                normal_docs.append(doc)
        
        # Diagnosticar documentos problemáticos primero
        if test_docs:
            print(f"\n" + "=" * 70)
            print(f"⚠️  DOCUMENTOS DE TEST ({len(test_docs)})")
            print("=" * 70)
            
            for doc in test_docs[:10]:  # Limitar a 10
                await self.diagnose_document(doc)
        
        # Mostrar muestra de documentos normales
        if normal_docs:
            print(f"\n" + "=" * 70)
            print(f"📚 DOCUMENTOS NORMALES ({len(normal_docs)})")
            print("=" * 70)
            
            for doc in normal_docs[:5]:  # Limitar a 5
                await self.diagnose_document(doc)
        
        # Resumen
        print(f"\n" + "=" * 70)
        print("RESUMEN")
        print("=" * 70)
        print(f"  Total documentos escaneados: {len(all_docs)}")
        print(f"  Documentos de test: {len(test_docs)}")
        print(f"  Documentos normales: {len(normal_docs)}")
        
        # Verificar descargabilidad
        downloadable = 0
        not_downloadable = 0
        
        print(f"\n🔄 Verificando descargabilidad de documentos de test...")
        
        for doc in test_docs:
            doc_id = doc.get("id") or doc.get("_id")
            # Probar en primer nodo disponible
            status = await self.check_document_status(self.nodes[0][0], self.nodes[0][1], doc_id)
            if status["can_download"]:
                downloadable += 1
            else:
                not_downloadable += 1
                title = doc.get("title", "Sin título")
                print(f"   ✗ No descargable: {title[:40]}")
        
        print(f"\n  Descargables: {downloadable}")
        print(f"  No descargables: {not_downloadable}")

    async def force_sync_all_nodes(self):
        """Fuerza sincronización en todos los nodos."""
        print("\n" + "=" * 70)
        print("🔄 FORZANDO SINCRONIZACIÓN COMPLETA")
        print("=" * 70)
        
        for host, port in self.nodes:
            url = f"http://{host}:{port}/api/v1/internal/sync/full"
            print(f"\n   Sincronizando {host}:{port}...")
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            print(f"   ✓ Sincronización exitosa:")
                            print(f"      Usuarios: {data.get('users_synced', 0)}")
                            print(f"      Registro: {data.get('registry_entries_synced', 0)}")
                            print(f"      Documentos: {data.get('documents_replicated', 0)}")
                        else:
                            print(f"   ✗ Error: HTTP {resp.status}")
            except Exception as e:
                print(f"   ✗ Error: {e}")

    async def cleanup_orphan_documents(self):
        """Elimina documentos que no tienen archivo físico descargable."""
        print("\n" + "=" * 70)
        print("🧹 LIMPIEZA DE DOCUMENTOS HUÉRFANOS")
        print("=" * 70)
        
        if not await self.authenticate():
            print("Error: No se pudo autenticar")
            return
        
        # Primero obtener todos los documentos
        all_docs = {}
        for host, port in self.nodes:
            docs = await self.get_documents_from_node(host, port)
            for doc in docs:
                doc_id = doc.get("id") or doc.get("_id")
                if doc_id and doc_id not in all_docs:
                    all_docs[doc_id] = doc
        
        orphans = []
        for doc_id, doc in all_docs.items():
            # Verificar si se puede descargar
            status = await self.check_document_status(self.nodes[0][0], self.nodes[0][1], doc_id)
            if not status["can_download"] and status["has_file_path"]:
                orphans.append(doc)
        
        if not orphans:
            print("   No se encontraron documentos huérfanos.")
            return
        
        print(f"\n   Encontrados {len(orphans)} documentos huérfanos:")
        for doc in orphans:
            title = doc.get("title", "Sin título")
            doc_id = doc.get("id") or doc.get("_id")
            print(f"   - {title[:40]} ({doc_id[:8]}...)")
        
        # Confirmar eliminación
        confirm = input("\n   ¿Eliminar estos documentos? (s/N): ")
        if confirm.lower() != 's':
            print("   Cancelado.")
            return
        
        # Eliminar documentos
        deleted = 0
        for doc in orphans:
            doc_id = doc.get("id") or doc.get("_id")
            for host, port in self.nodes:
                try:
                    url = f"http://{host}:{port}/api/v1/documents/{doc_id}"
                    headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
                    async with aiohttp.ClientSession() as session:
                        async with session.delete(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                            if resp.status in [200, 204]:
                                print(f"   ✓ Eliminado: {doc_id[:8]}...")
                                deleted += 1
                                break
                except Exception as e:
                    continue
        
        print(f"\n   Total eliminados: {deleted}")


def parse_args():
    parser = argparse.ArgumentParser(description="Diagnóstico de documentos DistriSearch")
    parser.add_argument(
        "--nodes", 
        type=str, 
        default="192.168.61.32:8001,192.168.61.32:8002,192.168.61.33:8003",
        help="Nodos en formato host:port,host:port,..."
    )
    parser.add_argument("--user", type=str, default="testuser", help="Usuario")
    parser.add_argument("--password", type=str, default="testpass123", help="Contraseña")
    parser.add_argument("--force-sync", action="store_true", help="Forzar sincronización completa")
    parser.add_argument("--cleanup-orphans", action="store_true", help="Eliminar documentos huérfanos (sin archivo)")
    return parser.parse_args()


async def main():
    args = parse_args()
    
    # Parsear nodos
    nodes = []
    for node_str in args.nodes.split(","):
        parts = node_str.strip().split(":")
        if len(parts) == 2:
            nodes.append((parts[0], int(parts[1])))
    
    if not nodes:
        print("Error: No se especificaron nodos válidos")
        sys.exit(1)
    
    diagnostic = DocumentDiagnostic(nodes, args.user, args.password)
    
    if args.force_sync:
        await diagnostic.force_sync_all_nodes()
    elif args.cleanup_orphans:
        await diagnostic.cleanup_orphan_documents()
    else:
        await diagnostic.run_full_diagnosis()


if __name__ == "__main__":
    asyncio.run(main())
