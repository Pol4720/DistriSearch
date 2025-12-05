"""
DistriSearch - Distributed Search System
Home page with navigation and feature overview
"""
import streamlit as st
import os
import pandas as pd
from utils.helpers import setup_page_config, init_session_state, get_api_client
from components.styles import apply_theme, get_animated_header

setup_page_config("DistriSearch - Home", "🔍", "wide", "expanded")

init_session_state()
api = get_api_client()

# Check authentication
if "token" not in st.session_state or not st.session_state.token:
    tab1, tab2 = st.tabs(["🔐 Iniciar Sesión", "📝 Registrarse"])
    
    with tab1:
        st.markdown("""
        <div style="text-align: center; margin-bottom: 2rem;">
            <h1>🔐 Iniciar Sesión</h1>
            <p style="color: #666;">Accede a tu cuenta de DistriSearch</p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form_main"):
            username = st.text_input("Usuario", placeholder="Ingresa tu usuario")
            password = st.text_input("Contraseña", type="password", placeholder="Ingresa tu contraseña")
            submitted = st.form_submit_button("Iniciar Sesión", use_container_width=True)
            
            if submitted:
                if username and password:
                    try:
                        result = api.login(username, password)
                        st.session_state.token = result["access_token"]
                        st.session_state.username = username
                        st.success("✅ Inicio de sesión exitoso")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error: {e}")
                else:
                    st.warning("⚠️ Por favor completa todos los campos")

    with tab2:
        st.markdown("""
        <div style="text-align: center; margin-bottom: 2rem;">
            <h1>📝 Registrarse</h1>
            <p style="color: #666;">Crea tu cuenta para acceder al sistema</p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("register_form_main"):
            email = st.text_input("Email", placeholder="tu@email.com")
            username = st.text_input("Usuario", placeholder="Elige un nombre de usuario")
            password = st.text_input("Contraseña", type="password", placeholder="Mínimo 6 caracteres")
            password_confirm = st.text_input("Confirmar Contraseña", type="password")
            submitted = st.form_submit_button("Registrarse", use_container_width=True)
            
            if submitted:
                if email and username and password and password_confirm:
                    if password != password_confirm:
                        st.error("❌ Las contraseñas no coinciden")
                    elif len(password) < 6:
                        st.error("❌ La contraseña debe tener al menos 6 caracteres")
                    else:
                        try:
                            api.register(email, username, password)
                            st.success("✅ Registro exitoso! Ahora puedes iniciar sesión")
                        except Exception as e:
                            st.error(f"❌ Error: {e}")
                else:
                    st.warning("⚠️ Por favor completa todos los campos")

    st.stop()

# Apply modern theme
apply_theme(st.session_state.theme)

# Sidebar
with st.sidebar:
    logo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'assets', 'logo.png'))
    if os.path.isfile(logo_path):
        st.image(logo_path, width=120)
    else:
        st.markdown("### 🔍 DistriSearch")
    
    st.markdown("---")
    
    # Theme toggle
    st.markdown("### 🎨 Tema de interfaz")
    col1, col2 = st.columns(2)
    with col1:
        if st.button('🌙 Oscuro', 
                    key='dark_theme',
                    disabled=st.session_state.theme == 'dark',
                    use_container_width=True):
            st.session_state.theme = 'dark'
            st.rerun()
    with col2:
        if st.button('☀️ Claro', 
                    key='light_theme',
                    disabled=st.session_state.theme == 'light',
                    use_container_width=True):
            st.session_state.theme = 'light'
            st.rerun()
    
    st.markdown("---")
    
    # User info
    if "username" in st.session_state:
        st.markdown(f"### 👤 {st.session_state.username}")
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            st.session_state.clear()
            st.rerun()
    
    st.markdown("---")
    
    # System status
    st.markdown("### 📊 Estado del Sistema")
    try:
        nodes = api.get_nodes()
        online_nodes = sum(1 for n in nodes if 'online' in str(n.get('status', '')).lower())
        st.metric("Nodos en línea", online_nodes, f"de {len(nodes)}")
    except Exception:
        st.metric("Nodos en línea", "N/A")
    
    st.markdown("---")
    
    # Navigation info
    st.markdown("### 🧭 Navegación")
    st.info("""
    **Usa las páginas del menú** para navegar:
    - 🔍 **Buscar** archivos
    - 🌐 **Nodos** - Gestión
    - 📊 **Estadísticas**
    """)

# Main content
st.markdown(get_animated_header("🔍 DistriSearch", "Sistema de Búsqueda Distribuida"), unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("""
    <div class="glass-panel" style="padding: 2rem; margin-bottom: 1.5rem;">
        <h2 style="margin-top: 0; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 2.2rem;">
            Bienvenido a DistriSearch 
        </h2>
        <p style="font-size: 1.1rem; line-height: 1.8; opacity: 0.9;">
            Sistema de búsqueda distribuida con arquitectura Master-Slave y vectorización semántica.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="features-grid">
        <div class="feature-card">
            <div class="feature-icon">🚀</div>
            <h3>Búsqueda Ultra-Rápida</h3>
            <p>Algoritmo BM25 optimizado</p>
        </div>
        <div class="feature-card">
            <div class="feature-icon">🌐</div>
            <h3>Arquitectura Master-Slave</h3>
            <p>Distribución con vectorización semántica</p>
        </div>
        <div class="feature-card">
            <div class="feature-icon">🔒</div>
            <h3>Seguro & Confiable</h3>
            <p>Autenticación robusta</p>
        </div>
        <div class="feature-card">
            <div class="feature-icon">📊</div>
            <h3>Monitoreo en Tiempo Real</h3>
            <p>Métricas detalladas</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="glass-panel" style="padding: 1.5rem;">
        <h3 style="margin-top: 0; color: #667eea;">⚡ Acciones Rápidas</h3>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.info("💡 Usa el menú lateral para navegar")
    st.success("**Modo:** 🌐 Distribuido")

st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown("""
<div class="glass-panel" style="padding: 1.5rem; text-align: center;">
    <h3>❓ ¿Cómo funciona?</h3>
    <p style="font-size: 1rem; opacity: 0.85; line-height: 1.7;">
        DistriSearch utiliza una arquitectura Master-Slave donde el Master coordina búsquedas mediante
        vectorización semántica y los Slaves almacenan y sirven los archivos de forma distribuida.
    </p>
</div>
""", unsafe_allow_html=True)

# Stats
st.markdown("<br><br>", unsafe_allow_html=True)
try:
    stats = api.get_stats()
    if stats:
        st.markdown(f"""
        <div class="features-grid">
            <div class="metric-card">
                <div class="metric-label">📁 ARCHIVOS TOTALES</div>
                <div class="metric-value">{stats.get('total_files', 0)}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">🖥️ NODOS TOTALES</div>
                <div class="metric-value">{stats.get('total_nodes', 0)}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">✅ NODOS ACTIVOS</div>
                <div class="metric-value">{stats.get('active_nodes', 0)}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">🔄 DUPLICADOS</div>
                <div class="metric-value">{stats.get('duplicates_count', 0)}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
except Exception:
    pass

st.markdown(f"""
<div style="text-align: center; opacity: 0.6; font-size: 0.85rem; padding: 2rem 0;">
    DistriSearch v2.0 - Arquitectura Master-Slave
</div>
""", unsafe_allow_html=True)
