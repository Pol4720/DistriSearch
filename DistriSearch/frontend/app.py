import streamlit as st
import pandas as pd
import os
import html as _html
from urllib.parse import urlparse
from utils.api_client import ApiClient
from components.styles import inject_css

st.set_page_config(page_title="DistriSearch", page_icon="🔎", layout="wide")

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
def api_client(cache_buster: str = "with_score_v1"):
    url = os.getenv("DISTRISEARCH_BACKEND_URL") or "http://localhost:8000"
    # Optional admin API key for protected management endpoints
    api_key = os.getenv("DISTRISEARCH_ADMIN_API_KEY") or os.getenv("ADMIN_API_KEY")

    # Solo intentar leer secrets si el archivo existe
    secret_candidates = [
        os.path.join("/app", ".streamlit", "secrets.toml"),
        os.path.expanduser("~/.streamlit/secrets.toml"),
    ]
    for sp in secret_candidates:
        if os.path.exists(sp):
            try:
                api_key = st.secrets.get("admin_api_key", api_key)
            except Exception:
                pass
            break

    return ApiClient(url, api_key=api_key)

api = api_client("with_score_v1")

ss = st.session_state
ss.setdefault('theme', 'dark')
ss.setdefault('ui_mode', 'Distribuido')
ss.setdefault('last_central_scan', None)
ss.setdefault('search_results', None)   # dict from API
ss.setdefault('search_df', None)        # DataFrame for display
ss.setdefault('nodes_map', {})
ss.setdefault('selected_file_id', None)
ss.setdefault('last_download_url', None)

# Inject CSS based on current theme
inject_css(theme=ss['theme'])

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
        st.rerun()

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
    query_col, type_col, btn_col, opt_col = st.columns([5,2,1,2])
    query = query_col.text_input("Consulta", placeholder="Nombre, término o contenido...")
    tipo = type_col.selectbox("Tipo", ["Todos","Documentos","Imágenes","Videos","Audio","Otros"], index=0)
    buscar = btn_col.button("Buscar")
    show_score = opt_col.toggle("Ver score", value=False, help="Muestra la puntuación de ranking (BM25)")

    # Execute search on click and persist in session
    if buscar and query:
        mapping = {"Documentos":"document","Imágenes":"image","Videos":"video","Audio":"audio","Otros":"other"}
        tipo_api = mapping.get(tipo) if tipo != 'Todos' else None
        with st.spinner("Buscando..."):
            try:
                if show_score:
                    try:
                        result = api.search_files_with_score(query, tipo_api)
                    except AttributeError:
                        # Instancia cacheada anterior a la adición del método; usar HTTP directo
                        import requests as _rq
                        params = {"q": query, "max_results": 50, "include_score": "true"}
                        if tipo_api:
                            params["file_type"] = tipo_api
                        r = _rq.get(f"{api.base_url}/search/", params=params, headers=api.headers or None)
                        r.raise_for_status()
                        result = r.json()
                else:
                    result = api.search_files(query, tipo_api)
                ss.search_results = result
                files = result.get('files', [])
                nodes_map = {n['node_id']: n for n in result.get('nodes_available', [])}
                ss.nodes_map = nodes_map
                rows = []
                for f in files:
                    node = nodes_map.get(f['node_id'], {'name':'?','status':'unknown'})
                    row = {
                        'Nombre': f['name'],
                        'Tipo': f['type'],
                        'Tamaño': _format_size(f.get('size',0)),
                        'Nodo': node.get('name'),
                        'Estado': node.get('status'),
                        'ID': f['file_id']
                    }
                    if show_score and f.get('score') is not None:
                        try:
                            row['Score'] = round(float(f['score']), 4)
                        except Exception:
                            row['Score'] = f['score']
                    rows.append(row)
                ss.search_df = pd.DataFrame(rows) if rows else pd.DataFrame()
                ss.selected_file_id = None
                ss.last_download_url = None
            except Exception as e:
                st.error(f"Error al buscar: {e}")
                ss.search_results = None
                ss.search_df = None

    # Render from persisted state
    if ss.search_df is not None and not ss.search_df.empty:
        st.success(f"{len(ss.search_df)} resultados")

        # Compute a public backend base for browser links
        public_base = os.getenv("DISTRISEARCH_BACKEND_PUBLIC_URL")
        if not public_base:
            try:
                u = urlparse(api.base_url)
                host = u.hostname or "localhost"
                port = u.port or 8000
                if host in {"backend", "backend.local", "backend.docker"}:
                    host = "localhost"
                public_base = f"{u.scheme}://{host}:{port}"
            except Exception:
                public_base = "http://localhost:8000"
        public_base = public_base.rstrip('/')

        base_cols = ['Nombre','Tipo','Tamaño','Nodo','Estado']
        if show_score and 'Score' in ss.search_df.columns:
            base_cols.append('Score')
        render_df = ss.search_df[base_cols].copy()
        render_df['Descargar'] = [f"{public_base}/download/file/{fid}" for fid in ss.search_df['ID']]

        try:
            st.dataframe(
                render_df,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Descargar": st.column_config.LinkColumn("Descargar", display_text="⬇️")
                }
            )
        except Exception:
            # Fallback if LinkColumn isn't available
            st.dataframe(render_df, hide_index=True, use_container_width=True)
    else:
        st.info("Ingresa una consulta y pulsa Buscar")

# ---------------------------- TAB: Nodos ------------------------------------
if "Nodos" in ti:
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

