"""
Common utilities and helper functions for the frontend
"""
import streamlit as st
import os
from typing import Optional
from utils.api_client import ApiClient

def setup_page_config(title: str, icon: str, layout: str = "wide", initial_sidebar: str = "expanded"):
    """Configure Streamlit page with enhanced settings"""
    st.set_page_config(
        page_title=title,
        page_icon=icon,
        layout=layout,
        initial_sidebar_state=initial_sidebar,
        menu_items={
            'Get Help': 'https://github.com/Pol4720/DS-Project',
            'Report a bug': "https://github.com/Pol4720/DS-Project/issues",
            'About': "DistriSearch - Sistema de Búsqueda Distribuida v1.0"
        }
    )
    
    # CRITICAL: Prevent white flash and fix header immediately
    st.markdown("""
    <style>
        /* PREVENT WHITE FLASH - Apply dark background IMMEDIATELY */
        html, body, [data-testid="stAppViewContainer"], .main, 
        [class*="main"], [data-testid="stApp"], .stApp {
            background-color: #0f172a !important;
            transition: background-color 0s !important;
        }
        
        /* Fix header background immediately */
        header[data-testid="stHeader"] {
            background-color: #0f172a !important;
            border-bottom: 1px solid rgba(148, 163, 184, 0.2) !important;
        }
        
        /* Light theme override (when needed) */
        .light-theme html,
        .light-theme body,
        .light-theme [data-testid="stAppViewContainer"],
        .light-theme .main,
        .light-theme header[data-testid="stHeader"] {
            background-color: #ffffff !important;
        }
        
        /* FORCE sidebar button to always be visible */
        button[kind="header"],
        button[data-testid="baseButton-header"],
        [data-testid="collapsedControl"] {
            visibility: visible !important;
            display: flex !important;
            opacity: 1 !important;
            position: fixed !important;
            left: 0 !important;
            top: 3.5rem !important;
            z-index: 9999999 !important;
            pointer-events: auto !important;
        }
    </style>
    
    <script>
        // Apply dark background IMMEDIATELY before anything renders
        (function() {
            document.documentElement.style.backgroundColor = '#0f172a';
            document.body.style.backgroundColor = '#0f172a';
        })();
    </script>
    """, unsafe_allow_html=True)

def init_session_state():
    """Initialize all session state variables"""
    defaults = {
        'theme': 'dark',
        'ui_mode': 'Distribuido',
        'last_central_scan': None,
        'search_results': None,
        'search_df': None,
        'nodes_map': {},
        'selected_file_id': None,
        'last_download_url': None,
        'api_client': None
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def get_api_client() -> ApiClient:
    """Get or create API client instance"""
    if st.session_state.api_client is None:
        url = os.getenv("DISTRISEARCH_BACKEND_URL", "http://localhost:8000")
        api_key = os.getenv("DISTRISEARCH_ADMIN_API_KEY") or os.getenv("ADMIN_API_KEY")
        
        # Try to read from secrets if available
        secret_candidates = [
            os.path.join("/app", ".streamlit", "secrets.toml"),
            os.path.expanduser("~/.streamlit/secrets.toml"),
        ]
        for sp in secret_candidates:
            if os.path.exists(sp):
                try:
                    api_key = st.secrets.get("admin_api_key", api_key)
                except Exception:
                    pass
                break
        
        st.session_state.api_client = ApiClient(url, api_key=api_key)
    
    return st.session_state.api_client

def format_size(size_bytes: int) -> str:
    """Format bytes to human readable size"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"

def normalize_status(status: str) -> str:
    """Normalize node status string"""
    status_str = str(status).lower()
    if status_str.endswith('online'):
        return 'online'
    if status_str.endswith('offline'):
        return 'offline'
    return status_str
