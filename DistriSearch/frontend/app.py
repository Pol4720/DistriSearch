"""
DistriSearch - Modern Distributed Search System
Home page with navigation and feature overview
"""
import streamlit as st
import os
<<<<<<< HEAD
import html as _html
from urllib.parse import urlparse
from utils.api_client import ApiClient
from components.styles import inject_css
from pages import AuthManager, TaskManager
=======
from utils.helpers import setup_page_config, init_session_state, get_api_client
from components.styles import apply_theme, get_animated_header, create_feature_card, create_metric_card
>>>>>>> e1cb07f02367011a93739309237b7d4c004d65b0

# Page config with sidebar always expanded initially
setup_page_config("DistriSearch - Home", "🔍", "wide", "expanded")

# Initialize
init_session_state()
api = get_api_client()

<<<<<<< HEAD
@st.cache_resource
def api_client():
    url = os.getenv("DISTRISEARCH_BACKEND_URL") or "http://localhost:8000"
    try:
        url = st.secrets.get("backend_url", url)  # type: ignore
    except Exception:
        pass
    # Optional admin API key for protected management endpoints
    api_key = os.getenv("DISTRISEARCH_ADMIN_API_KEY") or os.getenv("ADMIN_API_KEY")
    try:
        api_key = st.secrets.get("admin_api_key", api_key)  # type: ignore
    except Exception:
        pass

    # Auth token from session state
    auth_token = st.session_state.get('auth_token')
    return ApiClient(url, api_key=api_key, auth_token=auth_token)

api = api_client()

ss = st.session_state
ss.setdefault('theme', 'dark')
ss.setdefault('ui_mode', 'Distribuido')
ss.setdefault('last_central_scan', None)
ss.setdefault('search_results', None)   # dict from API
ss.setdefault('search_df', None)        # DataFrame for display
ss.setdefault('nodes_map', {})
ss.setdefault('selected_file_id', None)
ss.setdefault('last_download_url', None)
ss.setdefault('auth_token', None)
ss.setdefault('current_user', None)
ss.setdefault('show_register', False)
ss.setdefault('current_page', 'search')  # 'search' or 'tasks'

# Inject CSS based on current theme
inject_css(theme=ss['theme'])

# Theme toggle and navigation
top_left, top_mid, top_right = st.columns([1,4,2])
with top_left:
    logo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'assets', 'logo.png'))
    if os.path.isfile(logo_path):
        st.image(logo_path, width=72)
with top_mid:
    st.markdown("## DistriSearch")
    st.caption("Búsqueda distribuida y modo centralizado")
with top_right:
    col1, col2 = st.columns(2)
    with col1:
        if st.button('🌗 Tema'):
            ss.theme = 'light' if ss.theme == 'dark' else 'dark'
            st.rerun()
    with col2:
        if ss.get('auth_token'):
            if st.button('🚪 Cerrar Sesión'):
                ss.auth_token = None
                ss.current_user = None
                ss.current_page = 'search'
                st.rerun()
        else:
            if st.button('🔐 Iniciar Sesión'):
                ss.current_page = 'auth'
                st.rerun()

# Navigation tabs
if ss.get('auth_token'):
    nav_options = ["Buscar", "📋 Mis Tareas"]
    if ss.current_page not in ['search', 'tasks']:
        ss.current_page = 'search'
else:
    nav_options = ["Buscar"]
    if ss.current_page == 'tasks':
        ss.current_page = 'search'

nav_tabs = st.tabs(nav_options)
nav_idx = 0 if ss.current_page == 'search' else 1

# Main navigation logic
if ss.get('auth_token'):
    # User is authenticated
    with nav_tabs[0]:  # Search
        ss.current_page = 'search'
        show_search_interface()

    with nav_tabs[1]:  # Tasks
        ss.current_page = 'tasks'
        task_manager = TaskManager(api)
        task_manager.dashboard()
else:
    # User not authenticated - show auth or search
    if ss.current_page == 'auth':
        auth_manager = AuthManager(api)
        if ss.get('show_register', False):
            result = auth_manager.register_page()
        else:
            result = auth_manager.login_page()

        if result and 'access_token' in result:
            ss.auth_token = result['access_token']
            try:
                ss.current_user = api.get_current_user()
                ss.current_page = 'search'
                st.rerun()
            except Exception as e:
                st.error(f"Error al obtener información del usuario: {str(e)}")
                ss.auth_token = None
    else:
        # Show search interface for guests
        with nav_tabs[0]:
            show_search_interface()

def show_search_interface():
    """Muestra la interfaz de búsqueda."""
    mode_col1, mode_col2 = st.columns([2,8])
    with mode_col1:
        ss.ui_mode = st.radio("Modo", ["Distribuido","Centralizado"], horizontal=True, index=["Distribuido","Centralizado"].index(ss.ui_mode))
    with mode_col2:
        st.write("")

    # Build tabs dynamically depending on mode
    tab_names = ["Buscar"]
    if ss.ui_mode == "Distribuido":
        tab_names.append("Nodos")
    tab_names.extend(["Central","Estadísticas"])
    tabs = st.tabs(tab_names)
    ti = {name: i for i, name in enumerate(tab_names)}

    # ---------------------------- TAB: Buscar -----------------------------------
    with tabs[ti["Buscar"]]:
        query_col, type_col, btn_col = st.columns([5,2,1])
        query = query_col.text_input("Consulta", placeholder="Nombre, término o contenido...")
        tipo = type_col.selectbox("Tipo", ["Todos","Documentos","Imágenes","Videos","Audio","Otros"], index=0)
        buscar = btn_col.button("Buscar")

        # Execute search on click and persist in session
        if buscar and query:
            mapping = {"Documentos":"document","Imágenes":"image","Videos":"video","Audio":"audio","Otros":"other"}
            tipo_api = mapping.get(tipo) if tipo != 'Todos' else None
            with st.spinner("Buscando..."):
                try:
                    result = api.search_files(query, tipo_api)
                    ss.search_results = result
                    files = result.get('files', [])
                    nodes_map = {n['node_id']: n for n in result.get('nodes_available', [])}
                    ss.nodes_map = nodes_map
                    rows = []
                    for f in files:
                        node = nodes_map.get(f['node_id'], {'name':'?','status':'unknown'})
                        rows.append({
                            'Nombre': f['name'],
                            'Tamaño': _format_size(f['size']),
                            'Tipo': f['type'],
                            'Nodo': node['name'],
                            'Estado': node['status'],
                            'ID': f['file_id']
                        })
                    ss.search_df = pd.DataFrame(rows)
                except Exception as e:
                    st.error(f"Error en búsqueda: {str(e)}")

        # Display results
        if ss.search_df is not None and not ss.search_df.empty:
            st.markdown(f"### Resultados ({len(ss.search_df)})")
            st.dataframe(
                ss.search_df.drop(columns=['ID']),
                use_container_width=True,
                hide_index=True
            )

            # Download section
            if ss.selected_file_id:
                st.markdown("### Descarga")
                try:
                    download_info = api.get_download_url(ss.selected_file_id)
                    if download_info.get('download_url'):
                        st.markdown(f"[📥 Descargar archivo]({download_info['download_url']})")
                    if download_info.get('direct_node_url'):
                        st.markdown(f"[🔗 URL directa del nodo]({download_info['direct_node_url']})")
                except Exception as e:
                    st.error(f"Error al obtener URL de descarga: {str(e)}")
        elif buscar:
            st.info("No se encontraron resultados.")

    # Continue with other tabs...
    if ss.ui_mode == "Distribuido":
        with tabs[ti["Nodos"]]:
        st.markdown("### Gestión de nodos")
        with st.expander("Añadir nodo", expanded=True):
            c1,c2,c3,c4 = st.columns(4)
            node_id = c1.text_input("ID", placeholder="node1")
            node_name = c2.text_input("Nombre", placeholder="Agente 1")
            node_ip = c3.text_input("IP/Host", placeholder="127.0.0.1")
            node_port = c4.number_input("Puerto", min_value=1, max_value=65535, value=8081, step=1)
            if st.button("Registrar nodo") and node_id and node_name and node_ip:
                try:
                    res = api.register_node({
                        "node_id": node_id,
                        "name": node_name,
                        "ip_address": node_ip,
                        "port": int(node_port),
                        "status": "online",
                        "shared_files_count": 0
                    })
                    st.success(f"Nodo {res.get('node_id')} registrado/actualizado")
                except Exception as e:
                    st.error(f"Error al registrar nodo: {e}")

        with st.expander("Eliminar nodo"):
            del_id = st.text_input("ID de nodo a eliminar", placeholder="node1")
            del_files = st.checkbox("Eliminar también sus archivos del índice", value=True)
            if st.button("Eliminar nodo") and del_id:
                try:
                    res = api.delete_node(del_id, delete_files=del_files)
                    st.success(f"Nodo {res.get('node_id')} eliminado")
                except Exception as e:
                    st.error(f"Error al eliminar nodo: {e}")

        with st.expander("Simulación local (montar carpeta y escanear)", expanded=False):
            st.caption("Configura una carpeta local para un nodo (sin agente) y escanéala desde el backend.")
            # Crear nodo simulado (separado de nodos con agente)
            st.markdown("#### Crear nodo simulado (sin agente)")
            s1, s2, s3 = st.columns([2,2,1])
            sim_id = s1.text_input("ID de nodo simulado", placeholder="node_local_1", key="sim_node_id")
            sim_name = s2.text_input("Nombre", placeholder="Nodo Simulado", key="sim_node_name")
            if s3.button("Crear nodo simulado") and sim_id and sim_name:
                try:
                    res = api.register_node({
                        "node_id": sim_id,
                        "name": sim_name,
                        "ip_address": "127.0.0.1",
                        "port": 0,
                        "status": "online",
                        "shared_files_count": 0
                    })
                    st.success(f"Nodo simulado {res.get('node_id')} creado")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al crear nodo simulado: {e}")

            # Si hubo una ruta seleccionada por el diálogo en el ciclo anterior, aplícala
            if "pending_mount_folder" in st.session_state:
                st.session_state["mount_folder"] = st.session_state.pop("pending_mount_folder")
            m1,m2 = st.columns([2,3])
            mount_node = m1.text_input("ID de nodo", placeholder="node1", key="mount_node")
            mount_folder = m2.text_input("Carpeta local del nodo", placeholder="C:/ruta/a/carpeta", key="mount_folder")
            # Botón para seleccionar carpeta desde el Explorador de archivos (local)
            if m2.button("Seleccionar carpeta…"):
                try:
                    import tkinter as tk
                    from tkinter import filedialog
                    root = tk.Tk()
                    root.withdraw()
                    try:
                        # Llevar al frente el diálogo
                        root.call('wm', 'attributes', '.', '-topmost', True)
                    except Exception:
                        pass
                    folder = filedialog.askdirectory(title="Selecciona la carpeta del nodo")
                    root.destroy()
                    if folder:
                        # Guardar temporalmente y aplicarlo antes de renderizar el input en el próximo ciclo
                        st.session_state["pending_mount_folder"] = folder
                        st.rerun()
                except Exception as e:
                    st.warning(f"No se pudo abrir el selector del sistema. Ingresa la ruta manualmente. Detalle: {e}")
            cset, cscan = st.columns(2)
            if cset.button("Guardar carpeta del nodo") and mount_node and mount_folder:
                try:
                    res = api.set_node_mount(mount_node, mount_folder)
                    st.success(f"Carpeta configurada: {res.get('folder')}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al configurar carpeta: {e}")
            if cscan.button("Escanear e importar archivos") and mount_node:
                try:
                    res = api.import_node_folder(mount_node)
                    st.success(f"Importados: {res.get('imported',0)} desde {res.get('folder')}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al importar: {e}")

        with st.expander("Nodos registrados", expanded=True):
            try:
                nodes = api.get_nodes()
            except Exception:
                nodes = []
            if nodes:
                # Normalizar estado por si llega como 'NodeStatus.ONLINE'
                def _norm_status(x: str) -> str:
                    xs = str(x).lower()
                    if xs.endswith('online'):
                        return 'online'
                    if xs.endswith('offline'):
                        return 'offline'
                    return xs
                online = sum(1 for n in nodes if _norm_status(n.get('status',''))=='online')
                total = len(nodes)
                files_total = sum(n.get('shared_files_count',0) for n in nodes)
                m1,m2,m3 = st.columns(3)
                m1.metric("Activos", f"{online}/{total}")
                m2.metric("Archivos", files_total)
                m3.metric("Modo actual", ss.ui_mode)
                ndf = pd.DataFrame([{
                    'ID': n['node_id'],
                    'Nombre': n['name'],
                    'Estado': _norm_status(n.get('status','')),
                    'Archivos': n.get('shared_files_count',0),
                    'IP': n['ip_address'],
                    'Puerto': n['port']
                } for n in nodes])
                st.dataframe(ndf, hide_index=True, use_container_width=True)
            else:
                st.info("No hay nodos registrados")

        with st.expander("Replicación y tolerancia a fallos", expanded=False):
            st.caption("Ejecuta una pasada de replicación: mover archivos de nodos OFFLINE al repositorio central.")
            batch = st.slider("Batch", min_value=1, max_value=200, value=25, step=1)
            if st.button("Ejecutar replicación ahora"):
                try:
                    res = api.run_replication(batch=batch)
                    st.success(f"Revisados: {res.get('checked',0)} | Replicados: {res.get('replicated',0)}")
                except Exception as e:
                    st.error(f"Error ejecutando replicación: {e}")

# ---------------------------- TAB: Central ----------------------------------
with tabs[ti["Central"]]:
    st.markdown("### Modo Centralizado")
    st.caption("Escanea e indexa la carpeta central. Cambia el modo arriba para trabajar en central o distribuido.")
    folder = st.text_input("Carpeta central (vacío = por defecto)", value=ss.get('central_folder',''))
    auto = st.checkbox("Escanear automáticamente si no hay registro previo", value=True, key='auto_scan_central')
    run = st.button("Escanear ahora") or (auto and ss.last_central_scan is None)
    if run:
        with st.spinner("Escaneando..."):
            try:
                r = api.central_scan(folder or None)
                ss.last_central_scan = r.get('indexed_files')
                ss.central_folder = folder
                st.success(f"Indexados: {r.get('indexed_files')} | Carpeta: {r.get('folder')}")
            except Exception as e:
                st.error(f"Error: {e}")

# ---------------------------- TAB: Estadísticas ------------------------------
with tabs[ti["Estadísticas"]]:
    st.markdown("### Estadísticas")
=======
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
>>>>>>> e1cb07f02367011a93739309237b7d4c004d65b0
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
