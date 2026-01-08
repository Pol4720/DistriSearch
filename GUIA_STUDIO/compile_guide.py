#!/usr/bin/env python3
"""
Script para combinar todos los archivos markdown de GUIA_STUDIO en uno solo.
"""
import os
from pathlib import Path
from datetime import datetime

# Orden de los capítulos
CAPITULOS = [
    "00_Introduccion",
    "01_Arquitectura_General",
    "02_Vectorizacion_Busqueda",
    "03_Particionamiento",
    "04_Rebalanceo",
    "05_Replicacion",
    "06_Tolerancia_Fallos",
    "07_Consenso_Raft",
    "08_Docker_Swarm",
    "09_DNS_Descubrimiento",
    "10_Load_Balancer",
    "11_Almacenamiento",
    "12_Gossip_Protocol",
    "13_CAP_Theorem",
    "14_Despliegue",
    "15_API_Backend",
    "16_Frontend",
    "17_Testing",
    "18_Control_Center",
]

def get_markdown_files(folder: Path) -> list:
    """Obtiene archivos markdown ordenados (README primero, luego numerados)"""
    files = list(folder.glob("*.md"))
    
    # Separar README de otros archivos
    readme = [f for f in files if f.name.upper() == "README.MD"]
    others = [f for f in files if f.name.upper() != "README.MD"]
    
    # Ordenar otros por nombre (están numerados)
    others.sort(key=lambda x: x.name)
    
    # README primero, luego los demás
    return readme + others


def clean_content(content: str) -> str:
    """Limpia el contenido de marcadores de código innecesarios"""
    lines = content.split('\n')
    
    # Remover backticks de inicio si es markdown wrapper
    if lines and lines[0].strip() in ['````markdown', '```markdown']:
        lines = lines[1:]
    
    # Remover backticks de fin
    if lines and lines[-1].strip() in ['````', '```']:
        lines = lines[:-1]
    
    return '\n'.join(lines)


def main():
    # Ruta base
    guia_path = Path(__file__).parent
    output_file = guia_path / "GUIA_COMPLETA_DISTRISEARCH.md"
    
    # Contenido combinado
    combined = []
    
    # Portada
    combined.append(f"""# DistriSearch - Guía de Estudio Completa

**Sistema de Búsqueda Distribuida**

Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}

---

## Tabla de Contenidos

""")
    
    # Generar tabla de contenidos
    for i, cap in enumerate(CAPITULOS):
        nombre = cap.replace("_", " ").split(" ", 1)[1] if "_" in cap else cap
        combined.append(f"{i}. [{nombre}](#{cap.lower().replace('_', '-')})\n")
    
    combined.append("\n---\n\n")
    
    # Procesar cada capítulo
    for cap in CAPITULOS:
        folder = guia_path / cap
        if not folder.exists():
            print(f"ADVERTENCIA: No existe {folder}")
            continue
        
        # Título del capítulo
        titulo = cap.replace("_", " ")
        combined.append(f"\n# {titulo}\n\n")
        
        # Obtener archivos markdown
        files = get_markdown_files(folder)
        
        for md_file in files:
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Limpiar contenido
                content = clean_content(content)
                
                # Añadir separador si no es README
                if md_file.name.upper() != "README.MD":
                    combined.append(f"\n---\n\n")
                
                combined.append(content)
                combined.append("\n\n")
                
                print(f"  ✓ {md_file.name}")
                
            except Exception as e:
                print(f"  ✗ Error leyendo {md_file}: {e}")
        
        print(f"✓ {cap}")
    
    # Escribir archivo combinado
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(''.join(combined))
    
    print(f"\n✅ Guía combinada generada: {output_file}")
    print(f"   Tamaño: {output_file.stat().st_size / 1024:.1f} KB")
    
    return output_file


if __name__ == "__main__":
    main()
