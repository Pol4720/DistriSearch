#!/usr/bin/env python3
"""
Replication Viewer - Ver archivos en cada nodo con sus dueños
=============================================================

Script para visualizar la distribución y replicación de documentos
en el sistema DistriSearch usando la API REST.

Uso:
    python scripts/view_replication.py
    python scripts/view_replication.py --format json
    python scripts/view_replication.py --user alice

Muestra:
- Documentos en cada nodo
- Dueño de cada documento  
- Factor de replicación real
- Documentos únicos vs replicados
"""

import argparse
import json
import sys
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any
from collections import defaultdict


BASE_URL = "http://192.168.61.32"
NODES = [
    {"id": "node-1", "port": "8001"},
    {"id": "node-2", "port": "8002"},
    {"id": "node-3", "port": "8003"}
]

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
    "node-3": "magenta"
}


def colored(text: str, color: str) -> str:
    """Aplicar color al texto"""
    return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"


def get_node_color(node_id: str) -> str:
    """Obtener color para un nodo"""
    return NODE_COLORS.get(node_id, "white")


class ReplicationViewer:
    def __init__(self, output_format: str = "table", filter_user: Optional[str] = None):
        self.output_format = output_format
        self.filter_user = filter_user
        
        # Datos recopilados
        self.documents_by_node: Dict[str, List[Dict]] = defaultdict(list)
        self.users_cache: Dict[str, str] = {}  # user_id -> username
        self.all_documents: Dict[str, Dict] = {}  # doc_id -> doc info
        self.document_locations: Dict[str, List[str]] = defaultdict(list)  # doc_id -> [nodes]
        self.nodes_status: Dict[str, str] = {}
    
    def fetch_node_health(self, node: Dict) -> Dict:
        """Obtener información de salud del nodo"""
        try:
            url = f"{BASE_URL}:{node['port']}/api/v1/health"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                return resp.json()
        except:
            pass
        return {"status": "unreachable"}
    
    def fetch_node_users(self, node: Dict) -> Dict[str, str]:
        """Obtener usuarios registrados en el nodo"""
        users = {}
        # Los usuarios están en la base de datos local de cada nodo
        # No hay endpoint público para esto, usaremos el owner_id directamente
        return users
    
    def fetch_node_documents_via_search(self, node: Dict) -> List[Dict]:
        """Obtener documentos del nodo usando búsqueda con filtro de nodo"""
        try:
            url = f"{BASE_URL}:{node['port']}/api/v1/search"
            # Buscar todos los documentos
            resp = requests.get(url, params={"q": "*", "page_size": 500}, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                
                # Filtrar solo los que tienen este nodo como source
                local_docs = []
                for doc in results:
                    source = doc.get("source_node", "")
                    # Verificar si este documento es local a este nodo
                    if node['id'] in source or node['port'] in source:
                        local_docs.append(doc)
                    elif not source:
                        # Si no hay source_node, asumimos que es local
                        doc["_node"] = node["id"]
                        local_docs.append(doc)
                
                return local_docs
        except Exception as e:
            print(f"Error buscando en {node['id']}: {e}")
        return []
    
    def fetch_all_users(self) -> Dict[str, str]:
        """Obtener mapping de owner_id -> username de todos los nodos"""
        users = {}
        # Como no hay endpoint público de usuarios, usaremos el health para ver info
        return users
    
    def collect_data(self):
        """Recopilar todos los datos de los nodos"""
        all_docs_seen = set()
        
        for node in NODES:
            node_id = node["id"]
            
            # Obtener estado del nodo
            health = self.fetch_node_health(node)
            self.nodes_status[node_id] = health.get("status", "unknown")
            
            # Obtener documentos mediante la búsqueda interna
            # Cada nodo reporta sus documentos locales cuando buscamos en él
            try:
                url = f"{BASE_URL}:{node['port']}/api/v1/internal/debug/index"
                resp = requests.get(url, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    docs = data.get("documents", [])
                    for doc in docs:
                        doc_id = doc.get("id") or doc.get("document_id")
                        if doc_id:
                            self.documents_by_node[node_id].append(doc)
                            self.document_locations[doc_id].append(node_id)
                            if doc_id not in self.all_documents:
                                self.all_documents[doc_id] = doc
            except:
                pass
            
            # Alternativa: usar endpoint de búsqueda para ver qué tiene cada nodo
            if not self.documents_by_node.get(node_id):
                try:
                    # Buscar con node filter si existe
                    url = f"{BASE_URL}:{node['port']}/api/v1/search"
                    resp = requests.get(url, params={"q": "*", "page_size": 500, "local_only": "true"}, timeout=10)
                    if resp.status_code == 200:
                        data = resp.json()
                        for doc in data.get("results", []):
                            doc_id = doc.get("document_id") or doc.get("id")
                            # Solo añadir si source_node coincide con este nodo
                            source = doc.get("source_node", "")
                            if source == node_id or node['port'] in source or not source:
                                if doc_id and doc_id not in all_docs_seen:
                                    all_docs_seen.add(doc_id)
                                    self.documents_by_node[node_id].append(doc)
                                    self.document_locations[doc_id].append(node_id)
                                    if doc_id not in self.all_documents:
                                        self.all_documents[doc_id] = doc
                except:
                    pass
    
    def get_username(self, owner_id: str) -> str:
        """Obtener username para un owner_id"""
        return self.users_cache.get(owner_id, owner_id[:12] + ".." if len(owner_id) > 14 else owner_id)
    
    def print_table_format(self):
        """Imprimir en formato tabla"""
        print()
        print(colored("═" * 80, "cyan"))
        print(colored("  REPLICATION VIEWER - DistriSearch  ", "bold"))
        print(colored("═" * 80, "cyan"))
        print(f"  Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Base URL: {BASE_URL}")
        print(colored("═" * 80, "cyan"))
        
        # Resumen de nodos
        print(colored("\n📊 ESTADO DE NODOS:", "bold"))
        print("-" * 50)
        
        total_docs = 0
        for node in NODES:
            node_id = node["id"]
            status = self.nodes_status.get(node_id, "unknown")
            doc_count = len(self.documents_by_node.get(node_id, []))
            total_docs += doc_count
            
            status_color = "green" if status == "healthy" else "yellow" if status == "degraded" else "red"
            node_color = get_node_color(node_id)
            
            print(f"  {colored(node_id, node_color)}: "
                  f"{colored(status, status_color)} | "
                  f"{colored(str(doc_count), 'white')} documentos")
        
        print(f"\n  Total (con réplicas): {total_docs}")
        
        # Documentos por nodo
        print(colored("\n📁 DOCUMENTOS POR NODO:", "bold"))
        
        for node_id in ["node-1", "node-2", "node-3"]:
            docs = self.documents_by_node.get(node_id, [])
            node_color = get_node_color(node_id)
            
            print(f"\n{colored('─' * 70, node_color)}")
            print(f"  {colored(node_id.upper(), node_color)} ({len(docs)} documentos)")
            print(colored("─" * 70, node_color))
            
            if not docs:
                print(colored("    (vacío)", "yellow"))
                continue
            
            # Header
            print(f"  {'Título':<30} │ {'Dueño':<15} │ {'Tags':<15} │ {'Archivo'}")
            print(f"  {'-'*30}-┼-{'-'*15}-┼-{'-'*15}-┼-{'-'*15}")
            
            for doc in docs:
                title = doc.get("title", "Sin título")[:29]
                owner_id = doc.get("owner_id", "?")
                owner = self.get_username(owner_id)[:14]
                tags = ", ".join(doc.get("tags", [])[:2])[:14]
                has_file = "📄" if doc.get("file_path") else "-"
                
                # Filtrar por usuario si se especificó
                if self.filter_user:
                    owner_full = self.get_username(owner_id)
                    if self.filter_user.lower() not in owner_full.lower():
                        continue
                
                print(f"  {title:<30} │ {owner:<15} │ {tags:<15} │ {has_file}")
        
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
                title = doc.get("title", "?")[:35]
                owner = self.get_username(doc.get("owner_id", "?"))
                nodes_str = ", ".join(sorted(nodes))
                print(f"    • {title} (dueño: {owner})")
                print(f"      → Ubicado en: [{nodes_str}]")
            
            if len(replicated_docs) > 10:
                print(f"    ... y {len(replicated_docs) - 10} más")
        
        if single_copy_docs:
            print(colored("\n  ⚠️  Documentos sin replicar:", "yellow"))
            for doc_id, nodes in list(single_copy_docs.items())[:5]:
                doc = self.all_documents.get(doc_id, {})
                title = doc.get("title", "?")[:35]
                owner = self.get_username(doc.get("owner_id", "?"))
                print(f"    • {title} (dueño: {owner})")
                print(f"      → Solo en: {nodes[0]}")
            
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
            "mongo_uri": MONGO_URI,
            "documents_by_node": {
                node: [
                    {
                        "id": d.get("id"),
                        "title": d.get("title"),
                        "owner_id": d.get("owner_id"),
                        "owner_username": self.get_username(d.get("owner_id", "")),
                        "tags": d.get("tags", []),
                        "has_file": bool(d.get("file_path"))
                    }
                    for d in docs
                ]
                for node, docs in self.documents_by_node.items()
            },
            "replication_analysis": {
                "total_unique_documents": len(self.all_documents),
                "replicated_documents": len([v for v in self.document_locations.values() if len(v) >= 2]),
                "single_copy_documents": len([v for v in self.document_locations.values() if len(v) == 1]),
                "document_locations": {
                    doc_id: {
                        "title": self.all_documents.get(doc_id, {}).get("title"),
                        "owner": self.get_username(self.all_documents.get(doc_id, {}).get("owner_id", "")),
                        "nodes": nodes
                    }
                    for doc_id, nodes in self.document_locations.items()
                }
            }
        }
        print(json.dumps(output, indent=2, default=str))
    
    def print_compact_format(self):
        """Imprimir formato compacto"""
        print(f"\n{'='*60}")
        print(f"REPLICATION STATUS @ {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'='*60}")
        
        for node_id in ["node-1", "node-2", "node-3"]:
            docs = self.documents_by_node.get(node_id, [])
            color = get_node_color(node_id)
            print(colored(f"\n[{node_id}] ({len(docs)} docs):", color))
            
            for doc in docs:
                title = doc.get("title", "?")[:40]
                owner = self.get_username(doc.get("owner_id", "?"))[:15]
                
                if self.filter_user and self.filter_user.lower() not in owner.lower():
                    continue
                    
                print(f"  • {title} (dueño: {owner})")
    
    def run(self):
        """Ejecutar el viewer"""
        self.collect_data()
        
        if self.output_format == "json":
            self.print_json_format()
        elif self.output_format == "compact":
            self.print_compact_format()
        else:
            self.print_table_format()


def main():
    parser = argparse.ArgumentParser(
        description="View document replication status across DistriSearch nodes"
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
        output_format=args.format,
        filter_user=args.user
    )
    
    viewer.run()


if __name__ == "__main__":
    main()
