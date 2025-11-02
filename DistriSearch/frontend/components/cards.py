"""
Custom card components with animations and modern design
"""
import streamlit as st
from typing import Optional, Dict, Any

def metric_card(label: str, value: str, delta: Optional[str] = None, icon: str = "📊"):
    """Modern metric card with glassmorphism effect"""
    delta_html = ""
    if delta:
        delta_color = "#10b981" if delta.startswith("+") else "#ef4444"
        delta_html = f'<div style="color: {delta_color}; font-size: 0.9rem; font-weight: 500; margin-top: 0.5rem;">{delta}</div>'
    
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">{icon} {label}</div>
        <div class="metric-value">{value}</div>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)

def file_card(
    name: str,
    file_type: str,
    size: str,
    node_name: str,
    status: str,
    file_id: str,
    score: Optional[float] = None,
    download_url: Optional[str] = None
):
    """Modern file result card with hover effects"""
    
    # Icon mapping
    icon_map = {
        "document": "📄",
        "image": "🖼️",
        "video": "🎬",
        "audio": "🎵",
        "other": "📦"
    }
    
    icon = icon_map.get(file_type.lower(), "📦")
    
    # Status color
    status_class = "online" if status.lower() == "online" else "offline"
    
    # Score display
    score_html = ""
    if score is not None:
        score_html = f'<span style="background: rgba(102, 126, 234, 0.2); padding: 0.25rem 0.75rem; border-radius: 12px; font-size: 0.85rem; font-weight: 600; color: #667eea;">Score: {score:.4f}</span>'
    
    # Download button
    download_btn = ""
    if download_url:
        download_btn = f'<a href="{download_url}" class="download-btn" target="_blank" style="text-decoration: none; background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 0.5rem 1rem; border-radius: 10px; font-weight: 600; font-size: 0.85rem;">⬇️ Descargar</a>'
    
    st.markdown(f"""
    <div class="file-card" style="animation: fadeInUp 0.6s ease-out;">
        <div class="file-icon">{icon}</div>
        <div class="file-info">
            <div class="file-name">{name}</div>
            <div class="file-meta">
                {size} • {node_name} • 
                <span class="status-badge {status_class}" style="display: inline-flex; align-items: center; gap: 0.3rem; padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.75rem;">
                    {status}
                </span>
                {score_html}
            </div>
        </div>
        <div>{download_btn}</div>
    </div>
    """, unsafe_allow_html=True)

def info_card(title: str, content: str, icon: str = "ℹ️", color: str = "#3b82f6"):
    """Information card with custom styling"""
    st.markdown(f"""
    <div class="glass-panel" style="border-left: 4px solid {color}; animation: slideInLeft 0.6s ease-out;">
        <h3 style="margin: 0 0 1rem 0; color: {color}; display: flex; align-items: center; gap: 0.5rem;">
            <span style="font-size: 1.5rem;">{icon}</span>
            {title}
        </h3>
        <p style="margin: 0; line-height: 1.6; color: var(--text-secondary);">{content}</p>
    </div>
    """, unsafe_allow_html=True)

def node_card(node: Dict[str, Any]):
    """Display node information in a card"""
    status = str(node.get('status', 'unknown')).lower()
    if status.endswith('online'):
        status = 'online'
        status_color = '#10b981'
    elif status.endswith('offline'):
        status = 'offline'
        status_color = '#ef4444'
    else:
        status_color = '#9ca3af'
    
    files_count = node.get('shared_files_count', 0)
    
    st.markdown(f"""
    <div class="glass-panel" style="animation: fadeInUp 0.6s ease-out;">
        <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 1rem;">
            <div>
                <h3 style="margin: 0 0 0.5rem 0; color: var(--text-primary);">🖥️ {node.get('name', 'Unknown')}</h3>
                <p style="margin: 0; color: var(--text-muted); font-size: 0.85rem; font-family: monospace;">
                    {node.get('node_id', 'N/A')}
                </p>
            </div>
            <div class="status-badge {status}">{status.upper()}</div>
        </div>
        
        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem; margin-top: 1rem;">
            <div>
                <div style="color: var(--text-muted); font-size: 0.85rem; margin-bottom: 0.25rem;">IP Address</div>
                <div style="color: var(--text-primary); font-weight: 600;">{node.get('ip_address', 'N/A')}</div>
            </div>
            <div>
                <div style="color: var(--text-muted); font-size: 0.85rem; margin-bottom: 0.25rem;">Port</div>
                <div style="color: var(--text-primary); font-weight: 600;">{node.get('port', 'N/A')}</div>
            </div>
            <div style="grid-column: 1 / -1;">
                <div style="color: var(--text-muted); font-size: 0.85rem; margin-bottom: 0.25rem;">Shared Files</div>
                <div style="color: #667eea; font-weight: 700; font-size: 1.5rem;">{files_count}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def stats_grid(stats: Dict[str, Any]):
    """Display statistics in a responsive grid"""
    st.markdown(f"""
    <div class="features-grid">
        <div class="metric-card">
            <div class="metric-label">📁 ARCHIVOS TOTALES</div>
            <div class="metric-value">{stats.get('total_files', 0)}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">🖥️ NODOS TOTALES</div>
            <div class="metric-value">{stats.get('total_nodes', 0)}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">✅ NODOS ACTIVOS</div>
            <div class="metric-value">{stats.get('active_nodes', 0)}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">📋 DUPLICADOS</div>
            <div class="metric-value">{stats.get('duplicates_count', 0)}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def empty_state(message: str, icon: str = "🔍", action_text: Optional[str] = None):
    """Display an empty state with optional action"""
    action_html = ""
    if action_text:
        action_html = f'<p style="margin-top: 1.5rem; font-size: 1rem; color: var(--primary);">👉 {action_text}</p>'
    
    st.markdown(f"""
    <div style="text-align: center; padding: 4rem 2rem; animation: fadeInUp 0.8s ease-out;">
        <div style="font-size: 5rem; margin-bottom: 1rem; opacity: 0.5; animation: pulse 2s ease-in-out infinite;">
            {icon}
        </div>
        <h2 style="color: var(--text-secondary); font-weight: 500; margin: 0;">
            {message}
        </h2>
        {action_html}
    </div>
    """, unsafe_allow_html=True)

def loading_card(message: str = "Cargando..."):
    """Display a loading state"""
    st.markdown(f"""
    <div class="glass-panel" style="text-align: center; padding: 2rem;">
        <div style="display: inline-block; width: 50px; height: 50px; border: 4px solid rgba(102, 126, 234, 0.2); border-top-color: #667eea; border-radius: 50%; animation: spin 1s linear infinite; margin-bottom: 1rem;">
        </div>
        <p style="color: var(--text-secondary); margin: 0;">{message}</p>
    </div>
    """, unsafe_allow_html=True)
