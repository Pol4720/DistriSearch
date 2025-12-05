"""
Página para subir archivos al sistema distribuido
"""
import streamlit as st
from utils.helpers import setup_page_config, init_session_state, get_api_client, require_auth, format_size
from components.styles import apply_theme, get_animated_header
import io

# Page config
setup_page_config("Subir Archivos", "📤", "wide")

# Initialize
init_session_state()
require_auth()
api = get_api_client()

# Apply theme
apply_theme(st.session_state.theme)

# Header
st.markdown(get_animated_header("📤 Subir Archivos", "Agrega contenido al sistema distribuido"), unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Info panel
st.markdown("""
<div class="glass-panel" style="padding: 1.5rem; margin-bottom: 2rem;">
    <h3 style="margin: 0 0 1rem 0;">📋 Tipos de archivo soportados</h3>
    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem;">
        <div>
            <h4 style="color: var(--primary); margin: 0.5rem 0;">📄 Documentos</h4>
            <p style="margin: 0; color: var(--text-secondary); font-size: 0.9rem;">
                TXT, PDF, DOC, DOCX, JSON, XML, MD, CSV
            </p>
        </div>
        <div>
            <h4 style="color: var(--primary); margin: 0.5rem 0;">🖼️ Imágenes</h4>
            <p style="margin: 0; color: var(--text-secondary); font-size: 0.9rem;">
                JPG, PNG, GIF, SVG, WebP
            </p>
        </div>
        <div>
            <h4 style="color: var(--primary); margin: 0.5rem 0;">🎬 Videos</h4>
            <p style="margin: 0; color: var(--text-secondary); font-size: 0.9rem;">
                MP4, AVI, MKV, MOV, WebM
            </p>
        </div>
        <div>
            <h4 style="color: var(--primary); margin: 0.5rem 0;">🎵 Audio</h4>
            <p style="margin: 0; color: var(--text-secondary); font-size: 0.9rem;">
                MP3, WAV, FLAC, OGG, M4A
            </p>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Tabs for different upload modes
tab1, tab2, tab3 = st.tabs(["📁 Archivo Individual", "📦 Múltiples Archivos", "📝 Crear Documento"])

# TAB 1: Single File Upload
with tab1:
    st.markdown("### Subir Archivo Individual")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        uploaded_file = st.file_uploader(
            "Selecciona un archivo",
            type=None,
            help="Arrastra y suelta un archivo o haz clic para seleccionar",
            key="single_file_upload"
        )
    
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Nodo de destino
        try:
            nodes = api.get_nodes()
            node_options = {n['name']: n['node_id'] for n in nodes if n.get('status') == 'online'}
            
            if not node_options:
                st.warning("⚠️ No hay nodos online")
                target_node = api.local_node_id  # Usar nodo local
            else:
                selected_node = st.selectbox(
                    "Nodo destino",
                    options=list(node_options.keys()),
                    index=0,
                    key="target_node_single"
                )
                target_node = node_options[selected_node]
        except:
            target_node = api.local_node_id  # Usar nodo local
    
    if uploaded_file:
        # Show file info
        st.markdown(f"""
        <div class="glass-panel" style="padding: 1rem; margin: 1rem 0;">
            <h4 style="margin: 0 0 0.5rem 0;">📄 Información del archivo</h4>
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.5rem;">
                <div><strong>Nombre:</strong> {uploaded_file.name}</div>
                <div><strong>Tamaño:</strong> {format_size(uploaded_file.size)}</div>
                <div><strong>Tipo:</strong> {uploaded_file.type or 'Desconocido'}</div>
                <div><strong>Nodo:</strong> {target_node}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 2])
        with col_btn2:
            if st.button("📤 Subir Archivo", use_container_width=True, type="primary", key="upload_single_btn"):
                with st.spinner("⏳ Subiendo archivo..."):
                    try:
                        # Read file content
                        file_content = uploaded_file.read()
                        
                        # Upload
                        result = api.upload_file(file_content, uploaded_file.name, target_node)
                        
                        st.success(f"✅ Archivo **{result['filename']}** subido correctamente")
                        st.balloons()
                        
                        # Show details
                        with st.expander("📊 Detalles de la carga"):
                            st.json(result)
                        
                        # Reset uploader
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ Error: {e}")

# TAB 2: Multiple Files Upload
with tab2:
    st.markdown("### Subir Múltiples Archivos")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        uploaded_files = st.file_uploader(
            "Selecciona varios archivos",
            type=None,
            accept_multiple_files=True,
            help="Puedes seleccionar múltiples archivos a la vez",
            key="multiple_files_upload"
        )
    
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        
        try:
            nodes = api.get_nodes()
            node_options = {n['name']: n['node_id'] for n in nodes if n.get('status') == 'online'}
            
            if not node_options:
                target_node_multi = api.local_node_id  # Usar nodo local
            else:
                selected_node_multi = st.selectbox(
                    "Nodo destino",
                    options=list(node_options.keys()),
                    index=0,
                    key="target_node_multi"
                )
                target_node_multi = node_options[selected_node_multi]
        except:
            target_node_multi = api.local_node_id  # Usar nodo local
    
    if uploaded_files:
        total_size = sum(f.size for f in uploaded_files)
        
        st.markdown(f"""
        <div class="glass-panel" style="padding: 1rem; margin: 1rem 0;">
            <h4 style="margin: 0 0 0.5rem 0;">📦 Resumen de carga</h4>
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem;">
                <div><strong>Archivos:</strong> {len(uploaded_files)}</div>
                <div><strong>Tamaño total:</strong> {format_size(total_size)}</div>
                <div><strong>Nodo:</strong> {target_node_multi}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # List files
        with st.expander("📋 Ver lista de archivos"):
            for idx, file in enumerate(uploaded_files, 1):
                st.markdown(f"{idx}. **{file.name}** ({format_size(file.size)})")
        
        col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 2])
        with col_btn2:
            if st.button("📤 Subir Todos", use_container_width=True, type="primary", key="upload_multi_btn"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                try:
                    # Prepare files data
                    files_data = []
                    for idx, file in enumerate(uploaded_files):
                        status_text.text(f"Preparando {file.name}...")
                        files_data.append((file.name, file.read()))
                        progress_bar.progress((idx + 1) / len(uploaded_files))
                    
                    # Upload all
                    status_text.text("Subiendo archivos al servidor...")
                    result = api.upload_multiple_files(files_data, target_node_multi)
                    
                    progress_bar.progress(1.0)
                    status_text.empty()
                    
                    st.success(f"✅ {result['successful']}/{result['total']} archivos subidos correctamente")
                    
                    if result['failed'] > 0:
                        st.warning(f"⚠️ {result['failed']} archivos fallaron")
                    
                    st.balloons()
                    
                    # Show details
                    with st.expander("📊 Detalles de la carga"):
                        st.json(result)
                    
                except Exception as e:
                    st.error(f"❌ Error: {e}")
                finally:
                    progress_bar.empty()

# TAB 3: Create Document
with tab3:
    st.markdown("### Crear Documento de Texto")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        doc_filename = st.text_input(
            "Nombre del archivo",
            placeholder="mi_documento.txt",
            key="doc_filename"
        )
        
        doc_content = st.text_area(
            "Contenido del documento",
            placeholder="Escribe el contenido aquí...",
            height=300,
            key="doc_content"
        )
    
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        
        doc_format = st.selectbox(
            "Formato",
            options=["txt", "md", "json", "xml", "csv"],
            index=0,
            key="doc_format"
        )
        
        try:
            nodes = api.get_nodes()
            node_options = {n['name']: n['node_id'] for n in nodes if n.get('status') == 'online'}
            
            if not node_options:
                target_node_doc = api.local_node_id  # Usar nodo local
            else:
                selected_node_doc = st.selectbox(
                    "Nodo destino",
                    options=list(node_options.keys()),
                    index=0,
                    key="target_node_doc"
                )
                target_node_doc = node_options[selected_node_doc]
        except:
            target_node_doc = api.local_node_id  # Usar nodo local
    
    col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 2])
    with col_btn2:
        if st.button("💾 Guardar Documento", use_container_width=True, type="primary", key="create_doc_btn"):
            if not doc_filename:
                st.error("⚠️ Ingresa un nombre para el archivo")
            elif not doc_content:
                st.error("⚠️ El contenido no puede estar vacío")
            else:
                try:
                    # Ensure correct extension
                    if not doc_filename.endswith(f".{doc_format}"):
                        doc_filename = f"{doc_filename}.{doc_format}"
                    
                    # Create file
                    file_content = doc_content.encode('utf-8')
                    
                    with st.spinner("💾 Guardando documento..."):
                        result = api.upload_file(file_content, doc_filename, target_node_doc)
                        
                        st.success(f"✅ Documento **{result['filename']}** creado correctamente")
                        st.balloons()
                        
                        with st.expander("📊 Detalles"):
                            st.json(result)
                        
                except Exception as e:
                    st.error(f"❌ Error: {e}")

# Footer with stats
st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown("""
<div class="glass-panel" style="padding: 1rem; text-align: center;">
    <p style="margin: 0; color: var(--text-secondary);">
        💡 Los archivos se indexan automáticamente para búsqueda distribuida
    </p>
</div>
""", unsafe_allow_html=True)