import streamlit as st
import pandas as pd
import os
from utils.api_client import ApiClient
from components.styles import inject_css

st.set_page_config(page_title="DistriSearch", page_icon="🔎", layout="wide", initial_sidebar_state="collapsed")

# ---- Utilities ----
def _format_size(size_bytes: int) -> str:
    for unit in ['B','KB','MB','GB','TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"

@st.cache_resource
def get_api_client():
    backend_url = os.getenv("DISTRISEARCH_BACKEND_URL") or "http://localhost:8000"
    try:
        backend_url = st.secrets.get("backend_url", backend_url)  # type: ignore
    except Exception:
        pass
    return ApiClient(backend_url)

api = get_api_client()

# Inject CSS
inject_css()

# ---- Session State Defaults ----
ss = st.session_state
ss.setdefault('theme_mode', 'dark')
ss.setdefault('active_tab', 'Buscar')
ss.setdefault('ui_mode', 'Distribuido')

# ---- Top Nav Bar ----
logo_path_default = os.path.join(os.path.dirname(__file__), '..', 'assets', 'logo.png')
logo_path_env = os.getenv('DISTRISEARCH_LOGO')
logo_path = logo_path_env if (logo_path_env and os.path.isfile(logo_path_env)) else logo_path_default

nav_cols = st.columns([6,4,2])
with nav_cols[0]:
    st.markdown(f'''<div class="navbar"><div class="logo"><img src="file://{logo_path}" alt="logo"/> DistriSearch</div>''', unsafe_allow_html=True)
with nav_cols[1]:
    tabs_html = []
    for tab in ["Buscar","Nodos","Central","Estadísticas"]:
        active = 'true' if ss.active_tab == tab else 'false'
        tabs_html.append(f'<button data-active="{active}" onclick="window.location.search=\'?tab={tab}\'">{tab}</button>')
    st.markdown(f'<div class="nav-tabs">{"".join(tabs_html)}</div>', unsafe_allow_html=True)
with nav_cols[2]:
    toggle_label = '☀️ Claro' if ss.theme_mode == 'dark' else '🌙 Oscuro'
    if st.button(toggle_label):
        ss.theme_mode = 'light' if ss.theme_mode == 'dark' else 'dark'
    st.markdown('</div>', unsafe_allow_html=True)  # close navbar root

st.markdown(f'<script>document.body.classList.{"add" if ss.theme_mode=="light" else "remove"}("light-mode");</script>', unsafe_allow_html=True)

# Parse tab from query params (workaround for simple routing)
qp = st.query_params
if 'tab' in qp:
    ss.active_tab = qp['tab'] if isinstance(qp['tab'], str) else qp['tab'][0]

# ---- Data Fetch Helpers ----
def fetch_mode():
    try:
        return api.get_mode()
    except Exception:
        return {"centralized": False, "distributed": True}

def fetch_nodes():
    try:
        return api.get_nodes()
    except Exception:
        return []

def fetch_stats():
    try:
        return api.get_stats()
    except Exception:
        return {}

backend_mode = fetch_mode()

# ---- Panels by Tab ----
if ss.active_tab == 'Buscar':
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown("### 🔍 Búsqueda Distribuida")
    col_search, col_type, col_btn = st.columns([6,2,1])
    query = col_search.text_input("", placeholder="Escribe nombre, término o contenido...")
    file_type = col_type.selectbox("Tipo", ["Todos","Documentos","Imágenes","Videos","Audio","Otros"])
    do_search = col_btn.button("Buscar", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if do_search and query:
        with st.spinner("Buscando..."):
            mapping = {"Documentos":"document","Imágenes":"image","Videos":"video","Audio":"audio","Otros":"other"}
            ftype = mapping.get(file_type) if file_type != 'Todos' else None
            try:
                results = api.search_files(query, ftype)
                files = results.get('files', []) if results else []
                nodes_available = {n['node_id']: n for n in results.get('nodes_available', [])}
                if files:
                    st.markdown('<div class="panel">', unsafe_allow_html=True)
                    st.markdown(f"**Resultados:** {len(files)} archivos")
                    # Build table HTML
                    rows = []
                    for f in files:
                        node = nodes_available.get(f['node_id'], {'name':'Desconocido','status':'unknown'})
                        badge_class = 'online' if node.get('status')=='online' else 'offline'
                        size_str = _format_size(f.get('size',0))
                        rows.append(f"<tr><td>{f['name']}</td><td>{f['type'].capitalize()}</td><td>{size_str}</td><td><span class='badge {badge_class}'>{node.get('status','?')}</span></td><td>{node.get('name','?')}</td><td><button class='download-btn' onClick=\"window.location.href='?tab=Buscar&dl={f['file_id']}'\">Descargar</button></td></tr>")
                    table_html = """<table class='result-table'><thead><tr><th>Nombre</th><th>Tipo</th><th>Tamaño</th><th>Estado</th><th>Nodo</th><th></th></tr></thead><tbody>{}</tbody></table>""".format(''.join(rows))
                    st.markdown(table_html, unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                else:
                    st.info("Sin resultados.")
            except Exception as e:
                st.error(f"Error en la búsqueda: {e}")

    # Descargar si param dl presente
    if 'dl' in st.query_params:
        file_id = st.query_params['dl'] if isinstance(st.query_params['dl'], str) else st.query_params['dl'][0]
        with st.spinner("Generando enlace de descarga..."):
            try:
                url = api.get_download_url(file_id)
                if url:
                    st.success("Enlace listo:")
                    st.markdown(f"<a class='download-btn' href='{url}' target='_blank'>Descargar ahora</a>", unsafe_allow_html=True)
            except Exception as e:
                st.error(f"No se pudo obtener enlace: {e}")

elif ss.active_tab == 'Nodos':
    nodes = fetch_nodes()
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown("### 🖧 Nodos Conectados")
    if nodes:
        online = sum(1 for n in nodes if n.get('status')=='online')
        total_files = sum(n.get('shared_files_count',0) for n in nodes)
        mc1, mc2, _ = st.columns([1,1,6])
        mc1.metric("Nodos activos", f"{online}/{len(nodes)}")
        mc2.metric("Archivos compartidos", total_files)
        # Table of nodes
        rows = []
        for n in nodes:
            badge = 'online' if n.get('status')=='online' else 'offline'
            rows.append(f"<tr><td>{n['name']}</td><td><span class='badge {badge}'>{n['status']}</span></td><td>{n.get('shared_files_count',0)}</td></tr>")
        st.markdown("<table class='result-table'><thead><tr><th>Nombre</th><th>Estado</th><th>Archivos</th></tr></thead><tbody>{}</tbody></table>".format(''.join(rows)), unsafe_allow_html=True)
    else:
        st.info("No hay nodos registrados.")
    st.markdown('</div>', unsafe_allow_html=True)

elif ss.active_tab == 'Central':
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown("### 🗂️ Modo Centralizado")
    folder = st.text_input("Carpeta central (vacío = por defecto)", value=ss.get('central_folder',''))
    auto = st.checkbox("Escanear al abrir pestaña", value=ss.get('auto_scan', True))
    trigger = st.button("Escanear ahora") or (auto and ss.get('last_central_scan_done') is None)
    if trigger:
        with st.spinner("Escaneando e indexando..."):
            try:
                r = api.central_scan(folder or None)
                st.success(f"Indexados: {r.get('indexed_files')} | Carpeta: {r.get('folder')}")
                ss.last_central_scan_done = True
            except Exception as e:
                st.error(f"Error: {e}")
    st.markdown('</div>', unsafe_allow_html=True)

elif ss.active_tab == 'Estadísticas':
    stats = fetch_stats()
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown("### 📊 Estadísticas del Índice")
    if stats:
        colm = st.columns(4)
        colm[0].metric("Total archivos", stats.get('total_files',0))
        colm[1].metric("Nodos", stats.get('total_nodes',0))
        colm[2].metric("Activos", stats.get('active_nodes',0))
        colm[3].metric("Duplicados", stats.get('duplicates_count',0))
        # Distribution
        if stats.get('files_by_type'):
            dist_df = pd.DataFrame({
                'Tipo': list(stats['files_by_type'].keys()),
                'Cantidad': list(stats['files_by_type'].values())
            }).sort_values('Cantidad', ascending=False)
            st.bar_chart(dist_df.set_index('Tipo'))
    else:
        st.info("Sin datos de estadísticas.")
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("<br><center style='opacity:.35;font-size:.6rem;'>DistriSearch © 2025 • Build UI Modern</center>", unsafe_allow_html=True)

