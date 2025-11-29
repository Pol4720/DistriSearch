"""
Utilidades comunes para DistriSearch.
"""
import json
from typing import Any, Dict


def format_binary_id(node_id: int, dimensions: int = 20) -> str:
    """
    Formatea un ID como string binario.
    
    Args:
        node_id: ID del nodo
        dimensions: Número de bits
    
    Returns:
        String binario formateado
    """
    return format(node_id, f'0{dimensions}b')


def calculate_network_diameter(num_nodes: int, dimensions: int) -> int:
    """
    Calcula el diámetro de la red (máximo número de saltos).
    
    Para un hipercubo completo, el diámetro es igual a las dimensiones.
    Para redes parciales, puede ser mayor.
    
    Args:
        num_nodes: Número de nodos activos
        dimensions: Dimensiones del hipercubo
    
    Returns:
        Diámetro estimado
    """
    max_nodes = 2 ** dimensions
    if num_nodes >= max_nodes * 0.8:
        # Red casi completa
        return dimensions
    else:
        # Red parcial, estimar basado en densidad
        import math
        return min(dimensions * 2, int(math.log2(num_nodes) * 1.5)) if num_nodes > 1 else 0


def pretty_print_json(data: Dict[str, Any]) -> str:
    """
    Formatea JSON para impresión legible.
    
    Args:
        data: Diccionario a formatear
    
    Returns:
        String JSON formateado
    """
    return json.dumps(data, indent=2, ensure_ascii=False)


def estimate_index_size(num_terms: int, num_documents: int, avg_terms_per_doc: int = 50) -> Dict[str, Any]:
    """
    Estima el tamaño del índice en memoria.
    
    Args:
        num_terms: Número de términos únicos
        num_documents: Número de documentos
        avg_terms_per_doc: Términos promedio por documento
    
    Returns:
        Diccionario con estadísticas
    """
    # Estimaciones muy aproximadas
    bytes_per_term = 50  # String + overhead
    bytes_per_posting = 100  # doc_id + score + overhead
    
    total_postings = num_documents * avg_terms_per_doc
    
    terms_size = num_terms * bytes_per_term
    postings_size = total_postings * bytes_per_posting
    total_size = terms_size + postings_size
    
    return {
        'num_terms': num_terms,
        'num_documents': num_documents,
        'total_postings': total_postings,
        'estimated_size_bytes': total_size,
        'estimated_size_mb': round(total_size / (1024 * 1024), 2)
    }


def visualize_hypercube_neighbors(node_id: int, dimensions: int = 4) -> str:
    """
    Crea visualización ASCII de vecinos en el hipercubo.
    
    Args:
        node_id: ID del nodo
        dimensions: Dimensiones (recomendado <= 4 para visualización)
    
    Returns:
        String con visualización
    """
    if dimensions > 6:
        return "Visualización no disponible para más de 6 dimensiones"
    
    from hypercube import HypercubeNode
    
    node = HypercubeNode(node_id, dimensions)
    neighbors = node.get_neighbors()
    
    lines = []
    lines.append(f"Nodo: {node_id} ({node.binary_address})")
    lines.append(f"Vecinos ({len(neighbors)}):")
    
    for i, neighbor in enumerate(neighbors):
        neighbor_node = HypercubeNode(neighbor, dimensions)
        lines.append(f"  Bit {i}: {neighbor} ({neighbor_node.binary_address})")
    
    return "\n".join(lines)


def generate_test_documents(num_docs: int = 10) -> list:
    """
    Genera documentos de prueba.
    
    Args:
        num_docs: Número de documentos a generar
    
    Returns:
        Lista de tuplas (doc_id, content)
    """
    templates = [
        "Python es un lenguaje de programación interpretado",
        "JavaScript se usa para desarrollo web frontend",
        "Machine learning permite entrenar modelos predictivos",
        "El desarrollo web moderno usa frameworks como React",
        "Bases de datos relacionales usan SQL para consultas",
        "Docker permite containerizar aplicaciones",
        "Kubernetes orquesta contenedores en producción",
        "Git es un sistema de control de versiones",
        "REST APIs permiten comunicación entre servicios",
        "GraphQL es una alternativa a REST para APIs",
    ]
    
    docs = []
    for i in range(num_docs):
        doc_id = f"doc{i+1}"
        content = templates[i % len(templates)]
        docs.append((doc_id, content))
    
    return docs


def benchmark_search_performance(node, query: str, iterations: int = 10):
    """
    Benchmark simple de rendimiento de búsqueda.
    
    Args:
        node: Nodo a testear
        query: Consulta a ejecutar
        iterations: Número de iteraciones
    
    Returns:
        Diccionario con estadísticas
    """
    import asyncio
    import time
    
    async def run_benchmark():
        times = []
        
        for _ in range(iterations):
            start = time.time()
            await node.search(query)
            elapsed = time.time() - start
            times.append(elapsed)
        
        return {
            'query': query,
            'iterations': iterations,
            'min_time_ms': round(min(times) * 1000, 2),
            'max_time_ms': round(max(times) * 1000, 2),
            'avg_time_ms': round(sum(times) / len(times) * 1000, 2),
        }
    
    return asyncio.run(run_benchmark())
