"""
Modern CSS styles with animations and glassmorphism effects
Supports dark and light themes with smooth transitions
Streamlit 1.32+ optimized with advanced features
"""
import streamlit as st

MODERN_CSS_DARK = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

/* ==================== PREVENT WHITE FLASH ==================== */
/* Apply background immediately to prevent white flash */
html, body, [data-testid="stAppViewContainer"], .main, [class*="main"] {
    background-color: #0f172a !important;
    transition: none !important;
}

/* CSS Variables - Dark Theme */
:root {
    --primary: #667eea;
    --primary-light: #8b9ef8;
    --primary-dark: #5568d3;
    --secondary: #764ba2;
    --accent: #f59e0b;
    --success: #10b981;
    --warning: #f59e0b;
    --danger: #ef4444;
    --info: #3b82f6;
    
    /* High contrast text colors for dark theme */
    --text-primary: #ffffff;
    --text-secondary: #e2e8f0;
    --text-muted: #94a3b8;
    --text-inverse: #0f172a;
    
    --bg-primary: #0f172a;
    --bg-secondary: #1e293b;
    --bg-tertiary: #334155;
    
    /* Improved glass effect with better contrast */
    --glass-bg: rgba(30, 41, 59, 0.5);
    --glass-bg-hover: rgba(30, 41, 59, 0.7);
    --glass-border: rgba(148, 163, 184, 0.2);
    --glass-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.5);
    
    --border-radius: 16px;
    --border-radius-lg: 24px;
    --transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

/* Light Theme Variables */
.light-theme {
    --primary: #667eea;
    --primary-light: #8b9ef8;
    --primary-dark: #5568d3;
    --secondary: #764ba2;
    
    /* High contrast text for light theme */
    --text-primary: #0f172a;
    --text-secondary: #334155;
    --text-muted: #64748b;
    --text-inverse: #ffffff;
    
    --bg-primary: #ffffff;
    --bg-secondary: #f8fafc;
    --bg-tertiary: #e2e8f0;
    
    /* Light theme glass effect */
    --glass-bg: rgba(255, 255, 255, 0.8);
    --glass-bg-hover: rgba(255, 255, 255, 0.95);
    --glass-border: rgba(30, 41, 59, 0.15);
    --glass-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.1);
}

/* Base Styles */
* {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    transition: var(--transition);
}

html, body, [data-testid="stAppViewContainer"] {
    background: linear-gradient(135deg, #1a2332 0%, #2d1b3d 100%) !important;
    background-attachment: fixed !important;
}

/* Light theme background */
.light-theme html,
.light-theme body,
.light-theme [data-testid="stAppViewContainer"] {
    background: linear-gradient(135deg, #e0e7ff 0%, #f3e8ff 100%) !important;
}

.stApp::before {
    content: '';
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: 
        radial-gradient(circle at 20% 50%, rgba(102, 126, 234, 0.1) 0%, transparent 50%),
        radial-gradient(circle at 80% 80%, rgba(118, 75, 162, 0.1) 0%, transparent 50%);
    pointer-events: none;
    z-index: 0;
}

/* Hide Streamlit branding */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}

/* ==================== SIDEBAR - CRITICAL FIX ==================== */
/* IMPORTANT: Keep sidebar button ALWAYS visible */

/* Target ALL possible selectors for the collapse button */
button[kind="header"],
button[data-testid="baseButton-header"],
button[data-testid="stSidebarNavButton"],
[data-testid="collapsedControl"],
.css-1cypcdb,
button.css-1cypcdb,
section[data-testid="stSidebar"] > button,
[class*="baseButton-header"] {
    position: fixed !important;
    left: 0 !important;
    top: 3.5rem !important;
    z-index: 999999 !important;
    visibility: visible !important;
    display: flex !important;
    opacity: 1 !important;
    pointer-events: auto !important;
    background: var(--glass-bg) !important;
    backdrop-filter: blur(10px) !important;
    border: 2px solid var(--primary) !important;
    border-radius: 0 12px 12px 0 !important;
    padding: 0.75rem !important;
    color: var(--text-primary) !important;
    box-shadow: 0 4px 16px rgba(102, 126, 234, 0.5) !important;
    cursor: pointer !important;
    transition: all 0.3s ease !important;
}

button[kind="header"]:hover,
button[data-testid="baseButton-header"]:hover,
[data-testid="collapsedControl"]:hover {
    transform: translateX(5px) scale(1.05) !important;
    border-color: var(--primary-light) !important;
    box-shadow: 0 6px 24px rgba(102, 126, 234, 0.7) !important;
}

/* Ensure button icon is visible */
button[kind="header"] svg,
button[data-testid="baseButton-header"] svg {
    color: var(--text-primary) !important;
    fill: var(--text-primary) !important;
    width: 24px !important;
    height: 24px !important;
}

/* CRITICAL: Sidebar styling - ensure always accessible */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(15, 23, 42, 0.98) 0%, rgba(30, 41, 59, 0.98) 100%) !important;
    backdrop-filter: blur(20px) !important;
    border-right: 1px solid var(--glass-border) !important;
    min-width: 250px !important;
    transition: transform 0.3s ease-in-out !important;
}

.light-theme section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(248, 250, 252, 0.98) 100%) !important;
}

/* CRITICAL: Sidebar collapse button - always visible and functional */
button[kind="header"] {
    background: var(--glass-bg) !important;
    border: 1px solid var(--glass-border) !important;
    border-radius: 0 12px 12px 0 !important;
    color: var(--text-primary) !important;
    backdrop-filter: blur(20px) !important;
    z-index: 999999 !important;
    position: fixed !important;
    left: 0 !important;
    top: 0.5rem !important;
    padding: 0.5rem !important;
    margin: 0 !important;
    cursor: pointer !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3) !important;
}

button[kind="header"]:hover {
    background: var(--glass-bg-hover) !important;
    border-color: var(--primary) !important;
    transform: translateX(3px) scale(1.05) !important;
    box-shadow: 0 6px 16px rgba(102, 126, 234, 0.4) !important;
}

button[kind="header"] svg {
    color: var(--text-primary) !important;
    fill: var(--text-primary) !important;
}

/* Alternative selector for collapse button */
[data-testid="collapsedControl"] {
    background: var(--glass-bg) !important;
    border: 1px solid var(--glass-border) !important;
    border-radius: 0 12px 12px 0 !important;
    color: var(--text-primary) !important;
    backdrop-filter: blur(20px) !important;
    z-index: 999999 !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3) !important;
}

[data-testid="collapsedControl"]:hover {
    background: var(--glass-bg-hover) !important;
    border-color: var(--primary) !important;
    transform: translateX(3px) !important;
    box-shadow: 0 6px 16px rgba(102, 126, 234, 0.4) !important;
}

/* Ensure sidebar content is always visible */
section[data-testid="stSidebar"] > div {
    background: transparent !important;
}

section[data-testid="stSidebar"] [data-testid="stSidebarNav"] {
    background: transparent !important;
    padding-top: 3rem !important;
}

/* Sidebar content text - high contrast */
section[data-testid="stSidebar"] * {
    color: var(--text-primary) !important;
}

section[data-testid="stSidebar"] .stMarkdown p,
section[data-testid="stSidebar"] label {
    color: var(--text-primary) !important;
}

section[data-testid="stSidebar"] .stMarkdown h3,
section[data-testid="stSidebar"] .stMarkdown h2,
section[data-testid="stSidebar"] .stMarkdown h1 {
    color: var(--text-primary) !important;
    font-weight: 700 !important;
}

/* Ensure sidebar doesn't get cut off */
section[data-testid="stSidebar"][aria-expanded="true"] {
    min-width: 250px !important;
    max-width: 350px !important;
}

section[data-testid="stSidebar"][aria-expanded="false"] {
    min-width: 0 !important;
    width: 0 !important;
}


/* Glass Panel - improved contrast */
.glass-panel {
    background: var(--glass-bg) !important;
    backdrop-filter: blur(20px) saturate(180%) !important;
    -webkit-backdrop-filter: blur(20px) saturate(180%) !important;
    border: 1px solid var(--glass-border) !important;
    border-radius: var(--border-radius) !important;
    padding: 1.5rem !important;
    box-shadow: var(--glass-shadow) !important;
    transition: var(--transition) !important;
    animation: fadeInUp 0.6s ease-out !important;
}

.glass-panel:hover {
    transform: translateY(-4px) !important;
    box-shadow: 0 12px 48px 0 rgba(0, 0, 0, 0.3) !important;
    background: var(--glass-bg-hover) !important;
}

.glass-panel * {
    color: var(--text-primary) !important;
}

/* Animated Header */
@keyframes fadeInDown {
    from {
        opacity: 0;
        transform: translateY(-30px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

@keyframes fadeInUp {
    from {
        opacity: 0;
        transform: translateY(30px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

@keyframes slideInLeft {
    from {
        opacity: 0;
        transform: translateX(-50px);
    }
    to {
        opacity: 1;
        transform: translateX(0);
    }
}

@keyframes pulse {
    0%, 100% {
        opacity: 1;
    }
    50% {
        opacity: 0.5;
    }
}

@keyframes spin {
    from {
        transform: rotate(0deg);
    }
    to {
        transform: rotate(360deg);
    }
}

/* Feature Cards Grid - better text contrast */
.features-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 1.5rem;
    margin: 2rem 0;
}

.feature-card {
    background: var(--glass-bg) !important;
    backdrop-filter: blur(20px) !important;
    border: 1px solid var(--glass-border) !important;
    border-radius: var(--border-radius) !important;
    padding: 2rem !important;
    text-align: center !important;
    transition: var(--transition) !important;
    animation: fadeInUp 0.6s ease-out !important;
}

.feature-card:hover {
    transform: translateY(-8px) scale(1.02) !important;
    border-color: var(--primary) !important;
    box-shadow: 0 20px 60px rgba(102, 126, 234, 0.4) !important;
    background: var(--glass-bg-hover) !important;
}

.feature-icon {
    font-size: 3rem !important;
    margin-bottom: 1rem !important;
    animation: pulse 2s ease-in-out infinite !important;
}

.feature-card h3 {
    color: var(--text-primary) !important;
    margin: 1rem 0 0.5rem 0 !important;
    font-size: 1.3rem !important;
    font-weight: 700 !important;
}

.feature-card p {
    color: var(--text-secondary) !important;
    font-size: 1rem !important;
    line-height: 1.6 !important;
}

/* Metric Cards */
.metric-card {
    background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
    backdrop-filter: blur(20px);
    border: 1px solid var(--glass-border);
    border-radius: var(--border-radius);
    padding: 1.5rem;
    transition: var(--transition);
    position: relative;
    overflow: hidden;
}

.metric-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 3px;
    background: linear-gradient(90deg, var(--primary), var(--secondary));
}

.metric-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 12px 40px rgba(102, 126, 234, 0.3);
}

.metric-label {
    color: var(--text-secondary);
    font-size: 0.85rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 0.5rem;
}

.metric-value {
    color: var(--text-primary);
    font-size: 2.5rem;
    font-weight: 700;
    background: linear-gradient(135deg, var(--primary), var(--secondary));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

/* File Card */
.file-card {
    background: var(--glass-bg);
    backdrop-filter: blur(20px);
    border: 1px solid var(--glass-border);
    border-radius: var(--border-radius);
    padding: 1rem;
    margin: 0.5rem 0;
    transition: var(--transition);
    display: flex;
    align-items: center;
    gap: 1rem;
}

.file-card:hover {
    background: rgba(102, 126, 234, 0.1);
    border-color: var(--primary);
    transform: translateX(8px);
}

.file-icon {
    font-size: 2rem;
    width: 50px;
    height: 50px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, var(--primary), var(--secondary));
    border-radius: 12px;
}

.file-info {
    flex: 1;
}

.file-name {
    color: var(--text-primary);
    font-weight: 600;
    font-size: 1rem;
    margin-bottom: 0.25rem;
}

.file-meta {
    color: var(--text-secondary);
    font-size: 0.85rem;
}

/* Status Badge */
.status-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.4rem 1rem;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.status-badge.online {
    background: rgba(16, 185, 129, 0.2);
    border: 1px solid var(--success);
    color: var(--success);
}

.status-badge.offline {
    background: rgba(239, 68, 68, 0.2);
    border: 1px solid var(--danger);
    color: var(--danger);
}

.status-badge::before {
    content: '';
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: currentColor;
    animation: pulse 2s ease-in-out infinite;
}

/* Buttons - better visibility */
.stButton > button {
    background: linear-gradient(135deg, var(--primary), var(--secondary)) !important;
    color: white !important;
    border: none !important;
    border-radius: 12px !important;
    padding: 0.75rem 2rem !important;
    font-weight: 600 !important;
    font-size: 1rem !important;
    transition: var(--transition) !important;
    box-shadow: 0 4px 20px rgba(102, 126, 234, 0.4) !important;
    cursor: pointer !important;
}

.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 30px rgba(102, 126, 234, 0.6) !important;
    background: linear-gradient(135deg, var(--primary-light), var(--secondary)) !important;
}

.stButton > button:active {
    transform: translateY(0px) !important;
}

/* Theme toggle button - special styling */
button[key="theme_toggle"] {
    width: 100% !important;
    background: var(--glass-bg) !important;
    border: 1px solid var(--glass-border) !important;
    color: var(--text-primary) !important;
    padding: 0.5rem !important;
    border-radius: 8px !important;
    font-size: 1.2rem !important;
}

button[key="theme_toggle"]::before {
    content: '🌙' !important;
    font-size: 1.2rem !important;
}

.light-theme button[key="theme_toggle"]::before {
    content: '☀️' !important;
}

button[key="theme_toggle"]:hover {
    background: var(--glass-bg-hover) !important;
    border-color: var(--primary) !important;
    transform: scale(1.05) !important;
}

/* Input Fields - high contrast */
.stTextInput > div > div > input,
.stSelectbox > div > div > div,
.stTextArea > div > div > textarea {
    background: var(--glass-bg) !important;
    border: 2px solid var(--glass-border) !important;
    border-radius: 12px !important;
    color: var(--text-primary) !important;
    padding: 0.75rem 1rem !important;
    transition: var(--transition) !important;
    font-size: 1rem !important;
}

.stTextInput > div > div > input::placeholder,
.stTextArea > div > div > textarea::placeholder {
    color: var(--text-muted) !important;
}

.stTextInput > div > div > input:focus,
.stSelectbox > div > div > div:focus,
.stTextArea > div > div > textarea:focus {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.2) !important;
    background: var(--glass-bg-hover) !important;
}

/* Select boxes text */
.stSelectbox label,
.stTextInput label,
.stTextArea label {
    color: var(--text-primary) !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
}

/* Dataframe - better contrast */
.stDataFrame {
    background: var(--glass-bg) !important;
    backdrop-filter: blur(20px) !important;
    border-radius: var(--border-radius) !important;
    overflow: hidden !important;
    border: 1px solid var(--glass-border) !important;
}

.stDataFrame table {
    color: var(--text-primary) !important;
}

.stDataFrame th {
    background: var(--bg-secondary) !important;
    color: var(--text-primary) !important;
    font-weight: 700 !important;
}

.stDataFrame td {
    color: var(--text-secondary) !important;
}

/* Sidebar - ensure always accessible */
.css-1d391kg, [data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(15, 23, 42, 0.98) 0%, rgba(30, 41, 59, 0.98) 100%) !important;
    backdrop-filter: blur(20px) !important;
    min-width: 250px !important;
    max-width: 300px !important;
}

.light-theme [data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(248, 250, 252, 0.98) 100%) !important;
}

/* Metrics - improved visibility */
.stMetric {
    background: var(--glass-bg) !important;
    border: 1px solid var(--glass-border) !important;
    border-radius: var(--border-radius) !important;
    padding: 1rem !important;
}

.stMetric label {
    color: var(--text-secondary) !important;
    font-weight: 600 !important;
}

.stMetric [data-testid="stMetricValue"] {
    color: var(--text-primary) !important;
    font-size: 2rem !important;
    font-weight: 700 !important;
}

.stMetric [data-testid="stMetricDelta"] {
    color: var(--success) !important;
}

/* Loading Animation */
.stSpinner > div {
    border-color: var(--primary) !important;
}

/* Toast Messages */
.stAlert {
    background: var(--glass-bg) !important;
    backdrop-filter: blur(20px) !important;
    border: 1px solid var(--glass-border) !important;
    border-radius: var(--border-radius) !important;
    color: var(--text-primary) !important;
}

/* Info boxes */
.stInfo {
    background: rgba(59, 130, 246, 0.15) !important;
    border-left: 4px solid var(--info) !important;
    color: var(--text-primary) !important;
}

.stSuccess {
    background: rgba(16, 185, 129, 0.15) !important;
    border-left: 4px solid var(--success) !important;
    color: var(--text-primary) !important;
}

.stWarning {
    background: rgba(245, 158, 11, 0.15) !important;
    border-left: 4px solid var(--warning) !important;
    color: var(--text-primary) !important;
}

.stError {
    background: rgba(239, 68, 68, 0.15) !important;
    border-left: 4px solid var(--danger) !important;
    color: var(--text-primary) !important;
}

/* Tabs - improved contrast */
.stTabs [data-baseweb="tab-list"] {
    gap: 1rem !important;
    background: transparent !important;
}

.stTabs [data-baseweb="tab"] {
    background: var(--glass-bg) !important;
    backdrop-filter: blur(20px) !important;
    border: 1px solid var(--glass-border) !important;
    border-radius: 12px !important;
    padding: 0.75rem 1.5rem !important;
    color: var(--text-secondary) !important;
    transition: var(--transition) !important;
    font-weight: 600 !important;
}

.stTabs [data-baseweb="tab"]:hover {
    background: var(--glass-bg-hover) !important;
    border-color: var(--primary) !important;
    color: var(--text-primary) !important;
}

.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, var(--primary), var(--secondary)) !important;
    color: white !important;
    border-color: transparent !important;
}

/* Radio buttons */
.stRadio > label {
    color: var(--text-primary) !important;
    font-weight: 600 !important;
}

.stRadio [data-baseweb="radio"] > div {
    background: var(--glass-bg) !important;
    border: 2px solid var(--glass-border) !important;
}

.stRadio [data-baseweb="radio"]:hover > div {
    border-color: var(--primary) !important;
}

/* Markdown text - ensure visibility */
.stMarkdown {
    color: var(--text-primary) !important;
}

.stMarkdown h1, .stMarkdown h2, .stMarkdown h3, 
.stMarkdown h4, .stMarkdown h5, .stMarkdown h6 {
    color: var(--text-primary) !important;
}

.stMarkdown p, .stMarkdown li {
    color: var(--text-secondary) !important;
}

.stMarkdown a {
    color: var(--primary) !important;
}

.stMarkdown a:hover {
    color: var(--primary-light) !important;
}

/* Expander */
.streamlit-expanderHeader {
    background: var(--glass-bg) !important;
    border: 1px solid var(--glass-border) !important;
    border-radius: 12px !important;
    color: var(--text-primary) !important;
    font-weight: 600 !important;
}

.streamlit-expanderHeader:hover {
    background: var(--glass-bg-hover) !important;
    border-color: var(--primary) !important;
}

/* Column styling */
[data-testid="column"] {
    background: transparent !important;
}

/* Progress bar */
.stProgress > div > div {
    background: linear-gradient(90deg, var(--primary), var(--secondary)) !important;
}

/* File uploader */
.stFileUploader {
    background: var(--glass-bg) !important;
    border: 2px dashed var(--glass-border) !important;
    border-radius: var(--border-radius) !important;
    padding: 2rem !important;
}

.stFileUploader:hover {
    border-color: var(--primary) !important;
    background: var(--glass-bg-hover) !important;
}

.stFileUploader label {
    color: var(--text-primary) !important;
}

/* ==================== PLOTLY CHARTS FIX ==================== */
/* Ensure Plotly charts are visible and properly styled */
.js-plotly-plot,
.plotly,
[data-testid="stPlotlyChart"],
.user-select-none {
    background: transparent !important;
    color: var(--text-primary) !important;
}

/* Plotly chart container */
.js-plotly-plot .plotly {
    background: var(--glass-bg) !important;
    border-radius: var(--border-radius) !important;
    padding: 1rem !important;
}

/* Plotly modebar (toolbar) */
.modebar {
    background: var(--glass-bg) !important;
    border-radius: 8px !important;
    padding: 0.25rem !important;
}

.modebar-btn {
    color: var(--text-primary) !important;
    fill: var(--text-primary) !important;
}

.modebar-btn:hover {
    background: var(--primary) !important;
}

/* Plotly text elements */
.js-plotly-plot .plotly text {
    fill: var(--text-primary) !important;
}

/* Plotly grid lines */
.js-plotly-plot .gridlayer path,
.js-plotly-plot .gridlayer line {
    stroke: var(--glass-border) !important;
}

/* Plotly axis lines */
.js-plotly-plot .xaxislayer path,
.js-plotly-plot .yaxislayer path {
    stroke: var(--text-secondary) !important;
}

/* Plotly legend */
.js-plotly-plot .legend {
    background: var(--glass-bg) !important;
    border: 1px solid var(--glass-border) !important;
    border-radius: 8px !important;
}

.js-plotly-plot .legend text {
    fill: var(--text-primary) !important;
}

/* Ensure SVG elements are visible */
svg.main-svg {
    background: transparent !important;
}

/* Fix for invisible charts */
.js-plotly-plot .plotly .plot-container {
    visibility: visible !important;
    opacity: 1 !important;
    display: block !important;
}

/* Light theme adjustments for Plotly */
.light-theme .js-plotly-plot text {
    fill: var(--text-primary) !important;
}

.light-theme .modebar-btn {
    color: var(--text-primary) !important;
}

</style>
"""

def inject_modern_css(theme: str = "dark"):
    """Inject simple CSS with theme support"""
    # Inject base CSS
    st.markdown(MODERN_CSS_DARK, unsafe_allow_html=True)
    
    # Apply theme class with immediate background fix
    if theme == "light":
        st.markdown("""
        <script>
            // Apply light theme immediately
            document.documentElement.classList.add('light-theme');
            document.body.classList.add('light-theme');
            document.body.style.backgroundColor = '#ffffff';
            
            // Apply to all containers
            const containers = document.querySelectorAll('[data-testid="stAppViewContainer"], .main');
            containers.forEach(el => {
                el.classList.add('light-theme');
                el.style.backgroundColor = '#ffffff';
            });
            
            // Fix header
            const headers = document.querySelectorAll('header[data-testid="stHeader"]');
            headers.forEach(h => h.style.backgroundColor = '#ffffff');
        </script>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <script>
            // Apply dark theme immediately
            document.documentElement.classList.remove('light-theme');
            document.body.classList.remove('light-theme');
            document.body.style.backgroundColor = '#0f172a';
            
            // Apply to all containers
            const containers = document.querySelectorAll('[data-testid="stAppViewContainer"], .main');
            containers.forEach(el => {
                el.classList.remove('light-theme');
                el.style.backgroundColor = '#0f172a';
            });
            
            // Fix header
            const headers = document.querySelectorAll('header[data-testid="stHeader"]');
            headers.forEach(h => h.style.backgroundColor = '#0f172a');
        </script>
        """, unsafe_allow_html=True)
    
    # CRITICAL: Fix sidebar button visibility
    st.markdown("""
    <script>
        // More aggressive approach to keep sidebar button visible
        function forceSidebarButtonVisible() {
            // Try multiple selectors
            const selectors = [
                'button[kind="header"]',
                'button[data-testid="baseButton-header"]',
                'button[data-testid="stSidebarNavButton"]',
                '[data-testid="collapsedControl"]',
                'section[data-testid="stSidebar"] > button',
                '.css-1cypcdb',
                'button.css-1cypcdb'
            ];
            
            let found = false;
            selectors.forEach(selector => {
                const buttons = document.querySelectorAll(selector);
                buttons.forEach(button => {
                    if (button) {
                        // Force inline styles (highest priority)
                        button.setAttribute('style', 
                            'position: fixed !important; ' +
                            'left: 0 !important; ' +
                            'top: 3.5rem !important; ' +
                            'z-index: 999999 !important; ' +
                            'visibility: visible !important; ' +
                            'display: flex !important; ' +
                            'opacity: 1 !important; ' +
                            'pointer-events: auto !important;'
                        );
                        found = true;
                    }
                });
            });
            
            if (found) {
                console.log('✅ Sidebar button(s) found and styled');
            }
            return found;
        }
        
        // Execute immediately and repeatedly
        forceSidebarButtonVisible();
        
        // Retry with delays
        const delays = [50, 100, 200, 300, 500, 800, 1000, 1500, 2000];
        delays.forEach(delay => {
            setTimeout(forceSidebarButtonVisible, delay);
        });
        
        // Watch for DOM changes continuously
        const observer = new MutationObserver((mutations) => {
            forceSidebarButtonVisible();
        });
        
        // Start observing immediately
        observer.observe(document.body, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ['style', 'class', 'aria-expanded']
        });
        
        // Also run on various events
        window.addEventListener('load', forceSidebarButtonVisible);
        window.addEventListener('resize', forceSidebarButtonVisible);
        document.addEventListener('DOMContentLoaded', forceSidebarButtonVisible);
        
        console.log('🔧 Sidebar button fixer initialized');
    </script>
    """, unsafe_allow_html=True)

def get_animated_header(title: str, subtitle: str = "") -> str:
    """Generate an animated header with gradient text and high contrast"""
    return f"""
    <div style="animation: fadeInDown 0.8s ease-out; text-align: center; margin: 2rem 0;">
        <h1 style="
            font-size: 3.5rem;
            font-weight: 800;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin: 0;
            text-shadow: 0 0 80px rgba(102, 126, 234, 0.5);
            filter: drop-shadow(0 4px 20px rgba(102, 126, 234, 0.3));
        ">{title}</h1>
        {f'<p style="color: var(--text-primary); font-size: 1.3rem; margin-top: 0.5rem; animation: fadeInUp 1s ease-out; font-weight: 500;">{subtitle}</p>' if subtitle else ''}
    </div>
    """

# Legacy compatibility
def inject_css(theme: str = "dark"):
    """Legacy function for backward compatibility"""
    inject_modern_css(theme)


def apply_theme(theme: str = "dark"):
    """Apply modern theme - alias for inject_modern_css"""
    inject_modern_css(theme)


def create_feature_card(icon: str, title: str, description: str) -> str:
    """Create a feature card with hover effects"""
    return f"""
    <div class="glass-effect hover-lift" style="
        padding: 2rem;
        border-radius: 1.5rem;
        height: 100%;
        transition: all 0.3s ease;
    ">
        <div style="font-size: 3rem; margin-bottom: 1rem;">{icon}</div>
        <h3 style="color: var(--text-primary); font-weight: 700; margin-bottom: 1rem;">{title}</h3>
        <p style="color: var(--text-secondary); line-height: 1.6;">{description}</p>
    </div>
    """


def create_metric_card(label: str, value: str, delta: str = None, icon: str = "📊") -> str:
    """Create a modern metric card with glassmorphism"""
    delta_html = ""
    if delta:
        delta_color = "#4ade80" if delta.startswith("+") else "#f87171"
        delta_html = f'<div style="color: {delta_color}; font-size: 0.9rem; font-weight: 600; margin-top: 0.5rem;">{delta}</div>'
    
    return f"""
    <div class="glass-effect hover-lift" style="
        padding: 1.5rem;
        border-radius: 1rem;
        text-align: center;
        transition: all 0.3s ease;
    ">
        <div style="font-size: 2rem; margin-bottom: 0.5rem;">{icon}</div>
        <div style="color: var(--text-secondary); font-size: 0.875rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem;">
            {label}
        </div>
        <div style="color: var(--text-primary); font-size: 2rem; font-weight: 700;">
            {value}
        </div>
        {delta_html}
    </div>
    """

