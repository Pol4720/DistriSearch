"""
Simple Streamlit Styles - Clean and Functional
"""
import streamlit as st

SIMPLE_CSS = """
<style>
    /* ==================== THEME VARIABLES ==================== */
    :root {
        --sidebar-bg: #1e293b;
        --sidebar-text: #ffffff;
        --main-bg: #0f172a;
        --card-bg: #1e293b;
        --text-primary: #ffffff;
        --text-secondary: #e2e8f0;
        --primary: #667eea;
        --secondary: #764ba2;
    }
    
    .light-theme {
        --sidebar-bg: #f8fafc;
        --sidebar-text: #0f172a;
        --main-bg: #ffffff;
        --card-bg: #f8fafc;
        --text-primary: #0f172a;
        --text-secondary: #334155;
        --primary: #5b6fd8;
        --secondary: #6b3f9e;
    }
    
    /* ==================== SIDEBAR ==================== */
    [data-testid="stSidebar"] {
        background-color: var(--sidebar-bg) !important;
    }
    
    [data-testid="stSidebar"] * {
        color: var(--sidebar-text) !important;
    }
    
    [data-testid="stSidebar"] .stButton button {
        width: 100%;
        background: linear-gradient(135deg, var(--primary), var(--secondary));
        color: white !important;
        border: none;
        border-radius: 0.5rem;
        padding: 0.5rem 1rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    [data-testid="stSidebar"] .stButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
    }
    
    [data-testid="stSidebar"] .stButton button:disabled {
        opacity: 0.5;
        cursor: not-allowed;
        transform: none !important;
    }
    
    /* ==================== MAIN CONTENT ==================== */
    .main {
        background-color: var(--main-bg) !important;
    }
    
    [data-testid="stAppViewContainer"] {
        background-color: var(--main-bg) !important;
    }
    
    h1, h2, h3, h4, h5, h6, p, span, div, label {
        color: var(--text-primary) !important;
    }
    
    /* ==================== BUTTONS ==================== */
    .stButton button {
        background: linear-gradient(135deg, var(--primary), var(--secondary));
        color: white !important;
        border: none;
        border-radius: 0.5rem;
        padding: 0.5rem 1.5rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
    }
    
    /* ==================== INPUTS ==================== */
    .stTextInput input, .stTextArea textarea, .stSelectbox select {
        background-color: var(--card-bg) !important;
        border: 1px solid rgba(128, 128, 128, 0.3) !important;
        border-radius: 0.5rem !important;
        color: var(--text-primary) !important;
        padding: 0.5rem !important;
    }
    
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: var(--primary) !important;
        box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.2) !important;
    }
    
    /* ==================== CARDS ==================== */
    .card {
        background-color: var(--card-bg);
        border-radius: 1rem;
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    }
    
    /* ==================== TABLES ==================== */
    .dataframe {
        background-color: var(--card-bg) !important;
        border-radius: 0.5rem !important;
    }
    
    .dataframe th {
        background: linear-gradient(135deg, var(--primary), var(--secondary)) !important;
        color: white !important;
        font-weight: 600 !important;
        padding: 0.5rem !important;
    }
    
    .dataframe td {
        color: var(--text-primary) !important;
        background-color: var(--card-bg) !important;
        padding: 0.5rem !important;
    }
    
    /* ==================== TABS ==================== */
    .stTabs [data-baseweb="tab"] {
        color: var(--text-primary) !important;
        font-weight: 600;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, var(--primary), var(--secondary)) !important;
        color: white !important;
        border-radius: 0.5rem;
    }
    
    /* ==================== SCROLLBAR ==================== */
    ::-webkit-scrollbar {
        width: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: var(--card-bg);
    }
    
    ::-webkit-scrollbar-thumb {
        background: var(--primary);
        border-radius: 4px;
    }
    
    /* ==================== RESPONSIVE ==================== */
    @media (max-width: 768px) {
        .card {
            padding: 1rem;
        }
    }
</style>
"""


def apply_theme(theme: str = "dark"):
    """Apply simple theme styling"""
    st.markdown(SIMPLE_CSS, unsafe_allow_html=True)
    
    if theme == "light":
        st.markdown("""
        <script>
            document.documentElement.classList.add('light-theme');
            document.body.classList.add('light-theme');
        </script>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <script>
            document.documentElement.classList.remove('light-theme');
            document.body.classList.remove('light-theme');
        </script>
        """, unsafe_allow_html=True)
