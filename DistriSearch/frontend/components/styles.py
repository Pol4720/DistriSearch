"""Custom CSS and helpers for light/dark themes and Streamlit widgets."""

DARK_BASE = """
<style>
:root {
  --primary:#0B5FFF;
  --primary-accent:#4D8DFF;
  --bg-gradient: radial-gradient(circle at 20% 20%, #111a2b 0%, #070b12 70%);
  --glass-bg: rgba(255,255,255,0.06);
  --glass-border: rgba(255,255,255,0.12);
  --radius:16px;
  --danger:#ff4d4f;
  --warn:#fdbc3d;
  --ok:#2ecc71;
  --text-soft:#b4c1d2;
}

body, .stApp {background: var(--bg-gradient)!important; color: #eef3fa; font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;}
header[data-testid="stHeader"], footer {visibility:hidden; height:0;}

.panel {background:linear-gradient(140deg, rgba(255,255,255,0.08), rgba(255,255,255,0.04)); backdrop-filter:blur(14px) saturate(180%); -webkit-backdrop-filter:blur(14px) saturate(180%); border:1px solid var(--glass-border); border-radius: var(--radius); padding:1.25rem 1.35rem; box-shadow:0 4px 24px -8px rgba(0,0,0,0.55);} 
.panel h2, .panel h3 {margin-top:0; letter-spacing:.5px;}

.metrics {display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:1rem; margin-bottom:1.2rem;}
.metric {position:relative; overflow:hidden; padding:1rem 1rem .85rem; border-radius:20px; background:linear-gradient(160deg,#162132,#0f1724); border:1px solid #233044; box-shadow:0 3px 14px -6px rgba(0,0,0,.6);} 
.metric h4 {font-size:.70rem; text-transform:uppercase; letter-spacing:1.2px; opacity:.7; margin:0 0 4px;} 
.metric .value {font-size:1.35rem; font-weight:600; background:linear-gradient(90deg,var(--primary), var(--primary-accent)); -webkit-background-clip:text; color:transparent;}

.badge {display:inline-flex; align-items:center; gap:6px; font-size:.65rem; font-weight:600; text-transform:uppercase; letter-spacing:1px; padding:.35rem .65rem; border-radius:30px; border:1px solid var(--glass-border); background:var(--glass-bg);} 
.badge.online {color:var(--ok);} 
.badge.offline {color:var(--danger);} 

.result-table {width:100%; border-collapse:separate; border-spacing:0 6px;}
.result-table thead th {font-size:.65rem; text-transform:uppercase; letter-spacing:1px; font-weight:600; padding:.55rem .65rem; color:#90a4be;}
.result-table tbody tr {background:linear-gradient(145deg,#182537,#0f1927); transition:.25s;}
.result-table tbody tr:hover {transform:translateY(-2px); box-shadow:0 6px 16px -6px rgba(0,0,0,.8);} 
.result-table td {padding:.65rem .75rem; font-size:.82rem; border-top:1px solid #233044; border-bottom:1px solid #233044;}
.result-table td:first-child {border-left:1px solid #233044; border-top-left-radius:12px; border-bottom-left-radius:12px;}
.result-table td:last-child {border-right:1px solid #233044; border-top-right-radius:12px; border-bottom-right-radius:12px;}

.download-btn {background:linear-gradient(90deg,var(--primary), var(--primary-accent)); color:#fff; border:none; padding:.45rem .85rem; font-size:.72rem; font-weight:600; border-radius:10px; cursor:pointer; box-shadow:0 4px 14px -5px var(--primary); letter-spacing:.5px; text-decoration:none; display:inline-block;}
.download-btn:hover {filter:brightness(1.08);} 

/* Streamlit widgets - dark */
.stTextInput > div > div > input {background:#121d2b!important; border:1px solid #233044!important; color:#d9e4f2!important; border-radius:14px;}
.stSelectbox > div > div {background:#121d2b!important; border:1px solid #233044!important; color:#b4c1d2!important; border-radius:14px;}
.stButton button {background:linear-gradient(90deg,var(--primary), var(--primary-accent))!important; border:none!important; color:#fff!important; padding:.5rem 1rem!important; border-radius:12px!important; font-weight:600!important;}

</style>
"""

LIGHT_OVERRIDE = """
<style>
body, .stApp {background:linear-gradient(160deg,#f1f5fb,#d9e4f2)!important; color:#1b2735!important;}
.panel {background:rgba(255,255,255,0.55)!important; border-color:rgba(0,0,0,0.08)!important;}
.metric {background:linear-gradient(140deg,#f3f6fb,#e2eaf3)!important; border-color:#d2dae4!important;}
.metric .value {-webkit-background-clip:text; background:linear-gradient(90deg,#0044c2,#006bff); color:transparent;}
.result-table tbody tr {background:#ffffffd9!important;}
.result-table tbody tr:hover {box-shadow:0 6px 14px -4px rgba(0,40,90,.25)!important;} 
.badge.offline {color:#c92a2f!important;}
/* Streamlit widgets - light */
.stTextInput > div > div > input {background:#ffffff!important; border:1px solid #c8d4e2!important; color:#1b2735!important;}
.stSelectbox > div > div {background:#ffffff!important; border:1px solid #c8d4e2!important; color:#1b2735!important;}
.stButton button {background:linear-gradient(90deg,#0B5FFF, #4D8DFF)!important; color:#fff!important;}
</style>
"""

def inject_css(theme: str = "dark"):
    import streamlit as st
    st.markdown(DARK_BASE, unsafe_allow_html=True)
    if theme == "light":
        st.markdown(LIGHT_OVERRIDE, unsafe_allow_html=True)
