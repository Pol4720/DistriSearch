"""
Página de estadísticas y métricas del sistema
Con gráficos y visualizaciones interactivas
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils.helpers import setup_page_config, init_session_state, get_api_client
from components.styles import apply_theme, get_animated_header
from components.cards import stats_grid, empty_state

# Page config
setup_page_config("Estadísticas", "📊", "wide")

# Initialize
init_session_state()
api = get_api_client()

# Apply theme
apply_theme(st.session_state.theme)

# Set Plotly template and colors based on theme
plotly_template = "plotly_dark" if st.session_state.theme == "dark" else "plotly_white"
plotly_colors = {
    'dark': {'bg': 'rgba(15, 23, 42, 0.3)', 'paper': 'rgba(30, 41, 59, 0.5)', 'text': '#ffffff', 'grid': 'rgba(148, 163, 184, 0.2)'},
    'light': {'bg': 'rgba(248, 250, 252, 0.5)', 'paper': 'rgba(255, 255, 255, 0.7)', 'text': '#0f172a', 'grid': 'rgba(100, 116, 139, 0.2)'}
}
colors = plotly_colors[st.session_state.theme]

# Header
st.markdown(get_animated_header("📊 Estadísticas del Sistema", "Monitorea el rendimiento y uso"), unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Fetch statistics
try:
    with st.spinner("📊 Cargando estadísticas..."):
        stats = api.get_stats()
except Exception as e:
    st.error(f"❌ Error al obtener estadísticas: {e}")
    stats = {}

if stats:
    # Main metrics grid
    stats_grid(stats)
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    # Two column layout for charts
    col1, col2 = st.columns(2)
    
    with col1:
        # File types distribution
        if stats.get('files_by_type'):
            st.markdown("""
            <div class="glass-panel" style="padding: 1.5rem; margin-bottom: 1.5rem;">
                <h3 style="margin: 0 0 1rem 0;">📁 Distribución por Tipo</h3>
            </div>
            """, unsafe_allow_html=True)
            
            files_by_type = stats['files_by_type']
            df_types = pd.DataFrame({
                'Tipo': list(files_by_type.keys()),
                'Cantidad': list(files_by_type.values())
            })
            
            # Create a modern pie chart with Plotly
            fig = px.pie(
                df_types,
                values='Cantidad',
                names='Tipo',
                hole=0.4,
                color_discrete_sequence=px.colors.sequential.Purples_r
            )
            
            fig.update_traces(
                textposition='inside',
                textinfo='percent+label',
                hovertemplate='<b>%{label}</b><br>Cantidad: %{value}<br>Porcentaje: %{percent}<extra></extra>'
            )
            
            fig.update_layout(
                template=plotly_template,
                paper_bgcolor=colors['paper'],
                plot_bgcolor=colors['bg'],
                font=dict(color=colors['text'], size=14),
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=-0.2,
                    xanchor="center",
                    x=0.5,
                    bgcolor=colors['paper'],
                    font=dict(color=colors['text'])
                ),
                margin=dict(t=20, b=20, l=20, r=20),
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True, key="pie_types")
        
        # System health indicator
        st.markdown("""
        <div class="glass-panel" style="padding: 1.5rem; margin-top: 1.5rem;">
            <h3 style="margin: 0 0 1rem 0;">💚 Estado del Sistema</h3>
        </div>
        """, unsafe_allow_html=True)
        
        total_nodes = stats.get('total_nodes', 0)
        active_nodes = stats.get('active_nodes', 0)
        health_pct = (active_nodes / total_nodes * 100) if total_nodes > 0 else 0
        
        # Gauge chart for system health
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=health_pct,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "Disponibilidad de Nodos (%)", 'font': {'color': '#d1d5db'}},
            delta={'reference': 100, 'increasing': {'color': "#10b981"}},
            gauge={
                'axis': {'range': [None, 100], 'tickcolor': "#d1d5db"},
                'bar': {'color': "#667eea"},
                'bgcolor': "rgba(255,255,255,0.1)",
                'borderwidth': 2,
                'bordercolor': "#d1d5db",
                'steps': [
                    {'range': [0, 50], 'color': 'rgba(239, 68, 68, 0.3)'},
                    {'range': [50, 80], 'color': 'rgba(245, 158, 11, 0.3)'},
                    {'range': [80, 100], 'color': 'rgba(16, 185, 129, 0.3)'}
                ],
                'threshold': {
                    'line': {'color': "white", 'width': 4},
                    'thickness': 0.75,
                    'value': 90
                }
            }
        ))
        
        fig_gauge.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font={'color': "#d1d5db"},
            height=300,
            margin=dict(t=50, b=20, l=20, r=20)
        )
        
        st.plotly_chart(fig_gauge, use_container_width=True)
    
    with col2:
        # Bar chart for file distribution
        if stats.get('files_by_type'):
            st.markdown("""
            <div class="glass-panel" style="padding: 1.5rem; margin-bottom: 1.5rem;">
                <h3 style="margin: 0 0 1rem 0;">📊 Archivos por Categoría</h3>
            </div>
            """, unsafe_allow_html=True)
            
            fig_bar = px.bar(
                df_types,
                x='Tipo',
                y='Cantidad',
                color='Cantidad',
                color_continuous_scale='Purples'
            )
            
            fig_bar.update_traces(
                hovertemplate='<b>%{x}</b><br>Cantidad: %{y}<extra></extra>'
            )
            
            fig_bar.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#d1d5db'),
                xaxis=dict(
                    showgrid=False,
                    zeroline=False
                ),
                yaxis=dict(
                    showgrid=True,
                    gridcolor='rgba(255,255,255,0.1)',
                    zeroline=False
                ),
                showlegend=False,
                margin=dict(t=20, b=20, l=20, r=20),
                height=400
            )
            
            st.plotly_chart(fig_bar, use_container_width=True)
        
        # Nodes status
        st.markdown("""
        <div class="glass-panel" style="padding: 1.5rem; margin-top: 1.5rem;">
            <h3 style="margin: 0 0 1rem 0;">🖥️ Estado de Nodos</h3>
        </div>
        """, unsafe_allow_html=True)
        
        # Fetch nodes for detailed status
        try:
            nodes = api.get_nodes()
            online_count = sum(1 for n in nodes if 'online' in str(n.get('status', '')).lower())
            offline_count = len(nodes) - online_count
            
            fig_nodes = go.Figure(data=[
                go.Bar(
                    name='Online',
                    x=['Nodos'],
                    y=[online_count],
                    marker_color='#10b981',
                    text=[online_count],
                    textposition='auto'
                ),
                go.Bar(
                    name='Offline',
                    x=['Nodos'],
                    y=[offline_count],
                    marker_color='#ef4444',
                    text=[offline_count],
                    textposition='auto'
                )
            ])
            
            fig_nodes.update_layout(
                barmode='stack',
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#d1d5db'),
                xaxis=dict(showgrid=False, showticklabels=False),
                yaxis=dict(
                    showgrid=True,
                    gridcolor='rgba(255,255,255,0.1)'
                ),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="center",
                    x=0.5
                ),
                margin=dict(t=60, b=20, l=20, r=20),
                height=300
            )
            
            st.plotly_chart(fig_nodes, use_container_width=True)
            
        except Exception as e:
            st.warning(f"⚠️ No se pudo obtener información de nodos: {e}")
    
    # Additional metrics
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("""
    <div class="glass-panel" style="padding: 1.5rem;">
        <h3 style="margin: 0 0 1rem 0;">📈 Métricas Adicionales</h3>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        avg_files = stats.get('total_files', 0) / stats.get('total_nodes', 1)
        st.metric(
            "Archivos por Nodo (promedio)",
            f"{avg_files:.1f}",
            delta=None
        )
    
    with col2:
        duplication_rate = (stats.get('duplicates_count', 0) / stats.get('total_files', 1) * 100) if stats.get('total_files', 0) > 0 else 0
        st.metric(
            "Tasa de Duplicación",
            f"{duplication_rate:.1f}%",
            delta=None,
            help="Porcentaje de archivos duplicados respecto al total"
        )
    
    with col3:
        active_rate = (stats.get('active_nodes', 0) / stats.get('total_nodes', 1) * 100) if stats.get('total_nodes', 0) > 0 else 0
        st.metric(
            "Nodos Activos",
            f"{active_rate:.1f}%",
            delta=None
        )
    
    with col4:
        st.metric(
            "Modo Actual",
            st.session_state.ui_mode,
            delta=None
        )

else:
    empty_state(
        "No hay estadísticas disponibles",
        "📊",
        "Asegúrate de que el backend esté funcionando correctamente"
    )

# Footer with refresh option
st.markdown("<br><br>", unsafe_allow_html=True)
col1, col2, col3 = st.columns([2, 1, 2])
with col2:
    if st.button("🔄 Actualizar Estadísticas", use_container_width=True):
        st.rerun()

st.markdown("""
<div style="text-align: center; opacity: 0.6; font-size: 0.85rem; padding: 2rem 0;">
    📊 Las estadísticas se actualizan en tiempo real con cada consulta
</div>
""", unsafe_allow_html=True)
