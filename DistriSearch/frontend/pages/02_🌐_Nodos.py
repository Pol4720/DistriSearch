"""
Página de gestión de nodos
Registro, eliminación y monitoreo de nodos
"""
import streamlit as st
import pandas as pd
from utils.helpers import setup_page_config, init_session_state, get_api_client, normalize_status, require_auth
from components.styles import apply_theme, get_animated_header
from components.cards import node_card, empty_state, metric_card

# Page config
setup_page_config("Gestión de Nodos", "🌐", "wide")

# Initialize
init_session_state()
require_auth()
api = get_api_client()

# Apply theme
apply_theme(st.session_state.theme)

# Header
st.markdown(get_animated_header("🌐 Gestión de Nodos", "Administra la red distribuida"), unsafe_allow_html=True)

# Botón de refresco
col_refresh1, col_refresh2, col_refresh3 = st.columns([4,1,4])
with col_refresh2:
    if st.button("🔄 Refrescar Nodos", key="refresh_nodes_btn", use_container_width=True):
        st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# Get nodes
try:
    nodes = api.get_nodes()
except Exception as e:
    st.error(f"❌ Error al obtener nodos: {e}")
    nodes = []

# Summary metrics
if nodes:
    online_nodes = sum(1 for n in nodes if normalize_status(n.get('status', '')) == 'online')
    total_files = sum(n.get('shared_files_count', 0) for n in nodes)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("Nodos Totales", str(len(nodes)), icon="🖥️")
    with col2:
        metric_card("Nodos Activos", str(online_nodes), f"+{online_nodes}", icon="✅")
    with col3:
        metric_card("Archivos Compartidos", str(total_files), icon="📁")
    with col4:
        uptime_pct = (online_nodes / len(nodes) * 100) if len(nodes) > 0 else 0
        metric_card("Disponibilidad", f"{uptime_pct:.1f}%", icon="📊")
    
    st.markdown("<br>", unsafe_allow_html=True)

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["📋 Nodos Activos", "➕ Añadir Nodo", "🗑️ Eliminar Nodo", "⚙️ Configuración Avanzada"])

# Tab 1: Active Nodes
with tab1:
    st.markdown("### Nodos Registrados en el Sistema")
    
    if nodes:
        # Display nodes as cards
        cols = st.columns(2)
        for idx, node in enumerate(nodes):
            with cols[idx % 2]:
                node_card(node)
        
        # Table view
        st.markdown("<br><br>", unsafe_allow_html=True)
        with st.expander("📊 Ver como tabla"):
            ndf = pd.DataFrame([{
                'ID': n['node_id'],
                'Nombre': n['name'],
                'Estado': normalize_status(n.get('status', '')),
                'Archivos': n.get('shared_files_count', 0),
                'IP': n['ip_address'],
                'Puerto': n['port']
            } for n in nodes])
            st.dataframe(ndf, hide_index=True, use_container_width=True)
    else:
        empty_state(
            "No hay nodos registrados",
            "🌐",
            "Añade tu primer nodo en la pestaña 'Añadir Nodo'"
        )

# Tab 2: Add Node
with tab2:
    st.markdown("### Registrar Nuevo Nodo")
    
    st.markdown("""
    <div class="glass-panel" style="padding: 1.5rem; margin-bottom: 1.5rem;">
        <p style="margin: 0;">Los agentes dinámicos se auto-registran automáticamente. También puedes registrar nodos manualmente.</p>
    </div>
    """, unsafe_allow_html=True)
    
    # ✅ Registro rápido (solo verificar que existe)
    st.markdown("#### 🚀 Verificar Nodo Dinámico")
    st.info("💡 Si ya ejecutaste un agente, solo ingresa su ID para verificar que está registrado")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        quick_node_id = st.text_input(
            "ID del nodo a verificar",
            placeholder="agent_dev_01",
            key="quick_node_id",
            help="Ingresa el node_id del agente que ya iniciaste"
        )
    
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔍 Verificar", key="quick_verify", use_container_width=True, type="primary"):
            if quick_node_id:
                try:
                    existing = api.get_node(quick_node_id)
                    if existing:
                        status = existing.get('status', 'unknown')
                        st.success(f"✅ Nodo **{quick_node_id}** encontrado (Estado: {status})")
                        if status != 'online':
                            st.warning(f"⚠️ El nodo está {status}. Verifica que el agente esté corriendo.")
                        st.balloons()
                    else:
                        st.warning(f"⚠️ Nodo **{quick_node_id}** no encontrado. Asegúrate de que el agente se haya ejecutado correctamente.")
                except Exception as e:
                    st.error(f"❌ Error: {e}")
            else:
                st.warning("⚠️ Ingresa un ID de nodo")
    
    st.markdown("---")
    
    # ✅ Registro manual completo
    st.markdown("#### 📝 Registro Manual de Nodo")
    
    col1, col2 = st.columns(2)
    
    with col1:
        node_id = st.text_input(
            "🆔 ID del Nodo",
            placeholder="node_manual_01",
            key="manual_node_id",
            help="Identificador único del nodo"
        )
        node_name = st.text_input(
            "📛 Nombre del Nodo",
            placeholder="Agente Principal",
            key="manual_node_name",
            help="Nombre descriptivo del nodo"
        )
        node_ip = st.text_input(
            "🌐 IP del Nodo",
            placeholder="192.168.1.100",
            value="127.0.0.1",
            key="manual_node_ip",
            help="Dirección IP del nodo"
        )
    
    with col2:
        node_port = st.number_input(
            "🔌 Puerto",
            min_value=1,
            max_value=65535,
            value=8080,
            key="manual_node_port",
            help="Puerto del servidor del nodo"
        )
        node_status = st.selectbox(
            "📊 Estado Inicial",
            options=["online", "offline", "unknown"],
            index=0,
            key="manual_node_status"
        )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 2])
    with col_btn2:
        if st.button("✅ Registrar Nodo", use_container_width=True, type="primary", key="register_manual_btn"):
            if node_id and node_name and node_ip:
                try:
                    res = api.register_node({
                        "node_id": node_id,
                        "name": node_name,
                        "ip_address": node_ip,
                        "port": int(node_port),
                        "status": node_status,
                        "shared_files_count": 0
                    })
                    st.success(f"✅ Nodo **{res.get('node_id')}** registrado correctamente")
                    st.balloons()
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al registrar nodo: {e}")
            else:
                st.warning("⚠️ Por favor completa todos los campos obligatorios")

# Tab 3: Delete Node
with tab3:
    st.markdown("### Eliminar Nodo del Sistema")
    
    st.markdown("""
    <div class="glass-panel" style="padding: 1.5rem; margin-bottom: 1.5rem; border-left: 4px solid #ef4444;">
        <p style="margin: 0; color: #ef4444; font-weight: 600;">⚠️ Precaución</p>
        <p style="margin: 0.5rem 0 0 0;">Esta acción eliminará el nodo de la red. Opcionalmente, puedes eliminar también sus archivos del índice.</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        if nodes:
            node_options = {f"{n['name']} ({n['node_id']})": n['node_id'] for n in nodes}
            selected_node = st.selectbox(
                "Selecciona el nodo a eliminar",
                options=list(node_options.keys()),
                key="delete_node_select"
            )
            del_id = node_options[selected_node]
        else:
            st.info("No hay nodos disponibles para eliminar")
            del_id = None
    
    with col2:
        del_files = st.checkbox(
            "🗑️ Eliminar archivos del índice",
            value=True,
            key="delete_files_checkbox",
            help="Si está marcado, también se eliminarán los archivos del nodo del índice central"
        )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 2])
    with col_btn2:
        if st.button("🗑️ Eliminar Nodo", use_container_width=True, type="primary", disabled=not del_id, key="delete_node_btn"):
            if del_id:
                try:
                    res = api.delete_node(del_id, delete_files=del_files)
                    st.success(f"✅ Nodo **{res.get('node_id')}** eliminado correctamente")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al eliminar nodo: {e}")

# Tab 4: Advanced Configuration
with tab4:
    st.markdown("### Configuración Avanzada")
    
    # Replication
    with st.expander("🔄 Replicación y Tolerancia a Fallos", expanded=True):
        st.markdown("""
        <div class="glass-panel" style="padding: 1rem; margin-bottom: 1rem;">
            <p style="margin: 0;">Ejecuta sincronización de replicación para garantizar consistencia eventual.</p>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.info("💡 La replicación se ejecuta automáticamente cada 60 segundos")
        
        with col2:
            if st.button("▶️ Sincronizar Ahora", type="primary", use_container_width=True):
                try:
                    with st.spinner("🔄 Ejecutando replicación..."):
                        res = api.run_replication()
                        st.success(f"✅ Sincronización completada")
                        st.json(res)
                except Exception as e:
                    st.error(f"❌ Error: {e}")
        
        # Mostrar estado
        try:
            status = api.get_replication_status()
            st.markdown("#### Estado de Replicación")
            st.json(status)
        except:
            pass
    
    # Simulated node (local folder)
    with st.expander("🖥️ Nodo Simulado (Carpeta Local)", expanded=False):
        st.markdown("""
        <div class="glass-panel" style="padding: 1rem; margin-bottom: 1rem;">
            <p style="margin: 0;">Configura una carpeta local como nodo simulado sin necesidad de ejecutar un agente.</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("#### Paso 1: Crear nodo simulado")
        col1, col2 = st.columns([3, 1])
        with col1:
            sim_id = st.text_input("ID de nodo simulado", placeholder="node_local_1", key="sim_node_id")
            sim_name = st.text_input("Nombre", placeholder="Nodo Simulado", key="sim_node_name")
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("➕ Crear", key="create_sim_node"):
                if sim_id and sim_name:
                    try:
                        res = api.register_node({
                            "node_id": sim_id,
                            "name": sim_name,
                            "ip_address": "127.0.0.1",
                            "port": 0,
                            "status": "online",
                            "shared_files_count": 0
                        })
                        st.success(f"✅ Nodo simulado **{res.get('node_id')}** creado")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error: {e}")
        
        st.markdown("#### Paso 2: Configurar carpeta y escanear")
        mount_node = st.text_input("ID del nodo", placeholder="node_local_1", key="mount_node")
        mount_folder = st.text_input("Carpeta local", placeholder="C:/ruta/a/carpeta", key="mount_folder")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Guardar Carpeta", key="save_mount_btn"):
                if mount_node and mount_folder:
                    try:
                        res = api.set_node_mount(mount_node, mount_folder)
                        st.success(f"✅ Carpeta configurada: {res.get('folder')}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error: {e}")
        
        with col2:
            if st.button("🔍 Escanear e Importar", key="import_folder_btn"):
                if mount_node:
                    try:
                        with st.spinner("🔍 Escaneando carpeta..."):
                            res = api.import_node_folder(mount_node)
                            st.success(f"✅ Importados: **{res.get('imported', 0)}** archivos desde {res.get('folder')}")
                            st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error: {e}")
