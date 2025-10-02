# Custom CSS and small style helpers for modern look

BASE_CSS = """
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

/* Page background */
body, .stApp {
  background: var(--bg-gradient)!important;
  color: #eef3fa;
  font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
}

/* Hide default Streamlit header/footer */
header[data-testid="stHeader"], footer {visibility:hidden; height:0;}

/* Top navigation bar */
.navbar {
  position:sticky; top:0; z-index:100; backdrop-filter: blur(18px) saturate(160%);
  background:linear-gradient(135deg, rgba(255,255,255,0.08), rgba(255,255,255,0.02));
  border:1px solid var(--glass-border); border-radius: var(--radius);
  padding:0.75rem 1.25rem; margin-bottom:1rem; display:flex; align-items:center; gap:1.25rem;
}
.navbar .logo {display:flex; align-items:center; gap:.65rem; font-weight:600; font-size:1.05rem; letter-spacing:.5px;}
.navbar img {width:38px; height:38px; border-radius:10px; box-shadow:0 4px 14px -4px rgba(0,0,0,.6);}
.nav-tabs {display:flex; gap:.35rem; flex-wrap:wrap;}
.nav-tabs button {background:var(--glass-bg); border:1px solid var(--glass-border); color:#dbe7f5; padding:.55rem .95rem; border-radius:40px; cursor:pointer; font-size:.82rem; letter-spacing:.5px; transition:.25s;}
.nav-tabs button[data-active="true"] {background:linear-gradient(90deg,var(--primary),var(--primary-accent)); color:#fff; box-shadow:0 0 0 1px rgba(255,255,255,0.05), 0 4px 18px -6px var(--primary);}
.nav-tabs button:hover {border-color:var(--primary-accent);}
.theme-toggle {margin-left:auto;}
.theme-toggle button {background:var(--glass-bg); border:1px solid var(--glass-border); color:#eee; padding:.5rem .85rem; border-radius:12px; cursor:pointer; transition:.25s; font-size:.8rem;}
.theme-toggle button:hover {background:var(--primary);}

/* Glass panels */
.panel {background:linear-gradient(140deg, rgba(255,255,255,0.08), rgba(255,255,255,0.04)); backdrop-filter:blur(14px) saturate(180%); -webkit-backdrop-filter:blur(14px) saturate(180%); border:1px solid var(--glass-border); border-radius:var(--radius); padding:1.25rem 1.35rem; box-shadow:0 4px 24px -8px rgba(0,0,0,0.55);}
.panel h2, .panel h3 {margin-top:0; letter-spacing:.5px;}

/* Metric cards */
.metrics {display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:1rem; margin-bottom:1.2rem;}
.metric {position:relative; overflow:hidden; padding:1rem 1rem .85rem; border-radius:20px; background:linear-gradient(160deg,#162132,#0f1724); border:1px solid #233044; box-shadow:0 3px 14px -6px rgba(0,0,0,.6);} 
.metric h4 {font-size:.70rem; text-transform:uppercase; letter-spacing:1.2px; opacity:.7; margin:0 0 4px;} 
.metric .value {font-size:1.35rem; font-weight:600; background:linear-gradient(90deg,var(--primary), var(--primary-accent)); -webkit-background-clip:text; color:transparent;}

/* Status badge */
.badge {display:inline-flex; align-items:center; gap:6px; font-size:.65rem; font-weight:600; text-transform:uppercase; letter-spacing:1px; padding:.35rem .65rem; border-radius:30px; border:1px solid var(--glass-border); background:var(--glass-bg);}
.badge.online {color:var(--ok);}
.badge.offline {color:var(--danger);} 

/* Table styling */
.result-table {width:100%; border-collapse:separate; border-spacing:0 6px;}
.result-table thead th {font-size:.65rem; text-transform:uppercase; letter-spacing:1px; font-weight:600; padding:.55rem .65rem; color:#90a4be;}
.result-table tbody tr {background:linear-gradient(145deg,#182537,#0f1927); transition:.25s;}
.result-table tbody tr:hover {transform:translateY(-2px); box-shadow:0 6px 16px -6px rgba(0,0,0,.8);} 
.result-table td {padding:.65rem .75rem; font-size:.82rem; border-top:1px solid #233044; border-bottom:1px solid #233044;}
.result-table td:first-child {border-left:1px solid #233044; border-top-left-radius:12px; border-bottom-left-radius:12px;}
.result-table td:last-child {border-right:1px solid #233044; border-top-right-radius:12px; border-bottom-right-radius:12px;}

.download-btn {background:linear-gradient(90deg,var(--primary), var(--primary-accent)); color:#fff; border:none; padding:.45rem .85rem; font-size:.72rem; font-weight:600; border-radius:10px; cursor:pointer; box-shadow:0 4px 14px -5px var(--primary); letter-spacing:.5px;}
.download-btn:hover {filter:brightness(1.08);} 

.search-bar {display:flex; gap:.7rem; margin-bottom:1.1rem;}
.search-bar input {flex:1; background:#121d2b; border:1px solid #233044; border-radius:14px; padding:.75rem 1rem; color:#d9e4f2; font-size:.9rem;}
.search-bar input:focus {outline:2px solid var(--primary);}
.search-bar select {background:#121d2b; border:1px solid #233044; border-radius:14px; padding:.65rem .85rem; color:#b4c1d2; font-size:.8rem;}
.search-bar button {background:linear-gradient(90deg,var(--primary), var(--primary-accent)); border:none; color:#fff; padding:.75rem 1.2rem; border-radius:14px; font-weight:600; letter-spacing:.5px; cursor:pointer;}
.search-bar button:hover {filter:brightness(1.07);} 

.section-title {font-size:1.05rem; font-weight:600; letter-spacing:.75px; margin:1.4rem 0 .6rem;}

/* Light theme toggle (simple inversion) */
body.light-mode, .stApp.light-mode {background:linear-gradient(160deg,#f1f5fb,#d9e4f2)!important; color:#1b2735;}
.light-mode .panel {background:rgba(255,255,255,0.55); border-color:rgba(0,0,0,0.08);}
.light-mode .metric {background:linear-gradient(140deg,#f3f6fb,#e2eaf3); border-color:#d2dae4;}
.light-mode .metric .value {background:linear-gradient(90deg,#0044c2,#006bff); -webkit-background-clip:text;}
.light-mode .result-table tbody tr {background:#ffffffd9;}
.light-mode .result-table tbody tr:hover {box-shadow:0 6px 14px -4px rgba(0,40,90,.25);} 
.light-mode .search-bar input, .light-mode .search-bar select {background:#ffffff; border-color:#c8d4e2; color:#1b2735;}
.light-mode .search-bar input:focus {outline:2px solid #0B5FFF;}
.light-mode .badge.offline {color:#c92a2f;}

</style>
"""

def inject_css():
    import streamlit as st
    st.markdown(BASE_CSS, unsafe_allow_html=True)
