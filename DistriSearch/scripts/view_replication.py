#!/usr/bin/env python3
"""
Replication Viewer - Ver archivos en cada nodo con sus dueños
"""

import requests
from collections import defaultdict
from datetime import datetime

BASE_URL = "http://192.168.61.32:8001"

def main():
    print("\n" + "="*70)
    print("  REPLICATION VIEWER - DistriSearch")
    print("="*70)
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    # Buscar TODOS los documentos
    try:
        resp = requests.post(
            f"{BASE_URL}/api/v1/search",
            json={"query": "*", "page_size": 500},
            timeout=10
        )
        data = resp.json()
        results = data.get("results", [])
    except Exception as e:
        print(f"Error: {e}")
        return
    
    # Agrupar por nodo
    docs_by_node = defaultdict(list)
    for doc in results:
        node = doc.get("node_id", "unknown")
        docs_by_node[node].append(doc)
    
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
        
        print(f"  {'Título':<35} │ {'ID':<20}")
        print(f"  {'-'*35}-┼-{'-'*20}")
        
        for doc in docs:
            title = doc.get("title", "?")[:34]
            doc_id = doc.get("document_id", "?")[:19]
            print(f"  {title:<35} │ {doc_id:<20}")
    
    # Análisis de replicación
    print(f"\n{'='*70}")
    print("  ANÁLISIS DE REPLICACIÓN")
    print(f"{'='*70}")
    
    # Contar en cuántos nodos está cada documento
    doc_locations = defaultdict(list)
    for doc in results:
        doc_id = doc.get("document_id")
        node = doc.get("node_id")
        if doc_id and node:
            doc_locations[doc_id].append(node)
    
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
            # Buscar el título
            title = next((d.get("title") for d in results if d.get("document_id") == doc_id), "?")
            nodes_str = ", ".join(sorted(nodes))
            print(f"    • {title[:30]}: [{nodes_str}]")
    
    print("\n" + "="*70 + "\n")

if __name__ == "__main__":
    main()
