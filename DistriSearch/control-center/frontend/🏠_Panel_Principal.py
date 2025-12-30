"""
🎛️ DistriSearch Control Center
Página principal - Panel de Control
"""

import streamlit as st
import requests
import time
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
    /* Variables CSS */
    :root {
        --primary: #6366f1;
        --primary-light: #818cf8;
        --success: #10b981;
        --warning: #f59e0b;
        --danger: #ef4444;
        --bg-dark: #0f172a;
        --bg-card: #1e293b;
        --text-primary: #f1f5f9;
        --text-secondary: #94a3b8;
        --border: #334155;
    }
    
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
    
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        color: #e2e8f0;
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
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    
    .metric-container:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(99, 102, 241, 0.2);
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
    
    /* Status badges modernos */
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem 1rem;
        border-radius: 9999px;
        font-size: 0.875rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .status-healthy {
        background: rgba(16, 185, 129, 0.15);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.4);
        box-shadow: 0 0 20px rgba(16, 185, 129, 0.2);
    }
    
    .status-degraded {
        background: rgba(245, 158, 11, 0.15);
        color: #fbbf24;
        border: 1px solid rgba(245, 158, 11, 0.4);
        box-shadow: 0 0 20px rgba(245, 158, 11, 0.2);
    }
    
    .status-unhealthy {
        background: rgba(239, 68, 68, 0.15);
        color: #f87171;
        border: 1px solid rgba(239, 68, 68, 0.4);
        box-shadow: 0 0 20px rgba(239, 68, 68, 0.2);
    }
    
    /* Node cards */
    .node-card {
        background: rgba(30, 41, 59, 0.6);
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.75rem;
        border-left: 4px solid #6366f1;
        transition: all 0.3s ease;
    }
    
    .node-card:hover {
        background: rgba(30, 41, 59, 0.8);
        transform: translateX(4px);
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
        font-size: 1rem;
    }
    
    .node-stats {
        display: flex;
        gap: 1.5rem;
        color: #94a3b8;
        font-size: 0.85rem;
    }
    
    /* Pulse animation para status */
    @keyframes pulse-glow {
        0%, 100% { box-shadow: 0 0 5px currentColor; }
        50% { box-shadow: 0 0 20px currentColor, 0 0 30px currentColor; }
    }
    
    .pulse-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
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
        font-size: 0.95rem;
        margin-bottom: 0.5rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    .concept-text {
        color: #cbd5e1;
        font-size: 0.9rem;
        line-height: 1.6;
    }
    
    /* Botones modernos */
    .stButton > button {
        background: linear-gradient(135deg, #6366f1, #8b5cf6);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 0.6rem 1.5rem;
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3);
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 25px rgba(99, 102, 241, 0.4);
    }
    
    /* Header grande */
    .main-header {
        text-align: center;
        padding: 2rem 0;
        margin-bottom: 2rem;
    }
    
    .main-title {
        font-size: 3rem;
        font-weight: 800;
        background: linear-gradient(135deg, #6366f1, #a855f7, #ec4899);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    
    .main-subtitle {
        color: #94a3b8;
        font-size: 1.1rem;
    }
    
    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background: rgba(30, 41, 59, 0.5);
        border-radius: 12px;
        padding: 4px;
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        color: #94a3b8;
        font-weight: 500;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
        color: white !important;
    }
    
    /* Progress bars */
    .stProgress > div > div > div {
        background: linear-gradient(90deg, #6366f1, #a855f7);
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        background: rgba(30, 41, 59, 0.6);
        border-radius: 10px;
        font-weight: 500;
    }
    
    /* Info/Warning/Error boxes */
    .stAlert {
        border-radius: 12px;
    }
</style>
""", unsafe_allow_html=True)

# ============================================
# Funciones de API
# ============================================

@st.cache_data(ttl=2)
def api_get(endpoint: str) -> dict:
    """GET request a la API."""
    try:
        response = requests.get(f"{BACKEND_URL}/api{endpoint}", timeout=10)
        if response.ok:
            return response.json()
        return {"error": f"HTTP {response.status_code}"}
    except requests.exceptions.ConnectionError:
        return {"error": "Sin conexión al backend"}
    except Exception as e:
        return {"error": str(e)}


def api_post(endpoint: str, data: dict = None) -> dict:
    """POST request a la API."""
    try:
        response = requests.post(f"{BACKEND_URL}/api{endpoint}", json=data, timeout=30)
        if response.ok:
            return response.json()
        return {"error": f"HTTP {response.status_code}"}
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
        "paused": ("⏸", "status-degraded", "PAUSADO"),
    }
    icon, css, label = configs.get(status.lower(), ("?", "status-degraded", status.upper()))
    return f'<span class="status-badge {css}">{icon} {label}</span>'


# ============================================
# Sidebar
# ============================================

with st.sidebar:
    st.markdown("""
    <div style="text-align: center; padding: 1rem 0 2rem 0;">
        <div style="font-size: 3.5rem; margin-bottom: 0.5rem;">🎛️</div>
        <h1 style="color: #f1f5f9; font-size: 1.5rem; margin: 0; font-weight: 700;">Control Center</h1>
        <p style="color: #6366f1; font-size: 0.9rem; margin: 0.25rem 0 0 0;">DistriSearch</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Estado de conexión
    try:
        health = api_get("/cluster/health")
        if "error" not in health:
            st.success("🟢 Conectado al cluster")
        else:
            st.warning("🟡 Backend OK, cluster offline")
    except:
        st.error("🔴 Sin conexión")
    
    st.markdown("---")
    
    # Auto-refresh toggle
    auto_refresh = st.toggle("🔄 Auto-actualizar", value=True)
    if auto_refresh:
        st.caption("Actualizando cada 5 segundos...")
        time.sleep(5)
        st.rerun()
    
    st.markdown("---")
    
    st.markdown(f"""
    <div style="text-align: center; color: #64748b; font-size: 0.8rem;">
        <p style="margin: 0;">v1.0.0</p>
        <p style="margin: 0.25rem 0 0 0;">{datetime.now().strftime('%H:%M:%S')}</p>
    </div>
    """, unsafe_allow_html=True)

# ============================================
# Contenido Principal
# ============================================

# Header
st.markdown("""
<div class="main-header">
    <h1 class="main-title">🎛️ Panel de Control</h1>
    <p class="main-subtitle">Monitoreo en tiempo real del sistema distribuido DistriSearch</p>
</div>
""", unsafe_allow_html=True)

# Obtener datos
cluster = api_get("/cluster/status")

if "error" in cluster:
    st.error(f"⚠️ Error: {cluster['error']}")
    st.info("💡 Asegúrate de que el backend del Control Center esté corriendo en el puerto 8888")
    st.stop()

# Métricas principales
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
    status = cluster.get("status", "unknown")
    st.markdown(f"""
    <div class="metric-container">
        <div style="margin-bottom: 0.5rem;">
            <span class="pulse-dot pulse-dot-{status}" style="display: inline-block;"></span>
        </div>
        {render_status_badge(status)}
        <p class="metric-label" style="margin-top: 0.75rem;">Estado</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Dos columnas: Nodos y Líder
col_left, col_right = st.columns([2, 1])

with col_left:
    st.markdown("""
    <div class="glass-card">
        <div class="glass-card-header">
            <span style="font-size: 1.5rem;">🖥️</span>
            <h3 class="glass-card-title">Nodos del Cluster</h3>
        </div>
    """, unsafe_allow_html=True)
    
    nodes = cluster.get("nodes", [])
    if nodes:
        for node in nodes:
            role = node.get("role", "slave")
            status = node.get("status", "unknown")
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

with col_right:
    # Info del Líder
    leader = api_get("/cluster/leader")
    leader_data = leader.get("leader", {}) if "error" not in leader else {}
    
    st.markdown(f"""
    <div class="glass-card" style="text-align: center;">
        <div class="glass-card-header" style="justify-content: center;">
            <span style="font-size: 1.5rem;">👑</span>
            <h3 class="glass-card-title">Líder Actual</h3>
        </div>
        <div style="font-size: 4rem; margin: 1rem 0;">👑</div>
        <p style="color: #10b981; font-size: 1.2rem; font-weight: 600; margin: 0;">
            {leader_data.get('leader_id', 'Sin líder')}
        </p>
        <p style="color: #64748b; font-size: 0.9rem; margin: 0.5rem 0;">
            {leader_data.get('leader_address', '')}
        </p>
        <p style="color: #94a3b8; font-size: 0.8rem; margin-top: 1rem;">
            Término: {leader_data.get('term', 0)}
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Concept box
    st.markdown("""
    <div class="concept-box">
        <div class="concept-title">💡 Elección de Líder</div>
        <p class="concept-text">
            El líder coordina las operaciones de escritura y replica los datos 
            a los seguidores usando el algoritmo Raft.
        </p>
    </div>
    """, unsafe_allow_html=True)

# Gráfico de distribución
st.markdown("<br>", unsafe_allow_html=True)
st.markdown("### 📈 Distribución de Datos")

if nodes:
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=[n.get('node_id', 'N/A') for n in nodes],
        y=[n.get('document_count', 0) for n in nodes],
        name='Documentos',
        marker_color='#6366f1',
        marker_line_color='#818cf8',
        marker_line_width=2,
    ))
    
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#f1f5f9'),
        height=300,
        margin=dict(t=20, b=40, l=40, r=20),
        xaxis=dict(gridcolor='rgba(99,102,241,0.1)'),
        yaxis=dict(gridcolor='rgba(99,102,241,0.1)'),
        showlegend=False,
    )
    
    st.plotly_chart(fig, use_container_width=True)

# Conceptos
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
