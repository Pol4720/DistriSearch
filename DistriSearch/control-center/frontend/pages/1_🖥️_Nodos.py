"""
🖥️ Gestión de Nodos
Control de contenedores Docker del cluster
"""

import streamlit as st
import requests
from datetime import datetime

st.set_page_config(
    page_title="Nodos - Control Center",
    page_icon="🖥️",
    layout="wide",
)

# CSS (mismo estilo)
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
    
    .container-card {
        background: rgba(30, 41, 59, 0.6);
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        border: 1px solid rgba(99, 102, 241, 0.2);
        transition: all 0.3s ease;
    }
    
    .container-card:hover {
        border-color: rgba(99, 102, 241, 0.5);
        box-shadow: 0 4px 20px rgba(99, 102, 241, 0.1);
    }
    
    .container-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1rem;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid rgba(99, 102, 241, 0.1);
    }
    
    .container-name {
        color: #f1f5f9;
        font-weight: 600;
        font-size: 1.1rem;
    }
    
    .container-info {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 0.75rem;
        color: #94a3b8;
        font-size: 0.9rem;
    }
    
    .container-info-item {
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
    
    .status-running {
        background: rgba(16, 185, 129, 0.15);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.4);
    }
    
    .status-exited {
        background: rgba(239, 68, 68, 0.15);
        color: #f87171;
        border: 1px solid rgba(239, 68, 68, 0.4);
    }
    
    .status-paused {
        background: rgba(245, 158, 11, 0.15);
        color: #fbbf24;
        border: 1px solid rgba(245, 158, 11, 0.4);
    }
    
    .action-section {
        background: rgba(15, 23, 42, 0.5);
        border-radius: 10px;
        padding: 1rem;
        margin-top: 1rem;
    }
    
    .action-title {
        color: #94a3b8;
        font-size: 0.85rem;
        font-weight: 500;
        margin-bottom: 0.75rem;
    }
    
    .warning-box {
        background: rgba(245, 158, 11, 0.1);
        border: 1px solid rgba(245, 158, 11, 0.3);
        border-radius: 10px;
        padding: 1rem;
        color: #fbbf24;
        margin-top: 1rem;
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


def api_post(endpoint: str) -> dict:
    try:
        response = requests.post(f"{BACKEND_URL}/api{endpoint}", timeout=30)
        return response.json() if response.ok else {"error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def get_status_badge(status: str) -> str:
    configs = {
        "running": ("▶", "status-running", "ACTIVO"),
        "exited": ("■", "status-exited", "DETENIDO"),
        "paused": ("⏸", "status-paused", "PAUSADO"),
    }
    icon, css, label = configs.get(status.lower(), ("?", "status-exited", status.upper()))
    return f'<span class="status-badge {css}">{icon} {label}</span>'


# Header
st.markdown("""
<div style="text-align: center; padding: 2rem 0;">
    <h1 style="font-size: 2.5rem; font-weight: 800; background: linear-gradient(135deg, #6366f1, #a855f7); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
        🖥️ Gestión de Nodos
    </h1>
    <p style="color: #94a3b8; font-size: 1rem;">Control de contenedores Docker del cluster DistriSearch</p>
</div>
""", unsafe_allow_html=True)

# Obtener contenedores
containers_data = api_get("/nodes/containers")

if "error" in containers_data:
    st.error(f"Error: {containers_data['error']}")
    st.stop()

if not containers_data.get("docker_available", False):
    st.warning("⚠️ Docker no está disponible")
    st.markdown("""
    <div class="warning-box">
        <strong>Docker no accesible</strong><br>
        Para habilitar el control de nodos, asegúrate de que:
        <ul>
            <li>Docker esté instalado y corriendo</li>
            <li>El backend tenga acceso al socket de Docker</li>
            <li>El usuario tenga permisos adecuados</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

containers = containers_data.get("containers", [])

if not containers:
    st.info("📦 No se encontraron contenedores de DistriSearch")
    st.stop()

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
st.markdown(f"### 📦 {len(containers)} Contenedores Encontrados")

for container in containers:
    name = container["name"]
    status = container.get("status", "unknown")
    is_master = container.get("is_master", False)
    
    with st.expander(f"{'👑 ' if is_master else '🔹 '}{name}", expanded=(status == "running")):
        st.markdown(f"""
        <div class="container-card">
            <div class="container-header">
                <span class="container-name">{'👑 Master: ' if is_master else '🔹 Slave: '}{name}</span>
                {get_status_badge(status)}
            </div>
            <div class="container-info">
                <div class="container-info-item">
                    <span>🆔</span>
                    <code>{container['id']}</code>
                </div>
                <div class="container-info-item">
                    <span>🐳</span>
                    <span>{container['image']}</span>
                </div>
                <div class="container-info-item">
                    <span>🔌</span>
                    <span>{', '.join(container.get('ports', [])) or 'N/A'}</span>
                </div>
                <div class="container-info-item">
                    <span>📅</span>
                    <span>{container.get('created', 'N/A')[:19]}</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Acciones básicas
        st.markdown('<div class="action-section">', unsafe_allow_html=True)
        st.markdown('<p class="action-title">⚡ Acciones Básicas</p>', unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns(3)
        
        with c1:
            if status == "running":
                if st.button("⏹️ Detener", key=f"stop_{name}", use_container_width=True):
                    with st.spinner("Deteniendo..."):
                        result = api_post(f"/nodes/stop/{name}")
                    if "error" not in result:
                        st.success("✅ Detenido")
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
        
        with c2:
            if status == "running":
                if st.button("🔄 Reiniciar", key=f"restart_{name}", use_container_width=True):
                    with st.spinner("Reiniciando..."):
                        result = api_post(f"/nodes/restart/{name}")
                    if "error" not in result:
                        st.success("✅ Reiniciado")
                        st.rerun()
                    else:
                        st.error(result["error"])
        
        with c3:
            if status == "paused":
                if st.button("▶️ Reanudar", key=f"unpause_{name}", use_container_width=True):
                    with st.spinner("Reanudando..."):
                        result = api_post(f"/nodes/unpause/{name}")
                    if "error" not in result:
                        st.success("✅ Reanudado")
                        st.rerun()
                    else:
                        st.error(result["error"])
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Acciones avanzadas
        if status == "running":
            st.markdown('<div class="action-section">', unsafe_allow_html=True)
            st.markdown('<p class="action-title">⚠️ Acciones Avanzadas (Simulación de Fallos)</p>', unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            
            with c1:
                if st.button("💀 Kill (SIGKILL)", key=f"kill_{name}", use_container_width=True, type="secondary"):
                    with st.spinner("Terminando proceso..."):
                        result = api_post(f"/nodes/kill/{name}")
                    if "error" not in result:
                        st.warning("⚠️ Proceso terminado abruptamente")
                        st.rerun()
                    else:
                        st.error(result["error"])
            
            with c2:
                if st.button("🌐 Pausar (Partición Red)", key=f"pause_{name}", use_container_width=True, type="secondary"):
                    with st.spinner("Pausando..."):
                        result = api_post(f"/nodes/pause/{name}")
                    if "error" not in result:
                        st.info("🌐 Nodo pausado - simula partición de red")
                        st.rerun()
                    else:
                        st.error(result["error"])
            
            st.markdown('</div>', unsafe_allow_html=True)

# Explicaciones
st.markdown("---")
st.markdown("### 📚 ¿Qué hace cada acción?")

c1, c2 = st.columns(2)

with c1:
    st.markdown("""
    <div class="concept-box">
        <div class="concept-title">⏹️ Detener vs 💀 Kill</div>
        <p class="concept-text">
            <strong>Detener</strong> envía SIGTERM permitiendo un apagado controlado.<br><br>
            <strong>Kill</strong> envía SIGKILL terminando inmediatamente, simulando un fallo catastrófico 
            donde el nodo no puede notificar su salida.
        </p>
    </div>
    """, unsafe_allow_html=True)

with c2:
    st.markdown("""
    <div class="concept-box">
        <div class="concept-title">🌐 Pausar (Partición de Red)</div>
        <p class="concept-text">
            Pausar congela el proceso sin terminarlo. El nodo está "vivo" pero no puede comunicarse.<br><br>
            Simula una <strong>partición de red</strong> donde el nodo queda aislado del cluster.
            Útil para probar tolerancia a particiones (CAP theorem).
        </p>
    </div>
    """, unsafe_allow_html=True)
