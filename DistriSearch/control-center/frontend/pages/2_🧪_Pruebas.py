"""
🧪 Escenarios de Prueba
Tests automatizados para el sistema distribuido
"""

import streamlit as st
import requests
import time
from datetime import datetime

st.set_page_config(
    page_title="Pruebas - Control Center",
    page_icon="🧪",
    layout="wide",
)

# CSS
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%);
    }
    
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1e1b4b 0%, #0f172a 100%);
    }
    
    .scenario-card {
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(12px);
        border-radius: 16px;
        padding: 1.5rem;
        border: 1px solid rgba(99, 102, 241, 0.2);
        margin-bottom: 1rem;
        transition: all 0.3s ease;
    }
    
    .scenario-card:hover {
        border-color: rgba(99, 102, 241, 0.5);
        transform: translateY(-2px);
    }
    
    .scenario-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 1rem;
    }
    
    .scenario-title {
        color: #f1f5f9;
        font-size: 1.2rem;
        font-weight: 600;
        margin: 0;
    }
    
    .scenario-badge {
        background: rgba(99, 102, 241, 0.2);
        color: #a5b4fc;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 500;
    }
    
    .scenario-description {
        color: #94a3b8;
        font-size: 0.95rem;
        margin-bottom: 1rem;
        line-height: 1.5;
    }
    
    .scenario-steps {
        background: rgba(15, 23, 42, 0.5);
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 1rem;
    }
    
    .scenario-steps-title {
        color: #a855f7;
        font-weight: 600;
        font-size: 0.9rem;
        margin-bottom: 0.75rem;
    }
    
    .step-item {
        color: #cbd5e1;
        font-size: 0.9rem;
        padding: 0.25rem 0;
        display: flex;
        align-items: flex-start;
        gap: 0.5rem;
    }
    
    .step-number {
        background: rgba(99, 102, 241, 0.3);
        color: #a5b4fc;
        width: 20px;
        height: 20px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.75rem;
        flex-shrink: 0;
    }
    
    .concepts-list {
        display: flex;
        gap: 0.5rem;
        flex-wrap: wrap;
        margin-top: 0.75rem;
    }
    
    .concept-tag {
        background: rgba(168, 85, 247, 0.2);
        color: #c4b5fd;
        padding: 0.25rem 0.6rem;
        border-radius: 6px;
        font-size: 0.8rem;
    }
    
    .result-card {
        background: rgba(30, 41, 59, 0.6);
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        border-left: 4px solid #6366f1;
    }
    
    .result-running { border-left-color: #f59e0b; }
    .result-completed { border-left-color: #10b981; }
    .result-failed { border-left-color: #ef4444; }
    
    .result-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0.75rem;
    }
    
    .result-title {
        color: #f1f5f9;
        font-weight: 600;
    }
    
    .metrics-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 0.75rem;
        margin-top: 1rem;
    }
    
    .metric-item {
        background: rgba(15, 23, 42, 0.5);
        border-radius: 8px;
        padding: 0.75rem;
        text-align: center;
    }
    
    .metric-label {
        color: #94a3b8;
        font-size: 0.8rem;
    }
    
    .metric-value {
        color: #f1f5f9;
        font-weight: 600;
        font-size: 1rem;
    }
    
    .concept-box {
        background: linear-gradient(145deg, rgba(99, 102, 241, 0.1), rgba(30, 41, 59, 0.5));
        border-radius: 12px;
        padding: 1rem;
        border: 1px solid rgba(99, 102, 241, 0.2);
        margin: 0.5rem 0;
    }
    
    .concept-title {
        color: #a855f7;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }
    
    .concept-text {
        color: #cbd5e1;
        font-size: 0.9rem;
        line-height: 1.6;
    }
    
    .stButton > button {
        background: linear-gradient(135deg, #6366f1, #8b5cf6);
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)

BACKEND_URL = st.secrets.get("BACKEND_URL", "http://localhost:8888")


def api_get(endpoint: str) -> dict:
    try:
        response = requests.get(f"{BACKEND_URL}/api{endpoint}", timeout=10)
        return response.json() if response.ok else {"error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def api_post(endpoint: str) -> dict:
    try:
        response = requests.post(f"{BACKEND_URL}/api{endpoint}", timeout=30)
        return response.json() if response.ok else {"error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}


# Header
st.markdown("""
<div style="text-align: center; padding: 2rem 0;">
    <h1 style="font-size: 2.5rem; font-weight: 800; background: linear-gradient(135deg, #6366f1, #a855f7); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
        🧪 Escenarios de Prueba
    </h1>
    <p style="color: #94a3b8; font-size: 1rem;">Prueba el comportamiento del sistema distribuido con escenarios predefinidos</p>
</div>
""", unsafe_allow_html=True)

# Tabs
tab1, tab2 = st.tabs(["📋 Escenarios Disponibles", "📊 Resultados de Pruebas"])

with tab1:
    scenarios_data = api_get("/tests/scenarios")
    
    if "error" in scenarios_data:
        st.error(f"Error: {scenarios_data['error']}")
    else:
        scenarios = scenarios_data.get("scenarios", {})
        
        for scenario_id, scenario in scenarios.items():
            st.markdown(f"""
            <div class="scenario-card">
                <div class="scenario-header">
                    <h3 class="scenario-title">🔬 {scenario['name']}</h3>
                    <span class="scenario-badge">~{scenario.get('expected_time_seconds', 30)}s</span>
                </div>
                <p class="scenario-description">{scenario['description']}</p>
            </div>
            """, unsafe_allow_html=True)
            
            with st.expander("Ver detalles y ejecutar", expanded=False):
                st.markdown('<div class="scenario-steps">', unsafe_allow_html=True)
                st.markdown('<p class="scenario-steps-title">📝 Pasos del Escenario</p>', unsafe_allow_html=True)
                
                for i, step in enumerate(scenario.get("steps", []), 1):
                    # Limpiar el número del paso si ya viene incluido
                    step_text = step.split(". ", 1)[-1] if ". " in step else step
                    st.markdown(f"""
                    <div class="step-item">
                        <span class="step-number">{i}</span>
                        <span>{step_text}</span>
                    </div>
                    """, unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)
                
                # Conceptos relacionados
                concepts = scenario.get("concepts", [])
                if concepts:
                    st.markdown('<div class="concepts-list">', unsafe_allow_html=True)
                    for concept in concepts:
                        st.markdown(f'<span class="concept-tag">{concept}</span>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                if st.button(f"▶️ Ejecutar: {scenario['name']}", key=f"run_{scenario_id}", use_container_width=True):
                    with st.spinner(f"Iniciando {scenario['name']}..."):
                        result = api_post(f"/tests/run/{scenario_id}")
                    
                    if "error" not in result:
                        st.success(f"✅ Escenario iniciado - ID: `{result.get('test_id')}`")
                        st.info("💡 Ve a la pestaña 'Resultados de Pruebas' para ver el progreso")
                    else:
                        st.error(f"Error: {result['error']}")
        
        # Conceptos explicados
        st.markdown("---")
        st.markdown("### 📚 Conceptos de Sistemas Distribuidos")
        
        c1, c2 = st.columns(2)
        
        with c1:
            st.markdown("""
            <div class="concept-box">
                <div class="concept-title">🗳️ Algoritmo Raft</div>
                <p class="concept-text">
                    Raft garantiza que todos los nodos del cluster acuerden el mismo estado.
                    Funciona eligiendo un líder que coordina escrituras y las replica a seguidores.
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("""
            <div class="concept-box">
                <div class="concept-title">💔 Tolerancia a Fallos</div>
                <p class="concept-text">
                    El sistema sigue funcionando aunque fallen nodos, siempre que se mantenga
                    el quórum (mayoría de nodos disponibles).
                </p>
            </div>
            """, unsafe_allow_html=True)
        
        with c2:
            st.markdown("""
            <div class="concept-box">
                <div class="concept-title">🌐 Partición de Red</div>
                <p class="concept-text">
                    Cuando los nodos no pueden comunicarse entre sí. El teorema CAP dice que
                    debemos elegir entre Consistencia y Disponibilidad durante una partición.
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("""
            <div class="concept-box">
                <div class="concept-title">📋 Replicación de Datos</div>
                <p class="concept-text">
                    Los datos se copian a múltiples nodos para garantizar durabilidad.
                    El factor de replicación indica en cuántos nodos se almacena cada dato.
                </p>
            </div>
            """, unsafe_allow_html=True)

with tab2:
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔄 Actualizar", use_container_width=True):
            st.rerun()
    
    results_data = api_get("/tests/results")
    
    if "error" in results_data:
        st.error(f"Error: {results_data['error']}")
    else:
        results = results_data.get("results", [])
        
        if not results:
            st.info("📭 No hay resultados de pruebas aún. Ejecuta un escenario para ver los resultados.")
        else:
            for result in reversed(results):
                status = result.get("status", "unknown")
                status_class = f"result-{status}"
                status_icon = {"running": "🔄", "completed": "✅", "failed": "❌"}.get(status, "❓")
                
                st.markdown(f"""
                <div class="result-card {status_class}">
                    <div class="result-header">
                        <span class="result-title">{status_icon} {result.get('scenario_name', 'Test')}</span>
                        <code style="color: #94a3b8;">{result.get('test_id', 'N/A')}</code>
                    </div>
                """, unsafe_allow_html=True)
                
                # Progress
                total_steps = result.get("total_steps", 1)
                current_step = result.get("current_step", 0)
                progress = current_step / total_steps if total_steps > 0 else 0
                
                st.progress(progress, text=f"Paso {current_step}/{total_steps}")
                
                # Timestamps
                c1, c2 = st.columns(2)
                with c1:
                    st.caption(f"⏱️ Iniciado: {result.get('started_at', 'N/A')[:19]}")
                with c2:
                    if result.get("completed_at"):
                        st.caption(f"✓ Completado: {result.get('completed_at')[:19]}")
                
                # Métricas
                metrics = result.get("metrics", {})
                if metrics:
                    st.markdown('<div class="metrics-grid">', unsafe_allow_html=True)
                    cols = st.columns(min(len(metrics), 4))
                    for i, (key, value) in enumerate(metrics.items()):
                        with cols[i % len(cols)]:
                            st.markdown(f"""
                            <div class="metric-item">
                                <div class="metric-label">{key}</div>
                                <div class="metric-value">{value}</div>
                            </div>
                            """, unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                
                # Pasos completados
                steps = result.get("steps_completed", [])
                if steps:
                    with st.expander("Ver pasos ejecutados"):
                        for step in steps:
                            icon = "✅" if step.get("success") else "❌"
                            st.markdown(f"{icon} {step.get('description', 'Paso')}")
                
                # Errores
                errors = result.get("errors", [])
                if errors:
                    for error in errors:
                        st.error(error)
                
                st.markdown('</div>', unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
