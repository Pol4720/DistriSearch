#!/usr/bin/env python3
"""
Replication Viewer - Ver archivos en cada nodo con sus dueños
Usa el endpoint /api/v1/internal/search para ver documentos LOCALES de cada nodo
"""

import requests
from collections import defaultdict
from datetime import datetime

BASE_URL = "http://192.168.61.32"
PORTS = ["8001", "8002", "8003"]

def main():
    print("\n" + "="*70)
    print("  REPLICATION VIEWER - DistriSearch")
    print("="*70)
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    # Consultar CADA NODO usando endpoint INTERNO/LOCAL
    docs_by_node = {}
    queries = ["document", "test", "a", "e", "i", "o", "u", "the", "de", "la", "pdf", "report", "file"]
    
    for port in PORTS:
        node_id = f"node-{int(port) - 8000}"
        seen_ids = set()
        node_docs = []
        
        for query in queries:
            try:
                # Usar endpoint INTERNO que solo busca en MongoDB local
                resp = requests.post(
                    f"{BASE_URL}:{port}/api/v1/internal/search",
                    json={"query": query, "top_k": 500},
                    timeout=10
                )
                data = resp.json()
                for doc in data.get("results", []):
                    doc_id = doc.get("document_id")
                    if doc_id and doc_id not in seen_ids:
                        seen_ids.add(doc_id)
                        node_docs.append(doc)
            except Exception as e:
                pass
        
        docs_by_node[node_id] = node_docs
    
    # Mostrar por nodo
    colors = {"node-1": "\033[92m", "node-2": "\033[94m", "node-3": "\033[95m"}
    reset = "\033[0m"
    
    total = 0
    for node_id in ["node-1", "node-2", "node-3"]:
        docs = docs_by_node.get(node_id, [])
        total += len(docs)
        color = colors.get(node_id, "")
        
        print(f"\n{color}{'─'*70}")
        print(f"  {node_id.upper()} ({len(docs)} documentos)")
        print(f"{'─'*70}{reset}")
        
        if not docs:
            print("    (vacío)")
            continue
        
        print(f"  {'Título':<35} │ {'ID':<25}")
        print(f"  {'-'*35}-┼-{'-'*25}")
        
        for doc in docs:
            title = doc.get("title", "?")[:34]
            doc_id = doc.get("document_id", "?")[:24]
            print(f"  {title:<35} │ {doc_id:<25}")
    
    # Análisis de replicación
    print(f"\n{'='*70}")
    print("  ANÁLISIS DE REPLICACIÓN")
    print(f"{'='*70}")
    
    # Contar en cuántos nodos está cada documento
    doc_locations = defaultdict(set)
    doc_titles = {}
    
    for node_id, docs in docs_by_node.items():
        for doc in docs:
            doc_id = doc.get("document_id")
            if doc_id:
                doc_locations[doc_id].add(node_id)
                if doc_id not in doc_titles:
                    doc_titles[doc_id] = doc.get("title", "?")
    
    unique_docs = len(doc_locations)
    replicated = sum(1 for nodes in doc_locations.values() if len(nodes) >= 2)
    single = sum(1 for nodes in doc_locations.values() if len(nodes) == 1)
    
    print(f"\n  Documentos únicos: {unique_docs}")
    print(f"  Replicados (≥2 nodos): \033[92m{replicated}\033[0m")
    print(f"  Sin replicar (1 nodo): \033[93m{single}\033[0m")
    print(f"  Total instancias: {total}")
    
    if doc_locations:
        avg = sum(len(v) for v in doc_locations.values()) / len(doc_locations)
        print(f"  Factor replicación promedio: \033[96m{avg:.2f}\033[0m")
    
    # Mostrar ubicación de cada documento
    if doc_locations:
        print(f"\n  Ubicación de documentos:")
        for doc_id, nodes in doc_locations.items():
            title = doc_titles.get(doc_id, "?")[:35]
            nodes_str = ", ".join(sorted(nodes))
            status = "\033[92m✓\033[0m" if len(nodes) >= 2 else "\033[93m⚠\033[0m"
            print(f"    {status} {title}: [{nodes_str}]")
    
    print("\n" + "="*70 + "\n")

if __name__ == "__main__":
    main()
