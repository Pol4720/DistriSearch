"""
🎛️ DistriSearch Control Center
Centro de Control para monitoreo y pruebas del sistema distribuido
"""

import streamlit as st
import requests
import time
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from streamlit_option_menu import option_menu
from streamlit_autorefresh import st_autorefresh

# Configuración de la página
st.set_page_config(
    page_title="Control Center - DistriSearch",
    page_icon="🎛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# URL del backend del Control Center
BACKEND_URL = "http://localhost:8888"

# CSS personalizado moderno
st.markdown("""
<style>
    /* Ocultar elementos por defecto de Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Fondo con gradiente animado */
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%);
    }
    
    /* Estilo para métricas */
    [data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 700;
        color: #0ea5e9;
    }
    
    [data-testid="stMetricLabel"] {
        font-size: 0.9rem;
        color: #94a3b8;
    }
    
    /* Cards personalizadas */
    .custom-card {
        background: linear-gradient(145deg, #1e293b, #0f172a);
        border-radius: 16px;
        padding: 1.5rem;
        border: 1px solid #334155;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
        margin-bottom: 1rem;
    }
    
    .card-title {
        color: #f1f5f9;
        font-size: 1.2rem;
        font-weight: 600;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    /* Status badges */
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem 1rem;
        border-radius: 9999px;
        font-size: 0.875rem;
        font-weight: 500;
    }
    
    .status-healthy {
        background: rgba(34, 197, 94, 0.2);
        color: #22c55e;
        border: 1px solid #22c55e;
    }
    
    .status-degraded {
        background: rgba(245, 158, 11, 0.2);
        color: #f59e0b;
        border: 1px solid #f59e0b;
    }
    
    .status-unhealthy {
        background: rgba(239, 68, 68, 0.2);
        color: #ef4444;
        border: 1px solid #ef4444;
    }
    
    .status-unknown {
        background: rgba(148, 163, 184, 0.2);
        color: #94a3b8;
        border: 1px solid #94a3b8;
    }
    
    /* Node cards */
    .node-card {
        background: #1e293b;
        border-radius: 12px;
        padding: 1rem;
        border-left: 4px solid #0ea5e9;
        margin-bottom: 0.75rem;
    }
    
    .node-card-master {
        border-left-color: #22c55e;
    }
    
    .node-card-slave {
        border-left-color: #64748b;
    }
    
    /* Botones personalizados */
    .stButton > button {
        background: linear-gradient(135deg, #0ea5e9, #0284c7);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1.5rem;
        font-weight: 500;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        background: linear-gradient(135deg, #38bdf8, #0ea5e9);
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(14, 165, 233, 0.4);
    }
    
    /* Info boxes */
    .info-box {
        background: rgba(14, 165, 233, 0.1);
        border: 1px solid rgba(14, 165, 233, 0.3);
        border-radius: 12px;
        padding: 1rem;
        margin: 1rem 0;
        color: #7dd3fc;
    }
    
    .warning-box {
        background: rgba(245, 158, 11, 0.1);
        border: 1px solid rgba(245, 158, 11, 0.3);
        border-radius: 12px;
        padding: 1rem;
        margin: 1rem 0;
        color: #fcd34d;
    }
    
    .error-box {
        background: rgba(239, 68, 68, 0.1);
        border: 1px solid rgba(239, 68, 68, 0.3);
        border-radius: 12px;
        padding: 1rem;
        margin: 1rem 0;
        color: #fca5a5;
    }
    
    /* Progress bars */
    .stProgress > div > div {
        background: linear-gradient(90deg, #0ea5e9, #22c55e);
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: #0f172a;
        border-right: 1px solid #334155;
    }
    
    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: #1e293b;
        border-radius: 12px;
        padding: 4px;
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        color: #94a3b8;
        padding: 8px 16px;
    }
    
    .stTabs [aria-selected="true"] {
        background: #0ea5e9 !important;
        color: white !important;
    }
    
    /* Expander styling */
    .streamlit-expanderHeader {
        background: #1e293b;
        border-radius: 8px;
    }
    
    /* Animation classes */
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }
    
    .pulse-animation {
        animation: pulse 2s infinite;
    }
    
    @keyframes slideIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .slide-in {
        animation: slideIn 0.5s ease-out;
    }
    
    /* Concept explanation boxes */
    .concept-box {
        background: linear-gradient(145deg, #1e293b, #0f172a);
        border-radius: 12px;
        padding: 1.25rem;
        border: 1px solid #334155;
        margin: 0.5rem 0;
    }
    
    .concept-title {
        color: #0ea5e9;
        font-weight: 600;
        font-size: 1rem;
        margin-bottom: 0.5rem;
    }
    
    .concept-text {
        color: #cbd5e1;
        font-size: 0.9rem;
        line-height: 1.5;
    }
</style>
""", unsafe_allow_html=True)


# ============================================
# Funciones de API
# ============================================

def api_request(endpoint: str, method: str = "GET", data: dict = None) -> dict:
    """Realiza una petición a la API del backend."""
    try:
        url = f"{BACKEND_URL}/api{endpoint}"
        if method == "GET":
            response = requests.get(url, timeout=10)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=30)
        elif method == "DELETE":
            response = requests.delete(url, timeout=10)
        
        if response.ok:
            return response.json()
        return {"error": f"Error {response.status_code}"}
    except requests.exceptions.ConnectionError:
        return {"error": "No se puede conectar al backend"}
    except Exception as e:
        return {"error": str(e)}


def get_cluster_status():
    """Obtiene el estado del cluster."""
    return api_request("/cluster/status")


def get_leader_info():
    """Obtiene información del líder."""
    return api_request("/cluster/leader")


def get_containers():
    """Obtiene la lista de contenedores."""
    return api_request("/nodes/containers")


def get_scenarios():
    """Obtiene los escenarios de prueba."""
    return api_request("/tests/scenarios")


def run_scenario(scenario_id: str):
    """Ejecuta un escenario de prueba."""
    return api_request(f"/tests/run/{scenario_id}", method="POST")


def get_test_results():
    """Obtiene los resultados de pruebas."""
    return api_request("/tests/results")


def get_metrics_summary():
    """Obtiene el resumen de métricas."""
    return api_request("/metrics/summary")


def node_action(action: str, container_name: str):
    """Ejecuta una acción sobre un nodo."""
    return api_request(f"/nodes/{action}/{container_name}", method="POST")


# ============================================
# Componentes de UI reutilizables
# ============================================

def render_status_badge(status: str) -> str:
    """Renderiza un badge de estado."""
    status_map = {
        "healthy": ("✅", "status-healthy", "Saludable"),
        "degraded": ("⚠️", "status-degraded", "Degradado"),
        "unhealthy": ("❌", "status-unhealthy", "No Saludable"),
        "unknown": ("❓", "status-unknown", "Desconocido"),
        "running": ("✅", "status-healthy", "Ejecutando"),
        "exited": ("⏹️", "status-unhealthy", "Detenido"),
        "paused": ("⏸️", "status-degraded", "Pausado"),
    }
    icon, css_class, label = status_map.get(status.lower(), ("❓", "status-unknown", status))
    return f'<span class="status-badge {css_class}">{icon} {label}</span>'


def render_concept_box(title: str, text: str):
    """Renderiza una caja de explicación de concepto."""
    st.markdown(f"""
    <div class="concept-box">
        <div class="concept-title">💡 {title}</div>
        <div class="concept-text">{text}</div>
    </div>
    """, unsafe_allow_html=True)


def render_info_box(text: str, type: str = "info"):
    """Renderiza una caja de información."""
    st.markdown(f'<div class="{type}-box">{text}</div>', unsafe_allow_html=True)


# ============================================
# Páginas
# ============================================

def page_dashboard():
    """Página principal del dashboard."""
    st.title("🎛️ Panel de Control")
    st.markdown("*Monitoreo en tiempo real del cluster DistriSearch*")
    
    # Auto-refresh cada 5 segundos
    st_autorefresh(interval=5000, limit=None, key="dashboard_refresh")
    
    # Obtener datos
    cluster = get_cluster_status()
    metrics = get_metrics_summary()
    
    if "error" in cluster:
        st.error(f"⚠️ Error de conexión: {cluster['error']}")
        render_info_box(
            "🔌 Asegúrate de que el backend del Control Center esté ejecutándose en el puerto 8888 "
            "y que el sistema DistriSearch esté activo.",
            "warning"
        )
        return
    
    # Métricas principales
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="📊 Nodos Totales",
            value=cluster.get("total_nodes", 0),
            delta=f"{cluster.get('healthy_nodes', 0)} saludables"
        )
    
    with col2:
        st.metric(
            label="📄 Documentos",
            value=cluster.get("total_documents", 0),
            delta="Indexados"
        )
    
    with col3:
        st.metric(
            label="📦 Particiones",
            value=cluster.get("total_partitions", 0),
            delta=f"Factor: {cluster.get('replication_factor', 2)}x"
        )
    
    with col4:
        status = cluster.get("status", "unknown")
        st.markdown(f"""
        <div style="text-align: center;">
            <p style="color: #94a3b8; font-size: 0.9rem; margin-bottom: 0.5rem;">Estado del Cluster</p>
            {render_status_badge(status)}
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Dos columnas: Nodos y Líder
    col_left, col_right = st.columns([2, 1])
    
    with col_left:
        st.subheader("🖥️ Nodos del Cluster")
        
        nodes = cluster.get("nodes", [])
        if nodes:
            for node in nodes:
                role = node.get("role", "slave")
                status = node.get("status", "unknown")
                node_class = "node-card-master" if role == "master" else "node-card-slave"
                
                st.markdown(f"""
                <div class="node-card {node_class}">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <strong style="color: #f1f5f9;">{"👑 " if role == "master" else "🔹 "}{node.get('node_id', 'N/A')}</strong>
                            <span style="color: #64748b; margin-left: 1rem;">{node.get('address', '')}:{node.get('port', '')}</span>
                        </div>
                        {render_status_badge(status)}
                    </div>
                    <div style="margin-top: 0.75rem; display: flex; gap: 2rem; color: #94a3b8; font-size: 0.85rem;">
                        <span>📄 {node.get('document_count', 0)} docs</span>
                        <span>📦 {node.get('partition_count', 0)} particiones</span>
                        <span>🔄 CPU: {node.get('cpu_usage', 0):.1f}%</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No hay nodos registrados en el cluster")
    
    with col_right:
        st.subheader("👑 Líder Actual")
        
        leader = get_leader_info()
        if "error" not in leader:
            leader_data = leader.get("leader", {})
            st.markdown(f"""
            <div class="custom-card">
                <div style="text-align: center;">
                    <div style="font-size: 3rem; margin-bottom: 0.5rem;">👑</div>
                    <div style="color: #22c55e; font-weight: 600; font-size: 1.1rem;">
                        {leader_data.get('leader_id', 'N/A')}
                    </div>
                    <div style="color: #64748b; font-size: 0.9rem; margin-top: 0.5rem;">
                        {leader_data.get('leader_address', 'Sin dirección')}
                    </div>
                    <div style="color: #94a3b8; font-size: 0.8rem; margin-top: 1rem;">
                        Término: {leader_data.get('term', 0)}
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        render_concept_box(
            "Elección de Líder",
            "El líder coordina todas las operaciones de escritura y mantiene la consistencia "
            "del cluster usando el algoritmo de consenso Raft."
        )
    
    # Explicación del estado
    st.markdown("---")
    st.subheader("📚 ¿Qué significan estos estados?")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        render_concept_box(
            "Cluster Saludable (Healthy)",
            "Todos los nodos responden correctamente a los heartbeats y los datos están sincronizados entre réplicas."
        )
    
    with col2:
        render_concept_box(
            "Cluster Degradado (Degraded)",
            "Algunos nodos no están disponibles, pero el sistema mantiene el quórum necesario para operar."
        )
    
    with col3:
        render_concept_box(
            "Cluster No Saludable (Unhealthy)",
            "El sistema no puede garantizar la consistencia de datos. Se requiere intervención."
        )


def page_nodes():
    """Página de gestión de nodos."""
    st.title("🖥️ Gestión de Nodos")
    st.markdown("*Control y monitoreo de los contenedores del cluster*")
    
    # Obtener contenedores
    containers_response = get_containers()
    
    if "error" in containers_response:
        st.error(f"Error: {containers_response['error']}")
        return
    
    if not containers_response.get("docker_available", False):
        st.warning("⚠️ Docker no está disponible. Las funciones de control de nodos están deshabilitadas.")
        render_info_box(
            "Para habilitar el control de nodos, asegúrate de que Docker esté instalado y el "
            "backend del Control Center tenga acceso al socket de Docker.",
            "warning"
        )
        return
    
    containers = containers_response.get("containers", [])
    
    if not containers:
        st.info("No se encontraron contenedores de DistriSearch")
        return
    
    # Mostrar contenedores
    st.subheader(f"📦 {len(containers)} Contenedores Encontrados")
    
    for container in containers:
        with st.expander(
            f"{'👑 ' if container.get('is_master') else '🔹 '}{container['name']} - {container['status']}",
            expanded=container.get("status") == "running"
        ):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown(f"""
                **ID:** `{container['id']}`  
                **Imagen:** `{container['image']}`  
                **Estado:** {render_status_badge(container['status'])}  
                **Puertos:** {', '.join(container.get('ports', [])) or 'N/A'}
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown("**Acciones:**")
                status = container["status"]
                name = container["name"]
                
                col_a, col_b = st.columns(2)
                
                with col_a:
                    if status == "running":
                        if st.button("⏹️ Detener", key=f"stop_{name}", use_container_width=True):
                            with st.spinner("Deteniendo..."):
                                result = node_action("stop", name)
                            if "error" not in result:
                                st.success("✅ Nodo detenido")
                                st.rerun()
                            else:
                                st.error(f"Error: {result.get('error')}")
                    else:
                        if st.button("▶️ Iniciar", key=f"start_{name}", use_container_width=True):
                            with st.spinner("Iniciando..."):
                                result = node_action("start", name)
                            if "error" not in result:
                                st.success("✅ Nodo iniciado")
                                st.rerun()
                            else:
                                st.error(f"Error: {result.get('error')}")
                
                with col_b:
                    if status == "running":
                        if st.button("🔄 Reiniciar", key=f"restart_{name}", use_container_width=True):
                            with st.spinner("Reiniciando..."):
                                result = node_action("restart", name)
                            if "error" not in result:
                                st.success("✅ Nodo reiniciado")
                                st.rerun()
                            else:
                                st.error(f"Error: {result.get('error')}")
                
                st.markdown("---")
                st.markdown("**⚠️ Acciones Avanzadas:**")
                
                col_c, col_d = st.columns(2)
                
                with col_c:
                    if status == "running":
                        if st.button("💀 Kill (SIGKILL)", key=f"kill_{name}", use_container_width=True, type="secondary"):
                            with st.spinner("Terminando proceso..."):
                                result = node_action("kill", name)
                            if "error" not in result:
                                st.warning("⚠️ Nodo terminado abruptamente")
                                st.rerun()
                            else:
                                st.error(f"Error: {result.get('error')}")
                
                with col_d:
                    if status == "running":
                        if st.button("⏸️ Pausar (Red)", key=f"pause_{name}", use_container_width=True, type="secondary"):
                            with st.spinner("Pausando..."):
                                result = node_action("pause", name)
                            if "error" not in result:
                                st.info("🌐 Nodo pausado (simula partición de red)")
                                st.rerun()
                            else:
                                st.error(f"Error: {result.get('error')}")
                    elif status == "paused":
                        if st.button("▶️ Reanudar", key=f"unpause_{name}", use_container_width=True):
                            with st.spinner("Reanudando..."):
                                result = node_action("unpause", name)
                            if "error" not in result:
                                st.success("✅ Nodo reanudado")
                                st.rerun()
                            else:
                                st.error(f"Error: {result.get('error')}")
    
    # Explicaciones
    st.markdown("---")
    st.subheader("📚 Explicación de Acciones")
    
    col1, col2 = st.columns(2)
    
    with col1:
        render_concept_box(
            "Detener vs Kill",
            "**Detener** envía SIGTERM y permite un apagado controlado. "
            "**Kill** envía SIGKILL y termina el proceso inmediatamente, simulando un fallo catastrófico."
        )
    
    with col2:
        render_concept_box(
            "Pausar (Partición de Red)",
            "Pausar un contenedor simula una partición de red: el nodo sigue vivo pero no puede comunicarse. "
            "Útil para probar tolerancia a particiones (CAP theorem)."
        )


def page_tests():
    """Página de escenarios de prueba."""
    st.title("🧪 Escenarios de Prueba")
    st.markdown("*Prueba el comportamiento del sistema distribuido con escenarios predefinidos*")
    
    tab1, tab2 = st.tabs(["📋 Escenarios Disponibles", "📊 Resultados"])
    
    with tab1:
        scenarios_response = get_scenarios()
        
        if "error" in scenarios_response:
            st.error(f"Error: {scenarios_response['error']}")
            return
        
        scenarios = scenarios_response.get("scenarios", {})
        
        st.markdown("### Selecciona un escenario para probar")
        
        for scenario_id, scenario in scenarios.items():
            with st.expander(f"🔬 {scenario['name']}", expanded=False):
                st.markdown(f"**Descripción:** {scenario['description']}")
                
                st.markdown("**Pasos del escenario:**")
                for step in scenario.get("steps", []):
                    st.markdown(f"- {step}")
                
                st.markdown(f"**Tiempo estimado:** ~{scenario.get('expected_time_seconds', 30)} segundos")
                
                concepts = scenario.get("concepts", [])
                if concepts:
                    st.markdown(f"**Conceptos relacionados:** {', '.join(concepts)}")
                
                st.markdown("---")
                
                if st.button(f"▶️ Ejecutar: {scenario['name']}", key=f"run_{scenario_id}", use_container_width=True):
                    with st.spinner(f"Ejecutando {scenario['name']}..."):
                        result = run_scenario(scenario_id)
                    
                    if "error" not in result:
                        st.success(f"✅ Escenario iniciado. ID: {result.get('test_id')}")
                        st.info("Ve a la pestaña 'Resultados' para ver el progreso.")
                    else:
                        st.error(f"Error: {result.get('error')}")
        
        # Explicaciones de conceptos
        st.markdown("---")
        st.subheader("📚 Conceptos de Sistemas Distribuidos")
        
        col1, col2 = st.columns(2)
        
        with col1:
            render_concept_box(
                "Algoritmo Raft",
                "Raft es un algoritmo de consenso que garantiza que todos los nodos del cluster "
                "acuerden el mismo estado. Incluye elección de líder y replicación de logs."
            )
            
            render_concept_box(
                "Tolerancia a Fallos",
                "El sistema puede seguir funcionando aunque algunos nodos fallen, "
                "siempre que se mantenga el quórum (mayoría de nodos disponibles)."
            )
        
        with col2:
            render_concept_box(
                "Partición de Red",
                "Cuando los nodos no pueden comunicarse entre sí debido a problemas de red. "
                "El teorema CAP dice que debemos elegir entre Consistencia y Disponibilidad."
            )
            
            render_concept_box(
                "Replicación de Datos",
                "Los datos se copian a múltiples nodos para garantizar durabilidad. "
                "El factor de replicación indica en cuántos nodos se almacena cada dato."
            )
    
    with tab2:
        st.markdown("### Resultados de Pruebas")
        
        if st.button("🔄 Actualizar Resultados"):
            st.rerun()
        
        results_response = get_test_results()
        
        if "error" in results_response:
            st.error(f"Error: {results_response['error']}")
            return
        
        results = results_response.get("results", [])
        
        if not results:
            st.info("No hay resultados de pruebas aún. Ejecuta un escenario para ver los resultados.")
            return
        
        for result in reversed(results):  # Mostrar los más recientes primero
            status_icon = {
                "running": "🔄",
                "completed": "✅",
                "failed": "❌"
            }.get(result.get("status"), "❓")
            
            with st.expander(
                f"{status_icon} {result.get('scenario_name', 'Test')} - {result.get('test_id')}",
                expanded=result.get("status") == "running"
            ):
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.markdown(f"**Estado:** {result.get('status', 'unknown')}")
                    st.markdown(f"**Iniciado:** {result.get('started_at', 'N/A')}")
                    
                    if result.get("completed_at"):
                        st.markdown(f"**Completado:** {result.get('completed_at')}")
                    
                    # Progress bar
                    total_steps = result.get("total_steps", 1)
                    current_step = result.get("current_step", 0)
                    progress = current_step / total_steps if total_steps > 0 else 0
                    st.progress(progress, text=f"Paso {current_step}/{total_steps}")
                
                with col2:
                    metrics = result.get("metrics", {})
                    if metrics:
                        st.markdown("**Métricas:**")
                        for key, value in metrics.items():
                            st.markdown(f"- **{key}:** {value}")
                
                # Pasos completados
                steps = result.get("steps_completed", [])
                if steps:
                    st.markdown("**Pasos ejecutados:**")
                    for step in steps:
                        icon = "✅" if step.get("success") else "❌"
                        st.markdown(f"{icon} {step.get('description', 'Paso')}")
                
                # Errores
                errors = result.get("errors", [])
                if errors:
                    st.markdown("**Errores:**")
                    for error in errors:
                        st.error(error)


def page_metrics():
    """Página de métricas."""
    st.title("📊 Métricas del Sistema")
    st.markdown("*Visualización de métricas y estadísticas del cluster*")
    
    # Auto-refresh
    st_autorefresh(interval=5000, limit=None, key="metrics_refresh")
    
    metrics = get_metrics_summary()
    
    if "error" in metrics:
        st.error(f"Error: {metrics['error']}")
        return
    
    # Estado del cluster
    cluster_status = metrics.get("cluster_status", {})
    status = cluster_status.get("status", "unknown")
    
    st.markdown(f"""
    <div class="custom-card">
        <div class="card-title">🎯 Estado General del Cluster</div>
        <div style="display: flex; align-items: center; gap: 1rem;">
            <span style="font-size: 2rem;">{cluster_status.get('icon', '❓')}</span>
            {render_status_badge(status)}
        </div>
        <p style="color: #94a3b8; margin-top: 1rem;">{cluster_status.get('description_es', '')}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Métricas en columnas
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("### 🖥️ Nodos")
        nodes_data = metrics.get("nodes", {})
        
        # Gráfico de donut para nodos
        fig = go.Figure(data=[go.Pie(
            labels=['Saludables', 'No Saludables'],
            values=[nodes_data.get('healthy', 0), nodes_data.get('unhealthy', 0)],
            hole=.6,
            marker_colors=['#22c55e', '#ef4444']
        )])
        fig.update_layout(
            showlegend=True,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#f1f5f9'),
            height=250,
            margin=dict(t=20, b=20, l=20, r=20)
        )
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown(f"<p style='color: #94a3b8; text-align: center;'>{nodes_data.get('description_es', '')}</p>", unsafe_allow_html=True)
    
    with col2:
        st.markdown("### 📄 Datos")
        data_info = metrics.get("data", {})
        
        st.metric("Documentos", data_info.get("total_documents", 0))
        st.metric("Particiones", data_info.get("total_partitions", 0))
        st.metric("Factor de Replicación", f"{data_info.get('replication_factor', 2)}x")
        
        st.markdown(f"<p style='color: #94a3b8;'>{data_info.get('description_es', '')}</p>", unsafe_allow_html=True)
    
    with col3:
        st.markdown("### 💻 Recursos")
        resources = metrics.get("resources", {})
        
        # CPU
        cpu = resources.get("avg_cpu_usage", 0)
        st.markdown("**CPU Promedio**")
        st.progress(min(cpu/100, 1.0), text=f"{cpu:.1f}%")
        
        # Memory
        memory = resources.get("avg_memory_usage", 0)
        st.markdown("**Memoria Promedio**")
        st.progress(min(memory/100, 1.0), text=f"{memory:.1f}%")
        
        # Uptime
        uptime = metrics.get("uptime", {})
        st.markdown(f"**Uptime:** {uptime.get('formatted', 'N/A')}")
    
    # Conceptos explicados
    st.markdown("---")
    st.subheader("📚 Entendiendo las Métricas")
    
    concepts = metrics.get("concepts", {}).get("es", {})
    
    cols = st.columns(2)
    concept_items = list(concepts.items())
    
    for i, (key, value) in enumerate(concept_items):
        with cols[i % 2]:
            render_concept_box(key.title(), value)


def page_help():
    """Página de ayuda."""
    st.title("❓ Ayuda y Documentación")
    st.markdown("*Guía completa del Control Center y conceptos de sistemas distribuidos*")
    
    tab1, tab2, tab3 = st.tabs(["🎛️ Uso del Control Center", "📚 Conceptos", "🔧 Solución de Problemas"])
    
    with tab1:
        st.markdown("""
        ## 🎛️ Cómo usar el Control Center
        
        El Control Center te permite monitorear y probar tu sistema distribuido DistriSearch en tiempo real.
        
        ### Panel Principal
        Muestra el estado general del cluster:
        - **Nodos**: Cantidad y estado de los nodos del cluster
        - **Documentos**: Total de documentos indexados
        - **Líder**: Nodo que coordina las operaciones
        
        ### Gestión de Nodos
        Permite controlar los contenedores Docker:
        - **Iniciar/Detener**: Control graceful de nodos
        - **Kill**: Simula fallos catastróficos
        - **Pausar**: Simula particiones de red
        
        ### Escenarios de Prueba
        Pruebas automatizadas para verificar:
        - Elección de líder (Raft)
        - Recuperación de nodos
        - Tolerancia a particiones
        - Replicación de datos
        """)
    
    with tab2:
        st.markdown("## 📚 Conceptos de Sistemas Distribuidos")
        
        concepts = [
            ("Consenso y Raft", 
             "Raft es un algoritmo que garantiza que todos los nodos del cluster acuerden el mismo estado. "
             "Funciona eligiendo un líder que coordina todas las escrituras y las replica a los seguidores."),
            
            ("Elección de Líder",
             "Cuando el líder falla, los nodos detectan la ausencia de heartbeats y inician una nueva elección. "
             "El candidato que obtenga mayoría de votos se convierte en el nuevo líder."),
            
            ("Replicación de Logs",
             "El líder recibe las escrituras y las añade a su log. Luego replica las entradas a los seguidores. "
             "Una entrada se considera committed cuando la mayoría la ha replicado."),
            
            ("Heartbeats",
             "Mensajes periódicos que el líder envía a los seguidores para mantener su autoridad. "
             "Si un seguidor no recibe heartbeats, asume que el líder ha fallado."),
            
            ("Quórum",
             "Número mínimo de nodos necesarios para tomar decisiones (mayoría). "
             "Con N nodos, se necesitan (N/2)+1 nodos para mantener el quórum."),
            
            ("Teorema CAP",
             "Un sistema distribuido solo puede garantizar 2 de 3: Consistencia, Disponibilidad, "
             "Tolerancia a Particiones. DistriSearch prioriza Consistencia y Tolerancia."),
            
            ("Factor de Replicación",
             "Número de copias de cada dato en el cluster. Un factor de 3 significa que cada dato "
             "está en 3 nodos diferentes, permitiendo tolerar hasta 2 fallos."),
            
            ("Partición de Red",
             "Situación donde algunos nodos no pueden comunicarse con otros debido a fallos de red. "
             "El cluster debe decidir cómo manejar esta situación."),
        ]
        
        for title, description in concepts:
            render_concept_box(title, description)
    
    with tab3:
        st.markdown("""
        ## 🔧 Solución de Problemas
        
        ### El backend no responde
        1. Verifica que el backend esté corriendo: `python main.py`
        2. Confirma el puerto 8888 esté disponible
        3. Revisa los logs del backend
        
        ### Docker no disponible
        1. Verifica que Docker esté instalado y corriendo
        2. Confirma que el usuario tiene permisos para Docker
        3. En Linux: añade el usuario al grupo `docker`
        
        ### Nodos no detectados
        1. Verifica que DistriSearch esté desplegado
        2. Los contenedores deben tener 'distrisearch', 'master' o 'slave' en el nombre
        3. Revisa la red de Docker
        
        ### Tests fallan
        1. Asegúrate de que Docker tenga permisos suficientes
        2. Verifica que haya nodos corriendo para probar
        3. Algunos tests requieren múltiples nodos
        """)
        
        st.markdown("---")
        st.markdown("### 📧 ¿Necesitas más ayuda?")
        st.info("Revisa la documentación del proyecto DistriSearch o abre un issue en el repositorio.")


# ============================================
# Main
# ============================================

def main():
    """Función principal de la aplicación."""
    
    # Sidebar con navegación
    with st.sidebar:
        st.markdown("""
        <div style="text-align: center; padding: 1rem;">
            <div style="font-size: 2.5rem;">🎛️</div>
            <h2 style="color: #f1f5f9; margin: 0.5rem 0;">Control Center</h2>
            <p style="color: #64748b; font-size: 0.9rem;">DistriSearch</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        selected = option_menu(
            menu_title=None,
            options=["Panel Principal", "Nodos", "Escenarios", "Métricas", "Ayuda"],
            icons=["speedometer2", "hdd-stack", "flask", "graph-up", "question-circle"],
            default_index=0,
            styles={
                "container": {"padding": "0"},
                "icon": {"color": "#0ea5e9", "font-size": "1rem"},
                "nav-link": {
                    "font-size": "0.9rem",
                    "text-align": "left",
                    "margin": "0.25rem 0",
                    "padding": "0.75rem 1rem",
                    "border-radius": "8px",
                    "color": "#94a3b8",
                },
                "nav-link-selected": {
                    "background-color": "#0ea5e9",
                    "color": "white",
                },
            }
        )
        
        st.markdown("---")
        
        # Estado de conexión
        try:
            health = api_request("/cluster/health")
            if "error" not in health:
                st.success("🟢 Conectado")
            else:
                st.warning("🟡 Backend activo, cluster no disponible")
        except:
            st.error("🔴 Sin conexión")
        
        st.markdown(f"""
        <div style="text-align: center; color: #64748b; font-size: 0.8rem; margin-top: 2rem;">
            <p>v1.0.0</p>
            <p>{datetime.now().strftime('%H:%M:%S')}</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Renderizar página seleccionada
    if selected == "Panel Principal":
        page_dashboard()
    elif selected == "Nodos":
        page_nodes()
    elif selected == "Escenarios":
        page_tests()
    elif selected == "Métricas":
        page_metrics()
    elif selected == "Ayuda":
        page_help()


if __name__ == "__main__":
    main()
