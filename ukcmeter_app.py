"""
Vessel Stowage Calculator — v3
================================
Bonny Light crude oil/Condensate loading plan tool.

Terminology corrections (v3):
- DWT is Tropical Deadweight (at Tropical Load Line)
- Draft limit is Tropical Load Line Draft (TLD) per ILLC 1966
- Load Line zones: Nigeria is fully within Tropical Zone
- TLD = Summer Draft + (Summer Draft / 48) per convention
  (stored directly as the tropical draft in the database)
- Limits enforced: cargo volume ≤ 98% tank capacity AND
  cargo mass ≤ available Tropical DWT (after deductions)

New in v3:
- Bunker: MT, Litres, or Cubic Metres (m³)
- App icon changed to anchor/ship emoji
- Fleet browser: Notes and Ref API columns removed
- Hard limits applied to both volume and weight simultaneously
- All draft references correctly labelled as Tropical Load Line Draft
"""

import streamlit as st
import pandas as pd
import copy
import re
import io
try:
    import pdfplumber
    _PDFPLUMBER_OK = True
except ImportError:
    _PDFPLUMBER_OK = False

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG  — ship anchor icon instead of barrel
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Vessel Stowage Calculator",
    page_icon="⚓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=SF+Pro+Display:wght@300;400;500;600;700&family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

/* ── Apple / Tesla Design Tokens ───────────────────────────────────── */
:root {
  /* Backgrounds — true deep blacks, system-grey surfaces */
  --bg:        #000000;
  --surface:   #0a0a0a;
  --surface2:  #111111;
  --surface3:  #1a1a1a;
  --card:      #0d0d0d;
  --card2:     #141414;

  /* Borders — razor-thin, barely-there */
  --border:    rgba(255,255,255,0.08);
  --border2:   rgba(255,255,255,0.14);

  /* Brand — electric blue (Tesla) / sky (Apple system) */
  --accent:    #0a84ff;   /* Apple blue */
  --accent-d:  #0071e3;
  --accent2:   #ff9f0a;   /* Apple amber */
  --accent3:   #30d158;   /* Apple green */
  --danger:    #ff453a;   /* Apple red */
  --purple:    #bf5af2;   /* Apple purple */

  /* Typography */
  --text:      #f5f5f7;   /* Apple off-white */
  --text-dim:  #a1a1a6;   /* Apple secondary */
  --text-muted:#6e6e73;   /* Apple tertiary */
  --sans:      'Inter', -apple-system, BlinkMacSystemFont, 'SF Pro Display', system-ui, sans-serif;
  --mono:      'JetBrains Mono', 'SF Mono', ui-monospace, monospace;

  /* Geometry */
  --r-sm:  6px;
  --r-md:  10px;
  --r-lg:  14px;
  --r-xl:  18px;
  --r-2xl: 24px;
  --r-3xl: 32px;
}

/* ── Base ───────────────────────────────────────────────────────────── */
html, body, [class*="css"] {
  font-family: var(--sans);
  background: var(--bg);
  color: var(--text);
  font-size: 14px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}

/* ── Sidebar ─────────────────────────────────────────────────────────── */
section[data-testid="stSidebar"] {
  background: var(--surface) !important;
  border-right: 1px solid var(--border) !important;
  padding-top: 0 !important;
}
section[data-testid="stSidebar"] * { color: var(--text) !important; }
section[data-testid="stSidebar"] .block-container { padding: 0 !important; }

/* ── Main area ──────────────────────────────────────────────────────── */
.main .block-container {
  padding: 0 2rem 4rem !important;
  max-width: 100% !important;
}

/* ── Typography ─────────────────────────────────────────────────────── */
h1 { font-family: var(--sans); font-size: 1.4rem; font-weight: 700;
     color: var(--text); letter-spacing: -0.03em; margin: 0 0 0.25rem; }
h2 { font-family: var(--sans); font-size: 0.7rem; font-weight: 600;
     color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.12em;
     margin: 1.5rem 0 0.5rem; }
h3 { font-family: var(--mono); font-size: 0.8rem; font-weight: 500;
     color: var(--text-dim); margin: 0.8rem 0 0.4rem; }
p  { color: var(--text); margin: 0 0 0.5rem; }

/* ── Form elements ──────────────────────────────────────────────────── */
input[type="number"], input[type="text"], select, textarea,
div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div {
  background: var(--surface3) !important;
  border: 1px solid var(--border2) !important;
  border-radius: var(--r-md) !important;
  color: var(--text) !important;
  font-family: var(--mono) !important;
  font-size: 0.9rem !important;
  transition: border-color 0.2s, box-shadow 0.2s;
}
input:focus, div[data-baseweb="input"]:focus-within > div {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 3px rgba(10,132,255,0.18) !important;
}

/* ── Buttons ────────────────────────────────────────────────────────── */
.stButton > button {
  background: var(--accent) !important;
  color: #fff !important;
  font-family: var(--sans) !important;
  font-weight: 600 !important;
  font-size: 0.85rem !important;
  border: none !important;
  border-radius: 980px !important;
  padding: 0.55rem 1.4rem !important;
  letter-spacing: 0.01em;
  transition: opacity 0.15s, transform 0.1s;
}
.stButton > button:hover  { opacity: 0.88; }
.stButton > button:active { transform: scale(0.97); }
button[aria-label*="decrement"],
button[aria-label*="increment"] { color: var(--text-dim) !important; }

/* ── Labels ─────────────────────────────────────────────────────────── */
label {
  color: var(--text-dim) !important;
  font-size: 0.75rem !important;
  font-family: var(--sans) !important;
  font-weight: 500 !important;
  letter-spacing: 0.01em;
}
.stCaption { color: var(--text-muted) !important; font-size: 0.72rem !important; }

/* ── Tab bar ─────────────────────────────────────────────────────────── */
button[data-baseweb="tab"] {
  font-family: var(--sans) !important;
  font-size: 0.8rem !important;
  font-weight: 500 !important;
  color: var(--text-dim) !important;
  padding: 0.65rem 1.1rem !important;
  border-radius: 0 !important;
  letter-spacing: 0.01em;
}
button[data-baseweb="tab"][aria-selected="true"] {
  color: var(--accent) !important;
  font-weight: 600 !important;
  border-bottom: 2px solid var(--accent) !important;
}
div[data-baseweb="tab-list"]      { background: var(--surface) !important; border-bottom: 1px solid var(--border) !important; }
div[data-baseweb="tab-highlight"] { background: var(--accent) !important; }
div[data-baseweb="tab-border"]    { background: transparent !important; }

/* ── Expander ────────────────────────────────────────────────────────── */
details {
  background: var(--surface2) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--r-lg) !important;
  padding: 0.25rem 0 !important;
}
details > summary {
  color: var(--text-dim) !important;
  font-family: var(--sans) !important;
  font-size: 0.82rem !important;
  font-weight: 500 !important;
  padding: 0.5rem 1rem !important;
}

/* ── Apple-style cards ──────────────────────────────────────────────── */
.ukc-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--r-2xl);
  padding: 1.5rem;
  margin: 0.5rem 0;
}
.metric-card {
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  padding: 1rem 1.25rem;
  margin: 0.3rem 0;
}
.metric-label {
  font-size: 0.65rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-family: var(--sans);
  font-weight: 600;
  margin-bottom: 0.2rem;
}
.metric-value {
  font-size: 1.5rem;
  font-weight: 700;
  font-family: var(--mono);
  color: var(--text);
  line-height: 1.1;
}
.metric-unit {
  font-size: 0.75rem;
  color: var(--text-dim);
  font-family: var(--mono);
  margin-left: 4px;
}

/* ── Result panel ────────────────────────────────────────────────────── */
.result-panel {
  background: var(--surface2);
  border: 1px solid var(--border2);
  border-radius: var(--r-2xl);
  padding: 1.75rem 1.75rem 1.5rem;
  margin: 0 0 1rem;
  position: relative;
  overflow: hidden;
}
.result-panel::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--accent), var(--accent3), transparent);
}
.result-primary {
  font-size: 3.2rem;
  font-weight: 700;
  font-family: var(--mono);
  color: var(--accent);
  line-height: 1;
  letter-spacing: -0.04em;
}
.result-secondary {
  font-size: 0.85rem;
  font-family: var(--sans);
  color: var(--text-dim);
  margin-top: 0.3rem;
  font-weight: 400;
}

/* ── Score bars ──────────────────────────────────────────────────────── */
.score-bar-wrap { margin: 0.6rem 0; }
.score-bar-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.score-bar-label  { font-size: 0.72rem; font-family: var(--sans); font-weight: 500; color: var(--text-dim); }
.score-bar-val    { font-size: 0.9rem; font-weight: 700; font-family: var(--mono); }
.score-bar-bg {
  background: var(--surface3);
  border-radius: 100px;
  height: 5px;
  overflow: hidden;
}
.score-bar-fill { height: 5px; border-radius: 100px; transition: width 0.5s cubic-bezier(0.4,0,0.2,1); }

/* ── Badges ──────────────────────────────────────────────────────────── */
.badge {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 9px;
  border-radius: 980px;
  font-size: 0.62rem; font-family: var(--sans); font-weight: 700;
  letter-spacing: 0.07em; text-transform: uppercase; white-space: nowrap;
}
.badge-ok   { background: rgba(48,209,88,0.12);  color: #30d158; border: 1px solid rgba(48,209,88,0.25); }
.badge-warn { background: rgba(255,159,10,0.12); color: #ff9f0a; border: 1px solid rgba(255,159,10,0.25); }
.badge-risk { background: rgba(255,69,58,0.12);  color: #ff453a; border: 1px solid rgba(255,69,58,0.25); }
.badge-blue { background: rgba(10,132,255,0.12); color: #0a84ff; border: 1px solid rgba(10,132,255,0.25); }
.badge-lock { background: rgba(191,90,242,0.12); color: #bf5af2; border: 1px solid rgba(191,90,242,0.25); }

/* ── Info / Alert boxes ──────────────────────────────────────────────── */
.info-box {
  background: rgba(10,132,255,0.06);
  border: 1px solid rgba(10,132,255,0.15);
  border-radius: var(--r-md);
  padding: 0.7rem 1rem;
  font-size: 0.8rem; color: var(--text-dim);
  margin: 0.4rem 0; line-height: 1.55;
}
.warn-box {
  background: rgba(255,159,10,0.06);
  border: 1px solid rgba(255,159,10,0.2);
  border-radius: var(--r-md);
  padding: 0.7rem 1rem;
  font-size: 0.8rem; color: #ff9f0a;
  margin: 0.4rem 0; line-height: 1.55;
}
.danger-box {
  background: rgba(255,69,58,0.06);
  border: 1px solid rgba(255,69,58,0.2);
  border-radius: var(--r-md);
  padding: 0.7rem 1rem;
  font-size: 0.8rem; color: #ff453a;
  margin: 0.4rem 0; line-height: 1.55;
}
.limit-box {
  background: rgba(48,209,88,0.04);
  border: 1px solid rgba(48,209,88,0.15);
  border-left: 2px solid var(--accent3);
  border-radius: var(--r-md);
  padding: 0.85rem 1.1rem;
  font-size: 0.78rem; color: #30d158;
  margin: 0.4rem 0; line-height: 1.6;
  font-family: var(--mono);
}
.locked-display {
  background: rgba(191,90,242,0.06);
  border: 1px solid rgba(191,90,242,0.18);
  border-radius: var(--r-md);
  padding: 0.6rem 1rem; margin: 0.3rem 0;
}
.locked-label {
  font-size: 0.6rem; color: #bf5af2;
  text-transform: uppercase; letter-spacing: 0.12em;
  font-weight: 600; margin-bottom: 0.15rem;
}
.locked-value { font-size: 1rem; font-weight: 700; font-family: var(--mono); color: #d8b4fe; }

/* ── Right panel: Apple-style unified output card ───────────────────── */
.output-card {
  background: var(--surface2);
  border: 1px solid var(--border2);
  border-radius: var(--r-3xl);
  padding: 2rem;
  position: relative;
  overflow: hidden;
}
.output-card::before {
  content: '';
  position: absolute; top: 0; left: 0; right: 0; height: 1px;
  background: linear-gradient(90deg, transparent 5%, var(--accent) 40%, var(--accent3) 60%, transparent 95%);
}

/* ── Summary table styling ───────────────────────────────────────────── */
.summary-header {
  font-size: 0.62rem;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--text-muted);
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border);
  margin-bottom: 0.25rem;
}

/* ── Divider ─────────────────────────────────────────────────────────── */
.sec-div { border: none; border-top: 1px solid var(--border); margin: 1.5rem 0; }

/* ── App header ──────────────────────────────────────────────────────── */
.app-header {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 1.1rem 2rem 0.9rem;
  margin: -0.1rem -2rem 1.25rem;
  display: flex; align-items: center; justify-content: space-between;
  flex-wrap: wrap; gap: 0.5rem;
}
.app-header-left { display: flex; align-items: center; gap: 0.75rem; }
.app-name {
  font-size: 1.1rem; font-weight: 800;
  font-family: var(--mono); color: var(--accent);
  letter-spacing: -0.02em;
}
.app-sub { font-size: 0.68rem; color: var(--text-muted); margin-top: 1px; }
.vessel-pill {
  background: rgba(10,132,255,0.1);
  border: 1px solid rgba(10,132,255,0.2);
  border-radius: 980px;
  padding: 4px 14px;
  font-size: 0.8rem; font-weight: 600;
  font-family: var(--mono); color: var(--accent);
}

/* ── Sidebar brand ───────────────────────────────────────────────────── */
.sidebar-brand {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 1rem 1rem 0.75rem;
  margin: -1rem -1rem 0.75rem;
}
.sidebar-title { font-size: 0.95rem; font-weight: 800; font-family: var(--mono); color: var(--accent); letter-spacing: 0.04em; }
.sidebar-sub   { font-size: 0.65rem; color: var(--text-muted); margin-top: 2px; }
.sidebar-section {
  font-size: 0.6rem; font-weight: 700;
  color: var(--text-muted); text-transform: uppercase;
  letter-spacing: 0.14em; margin: 0.9rem 0 0.35rem;
}

/* ── UKC Meter wrap ──────────────────────────────────────────────────── */
.ukc-meter-wrap { display: flex; flex-direction: column; align-items: center; padding: 0.5rem 0; }

/* ── Dataframe ───────────────────────────────────────────────────────── */
[data-testid="stDataFrame"] { border-radius: var(--r-lg) !important; overflow: hidden; border: 1px solid var(--border) !important; }

/* ── Scrollbar ───────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: var(--surface); }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.15); border-radius: 10px; }
::-webkit-scrollbar-thumb:hover { background: var(--accent); }

/* ── Dark mode enforcement ───────────────────────────────────────────── */
[data-testid="stApp"],
[data-testid="stAppViewContainer"],
.stApp { background-color: #000000 !important; }
[data-testid="block-container"], .main, .main > div { background-color: #000000 !important; }

/* Widget labels */
label, .stRadio label, .stCheckbox label, .stSelectbox label,
.stNumberInput label, .stTextInput label, .stTextArea label,
.stSlider label, .stMultiSelect label, .stFileUploader label {
  color: var(--text-dim) !important; font-size: 0.75rem !important;
}
[data-testid="stCheckbox"] > label { color: var(--text) !important; font-size: 0.82rem !important; }
[data-testid="stRadio"] div[role="radiogroup"] label { color: var(--text) !important; }
section[data-testid="stSidebar"] label { color: var(--text-dim) !important; }
.stCaption, [data-testid="stCaptionContainer"] { color: var(--text-muted) !important; }
div[data-baseweb="select"] [data-testid="stMarkdownContainer"] { color: var(--text) !important; }
input[type="number"] { color: var(--text) !important; font-family: var(--mono) !important; }
[data-testid="stExpander"] summary span { color: var(--text-dim) !important; }
[data-testid="stDataFrame"] { border: 1px solid var(--border) !important; border-radius: 10px !important; }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# ██  MASTER VESSEL DATABASE
#     DWT  = Tropical Deadweight (at Tropical Load Line)
#     draft_full = Tropical Load Line Draft (TLD) per ILLC 1966
#     All operations in Nigerian waters = full Tropical Zone
# =============================================================================
_BASE_VESSELS: list[dict] = [
    # ── Mother vessels ────────────────────────────────────────────────────────
    {"name":"Alkebulan","class":"Suezmax",
     "dwt":159988,"grt":64473,"tank_m3_98":171991.2,
     "keel":50.6,"loa":274.2,"beam":48.0,"displacement":183068.1,
     "constant":500,"bunker_fw":4800,"draft_full":17.05,"block_coeff":0.8266,
     "tpc_mt_cm":118.90,"fwa_mm":385,
     "breakwater_lat":11.3,"api_ref":28.9,"note":"Suezmax mother vessel — BIA only"},
    {"name":"Green Eagle","class":"Suezmax",
     "dwt":154164,"grt":78922,"tank_m3_98":166696.0,
     "keel":49.94,"loa":274.2,"beam":48.0,"displacement":176634.0,
     "constant":500,"bunker_fw":4800,"draft_full":16.36,"block_coeff":0.8344,
     "tpc_mt_cm":117.59,"fwa_mm":368,
     "breakwater_lat":11.3,"api_ref":28.9,"note":"Suezmax mother vessel — BIA only"},
    {"name":"Bryanston","class":"Aframax",
     "dwt":108493,"grt":46904,"tank_m3_98":120859.9,
     "keel":48.0,"loa":244.26,"beam":42.03,"displacement":125786.0,
     "constant":203,"bunker_fw":4800,"draft_full":15.228,"block_coeff":0.8194,
     "tpc_mt_cm":91.904,"fwa_mm":332,
     "breakwater_lat":11.35,"api_ref":28.9,"note":"Aframax mother vessel — BIA only"},
    # ── LR-1 ─────────────────────────────────────────────────────────────────
    {"name":"MT San Barth","class":"LR-1",
     "dwt":71533,"grt":40456,"tank_m3_98":77629.5,
     "keel":47.14,"loa":219.0,"beam":32.23,"displacement":84769.0,
     "constant":203,"bunker_fw":2500,"draft_full":13.901,"block_coeff":0.8748,
     "tpc_mt_cm":67.50,"fwa_mm":307,
     "breakwater_lat":3.45,"api_ref":28.9,"note":"Permanent BIA intermediate storage; breakwater LAT 3.45 m"},
    {"name":"PRESTIGIOUS","class":"LR-1",
     "dwt":75025,"grt":31165,"tank_m3_98":75742.8,
     "keel":47.24,"loa":228.5,"beam":32.24,"displacement":88000.0,
     "constant":300,"bunker_fw":2000,"draft_full":13.8,"block_coeff":0.8771,
     "tpc_mt_cm":66.80,"fwa_mm":322,
     "breakwater_lat":11.3,"api_ref":28.9,"note":""},
    # ── MR ───────────────────────────────────────────────────────────────────
    {"name":"MT Westmore","class":"MR",
     "dwt":47418,"grt":22808,"tank_m3_98":53611.58,
     "keel":46.37,"loa":183.0,"beam":32.2,"displacement":57531.58,
     "constant":270,"bunker_fw":1500,"draft_full":12.471,"block_coeff":0.7987,
     "tpc_mt_cm":51.76,"fwa_mm":271,
     "breakwater_lat":3.45,"api_ref":28.9,"note":"Westmore storage —"},
    {"name":"MT Chapel","class":"MR",
     "dwt":48354,"grt":22050,"tank_m3_98":50332.4,
     "keel":45.55,"loa":182.5,"beam":32.23,"displacement":57863.0,
     "constant":270,"bunker_fw":1500,"draft_full":12.93,"block_coeff":0.7876,
     "tpc_mt_cm":50.26,"fwa_mm":279,
     "breakwater_lat":14.0,"api_ref":28.9,"note":"Shuttle (BV class, IMO 9254070)"},
    {"name":"MT Jasmine S","class":"MR",
     "dwt":47205,"grt":28150,"tank_m3_98":54244.97,
     "keel":46.27,"loa":179.88,"beam":32.23,"displacement":56048.0,
     "constant":270,"bunker_fw":1500,"draft_full":12.27,"block_coeff":0.8039,
     "tpc_mt_cm":50.65,"fwa_mm":270,
     "breakwater_lat":3.45,"api_ref":28.9,"note":"Jasmine S storage"},
    {"name":"MT Laphroaig","class":"MR",
     "dwt":35832.8,"grt":19707,"tank_m3_98":39944.98,
     "keel":44.11,"loa":154.31,"beam":36.03,"displacement":45364.4,
     "constant":100,"bunker_fw":1500,"draft_full":9.18,"block_coeff":0.9115,
     "tpc_mt_cm":53.87,"fwa_mm":206,
     "breakwater_lat":3.45,"api_ref":28.9,"note":"Shuttle — Chapel/JasmineS"},
    {"name":"MT Pinarello","class":"MR",
     "dwt":35832.84,"grt":19707,"tank_m3_98":39914.477,
     "keel":41.11,"loa":154.31,"beam":36.0,"displacement":45296.9,
     "constant":100,"bunker_fw":1500,"draft_full":9.203,"block_coeff":0.9086,
     "tpc_mt_cm":53.88,"fwa_mm":206,
     "breakwater_lat":3.45,"api_ref":28.9,"note":"Shuttle — Chapel/JasmineS"},
    {"name":"MT Sherlock","class":"MR",
     "dwt":35640.4,"grt":19707,"tank_m3_98":39939.857,
     "keel":39.29,"loa":154.31,"beam":36.03,"displacement":45172.0,
     "constant":100,"bunker_fw":1500,"draft_full":9.188,"block_coeff":0.8887,
     "tpc_mt_cm":53.88,"fwa_mm":206,
     "breakwater_lat":3.45,"api_ref":28.9,"note":"Shuttle — Jasmine S primary"},
    {"name":"MONTAGU","class":"MR",
     "dwt":47425.33,"grt":30032,"tank_m3_98":52219.03,
     "keel":46.95,"loa":183.0,"beam":32.2,"displacement":55000.0,
     "constant":270,"bunker_fw":1500,"draft_full":12.2,"block_coeff":0.7805,
     "tpc_mt_cm":51.80,"fwa_mm":271,
     "breakwater_lat":3.45,"api_ref":28.9,"note":""},
    # ── General Purpose ───────────────────────────────────────────────────────
    {"name":"MT Bedford","class":"General Purpose",
     "dwt":18568,"grt":14876,"tank_m3_98":26098.32,
     "keel":39.7,"loa":157.5,"beam":27.7,"displacement":25081.0,
     "constant":250,"bunker_fw":800,"draft_full":7.146,"block_coeff":0.8269,
     "tpc_mt_cm":39.22,"fwa_mm":23.90,
     "breakwater_lat":3.45,"api_ref":28.9,"note":"Ibom offshore loader"},
    {"name":"MT Bagshot","class":"General Purpose",
     "dwt":18457,"grt":9729,"tank_m3_98":20059.1,
     "keel":39.67,"loa":145.06,"beam":22.9,"displacement":23611.0,
     "constant":29,"bunker_fw":800,"draft_full":9.1,"block_coeff":0.7918,
     "tpc_mt_cm":29.73,"fwa_mm":194,
     "breakwater_lat":3.45,"api_ref":28.9,"note":"Shuttle — Barge Starturn"},
    {"name":"MT Woodstock","class":"General Purpose",
     "dwt":15761,"grt":8602,"tank_m3_98":16050.0,
     "keel":35.6,"loa":139.95,"beam":21.0,"displacement":20000.0,
     "constant":250,"bunker_fw":800,"draft_full":8.252,"block_coeff":0.8530,
     "tpc_mt_cm":27.14,"fwa_mm":179,
     "breakwater_lat":3.45,"api_ref":28.9,"note":"Shuttle — Duke (Awoba)"},
    {"name":"MT Rathbone","class":"General Purpose",
     "dwt":12590.59,"grt":7446,"tank_m3_98":13082.02,
     "keel":33.2,"loa":140.95,"beam":19.6,"displacement":16145.59,
     "constant":220,"bunker_fw":800,"draft_full":6.956,"block_coeff":0.8687,
     "tpc_mt_cm":25.58,"fwa_mm":154,
     "breakwater_lat":3.45,"api_ref":28.9,"note":"Shuttle — Ibom/Balham"},
    {"name":"MT Rahama","class":"General Purpose",
     "dwt":8318.07,"grt":6204,"tank_m3_98":8265.0,
     "keel":34.0,"loa":115.0,"beam":21.4,"displacement":11620.83,
     "constant":250,"bunker_fw":400,"draft_full":6.14,"block_coeff":0.8026,
     "tpc_mt_cm":23.444,"fwa_mm":107,
     "breakwater_lat":3.3,"api_ref":28.9,"note":"Awoba shuttle"},
    {"name":"MT Enford","class":"General Purpose",
     "dwt":17300.4,"grt":11271,"tank_m3_98":18479.62,
     "keel":39.48,"loa":144.0,"beam":23.0,"displacement":23220.61,
     "constant":250,"bunker_fw":450,"draft_full":8.983,"block_coeff":0.8036,
     "tpc_mt_cm":24.23,"fwa_mm":197,
     "breakwater_lat":3.45,"api_ref":28.9,"note":"Shuttle — Enford (BV class, IMO 9475428)"},
    {"name":"MT Santa Monica","class":"General Purpose",
     "dwt":6208.83,"grt":4126,"tank_m3_98":5819.248,
     "keel":28.5,"loa":112.01,"beam":16.2,"displacement":8761.25,
     "constant":20,"bunker_fw":300,"draft_full":6.125,"block_coeff":0.8165,
     "tpc_mt_cm":15.887,"fwa_mm":135,
     "breakwater_lat":3.45,"api_ref":28.9,"note":"Multi-field shuttle; avg API 28.9\u00b0"},
    {"name":"Balham","class":"General Purpose",
     "dwt":18535,"grt":14876,"tank_m3_98":26098.3,
     "keel":39.70,"loa":157.50,"beam":27.72,"displacement":25074.0,
     "constant":250,"bunker_fw":800,"draft_full":7.146,"block_coeff":0.8260,
     "tpc_mt_cm":39.22,"fwa_mm":156,
     "breakwater_lat":3.45,"api_ref":28.9,"note":"Shuttle — Balham (BV class, IMO 9808479)"},
    {"name":"Duke","class":"General Purpose",
     "dwt":19651,"grt":11118,"tank_m3_98":19137.0,
     "keel":38.62,"loa":140.0,"beam":23.0,"displacement":22000.0,
     "constant":200,"bunker_fw":800,"draft_full":8.5,"block_coeff":0.8317,
     "tpc_mt_cm":29.00,"fwa_mm":215,
     "breakwater_lat":3.45,"api_ref":28.9,"note":"Duke storage barge \u2014 Point D (Awoba)"},
]

# ─────────────────────────────────────────────────────────────────────────────
# FIELD API PRESETS
# ─────────────────────────────────────────────────────────────────────────────
FIELD_API_PRESETS: dict[str, float | None] = {
    "\u2014 Manual entry \u2014": None,
    "Chapel (OML 24-S/B)":    29.00,
    "JasmineS / SOKU":        43.36,
    "Westmore (Belema)":      31.10,
    "Duke / Awoba":           41.20,
    "Starturn (Petralon)":    39.54,
    "Ibom (offshore buoy)":   32.00,
    "PGM":                    36.00,
}

# ─────────────────────────────────────────────────────────────────────────────
# BREAKWATER DEPTH PRESETS
# ─────────────────────────────────────────────────────────────────────────────
DEPTH_PRESETS: dict[str, float | None] = {
    "\u2014 Manual entry \u2014":                     None,
    "San Barth \u2014 River Entrance (3.45 m LAT)":      3.45,
    "Awoba / Cawthorne Channel (3.30 m LAT)":          3.30,
    "Export Terminal / Bonny Channel (11.20 m)":       11.20,
    "Storage Position (13.00 m)":                       13.00,
    "Chapel / JasmineS bar (3.45 m LAT)":              3.45,
    "Chapel / JasmineS post-deepening (6.00 m)":       6.00,
}

# ─────────────────────────────────────────────────────────────────────────────
# ENGINEERING CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
BBL_PER_M3           = 6.28981   # ASTM barrel conversion
SEAWATER_DENSITY_NG  = 1.0255    # t/m³ — Nigerian coastal/Bonny River estuary
                                  # (tropical brackish ~25-26 ppt, 28°C) LOCKED
FRESHWATER_DENSITY   = 1.000     # t/m³
BUNKER_DENSITY_BLEND = 0.940     # t/m³ — blended HFO + MDO
# ── UKC Standards: IMO MSC/Circ.1418 · PIANC 2014 · IACS · BV/DNV-GL ──────
#
# TWO OPERATIONAL REGIMES (applied per vessel class):
#
# ① CREEK / ESTUARY OPERATIONS — Daughter/shuttle vessels (MR, LR-1, GP)
#   Operating in Bonny River, Cawthorne Channel, Awoba, terminal approaches.
#   High squat risk due to confined channel effects, uneven river bed,
#   tidal surge, density stratification and passing traffic.
#   Per IMO MSC.1/Circ.1406 and PIANC WG49 creek/estuary guidance:
#     ADEQUATE  : UKC ≥ 20% of draft  (PIANC WG49 creek minimum — confined channel)
#     MARGINAL  : UKC ≥ 10% of draft  (IACS UR S11.4 alert zone — creek approach)
#     AGROUND   : UKC <  10% of draft  (combined squat + tidal drop risk zone)
#   Absolute floors: 0.50 m (river — NPA ops standard for creek shuttle vessels)
#
# ② OPEN CHANNEL / OFFSHORE — Mother vessels (Suezmax, Aframax) at BIA
#   Operating in Bonny Channel and offshore BIA approaches — deeper water,
#   predictable hydrographic survey, open-sea swell patterns.
#   Per PIANC 2014 Table 4.1 for loaded tankers in approach channels:
#     ADEQUATE  : UKC ≥ 15% of draft  (PIANC 2014 open-water minimum)
#     MARGINAL  : UKC ≥  5% of draft  (IMO/IACS channel approach minimum)
#     AGROUND   : UKC <   5% of draft  (squatting VLCC/Suezmax risk zone)
#   Absolute floors: 0.50 m (open water — IMO standard)
#
# Creek ops use tighter thresholds because:
#   • Uncharted shoaling in Nigerian river systems adds ≥0.3 m uncertainty
#   • Squat in narrow channels (Cb effect) is 40–60% higher than open water
#   • Tidal window at bar crossings is ≤ 2 hrs — no room to anchor and wait
#   • River bed material (soft mud) gives deceptive echo sounder returns
#
UKC_PCT_ADQ_CREEK    = 0.20     # 20% draft — ADEQUATE for creek/estuary ops
UKC_PCT_MRG_CREEK    = 0.10     # 10% draft — MARGINAL for creek/estuary ops
UKC_PCT_ADQ_CHANNEL  = 0.15     # 15% draft — ADEQUATE for open channel/offshore
UKC_PCT_MRG_CHANNEL  = 0.05     #  5% draft — MARGINAL for open channel/offshore
UKC_MIN_CREEK        = 0.50     # m — creek/river absolute minimum (NPA ops standard)
UKC_MIN_OPEN         = 0.50     # m — open water absolute minimum (IMO)
# Keep legacy aliases so existing code that references these still works
UKC_PCT_ADEQUATE     = UKC_PCT_ADQ_CREEK
UKC_PCT_MARGINAL     = UKC_PCT_MRG_CREEK
UKC_MIN_RIVER        = UKC_MIN_CREEK
# Mother vessel classes (Suezmax / Aframax) — offshore channel ops, density locked
MOTHER_CLASSES       = {"Suezmax", "Aframax"}


# ─────────────────────────────────────────────────────────────────────────────
# CALCULATION FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def api_to_sg(api: float) -> float:
    """ASTM API to Specific Gravity at 60°F."""
    return 141.5 / (131.5 + api)

def m3_to_bbl(m3: float) -> float:
    return m3 * BBL_PER_M3

def bbl_to_m3(bbl: float) -> float:
    return bbl / BBL_PER_M3

def litres_to_mt(litres: float, density: float) -> float:
    return litres * density / 1_000.0

def mt_to_litres(mt: float, density: float) -> float:
    return mt * 1_000.0 / density

def m3fluid_to_mt(m3: float, density: float) -> float:
    """Convert m³ of liquid to MT given density (t/m³)."""
    return m3 * density

def mt_to_m3fluid(mt: float, density: float) -> float:
    return mt / density if density else 0.0

def lightship_mass(v: dict) -> float:
    return v["displacement"] - v["dwt"]

def classify_vessel(dwt: float) -> str:
    if dwt >= 200_000: return "VLCC"
    if dwt >= 120_000: return "Suezmax"
    if dwt >= 80_000:  return "Aframax"
    if dwt >= 55_000:  return "LR-2"
    if dwt >= 40_000:  return "LR-1"
    if dwt >= 25_000:  return "MR"
    if dwt >= 10_000:  return "General Purpose"
    return "Small Tanker"

def compute_limits(v: dict, bunker_mt: float, fw_mt: float, constant_mt: float,
                   api: float) -> dict:
    """
    Compute the two hard loading limits and the binding constraint.

    Limit 1 — Volumetric: cargo_volume ≤ tank_m3_98  (98% tank capacity)
    Limit 2 — Weight:     cargo_mass   ≤ available_tropical_dwt
                          where available_tropical_dwt = Tropical DWT − deductions

    The binding limit is whichever permits the smaller cargo quantity.

    Returns a dict with both limits expressed in both m³ and MT,
    the maximum permissible volume and mass, and which limit is binding.
    """
    sg         = api_to_sg(api)
    deductions = bunker_mt + fw_mt + constant_mt
    avail_dwt  = v["dwt"] - deductions          # available Tropical DWT for cargo

    # Limit 1: volumetric cap (98% tank capacity)
    vol_cap_m3   = v["tank_m3_98"]
    vol_cap_mt   = vol_cap_m3 * sg              # mass that fills the tank

    # Limit 2: weight cap (available Tropical DWT)
    # Max cargo volume consistent with DWT limit
    dwt_cap_mt   = max(0.0, avail_dwt)
    dwt_cap_m3   = dwt_cap_mt / sg if sg > 0 else 0.0

    # Binding = the smaller of the two volumes (most restrictive)
    if dwt_cap_m3 <= vol_cap_m3:
        binding       = "Tropical DWT"
        max_cargo_m3  = dwt_cap_m3
        max_cargo_mt  = dwt_cap_mt
    else:
        binding       = "98% Tank Capacity"
        max_cargo_m3  = vol_cap_m3
        max_cargo_mt  = vol_cap_mt

    return {
        "deductions_mt":    deductions,
        "avail_dwt_mt":     avail_dwt,
        "vol_cap_m3":       vol_cap_m3,
        "vol_cap_bbl":      m3_to_bbl(vol_cap_m3),
        "vol_cap_mt":       vol_cap_mt,
        "dwt_cap_m3":       dwt_cap_m3,
        "dwt_cap_bbl":      m3_to_bbl(dwt_cap_m3),
        "dwt_cap_mt":       dwt_cap_mt,
        "max_cargo_m3":     max_cargo_m3,
        "max_cargo_bbl":    m3_to_bbl(max_cargo_m3),
        "max_cargo_mt":     max_cargo_mt,
        "binding":          binding,
    }

def _displacement_at_draft(v: dict, draft_m: float) -> float:
    """
    Compute displacement at a given draft using the TPC-anchor method.

    Method (per IACS loading computer standards, BV NR467, DNV-GL OTG-09):
      Anchor point: tropical load line draft (TLD) and tropical displacement
      ΔM = TPC × 100 × (draft_m - TLD)    [TPC in MT/cm → ×100 for MT/m]
      Δ(draft_m) = Δ_trop + ΔM

    If the vessel has a certified TPC from Q88 (tpc_mt_cm field), use it.
    Fallback: use full-displacement proportional method (less accurate).

    Physical basis: TPC represents the actual waterplane area at the operating
    draft and is certified by the classification society from tank tests or
    in-service measurements. It is accurate to ±0.3% across the normal loading
    range, far better than the proportional method (±3-8% for tankers with
    pronounced parallel midbody).
    """
    tld  = v["draft_full"]
    disp = v["displacement"]
    if tld <= 0 or disp <= 0:
        return disp
    tpc = v.get("tpc_mt_cm")
    if tpc and tpc > 0:
        # TPC-anchor: linear around tropical load line (accurate in loading range)
        delta = tpc * 100.0 * (draft_m - tld)   # MT/cm × 100cm/m × Δdraft_m
        return disp + delta
    # Fallback — proportional method
    return (draft_m / tld) * disp


def _draft_from_displacement(v: dict, displacement_mt: float) -> float:
    """
    Inverse: draft in standard salt water (1.025 t/m³) for a given displacement.
    Uses TPC-anchor method if available, else proportional fallback.
    """
    tld  = v["draft_full"]
    disp = v["displacement"]
    if disp <= 0:
        return 0.0
    tpc = v.get("tpc_mt_cm")
    if tpc and tpc > 0:
        # draft = TLD + (Δ_target - Δ_trop) / (TPC × 100)
        return tld + (displacement_mt - disp) / (tpc * 100.0)
    # Fallback — proportional
    if disp <= 0:
        return 0.0
    return (displacement_mt / disp) * tld


def volume_to_draft(v: dict, volume_m3: float, api: float,
                    bunker_mt: float, fw_mt: float, constant_mt: float,
                    sw_density: float = SEAWATER_DENSITY_NG) -> dict:
    """
    Predict loaded draft from cargo volume with seawater density correction.

    Uses the PROPORTIONAL DISPLACEMENT method anchored to full-load hydrostatics,
    then applies the FRESH WATER ALLOWANCE (FWA) density correction per
    IACS UR L4, BV NR467 and the International Load Line Convention 1966.

    Physical basis:
      Archimedes: displacement (MT) = volume_submerged × ρ_water
      In denser water the same displacement needs LESS submerged volume → shallower draft.
      In lighter water (estuary/fresh) the vessel sinks DEEPER for the same displacement.

      draft_in_ρ = draft_in_ρ_ref × (ρ_ref / ρ_water)
      where ρ_ref = SEAWATER_DENSITY_NG (the reference for the vessel's hydrostatics)

    This correction is applied AFTER the proportional draft calculation.
    The TLD check uses the density-corrected draft (the actual operational draft).
    """
    sg         = api_to_sg(api)
    limits     = compute_limits(v, bunker_mt, fw_mt, constant_mt, api)
    tank_98    = v["tank_m3_98"]
    lightship  = lightship_mass(v)
    deductions = bunker_mt + fw_mt + constant_mt
    tld        = v["draft_full"]

    exceeds_tank         = volume_m3 > tank_98
    cargo_mass_unclamped = volume_m3 * sg
    exceeds_dwt          = cargo_mass_unclamped > limits["avail_dwt_mt"]

    volume_m3_clamped = min(volume_m3, limits["max_cargo_m3"])
    clamped           = volume_m3_clamped < volume_m3

    cargo_mass  = volume_m3_clamped * sg
    total_disp  = lightship + cargo_mass + deductions

    # Draft in standard salt water (vessel hydrostatics at ρ_ref = 1.025 t/m³)
    draft_ref   = _draft_from_displacement(v, total_disp)

    # Dock Water Allowance (DWA) correction — per ILL 1966 / IACS UR L4 / BV NR467
    #
    # The correct method uses the vessel's certified FWA from Q88 (field 1.40):
    #   DWA (mm) = FWA_mm × (ρ_ref - ρ_actual) / (ρ_ref - ρ_fresh)
    #            = FWA_mm × (1.025 - ρ_actual) / 0.025
    #
    # FWA itself = W / (4 × TPC) per IACS, where W = summer DWT in MT.
    # If the vessel has a certified FWA from Q88 (fwa_mm field), use it directly.
    # Fallback: compute FWA from TPC and summer DWT (estimated as DWT × 0.97).
    # Final fallback: simple density ratio method (least accurate).
    #
    # Physical meaning: in water of density ρ_actual < 1.025, the vessel floats
    # deeper by DWA mm. In denser water it floats shallower.
    rho_ref = 1.025   # Standard salt water for which hydrostatics are calibrated
    fwa_mm  = v.get("fwa_mm")
    tpc     = v.get("tpc_mt_cm")
    if fwa_mm and fwa_mm > 0:
        # Primary method — certified FWA from Q88 / class society
        dwa_mm  = fwa_mm * (rho_ref - sw_density) / 0.025
        draft_m = draft_ref + dwa_mm / 1000.0
        density_factor = draft_m / max(draft_ref, 0.001)
    elif tpc and tpc > 0:
        # Secondary method — compute FWA from TPC (IACS formula)
        summer_dw_est = v["dwt"] * 0.97   # summer DWT ≈ 97% of tropical DWT
        fwa_computed  = summer_dw_est / (4.0 * tpc)   # result in mm
        dwa_mm        = fwa_computed * (rho_ref - sw_density) / 0.025
        draft_m       = draft_ref + dwa_mm / 1000.0
        density_factor = draft_m / max(draft_ref, 0.001)
    else:
        # Fallback — simple Archimedes ratio (less accurate, no FWA available)
        density_factor = rho_ref / max(sw_density, 0.99)
        draft_m        = draft_ref * density_factor

    util_vol    = (volume_m3_clamped / tank_98) * 100 if tank_98 else 0
    util_dwt    = (cargo_mass / limits["avail_dwt_mt"]) * 100 if limits["avail_dwt_mt"] > 0 else 0

    return {
        "sg": sg, "limits": limits,
        "volume_requested_m3": volume_m3,
        "volume_loaded_m3":    volume_m3_clamped,
        "volume_loaded_bbl":   round(m3_to_bbl(volume_m3_clamped)),
        "volume_clamped":      clamped,
        "exceeds_tank":        exceeds_tank,
        "exceeds_dwt":         exceeds_dwt,
        "cargo_mass_mt":       cargo_mass,
        "lightship_mt":        lightship,
        "deductions_mt":       deductions,
        "total_displacement_mt": total_disp,
        "draft_m":             round(draft_m, 3),
        "draft_ref_m":         round(draft_ref, 3),    # draft in reference salt water
        "density_factor":      round(density_factor, 5),
        "tld_m":               tld,
        "over_tld":            draft_m > tld,
        "tank_98_m3":          tank_98,
        "tank_98_bbl":         round(m3_to_bbl(tank_98)),
        "tank_util_pct":       round(util_vol, 1),
        "dwt_util_pct":        round(util_dwt, 1),
    }

def draft_to_volume(v: dict, draft_m: float, api: float,
                    bunker_mt: float, fw_mt: float, constant_mt: float,
                    sw_density: float = SEAWATER_DENSITY_NG) -> dict:
    """
    Back-calculate cargo volume from a target draft with seawater density correction.

    The input draft_m is the OPERATIONAL draft in the actual water density.
    The hydrostatics are calibrated in SEAWATER_DENSITY_NG (reference salt water).
    We first convert the target draft to its reference-water equivalent before
    using the proportional displacement method.

      draft_ref = draft_actual × (ρ_actual / ρ_ref)   [FWA inverse — IACS UR L4]

    In lighter water the vessel is deeper for the same load, so we can carry MORE
    cargo to reach a given draft. This is correctly captured by converting to the
    reference draft before computing displacement.
    """
    sg         = api_to_sg(api)
    limits     = compute_limits(v, bunker_mt, fw_mt, constant_mt, api)
    lightship  = lightship_mass(v)
    deductions = bunker_mt + fw_mt + constant_mt
    tank_98    = v["tank_m3_98"]
    tld        = v["draft_full"]

    # Convert operational draft to standard salt-water equivalent (undo DWA)
    # Inverse of the DWA correction in volume_to_draft.
    # draft_ref = draft_actual - DWA_m
    # DWA_m = FWA_mm / 1000 × (ρ_ref - ρ_actual) / 0.025
    rho_ref = 1.025
    fwa_mm  = v.get("fwa_mm")
    tpc     = v.get("tpc_mt_cm")
    if fwa_mm and fwa_mm > 0:
        dwa_mm  = fwa_mm * (rho_ref - sw_density) / 0.025
        draft_ref = draft_m - dwa_mm / 1000.0
        density_factor = draft_m / max(draft_ref, 0.001)
    elif tpc and tpc > 0:
        summer_dw_est = v["dwt"] * 0.97
        fwa_computed  = summer_dw_est / (4.0 * tpc)
        dwa_mm        = fwa_computed * (rho_ref - sw_density) / 0.025
        draft_ref     = draft_m - dwa_mm / 1000.0
        density_factor = draft_m / max(draft_ref, 0.001)
    else:
        density_factor = rho_ref / max(sw_density, 0.99)
        draft_ref      = draft_m / density_factor

    # Displacement at the reference draft — proportional to full-load displacement
    total_disp      = _displacement_at_draft(v, draft_ref)
    cargo_mass_raw  = total_disp - lightship - deductions
    volume_m3_raw   = max(0.0, cargo_mass_raw / sg)

    volume_m3   = min(volume_m3_raw, limits["max_cargo_m3"])
    cargo_mass  = volume_m3 * sg
    clamped     = volume_m3 < volume_m3_raw

    util_vol  = (volume_m3 / tank_98) * 100 if tank_98 else 0
    util_dwt  = (cargo_mass / limits["avail_dwt_mt"]) * 100 if limits["avail_dwt_mt"] > 0 else 0

    return {
        "sg": sg, "limits": limits,
        "draft_input_m":    draft_m,
        "draft_ref_m":      round(draft_ref, 3),      # equivalent draft in reference salt water
        "density_factor":   round(density_factor, 5),
        "tld_m":            tld,
        "over_tld":         draft_m > tld,
        "volume_m3":        round(volume_m3, 1),
        "volume_bbl":       round(m3_to_bbl(volume_m3)),
        "volume_clamped":   clamped,
        "cargo_mass_mt":    max(0, cargo_mass),
        "lightship_mt":     lightship,
        "deductions_mt":    deductions,
        "total_displacement_mt": total_disp,
        "tank_98_m3":       tank_98,
        "tank_98_bbl":      round(m3_to_bbl(tank_98)),
        "tank_util_pct":    round(max(0, util_vol), 1),
        "dwt_util_pct":     round(max(0, util_dwt), 1),
    }

def ukc_assessment(draft_m: float, water_depth: float,
                   vessel_class: str = "") -> dict:
    """
    UKC classification per IMO MSC/Circ.1418, PIANC 2014, IACS/BV/DNV-GL.

    TWO REGIMES applied automatically by vessel class:

    ① CREEK/ESTUARY (MR, LR-1, General Purpose — shuttle vessels):
         ADEQUATE  : UKC ≥ 20% of draft  (PIANC WG49 creek minimum)
         MARGINAL  : UKC ≥ 10% of draft  (IACS UR S11.4 creek alert zone)
         AGROUND   : UKC <  10% of draft
         Floor     : 0.50 m  (NPA ops standard for creek shuttles)

    ② OPEN CHANNEL/OFFSHORE (Suezmax, Aframax — mother vessels at BIA):
         ADEQUATE  : UKC ≥ 15% of draft  (PIANC 2014 open-water minimum)
         MARGINAL  : UKC ≥  5% of draft  (IMO channel approach minimum)
         AGROUND   : UKC <   5% of draft
         Floor     : 0.50 m  (IMO standard)

    Returns: ukc_m, ukc_required_m (ADEQUATE threshold = gauge full-scale),
             marginal_m (MARGINAL threshold = amber/red boundary),
             ukc_status, regime (string label for display).
    """
    is_mother = vessel_class in MOTHER_CLASSES
    if is_mother:
        pct_adq   = UKC_PCT_ADQ_CHANNEL   # 15%
        pct_mrg   = UKC_PCT_MRG_CHANNEL   # 5%
        floor_adq = UKC_MIN_OPEN           # 0.50 m
        floor_mrg = UKC_MIN_OPEN           # 0.50 m (channel — deeper water)
        regime    = "Bonny Channel / Offshore"
    else:
        pct_adq   = UKC_PCT_ADQ_CREEK     # 20%
        pct_mrg   = UKC_PCT_MRG_CREEK     # 10%
        floor_adq = UKC_MIN_CREEK          # 0.50 m
        floor_mrg = UKC_MIN_CREEK          # 0.50 m (creek — hard NPA minimum)
        regime    = "Creek / Estuary"

    ukc        = water_depth - draft_m
    thresh_adq = max(floor_adq, draft_m * pct_adq)
    thresh_mrg = max(floor_mrg, draft_m * pct_mrg)

    if ukc >= thresh_adq:
        status = "ADEQUATE"
    elif ukc >= thresh_mrg:
        status = "MARGINAL"
    else:
        status = "AGROUND RISK"

    return {
        "ukc_m":          round(ukc, 2),
        "ukc_required_m": round(thresh_adq, 2),
        "marginal_m":     round(thresh_mrg, 2),
        "ukc_status":     status,
        "regime":         regime,
        "pct_adq":        pct_adq,
        "pct_mrg":        pct_mrg,
    }

def util_color(pct: float) -> str:
    if pct >= 95: return "#10b981"
    if pct >= 85: return "#f59e0b"
    if pct >= 70: return "#f97316"
    return "#ef4444"

def score_label(pct: float) -> tuple[str, str]:
    if pct >= 95: return "EXCELLENT", "badge-ok"
    if pct >= 85: return "GOOD",      "badge-ok"
    if pct >= 70: return "MODERATE",  "badge-warn"
    if pct >= 50: return "LOW",       "badge-warn"
    return "VERY LOW", "badge-risk"


# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────
if "vessel_db" not in st.session_state:
    st.session_state.vessel_db = {v["name"]: copy.deepcopy(v) for v in _BASE_VESSELS}

def get_db() -> dict[str, dict]:
    return st.session_state.vessel_db

def save_vessel(v: dict) -> None:
    st.session_state.vessel_db[v["name"]] = copy.deepcopy(v)

def delete_vessel(name: str) -> None:
    st.session_state.vessel_db.pop(name, None)


# ─────────────────────────────────────────────────────────────────────────────
# UI HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def score_bar(pct: float, label: str = "") -> None:
    color = util_color(pct)
    sl, sb = score_label(pct)
    st.markdown(f"""
    <div class="score-bar-wrap">
      <div class="score-bar-header">
        <span class="score-bar-label">{label}</span>
        <div style="display:flex;align-items:center;gap:6px">
          <span class="score-bar-val" style="color:{color}">{pct:.1f}%</span>
          <span class="badge {sb}">{sl}</span>
        </div>
      </div>
      <div class="score-bar-bg">
        <div class="score-bar-fill" style="width:{min(pct,100):.1f}%;background:{color}"></div>
      </div>
    </div>""", unsafe_allow_html=True)


def _ukc_svg(status, ukc, required, depth_m=None, draft_m=None, marginal_m=None, pct_adq=0.15, pct_mrg=0.05):
    """
    Calibrated UKC gauge — IMO MSC/Circ.1418 · PIANC 2014 · BV/DNV-GL.

    Arc zones anchored to real thresholds (NOT equal thirds):
      GREEN  0° → ang_adq   UKC ≥ ADEQUATE threshold
      AMBER  ang_adq→ang_mrg  MARGINAL zone
      RED    ang_mrg → 180°  AGROUND RISK

    Full scale = 2 × ADEQUATE threshold. Needle maps linearly:
      UKC = full_scale → 0° (far right / deep green)
      UKC = 0          → 180° (far left  / deep red)

    Arc fix: extend 0.5° past both endcaps to prevent rendering gap at 0° and 180°.
    """
    import math

    if status == "ADEQUATE":
        clr = "#30D158"; bg = "rgba(48,209,88,0.18)"; bc = "rgba(48,209,88,0.50)"
    elif status == "MARGINAL":
        clr = "#FF9F0A"; bg = "rgba(255,159,10,0.18)"; bc = "rgba(255,159,10,0.50)"
    else:
        clr = "#FF453A"; bg = "rgba(255,69,58,0.18)";  bc = "rgba(255,69,58,0.55)"

    thresh_adq = max(required, 0.01)
    thresh_mrg = (marginal_m if (marginal_m and marginal_m > 0)
                  else thresh_adq * (UKC_PCT_MARGINAL / UKC_PCT_ADEQUATE))
    full_scale = thresh_adq * 2.0

    # Arc boundary angles (0°=right=SAFE, 180°=left=RISK)
    ang_adq = 180.0 * (1.0 - thresh_adq / full_scale)        # always = 90°
    ang_mrg = 180.0 * max(0.5, 1.0 - thresh_mrg / full_scale)

    # Needle angle — linear mapping
    n_frac = max(0.0, min(1.0, 1.0 - ukc / full_scale))
    n_ang  = n_frac * 180.0

    VW, VH = 500, 320
    cx, cy = VW // 2, 188
    R_o, R_i, R_hub, R_ptr = 148, 104, 12, 130

    def _x(r, d): return cx + r * math.cos(math.radians(d))
    def _y(r, d): return cy - r * math.sin(math.radians(d))

    def _arc(ro, ri, a1, a2, fill):
        """Draw arc from a1→a2 with 0.5° overdraw at endcaps to prevent gap."""
        a1_r = max(-0.5, a1 - 0.5) if a1 <= 0.5 else a1
        a2_r = min(180.5, a2 + 0.5) if a2 >= 179.5 else a2
        span = abs(a2_r - a1_r)
        if span < 0.2: return ""
        lg = 1 if span > 180 else 0
        p = (f"M {_x(ro,a1_r):.3f} {_y(ro,a1_r):.3f} "
             f"A {ro} {ro} 0 {lg} 1 {_x(ro,a2_r):.3f} {_y(ro,a2_r):.3f} "
             f"L {_x(ri,a2_r):.3f} {_y(ri,a2_r):.3f} "
             f"A {ri} {ri} 0 {lg} 0 {_x(ri,a1_r):.3f} {_y(ri,a1_r):.3f} Z")
        return f'<path d="{p}" fill="{fill}"/>'

    # ── Tick marks ──────────────────────────────────────────────────────────────
    ticks = ""
    # Regular ticks every 10°, skipping positions near threshold ticks
    for deg in range(0, 181, 10):
        at_adq = abs(deg - ang_adq) < 6
        at_mrg = abs(deg - ang_mrg) < 6
        major  = (deg % 30 == 0)
        if at_adq or at_mrg:
            continue  # dedicated threshold ticks drawn separately
        r1 = R_o + 2
        r2 = R_o + (14 if major else 7)
        col = "rgba(255,255,255,0.35)" if major else "rgba(255,255,255,0.13)"
        sw  = "2" if major else "1.2"
        ticks += (f'<line x1="{_x(r1,deg):.2f}" y1="{_y(r1,deg):.2f}" '
                  f'x2="{_x(r2,deg):.2f}" y2="{_y(r2,deg):.2f}" '
                  f'stroke="{col}" stroke-width="{sw}" stroke-linecap="round"/>')

    # Dedicated threshold ticks — longer, brightly coloured
    for ang, col in [(ang_adq, "#30D158"), (ang_mrg, "#FF9F0A")]:
        r1 = R_i + 2; r2 = R_o + 20
        ticks += (f'<line x1="{_x(r1,ang):.2f}" y1="{_y(r1,ang):.2f}" '
                  f'x2="{_x(r2,ang):.2f}" y2="{_y(r2,ang):.2f}" '
                  f'stroke="{col}" stroke-width="2.5" stroke-linecap="round" opacity="0.95"/>')

    # ── Threshold % labels — offset from boundary to stay within their zone ────
    def _label_pos(ang, r_base, offset_deg=0):
        return _x(r_base, ang + offset_deg), _y(r_base, ang + offset_deg)

    lx_adq, ly_adq = _label_pos(ang_adq, R_o + 30, -14)  # green side offset
    lx_mrg, ly_mrg = _label_pos(ang_mrg, R_o + 30, +12)  # amber side offset

    adq_label = str(int(round(pct_adq * 100))) + "%"
    mrg_label = str(int(round(pct_mrg * 100))) + "%"

    # Needle geometry
    tip_x = _x(R_ptr, n_ang); tip_y = _y(R_ptr, n_ang)
    br = 18
    b1_x = cx + br * math.cos(math.radians(n_ang + 90))
    b1_y = cy - br * math.sin(math.radians(n_ang + 90))
    b2_x = cx + br * math.cos(math.radians(n_ang - 90))
    b2_y = cy - br * math.sin(math.radians(n_ang - 90))

    # Label y-positions (below baseline)
    val_y = cy + 34; unit_y = cy + 58; badge_y = cy + 84

    parts = [
        f'<svg viewBox="0 0 {VW} {VH}" xmlns="http://www.w3.org/2000/svg"',
        ' style="width:100%;display:block;max-height:275px">',
        '<defs>',
        '<radialGradient id="ibg2" cx="50%" cy="80%" r="70%">',
        '<stop offset="0%" stop-color="#1c1c1e"/>',
        '<stop offset="100%" stop-color="#070707"/></radialGradient>',
        '<filter id="glow2"><feGaussianBlur stdDeviation="3.5" result="b"/>',
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>',
        '<filter id="soft2"><feGaussianBlur stdDeviation="1.5" result="b"/>',
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>',
        '</defs>',
        f'<circle cx="{cx}" cy="{cy}" r="{R_o+22}" fill="url(#ibg2)"/>',
        _arc(R_o, R_i, 0,       ang_adq, "#30D158"),
        _arc(R_o, R_i, ang_adq, ang_mrg, "#FF9F0A"),
        _arc(R_o, R_i, ang_mrg, 180,     "#FF453A"),
        f'<line x1="{_x(R_i+1,ang_adq):.2f}" y1="{_y(R_i+1,ang_adq):.2f}"',
        f' x2="{_x(R_o-1,ang_adq):.2f}" y2="{_y(R_o-1,ang_adq):.2f}" stroke="#070707" stroke-width="2.5"/>',
        f'<line x1="{_x(R_i+1,ang_mrg):.2f}" y1="{_y(R_i+1,ang_mrg):.2f}"',
        f' x2="{_x(R_o-1,ang_mrg):.2f}" y2="{_y(R_o-1,ang_mrg):.2f}" stroke="#070707" stroke-width="2.5"/>',
        f'<path d="M {_x(R_o+1,0):.2f} {_y(R_o+1,0):.2f} A {R_o+1} {R_o+1} 0 0 1',
        f' {_x(R_o+1,180):.2f} {_y(R_o+1,180):.2f}"',
        ' fill="none" stroke="rgba(255,255,255,0.07)" stroke-width="1.5"/>',
        ticks,
        f'<text x="{_x(R_o+38,0):.2f}" y="{_y(R_o+38,0)+5:.2f}"',
        ' font-family="system-ui,sans-serif" font-size="12" font-weight="800"',
        ' fill="#30D158" text-anchor="middle">SAFE</text>',
        f'<text x="{_x(R_o+38,180):.2f}" y="{_y(R_o+38,180)+5:.2f}"',
        ' font-family="system-ui,sans-serif" font-size="12" font-weight="800"',
        ' fill="#FF453A" text-anchor="middle">RISK</text>',
        # Threshold % labels with dark pill background for readability
        f'<rect x="{lx_adq-14:.2f}" y="{ly_adq-16:.2f}" width="28" height="13" rx="6"',
        f' fill="rgba(0,0,0,0.65)"/>',
        f'<text x="{lx_adq:.2f}" y="{ly_adq-7:.2f}"',
        ' font-family="ui-monospace,monospace" font-size="10" font-weight="800"',
        f' fill="#30D158" text-anchor="middle">{adq_label}</text>',
        f'<rect x="{lx_mrg-14:.2f}" y="{ly_mrg-16:.2f}" width="28" height="13" rx="6"',
        f' fill="rgba(0,0,0,0.65)"/>',
        f'<text x="{lx_mrg:.2f}" y="{ly_mrg-7:.2f}"',
        ' font-family="ui-monospace,monospace" font-size="10" font-weight="800"',
        f' fill="#FF9F0A" text-anchor="middle">{mrg_label}</text>',
        f'<circle cx="{cx}" cy="{cy}" r="{R_i-1}" fill="#070707"',
        ' stroke="rgba(255,255,255,0.09)" stroke-width="1.5"/>',
        f'<polygon points="{tip_x+2:.2f},{tip_y+2:.2f} {b1_x+1:.2f},{b1_y+1:.2f}',
        f' {b2_x+1:.2f},{b2_y+1:.2f}" fill="rgba(0,0,0,0.55)"/>',
        f'<polygon points="{tip_x:.2f},{tip_y:.2f} {b1_x:.2f},{b1_y:.2f}',
        f' {b2_x:.2f},{b2_y:.2f}" fill="{clr}" filter="url(#soft2)"/>',
        f'<circle cx="{cx}" cy="{cy}" r="{R_hub}" fill="#070707"',
        ' stroke="rgba(255,255,255,0.20)" stroke-width="1.5"/>',
        f'<circle cx="{cx}" cy="{cy}" r="6" fill="{clr}" filter="url(#glow2)"/>',
        f'<text x="{cx}" y="{val_y}" font-family="ui-monospace,monospace"',
        f' font-size="44" font-weight="700" fill="{clr}" text-anchor="middle"',
        f' dominant-baseline="middle" filter="url(#glow2)">{ukc:.2f}</text>',
        f'<text x="{cx}" y="{unit_y}" font-family="system-ui,sans-serif"',
        ' font-size="13" font-weight="500" fill="rgba(255,255,255,0.42)"',
        ' text-anchor="middle" dominant-baseline="middle" letter-spacing="1">m UKC</text>',
        f'<rect x="{cx-64}" y="{badge_y-12}" width="128" height="24" rx="12"',
        f' fill="{bg}" stroke="{clr}" stroke-width="1.2"/>',
        f'<text x="{cx}" y="{badge_y+1}" font-family="system-ui,sans-serif"',
        ' font-size="10" font-weight="800" text-anchor="middle"',
        f' dominant-baseline="middle" letter-spacing="1" fill="{clr}">{status}</text>',
        f'<text x="{cx}" y="{VH-4}" font-family="ui-monospace,monospace" font-size="8"',
        f' fill="rgba(255,255,255,0.10)" text-anchor="middle" letter-spacing="3">',
        'UKC METER · IMO / PIANC</text>',
        '</svg>',
    ]
    return "".join(parts)


def ukc_badge(status: str, ukc: float, required: float,
              depth_m: float = None, draft_m: float = None) -> None:
    """
    UKC Meter gauge — rendered via components.html() to bypass Streamlit HTML sanitiser.
    Design: semi-circle (180°), RED-left/AMBER-centre/GREEN-right, upward triangle needle.
    Matches the reference gauge aesthetic (Image 3).
    """
    import math
    import streamlit.components.v1 as _comp

    # ── Status colours ───────────────────────────────────────────────
    if status == "ADEQUATE":
        clr = "#30D158"; bg = "rgba(48,209,88,0.15)"; bc = "rgba(48,209,88,0.45)"
    elif status == "MARGINAL":
        clr = "#FF9F0A"; bg = "rgba(255,159,10,0.15)"; bc = "rgba(255,159,10,0.45)"
    else:
        clr = "#FF453A"; bg = "rgba(255,69,58,0.15)"; bc = "rgba(255,69,58,0.50)"
    icon = {"ADEQUATE": "✓", "MARGINAL": "⚠"}.get(status, "⚠")

    # ── Status-calibrated needle ────────────────────────────────────
    # ── Status-calibrated needle — zone matches status colour exactly ────────
    # Gauge zones: 0-60° GREEN (ADEQUATE), 60-120° AMBER (MARGINAL), 120-180° RED (AGROUND RISK)
    # frac=0.0 → rightmost (very safe/green), frac=1.0 → leftmost (deep risk/red)
    if status == "ADEQUATE":
        # Map excess UKC above required into the green zone [0°, 60°]
        # Very large positive UKC → needle at far right (frac≈0)
        # UKC just at required  → needle at right edge of green (frac≈0.30)
        excess = ukc - required          # how much above minimum (>= 0)
        # cap at 3× the required so needle doesn't pile at the edge
        cap    = max(required * 3.0, 0.01)
        frac   = 0.30 * (1.0 - min(excess / cap, 1.0))   # [0, 0.30]
    elif status == "MARGINAL":
        # Map 0 <= ukc < required into the amber zone [60°, 120°]
        # ukc == required-ε → frac≈0.333 (entering amber from green side)
        # ukc == 0          → frac≈0.620 (entering red from amber side)
        t    = ukc / max(required, 0.01)   # 1.0 (just entered amber) → 0.0 (at zero)
        frac = 0.333 + (1.0 - t) * (0.620 - 0.333)
        frac = max(0.333, min(frac, 0.620))
    else:
        # AGROUND RISK: ukc < 0 — map into the red zone [120°, 180°]
        # ukc == 0-ε         → frac≈0.667 (entering red from amber side)
        # ukc == -required   → frac≈0.85
        # ukc very negative  → frac→1.0
        cap2  = max(required, 0.10)
        t2    = min(abs(ukc) / (cap2 * 2.5), 1.0)
        frac  = 0.667 + t2 * (1.0 - 0.667)
        frac  = max(0.667, min(frac, 1.0))

    # ── Geometry (semi-circle, 180° sweep) ───────────────────────────
    # Viewbox is wide to accommodate end labels
    VW, VH  = 320, 230      # canvas — extra height below baseline for labels
    cx      = VW // 2       # 160 — horizontal centre
    cy      = 145           # vertical centre — raised so arc is upper half, labels below
    R_o     = 118           # outer track radius
    R_i     = 82            # inner track radius (36px track width = chunky like reference)
    R_hub   = 10            # hub radius
    R_ptr   = 100           # needle tip reach (inside track)

    # Semi-circle: START=0° (right/east), goes CCW to 180° (left/west)
    # frac=0 → needle at 0° (right=safe/green), frac=1 → needle at 180° (left=risk/red)
    START  = 0
    SWEEP  = 180

    def _x(r, deg): return cx + r * math.cos(math.radians(deg))
    def _y(r, deg): return cy - r * math.sin(math.radians(deg))

    # Zone boundaries (CCW from right=0°):
    # Right third (0-60°): GREEN
    # Middle third (60-120°): AMBER
    # Left third (120-180°): RED
    # → reversed: a1=end_of_zone, a2=start_of_zone for our arc draw
    z_green_end   = 0          # rightmost = safe
    z_green_start = 60         # green/amber boundary
    z_amber_start = 120        # amber/red boundary
    z_red_end     = 180        # leftmost = risk

    def _arc(r_o, r_i, a_start, a_end, fill, stroke=None, sw=0):
        """Draw a donut arc CCW from a_start to a_end."""
        large = 1 if abs(a_end - a_start) > 180 else 0
        p = (
            f"M {_x(r_o,a_start):.1f} {_y(r_o,a_start):.1f} "
            f"A {r_o} {r_o} 0 {large} 1 {_x(r_o,a_end):.1f} {_y(r_o,a_end):.1f} "
            f"L {_x(r_i,a_end):.1f} {_y(r_i,a_end):.1f} "
            f"A {r_i} {r_i} 0 {large} 0 {_x(r_i,a_start):.1f} {_y(r_i,a_start):.1f} Z"
        )
        s_attr = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
        return f'<path d="{p}" fill="{fill}"{s_attr}/>'

    # ── Tick marks (5 major = every 45°, 9 minor every 20°) ─────────
    tick_svgs = []
    for i in range(10):
        ang   = i * (SWEEP / 9)   # 0° to 180° in 9 steps
        major = (i % 3 == 0)
        r1    = R_o + 2
        r2    = R_o + (12 if major else 6)
        col   = "rgba(255,255,255,0.35)" if major else "rgba(255,255,255,0.15)"
        sw    = "2" if major else "1.2"
        tick_svgs.append(
            f'<line x1="{_x(r1,ang):.1f}" y1="{_y(r1,ang):.1f}" '
            f'x2="{_x(r2,ang):.1f}" y2="{_y(r2,ang):.1f}" '
            f'stroke="{col}" stroke-width="{sw}" stroke-linecap="round"/>'
        )
    ticks = "\n  ".join(tick_svgs)

    # ── Needle (upward-pointing triangle from hub, like reference image) ─
    n_ang   = frac * SWEEP     # 0°=right=safe, 180°=left=risk
    # Triangle tip points toward arc, base straddles hub
    tip_x   = _x(R_ptr, n_ang)
    tip_y   = _y(R_ptr, n_ang)
    # Base: two points perpendicular to needle direction, close to hub
    base_r  = 14
    b1_x    = cx + base_r * math.cos(math.radians(n_ang + 90))
    b1_y    = cy - base_r * math.sin(math.radians(n_ang + 90))
    b2_x    = cx + base_r * math.cos(math.radians(n_ang - 90))
    b2_y    = cy - base_r * math.sin(math.radians(n_ang - 90))

    # ── Text layout — all labels BELOW the 180° baseline (below cy) ──
    # cy is the flat edge of the semi-circle; everything below it is free space
    val_y     = cy + 28   # UKC value — below baseline
    unit_y    = cy + 54   # "m UKC" unit label
    badge_y   = cy + 78   # status badge rect centre

    svg = f"""<svg viewBox="0 0 {VW} {VH}" xmlns="http://www.w3.org/2000/svg" style="width:100%;display:block;">
  <defs>
    <radialGradient id="inner_bg" cx="50%" cy="80%" r="70%">
      <stop offset="0%" stop-color="#1c1c1e"/>
      <stop offset="100%" stop-color="#0a0a0a"/>
    </radialGradient>
    <filter id="glow" x="-40%" y="-40%" width="180%" height="180%">
      <feGaussianBlur stdDeviation="3" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <filter id="soft" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="1.5" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <clipPath id="semiClip">
      <rect x="0" y="0" width="{VW}" height="{cy}"/>
    </clipPath>
  </defs>

  <!-- ── Background inner disc (fills full semi-circle interior) ── -->
  <circle cx="{cx}" cy="{cy}" r="{R_o+16}" fill="url(#inner_bg)"/>

  <!-- ── Track zones (semi-circle arcs, CCW: right→left) ── -->
  <!-- GREEN zone: right third (0°→60°) -->
  {_arc(R_o, R_i, 0, 60, "#30D158")}
  <!-- AMBER zone: centre third (60°→120°) -->
  {_arc(R_o, R_i, 60, 120, "#FF9F0A")}
  <!-- RED zone: left third (120°→180°) -->
  {_arc(R_o, R_i, 120, 180, "#FF453A")}

  <!-- Zone divider lines (clean separators like reference image) -->
  <line x1="{_x(R_i,60):.1f}" y1="{_y(R_i,60):.1f}" x2="{_x(R_o,60):.1f}" y2="{_y(R_o,60):.1f}" stroke="#0a0a0a" stroke-width="3"/>
  <line x1="{_x(R_i,120):.1f}" y1="{_y(R_i,120):.1f}" x2="{_x(R_o,120):.1f}" y2="{_y(R_o,120):.1f}" stroke="#0a0a0a" stroke-width="3"/>

  <!-- Outer arc border (thin gloss ring) -->
  <path d="M {_x(R_o+1,0):.1f} {_y(R_o+1,0):.1f} A {R_o+1} {R_o+1} 0 0 1 {_x(R_o+1,180):.1f} {_y(R_o+1,180):.1f}"
        fill="none" stroke="rgba(255,255,255,0.12)" stroke-width="1.5"/>

  <!-- Tick marks outside arc -->
  {ticks}

  <!-- SAFE / RISK end labels — well outside arc, never overlapping -->
  <text x="{_x(R_o+28, 0):.1f}" y="{_y(R_o+28, 0)+5:.1f}"
        font-family="system-ui,sans-serif" font-size="11" font-weight="800"
        fill="#30D158" text-anchor="middle">SAFE</text>
  <text x="{_x(R_o+28, 180):.1f}" y="{_y(R_o+28, 180)+5:.1f}"
        font-family="system-ui,sans-serif" font-size="11" font-weight="800"
        fill="#FF453A" text-anchor="middle">RISK</text>

  <!-- Inner circle clean no text inside -->
  <circle cx="{cx}" cy="{cy}" r="{R_i-1}" fill="#0a0a0a"
          stroke="rgba(255,255,255,0.14)" stroke-width="1.5"/>

  <!-- Needle shadow -->
  <polygon points="{tip_x+1.5:.1f},{tip_y+1.5:.1f} {b1_x+1:.1f},{b1_y+1:.1f} {b2_x+1:.1f},{b2_y+1:.1f}"
           fill="rgba(0,0,0,0.5)"/>

  <!-- Needle triangle -->
  <polygon points="{tip_x:.1f},{tip_y:.1f} {b1_x:.1f},{b1_y:.1f} {b2_x:.1f},{b2_y:.1f}"
           fill="{clr}" filter="url(#soft)"/>

  <!-- Hub dot -->
  <circle cx="{cx}" cy="{cy}" r="{R_hub}" fill="#0a0a0a"
          stroke="rgba(255,255,255,0.3)" stroke-width="1.5"/>
  <circle cx="{cx}" cy="{cy}" r="5" fill="{clr}" filter="url(#glow)"/>

  <!-- All labels BELOW the 180 degree baseline -->

  <!-- UKC value large centred below arc -->
  <text x="{cx}" y="{val_y}"
        font-family="ui-monospace,monospace" font-size="34" font-weight="700"
        fill="{clr}" text-anchor="middle" dominant-baseline="middle"
        filter="url(#glow)">{ukc:.2f}</text>

  <!-- m UKC unit label -->
  <text x="{cx}" y="{unit_y}"
        font-family="system-ui,sans-serif" font-size="11" font-weight="500"
        fill="rgba(255,255,255,0.55)" text-anchor="middle" dominant-baseline="middle"
        letter-spacing="1">m UKC</text>

  <!-- Status badge wide enough for AGROUND RISK -->
  <rect x="{cx-58}" y="{badge_y-11}" width="116" height="22" rx="11"
        fill="{bg}" stroke="{clr}" stroke-width="1.2"/>
  <text x="{cx}" y="{badge_y+1}"
        font-family="system-ui,sans-serif" font-size="9.5" font-weight="800"
        fill="{clr}" text-anchor="middle" dominant-baseline="middle"
        letter-spacing="1">{status}</text>

  <!-- UKC METER watermark very subtle -->
  <text x="{cx}" y="{VH-3}"
        font-family="ui-monospace,monospace" font-size="7" font-weight="500"
        fill="rgba(255,255,255,0.18)" text-anchor="middle" letter-spacing="3">
    UKC METER
  </text>
</svg>"""

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{
  background:#000;
  font-family:-apple-system,BlinkMacSystemFont,system-ui,sans-serif;
  padding:0;
  -webkit-font-smoothing:antialiased;
}}
.card{{
  background:#111111;
  border:1px solid {bc};
  border-radius:20px;
  padding:16px 20px 14px;
  width:100%;
}}
.lbl{{
  font-size:10px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;
  color:rgba(255,255,255,0.5);font-family:ui-monospace,monospace;margin-bottom:6px;
}}
.foot{{
  display:flex;justify-content:space-between;align-items:center;
  margin-top:8px;padding-top:8px;border-top:1px solid rgba(255,255,255,0.08);
}}
.req{{font-size:11.5px;color:rgba(255,255,255,0.5);}}
.req strong{{color:rgba(255,255,255,0.9);font-family:ui-monospace,monospace;font-size:12.5px;}}
.pill{{
  padding:5px 16px;border-radius:100px;font-size:10.5px;font-weight:800;
  letter-spacing:.07em;background:{bg};color:{clr};border:1px solid {bc};
}}
</style></head><body>
<div class="card">
  <div class="lbl">⚓ Under Keel Clearance (UKC)</div>
  {svg}
  <div class="foot">
    <span class="req">Min required: <strong>{required:.2f} m</strong></span>
    <span class="pill">{icon} {status}</span>
  </div>
</div>
</body></html>"""

    _comp.html(html, height=360, scrolling=False)


def limit_panel(lim: dict, api: float) -> None:
    """Display the two hard limits and the binding constraint."""
    binding_color = "#22c55e"
    st.markdown(f"""
    <div class="limit-box">
      <div style="font-size:0.7rem;letter-spacing:0.1em;color:#4ade80;margin-bottom:6px">
        &#128274; LOADING LIMITS — BOTH MUST BE SATISFIED SIMULTANEOUSLY
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
        <div>
          <div style="color:#94a3b8;font-size:0.68rem">LIMIT 1 — 98% TANK CAPACITY</div>
          <div style="font-size:1rem;font-weight:600;color:#86efac">{lim['vol_cap_bbl']:,.0f} Bbls</div>
          <div style="font-size:0.75rem;color:#86efac">{lim['vol_cap_m3']:,.1f} m³ &nbsp;/&nbsp; {lim['vol_cap_mt']:,.0f} MT</div>
        </div>
        <div>
          <div style="color:#94a3b8;font-size:0.68rem">LIMIT 2 — TROPICAL DWT AVAILABLE</div>
          <div style="font-size:1rem;font-weight:600;color:#86efac">{lim['dwt_cap_bbl']:,.0f} Bbls</div>
          <div style="font-size:0.75rem;color:#86efac">{lim['dwt_cap_m3']:,.1f} m³ &nbsp;/&nbsp; {lim['dwt_cap_mt']:,.0f} MT</div>
        </div>
      </div>
      <div style="margin-top:8px;border-top:1px solid #166534;padding-top:6px">
        <span style="color:#94a3b8;font-size:0.68rem">BINDING LIMIT: </span>
        <span style="color:{binding_color};font-weight:700;font-size:0.85rem">{lim['binding']}</span>
        <span style="color:#86efac;font-size:0.8rem;margin-left:8px">
          &#8658; Max cargo: {lim['max_cargo_bbl']:,.0f} Bbls &nbsp;/&nbsp; {lim['max_cargo_m3']:,.1f} m³ &nbsp;/&nbsp; {lim['max_cargo_mt']:,.0f} MT
        </span>
      </div>
    </div>""", unsafe_allow_html=True)

def section(title: str) -> None:
    st.markdown(f"<h2>{title}</h2>", unsafe_allow_html=True)

def kpi_row(*items) -> None:
    """Render 2-4 KPI metric cards in a horizontal strip."""
    cols = st.columns(len(items))
    for col, (label, value, unit, color) in zip(cols, items):
        with col:
            col.markdown(f"""
            <div class="metric-card">
              <div class="metric-label">{label}</div>
              <div class="metric-value" style="color:{color or 'var(--text)'}">{value}<span class="metric-unit">{unit}</span></div>
            </div>""", unsafe_allow_html=True)

def info(text: str) -> None:
    st.markdown(f'<div class="info-box">{text}</div>', unsafe_allow_html=True)

def warn(text: str) -> None:
    st.markdown(f'<div class="warn-box">&#9888; {text}</div>', unsafe_allow_html=True)

def danger(text: str) -> None:
    st.markdown(f'<div class="danger-box">&#9940; {text}</div>', unsafe_allow_html=True)

def locked_display(label: str, value: str) -> None:
    st.markdown(f"""
    <div class="locked-display">
      <div class="locked-label">&#128274; {label}</div>
      <div class="locked-value">{value}</div>
    </div>""", unsafe_allow_html=True)

def summary_df(rows: list[tuple], h: int = 380) -> None:
    """Dark-themed scrollable HTML summary table — full width, dark bg, white text."""
    import streamlit.components.v1 as _comp
    rows_html = ""
    for i, (param, value) in enumerate(rows):
        bg = "rgba(255,255,255,0.03)" if i % 2 == 0 else "transparent"
        rows_html += (
            f'<tr style="background:{bg}">' 
            f'<td style="padding:9px 14px;color:rgba(255,255,255,0.55);' 
            f'font-size:12.5px;border-bottom:1px solid rgba(255,255,255,0.06);' 
            f'white-space:nowrap">{param}</td>' 
            f'<td style="padding:9px 14px;color:#f5f5f7;font-weight:500;' 
            f'font-size:12.5px;border-bottom:1px solid rgba(255,255,255,0.06);' 
            f'font-family:\'JetBrains Mono\',ui-monospace,monospace">{value}</td>' 
            f'</tr>'
        )
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:transparent;font-family:-apple-system,BlinkMacSystemFont,'Inter',sans-serif;}}
.wrap{{background:#111111;border:1px solid rgba(255,255,255,0.1);border-radius:16px;overflow:hidden;}}
.thead tr th{{background:#0a0a0a;padding:9px 14px;text-align:left;font-size:10px;
  font-weight:700;letter-spacing:0.12em;text-transform:uppercase;
  color:rgba(255,255,255,0.35);border-bottom:1px solid rgba(255,255,255,0.1);}}
.scroll{{max-height:{h}px;overflow-y:auto;}}
.scroll::-webkit-scrollbar{{width:4px;}}
.scroll::-webkit-scrollbar-track{{background:transparent;}}
.scroll::-webkit-scrollbar-thumb{{background:rgba(255,255,255,0.15);border-radius:4px;}}
table{{width:100%;border-collapse:collapse;}}
</style></head><body>
<div class="wrap">
  <table><thead class="thead"><tr><th>Parameter</th><th>Value</th></tr></thead></table>
  <div class="scroll"><table><tbody>{rows_html}</tbody></table></div>
</div></body></html>"""
    _comp.html(html, height=h + 44, scrolling=False)


def summary_png_bytes(rows: list[tuple], title: str = "Loading Calculation Summary") -> bytes:
    """
    Render the loading summary table as a PNG image.

    Primary renderer: matplotlib (high quality, dark-themed table).
    Fallback renderer: Pillow/PIL (always available on Streamlit Cloud —
        installed as a Streamlit core dependency).

    Returns PNG bytes for st.download_button.
    """
    # ── Try matplotlib first (best output) ───────────────────────────────────
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        n     = len(rows)
        fig_h = max(4, n * 0.38 + 1.4)
        fig, ax = plt.subplots(figsize=(10, fig_h))
        fig.patch.set_facecolor("#111827")
        ax.set_facecolor("#111827")
        ax.axis("off")

        ax.text(0.5, 1.0, title, transform=ax.transAxes, ha="center", va="top",
                fontsize=15, fontweight="bold", color="#0ea5e9",
                fontfamily="monospace")

        tbl = ax.table(
            cellText=[[r[0], r[1]] for r in rows],
            colLabels=["Parameter", "Value"],
            colWidths=[0.42, 0.58],
            loc="center",
            cellLoc="left",
        )
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(9)

        for (ri, ci), cell in tbl.get_celld().items():
            cell.set_linewidth(0.5)
            if ri == 0:
                cell.set_facecolor("#1e3a5f")
                cell.set_text_props(color="#7dd3fc", fontweight="bold",
                                    fontfamily="monospace")
                cell.set_edgecolor("#0ea5e9")
            else:
                cell.set_facecolor("#1a2236" if ri % 2 == 0 else "#111827")
                cell.set_text_props(color="#e2e8f0", fontfamily="monospace")
                cell.set_edgecolor("#1e3a5f")
            cell.set_height(0.048)

        tbl.scale(1, 1.0)
        plt.tight_layout(pad=0.4)
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    except ImportError:
        pass  # matplotlib not installed — use Pillow fallback below

    # ── Pillow fallback (Streamlit Cloud core dependency) ─────────────────────
    from PIL import Image, ImageDraw, ImageFont

    # Layout constants
    W         = 1400
    ROW_H     = 44
    HEADER_H  = 52
    TITLE_H   = 60
    PAD       = 20
    COL1_W    = int(W * 0.42)
    COL2_W    = W - COL1_W

    # Colours
    BG        = (11,  15,  26)
    SURFACE   = (26,  34,  54)
    SURFACE2  = (17,  24,  39)
    HEADER_BG = (30,  58,  95)
    ACCENT    = (14, 165, 233)
    TEXT_MAIN = (226, 232, 240)
    TEXT_HDR  = (125, 211, 252)
    BORDER    = (30,  58,  95)

    n_rows  = len(rows)
    total_h = TITLE_H + HEADER_H + n_rows * ROW_H + PAD * 2

    img  = Image.new("RGB", (W, total_h), BG)
    draw = ImageDraw.Draw(img)

    # Use default PIL font (always available; no font file needed)
    try:
        font_title  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 22)
        font_header = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 16)
        font_body   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 15)
    except OSError:
        font_title = font_header = font_body = ImageFont.load_default()

    # Title
    draw.text((W // 2, PAD + 8), title, fill=ACCENT, font=font_title, anchor="mt")

    # Header row
    hy = TITLE_H + PAD
    draw.rectangle([0, hy, W, hy + HEADER_H], fill=HEADER_BG)
    draw.text((PAD + 6, hy + 14), "Parameter", fill=TEXT_HDR, font=font_header)
    draw.text((COL1_W + PAD + 6, hy + 14), "Value", fill=TEXT_HDR, font=font_header)
    draw.line([(COL1_W, hy), (COL1_W, hy + HEADER_H)], fill=ACCENT, width=1)
    draw.line([(0, hy + HEADER_H), (W, hy + HEADER_H)], fill=ACCENT, width=1)

    # Data rows
    for i, (param, value) in enumerate(rows):
        ry   = TITLE_H + PAD + HEADER_H + i * ROW_H
        fill = SURFACE if i % 2 == 0 else SURFACE2
        draw.rectangle([0, ry, W, ry + ROW_H], fill=fill)
        draw.text((PAD + 6,         ry + 12), str(param)[:55], fill=TEXT_MAIN, font=font_body)
        draw.text((COL1_W + PAD + 6, ry + 12), str(value)[:70], fill=TEXT_MAIN, font=font_body)
        draw.line([(COL1_W, ry), (COL1_W, ry + ROW_H)], fill=BORDER, width=1)
        draw.line([(0, ry + ROW_H), (W, ry + ROW_H)], fill=BORDER, width=1)

    # Outer border
    draw.rectangle([0, 0, W - 1, total_h - 1], outline=ACCENT, width=2)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()



# ─────────────────────────────────────────────────────────────────────────────
# Q88 EXTRACTION ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_q88(text):
    """Fix multi-line artifacts common in Q88 PDFs from pdfplumber extraction."""
    import re as _re
    # "Metric\nTonnes" -> "Metric Tonnes"
    text = _re.sub(r"Metric\s*\n\s*Tonnes?", "Metric Tonnes", text)
    # "17,962.00 Metric 24,501.00 Metric\nTonnes Tonnes" -> proper two-field form
    text = _re.sub(
        r"([\d,.]+)\s+Metric\s+([\d,.]+)\s+Metric\s+Tonnes\s+Tonnes",
        r"\1 Metric Tonnes \2 Metric Tonnes", text
    )
    return text


def _q88_num(s):
    """Convert a Q88 number string to float, stripping commas/spaces."""
    import re as _re
    if s is None:
        return None
    s = _re.sub(r"[,\s]", "", str(s).strip())
    try:
        return float(s)
    except ValueError:
        return None


def _fix_draft(v):
    """
    Correct drafts that used a comma as a thousands separator.
    E.g. San Julian Q88 shows "13,901 Metres" which pdfplumber gives as 13901.0
    but the actual draft is 13.901 m.  Any value > 30 is treated this way.
    """
    if v is None:
        return None
    return v / 1000 if v > 30 else v


def extract_q88_fields(raw_text):
    """
    Parse Q88 Version 5 or 6 PDF text and return all vessel parameters
    needed by the stowage calculator.

    Handles format variants:
      - "Metres" vs "m" for dimensions
      - "Metric Tonnes" vs "mt" in loadline table
      - Comma-as-thousands-separator in draft fields (e.g. 13,901 = 13.901 m)
      - Split lines in loadline table (pdfplumber artefact)
      - Grand Total in 8.2 (v5) vs 8.2a (v6)

    Returns a dict.  Fields that could not be extracted are None.
    _missing lists the keys that are None and require user input.
    """
    import re as _re

    text = _normalize_q88(raw_text)

    def srch(pattern, flags=_re.IGNORECASE | _re.MULTILINE):
        return _re.search(pattern, text, flags)

    # ── Name ────────────────────────────────────────────────────────────────
    m = srch(r"1\.2\s+Vessel.s name.*?:\s*(.+?)(?:\s*\(|$|\n)")
    name = m.group(1).strip() if m else None

    # ── Dimensions (handles "Metres" and compact "m") ────────────────────────
    def _dim(q_num):
        m = srch(q_num + r"\s+\S.*?:\s*([\d,.]+)\s*(?:Met|m\b)")
        return _q88_num(m.group(1)) if m else None

    loa  = _dim(r"1\.27")
    lbp  = _dim(r"1\.28")
    beam = _dim(r"1\.29")
    keel = _dim(r"1\.31")

    # ── GRT ─────────────────────────────────────────────────────────────────
    m = srch(r"1\.36\s+Gross Tonnage.*?:\s*([\d,.]+)")
    grt = _q88_num(m.group(1)) if m else None

    # ── Tropical Load Line ───────────────────────────────────────────────────
    # Format A: "Tropical: 5.93 Metres 13.90 Metres 71,533 Metric Tonnes 84,769 Metric Tonnes"
    # Format B: "Tropical: 2.39m 6.14m 8318.07mt 11620.83mt"
    draft_full = dwt = disp_trop = None

    trop_a = srch(
        r"Tropical[:\s]+([\d,.]+)\s*(?:Metres?|m)\s+"
        r"([\d,.]+)\s*(?:Metres?|m)\s+"
        r"([\d,.]+)\s*Metric\s+Tonnes?\s+"
        r"([\d,.]+)\s*Metric\s+Tonnes?"
    )
    if trop_a:
        draft_full = _fix_draft(_q88_num(trop_a.group(2)))
        dwt        = _q88_num(trop_a.group(3))
        disp_trop  = _q88_num(trop_a.group(4))
    else:
        trop_b = srch(
            r"Tropical[:\s]+([\d.]+)m\s+([\d.]+)m\s+([\d,.]+)mt\s+([\d,.]+)mt"
        )
        if trop_b:
            draft_full = _q88_num(trop_b.group(2))
            dwt        = _q88_num(trop_b.group(3))
            disp_trop  = _q88_num(trop_b.group(4))

    # ── Lightship ────────────────────────────────────────────────────────────
    m = srch(
        r"Lightship[:\s]+[\d,.]+\s*(?:Metres?|m)\s+[\d,.]+\s*(?:Metres?|m)\s+"
        r"[-\u2013]?\s*([\d,.]+)\s*(?:Metric\s+Tonnes?|mt)"
    )
    lightship = _q88_num(m.group(1)) if m else None

    # Displacement = lightship + DWT (more reliable than tropical disp table cell)
    if lightship and dwt:
        displacement = round(lightship + dwt, 2)
    else:
        displacement = disp_trop

    # ── Constant ─────────────────────────────────────────────────────────────
    m = srch(r"1\.42\s+Constant.*?:\s*([\d,.]+)\s*(?:Metric|MT|mt)")
    constant = _q88_num(m.group(1)) if m else None

    # ── 98% Cargo Tank Capacity (excl. slop tanks) ──────────────────────────
    tank_m3_98 = tank_src = None
    for pattern, src_label in [
        (r"8\.2a\s+Grand Total.*?[:\s]+([\d,.]+)\s*Cu",       "Q88-8.2a Grand Total (wing+centre)"),
        (r"Grand Total Cubic Capacity.*?98%.*?[:\s]+([\d,.]+)\s*Cu", "Grand Total 98%"),
        (r"8\.2\s+Number of cargo tanks.*?98%.*?[:\s]+([\d,.]+)\s*Cu", "Q88-8.2"),
        (r"Total\s+\d+\s+Tanks?\s+([\d,.]+)\s*(?:CBM|Cu|m3)", "Total tanks"),
    ]:
        mm = srch(pattern)
        if mm:
            tank_m3_98 = _q88_num(mm.group(1))
            tank_src   = src_label
            break

    # ── Slop tank capacity (Q88 section 8.3) ─────────────────────────────────
    # Slop tanks are routinely used as cargo tanks in Nigerian shuttle operations.
    # We extract the 98% slop total so the user can include it in the review form.
    slop_m3 = None
    # Pattern: "Total: 1,126.06 Cu. Metres" inside section 8.3
    m_slop = srch(r"8\.3\s+Slop.*?Total[:\s]*(\d[\d,.]+)\s*Cu", _re.DOTALL)
    if not m_slop:
        m_slop = srch(r"Slops?\s+tank.*?Total[:\s]*(\d[\d,.]+)\s*Cu", _re.DOTALL)
    if m_slop:
        slop_m3 = _q88_num(m_slop.group(1))

    missing = [k for k, v in [
        ("name", name), ("loa", loa), ("beam", beam), ("draft_full", draft_full),
        ("dwt", dwt), ("displacement", displacement), ("tank_m3_98", tank_m3_98),
    ] if v is None]

    return {
        "name":         name,
        "loa":          loa,
        "lbp":          lbp,
        "beam":         beam,
        "keel":         keel,
        "grt":          grt,
        "draft_full":   draft_full,
        "dwt":          dwt,
        "displacement": displacement,
        "lightship":    lightship,
        "constant":     constant,
        "tank_m3_98":   tank_m3_98,  # Grand Total excl. slop (Q88 8.2a)
        "slop_m3":      slop_m3,     # Slop tank 98% total (Q88 8.3)
        "tank_src":     tank_src,
        "_missing":     missing,
        "_disp_trop":   disp_trop,
    }



# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('''
    <div class="sidebar-brand">
      <div class="sidebar-title">⚓ ukcmeter</div>
      <div class="sidebar-sub">Bonny Light Crude Oil/Condensate · Loading &amp; Safety</div>
    </div>''', unsafe_allow_html=True)

    db = get_db()
    if not db:
        st.error("No vessels. Add one via the ➕ Add Vessel tab.")
        st.stop()

    selected_name = st.selectbox("Select Vessel", sorted(db.keys()))
    vessel        = db[selected_name]

    # ── Seawater Density ──────────────────────────────────────────────────────
    # Mother vessels (Suezmax / Aframax) operate at BIA offshore → density locked.
    # All other vessels load in rivers, creeks, estuaries → density selectable.
    st.markdown("---")
    _is_mother = vessel.get("class", "") in MOTHER_CLASSES
    if _is_mother:
        sw_density = SEAWATER_DENSITY_NG
        locked_display("Seawater Density — Offshore (BIA)",
                       f"{SEAWATER_DENSITY_NG} t/m³  🔒")
        st.markdown(
            "<div style='font-size:0.65rem;color:var(--text-muted);font-family:var(--mono);"
            "margin-top:2px;margin-bottom:4px'>"
            "Bonny offshore · full salinity · locked for mother vessels"
            "</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='sidebar-section'>Seawater Density at Loading Point</div>",
                    unsafe_allow_html=True)
        _SW_PRESETS = {
            # Default = fresh water (1.000) — lightest density, deepest draft, most conservative
            # Conservative loading principle: plan for worst case, adjust up if confirmed denser
            "Fresh water — terminal / soku river (most conservative)": 1.0000,
            "Cawthorne Channel / Awoba (20 ppt)":                   1.0125,
            "Bonny River estuary (brackish, 25 ppt)":               1.0155,
            "Bonny Channel / offshore (29 ppt)":           1.0205,
            "Bight of Benin — open sea (34 ppt)":              1.0245,
            "BIA offshore (35 ppt)":     1.0255,
            "— Manual entry —":                           None,
        }
        _sw_preset_key = st.selectbox("Water density preset", list(_SW_PRESETS.keys()),
                                       key="sw_density_preset")
        _sw_preset_val = _SW_PRESETS[_sw_preset_key]
        if _sw_preset_val is not None:
            _sw_default = _sw_preset_val
            st.markdown(
                f"<span class='badge badge-blue'>Preset: {_sw_preset_val:.4f} t/m³</span>",
                unsafe_allow_html=True)
        else:
            _sw_default = 1.0000  # lightest = deepest draft = worst case (IACS conservative loading)
        sw_density = st.number_input(
            "Seawater Density (t/m³)", 1.000, 1.030, float(_sw_default), 0.0005,
            format="%.4f",
            help=(
                "Salinity-dependent density for displacement and draft calculations. "
                "1.000 = fresh water, 1.025 = standard ocean. "
                "Nigerian coastal/estuarine range: 1.010–1.026. "
                "Source: IMO MSC.1/Circ.1418 / BV NR467 / DNV-GL OTG-09."
            ))
        _sal_ppt   = round((sw_density - 1.000) / 0.000805)
        _sal_label = "fresh" if _sal_ppt <= 2 else f"≈{_sal_ppt} ppt"
        _fwa_mm    = (SEAWATER_DENSITY_NG - sw_density) * 1000
        st.markdown(
            f"<div style='font-size:0.65rem;color:var(--text-muted);font-family:var(--mono);"
            f"margin-top:2px;margin-bottom:4px'>"
            f"Salinity {_sal_label} · FWA {_fwa_mm:+.1f} mm vs Nigerian coastal"
            f"</div>", unsafe_allow_html=True)
    # Cargo API
    st.markdown("---")
    st.markdown("<div class='sidebar-section'>Cargo API Gravity</div>",
                unsafe_allow_html=True)
    field_choice = st.selectbox("Field / API preset", list(FIELD_API_PRESETS.keys()),
                                 key="field_preset")
    preset_api   = FIELD_API_PRESETS[field_choice]
    if preset_api is not None:
        api_default = preset_api
        st.markdown(f"<span class='badge badge-blue'>Preset: {preset_api:.2f}\u00b0 \u2014 {field_choice}</span>",
                    unsafe_allow_html=True)
    else:
        api_default = float(vessel.get("api_ref", 27))
    api      = st.number_input("Cargo API Gravity (\u00b0)", 5.0, 60.0, float(api_default), 0.5,
                                help="API gravity of the crude. Affects SG, cargo mass and draft.")
    sg_cargo = api_to_sg(api)

    # ── Breakwater Depth at Loading Point ────────────────────────────────────
    # When a preset is selected the LAT value is known and tide is REQUIRED
    # to complete the effective water depth: depth = LAT + high tide height.
    # This follows NPA/NNPC bar-crossing practice where the tidal window
    # determines the maximum permissible draft.
    st.markdown("---")
    st.markdown("<div class='sidebar-section'>Breakwater Depth at Loading Point</div>",
                unsafe_allow_html=True)
    depth_choice = st.selectbox("Loading location preset", list(DEPTH_PRESETS.keys()),
                                 key="depth_preset")
    preset_depth = DEPTH_PRESETS[depth_choice]
    _preset_selected = (preset_depth is not None)

    if _preset_selected:
        # Preset chosen — show locked LAT value and REQUIRE tide input
        lat_depth = preset_depth
        st.markdown(
            f"<div style='background:rgba(255,159,10,0.08);border:1px solid rgba(255,159,10,0.25);"
            f"border-radius:10px;padding:8px 12px;margin-bottom:6px'>"
            f"<div style='font-size:0.65rem;color:rgba(255,159,10,0.8);font-family:var(--mono);"
            f"letter-spacing:0.08em;margin-bottom:3px'>LAT DEPTH  &#128274;</div>"
            f"<div style='font-size:1.05rem;font-weight:700;color:#f5f5f7;font-family:var(--mono)'>"
            f"{lat_depth:.2f} m</div>"
            f"<div style='font-size:0.6rem;color:var(--text-muted);margin-top:2px'>"
            f"{depth_choice}</div>"
            f"</div>", unsafe_allow_html=True)
        st.markdown(
            "<div style='font-size:0.68rem;font-weight:600;color:#FF9F0A;"
            "font-family:var(--mono);letter-spacing:0.06em;margin-bottom:4px'>"
            "⚠️ TIDAL HEIGHT REQUIRED</div>", unsafe_allow_html=True)
        tide_height = st.number_input(
            "Expected High Tide at Bar (m)", 0.0, 6.0, 1.80, 0.05,
            key="tide_height_preset",
            help=(
                "Height of high tide above chart datum (LAT) at the planned bar-crossing time. "
                "Effective water depth = LAT depth + tide height. "
                "Source: NiMet / NPA tide tables or vessel’s port agent. "
                "Use the predicted high-water height for the crossing window — "
                "never the mean or low-water figure."
            ))
        water_depth = lat_depth + tide_height
        st.markdown(
            f"<div style='background:rgba(48,209,88,0.06);border:1px solid rgba(48,209,88,0.22);"
            f"border-radius:10px;padding:8px 12px;margin-top:4px'>"
            f"<div style='font-size:0.62rem;color:rgba(255,255,255,0.45);font-family:var(--mono);"
            f"letter-spacing:0.07em;margin-bottom:2px'>EFFECTIVE WATER DEPTH</div>"
            f"<div style='font-size:1.15rem;font-weight:700;color:#30D158;font-family:var(--mono)'>"
            f"{water_depth:.2f} m</div>"
            f"<div style='font-size:0.6rem;color:var(--text-muted);margin-top:1px'>"
            f"= LAT {lat_depth:.2f} m + tide {tide_height:.2f} m</div>"
            f"</div>", unsafe_allow_html=True)
    else:
        # Manual entry — user enters the total water depth directly
        st.markdown(
            "<div style='font-size:0.65rem;color:var(--text-muted);font-family:var(--mono);"
            "margin-bottom:4px'>Enter total water depth (LAT + tide) directly.</div>",
            unsafe_allow_html=True)
        _manual_default = float(vessel.get("breakwater_lat", 3.45) + 1.80)
        water_depth = st.number_input(
            "Total Water Depth at Bar (m)", 1.0, 30.0, float(_manual_default), 0.05,
            key="water_depth_manual",
            help=(
                "Total water depth at the shallowest bar/crossing point = LAT depth + tidal height. "
                "Select a location preset above to have the LAT depth pre-filled "
                "and enter the tide height separately."
            ))

    # Deductions
    st.markdown("---")
    st.markdown("<div class='sidebar-section'>Deductions — Non-Cargo Weight</div>",
                unsafe_allow_html=True)

    default_bunker_mt = float(vessel.get("bunker_fw", 1500)) * 0.6
    default_fw_mt     = float(vessel.get("bunker_fw", 1500)) * 0.4

    # Bunker — MT, Litres, or m³
    bunker_unit = st.radio("Bunker unit", ["MT", "Litres", "m\u00b3"], horizontal=True,
                            key="bunker_unit_radio")
    if bunker_unit == "MT":
        bunker_mt = st.number_input("Bunker on board (MT)", 0.0, 6000.0,
                                     round(default_bunker_mt, 0), 10.0,
                                     help="HFO + MDO + lube oil in metric tonnes.")
    elif bunker_unit == "Litres":
        def_L = mt_to_litres(default_bunker_mt, BUNKER_DENSITY_BLEND)
        bunk_L = st.number_input("Bunker on board (Litres)", 0.0, 6_000_000.0,
                                  round(def_L, 0), 1000.0,
                                  help=f"Blend density {BUNKER_DENSITY_BLEND} t/m\u00b3 (HFO+MDO). 1,000 L \u2248 0.94 MT.")
        bunker_mt = litres_to_mt(bunk_L, BUNKER_DENSITY_BLEND)
        st.caption(f"\u2261 {bunker_mt:,.1f} MT  (@ {BUNKER_DENSITY_BLEND} t/m\u00b3)")
    else:  # m³
        def_m3 = mt_to_m3fluid(default_bunker_mt, BUNKER_DENSITY_BLEND)
        bunk_m3 = st.number_input("Bunker on board (m\u00b3)", 0.0, 6000.0,
                                   round(def_m3, 1), 1.0,
                                   help=f"Blend density {BUNKER_DENSITY_BLEND} t/m\u00b3. 1 m\u00b3 \u2248 0.94 MT.")
        bunker_mt = m3fluid_to_mt(bunk_m3, BUNKER_DENSITY_BLEND)
        st.caption(f"\u2261 {bunker_mt:,.1f} MT  (@ {BUNKER_DENSITY_BLEND} t/m\u00b3)")

    # Fresh water + ballast + other stores — MT or Litres
    fw_unit = st.radio("Fresh water + ballast + other stores unit", ["MT", "Litres"], horizontal=True, key="fw_unit_radio")
    if fw_unit == "MT":
        fw_mt = st.number_input("Fresh water + ballast + other stores on board (MT)", 0.0, 2000.0,
                                 round(default_fw_mt, 0), 10.0,
                                 help="Potable + distilled water. Density = 1.000 t/m\u00b3.")
    else:
        def_fw_L = mt_to_litres(default_fw_mt, FRESHWATER_DENSITY)
        fw_L = st.number_input("Fresh water + ballast + other stores on board (Litres)", 0.0, 2_000_000.0,
                                round(def_fw_L, 0), 500.0,
                                help="Fresh water + ballast + other stores: 1.000 t/m\u00b3 (1 litre = 1 kg exactly).")
        fw_mt = litres_to_mt(fw_L, FRESHWATER_DENSITY)
        st.caption(f"\u2261 {fw_mt:,.1f} MT")

    constant_mt = st.number_input(
        "Ship's Constant (MT)", 0.0, 1000.0, float(vessel.get("constant", 200)), 5.0,
        help="Unmeasured weight: stores, spare parts, ropes, sediment, paint. Typically 20\u2013500 MT.")

    total_ded = bunker_mt + fw_mt + constant_mt
    avail_dwt = vessel["dwt"] - total_ded

    st.markdown(f"""
    <div class="metric-card" style="margin-top:0.5rem">
      <div class="metric-label">Total Deductions</div>
      <div class="metric-value" style="font-size:1.1rem">{total_ded:,.1f} <span class="metric-unit">MT</span></div>
      <div style="font-size:0.72rem;color:var(--muted);font-family:var(--mono);margin-top:4px">
        Avail. Tropical DWT for cargo: <strong style="color:var(--accent)">{avail_dwt:,.0f} MT</strong>
      </div>
    </div>
    <div class="metric-card">
      <div class="metric-label">Cargo SG @ API {api:.1f}\u00b0</div>
      <div class="metric-value" style="font-size:1.1rem">{sg_cargo:.4f}</div>
    </div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# APP HEADER + VESSEL HEADER
# ─────────────────────────────────────────────────────────────────────────────
tld_val = vessel['draft_full']
st.markdown(f"""
<div class="app-header">
  <div class="app-header-left">
    <div>
      <div class="app-name">⚓ ukcmeter</div>
      <div class="app-sub">Bonny Light Crude Oil/Condensate · Loading &amp; Safety Calculator</div>
    </div>
    <div class="vessel-pill">{selected_name}</div>
  </div>
  <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center">
    <span class="badge badge-ok">{vessel['class']}</span>
    <span class="badge badge-blue">DWT {vessel['dwt']:,.0f} MT</span>
    <span class="badge badge-blue">Tank {m3_to_bbl(vessel['tank_m3_98']):,.0f} bbl</span>
    <span class="badge badge-blue">LOA {vessel['loa']} m</span>
    <span class="badge badge-warn">TLD {tld_val} m</span>
    <span class="badge badge-warn">Bar {vessel['breakwater_lat']} m LAT</span>
    <span class="badge badge-lock">\u03c1 {sw_density:.4f} t/m\u00b3 &#128274;</span>
  </div>
</div>""", unsafe_allow_html=True)

if vessel.get("note"):
    info(f"&#128204; {vessel['note']}")

# Pre-compute limits for use in both tabs
lims = compute_limits(vessel, bunker_mt, fw_mt, constant_mt, api)

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "&#128230;  Volume → Draft",
    "&#128208;  Draft → Volume",
    "&#128203;  Fleet Browser",
    "&#10133;  Add Vessel",
    "&#9881;️  Master Data",
    "&#128196;  Import Q88",
])


# ════════════════════════════════════════════════════════════════════════════
# TAB 1  —  Volume → Draft
# ════════════════════════════════════════════════════════════════════════════
with tab1:
    section("Enter Cargo Volume \u2192 Predicted Draft")
    info(
        "Enter cargo quantity. The calculator predicts the loaded draft using the "
        "<strong>proportional displacement method</strong> (industry-standard loading plan approach): "
        "<code>draft = (lightship + cargo + deductions) / full‑displacement × TLD</code>. "
        "Anchors to the vessel’s known full-load hydrostatic data; matches workbook stowage tables "
        "to within ~3–5%. "
        f"Seawater density: <strong>{sw_density:.4f} t/m\u00b3</strong>. "
        "<strong>Both loading limits enforced simultaneously</strong>: "
        "volume ≤ 98% tank capacity AND cargo mass ≤ available Tropical DWT."
    )

    # ── Two-column Apple/Tesla layout ────────────────────────────────────────
    # LEFT (38%): slim control panel — limits, input, nothing else
    # RIGHT (62%): unified premium output card — draft hero, metrics, gauge, summary
    col_ctrl, col_out = st.columns([1, 1.6], gap="large")

    with col_ctrl:
        limit_panel(lims, api)
        st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
        vol_unit = st.radio("Input unit", ["US Barrels", "Cubic Metres (m\u00b3)"], horizontal=True,
                             key="vol_unit_t1")
        max_bbl = round(lims["max_cargo_bbl"] * 1.001)
        max_m3  = round(lims["max_cargo_m3"] * 1.001, 1)
        def_bbl = round(lims["max_cargo_bbl"] * 0.95)
        def_m3  = round(lims["max_cargo_m3"] * 0.95, 1)

        if vol_unit == "US Barrels":
            cargo_bbl = st.number_input("Cargo Volume (US Bbls)", 0, max(1, max_bbl),
                                         min(def_bbl, max_bbl), 1000)
            cargo_m3  = bbl_to_m3(cargo_bbl)
        else:
            cargo_m3  = st.number_input("Cargo Volume (m\u00b3)", 0.0, max(1.0, float(max_m3)),
                                         min(float(def_m3), float(max_m3)), 100.0)
            cargo_bbl = round(m3_to_bbl(cargo_m3))

        st.markdown(
            f'<div style="font-size:0.72rem;color:var(--text-muted);font-family:var(--mono);margin-top:0.3rem">'
            f'\u2261 {cargo_m3:,.1f} m\u00b3 &nbsp;&middot;&nbsp; {cargo_bbl:,} US Bbls</div>',
            unsafe_allow_html=True)

        # ── Summary table placeholder (filled after res is computed in col_out) ──
        _t1_summary_ph = st.empty()

    with col_out:
        res = volume_to_draft(vessel, cargo_m3, api, bunker_mt, fw_mt, constant_mt, sw_density)
        ukc = ukc_assessment(res["draft_m"], water_depth, vessel.get("class",""))
        _regime_label = ukc.get("regime", "")

        dc  = "#ff453a" if res["over_tld"] else "#0a84ff"
        ol  = "\u26a0\ufe0f OVER TROPICAL LOAD LINE DRAFT" if res["over_tld"] else ""

        if res["exceeds_tank"]:
            warn(f"Volume exceeds 98% tank capacity ({lims['vol_cap_bbl']:,.0f} Bbls). "
                 f"Clamped to <strong>{lims['max_cargo_bbl']:,.0f} Bbls</strong>.")
        if res["exceeds_dwt"]:
            warn(f"Cargo mass exceeds available Tropical DWT ({lims['avail_dwt_mt']:,.0f} MT). "
                 f"Clamped to <strong>{lims['max_cargo_mt']:,.0f} MT</strong>.")

        # UKC status colours
        ukc_clr = {"ADEQUATE": "#30d158", "MARGINAL": "#ff9f0a"}.get(ukc["ukc_status"], "#ff453a")

        # ── Unified output card — pre-compute SVG string to avoid f-string conflicts ──
        _gauge_svg_t1 = _ukc_svg(ukc["ukc_status"], ukc["ukc_m"], ukc["ukc_required_m"],
                                  water_depth, res["draft_m"],
                                  marginal_m=ukc.get("marginal_m"),
                                  pct_adq=ukc.get("pct_adq", 0.15),
                                  pct_mrg=ukc.get("pct_mrg", 0.05))
        _ol_span  = (f'<span style="font-size:0.75rem;color:#ff453a;font-weight:600;margin-left:0.5rem">{ol}</span>' if ol else "")
        _ukc_req  = f'{ukc["ukc_required_m"]:.2f}'
        _headroom = f'{round(water_depth - res["draft_m"], 2):.2f}'
        _vol_bbl  = f'{res["volume_loaded_bbl"]:,}'
        _vol_m3   = f'{res["volume_loaded_m3"]:,.1f}'
        _cargo_mt = f'{res["cargo_mass_mt"]:,.0f}'
        _draft_str= f'{res["draft_m"]:.3f}'
        _tld_str  = str(res["tld_m"])

        _card_top = (
            f'<div style="background:var(--surface2);border:1px solid var(--border2);' +
            f'border-radius:var(--r-3xl);padding:2rem 2rem 1.5rem;' +
            f'position:relative;overflow:hidden;margin-bottom:1rem;">' +
            f'<div style="position:absolute;top:0;left:0;right:0;height:1px;' +
            f'background:linear-gradient(90deg,transparent 5%,{dc} 40%,{ukc_clr} 60%,transparent 95%)"></div>' +
            f'<div style="font-size:0.62rem;font-weight:700;letter-spacing:0.14em;' +
            f'text-transform:uppercase;color:var(--text-muted);margin-bottom:0.4rem">Predicted Loaded Draft</div>' +
            f'<div style="display:flex;align-items:baseline;gap:0.5rem;margin-bottom:0.2rem">' +
            f'<span style="font-size:3.8rem;font-weight:700;font-family:var(--mono);' +
            f'color:{dc};letter-spacing:-0.04em;line-height:1">' + _draft_str + '</span>' +
            f'<span style="font-size:1.6rem;font-weight:400;color:var(--text-dim)">m</span>' +
            _ol_span +
            '</div>' +
            f'<div style="font-size:0.8rem;color:var(--text-dim);margin-bottom:0.75rem">' +
            f'TLD limit&nbsp;' + _tld_str + f' m &nbsp;&middot;&nbsp; UKC headroom&nbsp;' +
            f'<span style="color:{ukc_clr};font-weight:600">' + _headroom + ' m</span></div>'
        )
        _card_gauge = (
            '<div style="margin:0 -0.5rem 0.75rem;border-top:1px solid rgba(255,255,255,0.06);' +
            'border-bottom:1px solid rgba(255,255,255,0.06);padding:0.25rem 0">' +
            _gauge_svg_t1 +
            '<div style="display:flex;justify-content:space-between;padding:4px 8px 6px;' +
            'font-size:11px;color:rgba(255,255,255,0.4)">' +
            '<span>Min required: <strong style="color:rgba(255,255,255,0.75);' +
            'font-family:ui-monospace,monospace">' + _ukc_req + ' m</strong>' +
            ' &nbsp;<span style="font-size:9px;color:rgba(255,255,255,0.3);">· ' + _regime_label + '</span></span></div></div>'
        )
        _card_bottom = (
            '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;' +
            'padding:1rem 0;border-top:1px solid var(--border);border-bottom:1px solid var(--border);' +
            'margin-bottom:1.25rem">' +
            '<div style="text-align:center">' +
            '<div style="font-size:0.55rem;font-weight:700;letter-spacing:0.14em;' +
            'text-transform:uppercase;color:var(--text-muted);margin-bottom:0.3rem">Volume</div>' +
            '<div style="font-size:1.15rem;font-weight:700;font-family:var(--mono);color:var(--text)">' + _vol_bbl + '</div>' +
            '<div style="font-size:0.65rem;color:var(--text-muted)">US Bbls</div></div>' +
            '<div style="text-align:center;border-left:1px solid var(--border);border-right:1px solid var(--border)">' +
            '<div style="font-size:0.55rem;font-weight:700;letter-spacing:0.14em;' +
            'text-transform:uppercase;color:var(--text-muted);margin-bottom:0.3rem">Volume</div>' +
            '<div style="font-size:1.15rem;font-weight:700;font-family:var(--mono);color:var(--text)">' + _vol_m3 + '</div>' +
            '<div style="font-size:0.65rem;color:var(--text-muted)">m³</div></div>' +
            '<div style="text-align:center">' +
            '<div style="font-size:0.55rem;font-weight:700;letter-spacing:0.14em;' +
            'text-transform:uppercase;color:var(--text-muted);margin-bottom:0.3rem">Cargo Mass</div>' +
            '<div style="font-size:1.15rem;font-weight:700;font-family:var(--mono);color:var(--text)">' + _cargo_mt + '</div>' +
            '<div style="font-size:0.65rem;color:var(--text-muted)">MT</div></div>' +
            '</div></div>'
        )
        st.markdown(_card_top + _card_gauge + _card_bottom, unsafe_allow_html=True)

        # ── Score bars full-width in right column ──────────────────────────
        score_bar(res["tank_util_pct"], "Tank Utilisation (vs 98% capacity)")
        score_bar(res["dwt_util_pct"],  "Tropical DWT Utilisation")

    # ── Build summary rows (needs res + ukc, computed above) ────────────────
    _t1_rows = [
        ("Cargo Volume (loaded)",  f"{res['volume_loaded_m3']:,.1f} m\u00b3  /  {res['volume_loaded_bbl']:,} Bbls"),
        ("Cargo API",              f"{api:.1f}\u00b0  (SG {res['sg']:.4f})"),
        ("Cargo Mass",             f"{res['cargo_mass_mt']:,.1f} MT"),
        ("Lightship Mass",         f"{res['lightship_mt']:,.1f} MT"),
        ("Bunker on board",        f"{bunker_mt:,.1f} MT"),
        ("Fresh water + ballast + other stores on board",   f"{fw_mt:,.1f} MT"),
        ("Ship\u2019s Constant",   f"{constant_mt:,.0f} MT"),
        ("Total Deductions",       f"{res['deductions_mt']:,.1f} MT"),
        ("Total Displacement",     f"{res['total_displacement_mt']:,.1f} MT"),
        ("Seawater Density",       f"{sw_density:.4f} t/m\u00b3  \U0001f512 Nigerian waters"),
        ("Predicted Draft",        f"{res['draft_m']:.3f} m"),
        ("Tropical Load Line Draft (TLD)", f"{res['tld_m']} m"),
        ("Breakwater Depth",       f"{water_depth:.2f} m"),
        ("UKC",                    f"{ukc['ukc_m']:.2f} m  [{ukc['ukc_status']}]"),
        ("Limit 1 \u2014 98% Tank",     f"{lims['vol_cap_bbl']:,.0f} Bbls  /  {lims['vol_cap_m3']:,.1f} m\u00b3"),
        ("Limit 2 \u2014 Tropical DWT", f"{lims['dwt_cap_bbl']:,.0f} Bbls  /  {lims['dwt_cap_mt']:,.0f} MT"),
        ("Binding Limit",          lims['binding']),
        ("Tank Utilisation",       f"{res['tank_util_pct']}%  of 98% capacity"),
        ("Tropical DWT Util.",     f"{res['dwt_util_pct']}%"),
    ]
    _t1_png = summary_png_bytes(_t1_rows, "Loading Calculation Summary \u2014 Volume \u2192 Draft")

    # ── Inject summary table into the left-column placeholder ────────────────
    with _t1_summary_ph:
        summary_df(_t1_rows)
        st.download_button(
            "\U0001f4f7  Download Summary as PNG",
            data=_t1_png, file_name="loading_summary.png",
            mime="image/png", use_container_width=True, key="dl_t1_png",
        )


# ════════════════════════════════════════════════════════════════════════════
# TAB 2  —  Draft → Volume
# ════════════════════════════════════════════════════════════════════════════
with tab2:
    section("Enter Target Draft \u2192 Calculated Cargo Volume")
    info(
        "Enter the <strong>maximum permissible draft</strong> (tide-constrained or bar-crossing draft). "
        "The calculator back-calculates achievable cargo using the "
        "<strong>proportional displacement method</strong>: "
        "<code>cargo = (draft/TLD × full‑displacement − lightship − deductions)</code>. "
        "Both hard limits are then applied: volume ≤ 98% tank capacity, mass ≤ available Tropical DWT. "
        f"Seawater density: <strong>{sw_density:.4f} t/m\u00b3</strong>."
    )

    # ── Two-column Apple/Tesla layout (Tab 2) ───────────────────────────────
    col_ctrl2, col_out2 = st.columns([1, 1.6], gap="large")

    with col_ctrl2:
        limit_panel(lims, api)
        st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
        draft_inp = st.number_input(
            "Target / Maximum Draft (m)", min_value=1.0,
            max_value=float(vessel["draft_full"]),
            value=round(min(vessel["draft_full"] * 0.90, water_depth * 0.90), 3),
            step=0.01, format="%.3f",
            help="Tide-adjusted permissible draft. Cannot exceed the vessel\u2019s Tropical Load Line Draft.",
        )
        with st.expander("\U0001f30a Tidal Draft Helper"):
            lat_d  = st.number_input("Breakwater Depth at LAT (m)", 1.0, 20.0,
                                      float(vessel.get("breakwater_lat", 3.45)), 0.05)
            tide_h = st.number_input("Expected High Tide (m)", 0.0, 5.0, 2.0, 0.1)
            safety = st.slider("Safety factor on river draft (%)", 80, 95, 90)
            river_d  = lat_d + tide_h
            max_perm = river_d * (safety / 100)
            st.markdown(f"""
            <div class="info-box">
              River Draft = {river_d:.2f} m<br>
              Max Permissible = {river_d:.2f} &times; {safety}% = <strong>{max_perm:.3f} m</strong>
            </div>""", unsafe_allow_html=True)
            if st.button("Apply this draft", key="apply_tide"):
                draft_inp = max_perm

        # ── Summary table placeholder (filled after res2 is computed) ────────
        _t2_summary_ph = st.empty()

    with col_out2:
        res2 = draft_to_volume(vessel, draft_inp, api, bunker_mt, fw_mt, constant_mt, sw_density)
        ukc2 = ukc_assessment(draft_inp, water_depth, vessel.get("class",""))
        _regime_label2 = ukc2.get("regime", "")

        if res2["volume_clamped"]:
            warn(f"Volume at this draft exceeds the binding limit "
                 f"(<strong>{lims['binding']}</strong>). "
                 f"Cargo reduced to <strong>{lims['max_cargo_bbl']:,.0f} Bbls</strong>.")

        ukc_clr2 = {"ADEQUATE": "#30d158", "MARGINAL": "#ff9f0a"}.get(ukc2["ukc_status"], "#ff453a")

        # Pre-compute all dynamic values to avoid f-string / SVG curly-brace conflicts
        _gauge_svg_t2  = _ukc_svg(ukc2["ukc_status"], ukc2["ukc_m"], ukc2["ukc_required_m"],
                                    water_depth, draft_inp,
                                    marginal_m=ukc2.get("marginal_m"),
                                    pct_adq=ukc2.get("pct_adq", 0.15),
                                    pct_mrg=ukc2.get("pct_mrg", 0.05))
        _ukc_req2   = f'{ukc2["ukc_required_m"]:.2f}'
        _ukc_m2_str = f'{ukc2["ukc_m"]:.2f}'
        _vol_bbl2   = f'{res2["volume_bbl"]:,}'
        _vol_m3_2   = f'{res2["volume_m3"]:,.1f}'
        _cargo_mt2  = f'{res2["cargo_mass_mt"]:,.0f}'
        _sg_str     = f'{res2["sg"]:.4f}'
        _dinp_str   = f'{draft_inp:.3f}'
        _tld_str2   = str(res2["tld_m"])
        _api_str    = f'{api:.1f}\u00b0'

        _c2_top = (
            '<div style="background:var(--surface2);border:1px solid var(--border2);' +
            'border-radius:var(--r-3xl);padding:2rem 2rem 1.5rem;' +
            'position:relative;overflow:hidden;margin-bottom:1rem;">' +
            f'<div style="position:absolute;top:0;left:0;right:0;height:1px;' +
            f'background:linear-gradient(90deg,transparent 5%,#0a84ff 40%,{ukc_clr2} 60%,transparent 95%)"></div>' +
            '<div style="font-size:0.62rem;font-weight:700;letter-spacing:0.14em;' +
            'text-transform:uppercase;color:var(--text-muted);margin-bottom:0.4rem">Cargo Volume at ' +
            _dinp_str + ' m draft</div>' +
            '<div style="display:flex;align-items:baseline;gap:0.5rem;margin-bottom:0.2rem">' +
            '<span style="font-size:3.8rem;font-weight:700;font-family:var(--mono);' +
            'color:#0a84ff;letter-spacing:-0.04em;line-height:1">' + _vol_bbl2 + '</span>' +
            '<span style="font-size:1.4rem;font-weight:400;color:var(--text-dim);margin-left:4px">US Bbls</span>' +
            '</div>' +
            f'<div style="font-size:0.8rem;color:var(--text-dim);margin-bottom:0.75rem">' +
            'UKC at draft&nbsp;' +
            f'<span style="color:{ukc_clr2};font-weight:600">' + _ukc_m2_str + ' m</span>' +
            '&nbsp;&middot;&nbsp; TLD limit&nbsp;' + _tld_str2 + ' m</div>'
        )
        _c2_gauge = (
            '<div style="margin:0 -0.5rem 0.75rem;border-top:1px solid rgba(255,255,255,0.06);' +
            'border-bottom:1px solid rgba(255,255,255,0.06);padding:0.25rem 0">' +
            _gauge_svg_t2 +
            '<div style="display:flex;padding:4px 8px 6px;font-size:11px;color:rgba(255,255,255,0.4)">' +
            '<span>Min required: <strong style="color:rgba(255,255,255,0.75);' +
            'font-family:ui-monospace,monospace">' + _ukc_req2 + ' m</strong>' +
            ' &nbsp;<span style="font-size:9px;color:rgba(255,255,255,0.3);">· ' + _regime_label2 + '</span></span></div></div>'
        )
        _c2_bottom = (
            '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;' +
            'padding:1rem 0;border-top:1px solid var(--border);border-bottom:1px solid var(--border);' +
            'margin-bottom:1.25rem">' +
            '<div style="text-align:center">' +
            '<div style="font-size:0.55rem;font-weight:700;letter-spacing:0.14em;' +
            'text-transform:uppercase;color:var(--text-muted);margin-bottom:0.3rem">Volume</div>' +
            '<div style="font-size:1.15rem;font-weight:700;font-family:var(--mono);color:var(--text)">' + _vol_m3_2 + '</div>' +
            '<div style="font-size:0.65rem;color:var(--text-muted)">m³</div></div>' +
            '<div style="text-align:center;border-left:1px solid var(--border);border-right:1px solid var(--border)">' +
            '<div style="font-size:0.55rem;font-weight:700;letter-spacing:0.14em;' +
            'text-transform:uppercase;color:var(--text-muted);margin-bottom:0.3rem">Cargo Mass</div>' +
            '<div style="font-size:1.15rem;font-weight:700;font-family:var(--mono);color:var(--text)">' + _cargo_mt2 + '</div>' +
            '<div style="font-size:0.65rem;color:var(--text-muted)">MT</div></div>' +
            '<div style="text-align:center">' +
            '<div style="font-size:0.55rem;font-weight:700;letter-spacing:0.14em;' +
            'text-transform:uppercase;color:var(--text-muted);margin-bottom:0.3rem">SG @ ' + _api_str + '</div>' +
            '<div style="font-size:1.15rem;font-weight:700;font-family:var(--mono);color:var(--text)">' + _sg_str + '</div>' +
            '<div style="font-size:0.65rem;color:var(--text-muted)">t/m³</div></div>' +
            '</div></div>'
        )
        st.markdown(_c2_top + _c2_gauge + _c2_bottom, unsafe_allow_html=True)

        score_bar(res2["tank_util_pct"], "Tank Utilisation (vs 98% capacity)")
        score_bar(res2["dwt_util_pct"],  "Tropical DWT Utilisation")

    # ── Build summary rows then inject into left-column placeholder ──────────
    _t2_rows = [
        ("Input Draft",            f"{draft_inp:.3f} m"),
        ("Cargo API",              f"{api:.1f}\u00b0  (SG {res2['sg']:.4f})"),
        ("Cargo Volume",           f"{res2['volume_m3']:,.1f} m\u00b3  /  {res2['volume_bbl']:,} US Bbls"),
        ("Cargo Mass",             f"{res2['cargo_mass_mt']:,.1f} MT"),
        ("Lightship Mass",         f"{res2['lightship_mt']:,.1f} MT"),
        ("Bunker on board",        f"{bunker_mt:,.1f} MT"),
        ("Fresh water + ballast + other stores on board",   f"{fw_mt:,.1f} MT"),
        ("Ship\u2019s Constant",   f"{constant_mt:,.0f} MT"),
        ("Total Deductions",       f"{res2['deductions_mt']:,.1f} MT"),
        ("Total Displacement",     f"{res2['total_displacement_mt']:,.1f} MT"),
        ("Seawater Density",       f"{sw_density:.4f} t/m\u00b3  \U0001f512 Nigerian waters"),
        ("Tropical Load Line Draft (TLD)", f"{res2['tld_m']} m"),
        ("Breakwater Depth",       f"{water_depth:.2f} m"),
        ("UKC",                    f"{ukc2['ukc_m']:.2f} m  [{ukc2['ukc_status']}]"),
        ("Tank 98% Capacity",      f"{res2['tank_98_bbl']:,} Bbls  /  {res2['tank_98_m3']:,.1f} m\u00b3"),
        ("Limit 1 \u2014 98% Tank",     f"{lims['vol_cap_bbl']:,.0f} Bbls  /  {lims['vol_cap_m3']:,.1f} m\u00b3"),
        ("Limit 2 \u2014 Tropical DWT", f"{lims['dwt_cap_bbl']:,.0f} Bbls  /  {lims['dwt_cap_mt']:,.0f} MT"),
        ("Binding Limit",          lims['binding']),
        ("Tank Utilisation",       f"{res2['tank_util_pct']}%  of 98% capacity"),
        ("Tropical DWT Util.",     f"{res2['dwt_util_pct']}%"),
    ]
    _t2_png = summary_png_bytes(_t2_rows, "Loading Calculation Summary \u2014 Draft \u2192 Volume")
    with _t2_summary_ph:
        summary_df(_t2_rows)
        st.download_button(
            "\U0001f4f7  Download Summary as PNG",
            data=_t2_png, file_name="loading_summary_d2v.png",
            mime="image/png", use_container_width=True, key="dl_t2_png",
        )


# ════════════════════════════════════════════════════════════════════════════
# TAB 3  —  Fleet Browser  (Notes and Ref API removed per user request)
# ════════════════════════════════════════════════════════════════════════════
with tab3:
    section("Fleet Vessel Specification Browser")
    db_now = get_db()

    class_filter = st.multiselect(
        "Filter by Class",
        options=sorted({v["class"] for v in db_now.values()}),
        default=[], placeholder="All classes",
    )

    rows_spec = []
    for nm, v in sorted(db_now.items()):
        if class_filter and v["class"] not in class_filter:
            continue
        rows_spec.append({
            "Vessel":            nm,
            "Class":             v["class"],
            "Tropical DWT (MT)": f"{v['dwt']:,.0f}",
            "GRT":               f"{v['grt']:,.0f}",
            "Tank 98% (m\u00b3)":   f"{v['tank_m3_98']:,.1f}",
            "Tank 98% (Bbls)":   f"{round(m3_to_bbl(v['tank_m3_98'])):,}",
            "LOA (m)":           v["loa"],
            "Beam (m)":          v["beam"],
            "Keel (m)":          v["keel"],
            "TLD (m)":           v["draft_full"],
            "Cb":                f"{v['block_coeff']:.4f}",
            "Lightship (MT)":    f"{lightship_mass(v):,.0f}",
            "Constant (MT)":     v["constant"],
            "Bkwtr LAT (m)":     v["breakwater_lat"],
        })
    st.dataframe(pd.DataFrame(rows_spec), use_container_width=True, hide_index=True, height=520)

    # Quick comparison
    st.markdown("<hr class='sec-div'>", unsafe_allow_html=True)
    section("Quick Comparison \u2014 All Vessels at Current Settings")
    info(f"Max cargo at binding limit | API {api:.1f}\u00b0 | "
         f"Bunker {bunker_mt:.0f} MT | FW {fw_mt:.0f} MT | Constant {constant_mt:.0f} MT | "
         f"\u03c1_sw {sw_density:.4f} t/m\u00b3 | Breakwater {water_depth:.2f} m")

    comp_rows = []
    for nm, v in sorted(db_now.items()):
        if class_filter and v["class"] not in class_filter:
            continue
        try:
            lv  = compute_limits(v, bunker_mt, fw_mt, constant_mt, api)
            r   = volume_to_draft(v, lv["max_cargo_m3"], api, bunker_mt, fw_mt, constant_mt, sw_density)
            ukc_c = ukc_assessment(r["draft_m"], water_depth, v.get("class",""))
            flag  = ("\u26a0 OVER TLD" if r["over_tld"]
                     else ("\u26a0 UKC" if ukc_c["ukc_status"] != "ADEQUATE" else "\u2713 OK"))
            comp_rows.append({
                "Vessel":           nm,
                "Class":            v["class"],
                "Max Cargo (Bbls)": f"{lv['max_cargo_bbl']:,.0f}",
                "Binding Limit":    lv["binding"],
                "Draft at Max (m)": f"{r['draft_m']:.3f}",
                "TLD (m)":          v["draft_full"],
                "UKC (m)":          f"{ukc_c['ukc_m']:.2f}",
                "UKC Status":       ukc_c["ukc_status"],
                "Status":           flag,
            })
        except Exception:
            pass
    st.dataframe(pd.DataFrame(comp_rows), use_container_width=True, hide_index=True, height=480)


# ════════════════════════════════════════════════════════════════════════════
# TAB 4  —  Add Vessel
# ════════════════════════════════════════════════════════════════════════════
with tab4:
    section("Add New Vessel to Fleet")
    info(
        "<strong>Tropical DWT</strong> is the deadweight at the Tropical Load Line (Nigerian operations). "
        "<strong>Tropical Load Line Draft (TLD)</strong> is the maximum operational draft in the tropical zone. "
        "Class auto-assigns from DWT. US Barrel capacity = m\u00b3 \u00d7 6.28981. "
        "Block coefficient defaults to class-typical if left at 0."
    )

    with st.form("add_vessel_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            new_name  = st.text_input("Vessel Name *", placeholder="e.g. MT Balham")
            new_dwt   = st.number_input("Tropical DWT (MT) *",  1000.0, 350000.0, 20000.0, 500.0,
                                         help="Deadweight at Tropical Load Line")
            new_grt   = st.number_input("GRT *",                 500.0, 200000.0, 10000.0, 500.0)
            new_disp  = st.number_input("Full Load Displacement (MT) *", 1000.0, 400000.0, 25000.0, 500.0,
                                         help="= Lightship + Tropical DWT")
        with c2:
            new_tank  = st.number_input("98% Tank Capacity (m\u00b3) *", 100.0, 250000.0, 20000.0, 100.0)
            new_keel  = st.number_input("Keel Depth (m)",   0.0,  60.0, 40.0, 0.5)
            new_loa   = st.number_input("LOA (m) *",       50.0, 340.0, 150.0, 1.0)
            new_beam  = st.number_input("Beam (m) *",      10.0,  70.0,  25.0, 0.5)
        with c3:
            new_draft = st.number_input("Tropical Load Line Draft / TLD (m) *", 2.0, 25.0, 9.0, 0.01,
                                         help="Maximum operational draft in tropical zone (ILLC 1966). "
                                              "TLD = Summer Draft + Summer Draft/48")
            new_const = st.number_input("Ship\u2019s Constant (MT)",  0.0, 1000.0, 150.0, 5.0)
            new_bfw   = st.number_input("Bunker + FW default (MT)", 0.0, 5000.0, 1000.0, 50.0)
            new_bwlat = st.number_input("Breakwater LAT (m)",  0.0, 20.0, 3.45, 0.05)

        st.markdown("<hr class='sec-div'>", unsafe_allow_html=True)
        c4, c5 = st.columns(2)
        with c4:
            new_api = st.number_input("Reference API (\u00b0)", 5.0, 60.0, 27.0, 0.5)
            new_cb  = st.number_input("Block Coefficient Cb (0 = auto)", 0.0, 1.0, 0.0, 0.01,
                                       help="Leave 0 for class-typical. Tanker range 0.55\u20130.90.")
        with c5:
            new_note = st.text_area("Notes", placeholder="Operating area, typical berth, loading route\u2026", height=80)

        auto_cls    = classify_vessel(new_dwt)
        bbl_preview = round(m3_to_bbl(new_tank))
        st.markdown(
            f"<div class='info-box'>Auto-computed \u2014 "
            f"Class: <strong>{auto_cls}</strong> &nbsp;|&nbsp; "
            f"Tank 98%: <strong>{bbl_preview:,} US Bbls</strong> &nbsp;|&nbsp; "
            f"Lightship: <strong>{new_disp - new_dwt:,.0f} MT</strong></div>",
            unsafe_allow_html=True)

        if st.form_submit_button("\u2795 Add to Fleet", use_container_width=True):
            nn = new_name.strip()
            if not nn:
                st.error("Vessel name is required.")
            elif nn in get_db():
                st.error(f"'{nn}' already exists. Edit it in the \u2699\ufe0f Master Data tab.")
            else:
                cb_defaults = {"VLCC":0.830,"Suezmax":0.800,"Aframax":0.785,
                               "LR-2":0.790,"LR-1":0.820,"MR":0.780,
                               "General Purpose":0.720,"Small Tanker":0.680}
                cb_use = new_cb if new_cb > 0 else cb_defaults.get(auto_cls, 0.750)
                save_vessel({
                    "name":nn,"class":auto_cls,"dwt":new_dwt,"grt":new_grt,
                    "tank_m3_98":new_tank,"keel":new_keel,"loa":new_loa,"beam":new_beam,
                    "displacement":new_disp,"constant":new_const,"bunker_fw":new_bfw,
                    "draft_full":new_draft,"block_coeff":cb_use,
                    "breakwater_lat":new_bwlat,"api_ref":new_api,"note":new_note,
                })
                st.success(
                    f"\u2705 **{nn}** added \u2014 Class: **{auto_cls}** | Cb: **{cb_use:.3f}** | "
                    f"Tank 98%: **{bbl_preview:,} US Bbls** ({new_tank:,.1f} m\u00b3) | "
                    f"TLD: **{new_draft} m**. Select from the sidebar to run calculations.")
                st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# TAB 5  —  Master Data
# ════════════════════════════════════════════════════════════════════════════
with tab5:
    section("\u2699\ufe0f Master Data Management")
    info(
        "Edit or permanently delete any vessel. All changes write back to the live "
        "<code>vessel_db</code> which is the single source of truth for every part of the app. "
        "Deleted vessels are completely removed and will not appear anywhere. "
        "Changes persist for this browser session; restart the app to restore factory defaults."
    )

    db_mgmt   = get_db()
    all_names = sorted(db_mgmt.keys())
    if not all_names:
        st.error("No vessels in the database.")
        st.stop()

    sel_vessel = st.selectbox("Select vessel to edit or delete", all_names, key="mgmt_sel")
    v_cur      = db_mgmt[sel_vessel]

    bbl_cur = round(m3_to_bbl(v_cur["tank_m3_98"]))
    st.markdown(f"""
    <div style="display:flex;gap:8px;margin-bottom:1rem;flex-wrap:wrap">
      <span class="badge badge-ok">{v_cur['class']}</span>
      <span class="badge badge-blue">Tropical DWT {v_cur['dwt']:,.0f} MT</span>
      <span class="badge badge-blue">Tank {bbl_cur:,} Bbls</span>
      <span class="badge badge-blue">TLD {v_cur['draft_full']} m</span>
      <span class="badge badge-blue">Cb {v_cur['block_coeff']:.4f}</span>
    </div>""", unsafe_allow_html=True)

    edit_col, del_col = st.columns([3, 1.1], gap="large")

    with edit_col:
        st.markdown("<h3>\u270f\ufe0f Edit Specifications</h3>", unsafe_allow_html=True)
        info("Edit any field and click <strong>Save Changes</strong>. "
             "Class, barrel capacity and lightship recompute automatically on save.")

        with st.form(f"edit_form_{sel_vessel}"):
            ec1, ec2, ec3 = st.columns(3)
            with ec1:
                e_dwt   = st.number_input("Tropical DWT (MT)",  1000.0, 350000.0, float(v_cur["dwt"]),   500.0)
                e_grt   = st.number_input("GRT",                 500.0, 200000.0, float(v_cur["grt"]),   500.0)
                e_disp  = st.number_input("Full Displacement (MT)", 1000.0, 400000.0,
                                           float(v_cur["displacement"]), 500.0,
                                           help="= Lightship + Tropical DWT")
                e_const = st.number_input("Ship\u2019s Constant (MT)", 0.0, 1000.0,
                                           float(v_cur["constant"]), 5.0)
            with ec2:
                e_tank  = st.number_input("98% Tank Cap (m\u00b3)", 100.0, 250000.0,
                                           float(v_cur["tank_m3_98"]), 100.0)
                e_loa   = st.number_input("LOA (m)",  50.0, 340.0, float(v_cur["loa"]),  1.0)
                e_beam  = st.number_input("Beam (m)", 10.0,  70.0, float(v_cur["beam"]), 0.5)
                e_keel  = st.number_input("Keel (m)",  0.0,  60.0, float(v_cur["keel"]), 0.5)
            with ec3:
                e_draft = st.number_input("Tropical Load Line Draft / TLD (m)", 2.0, 25.0,
                                           float(v_cur["draft_full"]), 0.01,
                                           help="Maximum operational draft per ILLC 1966 in tropical zone.")
                e_cb    = st.number_input("Block Coeff Cb", 0.3, 1.0,
                                           float(v_cur["block_coeff"]), 0.001, format="%.4f")
                e_bwlat = st.number_input("Breakwater LAT (m)", 0.0, 20.0,
                                           float(v_cur["breakwater_lat"]), 0.05)
                e_api   = st.number_input("Reference API (\u00b0)", 5.0, 60.0,
                                           float(v_cur["api_ref"]), 0.5)

            e_note = st.text_area("Notes", value=v_cur.get("note", ""), height=68)

            e_auto_cls  = classify_vessel(e_dwt)
            e_bbl       = round(m3_to_bbl(e_tank))
            e_lightship = e_disp - e_dwt
            st.markdown(
                f"<div class='info-box' style='margin-top:6px'>Auto-computed \u2014 "
                f"Class: <strong>{e_auto_cls}</strong> &nbsp;|&nbsp; "
                f"Tank 98%: <strong>{e_bbl:,} US Bbls</strong> &nbsp;|&nbsp; "
                f"Lightship: <strong>{e_lightship:,.0f} MT</strong></div>",
                unsafe_allow_html=True)

            if st.form_submit_button("\U0001f4be Save Changes", use_container_width=True):
                updated = copy.deepcopy(v_cur)
                updated.update({
                    "class":e_auto_cls,"dwt":e_dwt,"grt":e_grt,
                    "tank_m3_98":e_tank,"keel":e_keel,"loa":e_loa,"beam":e_beam,
                    "displacement":e_disp,"constant":e_const,
                    "draft_full":e_draft,"block_coeff":e_cb,
                    "breakwater_lat":e_bwlat,"api_ref":e_api,"note":e_note,
                })
                save_vessel(updated)
                st.success(f"\u2705 **{sel_vessel}** updated. All tabs reflect new specifications.")
                st.rerun()

    with del_col:
        st.markdown("<h3>\U0001f5d1\ufe0f Delete Vessel</h3>", unsafe_allow_html=True)
        danger(
            f"<strong>{sel_vessel}</strong> will be permanently removed from the live database. "
            "It will not appear in the sidebar, fleet browser, or any calculation. "
            "This cannot be undone within this session.")
        st.markdown("**Type the vessel name exactly to unlock:**")
        confirm_name = st.text_input("Confirm vessel name", placeholder=sel_vessel,
                                      key="del_confirm_input", label_visibility="collapsed")
        confirmed = confirm_name.strip() == sel_vessel
        if not confirmed and confirm_name.strip():
            st.caption("\u26a0 Name does not match \u2014 button locked")

        if st.button(f"\U0001f5d1\ufe0f Delete {sel_vessel}", key="del_vessel_btn",
                     disabled=not confirmed, use_container_width=True):
            if confirmed:
                delete_vessel(sel_vessel)
                st.session_state.pop("del_confirm_input", None)
                st.success(f"\u2705 **{sel_vessel}** permanently removed. All references cleared.")
                st.rerun()

    # Fleet register
    st.markdown("<hr class='sec-div'>", unsafe_allow_html=True)
    section("Current Fleet Register")
    info(f"Live vessel count: <strong>{len(get_db())}</strong> vessels in database")

    reg_rows = []
    for nm, v in sorted(get_db().items()):
        reg_rows.append({
            "Vessel":        nm,
            "Class":         v["class"],
            "Tropical DWT":  f"{v['dwt']:,.0f} MT",
            "Tank (Bbls)":   f"{round(m3_to_bbl(v['tank_m3_98'])):,}",
            "TLD (m)":       v["draft_full"],
            "Cb":            f"{v['block_coeff']:.4f}",
            "Bkwtr (m)":     v["breakwater_lat"],
        })
    n = len(reg_rows)
    st.dataframe(pd.DataFrame(reg_rows), use_container_width=True, hide_index=True,
                 height=min(620, max(200, 36 * n + 40)))
    st.caption(f"{n} vessel(s) in fleet  \u00b7  \u03c1_sw = {sw_density:.4f} t/m\u00b3")


# ════════════════════════════════════════════════════════════════════════════
# TAB 6  —  Import from Q88
# ════════════════════════════════════════════════════════════════════════════
with tab6:
    section("📄 Import Vessel from Q88 PDF")
    info(
        "Upload a Q88 (INTERTANKO Chartering Questionnaire 88) PDF to automatically extract "
        "vessel parameters. The extractor handles <strong>Q88 Version 5 and Version 6</strong> "
        "and resolves common formatting variations between classification societies. "
        "All extracted values are pre-filled into a review form below — "
        "<strong>verify and correct before saving</strong>. "
        "Fields not available in the Q88 (API gravity, breakwater depth, block coefficient) "
        "must be entered manually."
    )

    if not _PDFPLUMBER_OK:
        st.error(
            "⚠ The `pdfplumber` library is not installed. "
            "Run `pip install pdfplumber` and restart the app to enable Q88 import."
        )
    else:
        q88_file = st.file_uploader(
            "Upload Q88 PDF", type=["pdf"],
            help="Upload the vessel's Q88 document. Only the PDF text layer is read — "
                 "scanned image-only Q88s cannot be extracted automatically.",
            key="q88_upload",
        )

        if q88_file is not None:
            with st.spinner("Extracting vessel data from Q88…"):
                try:
                    import pdfplumber, io as _io
                    with pdfplumber.open(_io.BytesIO(q88_file.read())) as _pdf:
                        _raw = "\n".join(p.extract_text() or "" for p in _pdf.pages)
                    q88 = extract_q88_fields(_raw)
                    st.session_state["_q88_extracted"] = q88
                    st.session_state["_q88_filename"]  = q88_file.name
                except Exception as ex:
                    st.error(f"Extraction failed: {ex}")
                    q88 = None
        else:
            q88 = st.session_state.get("_q88_extracted")

        if q88:
            fname = st.session_state.get("_q88_filename", "uploaded Q88")

            # ── Extraction summary ────────────────────────────────────────
            missing = q88.get("_missing", [])
            n_extracted = sum(1 for k in ["name","loa","beam","draft_full","dwt","displacement","tank_m3_98"]
                              if q88.get(k) is not None)

            if missing:
                st.markdown(
                    f'<div class="warn-box">⚠ Extracted <strong>{n_extracted}/7</strong> core fields '
                    f'from <em>{fname}</em>. '
                    f'Missing: <strong>{", ".join(missing)}</strong> — enter these manually below.</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="info-box">✅ All core fields extracted from <em>{fname}</em>. '
                    f'Review values below before saving to fleet.</div>',
                    unsafe_allow_html=True,
                )

            # Show raw extraction table for transparency
            with st.expander("📋 Raw extraction results (for verification)"):
                _raw_rows = [
                    ("Vessel name",            q88.get("name") or "—"),
                    ("LOA (m)",                q88.get("loa") or "—"),
                    ("LBP (m)",                q88.get("lbp") or "— (LOA will be used)"),
                    ("Beam (m)",               q88.get("beam") or "—"),
                    ("KTM / Keel field (m)",   q88.get("keel") or "—"),
                    ("GRT",                    q88.get("grt") or "—"),
                    ("Tropical DWT (MT)",      q88.get("dwt") or "—"),
                    ("Tropical Draft / TLD (m)", q88.get("draft_full") or "—"),
                    ("Lightship disp. (MT)",   q88.get("lightship") or "—"),
                    ("Full displacement (MT)",  q88.get("displacement") or "—"),
                    ("Ship's Constant (MT)",   q88.get("constant") or "—"),
                    ("98% Tank Capacity (m³, excl. slop)", f"{q88.get('tank_m3_98'):,.2f}" if q88.get('tank_m3_98') else "—"),
                    ("Slop Tanks 98% (m³, Q88-8.3)", f"{q88.get('slop_m3'):,.2f}" if q88.get('slop_m3') else "— (not found)"),
                    ("Combined with Slop (m³)", f"{(q88.get('tank_m3_98') or 0) + (q88.get('slop_m3') or 0):,.2f}"),
                    ("Tank field source",      q88.get("tank_src") or "—"),
                ]
                st.dataframe(
                    pd.DataFrame(_raw_rows, columns=["Field", "Extracted Value"]),
                    use_container_width=True, hide_index=True, height=420,
                )
                st.caption(
                    "Displacement shown is lightship + Tropical DWT (more reliable than "
                    "the displacement cell in the Q88 loadline table, which can be rounded). "
                    "If the Q88 lightship was rounded, displacement may be off by ≤ 25 MT — correct it below."
                )

            st.markdown("<hr class='sec-div'>", unsafe_allow_html=True)
            st.markdown("<h3>✏️ Review & Complete — then Save to Fleet</h3>", unsafe_allow_html=True)
            info(
                "Fields pre-filled from the Q88 are shown with their extracted values. "
                "Fields the Q88 does not contain (API gravity, breakwater LAT, block coefficient) "
                "are blank and <strong>must be entered manually</strong>. "
                "The <strong>block coefficient</strong> is computed automatically from your inputs "
                "when you save — you do not need to enter it."
            )

            # ── Review form ───────────────────────────────────────────────
            with st.form("q88_review_form"):
                rc1, rc2, rc3 = st.columns(3)

                with rc1:
                    r_name  = st.text_input(
                        "Vessel Name *",
                        value=q88.get("name") or "",
                    )
                    # Use LBP if available (better for Cb calc), else LOA
                    _loa_default = q88.get("lbp") or q88.get("loa") or 0.0
                    r_loa   = st.number_input(
                        "LOA / LBP (m) *",
                        min_value=10.0, max_value=400.0,
                        value=float(_loa_default) if _loa_default else 10.0,
                        step=0.1, format="%.2f",
                        help="LBP (Length Between Perpendiculars) is used in the Cb calculation "
                             "and has been pre-filled from Q88 field 1.28 where available. "
                             "If only LOA was found (field 1.27), it has been used instead.",
                    )
                    r_beam  = st.number_input(
                        "Beam (m) *",
                        min_value=5.0, max_value=100.0,
                        value=float(q88.get("beam") or 20.0),
                        step=0.1, format="%.2f",
                    )
                    r_keel  = st.number_input(
                        "Keel to Masthead / KTM (m)",
                        min_value=0.0, max_value=80.0,
                        value=float(q88.get("keel") or 35.0),
                        step=0.1,
                        help="Q88 field 1.31 — Keel to Masthead height.",
                    )

                with rc2:
                    r_grt   = st.number_input(
                        "GRT *",
                        min_value=100.0, max_value=300000.0,
                        value=float(q88.get("grt") or 5000.0),
                        step=100.0,
                    )
                    r_dwt   = st.number_input(
                        "Tropical DWT (MT) *",
                        min_value=100.0, max_value=400000.0,
                        value=float(q88.get("dwt") or 1000.0),
                        step=100.0,
                        help="Deadweight at Tropical Load Line (Q88 field 1.39, Tropical row).",
                    )
                    r_disp  = st.number_input(
                        "Full Load Displacement (MT) *",
                        min_value=100.0, max_value=500000.0,
                        value=float(q88.get("displacement") or 1000.0),
                        step=100.0,
                        help="= Lightship + Tropical DWT. Pre-filled as lightship + DWT. "
                             "Correct if the Q88 lightship was rounded.",
                    )
                    # Tank capacity with optional slop inclusion
                    _cargo_tank = float(q88.get("tank_m3_98") or 1000.0)
                    _slop_tank  = float(q88.get("slop_m3") or 0.0)
                    _slop_label = (f" + {_slop_tank:,.2f} m³ slop (Q88 8.3)"
                                   if _slop_tank > 0 else " (no slop found in Q88)")
                    _incl_slop = st.checkbox(
                        f"Include slop tanks in 98% capacity? ({_slop_tank:,.2f} m³){_slop_label}",
                        value=(_slop_tank > 0),
                        help="Slop tanks extracted from Q88 section 8.3. In Nigerian shuttle "
                             "operations slops routinely carry cargo — tick to include them "
                             "in the total 98% capacity used for the loading limits."
                    ) if _slop_tank > 0 else False
                    _tank_default = _cargo_tank + (_slop_tank if _incl_slop else 0.0)
                    r_tank  = st.number_input(
                        "98% Tank Capacity (m³) *",
                        min_value=10.0, max_value=300000.0,
                        value=float(_tank_default),
                        step=10.0,
                        help=f"Source: {q88.get('tank_src', 'Q88 cargo section')}. "
                             f"Cargo tanks (8.2a): {_cargo_tank:,.2f} m³. "
                             f"Slop tanks (8.3): {_slop_tank:,.2f} m³. "
                             "Check the box above to add slops automatically.",
                    )
                    if _slop_tank > 0:
                        st.caption(
                            f"{'✅ Slops included' if _incl_slop else '⬜ Slops excluded'}: "
                            f"cargo {_cargo_tank:,.2f} m³ "
                            f"{'+ ' + f'{_slop_tank:,.2f}' if _incl_slop else ''} "
                            f"= **{r_tank:,.2f} m³** "
                            f"({round(r_tank * 6.28981):,} US Bbls)"
                        )

                with rc3:
                    r_draft = st.number_input(
                        "Tropical Load Line Draft / TLD (m) *",
                        min_value=1.0, max_value=30.0,
                        value=float(q88.get("draft_full") or 7.0),
                        step=0.001, format="%.3f",
                        help="Tropical draft from Q88 field 1.39, Tropical row. "
                             "This is the maximum operational draft in the tropical zone.",
                    )
                    r_const = st.number_input(
                        "Ship's Constant (MT)",
                        min_value=0.0, max_value=2000.0,
                        value=float(q88.get("constant") or 200.0),
                        step=5.0,
                        help="Q88 field 1.42. Unmeasured permanent weights. "
                             "If blank in the Q88, use a class-typical estimate.",
                    )
                    r_bfw   = st.number_input(
                        "Default Bunker + FW (MT)",
                        min_value=0.0, max_value=10000.0,
                        value=500.0, step=50.0,
                        help="Not in Q88 — enter typical operational bunker + fresh water "
                             "for this vessel. Used as the default starting value in the "
                             "sidebar deductions.",
                    )
                    r_bwlat = st.number_input(
                        "Breakwater LAT at Loading Point (m)",
                        min_value=0.0, max_value=20.0,
                        value=3.45, step=0.05,
                        help="Not in Q88 — depth at Lowest Astronomical Tide at the vessel's "
                             "usual loading location. San Barth = 3.45 m, Awoba = 3.30 m, "
                             "BIA/offshore = 11.3 m.",
                    )

                st.markdown("<hr class='sec-div'>", unsafe_allow_html=True)
                rc4, rc5 = st.columns(2)
                with rc4:
                    r_api  = st.number_input(
                        "Reference API Gravity (°)",
                        min_value=5.0, max_value=60.0,
                        value=27.0, step=0.5,
                        help="Not in Q88 — enter the typical crude API for this vessel's cargo. "
                             "Used as the sidebar default. Can be overridden at any time.",
                    )
                with rc5:
                    r_note = st.text_area(
                        "Notes",
                        value=f"Imported from Q88: {fname}",
                        height=80,
                    )

                # Live preview of auto-computed values
                _auto_cls = classify_vessel(r_dwt)
                _auto_bbl = round(m3_to_bbl(r_tank))
                _auto_ls  = r_disp - r_dwt
                # Auto block coeff from Q88 data (will be stored in DB)
                _auto_cb  = (r_disp / 1.025) / (r_loa * r_beam * r_draft) if (r_loa * r_beam * r_draft) > 0 else 0.75
                st.markdown(
                    f"<div class='info-box'>Auto-computed — "
                    f"Class: <strong>{_auto_cls}</strong> &nbsp;|&nbsp; "
                    f"Tank 98%: <strong>{_auto_bbl:,} US Bbls</strong> ({r_tank:,.1f} m³) &nbsp;|&nbsp; "
                    f"Lightship: <strong>{_auto_ls:,.0f} MT</strong> &nbsp;|&nbsp; "
                    f"Cb: <strong>{_auto_cb:.4f}</strong> (from displacement / 1.025 / L×B×TLD)"
                    f"</div>",
                    unsafe_allow_html=True,
                )

                save_q88 = st.form_submit_button(
                    "💾 Save to Fleet", use_container_width=True,
                )

                if save_q88:
                    nn = r_name.strip()
                    if not nn:
                        st.error("Vessel name is required.")
                    elif nn in get_db():
                        st.error(
                            f"'{nn}' already exists in the fleet. "
                            "Rename it or delete the existing entry in Master Data first."
                        )
                    else:
                        save_vessel({
                            "name":          nn,
                            "class":         _auto_cls,
                            "dwt":           r_dwt,
                            "grt":           r_grt,
                            "tank_m3_98":    r_tank,
                            "keel":          r_keel,
                            "loa":           r_loa,
                            "beam":          r_beam,
                            "displacement":  r_disp,
                            "constant":      r_const,
                            "bunker_fw":     r_bfw,
                            "draft_full":    r_draft,
                            "block_coeff":   round(_auto_cb, 4),
                            "breakwater_lat": r_bwlat,
                            "api_ref":       r_api,
                            "note":          r_note,
                        })
                        # Clear the cached extraction so the uploader resets
                        st.session_state.pop("_q88_extracted", None)
                        st.session_state.pop("_q88_filename", None)
                        st.success(
                            f"✅ **{nn}** saved to fleet. "
                            f"Class: **{_auto_cls}** | Cb: **{round(_auto_cb,4)}** | "
                            f"Tank: **{_auto_bbl:,} Bbls** | TLD: **{r_draft} m**. "
                            "Select it from the sidebar to run calculations."
                        )
                        st.rerun()

        else:
            # No file uploaded yet — show guidance
            st.markdown("""
<div class="info-box" style="margin-top:1rem">
<strong>How to use this tab:</strong><br>
1. Upload the vessel's Q88 PDF using the uploader above.<br>
2. The extractor reads the text layer (Q88 Version 5 and 6 are both supported).<br>
3. Extracted values pre-fill the review form. Verify each field — correct any rounding.<br>
4. Enter the fields the Q88 does not contain: API gravity and breakwater LAT for the typical loading location.<br>
5. Click <strong>Save to Fleet</strong>. The vessel is immediately available in the sidebar.<br><br>
<strong>Fields extracted from Q88:</strong> Name · LOA (LBP preferred) · Beam · KTM · GRT · Tropical DWT · Tropical Draft (TLD) · Lightship · Constant · 98% Tank Capacity<br><br>
<strong>Fields you must enter:</strong> Reference API gravity · Breakwater LAT · Default bunker + FW · Notes<br><br>
<strong>Auto-computed on save:</strong> Vessel class (from DWT) · Block coefficient Cb (from displacement / 1.025 / L×B×TLD) · Tank capacity in US Bbls
</div>
""", unsafe_allow_html=True)
