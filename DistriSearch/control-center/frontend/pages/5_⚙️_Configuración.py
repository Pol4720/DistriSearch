"""
⚙️ Configuración
Ajustes y configuración del sistema de monitoreo
"""

import streamlit as st

st.set_page_config(
    page_title="Configuración - Control Center",
    page_icon="⚙️",
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
    
    .config-section {
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(12px);
        border-radius: 16px;
        padding: 1.5rem;
        border: 1px solid rgba(99, 102, 241, 0.2);
        margin-bottom: 1.5rem;
    }
    
    .section-title {
        color: #f1f5f9;
        font-size: 1.2rem;
        font-weight: 600;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    .config-item {
        background: rgba(15, 23, 42, 0.5);
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 0.75rem;
    }
    
    .config-label {
        color: #94a3b8;
        font-size: 0.85rem;
        margin-bottom: 0.5rem;
    }
    
    .config-desc {
        color: #64748b;
        font-size: 0.8rem;
        margin-top: 0.5rem;
    }
    
    .status-badge {
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 500;
    }
    
    .badge-success {
        background: rgba(16, 185, 129, 0.2);
        color: #10b981;
    }
    
    .badge-warning {
        background: rgba(245, 158, 11, 0.2);
        color: #f59e0b;
    }
    
    .badge-error {
        background: rgba(239, 68, 68, 0.2);
        color: #ef4444;
    }
    
    .info-box {
        background: linear-gradient(145deg, rgba(99, 102, 241, 0.1), rgba(30, 41, 59, 0.5));
        border-radius: 12px;
        padding: 1rem;
        border: 1px solid rgba(99, 102, 241, 0.3);
        margin-bottom: 1rem;
    }
    
    .info-title {
        color: #a5b4fc;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }
    
    .info-text {
        color: #94a3b8;
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)

# Inicializar configuración en session state
if "backend_url" not in st.session_state:
    st.session_state.backend_url = st.secrets.get("BACKEND_URL", "http://localhost:8888")

if "refresh_interval" not in st.session_state:
    st.session_state.refresh_interval = 5

if "theme" not in st.session_state:
    st.session_state.theme = "oscuro"

# Header
st.markdown("""
<div style="text-align: center; padding: 2rem 0;">
    <h1 style="font-size: 2.5rem; font-weight: 800; background: linear-gradient(135deg, #6366f1, #a855f7); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
        ⚙️ Configuración
    </h1>
    <p style="color: #94a3b8; font-size: 1rem;">Ajusta la configuración del Centro de Control</p>
</div>
""", unsafe_allow_html=True)

col_left, col_right = st.columns([1, 1], gap="large")

with col_left:
    # Conexión al Backend
    st.markdown("""
    <div class="section-title">🔌 Conexión al Backend</div>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="config-section">', unsafe_allow_html=True)
    
    backend_url = st.text_input(
        "URL del Backend API",
        value=st.session_state.backend_url,
        placeholder="http://localhost:8888",
        help="Dirección del servidor backend del Control Center"
    )
    
    if backend_url != st.session_state.backend_url:
        st.session_state.backend_url = backend_url
    
    distrisearch_url = st.text_input(
        "URL de DistriSearch",
        value="http://localhost:8001",
        placeholder="http://localhost:8001",
        help="Dirección del cluster DistriSearch principal"
    )
    
    # Test de conexión
    if st.button("🔍 Probar Conexión", use_container_width=True):
        import requests
        with st.spinner("Probando conexión..."):
            try:
                response = requests.get(f"{backend_url}/health", timeout=5)
                if response.ok:
                    st.success("✅ Conexión exitosa al backend")
                else:
                    st.warning(f"⚠️ Respuesta: {response.status_code}")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Intervalos de actualización
    st.markdown("""
    <div class="section-title">⏱️ Actualización Automática</div>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="config-section">', unsafe_allow_html=True)
    
    refresh_interval = st.slider(
        "Intervalo de actualización (segundos)",
        min_value=1,
        max_value=30,
        value=st.session_state.refresh_interval,
        step=1,
        help="Cada cuántos segundos se actualizan los datos automáticamente"
    )
    
    if refresh_interval != st.session_state.refresh_interval:
        st.session_state.refresh_interval = refresh_interval
        st.info(f"✓ Intervalo actualizado a {refresh_interval}s")
    
    auto_refresh_default = st.checkbox(
        "Habilitar auto-actualización por defecto",
        value=False,
        help="Iniciar con actualización automática habilitada"
    )
    
    st.markdown('</div>', unsafe_allow_html=True)

with col_right:
    # Apariencia
    st.markdown("""
    <div class="section-title">🎨 Apariencia</div>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="config-section">', unsafe_allow_html=True)
    
    theme = st.radio(
        "Tema de la interfaz",
        options=["oscuro", "claro"],
        index=0 if st.session_state.theme == "oscuro" else 1,
        horizontal=True,
        help="El tema oscuro es el recomendado para uso prolongado"
    )
    
    if theme != st.session_state.theme:
        st.session_state.theme = theme
        st.info(f"✓ Tema cambiado a {theme}")
    
    show_animations = st.checkbox(
        "Mostrar animaciones",
        value=True,
        help="Habilita/deshabilita animaciones de la interfaz"
    )
    
    compact_mode = st.checkbox(
        "Modo compacto",
        value=False,
        help="Reduce el espaciado para mostrar más información"
    )
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Notificaciones
    st.markdown("""
    <div class="section-title">🔔 Notificaciones</div>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="config-section">', unsafe_allow_html=True)
    
    notify_node_down = st.checkbox(
        "🔴 Alertar cuando un nodo caiga",
        value=True
    )
    
    notify_leader_change = st.checkbox(
        "👑 Alertar en cambio de líder",
        value=True
    )
    
    notify_sync_issues = st.checkbox(
        "🔄 Alertar problemas de sincronización",
        value=True
    )
    
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("---")

# Información del Sistema
st.markdown("""
<div class="section-title">📊 Información del Sistema</div>
""", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    <div class="info-box">
        <div class="info-title">🏷️ Versión</div>
        <p class="info-text">Control Center v1.0.0</p>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="info-box">
        <div class="info-title">🐍 Streamlit</div>
        <p class="info-text">v1.29.0</p>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
    <div class="info-box">
        <div class="info-title">⚡ Backend</div>
        <p class="info-text">FastAPI 0.104.1</p>
    </div>
    """, unsafe_allow_html=True)

# Acciones de administración
st.markdown("### 🛠️ Acciones de Administración")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🔄 Reiniciar Conexiones", use_container_width=True):
        st.cache_data.clear()
        st.success("✅ Cache limpiado")

with col2:
    if st.button("📋 Exportar Configuración", use_container_width=True):
        config = {
            "backend_url": st.session_state.backend_url,
            "refresh_interval": st.session_state.refresh_interval,
            "theme": st.session_state.theme,
        }
        st.json(config)

with col3:
    if st.button("🔙 Restaurar Valores", use_container_width=True):
        st.session_state.backend_url = "http://localhost:8888"
        st.session_state.refresh_interval = 5
        st.session_state.theme = "oscuro"
        st.success("✅ Configuración restaurada")
        st.rerun()

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #64748b; padding: 1rem;">
    <p>Control Center para DistriSearch</p>
    <p style="font-size: 0.8rem;">Sistema de monitoreo y pruebas para arquitectura distribuida</p>
</div>
""", unsafe_allow_html=True)
