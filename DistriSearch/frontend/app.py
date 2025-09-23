import streamlit as st
import requests
import pandas as pd
import time
from utils.api_client import ApiClient
import os

# Función para formatear tamaño de archivo
def _format_size(size_bytes):
    """Convierte bytes a formato legible (KB, MB, GB)"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"

# Configuración de la página
st.set_page_config(
    page_title="DistriSearch",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicializar el cliente API
@st.cache_resource
def get_api_client():
    # Resolver URL del backend de forma segura:
    # 1) variable de entorno DISTRISEARCH_BACKEND_URL
    # 2) st.secrets['backend_url'] si existe
    # 3) valor por defecto
    backend_url = os.getenv("DISTRISEARCH_BACKEND_URL") or "http://localhost:8000"
    try:
        # Puede lanzar si no hay secrets; se ignora y se usa el valor actual
        backend_url = st.secrets.get("backend_url", backend_url)
    except Exception:
        pass
    return ApiClient(backend_url)

api_client = get_api_client()

# Título y descripción
st.title("🔍 DistriSearch")
st.markdown("""
Busca archivos compartidos en una red distribuida de nodos.
""")

# Barra lateral con estado del sistema
with st.sidebar:
    st.header("Estado del Sistema")
    
    # Sección de nodos
    st.subheader("Nodos Conectados")
    
    # Botón para refrescar estado
    if st.button("Refrescar Estado"):
        st.cache_resource.clear()
    
    # Mostrar nodos
    try:
        nodes = api_client.get_nodes()
        
        # Convertir a DataFrame para mejor visualización
        nodes_df = pd.DataFrame(nodes)
        
        if not nodes_df.empty:
            # Contar nodos online/offline
            online_count = nodes_df[nodes_df['status'] == 'online'].shape[0]
            total_count = nodes_df.shape[0]
            
            # Mostrar métricas
            col1, col2 = st.columns(2)
            col1.metric("Nodos Activos", f"{online_count}/{total_count}")
            
            # Calcular archivos totales
            total_files = nodes_df['shared_files_count'].sum()
            col2.metric("Archivos Compartidos", total_files)
            
            # Tabla de nodos
            st.dataframe(
                nodes_df[['name', 'status', 'shared_files_count']].rename(
                    columns={
                        'name': 'Nombre',
                        'status': 'Estado',
                        'shared_files_count': 'Archivos'
                    }
                ),
                hide_index=True
            )
        else:
            st.info("No hay nodos conectados")
    
    except Exception as e:
        st.error(f"Error al obtener estado de nodos: {str(e)}")
    
    # Estadísticas del sistema
    st.subheader("Estadísticas")
    try:
        stats = api_client.get_stats()
        
        st.metric("Total Archivos", stats.get('total_files', 0))
        st.metric("Archivos Duplicados", stats.get('duplicates_count', 0))
        
        # Mostrar distribución por tipo
        if 'files_by_type' in stats and stats['files_by_type']:
            st.write("Distribución por tipo:")
            
            # Crear gráfico de barras
            types_df = pd.DataFrame({
                'Tipo': list(stats['files_by_type'].keys()),
                'Cantidad': list(stats['files_by_type'].values())
            })
            
            st.bar_chart(types_df.set_index('Tipo'))
    
    except Exception as e:
        st.error(f"Error al obtener estadísticas: {str(e)}")

# Formulario de búsqueda
with st.form(key='search_form'):
    col1, col2 = st.columns([3, 1])
    
    with col1:
        query = st.text_input("Buscar archivos", placeholder="Nombre de archivo...")
    
    with col2:
        file_type = st.selectbox(
            "Tipo",
            options=[
                "Todos", "Documentos", "Imágenes", 
                "Videos", "Audio", "Otros"
            ]
        )
    
    submit_button = st.form_submit_button(label='Buscar')

# Procesar búsqueda
if submit_button and query:
    with st.spinner('Buscando archivos...'):
        # Mapear tipos a valores esperados por la API
        type_mapping = {
            "Documentos": "document",
            "Imágenes": "image",
            "Videos": "video",
            "Audio": "audio",
            "Otros": "other"
        }
        
        # Enviar tipo solo si no es "Todos"
        file_type_param = type_mapping.get(file_type) if file_type != "Todos" else None
        
        try:
            results = api_client.search_files(query, file_type_param)
            
            if results and results.get('files'):
                st.success(f"Se encontraron {len(results['files'])} resultados")
                
                # Preparar datos para tabla
                files_data = []
                for file in results['files']:
                    # Buscar nodo asociado
                    node = next(
                        (n for n in results['nodes_available'] if n['node_id'] == file['node_id']),
                        {'name': 'Desconocido', 'status': 'unknown'}
                    )
                    
                    # Convertir tamaño a formato legible
                    size_str = _format_size(file.get('size', 0))
                    
                    files_data.append({
                        'ID': file['file_id'][:8] + '...',
                        'Nombre': file['name'],
                        'Tipo': file['type'].capitalize(),
                        'Tamaño': size_str,
                        'Nodo': node['name'],
                        'Estado': node['status'],
                        'Descargar': file['file_id']
                    })
                
                # Crear DataFrame
                df = pd.DataFrame(files_data)
                
                # Mostrar tabla de resultados con links de descarga
                table = st.dataframe(
                    df.drop(columns=['ID', 'Descargar']),
                    hide_index=True
                )
                
                # Sección de descarga
                st.subheader("Descargar archivo")
                
                # Selector de archivos
                selected_file = st.selectbox(
                    "Seleccione un archivo para descargar",
                    options=df['Nombre'].tolist(),
                    format_func=lambda x: x
                )
                
                if selected_file:
                    # Obtener ID del archivo seleccionado
                    file_id = df.loc[df['Nombre'] == selected_file, 'Descargar'].iloc[0]
                    
                    # Botón de descarga
                    if st.button(f"Descargar {selected_file}"):
                        with st.spinner("Obteniendo enlace de descarga..."):
                            download_url = api_client.get_download_url(file_id)
                            
                            if download_url:
                                # Crear link de descarga
                                st.markdown(f"[Descargar archivo]({download_url})")
        except Exception as e:
            st.error(f"Error al buscar archivos: {str(e)}")
# Nota: _format_size se movió arriba para que esté definido antes de su uso.

# Función para formatear tamaño de archivo
def _format_size(size_bytes):
    """Convierte bytes a formato legible (KB, MB, GB)"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"
