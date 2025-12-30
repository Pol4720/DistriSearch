"""
🔄 Replicación y Consistencia
Monitor de replicación de datos y estado de consistencia
"""

import streamlit as st
import requests
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(
    page_title="Replicación - Control Center",
    page_icon="🔄",
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
    
    .replication-card {
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(12px);
        border-radius: 16px;
        padding: 1.5rem;
        border: 1px solid rgba(99, 102, 241, 0.2);
        margin-bottom: 1rem;
        transition: all 0.3s ease;
    }
    
    .replication-card:hover {
        border-color: rgba(99, 102, 241, 0.5);
        box-shadow: 0 8px 30px rgba(99, 102, 241, 0.2);
    }
    
    .partition-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1rem;
    }
    
    .partition-name {
        color: #f1f5f9;
        font-size: 1.2rem;
        font-weight: 600;
    }
    
    .partition-status {
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 500;
    }
    
    .status-synced {
        background: rgba(16, 185, 129, 0.2);
        color: #10b981;
    }
    
    .status-syncing {
        background: rgba(245, 158, 11, 0.2);
        color: #f59e0b;
    }
    
    .status-out-of-sync {
        background: rgba(239, 68, 68, 0.2);
        color: #ef4444;
    }
    
    .replica-list {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin-top: 1rem;
    }
    
    .replica-badge {
        background: rgba(99, 102, 241, 0.2);
        color: #a5b4fc;
        padding: 0.4rem 0.8rem;
        border-radius: 8px;
        font-size: 0.85rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    .replica-leader {
        background: rgba(168, 85, 247, 0.3);
        color: #c4b5fd;
        border: 1px solid rgba(168, 85, 247, 0.5);
    }
    
    .info-panel {
        background: linear-gradient(145deg, rgba(99, 102, 241, 0.15), rgba(30, 41, 59, 0.6));
        border-radius: 16px;
        padding: 1.5rem;
        border: 1px solid rgba(99, 102, 241, 0.3);
        margin-bottom: 1.5rem;
    }
    
    .info-title {
        color: #a855f7;
        font-size: 1.1rem;
        font-weight: 600;
        margin-bottom: 0.8rem;
    }
    
    .info-text {
        color: #cbd5e1;
        font-size: 0.95rem;
        line-height: 1.7;
    }
    
    .log-entry {
        background: rgba(15, 23, 42, 0.6);
        border-radius: 8px;
        padding: 0.8rem 1rem;
        margin-bottom: 0.5rem;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.85rem;
        color: #94a3b8;
        display: flex;
        justify-content: space-between;
    }
    
    .log-index {
        color: #6366f1;
        font-weight: 600;
    }
    
    .log-term {
        color: #a855f7;
    }
    
    .log-command {
        color: #f1f5f9;
    }
    
    .log-time {
        color: #64748b;
        font-size: 0.8rem;
    }
    
    .concept-card {
        background: rgba(30, 41, 59, 0.5);
        border-radius: 12px;
        padding: 1.2rem;
        border: 1px solid rgba(99, 102, 241, 0.2);
    }
    
    .concept-title {
        color: #f1f5f9;
        font-weight: 600;
        margin-bottom: 0.5rem;
        font-size: 1rem;
    }
    
    .concept-desc {
        color: #94a3b8;
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
        🔄 Replicación y Consistencia
    </h1>
    <p style="color: #94a3b8; font-size: 1rem;">Monitor del estado de replicación de datos en el cluster</p>
</div>
""", unsafe_allow_html=True)

# Panel informativo
st.markdown("""
<div class="info-panel">
    <div class="info-title">📖 ¿Qué es la Replicación?</div>
    <p class="info-text">
        La <strong>replicación</strong> es el proceso de mantener copias idénticas de los datos en múltiples nodos del cluster.
        Esto garantiza <strong>alta disponibilidad</strong> (los datos siguen accesibles si un nodo falla) y 
        <strong>tolerancia a fallos</strong> (no hay pérdida de datos).
    </p>
</div>
""", unsafe_allow_html=True)

# Obtener estado de replicación
replication_status = api_get("/cluster/replication")

if "error" in replication_status:
    st.warning(f"⚠️ No se pudo obtener estado de replicación: {replication_status['error']}")
    
    # Mostrar datos simulados para demo
    st.markdown("### 📊 Vista de Ejemplo")
    
    partitions_demo = [
        {"name": "partition-0", "leader": "node-1", "replicas": ["node-1", "node-2", "node-3"], "status": "synced", "log_index": 142},
        {"name": "partition-1", "leader": "node-2", "replicas": ["node-2", "node-3", "node-1"], "status": "synced", "log_index": 138},
        {"name": "partition-2", "leader": "node-3", "replicas": ["node-3", "node-1", "node-2"], "status": "syncing", "log_index": 137},
    ]
else:
    partitions_demo = replication_status.get("partitions", [])

# Resumen de replicación
col1, col2, col3, col4 = st.columns(4)

synced = sum(1 for p in partitions_demo if p.get("status") == "synced")
syncing = sum(1 for p in partitions_demo if p.get("status") == "syncing")
out_of_sync = sum(1 for p in partitions_demo if p.get("status") == "out-of-sync")
total = len(partitions_demo)

with col1:
    st.metric("📦 Total Particiones", total)

with col2:
    st.metric("✅ Sincronizadas", synced)

with col3:
    st.metric("🔄 Sincronizando", syncing)

with col4:
    st.metric("❌ Desincronizadas", out_of_sync)

st.markdown("---")

# Visualización de particiones
col_left, col_right = st.columns([1, 1])

with col_left:
    st.markdown("### 📦 Estado de Particiones")
    
    for partition in partitions_demo:
        status = partition.get("status", "unknown")
        status_class = f"status-{status.replace('_', '-')}"
        status_label = {
            "synced": "✅ Sincronizada",
            "syncing": "🔄 Sincronizando",
            "out-of-sync": "❌ Desincronizada"
        }.get(status, "❓ Desconocido")
        
        st.markdown(f"""
        <div class="replication-card">
            <div class="partition-header">
                <span class="partition-name">📁 {partition.get('name', 'N/A')}</span>
                <span class="partition-status {status_class}">{status_label}</span>
            </div>
            <div style="color: #94a3b8; font-size: 0.9rem;">
                Índice de log: <strong style="color: #a5b4fc;">{partition.get('log_index', 0)}</strong>
            </div>
            <div class="replica-list">
        """, unsafe_allow_html=True)
        
        for replica in partition.get("replicas", []):
            is_leader = replica == partition.get("leader")
            badge_class = "replica-badge replica-leader" if is_leader else "replica-badge"
            icon = "👑" if is_leader else "📥"
            st.markdown(f'<span class="{badge_class}">{icon} {replica}</span>', unsafe_allow_html=True)
        
        st.markdown("</div></div>", unsafe_allow_html=True)

with col_right:
    st.markdown("### 📊 Distribución de Réplicas")
    
    # Gráfico de distribución
    if partitions_demo:
        fig = go.Figure(data=[go.Bar(
            x=[p.get("name", f"P{i}") for i, p in enumerate(partitions_demo)],
            y=[len(p.get("replicas", [])) for p in partitions_demo],
            marker_color='#6366f1',
            text=[len(p.get("replicas", [])) for p in partitions_demo],
            textposition='outside',
            textfont=dict(color='#f1f5f9'),
        )])
        
        fig.update_layout(
            xaxis=dict(
                title="Partición",
                color='#94a3b8',
                tickcolor='#475569',
                linecolor='#475569',
            ),
            yaxis=dict(
                title="Número de Réplicas",
                color='#94a3b8',
                tickcolor='#475569',
                linecolor='#475569',
                gridcolor='rgba(71, 85, 105, 0.3)',
            ),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            height=300,
            margin=dict(t=30, b=50, l=50, r=30),
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Log de replicación simulado
    st.markdown("### 📝 Log de Replicación Reciente")
    
    logs_demo = [
        {"index": 142, "term": 5, "command": "PUT doc_001", "time": "hace 2s"},
        {"index": 141, "term": 5, "command": "PUT doc_002", "time": "hace 5s"},
        {"index": 140, "term": 5, "command": "DELETE doc_003", "time": "hace 12s"},
        {"index": 139, "term": 4, "command": "PUT doc_004", "time": "hace 30s"},
    ]
    
    for log in logs_demo:
        st.markdown(f"""
        <div class="log-entry">
            <div>
                <span class="log-index">#{log['index']}</span>
                <span class="log-term">T{log['term']}</span>
                <span class="log-command">{log['command']}</span>
            </div>
            <span class="log-time">{log['time']}</span>
        </div>
        """, unsafe_allow_html=True)

st.markdown("---")

# Conceptos educativos
st.markdown("### 📚 Conceptos de Replicación")

concepts = [
    {
        "icon": "👑",
        "title": "Líder (Leader)",
        "desc": "Nodo responsable de procesar todas las escrituras y coordinar la replicación hacia los seguidores."
    },
    {
        "icon": "📥",
        "title": "Seguidor (Follower)",
        "desc": "Nodos que reciben copias de los datos del líder. Pueden atender lecturas y están listos para convertirse en líder si es necesario."
    },
    {
        "icon": "📜",
        "title": "Log Replicado",
        "desc": "Secuencia ordenada de comandos que se replican a todos los nodos. Garantiza que todos apliquen los mismos cambios en el mismo orden."
    },
    {
        "icon": "🔄",
        "title": "Sincronización",
        "desc": "Proceso por el cual un seguidor actualiza su log para coincidir con el del líder, asegurando consistencia de datos."
    }
]

cols = st.columns(4)
for i, concept in enumerate(concepts):
    with cols[i]:
        st.markdown(f"""
        <div class="concept-card">
            <div class="concept-title">{concept['icon']} {concept['title']}</div>
            <p class="concept-desc">{concept['desc']}</p>
        </div>
        """, unsafe_allow_html=True)

# Botón de prueba de replicación
st.markdown("<br>", unsafe_allow_html=True)
col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    if st.button("🧪 Ejecutar Prueba de Replicación", use_container_width=True):
        with st.spinner("Ejecutando prueba de replicación..."):
            result = api_get("/tests/test/replication")
        
        if "error" not in result:
            st.success("✅ Prueba completada")
            if isinstance(result, dict) and result.get("success"):
                st.json(result)
        else:
            st.error(f"Error: {result.get('error')}")
