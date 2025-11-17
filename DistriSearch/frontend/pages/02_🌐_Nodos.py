"""
Página de gestión de nodos
Registro, eliminación y monitoreo de nodos
"""
import streamlit as st
import pandas as pd
from utils.helpers import setup_page_config, init_session_state, get_api_client, normalize_status
from components.styles import inject_modern_css, get_animated_header
from components.cards import node_card, empty_state, metric_card

# Page config
setup_page_config("Gestión de Nodos", "🌐", "wide")

# Initialize
init_session_state()
api = get_api_client()

# Inject styles
inject_modern_css(st.session_state.theme)

# Header
st.markdown(get_animated_header("🌐 Gestión de Nodos", "Administra la red distribuida"), unsafe_allow_html=True)

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

# Tabs for different operations
tab1, tab2, tab3, tab4 = st.tabs(["📋 Nodos Activos", "➕ Añadir Nodo", "🗑️ Eliminar Nodo", "⚙️ Configuración Avanzada"])

# Tab 1: Active Nodes
with tab1:
    st.markdown("### Nodos Registrados en el Sistema")
    
    if nodes:
        # Display nodes as cards in a grid
        cols = st.columns(2)
        for idx, node in enumerate(nodes):
            with cols[idx % 2]:
                node_card(node)
        
        # Also show as table
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
        <p style="margin: 0;">Completa los datos del nodo para agregarlo a la red distribuida.</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        node_id = st.text_input(
            "🆔 ID del Nodo",
            placeholder="node1",
            help="Identificador único del nodo"
        )
        node_name = st.text_input(
            "📛 Nombre del Nodo",
            placeholder="Agente Principal",
            help="Nombre descriptivo del nodo"
        )
    
    with col2:
        node_ip = st.text_input(
            "🌐 Dirección IP",
            placeholder="192.168.1.100",
            help="IP o hostname del nodo"
        )
        node_port = st.number_input(
            "🔌 Puerto",
            min_value=1,
            max_value=65535,
            value=8081,
            step=1,
            help="Puerto del servicio del agente"
        )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 2])
    with col_btn2:
        if st.button("✅ Registrar Nodo", use_container_width=True, type="primary"):
            if node_id and node_name and node_ip:
                try:
                    res = api.register_node({
                        "node_id": node_id,
                        "name": node_name,
                        "ip_address": node_ip,
                        "port": int(node_port),
                        "status": "online",
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
                options=list(node_options.keys())
            )
            del_id = node_options[selected_node]
        else:
            st.info("No hay nodos disponibles para eliminar")
            del_id = None
    
    with col2:
        del_files = st.checkbox(
            "🗑️ Eliminar archivos del índice",
            value=True,
            help="Si está marcado, también se eliminarán los archivos del nodo del índice central"
        )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 2])
    with col_btn2:
        if st.button("🗑️ Eliminar Nodo", use_container_width=True, type="primary", disabled=not del_id):
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
            <p style="margin: 0;">Ejecuta una pasada de replicación para mover archivos de nodos OFFLINE al repositorio central.</p>
        </div>
        """, unsafe_allow_html=True)
        
        batch = st.slider(
            "Tamaño del lote",
            min_value=1,
            max_value=200,
            value=25,
            step=1,
            help="Número de archivos a procesar en cada lote"
        )
        
        if st.button("▶️ Ejecutar Replicación", type="primary"):
            try:
                with st.spinner("🔄 Ejecutando replicación..."):
                    res = api.run_replication(batch=batch)
                    st.success(f"✅ Replicación completada: **{res.get('replicated', 0)}** archivos replicados de **{res.get('checked', 0)}** revisados")
            except Exception as e:
                st.error(f"❌ Error ejecutando replicación: {e}")
    
        # --- DHT Controls ---
        with st.expander("🧩 DHT (Red Distribuida)", expanded=False):
            st.markdown("""
            <div class="glass-panel" style="padding: 1rem; margin-bottom: 1rem;">
                <p style="margin: 0;">Controla una instancia DHT desde el backend. Puede funcionar en modo externo (servicio DHT separado) o inproc (arranca un Peer en el backend).</p>
            </div>
            """, unsafe_allow_html=True)

            col_a, col_b = st.columns([2, 1])
            with col_a:
                if st.button("▶️ Iniciar DHT (backend)"):
                    try:
                        res = api.dht_start()
                        st.success(f"✅ DHT iniciada (modo: {res.get('mode')})")
                    except Exception as e:
                        st.error(f"❌ Error iniciando DHT: {e}")

            with st.expander("🔗 Unirse a red DHT (seed)"):
                seed_ip = st.text_input("Seed IP", placeholder="192.168.1.10")
                seed_port = st.number_input("Seed puerto", min_value=1, max_value=65535, value=2000)
                if st.button("➕ Unirse al seed"):
                    if seed_ip:
                        try:
                            res = api.dht_join(seed_ip, int(seed_port))
                            st.success(f"✅ Resultado: {res.get('result')}")
                        except Exception as e:
                            st.error(f"❌ Error al unirse: {e}")
                    else:
                        st.warning("⚠️ Introduce la IP del seed")

            with st.expander("📡 Estado DHT / Finger table"):
                if st.button("🔄 Obtener Finger Table"):
                    try:
                        res = api.dht_finger()
                        st.code(res.get('finger'))
                    except Exception as e:
                        st.error(f"❌ Error: {e}")

                if st.button("🔍 Sucesor / Predecesor"):
                    try:
                        res = api.dht_sucpred()
                        st.json(res.get('sucpred'))
                    except Exception as e:
                        st.error(f"❌ Error: {e}")

            with st.expander("📁 Subir / Descargar archivo (prueba)"):
                test_name = st.text_input("Nombre archivo (prueba)", value="prueba.txt")
                test_data = st.text_area("Contenido del archivo", value="Contenido de prueba desde frontend")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("⬆️ Subir a DHT"):
                        try:
                            res = api.dht_upload(test_name, test_data)
                            st.success(f"✅ {res.get('result')}")
                        except Exception as e:
                            st.error(f"❌ Error al subir: {e}")
                with c2:
                    if st.button("⬇️ Descargar desde DHT"):
                        try:
                            res = api.dht_download(test_name)
                            st.write(res.get('result'))
                        except Exception as e:
                            st.error(f"❌ Error al descargar: {e}")

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
            if st.button("💾 Guardar Carpeta"):
                if mount_node and mount_folder:
                    try:
                        res = api.set_node_mount(mount_node, mount_folder)
                        st.success(f"✅ Carpeta configurada: {res.get('folder')}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error: {e}")
        
        with col2:
            if st.button("🔍 Escanear e Importar"):
                if mount_node:
                    try:
                        with st.spinner("🔍 Escaneando carpeta..."):
                            res = api.import_node_folder(mount_node)
                            st.success(f"✅ Importados: **{res.get('imported', 0)}** archivos desde {res.get('folder')}")
                            st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error: {e}")
