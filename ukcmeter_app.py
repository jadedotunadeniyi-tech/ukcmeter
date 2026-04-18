"""
Vessel Stowage Calculator — v3
================================
Nigerian offshore crude oil loading plan tool.

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
@import url('https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&family=JetBrains+Mono:wght@400;500;600&display=swap');

/* ══ Design Tokens ══════════════════════════════════════════════════ */
:root {
  /* Backgrounds — true Apple dark hierarchy */
  --sys-bg:          #000000;      /* System background — true black */
  --sys-bg2:         #0a0a0a;      /* Elevated background */
  --sys-surface:     #141414;      /* Card / panel surface */
  --sys-surface2:    #1c1c1e;      /* Secondary surface (iOS grouped) */
  --sys-surface3:    #2c2c2e;      /* Tertiary / input fill */
  --sys-separator:   #38383a;      /* Hairline separator */
  --sys-separator2:  #545458;      /* Secondary separator */

  /* iOS System Colours */
  --sys-blue:        #007AFF;      /* iOS blue — primary accent */
  --sys-blue-light:  #409CFF;      /* Lighter blue for text on dark */
  --sys-green:       #30D158;      /* iOS green */
  --sys-orange:      #FF9F0A;      /* iOS orange */
  --sys-red:         #FF453A;      /* iOS red */
  --sys-yellow:      #FFD60A;      /* iOS yellow */
  --sys-teal:        #40C8E0;      /* iOS teal */
  --sys-purple:      #BF5AF2;      /* iOS purple */
  --sys-indigo:      #5E5CE6;      /* iOS indigo */

  /* Text colours */
  --sys-label:       #FFFFFF;      /* Primary label */
  --sys-label2:      rgba(255,255,255,0.60);  /* Secondary label */
  --sys-label3:      rgba(255,255,255,0.30);  /* Tertiary label */
  --sys-label4:      rgba(255,255,255,0.18);  /* Quaternary label */
  --sys-placeholder: rgba(255,255,255,0.25);

  /* Semantic aliases (keep backward compat) */
  --accent:   var(--sys-blue);
  --accent2:  var(--sys-orange);
  --accent3:  var(--sys-green);
  --danger:   var(--sys-red);
  --text:     var(--sys-label);
  --muted:    var(--sys-label2);
  --border:   var(--sys-separator);
  --surface:  var(--sys-surface2);
  --surface2: var(--sys-surface3);

  --mono: 'JetBrains Mono', 'SF Mono', ui-monospace, monospace;
  --sans: 'Inter', -apple-system, 'SF Pro Display', system-ui, sans-serif;
}

/* ══ Global reset ═══════════════════════════════════════════════════ */
*, *::before, *::after { box-sizing: border-box; }
html, body, [class*="css"] {
  font-family: var(--sans);
  background: var(--sys-bg) !important;
  color: var(--sys-label);
  font-size: 14px;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* ══ Apple-style scrollbars ═════════════════════════════════════════
   Overlay scrollbars: thin, fade on idle, no track */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
  background: rgba(255,255,255,0.20);
  border-radius: 100px;
  transition: background 0.2s;
}
::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.40); }
::-webkit-scrollbar-corner { background: transparent; }
* { scrollbar-width: thin; scrollbar-color: rgba(255,255,255,0.18) transparent; }

/* ══ Force dark background ══════════════════════════════════════════ */
[data-testid="stApp"],
[data-testid="stAppViewContainer"],
.stApp,
[data-testid="block-container"],
.main, .main > div { background: var(--sys-bg) !important; }

/* ══ Sidebar ════════════════════════════════════════════════════════ */
section[data-testid="stSidebar"] {
  background: var(--sys-bg2) !important;
  border-right: 0.5px solid var(--sys-separator) !important;
}
section[data-testid="stSidebar"] * { color: var(--sys-label) !important; }

/* ══ Main layout ════════════════════════════════════════════════════ */
.main .block-container {
  padding: 0 1.5rem 4rem !important;
  max-width: 100% !important;
}

/* ══ Typography ═════════════════════════════════════════════════════ */
h1 {
  font-family: var(--sans);
  font-size: 1.35rem;
  font-weight: 700;
  color: var(--sys-label);
  letter-spacing: -0.025em;
  margin: 0 0 0.2rem;
}
h2 {
  font-family: var(--sans);
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--sys-label3);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin: 1.5rem 0 0.6rem;
}
h3 {
  font-family: var(--mono);
  font-size: 0.82rem;
  font-weight: 500;
  color: var(--sys-orange);
  margin: 0.75rem 0 0.35rem;
}
p { color: var(--sys-label2); margin: 0 0 0.5rem; }

/* ══ Form elements ══════════════════════════════════════════════════ */
input[type="number"], input[type="text"], select, textarea,
div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div {
  background: var(--sys-surface3) !important;
  border: 0.5px solid var(--sys-separator) !important;
  border-radius: 10px !important;
  color: var(--sys-label) !important;
  font-family: var(--mono) !important;
  font-size: 0.88rem !important;
}
input[type="number"]:focus,
div[data-baseweb="input"]:focus-within > div {
  border-color: var(--sys-blue) !important;
  box-shadow: 0 0 0 3px rgba(0,122,255,0.18) !important;
  outline: none !important;
}

/* ══ Buttons ════════════════════════════════════════════════════════ */
.stButton > button {
  background: var(--sys-blue) !important;
  color: #fff !important;
  font-family: var(--sans) !important;
  font-weight: 600 !important;
  font-size: 0.85rem !important;
  border: none !important;
  border-radius: 12px !important;
  padding: 0.55rem 1.3rem !important;
  letter-spacing: -0.01em;
  transition: opacity 0.15s, transform 0.1s;
}
.stButton > button:hover { opacity: 0.85 !important; }
.stButton > button:active { transform: scale(0.97); opacity: 0.75 !important; }
button[aria-label*="decrement"],
button[aria-label*="increment"] { color: var(--sys-label2) !important; }

/* ══ Labels ═════════════════════════════════════════════════════════ */
label,
.stRadio label,
.stCheckbox label,
.stSelectbox label,
.stNumberInput label,
.stTextInput label,
.stTextArea label,
.stSlider label,
.stFileUploader label {
  color: var(--sys-label2) !important;
  font-size: 0.78rem !important;
  font-family: var(--sans) !important;
  font-weight: 500 !important;
  letter-spacing: -0.005em;
}
[data-testid="stCheckbox"] > label { color: var(--sys-label) !important; font-size: 0.85rem !important; }
[data-testid="stRadio"] div[role="radiogroup"] label { color: var(--sys-label) !important; }
section[data-testid="stSidebar"] label { color: rgba(255,255,255,0.75) !important; }
.stCaption, [data-testid="stCaptionContainer"] { color: var(--sys-label3) !important; font-size: 0.72rem !important; }

/* ══ Tab bar ════════════════════════════════════════════════════════ */
div[data-baseweb="tab-list"] {
  background: var(--sys-bg2) !important;
  border-bottom: 0.5px solid var(--sys-separator) !important;
  gap: 0 !important;
}
button[data-baseweb="tab"] {
  font-family: var(--sans) !important;
  font-size: 0.8rem !important;
  font-weight: 500 !important;
  color: var(--sys-label2) !important;
  padding: 0.65rem 1rem !important;
  border-radius: 0 !important;
  letter-spacing: -0.01em;
}
button[data-baseweb="tab"][aria-selected="true"] {
  color: var(--sys-blue) !important;
  font-weight: 600 !important;
}
div[data-baseweb="tab-highlight"] { background: var(--sys-blue) !important; height: 2px !important; }
div[data-baseweb="tab-border"] { background: transparent !important; }

/* ══ Expander ═══════════════════════════════════════════════════════ */
[data-testid="stExpander"] {
  background: var(--sys-surface2) !important;
  border: 0.5px solid var(--sys-separator) !important;
  border-radius: 12px !important;
}
[data-testid="stExpander"] summary span { color: var(--sys-orange) !important; font-weight: 600; }

/* ══ Cards ══════════════════════════════════════════════════════════ */
.ukc-card {
  background: var(--sys-surface);
  border: 0.5px solid var(--sys-separator);
  border-radius: 16px;
  padding: 16px;
  margin: 8px 0;
}
.metric-card {
  background: var(--sys-surface2);
  border-radius: 12px;
  padding: 12px 14px;
  margin: 5px 0;
  border: 0.5px solid var(--sys-separator);
}
.metric-label {
  font-size: 0.66rem;
  color: var(--sys-label3);
  text-transform: uppercase;
  letter-spacing: 0.09em;
  font-family: var(--sans);
  font-weight: 600;
  margin-bottom: 3px;
}
.metric-value {
  font-size: 1.5rem;
  font-weight: 700;
  font-family: var(--mono);
  color: var(--sys-label);
  line-height: 1.1;
}
.metric-unit {
  font-size: 0.75rem;
  color: var(--sys-label2);
  font-family: var(--mono);
  margin-left: 3px;
}

/* ══ Result panel ═══════════════════════════════════════════════════ */
.result-panel {
  background: var(--sys-surface2);
  border-radius: 16px;
  padding: 20px;
  margin: 10px 0;
  border: 0.5px solid var(--sys-separator);
  position: relative;
  overflow: hidden;
}
.result-panel::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 2px;
  background: linear-gradient(90deg, var(--sys-blue), var(--sys-teal));
  border-radius: 16px 16px 0 0;
}
.result-primary {
  font-size: 2.8rem;
  font-weight: 700;
  font-family: var(--mono);
  color: var(--sys-blue-light);
  line-height: 1;
  letter-spacing: -0.04em;
}
.result-secondary {
  font-size: 0.9rem;
  font-family: var(--sans);
  color: var(--sys-label2);
  margin-top: 4px;
  font-weight: 400;
}

/* ══ Score bars ═════════════════════════════════════════════════════ */
.score-bar-wrap { margin: 8px 0; }
.score-bar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.score-bar-label {
  font-size: 0.75rem;
  font-family: var(--sans);
  font-weight: 500;
  color: var(--sys-label2);
  letter-spacing: -0.005em;
}
.score-bar-val {
  font-size: 0.92rem;
  font-weight: 700;
  font-family: var(--mono);
}
.score-bar-bg {
  background: var(--sys-surface3);
  border-radius: 100px;
  height: 6px;
  overflow: hidden;
}
.score-bar-fill {
  height: 6px;
  border-radius: 100px;
  transition: width 0.5s cubic-bezier(0.34,1.56,0.64,1);
}

/* ══ Badges ═════════════════════════════════════════════════════════ */
.badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 9px;
  border-radius: 100px;
  font-size: 0.66rem;
  font-family: var(--sans);
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  white-space: nowrap;
}
.badge-ok   { background: rgba(48,209,88,0.15);  color: #30D158; border: 0.5px solid rgba(48,209,88,0.35); }
.badge-warn { background: rgba(255,159,10,0.15); color: #FF9F0A; border: 0.5px solid rgba(255,159,10,0.35); }
.badge-risk { background: rgba(255,69,58,0.15);  color: #FF453A; border: 0.5px solid rgba(255,69,58,0.35); }
.badge-blue { background: rgba(0,122,255,0.15);  color: #409CFF; border: 0.5px solid rgba(0,122,255,0.35); }
.badge-lock { background: rgba(94,92,230,0.15);  color: #7D7AFF; border: 0.5px solid rgba(94,92,230,0.35); }

/* ══ Info boxes ═════════════════════════════════════════════════════ */
.info-box {
  background: rgba(0,122,255,0.07);
  border: 0.5px solid rgba(0,122,255,0.22);
  border-left: 2.5px solid var(--sys-blue);
  border-radius: 10px;
  padding: 10px 14px;
  font-size: 0.81rem;
  color: var(--sys-label2);
  margin: 6px 0;
  font-family: var(--sans);
  line-height: 1.55;
}
.warn-box {
  background: rgba(255,159,10,0.07);
  border: 0.5px solid rgba(255,159,10,0.25);
  border-left: 2.5px solid var(--sys-orange);
  border-radius: 10px;
  padding: 10px 14px;
  font-size: 0.81rem;
  color: #FFD60A;
  margin: 6px 0;
  font-family: var(--sans);
  line-height: 1.55;
}
.danger-box {
  background: rgba(255,69,58,0.07);
  border: 0.5px solid rgba(255,69,58,0.25);
  border-left: 2.5px solid var(--sys-red);
  border-radius: 10px;
  padding: 10px 14px;
  font-size: 0.81rem;
  color: #FF6961;
  margin: 6px 0;
  font-family: var(--sans);
  line-height: 1.55;
}
.limit-box {
  background: rgba(48,209,88,0.06);
  border: 0.5px solid rgba(48,209,88,0.22);
  border-left: 2.5px solid var(--sys-green);
  border-radius: 10px;
  padding: 10px 14px;
  font-size: 0.8rem;
  color: #30D158;
  margin: 6px 0;
  font-family: var(--mono);
  line-height: 1.6;
}

/* ══ Locked display ═════════════════════════════════════════════════ */
.locked-display {
  background: rgba(94,92,230,0.09);
  border: 0.5px solid rgba(94,92,230,0.28);
  border-radius: 10px;
  padding: 8px 12px;
  margin: 4px 0;
}
.locked-label {
  font-size: 0.64rem;
  color: #7D7AFF;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  font-family: var(--sans);
  font-weight: 600;
  margin-bottom: 2px;
}
.locked-value {
  font-size: 1rem;
  font-weight: 700;
  font-family: var(--mono);
  color: #A78BFA;
}

/* ══ Sidebar brand / section headers ════════════════════════════════ */
.sidebar-brand {
  padding: 16px 14px 12px;
  border-bottom: 0.5px solid var(--sys-separator);
  margin-bottom: 8px;
}
.sidebar-title {
  font-size: 0.95rem;
  font-weight: 800;
  font-family: var(--mono);
  color: var(--sys-blue-light);
  letter-spacing: 0.04em;
}
.sidebar-sub {
  font-size: 0.67rem;
  color: var(--sys-label3);
  font-family: var(--sans);
  margin-top: 2px;
}
.sidebar-section {
  font-size: 0.62rem;
  font-weight: 700;
  font-family: var(--sans);
  color: var(--sys-label3);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  margin: 12px 0 4px;
  padding: 0 2px;
}

/* ══ App header strip ═══════════════════════════════════════════════ */
.app-header {
  background: var(--sys-bg2);
  border-bottom: 0.5px solid var(--sys-separator);
  padding: 12px 20px 10px;
  margin: 0 -1.5rem 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
}
.app-header-left { display: flex; align-items: center; gap: 10px; }
.app-name {
  font-size: 1.1rem;
  font-weight: 800;
  font-family: var(--mono);
  color: var(--sys-blue-light);
  letter-spacing: -0.02em;
}
.app-sub {
  font-size: 0.68rem;
  color: var(--sys-label3);
  font-family: var(--sans);
  margin-top: 1px;
}
.vessel-pill {
  background: rgba(0,122,255,0.12);
  border: 0.5px solid rgba(0,122,255,0.3);
  border-radius: 100px;
  padding: 4px 14px;
  font-size: 0.8rem;
  font-weight: 600;
  font-family: var(--mono);
  color: var(--sys-blue-light);
}

/* ══ Section divider ════════════════════════════════════════════════ */
.sec-div {
  border: none;
  border-top: 0.5px solid var(--sys-separator);
  margin: 16px 0;
}

/* ══ Dataframe ══════════════════════════════════════════════════════ */
[data-testid="stDataFrame"] {
  border: 0.5px solid var(--sys-separator) !important;
  border-radius: 12px !important;
  overflow: hidden;
}
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
     "constant":500,"bunker_fw":2500,"draft_full":17.05,"block_coeff":0.7959,
     "breakwater_lat":11.3,"api_ref":28.9,"note":"Suezmax mother vessel — BIA only"},
    {"name":"Green Eagle","class":"Suezmax",
     "dwt":154164,"grt":78922,"tank_m3_98":166696.0,
     "keel":49.94,"loa":274.2,"beam":48.0,"displacement":176634.0,
     "constant":500,"bunker_fw":2500,"draft_full":16.36,"block_coeff":0.7862,
     "breakwater_lat":11.3,"api_ref":28.9,"note":"Suezmax mother vessel — BIA only"},
    {"name":"Bryanston","class":"Aframax",
     "dwt":108493,"grt":46904,"tank_m3_98":120859.9,
     "keel":48.0,"loa":244.26,"beam":42.03,"displacement":125786.0,
     "constant":203,"bunker_fw":2500,"draft_full":15.228,"block_coeff":0.7850,
     "breakwater_lat":11.35,"api_ref":28.9,"note":"Aframax mother vessel — BIA only"},
    # ── LR-1 ─────────────────────────────────────────────────────────────────
    {"name":"MT San Barth","class":"LR-1",
     "dwt":71533,"grt":40456,"tank_m3_98":77629.5,
     "keel":47.14,"loa":219.0,"beam":32.23,"displacement":84769.0,
     "constant":203,"bunker_fw":2500,"draft_full":13.901,"block_coeff":0.8429,
     "breakwater_lat":3.45,"api_ref":28.9,"note":"Permanent BIA intermediate storage; breakwater LAT 3.45 m"},
    {"name":"PRESTIGIOUS","class":"LR-1",
     "dwt":75025,"grt":31165,"tank_m3_98":75742.8,
     "keel":47.24,"loa":228.5,"beam":32.24,"displacement":88000.0,
     "constant":300,"bunker_fw":2000,"draft_full":13.8,"block_coeff":0.820,
     "breakwater_lat":11.3,"api_ref":28.9,"note":""},
    # ── MR ───────────────────────────────────────────────────────────────────
    {"name":"MT Westmore","class":"MR",
     "dwt":47418,"grt":22808,"tank_m3_98":53611.58,
     "keel":46.37,"loa":183.0,"beam":32.2,"displacement":57531.58,
     "constant":270,"bunker_fw":1500,"draft_full":12.471,"block_coeff":0.7638,
     "breakwater_lat":3.45,"api_ref":28.9,"note":"Westmore storage — dredge depth 7 m"},
    {"name":"MT Chapel","class":"MR",
     "dwt":48354,"grt":22050,"tank_m3_98":50332.4,
     "keel":45.55,"loa":182.5,"beam":32.23,"displacement":48354.0,
     "constant":270,"bunker_fw":1500,"draft_full":12.93,"block_coeff":0.6203,
     "breakwater_lat":14.0,"api_ref":28.9,"note":"Chapel storage — deep water terminal"},
    {"name":"MT Jasmine S","class":"MR",
     "dwt":47205,"grt":28150,"tank_m3_98":54244.97,
     "keel":46.27,"loa":179.88,"beam":32.23,"displacement":56048.0,
     "constant":270,"bunker_fw":1500,"draft_full":12.27,"block_coeff":0.7862,
     "breakwater_lat":3.45,"api_ref":28.9,"note":"Jasmine S storage"},
    {"name":"MT Laphroaig","class":"MR",
     "dwt":35832.8,"grt":19707,"tank_m3_98":39944.98,
     "keel":44.11,"loa":154.31,"beam":36.03,"displacement":45364.4,
     "constant":100,"bunker_fw":1500,"draft_full":9.18,"block_coeff":0.8671,
     "breakwater_lat":3.45,"api_ref":28.9,"note":"Shuttle — Chapel/JasmineS; dredge depth 2.55 m"},
    {"name":"MT Pinarello","class":"MR",
     "dwt":35832.84,"grt":19707,"tank_m3_98":39914.477,
     "keel":41.11,"loa":154.31,"beam":36.0,"displacement":45296.9,
     "constant":100,"bunker_fw":1500,"draft_full":9.203,"block_coeff":0.8640,
     "breakwater_lat":3.45,"api_ref":28.9,"note":"Shuttle — Chapel/JasmineS; dredge depth 2.55 m"},
    {"name":"MT Sherlock","class":"MR",
     "dwt":35640.4,"grt":19707,"tank_m3_98":39939.857,
     "keel":39.29,"loa":154.31,"beam":36.03,"displacement":45172.0,
     "constant":100,"bunker_fw":1500,"draft_full":9.188,"block_coeff":0.8627,
     "breakwater_lat":3.45,"api_ref":28.9,"note":"Shuttle — Jasmine S primary; dredge depth 2.55 m"},
    {"name":"MONTAGU","class":"MR",
     "dwt":47425.33,"grt":30032,"tank_m3_98":52219.03,
     "keel":46.95,"loa":183.0,"beam":32.2,"displacement":55000.0,
     "constant":270,"bunker_fw":1500,"draft_full":12.2,"block_coeff":0.780,
     "breakwater_lat":3.45,"api_ref":28.9,"note":""},
    # ── General Purpose ───────────────────────────────────────────────────────
    {"name":"MT Bedford","class":"General Purpose",
     "dwt":18568,"grt":14876,"tank_m3_98":26098.32,
     "keel":39.7,"loa":157.5,"beam":27.7,"displacement":25081.0,
     "constant":200,"bunker_fw":800,"draft_full":7.146,"block_coeff":0.620,
     "breakwater_lat":3.45,"api_ref":28.9,"note":"Ibom offshore loader; dredge depth 2.55 m"},
    {"name":"MT Bagshot","class":"General Purpose",
     "dwt":18457,"grt":9729,"tank_m3_98":20059.1,
     "keel":39.67,"loa":145.06,"beam":22.9,"displacement":23611.0,
     "constant":29,"bunker_fw":800,"draft_full":9.1,"block_coeff":0.720,
     "breakwater_lat":3.45,"api_ref":28.9,"note":"Shuttle — Barge Starturn; dredge depth 2.55 m"},
    {"name":"MT Woodstock","class":"General Purpose",
     "dwt":15761,"grt":8602,"tank_m3_98":16050.0,
     "keel":35.6,"loa":139.95,"beam":21.0,"displacement":20000.0,
     "constant":250,"bunker_fw":800,"draft_full":8.252,"block_coeff":0.760,
     "breakwater_lat":3.45,"api_ref":28.9,"note":"Shuttle — Duke (Awoba); dredge depth 2.55 m"},
    {"name":"MT Rathbone","class":"General Purpose",
     "dwt":12590.59,"grt":7446,"tank_m3_98":13082.02,
     "keel":33.2,"loa":140.95,"beam":19.6,"displacement":16145.59,
     "constant":220,"bunker_fw":800,"draft_full":6.956,"block_coeff":0.720,
     "breakwater_lat":3.45,"api_ref":28.9,"note":"Shuttle — Ibom/Balham; dredge depth 2.55 m"},
    {"name":"MT Rahama","class":"General Purpose",
     "dwt":8318.07,"grt":6204,"tank_m3_98":8265.0,
     "keel":34.0,"loa":115.0,"beam":21.4,"displacement":11620.83,
     "constant":0,"bunker_fw":400,"draft_full":6.14,"block_coeff":0.700,
     "breakwater_lat":3.3,"api_ref":28.9,"note":"Awoba shuttle"},
    {"name":"MT Enford","class":"General Purpose",
     "dwt":17300.4,"grt":11271,"tank_m3_98":18479.62,
     "keel":39.48,"loa":144.0,"beam":23.0,"displacement":23220.61,
     "constant":250,"bunker_fw":450,"draft_full":8.983,"block_coeff":0.740,
     "breakwater_lat":3.45,"api_ref":28.9,"note":"Dredge depth 2.55 m"},
    {"name":"MT Santa Monica","class":"General Purpose",
     "dwt":6208.83,"grt":4126,"tank_m3_98":5819.248,
     "keel":28.5,"loa":112.01,"beam":16.2,"displacement":8761.25,
     "constant":20,"bunker_fw":300,"draft_full":6.125,"block_coeff":0.680,
     "breakwater_lat":3.45,"api_ref":28.9,"note":"Multi-field shuttle; avg API 28.9\u00b0"},
    {"name":"Duke","class":"General Purpose",
     "dwt":19651,"grt":11118,"tank_m3_98":19137.0,
     "keel":38.62,"loa":140.0,"beam":23.0,"displacement":22000.0,
     "constant":200,"bunker_fw":600,"draft_full":8.5,"block_coeff":0.720,
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
    "\u2014 Manual entry \u2014":                None,
    "San Barth \u2014 Bonny River (3.45 m LAT)": 3.45,
    "Awoba / Cawthorne Channel (3.30 m LAT)":    3.30,
    "Export Terminal / Bonny Channel (11.2 m)":  11.20,
    "Westmore post-dredge (7.00 m)":             7.00,
    "Chapel / JasmineS pre-dredge (3.45 m)":     3.45,
    "Chapel / JasmineS post-dredge (6.00 m)":    6.00,
}

# ─────────────────────────────────────────────────────────────────────────────
# ENGINEERING CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
BBL_PER_M3           = 6.28981   # ASTM barrel conversion
SEAWATER_DENSITY_NG  = 1.0255    # t/m³ — Nigerian coastal/Bonny River estuary
                                  # (tropical brackish ~25-26 ppt, 28°C) LOCKED
FRESHWATER_DENSITY   = 1.000     # t/m³
BUNKER_DENSITY_BLEND = 0.940     # t/m³ — blended HFO + MDO
UKC_MIN_RIVER        = 0.30      # m — NNPC/ops standard, restricted waterway
UKC_MIN_OPEN         = 0.50      # m — offshore open-water standard


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
    Compute displacement at a given draft using the PROPORTIONAL method.

    Method: Δ(T) = (T / TLD) × Δ_full
    where TLD = Tropical Load Line Draft, Δ_full = full load displacement.

    This is the industry-standard planning approach used in loading computers
    and manual stowage tables. It treats the displacement-draft curve as LINEAR
    from keel (T=0) through the operating range to TLD, which matches the
    hydrostatic tables in the workbook to within ~3-5%.

    WHY NOT THE BLOCK COEFFICIENT FORMULA?
    The constant-Cb formula  Δ = Cb × L × B × T × ρ  uses the FULL-LOAD Cb
    which is calibrated at TLD only. At partial drafts the actual waterplane
    area is LARGER than the full-load Cb predicts (the hull's parallel midbody
    gives more buoyancy per metre of immersion at shallow drafts). For vessels
    with fine form (Cb < 0.75) this causes underestimation of 20-38%.
    The proportional method bypasses this by anchoring directly to the known
    full-load displacement from the vessel's hydrostatic record.
    """
    tld = v["draft_full"]
    if tld <= 0:
        return v["displacement"]
    return (draft_m / tld) * v["displacement"]


def _draft_from_displacement(v: dict, displacement_mt: float) -> float:
    """Inverse of _displacement_at_draft."""
    tld = v["draft_full"]
    if v["displacement"] <= 0:
        return 0.0
    return (displacement_mt / v["displacement"]) * tld


def volume_to_draft(v: dict, volume_m3: float, api: float,
                    bunker_mt: float, fw_mt: float, constant_mt: float) -> dict:
    """
    Predict loaded draft from cargo volume.

    Uses the PROPORTIONAL DISPLACEMENT method (industry standard for loading plans):
      loaded_displacement = lightship + cargo_mass + deductions
      draft = (loaded_displacement / full_displacement) × TLD

    Clamps volume to the binding limit (98% tank capacity or available Tropical DWT,
    whichever is smaller). Warns if the requested volume exceeds either limit.
    """
    sg         = api_to_sg(api)
    limits     = compute_limits(v, bunker_mt, fw_mt, constant_mt, api)
    tank_98    = v["tank_m3_98"]
    lightship  = lightship_mass(v)
    deductions = bunker_mt + fw_mt + constant_mt
    tld        = v["draft_full"]

    # Flags before clamping
    exceeds_tank         = volume_m3 > tank_98
    cargo_mass_unclamped = volume_m3 * sg
    exceeds_dwt          = cargo_mass_unclamped > limits["avail_dwt_mt"]

    # Clamp to binding limit
    volume_m3_clamped = min(volume_m3, limits["max_cargo_m3"])
    clamped           = volume_m3_clamped < volume_m3

    cargo_mass  = volume_m3_clamped * sg
    total_disp  = lightship + cargo_mass + deductions

    # Proportional draft: anchored to known full-load displacement
    draft_m     = _draft_from_displacement(v, total_disp)

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
        "tld_m":               tld,
        "over_tld":            draft_m > tld,
        "tank_98_m3":          tank_98,
        "tank_98_bbl":         round(m3_to_bbl(tank_98)),
        "tank_util_pct":       round(util_vol, 1),
        "dwt_util_pct":        round(util_dwt, 1),
    }

def draft_to_volume(v: dict, draft_m: float, api: float,
                    bunker_mt: float, fw_mt: float, constant_mt: float) -> dict:
    """
    Back-calculate cargo volume from a target draft.

    Uses the PROPORTIONAL DISPLACEMENT method:
      displacement_at_draft = (draft / TLD) × full_displacement
      cargo_mass = displacement_at_draft - lightship - deductions
      volume = cargo_mass / SG

    Clamps result to binding limit (98% tank capacity or available Tropical DWT).
    """
    sg         = api_to_sg(api)
    limits     = compute_limits(v, bunker_mt, fw_mt, constant_mt, api)
    lightship  = lightship_mass(v)
    deductions = bunker_mt + fw_mt + constant_mt
    tank_98    = v["tank_m3_98"]
    tld        = v["draft_full"]

    # Displacement at this draft — proportional to full-load displacement
    total_disp      = _displacement_at_draft(v, draft_m)
    cargo_mass_raw  = total_disp - lightship - deductions
    volume_m3_raw   = max(0.0, cargo_mass_raw / sg)

    # Apply binding limit
    volume_m3   = min(volume_m3_raw, limits["max_cargo_m3"])
    cargo_mass  = volume_m3 * sg
    clamped     = volume_m3 < volume_m3_raw

    util_vol  = (volume_m3 / tank_98) * 100 if tank_98 else 0
    util_dwt  = (cargo_mass / limits["avail_dwt_mt"]) * 100 if limits["avail_dwt_mt"] > 0 else 0

    return {
        "sg": sg, "limits": limits,
        "draft_input_m":    draft_m,
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

def ukc_assessment(draft_m: float, water_depth: float) -> dict:
    ukc     = water_depth - draft_m
    ukc_req = max(UKC_MIN_RIVER, draft_m * 0.10)
    status  = "ADEQUATE" if ukc >= ukc_req else ("MARGINAL" if ukc >= 0 else "AGROUND RISK")
    return {"ukc_m": round(ukc, 2), "ukc_required_m": round(ukc_req, 2), "ukc_status": status}

# ── Utilisation scoring — recalibrated to charter party & INTERTANKO standards ──
# Tank utilisation (cargo vol vs 98% physical capacity):
#   97-100%: OPTIMAL  — at or near MOLCO / commercial target
#   90-97%:  GOOD     — acceptable, typical multi-grade / partial
#   75-90%:  PARTIAL  — below optimum; may trigger freight adjustment
#   50-75%:  LOW      — material shortfall; ops review warranted
#   <50%:    CRITICAL — gross under-utilisation; likely constraint or error
#
# DWT utilisation (cargo mass vs available Tropical DWT):
#   95-100%: OPTIMAL  — full tropical deadweight utilised
#   85-95%:  GOOD     — minor headroom, typical with deductions uncertainty
#   70-85%:  PARTIAL  — draft or UKC constrained
#   50-70%:  LOW      — significant weight constraint
#   <50%:    CRITICAL — very limited cargo relative to vessel capacity

def tank_util_color(pct: float) -> str:
    """Colour for tank volumetric utilisation."""
    if pct >= 97: return "#10b981"   # emerald — OPTIMAL
    if pct >= 90: return "#34d399"   # emerald-light — GOOD
    if pct >= 75: return "#f59e0b"   # amber — PARTIAL
    if pct >= 50: return "#f97316"   # orange — LOW
    return "#ef4444"                  # red — CRITICAL

def dwt_util_color(pct: float) -> str:
    """Colour for DWT weight utilisation."""
    if pct >= 95: return "#10b981"
    if pct >= 85: return "#34d399"
    if pct >= 70: return "#f59e0b"
    if pct >= 50: return "#f97316"
    return "#ef4444"

def tank_util_label(pct: float) -> tuple[str, str]:
    """Label + badge class for tank volumetric utilisation."""
    if pct >= 97: return "OPTIMAL",  "badge-ok"
    if pct >= 90: return "GOOD",     "badge-ok"
    if pct >= 75: return "PARTIAL",  "badge-warn"
    if pct >= 50: return "LOW",      "badge-warn"
    return "CRITICAL", "badge-risk"

def dwt_util_label(pct: float) -> tuple[str, str]:
    """Label + badge class for DWT weight utilisation."""
    if pct >= 95: return "OPTIMAL",  "badge-ok"
    if pct >= 85: return "GOOD",     "badge-ok"
    if pct >= 70: return "PARTIAL",  "badge-warn"
    if pct >= 50: return "LOW",      "badge-warn"
    return "CRITICAL", "badge-risk"

# Legacy aliases used by fleet comparison loop
def util_color(pct: float) -> str:
    return tank_util_color(pct)

def score_label(pct: float) -> tuple[str, str]:
    return tank_util_label(pct)


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

def score_bar(pct: float, label: str = "", mode: str = "tank") -> None:
    """
    Render a utilisation progress bar.
    mode="tank" uses tank_util thresholds (97/90/75/50).
    mode="dwt"  uses dwt_util thresholds  (95/85/70/50).
    """
    if mode == "dwt":
        color = dwt_util_color(pct)
        sl, sb = dwt_util_label(pct)
    else:
        color = tank_util_color(pct)
        sl, sb = tank_util_label(pct)
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


def ukc_badge(status: str, ukc: float, required: float,
              depth_m: float = None, draft_m: float = None) -> None:
    """
    Render the UKC Meter gauge — Apple/Tesla quality — via components.html().
    Layout: UKC reading above the arc, status label below, SAFE/RISK at arc ends.
    Zero text overlap by design.
    """
    import math
    import streamlit.components.v1 as _comp

    # ── Status colours (iOS system palette) ──────────────────────────
    if status == "ADEQUATE":
        clr = "#30D158"; bg = "rgba(48,209,88,0.12)"; bc = "rgba(48,209,88,0.35)"
    elif status == "MARGINAL":
        clr = "#FF9F0A"; bg = "rgba(255,159,10,0.12)"; bc = "rgba(255,159,10,0.35)"
    else:
        clr = "#FF453A"; bg = "rgba(255,69,58,0.12)"; bc = "rgba(255,69,58,0.40)"
    icon = {"ADEQUATE": "✓", "MARGINAL": "⚠"}.get(status, "⚠")

    # ── Needle position (frac 0=safe/left → 1=aground/right) ────────
    if depth_m and depth_m > 0 and draft_m is not None:
        frac = min(1.0, max(0.0, draft_m / depth_m))
    elif required > 0:
        # Proxy: how much of the "double-required" buffer is consumed
        headroom = ukc / (required * 2.0)
        frac = max(0.0, min(1.0, 1.0 - headroom))
    else:
        frac = 0.3

    # ── Geometry ─────────────────────────────────────────────────────
    # viewBox gives generous padding so nothing clips
    VW, VH   = 280, 220    # viewBox dimensions
    cx       = VW // 2     # 140 — centre x
    cy       = 160          # centre y — pushed down so arc sits in upper 3/4

    R_track  = 100          # outer radius of track
    R_fill   = 86           # inner radius of track (14px track width)
    R_needle = 78           # needle tip radius
    R_hub    = 6            # hub circle radius

    START    = 215          # leftmost angle (CCW from east, i.e. ~7-o'clock)
    SWEEP    = 250          # total sweep — wider arc = more resolution

    def _x(r, deg): return cx + r * math.cos(math.radians(deg))
    def _y(r, deg): return cy - r * math.sin(math.radians(deg))

    # Zone boundaries (CCW from east)
    ang_safe    = START                    # leftmost = safest
    ang_end     = START - SWEEP            # rightmost = aground
    ang_amber   = START - SWEEP * 0.30    # 30% → amber starts
    ang_green   = START - SWEEP * 0.60    # 60% → green starts (safe zone)

    # SAFE/RISK label positions — placed outside arc at its endpoints
    safe_lx  = _x(R_track + 18, ang_safe  - 2)
    safe_ly  = _y(R_track + 18, ang_safe  - 2)
    risk_lx  = _x(R_track + 18, ang_end   + 2)
    risk_ly  = _y(R_track + 18, ang_end   + 2)

    def _arc_path(r_o, r_i, a1, a2):
        """Donut arc from angle a1 to a2 (both CCW from east)."""
        diff  = abs(a2 - a1)
        large = 1 if diff > 180 else 0
        return (
            f"M {_x(r_o,a1):.1f} {_y(r_o,a1):.1f} "
            f"A {r_o} {r_o} 0 {large} 0 {_x(r_o,a2):.1f} {_y(r_o,a2):.1f} "
            f"L {_x(r_i,a2):.1f} {_y(r_i,a2):.1f} "
            f"A {r_i} {r_i} 0 {large} 1 {_x(r_i,a1):.1f} {_y(r_i,a1):.1f} Z"
        )

    # ── Tick marks (major every 50%, minor every 10%) ───────────────
    ticks = []
    for i in range(11):
        ang  = START - i / 10 * SWEEP
        is_major = (i % 5 == 0)
        r1   = R_track + 1
        r2   = R_track + (8 if is_major else 4)
        sw   = "1.8" if is_major else "1"
        col  = "rgba(255,255,255,0.25)" if is_major else "rgba(255,255,255,0.12)"
        ticks.append(
            f'<line x1="{_x(r1,ang):.1f}" y1="{_y(r1,ang):.1f}" ' +
            f'x2="{_x(r2,ang):.1f}" y2="{_y(r2,ang):.1f}" ' +
            f'stroke="{col}" stroke-width="{sw}" stroke-linecap="round"/>' 
        )
    tick_svg = "\n  ".join(ticks)

    # ── Needle (thin line + tip circle — Tesla style) ───────────────
    n_ang    = START - frac * SWEEP
    n_tip_x  = _x(R_needle, n_ang)
    n_tip_y  = _y(R_needle, n_ang)
    # Base: short line from hub outward
    n_base_x = _x(R_hub * 1.5, n_ang + 180)
    n_base_y = _y(R_hub * 1.5, n_ang + 180)

    # ── SVG ────────────────────────────────────────────────────────
    svg = f"""<svg viewBox="0 0 {VW} {VH}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{VW}px;display:block;margin:0 auto;">
  <defs>
    <radialGradient id="bgGrad" cx="50%" cy="60%" r="55%">
      <stop offset="0%" stop-color="#1c1c1e"/>
      <stop offset="100%" stop-color="#0a0a0a"/>
    </radialGradient>
    <filter id="glow" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="3" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <filter id="needleGlow" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="2" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <clipPath id="clip"><rect x="0" y="0" width="{VW}" height="{VH}"/></clipPath>
  </defs>

  <!-- Outer disc -->
  <circle cx="{cx}" cy="{cy}" r="{R_track+28}" fill="url(#bgGrad)"/>
  <circle cx="{cx}" cy="{cy}" r="{R_track+28}" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="0.5"/>

  <!-- Track background (full sweep, dark) -->
  <path d="{_arc_path(R_track, R_fill, ang_end, ang_safe)}" fill="#1c1c1e"/>

  <!-- RED zone — right 30% (danger) -->
  <path d="{_arc_path(R_track, R_fill, ang_end, ang_amber)}" fill="rgba(255,69,58,0.85)"/>

  <!-- AMBER zone — middle 30% -->
  <path d="{_arc_path(R_track, R_fill, ang_amber, ang_green)}" fill="rgba(255,159,10,0.85)"/>

  <!-- GREEN zone — left 40% (safe) -->
  <path d="{_arc_path(R_track, R_fill, ang_green, ang_safe)}" fill="rgba(48,209,88,0.85)"/>

  <!-- Zone separator lines -->
  <line x1="{_x(R_fill,ang_amber):.1f}" y1="{_y(R_fill,ang_amber):.1f}" x2="{_x(R_track,ang_amber):.1f}" y2="{_y(R_track,ang_amber):.1f}" stroke="#0a0a0a" stroke-width="2"/>
  <line x1="{_x(R_fill,ang_green):.1f}" y1="{_y(R_fill,ang_green):.1f}" x2="{_x(R_track,ang_green):.1f}" y2="{_y(R_track,ang_green):.1f}" stroke="#0a0a0a" stroke-width="2"/>

  <!-- Tick marks (outside arc) -->
  {tick_svg}

  <!-- SAFE label — at left end of arc (below arc, outside) -->
  <text x="{safe_lx:.1f}" y="{safe_ly:.1f}"
        font-family="system-ui,sans-serif" font-size="9" font-weight="700"
        fill="#30D158" text-anchor="middle" dominant-baseline="middle">SAFE</text>

  <!-- RISK label — at right end of arc -->
  <text x="{risk_lx:.1f}" y="{risk_ly:.1f}"
        font-family="system-ui,sans-serif" font-size="9" font-weight="700"
        fill="#FF453A" text-anchor="middle" dominant-baseline="middle">RISK</text>

  <!-- Needle shadow -->
  <line x1="{n_base_x:.1f}" y1="{n_base_y:.1f}" x2="{n_tip_x:.1f}" y2="{n_tip_y:.1f}"
        stroke="rgba(0,0,0,0.4)" stroke-width="3" stroke-linecap="round"
        transform="translate(1.5,1.5)"/>

  <!-- Needle -->
  <line x1="{n_base_x:.1f}" y1="{n_base_y:.1f}" x2="{n_tip_x:.1f}" y2="{n_tip_y:.1f}"
        stroke="{clr}" stroke-width="2.5" stroke-linecap="round"
        filter="url(#needleGlow)"/>

  <!-- Needle tip dot -->
  <circle cx="{n_tip_x:.1f}" cy="{n_tip_y:.1f}" r="3.5" fill="{clr}" filter="url(#needleGlow)"/>

  <!-- Hub circle -->
  <circle cx="{cx}" cy="{cy}" r="{R_hub+3}" fill="#0a0a0a" stroke="rgba(255,255,255,0.12)" stroke-width="0.5"/>
  <circle cx="{cx}" cy="{cy}" r="{R_hub}" fill="{clr}" filter="url(#glow)"/>

  <!-- UKC VALUE — displayed ABOVE the arc centre, large and clear -->
  <text x="{cx}" y="{cy - R_track - 10}"
        font-family="ui-monospace,monospace" font-size="36" font-weight="700"
        fill="{clr}" text-anchor="middle" dominant-baseline="middle"
        filter="url(#glow)" letter-spacing="-1">{ukc:.2f}</text>
  <text x="{cx}" y="{cy - R_track + 16}"
        font-family="system-ui,sans-serif" font-size="10" font-weight="500"
        fill="rgba(255,255,255,0.45)" text-anchor="middle" dominant-baseline="middle"
        letter-spacing="0.5">METRES UKC</text>

  <!-- STATUS — displayed BELOW hub, inside the arc well -->
  <rect x="{cx-36}" y="{cy+14}" width="72" height="20" rx="10"
        fill="{bg}" stroke="{clr}" stroke-width="0.75"/>
  <text x="{cx}" y="{cy+24}"
        font-family="system-ui,sans-serif" font-size="8.5" font-weight="800"
        fill="{clr}" text-anchor="middle" dominant-baseline="middle"
        letter-spacing="0.8">{status.replace(" ", " ")}</text>

  <!-- "UKC METER" footer — well below everything -->
  <text x="{cx}" y="{VH - 6}"
        font-family="ui-monospace,monospace" font-size="7" font-weight="500"
        fill="rgba(255,255,255,0.18)" text-anchor="middle" letter-spacing="3">
    UKC METER
  </text>
</svg>"""

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{
  background:#000;
  font-family:-apple-system,BlinkMacSystemFont,'Inter',system-ui,sans-serif;
  padding:10px;
  -webkit-font-smoothing:antialiased;
}}
.card{{
  background:#141414;
  border:0.5px solid {bc};
  border-radius:18px;
  padding:14px 16px 12px;
  overflow:hidden;
}}
.lbl{{
  font-size:10px;font-weight:600;letter-spacing:.12em;text-transform:uppercase;
  color:rgba(255,255,255,0.45);font-family:ui-monospace,monospace;
  margin-bottom:8px;
}}
.foot{{
  display:flex;justify-content:space-between;align-items:center;
  margin-top:10px;padding-top:10px;
  border-top:0.5px solid rgba(255,255,255,0.08);
}}
.req{{font-size:11px;color:rgba(255,255,255,0.45);}}
.req strong{{color:rgba(255,255,255,0.85);font-family:ui-monospace,monospace;}}
.status-pill{{
  padding:4px 14px;border-radius:100px;font-size:10px;font-weight:800;
  letter-spacing:.07em;background:{bg};color:{clr};border:0.5px solid {bc};
}}
</style></head><body>
<div class="card">
  <div class="lbl">⚓ Under Keel Clearance (UKC)</div>
  {svg}
  <div class="foot">
    <span class="req">Min required: <strong>{required:.2f} m</strong></span>
    <span class="status-pill">{icon} {status}</span>
  </div>
</div>
</body></html>"""

    _comp.html(html, height=340, scrolling=False)


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

def summary_df(rows: list[tuple], h: int = 440) -> None:
    st.dataframe(pd.DataFrame(rows, columns=["Parameter","Value"]),
                 use_container_width=True, hide_index=True, height=h)


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
      <div class="sidebar-sub">Nigerian Offshore Crude Oil · Loading &amp; Safety</div>
    </div>''', unsafe_allow_html=True)

    db = get_db()
    if not db:
        st.error("No vessels. Add one via the ➕ Add Vessel tab.")
        st.stop()

    selected_name = st.selectbox("Select Vessel", sorted(db.keys()))
    vessel        = db[selected_name]

    # Locked seawater density
    st.markdown("---")
    locked_display("Seawater Density — Nigerian Waters",
                   f"{SEAWATER_DENSITY_NG} t/m\u00b3")
    st.markdown(
        "<div style='font-size:0.68rem;color:var(--muted);font-family:var(--mono);"
        "margin-top:2px;margin-bottom:6px'>"
        "Bonny River estuary &#183; tropical brackish 25\u201326 ppt &#183; 28\u00b0C &#183; not editable"
        "</div>", unsafe_allow_html=True)

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

    # Breakwater depth
    st.markdown("---")
    st.markdown("<div class='sidebar-section'>Breakwater Depth at Loading Point</div>",
                unsafe_allow_html=True)
    depth_choice = st.selectbox("Loading location preset", list(DEPTH_PRESETS.keys()),
                                 key="depth_preset")
    preset_depth = DEPTH_PRESETS[depth_choice]
    if preset_depth is not None:
        depth_default = preset_depth
        st.markdown(f"<span class='badge badge-blue'>Preset: {preset_depth:.2f} m \u2014 {depth_choice}</span>",
                    unsafe_allow_html=True)
    else:
        depth_default = float(vessel.get("breakwater_lat", 3.45) + 2.0)
    water_depth = st.number_input(
        "Breakwater Depth for Shallow Point (m)", 1.0, 30.0, float(depth_default), 0.05,
        help="Depth at LAT of the breakwater/river bar. Used to compute UKC and max permissible draft.")

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
      <div class="app-sub">Nigerian Offshore Crude Oil · Loading &amp; Safety Calculator</div>
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
    <span class="badge badge-lock">\u03c1 {SEAWATER_DENSITY_NG} t/m\u00b3 &#128274;</span>
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
        f"Seawater density locked at <strong>{SEAWATER_DENSITY_NG} t/m\u00b3</strong> (Nigerian waters). "
        "<strong>Both loading limits enforced simultaneously</strong>: "
        "volume ≤ 98% tank capacity AND cargo mass ≤ available Tropical DWT."
    )

    col_inp, col_res = st.columns([1, 1.2], gap="large")

    with col_inp:
        limit_panel(lims, api)
        st.markdown("<br>", unsafe_allow_html=True)
        vol_unit = st.radio("Input unit", ["US Barrels", "Cubic Metres (m\u00b3)"], horizontal=True,
                             key="vol_unit_t1")
        # Input ceiling = binding limit (never allow entry beyond it)
        max_bbl = round(lims["max_cargo_bbl"] * 1.001)  # tiny buffer for slider headroom
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
            f'<div style="font-size:0.78rem;color:var(--muted);font-family:var(--mono);margin-top:0.4rem">'
            f'\u2261 {cargo_m3:,.1f} m\u00b3 &nbsp;/&nbsp; {cargo_bbl:,} US Bbls</div>',
            unsafe_allow_html=True)

    with col_res:
        res = volume_to_draft(vessel, cargo_m3, api, bunker_mt, fw_mt, constant_mt)
        ukc = ukc_assessment(res["draft_m"], water_depth)

        dc = "#ef4444" if res["over_tld"] else "#0ea5e9"
        ol = " \u26a0 OVER TROPICAL LOAD LINE DRAFT" if res["over_tld"] else ""

        # Clamp/limit warnings
        if res["exceeds_tank"]:
            warn(f"Requested volume exceeds 98% tank capacity "
                 f"({lims['vol_cap_bbl']:,.0f} Bbls / {lims['vol_cap_m3']:,.1f} m\u00b3). "
                 f"Cargo has been clamped to the binding limit: "
                 f"<strong>{lims['max_cargo_bbl']:,.0f} Bbls</strong>.")
        if res["exceeds_dwt"]:
            warn(f"Cargo mass at requested volume exceeds available Tropical DWT "
                 f"({lims['avail_dwt_mt']:,.0f} MT). "
                 f"Cargo has been clamped to the binding limit: "
                 f"<strong>{lims['max_cargo_mt']:,.0f} MT</strong>.")

        st.markdown(f"""
        <div class="result-panel">
          <div class="metric-label">Predicted Loaded Draft</div>
          <div class="result-primary" style="color:{dc}">{res['draft_m']:.3f}<span style="font-size:1.4rem;margin-left:4px">m</span>{ol}</div>
          <div class="result-secondary">TLD limit: {res['tld_m']} m &nbsp;·&nbsp; UKC headroom: {round(water_depth - res['draft_m'],2):.2f} m</div>
          <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-top:12px;padding-top:10px;border-top:1px solid var(--border)">
            <div>
              <div style="font-size:0.65rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.08em;font-weight:600">Volume</div>
              <div style="font-size:1.1rem;font-weight:700;font-family:var(--mono);color:var(--text)">{res['volume_loaded_bbl']:,}</div>
              <div style="font-size:0.7rem;color:var(--text-dim)">US Bbls</div>
            </div>
            <div>
              <div style="font-size:0.65rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.08em;font-weight:600">Volume</div>
              <div style="font-size:1.1rem;font-weight:700;font-family:var(--mono);color:var(--text)">{res['volume_loaded_m3']:,.1f}</div>
              <div style="font-size:0.7rem;color:var(--text-dim)">m³</div>
            </div>
            <div>
              <div style="font-size:0.65rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.08em;font-weight:600">Cargo Mass</div>
              <div style="font-size:1.1rem;font-weight:700;font-family:var(--mono);color:var(--text)">{res['cargo_mass_mt']:,.0f}</div>
              <div style="font-size:0.7rem;color:var(--text-dim)">MT</div>
            </div>
          </div>
        </div>""", unsafe_allow_html=True)

        score_bar(res["tank_util_pct"], "Tank Utilisation (vs 98% capacity)", mode="tank")
        score_bar(res["dwt_util_pct"],  "Tropical DWT Utilisation", mode="dwt")
        ukc_badge(ukc["ukc_status"], ukc["ukc_m"], ukc["ukc_required_m"], water_depth, res["draft_m"])

        st.markdown("<hr class='sec-div'>", unsafe_allow_html=True)
        st.markdown("<h3>Loading Calculation Summary</h3>", unsafe_allow_html=True)
        # ── PNG download ─────────────────────────────────────────────────
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
            ("Seawater Density",       f"{SEAWATER_DENSITY_NG} t/m³  🔒 Nigerian waters"),
            ("Predicted Draft",        f"{res['draft_m']:.3f} m"),
            ("Tropical Load Line Draft (TLD)", f"{res['tld_m']} m"),
            ("Breakwater Depth",       f"{water_depth:.2f} m"),
            ("UKC",                    f"{ukc['ukc_m']:.2f} m  [{ukc['ukc_status']}]"),
            ("Limit 1 — 98% Tank",     f"{lims['vol_cap_bbl']:,.0f} Bbls  /  {lims['vol_cap_m3']:,.1f} m\u00b3"),
            ("Limit 2 — Tropical DWT", f"{lims['dwt_cap_bbl']:,.0f} Bbls  /  {lims['dwt_cap_mt']:,.0f} MT"),
            ("Binding Limit",          lims['binding']),
            ("Tank Utilisation",       f"{res['tank_util_pct']}%  of 98% capacity"),
            ("Tropical DWT Util.",     f"{res['dwt_util_pct']}%"),
        ]
        summary_df(_t1_rows)
        _t1_png = summary_png_bytes(_t1_rows, "Loading Calculation Summary — Volume \u2192 Draft")
        st.download_button(
            "\U0001f4f7 Download Summary as PNG",
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
        f"Seawater density locked at <strong>{SEAWATER_DENSITY_NG} t/m\u00b3</strong>."
    )

    c_d1, c_d2 = st.columns([1, 1.2], gap="large")
    with c_d1:
        limit_panel(lims, api)
        st.markdown("<br>", unsafe_allow_html=True)
        draft_inp = st.number_input(
            "Target / Maximum Draft (m)", min_value=1.0,
            max_value=float(vessel["draft_full"]),
            value=round(min(vessel["draft_full"] * 0.90, water_depth * 0.90), 3),
            step=0.01, format="%.3f",
            help="Tide-adjusted permissible draft. Cannot exceed the vessel\u2019s Tropical Load Line Draft.",
        )
        with st.expander("&#127754; Tidal Draft Helper"):
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

    with c_d2:
        res2 = draft_to_volume(vessel, draft_inp, api, bunker_mt, fw_mt, constant_mt)
        ukc2 = ukc_assessment(draft_inp, water_depth)

        if res2["volume_clamped"]:
            warn(f"Volume at this draft exceeds the binding limit "
                 f"(<strong>{lims['binding']}</strong>). "
                 f"Cargo has been reduced to <strong>{lims['max_cargo_bbl']:,.0f} Bbls</strong>.")

        st.markdown(f"""
        <div class="result-panel">
          <div class="metric-label">Cargo Volume at {draft_inp:.3f} m draft</div>
          <div class="result-primary">{res2['volume_bbl']:,}<span style="font-size:1.4rem;margin-left:6px">US Bbls</span></div>
          <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-top:12px;padding-top:10px;border-top:1px solid var(--border)">
            <div>
              <div style="font-size:0.65rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.08em;font-weight:600">Volume</div>
              <div style="font-size:1.1rem;font-weight:700;font-family:var(--mono);color:var(--text)">{res2['volume_m3']:,.1f}</div>
              <div style="font-size:0.7rem;color:var(--text-dim)">m³</div>
            </div>
            <div>
              <div style="font-size:0.65rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.08em;font-weight:600">Cargo Mass</div>
              <div style="font-size:1.1rem;font-weight:700;font-family:var(--mono);color:var(--text)">{res2['cargo_mass_mt']:,.0f}</div>
              <div style="font-size:0.7rem;color:var(--text-dim)">MT</div>
            </div>
            <div>
              <div style="font-size:0.65rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.08em;font-weight:600">SG @{api:.1f}°</div>
              <div style="font-size:1.1rem;font-weight:700;font-family:var(--mono);color:var(--text)">{res2['sg']:.4f}</div>
              <div style="font-size:0.7rem;color:var(--text-dim)">t/m³</div>
            </div>
          </div>
        </div>""", unsafe_allow_html=True)

        score_bar(res2["tank_util_pct"], "Tank Utilisation (vs 98% capacity)", mode="tank")
        score_bar(res2["dwt_util_pct"],  "Tropical DWT Utilisation", mode="dwt")
        ukc_badge(ukc2["ukc_status"], ukc2["ukc_m"], ukc2["ukc_required_m"], water_depth, draft_inp)

        st.markdown("<hr class='sec-div'>", unsafe_allow_html=True)
        st.markdown("<h3>Loading Calculation Summary</h3>", unsafe_allow_html=True)
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
            ("Seawater Density",       f"{SEAWATER_DENSITY_NG} t/m³  🔒 Nigerian waters"),
            ("Tropical Load Line Draft (TLD)", f"{res2['tld_m']} m"),
            ("Breakwater Depth",       f"{water_depth:.2f} m"),
            ("UKC",                    f"{ukc2['ukc_m']:.2f} m  [{ukc2['ukc_status']}]"),
            ("Tank 98% Capacity",      f"{res2['tank_98_bbl']:,} Bbls  /  {res2['tank_98_m3']:,.1f} m\u00b3"),
            ("Limit 1 — 98% Tank",     f"{lims['vol_cap_bbl']:,.0f} Bbls  /  {lims['vol_cap_m3']:,.1f} m\u00b3"),
            ("Limit 2 — Tropical DWT", f"{lims['dwt_cap_bbl']:,.0f} Bbls  /  {lims['dwt_cap_mt']:,.0f} MT"),
            ("Binding Limit",          lims['binding']),
            ("Tank Utilisation",       f"{res2['tank_util_pct']}%  of 98% capacity"),
            ("Tropical DWT Util.",     f"{res2['dwt_util_pct']}%"),
        ]
        summary_df(_t2_rows)
        _t2_png = summary_png_bytes(_t2_rows, "Loading Calculation Summary — Draft \u2192 Volume")
        st.download_button(
            "\U0001f4f7 Download Summary as PNG",
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
         f"\u03c1_sw {SEAWATER_DENSITY_NG} t/m\u00b3 | Breakwater {water_depth:.2f} m")

    comp_rows = []
    for nm, v in sorted(db_now.items()):
        if class_filter and v["class"] not in class_filter:
            continue
        try:
            lv  = compute_limits(v, bunker_mt, fw_mt, constant_mt, api)
            r   = volume_to_draft(v, lv["max_cargo_m3"], api, bunker_mt, fw_mt, constant_mt)
            ukc_c = ukc_assessment(r["draft_m"], water_depth)
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
            new_note = st.text_area("Notes", placeholder="Operating area, dredge depth, role\u2026", height=80)

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
    st.caption(f"{n} vessel(s) in fleet  \u00b7  \u03c1_sw = {SEAWATER_DENSITY_NG} t/m\u00b3 (locked)")


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
