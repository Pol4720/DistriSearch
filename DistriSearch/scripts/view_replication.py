#!/usr/bin/env python3
"""
Replication Viewer - Ver archivos en cada nodo con sus dueños
=============================================================

Script para visualizar la distribución y replicación de documentos
en el sistema DistriSearch.

Uso:
    python scripts/view_replication.py
    python scripts/view_replication.py --base-url http://192.168.61.32:8001
    python scripts/view_replication.py --format json
    python scripts/view_replication.py --user alice
    python scripts/view_replication.py --method mongo  # Usar MongoDB directamente

Muestra:
- Documentos en cada nodo
- Dueño de cada documento
- Factor de replicación real
- Documentos únicos vs replicados
"""

import asyncio
import argparse
import json
import sys
import subprocess
from datetime import datetime
from typing import Dict, List, Optional, Any
from collections import defaultdict
import aiohttp


DEFAULT_BASE_URL = "http://192.168.61.32:8001"
MONGO_HOST = "192.168.61.32"
MONGO_PORT = 27017
API_V1 = "/api/v1"
TIMEOUT = 15.0

# Colores para terminal
COLORS = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "red": "\033[91m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "blue": "\033[94m",
    "magenta": "\033[95m",
    "cyan": "\033[96m",
    "white": "\033[97m"
}

NODE_COLORS = {
    "node-1": "green",
    "node-2": "blue",
    "node-3": "magenta",
    "8001": "green",
    "8002": "blue",
    "8003": "magenta"
}


def colored(text: str, color: str) -> str:
    """Aplicar color al texto"""
    return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"


def get_node_color(node_id: str) -> str:
    """Obtener color para un nodo"""
    for key, color in NODE_COLORS.items():
        if key in str(node_id):
            return color
    return "white"


class ReplicationViewer:
    def __init__(self, base_url: str, output_format: str = "table", filter_user: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}{API_V1}"
        self.output_format = output_format
        self.filter_user = filter_user
        
        # Datos recopilados
        self.nodes_info: Dict[str, Any] = {}
        self.documents_by_node: Dict[str, List[Dict]] = defaultdict(list)
        self.users_cache: Dict[str, str] = {}  # user_id -> username
        self.all_documents: Dict[str, Dict] = {}  # doc_id -> doc info
        self.document_locations: Dict[str, List[str]] = defaultdict(list)  # doc_id -> [nodes]
    
    async def fetch_nodes(self, session: aiohttp.ClientSession) -> List[str]:
        """Obtener lista de nodos del sistema"""
        try:
            async with session.get(f"{self.api_url}/health/") as resp:
                if resp.status == 200:
                    health = await resp.json()
                    nodes = health.get("nodes", {})
                    return list(nodes.keys())
        except:
            pass
        
        # Fallback a nodos conocidos
        return ["node-1", "node-2", "node-3"]
    
    async def fetch_node_documents(self, session: aiohttp.ClientSession, node_id: str) -> List[Dict]:
        """Obtener documentos de un nodo específico (requiere endpoint interno o MongoDB)"""
        # Intentar obtener documentos desde el endpoint de documentos
        # Nota: Este método puede necesitar ajustes según la API real
        try:
            # Intentar endpoint de health para obtener info del nodo
            port_map = {"node-1": "8001", "node-2": "8002", "node-3": "8003"}
            port = port_map.get(node_id, "8001")
            
            base = self.base_url.rsplit(":", 1)[0]
            node_url = f"{base}:{port}{API_V1}"
            
            async with session.get(f"{node_url}/documents/local-index") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("documents", [])
        except:
            pass
        
        return []
    
    async def fetch_all_documents_admin(self, session: aiohttp.ClientSession) -> Dict[str, List[Dict]]:
        """Obtener todos los documentos usando endpoint administrativo"""
        result = {}
        
        # Puertos de los nodos
        ports = ["8001", "8002", "8003"]
        base = self.base_url.rsplit(":", 1)[0]
        
        for port in ports:
            node_url = f"{base}:{port}{API_V1}"
            node_id = f"node-{int(port) - 8000}"
            
            try:
                # Intentar diferentes endpoints
                endpoints = [
                    "/debug/documents",
                    "/admin/documents",
                    "/documents/all",
                    "/internal/documents"
                ]
                
                for endpoint in endpoints:
                    try:
                        async with session.get(f"{node_url}{endpoint}", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                docs = data if isinstance(data, list) else data.get("documents", [])
                                result[node_id] = docs
                                break
                    except:
                        continue
                
                if node_id not in result:
                    result[node_id] = []
                    
            except Exception as e:
                result[node_id] = []
        
        return result
    
    async def fetch_via_search(self, session: aiohttp.ClientSession) -> Dict[str, List[Dict]]:
        """Obtener documentos usando búsqueda general"""
        result = defaultdict(list)
        seen_docs = set()
        
        ports = ["8001", "8002", "8003"]
        base = self.base_url.rsplit(":", 1)[0]
        
        for port in ports:
            node_url = f"{base}:{port}{API_V1}"
            node_id = f"node-{int(port) - 8000}"
            
            try:
                # Buscar con query vacío o asterisco
                params = {"q": "*", "page": 1, "page_size": 1000}
                async with session.get(f"{node_url}/search", params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = data.get("results", [])
                        
                        for doc in results:
                            doc_id = doc.get("document_id") or doc.get("id")
                            if doc_id and doc_id not in seen_docs:
                                doc["source_node"] = doc.get("source_node", node_id)
                                result[doc["source_node"]].append(doc)
                                seen_docs.add(doc_id)
                                
            except Exception:
                pass
        
        return dict(result)
    
    async def fetch_via_health(self, session: aiohttp.ClientSession) -> Dict[str, Any]:
        """Obtener información de nodos desde health"""
        ports = ["8001", "8002", "8003"]
        base = self.base_url.rsplit(":", 1)[0]
        result = {}
        
        for port in ports:
            node_url = f"{base}:{port}{API_V1}"
            node_id = f"node-{int(port) - 8000}"
            
            try:
                async with session.get(f"{node_url}/health/") as resp:
                    if resp.status == 200:
                        health = await resp.json()
                        result[node_id] = {
                            "status": health.get("status", "unknown"),
                            "documents_count": health.get("documents_count", 0),
                            "node_info": health.get("node_info", {})
                        }
            except:
                result[node_id] = {"status": "unreachable", "documents_count": 0}
        
        return result
    
    async def fetch_node_index(self, session: aiohttp.ClientSession) -> Dict[str, List[Dict]]:
        """Obtener índice de documentos de cada nodo"""
        result = {}
        ports = ["8001", "8002", "8003"]
        base = self.base_url.rsplit(":", 1)[0]
        
        for port in ports:
            node_url = f"{base}:{port}{API_V1}"
            node_id = f"node-{int(port) - 8000}"
            
            try:
                # Endpoint de índice local
                async with session.get(f"{node_url}/documents/local-index") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        docs = data.get("documents", [])
                        # Añadir información del nodo a cada documento
                        for doc in docs:
                            doc["_located_on"] = node_id
                            doc["_port"] = port
                        result[node_id] = docs
                    else:
                        result[node_id] = []
            except Exception as e:
                result[node_id] = []
        
        return result
    
    async def collect_data(self):
        """Recopilar todos los datos de los nodos"""
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=TIMEOUT)) as session:
            # Obtener información de salud de los nodos
            self.nodes_info = await self.fetch_via_health(session)
            
            # Obtener documentos por nodo usando el endpoint local-index
            self.documents_by_node = await self.fetch_node_index(session)
            
            # Procesar datos para análisis de replicación
            for node_id, docs in self.documents_by_node.items():
                for doc in docs:
                    doc_id = doc.get("id") or doc.get("document_id")
                    if doc_id:
                        self.document_locations[doc_id].append(node_id)
                        if doc_id not in self.all_documents:
                            self.all_documents[doc_id] = doc
    
    def print_table_format(self):
        """Imprimir en formato tabla"""
        print()
        print(colored("═" * 80, "cyan"))
        print(colored("  REPLICATION VIEWER - DistriSearch  ", "bold"))
        print(colored("═" * 80, "cyan"))
        print(f"  Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Base URL: {self.base_url}")
        print(colored("═" * 80, "cyan"))
        
        # Resumen de nodos
        print(colored("\n📊 ESTADO DE NODOS:", "bold"))
        print("-" * 50)
        
        for node_id, info in sorted(self.nodes_info.items()):
            status = info.get("status", "unknown")
            doc_count = len(self.documents_by_node.get(node_id, []))
            
            status_color = "green" if status == "healthy" else "yellow" if status == "degraded" else "red"
            node_color = get_node_color(node_id)
            
            print(f"  {colored(node_id, node_color)}: "
                  f"{colored(status, status_color)} | "
                  f"Documentos: {colored(str(doc_count), 'white')}")
        
        # Documentos por nodo
        print(colored("\n📁 DOCUMENTOS POR NODO:", "bold"))
        
        for node_id in sorted(self.documents_by_node.keys()):
            docs = self.documents_by_node[node_id]
            node_color = get_node_color(node_id)
            
            print(f"\n{colored('─' * 60, node_color)}")
            print(f"  {colored(node_id.upper(), node_color)} ({len(docs)} documentos)")
            print(colored("─" * 60, node_color))
            
            if not docs:
                print(colored("    (vacío)", "yellow"))
                continue
            
            # Header
            print(f"  {'ID':<12} │ {'Título':<25} │ {'Dueño':<15} │ {'Tags'}")
            print(f"  {'-'*12}-┼-{'-'*25}-┼-{'-'*15}-┼-{'-'*20}")
            
            for doc in docs:
                doc_id = doc.get("id", doc.get("document_id", "?"))[:10]
                title = doc.get("title", "Sin título")[:24]
                owner = doc.get("owner_id", doc.get("user_id", "?"))
                if len(owner) > 14:
                    owner = owner[:12] + ".."
                tags = ", ".join(doc.get("tags", [])[:3])[:18]
                
                # Filtrar por usuario si se especificó
                if self.filter_user:
                    owner_match = self.filter_user.lower() in owner.lower()
                    if not owner_match:
                        continue
                
                print(f"  {doc_id:<12} │ {title:<25} │ {owner:<15} │ {tags}")
        
        # Análisis de replicación
        print(colored("\n🔄 ANÁLISIS DE REPLICACIÓN:", "bold"))
        print("-" * 60)
        
        total_unique = len(self.all_documents)
        replicated_docs = {k: v for k, v in self.document_locations.items() if len(v) >= 2}
        single_copy_docs = {k: v for k, v in self.document_locations.items() if len(v) == 1}
        
        print(f"  Documentos únicos totales: {colored(str(total_unique), 'white')}")
        print(f"  Documentos replicados (≥2 nodos): {colored(str(len(replicated_docs)), 'green')}")
        print(f"  Documentos sin replicar (1 nodo): {colored(str(len(single_copy_docs)), 'yellow')}")
        
        if replicated_docs:
            print(colored("\n  📋 Documentos replicados:", "bold"))
            for doc_id, nodes in list(replicated_docs.items())[:10]:
                doc = self.all_documents.get(doc_id, {})
                title = doc.get("title", "?")[:30]
                nodes_str = ", ".join(sorted(nodes))
                print(f"    • {title}: [{nodes_str}]")
            
            if len(replicated_docs) > 10:
                print(f"    ... y {len(replicated_docs) - 10} más")
        
        if single_copy_docs:
            print(colored("\n  ⚠️  Documentos sin replicar:", "yellow"))
            for doc_id, nodes in list(single_copy_docs.items())[:5]:
                doc = self.all_documents.get(doc_id, {})
                title = doc.get("title", "?")[:30]
                print(f"    • {title}: solo en {nodes[0]}")
            
            if len(single_copy_docs) > 5:
                print(f"    ... y {len(single_copy_docs) - 5} más")
        
        # Factor de replicación promedio
        if self.document_locations:
            avg_replication = sum(len(v) for v in self.document_locations.values()) / len(self.document_locations)
            print(f"\n  Factor de replicación promedio: {colored(f'{avg_replication:.2f}', 'cyan')}")
        
        print(colored("\n" + "═" * 80, "cyan"))
    
    def print_json_format(self):
        """Imprimir en formato JSON"""
        output = {
            "timestamp": datetime.now().isoformat(),
            "base_url": self.base_url,
            "nodes": self.nodes_info,
            "documents_by_node": {
                node: [
                    {
                        "id": d.get("id") or d.get("document_id"),
                        "title": d.get("title"),
                        "owner_id": d.get("owner_id") or d.get("user_id"),
                        "tags": d.get("tags", [])
                    }
                    for d in docs
                ]
                for node, docs in self.documents_by_node.items()
            },
            "replication_analysis": {
                "total_unique_documents": len(self.all_documents),
                "replicated_documents": len([v for v in self.document_locations.values() if len(v) >= 2]),
                "single_copy_documents": len([v for v in self.document_locations.values() if len(v) == 1]),
                "document_locations": dict(self.document_locations)
            }
        }
        print(json.dumps(output, indent=2, default=str))
    
    def print_compact_format(self):
        """Imprimir formato compacto"""
        print(f"\n{'='*60}")
        print(f"REPLICATION STATUS @ {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'='*60}")
        
        for node_id, docs in sorted(self.documents_by_node.items()):
            color = get_node_color(node_id)
            print(colored(f"\n[{node_id}] ({len(docs)} docs):", color))
            
            for doc in docs:
                title = doc.get("title", "?")[:40]
                owner = doc.get("owner_id", "?")[:15]
                print(f"  • {title} (owner: {owner})")
    
    async def run(self):
        """Ejecutar el viewer"""
        await self.collect_data()
        
        if self.output_format == "json":
            self.print_json_format()
        elif self.output_format == "compact":
            self.print_compact_format()
        else:
            self.print_table_format()


async def main():
    parser = argparse.ArgumentParser(
        description="View document replication status across DistriSearch nodes"
    )
    parser.add_argument(
        "--base-url", 
        default=DEFAULT_BASE_URL,
        help=f"Base URL (default: {DEFAULT_BASE_URL})"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["table", "json", "compact"],
        default="table",
        help="Output format (default: table)"
    )
    parser.add_argument(
        "--user", "-u",
        help="Filter documents by owner/user"
    )
    
    args = parser.parse_args()
    
    viewer = ReplicationViewer(
        base_url=args.base_url,
        output_format=args.format,
        filter_user=args.user
    )
    
    await viewer.run()


if __name__ == "__main__":
    asyncio.run(main())
