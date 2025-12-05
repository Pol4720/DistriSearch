"""
Common utilities and helper functions for the frontend
"""
import streamlit as st
from typing import Optional
from utils.api_client import ApiClient
import os
import socket

def setup_page_config(title: str, icon: str, layout: str = "wide", initial_sidebar: str = "expanded"):
    """Configure Streamlit page with enhanced settings"""
    st.set_page_config(
        page_title=title,
        page_icon=icon,
        layout=layout,
        initial_sidebar_state=initial_sidebar
    )

def init_session_state():
    """Initialize session state variables"""
    if 'search_results' not in st.session_state:
        st.session_state.search_results = None
    if 'search_df' not in st.session_state:
        st.session_state.search_df = None
    if 'nodes_map' not in st.session_state:
        st.session_state.nodes_map = {}
    if 'theme' not in st.session_state:
        st.session_state.theme = 'dark'
    if 'ui_mode' not in st.session_state:
        st.session_state.ui_mode = 'distributed'
    if 'token' not in st.session_state:
        st.session_state.token = None
    if 'username' not in st.session_state:
        st.session_state.username = None

def require_auth():
    """Require authentication to access page"""
    if 'token' not in st.session_state or not st.session_state.token:
        st.error("⚠️ Debes iniciar sesión para acceder a esta página")
        st.stop()

def get_backend_url() -> str:
    """
    ✅ NUEVA FUNCIÓN: Obtiene URL del backend de forma dinámica
    Prioridad:
    1. Variable de entorno DISTRISEARCH_BACKEND_URL
    2. Autodetección en red local
    3. Fallback a localhost
    """
    # Intento 1: Variable de entorno
    env_url = os.getenv("DISTRISEARCH_BACKEND_URL")
    if env_url:
        return env_url.rstrip('/')
    
    # Intento 2: Autodetección
    try:
        # Obtener IP de la máquina local
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        
        # Intentar conectar al backend en la misma red
        import requests
        backend_url = f"http://{local_ip}:8000"
        
        response = requests.get(f"{backend_url}/health", timeout=2)
        if response.status_code == 200:
            return backend_url
    except:
        pass
    
    # Intento 3: Probar IPs comunes de la red local
    try:
        import requests
        
        # Obtener prefijo de red
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        
        network_prefix = '.'.join(local_ip.split('.')[:-1])
        
        # Probar IPs comunes en la red (2-50)
        for i in [2, 1, 10, 100]:
            test_ip = f"{network_prefix}.{i}"
            try:
                test_url = f"http://{test_ip}:8000"
                response = requests.get(f"{test_url}/health", timeout=1)
                if response.status_code == 200:
                    st.sidebar.success(f"✅ Backend detectado automáticamente en {test_ip}")
                    return test_url
            except:
                continue
    except:
        pass
    
    # Fallback: localhost
    st.sidebar.warning("⚠️ Backend no detectado automáticamente. Usando localhost")
    return "http://localhost:8000"

def get_api_client() -> ApiClient:
    """Get configured API client instance"""
    backend_url = get_backend_url()
    api_key = os.getenv("DISTRISEARCH_ADMIN_API_KEY", "")
    token = st.session_state.get('token')
    
    return ApiClient(base_url=backend_url, api_key=api_key, token=token)

def format_size(size_bytes: int) -> str:
    """Format bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"

def normalize_status(status: str) -> str:
    """Normalize node status for display"""
    status_lower = str(status).lower()
    if 'online' in status_lower:
        return 'online'
    elif 'offline' in status_lower:
        return 'offline'
    else:
        return 'unknown'
