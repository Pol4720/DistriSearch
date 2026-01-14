#!/usr/bin/env python3
"""
Replication Viewer - Ver archivos en cada nodo con sus dueños
Usa el endpoint /api/v1/internal/search para ver documentos LOCALES de cada nodo

Actualizado para sistema Standalone:
  - Máquina A (192.168.1.11): Node-1 (:8001), Node-2 (:8002)
  - Máquina B (192.168.1.13): Node-3 (:8003)

Uso:
    python scripts/view_replication.py
    python scripts/view_replication.py --host 192.168.1.11 --ports 8001,8002,8003
    python scripts/view_replication.py --machine A   # Solo nodos de Máquina A
    python scripts/view_replication.py --machine B   # Solo nodos de Máquina B
"""

import argparse
import requests
from collections import defaultdict
from datetime import datetime

# Importar configuración standalone
try:
    from config_standalone import (
        MACHINE_A_IP, MACHINE_B_IP, 
        DEFAULT_HOST, DEFAULT_PORTS,
        STANDALONE_CONFIG, get_nodes_by_machine
    )
except ImportError:
    # Fallback si no se puede importar
    MACHINE_A_IP = "192.168.1.11"
    MACHINE_B_IP = "192.168.1.13"
    DEFAULT_HOST = MACHINE_A_IP
    DEFAULT_PORTS = ["8001", "8002", "8003"]
    STANDALONE_CONFIG = None
    get_nodes_by_machine = None

def main():
    parser = argparse.ArgumentParser(description="Ver replicación de documentos en DistriSearch")
    parser.add_argument("--host", default=DEFAULT_HOST, 
                        help=f"Host/IP de los nodos (default: {DEFAULT_HOST})")
    parser.add_argument("--ports", default=",".join(DEFAULT_PORTS),
                        help=f"Puertos separados por coma (default: {','.join(DEFAULT_PORTS)})")
    parser.add_argument("--machine", choices=["A", "B", "all"], default="all",
                        help="Filtrar por máquina: A (192.168.1.11), B (192.168.1.13), o all")
    args = parser.parse_args()
    
    # Determinar nodos a consultar
    if args.machine == "all":
        # Consultar todos los nodos en ambas IPs
        nodes_to_query = []
        if STANDALONE_CONFIG:
            for node in STANDALONE_CONFIG["nodes"]:
                nodes_to_query.append((node["ip"], node["api_port"], node["id"]))
        else:
            # Fallback: usar host único con múltiples puertos
            ports = [p.strip() for p in args.ports.split(",")]
            for port in ports:
                node_id = f"node-{int(port) - 8000}"
                nodes_to_query.append((args.host, port, node_id))
    elif args.machine in ["A", "B"]:
        # Solo nodos de una máquina específica
        if get_nodes_by_machine:
            nodes = get_nodes_by_machine(args.machine)
            nodes_to_query = [(n["ip"], n["api_port"], n["id"]) for n in nodes]
        else:
            ip = MACHINE_A_IP if args.machine == "A" else MACHINE_B_IP
            if args.machine == "A":
                nodes_to_query = [(ip, 8001, "node-1"), (ip, 8002, "node-2")]
            else:
                nodes_to_query = [(ip, 8003, "node-3")]
    else:
        ports = [p.strip() for p in args.ports.split(",")]
        nodes_to_query = [(args.host, p, f"node-{int(p) - 8000}") for p in ports]
    
    print("\n" + "="*70)
    print("  REPLICATION VIEWER - DistriSearch Standalone")
    print("="*70)
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Máquina A: {MACHINE_A_IP} (node-1, node-2)")
    print(f"  Máquina B: {MACHINE_B_IP} (node-3)")
    print(f"  Consultando: {len(nodes_to_query)} nodos")
    print("="*70)
    
    # Consultar CADA NODO usando endpoint INTERNO/LOCAL
    docs_by_node = {}
    queries = ["document", "test", "a", "e", "i", "o", "u", "the", "de", "la", "pdf", "report", "file"]
    
    for ip, port, node_id in nodes_to_query:
        seen_ids = set()
        node_docs = []
        
        for query in queries:
            try:
                # Usar endpoint INTERNO que solo busca en MongoDB local
                resp = requests.post(
                    f"http://{ip}:{port}/api/v1/internal/search",
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
    colors = {
        "node-1": "\033[92m", "node-2": "\033[94m", "node-3": "\033[95m",
        "node-4": "\033[96m", "node-5": "\033[93m", "node-6": "\033[91m",
    }
    reset = "\033[0m"
    
    total = 0
    for ip, port, node_id in nodes_to_query:
        docs = docs_by_node.get(node_id, [])
        total += len(docs)
        color = colors.get(node_id, "\033[0m")
        
        machine_label = "Máquina A" if ip == MACHINE_A_IP else "Máquina B"
        
        print(f"\n{color}{'─'*70}")
        print(f"  {node_id.upper()} ({machine_label} - {ip}:{port}) - {len(docs)} documentos")
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
