"""
🖥️ Gestión de Nodos DistriSearch
Visualización y control de nodos del sistema distribuido
"""

import streamlit as st
import requests
from datetime import datetime

st.set_page_config(
    page_title="Nodos - Control Center",
    page_icon="🖥️",
    layout="wide",
)

# CSS Moderno
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%);
    }
    
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1e1b4b 0%, #0f172a 100%);
    }
    
    .glass-card {
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(12px);
        border-radius: 16px;
        padding: 1.5rem;
        border: 1px solid rgba(99, 102, 241, 0.2);
        margin-bottom: 1rem;
    }
    
    .node-card {
        background: rgba(30, 41, 59, 0.6);
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        border: 1px solid rgba(99, 102, 241, 0.2);
        transition: all 0.3s ease;
    }
    
    .node-card:hover {
        border-color: rgba(99, 102, 241, 0.5);
        box-shadow: 0 4px 20px rgba(99, 102, 241, 0.1);
    }
    
    .node-card-master {
        border-left: 4px solid #10b981;
        background: linear-gradient(90deg, rgba(16, 185, 129, 0.1), rgba(30, 41, 59, 0.6));
    }
    
    .node-card-slave {
        border-left: 4px solid #6366f1;
    }
    
    .node-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1rem;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid rgba(99, 102, 241, 0.1);
    }
    
    .node-name {
        color: #f1f5f9;
        font-weight: 600;
        font-size: 1.1rem;
    }
    
    .node-components {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 0.75rem;
        margin-top: 1rem;
    }
    
    .component-badge {
        background: rgba(99, 102, 241, 0.1);
        border: 1px solid rgba(99, 102, 241, 0.2);
        border-radius: 8px;
        padding: 0.5rem;
        text-align: center;
        font-size: 0.8rem;
        color: #94a3b8;
    }
    
    .component-badge-active {
        background: rgba(16, 185, 129, 0.1);
        border-color: rgba(16, 185, 129, 0.3);
        color: #34d399;
    }
    
    .node-stats {
        display: flex;
        gap: 1.5rem;
        color: #94a3b8;
        font-size: 0.9rem;
    }
    
    .stat-item {
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.4rem 0.8rem;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    
    .status-healthy {
        background: rgba(16, 185, 129, 0.15);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.4);
    }
    
    .status-unhealthy {
        background: rgba(239, 68, 68, 0.15);
        color: #f87171;
        border: 1px solid rgba(239, 68, 68, 0.4);
    }
    
    .status-unknown {
        background: rgba(245, 158, 11, 0.15);
        color: #fbbf24;
        border: 1px solid rgba(245, 158, 11, 0.4);
    }
    
    .concept-box {
        background: linear-gradient(145deg, rgba(99, 102, 241, 0.1), rgba(30, 41, 59, 0.5));
        border-radius: 12px;
        padding: 1rem;
        border: 1px solid rgba(99, 102, 241, 0.2);
        margin: 0.5rem 0;
    }
    
    .concept-title {
        color: #a855f7;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }
    
    .concept-text {
        color: #cbd5e1;
        font-size: 0.9rem;
        line-height: 1.6;
    }
    
    .arch-diagram {
        background: rgba(15, 23, 42, 0.8);
        border: 1px solid rgba(99, 102, 241, 0.3);
        border-radius: 12px;
        padding: 1.5rem;
        text-align: center;
        color: #94a3b8;
        font-family: monospace;
        font-size: 0.85rem;
        line-height: 1.8;
    }
    
    .stButton > button {
        background: linear-gradient(135deg, #6366f1, #8b5cf6);
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3);
    }
</style>
""", unsafe_allow_html=True)

BACKEND_URL = st.secrets.get("BACKEND_URL", "http://localhost:8888")


def api_get(endpoint: str) -> dict:
    try:
        response = requests.get(f"{BACKEND_URL}/api{endpoint}", timeout=10)
        return response.json() if response.ok else {"error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def api_post(endpoint: str, data: dict = None) -> dict:
    try:
        response = requests.post(f"{BACKEND_URL}/api{endpoint}", json=data, timeout=30)
        return response.json() if response.ok else {"error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def get_status_badge(status: str) -> str:
    configs = {
        "healthy": ("✓", "status-healthy", "ACTIVO"),
        "running": ("✓", "status-healthy", "ACTIVO"),
        "unhealthy": ("✗", "status-unhealthy", "INACTIVO"),
        "degraded": ("⚠", "status-unknown", "DEGRADADO"),
        "unknown": ("?", "status-unknown", "DESCONOCIDO"),
    }
    icon, css, label = configs.get(status.lower(), ("?", "status-unknown", status.upper()))
    return f'<span class="status-badge {css}">{icon} {label}</span>'


# Header
st.markdown("""
<div style="text-align: center; padding: 2rem 0;">
    <h1 style="font-size: 2.5rem; font-weight: 800; background: linear-gradient(135deg, #6366f1, #a855f7); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
        🖥️ Nodos DistriSearch
    </h1>
    <p style="color: #94a3b8; font-size: 1rem;">Visualización de la arquitectura Master-Slave del sistema distribuido</p>
</div>
""", unsafe_allow_html=True)

# Tabs para organizar contenido
tab_nodes, tab_arch, tab_docker = st.tabs(["📊 Nodos del Cluster", "🏗️ Arquitectura", "🐳 Contenedores Docker"])

with tab_nodes:
    st.markdown("### 🔍 Estado de los Nodos")
    
    # Obtener estado del cluster
    cluster_data = api_get("/cluster/status")
    
    if "error" in cluster_data:
        st.error(f"❌ No se pudo conectar al cluster DistriSearch: {cluster_data['error']}")
        st.info("💡 Asegúrate de que el cluster esté corriendo y accesible.")
        nodes = []
    else:
        nodes = cluster_data.get("nodes", [])
    
    if not nodes:
        st.info("📦 No hay nodos registrados en el cluster")
    else:
        # Resumen
        col1, col2, col3, col4 = st.columns(4)
        
        total = len(nodes)
        healthy = sum(1 for n in nodes if n.get("status") == "healthy")
        masters = sum(1 for n in nodes if n.get("role") == "master")
        slaves = sum(1 for n in nodes if n.get("role") == "slave")
        
        with col1:
            st.metric("📊 Total Nodos", total)
        with col2:
            st.metric("🟢 Saludables", healthy)
        with col3:
            st.metric("👑 Master(s)", masters)
        with col4:
            st.metric("🔹 Slave(s)", slaves)
        
        st.markdown("---")
        
        # Lista de nodos
        for node in nodes:
            node_id = node.get("node_id", "unknown")
            role = node.get("role", "slave")
            status = node.get("status", "unknown")
            is_master = role == "master"
            
            card_class = "node-card-master" if is_master else "node-card-slave"
            role_icon = "👑" if is_master else "🔹"
            role_label = "Master" if is_master else "Slave"
            
            with st.expander(f"{role_icon} {node_id} ({role_label})", expanded=(is_master)):
                st.markdown(f"""
                <div class="node-card {card_class}">
                    <div class="node-header">
                        <span class="node-name">{role_icon} {node_id}</span>
                        {get_status_badge(status)}
                    </div>
                    
                    <div class="node-stats">
                        <div class="stat-item">
                            <span>🌐</span>
                            <span>{node.get('address', 'N/A')}:{node.get('port', 'N/A')}</span>
                        </div>
                        <div class="stat-item">
                            <span>📄</span>
                            <span>{node.get('document_count', 0)} documentos</span>
                        </div>
                        <div class="stat-item">
                            <span>📦</span>
                            <span>{node.get('partition_count', 0)} particiones</span>
                        </div>
                    </div>
                    
                    <div class="node-components">
                        <div class="component-badge component-badge-active">
                            🔧 Backend<br/><small>FastAPI</small>
                        </div>
                        <div class="component-badge component-badge-active">
                            🎨 Frontend<br/><small>React+Nginx</small>
                        </div>
                        <div class="component-badge component-badge-active">
                            🗄️ MongoDB<br/><small>Base Datos</small>
                        </div>
                        <div class="component-badge component-badge-active">
                            💓 Heartbeat<br/><small>UDP</small>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Métricas del nodo
                if node.get('cpu_usage') or node.get('memory_usage'):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        cpu = node.get('cpu_usage', 0)
                        st.metric("CPU", f"{cpu:.1f}%")
                    with c2:
                        mem = node.get('memory_usage', 0)
                        st.metric("Memoria", f"{mem:.1f}%")
                    with c3:
                        disk = node.get('disk_usage', 0)
                        st.metric("Disco", f"{disk:.1f}%")
                
                # Información adicional para el Master
                if is_master:
                    st.markdown("""
                    <div class="concept-box">
                        <div class="concept-title">👑 Responsabilidades del Master</div>
                        <p class="concept-text">
                            • Mantiene el índice semántico global (TF-IDF + MinHash)<br/>
                            • Enruta consultas a los Slaves apropiados<br/>
                            • Coordina la replicación de datos<br/>
                            • Monitorea la salud del cluster via heartbeats
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown("""
                    <div class="concept-box">
                        <div class="concept-title">🔹 Responsabilidades del Slave</div>
                        <p class="concept-text">
                            • Almacena documentos en MongoDB local<br/>
                            • Procesa búsquedas locales<br/>
                            • Participa en elecciones de líder (algoritmo Bully)<br/>
                            • Replica datos a otros nodos
                        </p>
                    </div>
                    """, unsafe_allow_html=True)


with tab_arch:
    st.markdown("### 🏗️ Arquitectura de un Nodo DistriSearch")
    
    st.markdown("""
    <div class="concept-box">
        <div class="concept-title">📌 ¿Qué es un Nodo en DistriSearch?</div>
        <p class="concept-text">
            Un <strong>nodo</strong> en DistriSearch es una unidad autónoma que integra todos los componentes 
            necesarios para operar de forma independiente. Cada nodo (Master o Slave) contiene:
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <div class="glass-card">
            <h4 style="color: #f1f5f9; margin-bottom: 1rem;">🔧 Componentes de un Nodo</h4>
            
            <div class="component-badge component-badge-active" style="margin: 0.5rem 0; display: block; text-align: left; padding: 1rem;">
                <strong>🔧 Backend (FastAPI)</strong><br/>
                API REST para procesamiento de consultas, gestión de documentos y comunicación con el cluster.
            </div>
            
            <div class="component-badge component-badge-active" style="margin: 0.5rem 0; display: block; text-align: left; padding: 1rem;">
                <strong>🎨 Frontend (React + Nginx)</strong><br/>
                Aplicación web para interacción con usuarios. Cada nodo puede atender usuarios directamente.
            </div>
            
            <div class="component-badge component-badge-active" style="margin: 0.5rem 0; display: block; text-align: left; padding: 1rem;">
                <strong>🗄️ MongoDB Local</strong><br/>
                Base de datos para almacenamiento de documentos indexados.
            </div>
            
            <div class="component-badge component-badge-active" style="margin: 0.5rem 0; display: block; text-align: left; padding: 1rem;">
                <strong>💓 Servicios de Cluster</strong><br/>
                Heartbeat (UDP), elección de líder, replicación y sincronización.
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="glass-card">
            <h4 style="color: #f1f5f9; margin-bottom: 1rem;">👑 Master vs 🔹 Slave</h4>
            
            <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 8px; padding: 1rem; margin: 0.5rem 0;">
                <strong style="color: #34d399;">👑 Master (Coordinador)</strong><br/>
                <span style="color: #94a3b8; font-size: 0.9rem;">
                    Además de los componentes base, el Master mantiene:
                    <ul style="margin: 0.5rem 0;">
                        <li>Índice semántico global</li>
                        <li>Balanceador de carga</li>
                        <li>Coordinador de replicación</li>
                        <li>Enrutador de consultas</li>
                    </ul>
                </span>
            </div>
            
            <div style="background: rgba(99, 102, 241, 0.1); border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 8px; padding: 1rem; margin: 0.5rem 0;">
                <strong style="color: #818cf8;">🔹 Slave (Trabajador)</strong><br/>
                <span style="color: #94a3b8; font-size: 0.9rem;">
                    Nodo autónomo que:
                    <ul style="margin: 0.5rem 0;">
                        <li>Almacena documentos localmente</li>
                        <li>Procesa búsquedas asignadas</li>
                        <li>Puede convertirse en Master si el líder falla</li>
                    </ul>
                </span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Diagrama ASCII de la arquitectura
    st.markdown("### 📐 Diagrama de Arquitectura")
    st.markdown("""
    <div class="arch-diagram">
    <pre style="color: #94a3b8; font-size: 0.85rem;">
                    ┌─────────────────────────────────────┐
                    │           👑 MASTER NODE            │
                    │  ┌─────────┐  ┌─────────┐          │
                    │  │ Backend │  │Frontend │          │
                    │  │ FastAPI │  │  React  │          │
                    │  └────┬────┘  └─────────┘          │
                    │       │                             │
                    │  ┌────┴────┐  ┌─────────────────┐  │
                    │  │ MongoDB │  │ Índice Semántico│  │
                    │  └─────────┘  │  (TF-IDF+MinHash)│  │
                    │               └─────────────────┘  │
                    └───────────────┬─────────────────────┘
                                    │ Heartbeat + Replicación
            ┌───────────────────────┼───────────────────────┐
            │                       │                       │
    ┌───────┴───────┐       ┌───────┴───────┐       ┌───────┴───────┐
    │ 🔹 SLAVE 1    │       │ 🔹 SLAVE 2    │       │ 🔹 SLAVE 3    │
    │ ┌──────────┐  │       │ ┌──────────┐  │       │ ┌──────────┐  │
    │ │ Backend  │  │       │ │ Backend  │  │       │ │ Backend  │  │
    │ │ Frontend │  │◄─────►│ │ Frontend │  │◄─────►│ │ Frontend │  │
    │ │ MongoDB  │  │       │ │ MongoDB  │  │       │ │ MongoDB  │  │
    │ └──────────┘  │       │ └──────────┘  │       │ └──────────┘  │
    └───────────────┘       └───────────────┘       └───────────────┘
           ↑                       ↑                       ↑
           │                       │                       │
           └───────────────────────┴───────────────────────┘
                         Heartbeat entre Slaves
    </pre>
    </div>
    """, unsafe_allow_html=True)


with tab_docker:
    st.markdown("### 🐳 Contenedores Docker")
    st.markdown("""
    <div class="concept-box">
        <div class="concept-title">⚠️ Vista de Bajo Nivel</div>
        <p class="concept-text">
            Esta sección muestra los <strong>contenedores Docker</strong> individuales que componen el sistema.
            Es útil para operaciones de mantenimiento y simulación de fallos, pero recuerda que un 
            <strong>nodo lógico</strong> puede estar compuesto por múltiples contenedores.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Obtener contenedores
    containers_data = api_get("/nodes/containers")
    
    if "error" in containers_data:
        st.error(f"Error: {containers_data['error']}")
    elif not containers_data.get("docker_available", False):
        st.warning("⚠️ Docker no está disponible")
    else:
        containers = containers_data.get("containers", [])
        
        if not containers:
            st.info("📦 No se encontraron contenedores de DistriSearch")
        else:
            # Resumen
            col1, col2, col3 = st.columns(3)
            
            running = sum(1 for c in containers if c.get("status") == "running")
            stopped = sum(1 for c in containers if c.get("status") == "exited")
            paused = sum(1 for c in containers if c.get("status") == "paused")
            
            with col1:
                st.metric("🟢 Activos", running)
            with col2:
                st.metric("🔴 Detenidos", stopped)
            with col3:
                st.metric("🟡 Pausados", paused)
            
            st.markdown("---")
            
            # Lista de contenedores
            for container in containers:
                name = container["name"]
                status = container.get("status", "unknown")
                is_master = "master" in name.lower()
                
                status_configs = {
                    "running": ("✓", "status-healthy", "ACTIVO"),
                    "exited": ("✗", "status-unhealthy", "DETENIDO"),
                    "paused": ("⏸", "status-unknown", "PAUSADO"),
                }
                icon, css, label = status_configs.get(status.lower(), ("?", "status-unknown", status.upper()))
                
                with st.expander(f"{'👑' if is_master else '📦'} {name}", expanded=(status == "running")):
                    col_info, col_actions = st.columns([2, 1])
                    
                    with col_info:
                        st.markdown(f"""
                        <div style="color: #94a3b8; font-size: 0.9rem;">
                            <p><strong>ID:</strong> <code>{container['id']}</code></p>
                            <p><strong>Imagen:</strong> {container['image']}</p>
                            <p><strong>Puertos:</strong> {', '.join(container.get('ports', [])) or 'N/A'}</p>
                            <p><strong>Estado:</strong> <span class="status-badge {css}">{icon} {label}</span></p>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col_actions:
                        st.markdown("**Acciones:**")
                        
                        if status == "running":
                            if st.button("⏹️ Detener", key=f"stop_{name}", use_container_width=True):
                                with st.spinner("Deteniendo..."):
                                    result = api_post(f"/nodes/stop/{name}")
                                if "error" not in result:
                                    st.success("✅ Detenido")
                                    st.rerun()
                                else:
                                    st.error(result["error"])
                            
                            if st.button("🔄 Reiniciar", key=f"restart_{name}", use_container_width=True):
                                with st.spinner("Reiniciando..."):
                                    result = api_post(f"/nodes/restart/{name}")
                                if "error" not in result:
                                    st.success("✅ Reiniciado")
                                    st.rerun()
                                else:
                                    st.error(result["error"])
                            
                            if st.button("💀 Kill", key=f"kill_{name}", use_container_width=True, type="secondary"):
                                with st.spinner("Terminando..."):
                                    result = api_post(f"/nodes/kill/{name}")
                                if "error" not in result:
                                    st.warning("⚠️ Proceso terminado")
                                    st.rerun()
                                else:
                                    st.error(result["error"])
                        else:
                            if st.button("▶️ Iniciar", key=f"start_{name}", use_container_width=True):
                                with st.spinner("Iniciando..."):
                                    result = api_post(f"/nodes/start/{name}")
                                if "error" not in result:
                                    st.success("✅ Iniciado")
                                    st.rerun()
                                else:
                                    st.error(result["error"])

# Footer con conceptos
st.markdown("---")
st.markdown("### 📚 Conceptos Clave")

c1, c2 = st.columns(2)

with c1:
    st.markdown("""
    <div class="concept-box">
        <div class="concept-title">🏛️ Arquitectura Master-Slave</div>
        <p class="concept-text">
            DistriSearch utiliza una arquitectura <strong>Master-Slave</strong> donde el Master coordina 
            y los Slaves almacenan/procesan. A diferencia de P2P puro, esto simplifica la coordinación 
            mientras mantiene escalabilidad horizontal.
        </p>
    </div>
    """, unsafe_allow_html=True)

with c2:
    st.markdown("""
    <div class="concept-box">
        <div class="concept-title">🗳️ Algoritmo Bully</div>
        <p class="concept-text">
            Cuando el Master falla, los Slaves ejecutan el <strong>algoritmo Bully</strong> para 
            elegir un nuevo líder. El nodo con mayor ID gana la elección, garantizando 
            continuidad del servicio sin intervención manual.
        </p>
    </div>
    """, unsafe_allow_html=True)
