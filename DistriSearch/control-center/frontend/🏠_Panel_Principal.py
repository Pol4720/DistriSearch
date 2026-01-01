"""
🎛️ DistriSearch Control Center
Página principal - Panel de Control
Usando st.fragment para actualizaciones parciales
"""

import streamlit as st
import requests
from datetime import datetime
import plotly.graph_objects as go

# Configuración de la página
st.set_page_config(
    page_title="Control Center - DistriSearch",
    page_icon="🎛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# URL del backend
BACKEND_URL = st.secrets.get("BACKEND_URL", "http://localhost:8888")

# ============================================
# CSS Moderno
# ============================================
st.markdown("""
<style>
    /* Ocultar elementos Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Fondo principal */
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%);
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1e1b4b 0%, #0f172a 100%);
        border-right: 1px solid rgba(99, 102, 241, 0.2);
    }
    
    /* Cards con glassmorphism */
    .glass-card {
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(12px);
        border-radius: 16px;
        padding: 1.5rem;
        border: 1px solid rgba(99, 102, 241, 0.2);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        margin-bottom: 1rem;
    }
    
    .glass-card-header {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin-bottom: 1rem;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid rgba(99, 102, 241, 0.2);
    }
    
    .glass-card-title {
        color: #f1f5f9;
        font-size: 1.1rem;
        font-weight: 600;
        margin: 0;
    }
    
    /* Métricas estilizadas */
    .metric-container {
        background: linear-gradient(145deg, rgba(99, 102, 241, 0.1), rgba(30, 41, 59, 0.8));
        border-radius: 12px;
        padding: 1.25rem;
        border: 1px solid rgba(99, 102, 241, 0.3);
        text-align: center;
        transition: transform 0.3s ease;
    }
    
    .metric-container:hover {
        transform: translateY(-2px);
    }
    
    .metric-value {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #6366f1, #a855f7);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
    }
    
    .metric-label {
        color: #94a3b8;
        font-size: 0.9rem;
        margin-top: 0.5rem;
    }
    
    .metric-delta {
        color: #10b981;
        font-size: 0.8rem;
        margin-top: 0.25rem;
    }
    
    /* Status badges */
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem 1rem;
        border-radius: 9999px;
        font-size: 0.875rem;
        font-weight: 600;
    }
    
    .status-healthy {
        background: rgba(16, 185, 129, 0.15);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.4);
    }
    
    .status-degraded {
        background: rgba(245, 158, 11, 0.15);
        color: #fbbf24;
        border: 1px solid rgba(245, 158, 11, 0.4);
    }
    
    .status-unhealthy {
        background: rgba(239, 68, 68, 0.15);
        color: #f87171;
        border: 1px solid rgba(239, 68, 68, 0.4);
    }
    
    /* Node cards */
    .node-card {
        background: rgba(30, 41, 59, 0.6);
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.75rem;
        border-left: 4px solid #6366f1;
    }
    
    .node-card-master {
        border-left-color: #10b981;
        background: linear-gradient(90deg, rgba(16, 185, 129, 0.1), rgba(30, 41, 59, 0.6));
    }
    
    .node-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0.5rem;
    }
    
    .node-name {
        color: #f1f5f9;
        font-weight: 600;
    }
    
    .node-stats {
        display: flex;
        gap: 1.5rem;
        color: #94a3b8;
        font-size: 0.85rem;
    }
    
    /* Pulse animation */
    @keyframes pulse-glow {
        0%, 100% { box-shadow: 0 0 5px currentColor; }
        50% { box-shadow: 0 0 20px currentColor; }
    }
    
    .pulse-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        display: inline-block;
        animation: pulse-glow 2s infinite;
    }
    
    .pulse-dot-healthy { background: #10b981; color: #10b981; }
    .pulse-dot-degraded { background: #f59e0b; color: #f59e0b; }
    .pulse-dot-unhealthy { background: #ef4444; color: #ef4444; }
    
    /* Concept boxes */
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
    
    /* Header */
    .main-header {
        text-align: center;
        padding: 2rem 0;
    }
    
    .main-title {
        font-size: 3rem;
        font-weight: 800;
        background: linear-gradient(135deg, #6366f1, #a855f7, #ec4899);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .main-subtitle {
        color: #94a3b8;
        font-size: 1.1rem;
    }
</style>
""", unsafe_allow_html=True)

# ============================================
# Funciones de API (sin cache para fragments)
# ============================================

def api_get(endpoint: str) -> dict:
    """GET request a la API."""
    try:
        response = requests.get(f"{BACKEND_URL}/api{endpoint}", timeout=5)
        if response.ok:
            return response.json()
        return {"error": f"HTTP {response.status_code}"}
    except requests.exceptions.ConnectionError:
        return {"error": "Sin conexión al backend"}
    except Exception as e:
        return {"error": str(e)}


def render_status_badge(status: str) -> str:
    """Genera HTML para badge de estado."""
    configs = {
        "healthy": ("✓", "status-healthy", "OPERATIVO"),
        "degraded": ("⚠", "status-degraded", "DEGRADADO"),
        "unhealthy": ("✗", "status-unhealthy", "CRÍTICO"),
        "running": ("✓", "status-healthy", "ACTIVO"),
        "exited": ("✗", "status-unhealthy", "DETENIDO"),
    }
    icon, css, label = configs.get(status.lower(), ("?", "status-degraded", status.upper()))
    return f'<span class="status-badge {css}">{icon} {label}</span>'


# ============================================
# Sidebar (estático)
# ============================================

with st.sidebar:
    st.markdown("""
    <div style="text-align: center; padding: 1rem 0 2rem 0;">
        <div style="font-size: 3.5rem; margin-bottom: 0.5rem;">🎛️</div>
        <h1 style="color: #f1f5f9; font-size: 1.5rem; margin: 0;">Control Center</h1>
        <p style="color: #6366f1; font-size: 0.9rem; margin: 0.25rem 0 0 0;">DistriSearch</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #64748b; font-size: 0.8rem;">
        <p style="margin: 0;">v1.0.0</p>
    </div>
    """, unsafe_allow_html=True)


# ============================================
# Header (estático)
# ============================================

st.markdown("""
<div class="main-header">
    <h1 class="main-title">🎛️ Panel de Control</h1>
    <p class="main-subtitle">Monitoreo en tiempo real del sistema distribuido DistriSearch</p>
</div>
""", unsafe_allow_html=True)


# ============================================
# FRAGMENTOS con actualización automática
# ============================================

@st.fragment(run_every=5)
def cluster_metrics():
    """Fragmento que muestra métricas del cluster - se actualiza cada 5s."""
    cluster = api_get("/cluster/status")
    
    if "error" in cluster:
        # Datos demo para mostrar la UI
        cluster = {
            "status": "healthy",
            "total_nodes": 3,
            "healthy_nodes": 3,
            "total_documents": 150,
            "total_partitions": 6,
            "replication_factor": 2,
        }
    
    st.markdown("### 📊 Métricas del Cluster")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="metric-container">
            <p class="metric-value">{cluster.get('total_nodes', 0)}</p>
            <p class="metric-label">Nodos Totales</p>
            <p class="metric-delta">↑ {cluster.get('healthy_nodes', 0)} activos</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="metric-container">
            <p class="metric-value">{cluster.get('total_documents', 0)}</p>
            <p class="metric-label">Documentos</p>
            <p class="metric-delta">Indexados</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="metric-container">
            <p class="metric-value">{cluster.get('total_partitions', 0)}</p>
            <p class="metric-label">Particiones</p>
            <p class="metric-delta">{cluster.get('replication_factor', 2)}x replicación</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        status = cluster.get("status", "healthy")
        st.markdown(f"""
        <div class="metric-container">
            <span class="pulse-dot pulse-dot-{status}"></span>
            <br><br>
            {render_status_badge(status)}
            <p class="metric-label">Estado</p>
        </div>
        """, unsafe_allow_html=True)


@st.fragment(run_every=5)
def nodes_panel():
    """Fragmento que muestra los nodos - se actualiza cada 5s."""
    cluster = api_get("/cluster/status")
    
    if "error" in cluster:
        nodes = [
            {"node_id": "node-1", "role": "master", "status": "running", "address": "localhost", "port": 8001, "document_count": 50, "partition_count": 2},
            {"node_id": "node-2", "role": "slave", "status": "running", "address": "localhost", "port": 8002, "document_count": 50, "partition_count": 2},
            {"node_id": "node-3", "role": "slave", "status": "running", "address": "localhost", "port": 8003, "document_count": 50, "partition_count": 2},
        ]
    else:
        nodes = cluster.get("nodes", [])
    
    st.markdown("""
    <div class="glass-card">
        <div class="glass-card-header">
            <span style="font-size: 1.5rem;">🖥️</span>
            <h3 class="glass-card-title">Nodos del Cluster</h3>
        </div>
    """, unsafe_allow_html=True)
    
    if nodes:
        for node in nodes:
            role = node.get("role", "slave")
            status = node.get("status", "running")
            is_master = role == "master"
            
            st.markdown(f"""
            <div class="node-card {'node-card-master' if is_master else ''}">
                <div class="node-header">
                    <span class="node-name">{'👑 ' if is_master else '🔹 '}{node.get('node_id', 'N/A')}</span>
                    {render_status_badge(status)}
                </div>
                <div class="node-stats">
                    <span>📍 {node.get('address', '')}:{node.get('port', '')}</span>
                    <span>📄 {node.get('document_count', 0)} docs</span>
                    <span>📦 {node.get('partition_count', 0)} particiones</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No hay nodos registrados")
    
    st.markdown("</div>", unsafe_allow_html=True)


@st.fragment(run_every=5)
def leader_panel():
    """Fragmento que muestra info del líder - se actualiza cada 5s."""
    leader = api_get("/cluster/leader")
    
    if "error" in leader:
        leader_data = {"leader_id": "node-1", "leader_address": "localhost:8001", "term": 5}
    else:
        leader_data = leader.get("leader", {})
    
    st.markdown(f"""
    <div class="glass-card" style="text-align: center;">
        <div class="glass-card-header" style="justify-content: center;">
            <span style="font-size: 1.5rem;">👑</span>
            <h3 class="glass-card-title">Líder Actual</h3>
        </div>
        <div style="font-size: 4rem; margin: 1rem 0;">👑</div>
        <p style="color: #10b981; font-size: 1.2rem; font-weight: 600; margin: 0;">
            {leader_data.get('leader_id', 'node-1')}
        </p>
        <p style="color: #64748b; font-size: 0.9rem; margin: 0.5rem 0;">
            {leader_data.get('leader_address', '')}
        </p>
        <p style="color: #94a3b8; font-size: 0.8rem; margin-top: 1rem;">
            Término: {leader_data.get('term', 0)}
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="concept-box">
        <div class="concept-title">💡 Elección de Líder</div>
        <p class="concept-text">
            El líder coordina las operaciones de escritura y replica los datos 
            a los seguidores usando el algoritmo Raft.
        </p>
    </div>
    """, unsafe_allow_html=True)


@st.fragment(run_every=10)
def status_indicator():
    """Indicador de conexión que se actualiza cada 10s."""
    try:
        cluster = api_get("/cluster/status")
        if "error" not in cluster:
            st.success(f"🟢 Conectado - {datetime.now().strftime('%H:%M:%S')}")
        else:
            st.warning(f"🟡 Demo Mode - {datetime.now().strftime('%H:%M:%S')}")
    except:
        st.error(f"🔴 Desconectado - {datetime.now().strftime('%H:%M:%S')}")


# ============================================
# Layout Principal
# ============================================

# Indicador de estado en sidebar
with st.sidebar:
    st.markdown("### 📡 Estado")
    status_indicator()

# Métricas principales
cluster_metrics()

st.markdown("<br>", unsafe_allow_html=True)

# Dos columnas: Nodos y Líder
col_left, col_right = st.columns([2, 1])

with col_left:
    nodes_panel()

with col_right:
    leader_panel()

# Conceptos (estático, no necesita actualización)
st.markdown("<br>", unsafe_allow_html=True)
st.markdown("### 📚 Conceptos Clave")

c1, c2, c3 = st.columns(3)

with c1:
    st.markdown("""
    <div class="concept-box">
        <div class="concept-title">🟢 Cluster Saludable</div>
        <p class="concept-text">
            Todos los nodos responden a heartbeats y los datos están sincronizados entre réplicas.
        </p>
    </div>
    """, unsafe_allow_html=True)

with c2:
    st.markdown("""
    <div class="concept-box">
        <div class="concept-title">🟡 Cluster Degradado</div>
        <p class="concept-text">
            Algunos nodos no disponibles, pero el sistema mantiene quórum para operar.
        </p>
    </div>
    """, unsafe_allow_html=True)

with c3:
    st.markdown("""
    <div class="concept-box">
        <div class="concept-title">🔴 Cluster Crítico</div>
        <p class="concept-text">
            No se puede garantizar consistencia de datos. Se requiere intervención.
        </p>
    </div>
    """, unsafe_allow_html=True)
