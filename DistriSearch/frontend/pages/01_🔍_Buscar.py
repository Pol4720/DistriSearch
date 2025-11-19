"""
Página de búsqueda de archivos distribuida
Con interfaz moderna y componentes personalizados
"""
import streamlit as st
import pandas as pd
from utils.helpers import setup_page_config, init_session_state, get_api_client, format_size, require_auth
from components.styles import apply_theme, get_animated_header

# Page config with expanded sidebar
setup_page_config("Buscar Archivos", "🔍", "wide", "expanded")

# Initialize
init_session_state()
require_auth()
api = get_api_client()

# Apply modern theme
apply_theme(st.session_state.theme)

# Animated header
st.markdown(get_animated_header("🔍 Buscar Archivos", "Encuentra lo que necesitas en segundos"), unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Search interface with improved contrast
col1, col2, col3 = st.columns([5, 2, 2])

with col1:
    query = st.text_input(
        "¿Qué estás buscando?",
        placeholder="Escribe el nombre del archivo o contenido...",
        label_visibility="visible",
        key="search_query",
        help="Busca archivos por nombre, extensión o contenido"
    )

with col2:
    tipo = st.selectbox(
        "Tipo de archivo",
        ["Todos", "Documentos", "Imágenes", "Videos", "Audio", "Otros"],
        index=0,
        key="file_type_filter"
    )

with col3:
    show_score = st.toggle(
        "Mostrar score BM25",
        value=False,
        help="Muestra la puntuación de relevancia de cada resultado"
    )

# Search button
col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 2])
with col_btn2:
    buscar = st.button("🔍 Buscar", use_container_width=True, type="primary")

st.markdown("---")

# Execute search
if buscar and query:
    mapping = {
        "Documentos": "document",
        "Imágenes": "image",
        "Videos": "video",
        "Audio": "audio",
        "Otros": "other"
    }
    tipo_api = mapping.get(tipo) if tipo != 'Todos' else None
    
    with st.spinner("🔍 Buscando en los nodos..."):
        try:
            if show_score:
                result = api.search_files_with_score(query, tipo_api)
            else:
                result = api.search_files(query, tipo_api)
            
            st.session_state.search_results = result
            files = result.get('files', [])
            nodes_map = {n['node_id']: n for n in result.get('nodes_available', [])}
            st.session_state.nodes_map = nodes_map
            
            # Process results
            rows = []
            for f in files:
                node = nodes_map.get(f['node_id'], {'name': '?', 'status': 'unknown'})
                row = {
                    'Nombre': f['name'],
                    'Tipo': f['type'],
                    'Tamaño': format_size(f.get('size', 0)),
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
            
            st.session_state.search_df = pd.DataFrame(rows) if rows else pd.DataFrame()
            
        except Exception as e:
            st.error(f"❌ Error al buscar: {e}")
            st.session_state.search_results = None
            st.session_state.search_df = None

# Display results
if st.session_state.search_df is not None and not st.session_state.search_df.empty:
    df = st.session_state.search_df
    
    # Success message with count
    st.success(f"✅ Se encontraron **{len(df)}** resultados")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Display results using custom cards
    for idx, row in df.iterrows():
        # Get download URL
        import os
        from urllib.parse import urlparse
        
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
        
        download_url = f"{public_base}/download/file/{row['ID']}"
        
        # Modern glassmorphism file card
        score_html = f"<div style='color: var(--warning-color); font-weight: 600; margin-top: 0.5rem;'>⭐ Score: {row.get('Score', 'N/A')}</div>" if row.get('Score') else ''
        
        st.markdown(f"""
        <div class="glass-effect hover-lift" style="
            padding: 1.5rem;
            border-radius: 1rem;
            margin-bottom: 1rem;
            transition: all 0.3s ease;
        ">
            <div style="display: flex; align-items: center; margin-bottom: 1rem;">
                <div style="font-size: 2rem; margin-right: 1rem;">📄</div>
                <h3 style="color: var(--text-primary); margin: 0; font-weight: 700;">{row['Nombre']}</h3>
            </div>
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.5rem; color: var(--text-secondary);">
                <div><strong>Tipo:</strong> {row['Tipo']}</div>
                <div><strong>Tamaño:</strong> {row['Tamaño']}</div>
                <div><strong>Nodo:</strong> {row['Nodo']}</div>
                <div><strong>Estado:</strong> {row['Estado']}</div>
            </div>
            {score_html}
        </div>
        """, unsafe_allow_html=True)
        
        col_download, col_space = st.columns([1, 4])
        with col_download:
            st.link_button("⬇️ Descargar", download_url, use_container_width=True)
    
    # Alternative: DataTable view
    st.markdown("<br><br>", unsafe_allow_html=True)
    with st.expander("📊 Ver como tabla"):
        base_cols = ['Nombre', 'Tipo', 'Tamaño', 'Nodo', 'Estado']
        if show_score and 'Score' in df.columns:
            base_cols.append('Score')
        render_df = df[base_cols].copy()
        st.dataframe(render_df, hide_index=True, use_container_width=True)

elif st.session_state.search_df is not None and st.session_state.search_df.empty:
    st.info("🔍 No se encontraron resultados. Intenta con otros términos de búsqueda")
else:
    st.info("🔎 Ingresa una consulta y presiona Buscar. El sistema buscará en todos los nodos activos")

# Footer with tips
st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown("""
<div class="glass-panel" style="padding: 1rem;">
    <h4 style="margin: 0 0 0.5rem 0;">💡 Tips de búsqueda:</h4>
    <ul style="margin: 0; padding-left: 1.5rem; line-height: 1.8;">
        <li>Usa <strong>palabras clave específicas</strong> para mejores resultados</li>
        <li>El algoritmo <strong>BM25</strong> rankea los resultados por relevancia</li>
        <li>Puedes filtrar por <strong>tipo de archivo</strong> para búsquedas más rápidas</li>
        <li>El <strong>score</strong> indica qué tan relevante es cada resultado (mayor = más relevante)</li>
    </ul>
</div>
""", unsafe_allow_html=True)
