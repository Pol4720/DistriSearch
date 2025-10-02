import streamlit as st
import pandas as pd
import os
from utils.api_client import ApiClient
from components.styles import inject_css

st.set_page_config(page_title="DistriSearch", page_icon="�", layout="wide")

# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def _format_size(size_bytes: int) -> str:
    for unit in ['B','KB','MB','GB','TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"

@st.cache_resource
def api_client():
    url = os.getenv("DISTRISEARCH_BACKEND_URL") or "http://localhost:8000"
    try:
        url = st.secrets.get("backend_url", url)  # type: ignore
    except Exception:
        pass
    return ApiClient(url)

api = api_client()
inject_css()

ss = st.session_state
ss.setdefault('theme', 'dark')
ss.setdefault('ui_mode', 'Distribuido')
ss.setdefault('last_central_scan', None)

# Theme toggle
top_left, top_mid, top_right = st.columns([1,6,1])
with top_left:
    logo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'assets', 'logo.png'))
    if os.path.isfile(logo_path):
        st.image(logo_path, width=72)
with top_mid:
    st.markdown("## DistriSearch")
    st.caption("Búsqueda distribuida y modo centralizado")
with top_right:
    if st.button('🌗 Tema'):
        ss.theme = 'light' if ss.theme == 'dark' else 'dark'
    st.markdown(f'<script>document.body.classList.{"add" if ss.theme=="light" else "remove"}("light-mode");</script>', unsafe_allow_html=True)

mode_col1, mode_col2 = st.columns([2,8])
with mode_col1:
    ss.ui_mode = st.radio("Modo", ["Distribuido","Centralizado"], horizontal=True, index=["Distribuido","Centralizado"].index(ss.ui_mode))
with mode_col2:
    st.write("")

tabs = st.tabs(["Buscar","Nodos","Central","Estadísticas"])

# ---------------------------- TAB: Buscar -----------------------------------
with tabs[0]:
    query_col, type_col, btn_col = st.columns([5,2,1])
    query = query_col.text_input("Consulta", placeholder="Nombre, término o contenido...")
    tipo = type_col.selectbox("Tipo", ["Todos","Documentos","Imágenes","Videos","Audio","Otros"], index=0)
    buscar = btn_col.button("Buscar")

    if buscar and query:
        mapping = {"Documentos":"document","Imágenes":"image","Videos":"video","Audio":"audio","Otros":"other"}
        tipo_api = mapping.get(tipo) if tipo != 'Todos' else None
        with st.spinner("Buscando..."):
            try:
                result = api.search_files(query, tipo_api)
            except Exception as e:
                st.error(f"Error al buscar: {e}")
                result = None
        if result and result.get('files'):
            files = result['files']
            nodes_map = {n['node_id']: n for n in result.get('nodes_available', [])}
            st.success(f"{len(files)} resultados")
            # Build dataframe for display
            rows = []
            for f in files:
                node = nodes_map.get(f['node_id'], {'name':'?','status':'unknown'})
                rows.append({
                    'Nombre': f['name'],
                    'Tipo': f['type'],
                    'Tamaño': _format_size(f.get('size',0)),
                    'Nodo': node.get('name'),
                    'Estado': node.get('status'),
                    'ID': f['file_id']
                })
            df = pd.DataFrame(rows)
            st.dataframe(df[['Nombre','Tipo','Tamaño','Nodo','Estado']], hide_index=True, use_container_width=True)

            sel = st.selectbox("Selecciona archivo", options=df['Nombre'])
            if st.button("Obtener enlace de descarga"):
                fid = df[df['Nombre']==sel]['ID'].iloc[0]
                with st.spinner("Generando enlace..."):
                    try:
                        url = api.get_download_url(fid)
                        if url:
                            st.markdown(f"<a class='download-btn' href='{url}' target='_blank'>Descargar {sel}</a>", unsafe_allow_html=True)
                    except Exception as e:
                        st.error(f"Error obteniendo enlace: {e}")
        else:
            if buscar:
                st.info("Sin resultados")

# ---------------------------- TAB: Nodos ------------------------------------
with tabs[1]:
    try:
        nodes = api.get_nodes()
    except Exception:
        nodes = []
    st.markdown("### Nodos")
    if nodes:
        online = sum(1 for n in nodes if n.get('status')=='online')
        total = len(nodes)
        files_total = sum(n.get('shared_files_count',0) for n in nodes)
        m1,m2,m3 = st.columns(3)
        m1.metric("Activos", f"{online}/{total}")
        m2.metric("Archivos", files_total)
        m3.metric("Modo actual", ss.ui_mode)
        ndf = pd.DataFrame([{
            'Nombre': n['name'],
            'Estado': n['status'],
            'Archivos': n.get('shared_files_count',0),
            'IP': n['ip_address'],
            'Puerto': n['port']
        } for n in nodes])
        st.dataframe(ndf, hide_index=True, use_container_width=True)
    else:
        st.info("No hay nodos registrados")

# ---------------------------- TAB: Central ----------------------------------
with tabs[2]:
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
with tabs[3]:
    st.markdown("### Estadísticas")
    try:
        stats = api.get_stats()
    except Exception as e:
        st.error(f"No se pudieron obtener estadísticas: {e}")
        stats = {}
    if stats:
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Archivos", stats.get('total_files',0))
        c2.metric("Nodos", stats.get('total_nodes',0))
        c3.metric("Activos", stats.get('active_nodes',0))
        c4.metric("Duplicados", stats.get('duplicates_count',0))
        if stats.get('files_by_type'):
            dist_df = pd.DataFrame({
                'Tipo': list(stats['files_by_type'].keys()),
                'Cantidad': list(stats['files_by_type'].values())
            })
            st.bar_chart(dist_df.set_index('Tipo'))
    else:
        st.info("Sin datos de estadísticas")

st.markdown("<br><center style='opacity:.35;font-size:.6rem;'>DistriSearch © 2025</center>", unsafe_allow_html=True)

