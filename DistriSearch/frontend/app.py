"""
DistriSearch - Modern Distributed Search System
Home page with navigation and feature overview
"""
import streamlit as st
import os
import requests
from utils.helpers import setup_page_config, init_session_state, get_api_client
from components.styles import apply_theme, get_animated_header, create_feature_card, create_metric_card

# Page config with sidebar always expanded initially
setup_page_config("DistriSearch - Home", "🔍", "wide", "expanded")

# Initialize
init_session_state()
api = get_api_client()

# Check authentication
if "token" not in st.session_state or not st.session_state.token:
    # Show login/register forms without sidebar
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

            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                submit_button = st.form_submit_button("🚀 Iniciar Sesión", use_container_width=True, type="primary")

            if submit_button:
                if not username or not password:
                    st.error("Por favor, completa todos los campos.")
                    st.stop()

                with st.spinner("Verificando credenciales..."):
                    try:
                        response = requests.post(f"{api.base_url}/token", json={"username": username, "password": password})
                        if response.status_code == 200:
                            token_data = response.json()
                            st.session_state.token = token_data["access_token"]
                            st.session_state.username = username
                            st.success("¡Inicio de sesión exitoso!")
                            st.rerun()
                        else:
                            st.error("Usuario o contraseña incorrectos.")
                    except Exception as e:
                        st.error(f"Error de conexión: {str(e)}")

    with tab2:
        st.markdown("""
        <div style="text-align: center; margin-bottom: 2rem;">
            <h1>📝 Registrarse</h1>
            <p style="color: #666;">Crea tu cuenta para acceder al sistema</p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("register_form_main"):
            username = st.text_input("Usuario", placeholder="Elige un usuario único")
            email = st.text_input("Correo Electrónico", placeholder="tu@email.com")
            password = st.text_input("Contraseña", type="password", placeholder="Crea una contraseña segura")
            confirm_password = st.text_input("Confirmar Contraseña", type="password", placeholder="Repite la contraseña")

            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                submit_button = st.form_submit_button("📝 Registrarse", use_container_width=True, type="primary")

            if submit_button:
                if not username or not email or not password or not confirm_password:
                    st.error("Por favor, completa todos los campos.")
                    st.stop()
                if password != confirm_password:
                    st.error("Las contraseñas no coinciden.")
                    st.stop()
                if len(password) < 6:
                    st.error("La contraseña debe tener al menos 6 caracteres.")
                    st.stop()

                with st.spinner("Creando cuenta..."):
                    try:
                        response = requests.post(f"{api.base_url}/register", json={"username": username, "email": email, "password": password})
                        if response.status_code == 200:
                            token_data = response.json()
                            st.session_state.token = token_data["access_token"]
                            st.session_state.username = username
                            st.success("¡Cuenta creada exitosamente!")
                            st.rerun()
                        else:
                            error_detail = response.json().get("detail", "Error desconocido")
                            st.error(f"Error al registrar: {error_detail}")
                    except Exception as e:
                        st.error(f"Error de conexión: {str(e)}")

    st.stop()  # Stop execution here if not logged in

# Apply modern theme
apply_theme(st.session_state.theme)

# Sidebar with improved UX
with st.sidebar:
    logo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'assets', 'logo.png'))
    if os.path.isfile(logo_path):
        st.image(logo_path, width=120)
    else:
        st.markdown("### 🔍 DistriSearch")
    
    st.markdown("---")
    
    # Theme toggle with better UI
    st.markdown("### 🎨 Tema de interfaz")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button('🌙 Oscuro' if st.session_state.theme == 'light' else '🌙 Oscuro', 
                    key='dark_theme',
                    disabled=st.session_state.theme == 'dark',
                    use_container_width=True):
            st.session_state.theme = 'dark'
            st.rerun()
    with col2:
        if st.button('☀️ Claro' if st.session_state.theme == 'dark' else '☀️ Claro', 
                    key='light_theme',
                    disabled=st.session_state.theme == 'light',
                    use_container_width=True):
            st.session_state.theme = 'light'
            st.rerun()
    
    st.markdown("---")
    
    # User info and logout
    if "username" in st.session_state:
        st.markdown(f"### 👤 {st.session_state.username}")
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            del st.session_state.token
            del st.session_state.username
            st.rerun()
    
    st.markdown("---")
    
    # Mode selector with better contrast
    st.markdown("### 🌐 Modo de operación")
    mode_options = ["🌐 Distribuido", "🏢 Centralizado"]
    current_idx = 0 if st.session_state.ui_mode == 'Distribuido' else 1
    
    selected_mode = st.radio(
        "Selecciona el modo:",
        mode_options,
        index=current_idx,
        label_visibility="collapsed",
        key="mode_selector"
    )
    
    if "Distribuido" in selected_mode:
        st.session_state.ui_mode = 'Distribuido'
    else:
        st.session_state.ui_mode = 'Centralizado'
    
    st.markdown("---")
    
    # System status with improved styling
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
    - 🏢 **Central** - Panel
    - 📊 **Estadísticas**
    """)
    
    st.markdown("---")
    st.caption("💡 **Tip**: Puedes ocultar/mostrar este menú con el botón superior izquierdo")


# Main content
# Main content with animated header
st.markdown(get_animated_header("🔍 DistriSearch", "Sistema de Búsqueda Distribuida de Nueva Generación"), unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("""
    <div class="glass-panel" style="padding: 2rem; margin-bottom: 1.5rem;">
        <h2 style="margin-top: 0; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 2.2rem;">
            Bienvenido a DistriSearch 
        </h2>
        <p style="font-size: 1.1rem; line-height: 1.8; opacity: 0.9;">
            Experimenta la búsqueda distribuida de archivos con una interfaz moderna y potente.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="features-grid">
        <div class="feature-card">
            <div class="feature-icon"></div>
            <h3>Búsqueda Ultra-Rápida</h3>
            <p>Algoritmo BM25 optimizado</p>
        </div>
        <div class="feature-card">
            <div class="feature-icon"></div>
            <h3>Arquitectura Distribuida</h3>
            <p>Escalabilidad horizontal</p>
        </div>
        <div class="feature-card">
            <div class="feature-icon"></div>
            <h3>Seguro & Confiable</h3>
            <p>Autenticación robusta</p>
        </div>
        <div class="feature-card">
            <div class="feature-icon"></div>
            <h3>Monitoreo en Tiempo Real</h3>
            <p>Métricas detalladas</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="glass-panel" style="padding: 1.5rem;">
        <h3 style="margin-top: 0; color: #667eea;"> Acciones Rápidas</h3>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.info(" Usa el menú lateral para navegar")
    mode_emoji = "" if st.session_state.ui_mode == "Distribuido" else ""
    st.success(f"**Modo actual:** {mode_emoji} {st.session_state.ui_mode}")

st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown("""
<div class="glass-panel" style="padding: 1.5rem; text-align: center;">
    <h3> Cómo funciona?</h3>
    <p style="font-size: 1rem; opacity: 0.85; line-height: 1.7;">
        DistriSearch utiliza una arquitectura P2P donde cada nodo mantiene su propio índice de archivos.
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
                <div class="metric-label"> ARCHIVOS TOTALES</div>
                <div class="metric-value">{stats.get('total_files', 0)}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label"> NODOS TOTALES</div>
                <div class="metric-value">{stats.get('total_nodes', 0)}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label"> NODOS ACTIVOS</div>
                <div class="metric-value">{stats.get('active_nodes', 0)}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label"> DUPLICADOS</div>
                <div class="metric-value">{stats.get('duplicates_count', 0)}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
except Exception:
    pass

st.markdown(f"""
<div style="text-align: center; opacity: 0.6; font-size: 0.85rem; padding: 2rem 0;">
    DistriSearch v2.0 | Modo: <span style="color: #667eea;">{st.session_state.ui_mode}</span>
</div>
""", unsafe_allow_html=True)
