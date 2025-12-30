"""
📊 Métricas del Sistema
Visualización de métricas y estadísticas del cluster
"""

import streamlit as st
import requests
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

st.set_page_config(
    page_title="Métricas - Control Center",
    page_icon="📊",
    layout="wide",
)

# CSS
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
    
    .metric-card {
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(12px);
        border-radius: 16px;
        padding: 1.5rem;
        border: 1px solid rgba(99, 102, 241, 0.2);
        text-align: center;
        transition: all 0.3s ease;
    }
    
    .metric-card:hover {
        border-color: rgba(99, 102, 241, 0.5);
        transform: translateY(-3px);
        box-shadow: 0 8px 30px rgba(99, 102, 241, 0.2);
    }
    
    .metric-icon {
        font-size: 2.5rem;
        margin-bottom: 0.5rem;
    }
    
    .metric-value {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #6366f1, #a855f7);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .metric-label {
        color: #94a3b8;
        font-size: 0.9rem;
        margin-top: 0.5rem;
    }
    
    .metric-sublabel {
        color: #64748b;
        font-size: 0.8rem;
    }
    
    .status-card {
        background: rgba(30, 41, 59, 0.7);
        border-radius: 16px;
        padding: 1.5rem;
        border: 1px solid rgba(99, 102, 241, 0.2);
        margin-bottom: 1rem;
    }
    
    .status-header {
        display: flex;
        align-items: center;
        gap: 1rem;
        margin-bottom: 1rem;
    }
    
    .status-icon {
        font-size: 3rem;
    }
    
    .status-text {
        color: #f1f5f9;
        font-size: 1.5rem;
        font-weight: 600;
    }
    
    .status-description {
        color: #94a3b8;
        font-size: 0.95rem;
        line-height: 1.6;
    }
    
    .status-healthy { border-left: 4px solid #10b981; }
    .status-degraded { border-left: 4px solid #f59e0b; }
    .status-unhealthy { border-left: 4px solid #ef4444; }
    
    .resource-bar {
        background: rgba(15, 23, 42, 0.6);
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 0.75rem;
    }
    
    .resource-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0.5rem;
    }
    
    .resource-label {
        color: #f1f5f9;
        font-weight: 500;
    }
    
    .resource-value {
        color: #a5b4fc;
        font-weight: 600;
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
</style>
""", unsafe_allow_html=True)

BACKEND_URL = st.secrets.get("BACKEND_URL", "http://localhost:8888")


@st.cache_data(ttl=3)
def api_get(endpoint: str) -> dict:
    try:
        response = requests.get(f"{BACKEND_URL}/api{endpoint}", timeout=10)
        return response.json() if response.ok else {"error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}


# Header
st.markdown("""
<div style="text-align: center; padding: 2rem 0;">
    <h1 style="font-size: 2.5rem; font-weight: 800; background: linear-gradient(135deg, #6366f1, #a855f7); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
        📊 Métricas del Sistema
    </h1>
    <p style="color: #94a3b8; font-size: 1rem;">Visualización en tiempo real del estado del cluster</p>
</div>
""", unsafe_allow_html=True)

# Auto-refresh
col1, col2 = st.columns([4, 1])
with col2:
    auto_refresh = st.toggle("🔄 Auto", value=False)

if auto_refresh:
    import time
    time.sleep(5)
    st.rerun()

# Obtener métricas
metrics = api_get("/metrics/summary")

if "error" in metrics:
    st.error(f"Error: {metrics['error']}")
    st.stop()

# Estado general del cluster
cluster_status = metrics.get("cluster_status", {})
status = cluster_status.get("status", "unknown")

status_configs = {
    "healthy": ("✅", "OPERATIVO", "status-healthy", "El cluster está funcionando perfectamente. Todos los nodos responden y los datos están sincronizados."),
    "degraded": ("⚠️", "DEGRADADO", "status-degraded", "Algunos nodos no están disponibles, pero el sistema mantiene el quórum necesario para operar."),
    "unhealthy": ("❌", "CRÍTICO", "status-unhealthy", "El sistema no puede garantizar la consistencia. Se requiere intervención inmediata."),
    "unknown": ("❓", "DESCONOCIDO", "status-degraded", "No se puede determinar el estado del cluster."),
}

icon, label, css_class, description = status_configs.get(status, status_configs["unknown"])

st.markdown(f"""
<div class="status-card {css_class}">
    <div class="status-header">
        <span class="status-icon">{icon}</span>
        <div>
            <div class="status-text">{label}</div>
            <div class="status-description">{description}</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Métricas principales
st.markdown("### 📈 Métricas Principales")

nodes_info = metrics.get("nodes", {})
data_info = metrics.get("data", {})
uptime_info = metrics.get("uptime", {})

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-icon">🖥️</div>
        <div class="metric-value">{nodes_info.get('total', 0)}</div>
        <div class="metric-label">Nodos Totales</div>
        <div class="metric-sublabel">{nodes_info.get('healthy', 0)} saludables</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-icon">📄</div>
        <div class="metric-value">{data_info.get('total_documents', 0)}</div>
        <div class="metric-label">Documentos</div>
        <div class="metric-sublabel">Indexados</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-icon">📦</div>
        <div class="metric-value">{data_info.get('total_partitions', 0)}</div>
        <div class="metric-label">Particiones</div>
        <div class="metric-sublabel">{data_info.get('replication_factor', 2)}x replicación</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-icon">⏱️</div>
        <div class="metric-value" style="font-size: 1.5rem;">{uptime_info.get('formatted', 'N/A')}</div>
        <div class="metric-label">Uptime</div>
        <div class="metric-sublabel">Sistema activo</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Recursos y Gráficos
col_left, col_right = st.columns([1, 1])

with col_left:
    st.markdown("### 💻 Uso de Recursos")
    
    resources = metrics.get("resources", {})
    
    # CPU
    cpu = resources.get("avg_cpu_usage", 0)
    st.markdown(f"""
    <div class="resource-bar">
        <div class="resource-header">
            <span class="resource-label">🔲 CPU Promedio</span>
            <span class="resource-value">{cpu:.1f}%</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.progress(min(cpu/100, 1.0))
    
    # Memoria
    memory = resources.get("avg_memory_usage", 0)
    st.markdown(f"""
    <div class="resource-bar">
        <div class="resource-header">
            <span class="resource-label">🧠 Memoria Promedio</span>
            <span class="resource-value">{memory:.1f}%</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.progress(min(memory/100, 1.0))

with col_right:
    st.markdown("### 🥧 Distribución de Nodos")
    
    healthy = nodes_info.get("healthy", 0)
    unhealthy = nodes_info.get("unhealthy", 0)
    
    if healthy > 0 or unhealthy > 0:
        fig = go.Figure(data=[go.Pie(
            labels=['Saludables', 'No Saludables'],
            values=[healthy, unhealthy],
            hole=0.6,
            marker_colors=['#10b981', '#ef4444'],
            textinfo='value',
            textfont=dict(color='white', size=14),
        )])
        
        fig.update_layout(
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.2,
                xanchor="center",
                x=0.5,
                font=dict(color='#f1f5f9')
            ),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            height=280,
            margin=dict(t=20, b=60, l=20, r=20),
            annotations=[dict(
                text=f'{healthy + unhealthy}',
                x=0.5, y=0.5,
                font_size=24,
                font_color='#f1f5f9',
                showarrow=False
            )]
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay datos de nodos disponibles")

# Conceptos explicados
st.markdown("---")
st.markdown("### 📚 Entendiendo las Métricas")

concepts = metrics.get("concepts", {}).get("es", {})

if concepts:
    cols = st.columns(2)
    for i, (key, value) in enumerate(concepts.items()):
        with cols[i % 2]:
            st.markdown(f"""
            <div class="concept-box">
                <div class="concept-title">📖 {key.replace('_', ' ').title()}</div>
                <p class="concept-text">{value}</p>
            </div>
            """, unsafe_allow_html=True)
else:
    c1, c2 = st.columns(2)
    
    with c1:
        st.markdown("""
        <div class="concept-box">
            <div class="concept-title">📊 Factor de Replicación</div>
            <p class="concept-text">
                Indica en cuántos nodos se almacena cada dato. 
                Un factor de 3 significa que el sistema tolera hasta 2 fallos.
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    with c2:
        st.markdown("""
        <div class="concept-box">
            <div class="concept-title">📦 Particiones</div>
            <p class="concept-text">
                Los datos se dividen en particiones para distribuir la carga.
                Cada partición se replica según el factor de replicación.
            </p>
        </div>
        """, unsafe_allow_html=True)
