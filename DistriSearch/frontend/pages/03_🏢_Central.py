"""
Página del panel central
Gestión del repositorio centralizado
"""
import streamlit as st
from utils.helpers import setup_page_config, init_session_state, get_api_client
from components.styles import inject_modern_css, get_animated_header
from components.cards import info_card, empty_state

# Page config
setup_page_config("Panel Central", "🏢", "wide")

# Initialize
init_session_state()
api = get_api_client()

# Inject styles
inject_modern_css(st.session_state.theme)

# Header
st.markdown(get_animated_header("🏢 Panel Central", "Gestiona el repositorio centralizado"), unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Mode indicator
mode_class = "online" if st.session_state.ui_mode == "Centralizado" else "offline"
st.markdown(f"""
<div class="glass-panel" style="padding: 1.5rem; margin-bottom: 2rem;">
    <div style="display: flex; align-items: center; gap: 1rem;">
        <div class="status-badge {mode_class}" style="font-size: 1rem; padding: 0.5rem 1.5rem;">
            MODO {st.session_state.ui_mode.upper()}
        </div>
        <div style="flex: 1;">
            <p style="margin: 0; font-size: 0.95rem; opacity: 0.9;">
                {'✅ El sistema está operando en modo centralizado. Los archivos se indexan desde una carpeta central.' if st.session_state.ui_mode == 'Centralizado' else '⚠️ Actualmente en modo distribuido. Cambia el modo en el sidebar para usar el repositorio central.'}
            </p>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

if st.session_state.ui_mode == "Centralizado":
    # Central mode interface
    st.markdown("### 📁 Escanear Repositorio Central")
    
    info_card(
        "ℹ️ Información",
        "El modo centralizado indexa archivos desde una carpeta específica en el servidor. "
        "Todos los archivos en esa carpeta serán indexados y estarán disponibles para búsqueda.",
        "ℹ️",
        "#3b82f6"
    )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Configuration
    col1, col2 = st.columns([3, 1])
    
    with col1:
        folder = st.text_input(
            "📂 Carpeta del repositorio central",
            value=st.session_state.get('central_folder', ''),
            placeholder="Dejar vacío para usar la carpeta por defecto",
            help="Ruta absoluta a la carpeta que contiene los archivos a indexar"
        )
    
    with col2:
        auto_scan = st.checkbox(
            "🔄 Auto-escanear",
            value=True,
            help="Escanear automáticamente si no hay registro previo"
        )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Scan button
    col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 2])
    with col_btn2:
        scan_now = st.button("🔍 Escanear Ahora", use_container_width=True, type="primary")
    
    # Execute scan
    should_scan = scan_now or (auto_scan and st.session_state.last_central_scan is None)
    
    if should_scan:
        with st.spinner("🔍 Escaneando carpeta central..."):
            try:
                result = api.central_scan(folder or None)
                st.session_state.last_central_scan = result.get('indexed_files')
                st.session_state.central_folder = folder
                
                st.success(f"""
                ✅ **Escaneo completado exitosamente**
                
                - **Archivos indexados:** {result.get('indexed_files', 0)}
                - **Carpeta:** `{result.get('folder', 'N/A')}`
                """)
                
                st.balloons()
                
            except Exception as e:
                st.error(f"❌ Error al escanear: {e}")
    
    # Last scan info
    if st.session_state.last_central_scan is not None:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown(f"""
        <div class="glass-panel" style="padding: 1.5rem;">
            <h4 style="margin: 0 0 1rem 0;">📊 Último Escaneo</h4>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem;">
                <div>
                    <div style="color: var(--text-secondary); font-size: 0.85rem; margin-bottom: 0.25rem;">Archivos Indexados</div>
                    <div style="color: #667eea; font-weight: 700; font-size: 1.8rem;">{st.session_state.last_central_scan}</div>
                </div>
                <div>
                    <div style="color: var(--text-secondary); font-size: 0.85rem; margin-bottom: 0.25rem;">Carpeta Configurada</div>
                    <div style="color: var(--text-primary); font-weight: 600; font-size: 1rem; font-family: monospace;">
                        {st.session_state.get('central_folder') or 'Por defecto'}
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Tips
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("""
    <div class="glass-panel" style="padding: 1.5rem;">
        <h4 style="margin: 0 0 1rem 0;">💡 Consejos para el Modo Central</h4>
        <ul style="margin: 0; padding-left: 1.5rem; line-height: 1.8;">
            <li><strong>Estructura organizada:</strong> Mantén los archivos organizados en subcarpetas por categoría</li>
            <li><strong>Re-escanear:</strong> Ejecuta un escaneo después de agregar nuevos archivos a la carpeta</li>
            <li><strong>Rendimiento:</strong> El modo central es más rápido para carpetas con muchos archivos</li>
            <li><strong>Backup:</strong> Asegúrate de tener respaldos de la carpeta central</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

else:
    # Distributed mode message
    empty_state(
        "Panel Central no disponible en modo distribuido",
        "🏢",
        "Cambia al modo 'Centralizado' en el sidebar para acceder a esta funcionalidad"
    )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    info_card(
        "🌐 Modo Distribuido Activo",
        "Actualmente el sistema está operando en modo distribuido. "
        "En este modo, cada nodo mantiene su propio repositorio de archivos. "
        "Para usar el repositorio central, cambia al modo 'Centralizado' en la configuración del sidebar.",
        "ℹ️",
        "#f59e0b"
    )

# Footer
st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown("""
<div style="text-align: center; opacity: 0.6; font-size: 0.85rem; padding: 2rem 0;">
    💡 El modo central es ideal para entornos con un único punto de acceso a los archivos
</div>
""", unsafe_allow_html=True)
