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
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');
:root {
    --bg:#0b0f1a; --surface:#111827; --surface2:#1a2236; --border:#1e3a5f;
    --accent:#0ea5e9; --accent2:#f59e0b; --accent3:#10b981;
    --danger:#ef4444; --text:#e2e8f0; --muted:#64748b;
    --mono:'IBM Plex Mono',monospace; --sans:'IBM Plex Sans',sans-serif;
}
html,body,[class*="css"]{font-family:var(--sans);background:var(--bg);color:var(--text);}
section[data-testid="stSidebar"]{background:var(--surface)!important;border-right:1px solid var(--border);}
section[data-testid="stSidebar"] *{color:var(--text)!important;}
.main .block-container{padding:1.5rem 2rem 3rem;}
h1,h2,h3{font-family:var(--mono);font-weight:600;letter-spacing:-0.02em;}
h1{font-size:1.8rem;color:var(--accent);border-bottom:1px solid var(--border);padding-bottom:0.5rem;}
h2{font-size:1.2rem;color:var(--accent);margin-top:1.5rem;}
h3{font-size:1rem;color:var(--accent2);}
input[type="number"],input[type="text"],select,textarea,
div[data-baseweb="select"]>div,div[data-baseweb="input"]>div{
    background:var(--surface2)!important;border:1px solid var(--border)!important;
    border-radius:4px!important;color:var(--text)!important;font-family:var(--mono)!important;}
.metric-card{background:var(--surface2);border:1px solid var(--border);border-radius:6px;
    padding:1rem 1.25rem;margin:0.4rem 0;}
.metric-label{font-size:0.72rem;color:var(--muted);text-transform:uppercase;
    letter-spacing:0.08em;font-family:var(--mono);margin-bottom:0.2rem;}
.metric-value{font-size:1.6rem;font-weight:600;font-family:var(--mono);color:var(--text);line-height:1.1;}
.metric-unit{font-size:0.8rem;color:var(--muted);font-family:var(--mono);margin-left:4px;}
.result-panel{background:var(--surface2);border:1px solid var(--border);border-radius:8px;
    padding:1.5rem;margin:1rem 0;}
.result-primary{font-size:2.4rem;font-weight:600;font-family:var(--mono);color:var(--accent);line-height:1.1;}
.result-secondary{font-size:1.1rem;font-family:var(--mono);color:var(--accent2);margin-top:0.3rem;}
.score-bar-bg{background:var(--border);border-radius:4px;height:12px;margin:8px 0;overflow:hidden;}
.score-bar-fill{height:12px;border-radius:4px;}
.badge{display:inline-block;padding:2px 10px;border-radius:3px;font-size:0.72rem;
    font-family:var(--mono);font-weight:600;letter-spacing:0.06em;text-transform:uppercase;}
.badge-ok{background:#064e3b;color:#6ee7b7;border:1px solid #065f46;}
.badge-warn{background:#78350f;color:#fde68a;border:1px solid #92400e;}
.badge-risk{background:#7f1d1d;color:#fca5a5;border:1px solid #991b1b;}
.badge-blue{background:#0c4a6e;color:#7dd3fc;border:1px solid #0369a1;}
.badge-lock{background:#1e1b4b;color:#a5b4fc;border:1px solid #4338ca;}
.sec-div{border:none;border-top:1px solid var(--border);margin:1.5rem 0;}
.info-box{background:#0c1a2e;border:1px solid #1e3a5f;border-left:3px solid var(--accent);
    border-radius:4px;padding:0.75rem 1rem;font-size:0.85rem;color:var(--muted);
    margin:0.5rem 0;font-family:var(--sans);line-height:1.5;}
.warn-box{background:#1c1004;border:1px solid #92400e;border-left:3px solid #f59e0b;
    border-radius:4px;padding:0.75rem 1rem;font-size:0.85rem;color:#fde68a;
    margin:0.5rem 0;font-family:var(--sans);line-height:1.5;}
.danger-box{background:#1c0404;border:1px solid #991b1b;border-left:3px solid #ef4444;
    border-radius:4px;padding:0.75rem 1rem;font-size:0.85rem;color:#fca5a5;
    margin:0.5rem 0;font-family:var(--sans);line-height:1.5;}
.limit-box{background:#0f1f10;border:1px solid #166534;border-left:3px solid #22c55e;
    border-radius:4px;padding:0.75rem 1rem;font-size:0.82rem;color:#86efac;
    margin:0.5rem 0;font-family:var(--mono);line-height:1.6;}
.locked-display{background:var(--surface2);border:1px solid #4338ca;border-radius:6px;
    padding:0.6rem 1rem;margin:0.4rem 0;}
.locked-label{font-size:0.68rem;color:#a5b4fc;text-transform:uppercase;letter-spacing:0.1em;
    font-family:var(--mono);margin-bottom:0.15rem;}
.locked-value{font-size:1.15rem;font-weight:600;font-family:var(--mono);color:#c7d2fe;}
button[data-baseweb="tab"]{font-family:var(--mono)!important;font-size:0.85rem!important;color:var(--muted)!important;}
button[data-baseweb="tab"][aria-selected="true"]{color:var(--accent)!important;border-bottom-color:var(--accent)!important;}
details{border:1px solid var(--border)!important;border-radius:6px!important;}
details>summary{color:var(--accent2)!important;font-family:var(--mono)!important;}
.stButton>button{background:var(--accent)!important;color:#0b0f1a!important;
    font-family:var(--mono)!important;font-weight:600!important;border:none!important;
    border-radius:4px!important;letter-spacing:0.04em;}
.stButton>button:hover{opacity:0.9!important;}
button[aria-label*="decrement"],button[aria-label*="increment"]{color:var(--muted)!important;}
label{color:var(--muted)!important;font-size:0.8rem!important;font-family:var(--mono)!important;}
p{color:var(--text);}
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
    {"name":"Fatima Zarah","class":"MR",
     "dwt":51460.30,"grt":30087,"tank_m3_98":52111.01,
     "keel":48.45,"loa":183.0,"beam":32.23,"displacement":62385.20,
     "constant":270,"bunker_fw":1500,"draft_full":13.35,"block_coeff":0.7726,
     "breakwater_lat":3.45,"api_ref":28.9,
     "note":"IMO 9636694 (ex-Evo/Kiribora); Oil/Chemical, IMO Type 3, double hull, "
            "COW+IGS fitted. Q88 V6 30-Mar-2026. Constant/bunker_fw/breakwater_lat "
            "are fleet-default assumptions, NOT from Q88 \u2014 verify. Recent cargoes "
            "AGO/Jet A1 (products, Lom\u00e9/Cotonou) \u2014 confirm crude-service fit."},
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
     "breakwater_lat":3.45,"api_ref":28.9,"note":"Multi-field shuttle; avg API 23\u00b0"},
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
    "Westmore post-dredge (3.45 m)":             3.45,
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

def volume_to_draft(v: dict, volume_m3: float, api: float,
                    bunker_mt: float, fw_mt: float, constant_mt: float) -> dict:
    """
    Predict loaded draft from cargo volume.
    Clamps volume to the binding limit (whichever of 98% tank or Tropical DWT is smaller).
    Returns warnings if the requested volume exceeds either limit.
    """
    sg         = api_to_sg(api)
    limits     = compute_limits(v, bunker_mt, fw_mt, constant_mt, api)
    tank_98    = v["tank_m3_98"]

    # Flags before clamping
    exceeds_tank = volume_m3 > tank_98
    cargo_mass_unclamped = volume_m3 * sg
    exceeds_dwt  = cargo_mass_unclamped > limits["avail_dwt_mt"]

    # Clamp to binding limit
    volume_m3_clamped = min(volume_m3, limits["max_cargo_m3"])
    clamped = volume_m3_clamped < volume_m3

    cargo_mass  = volume_m3_clamped * sg
    lightship   = lightship_mass(v)
    deductions  = bunker_mt + fw_mt + constant_mt
    total_disp  = lightship + cargo_mass + deductions

    draft_m     = total_disp / (v["block_coeff"] * v["loa"] * v["beam"] * SEAWATER_DENSITY_NG)
    tld         = v["draft_full"]   # Tropical Load Line Draft

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
    Clamps result to binding limit (98% tank or Tropical DWT).
    """
    sg         = api_to_sg(api)
    limits     = compute_limits(v, bunker_mt, fw_mt, constant_mt, api)
    lightship  = lightship_mass(v)
    deductions = bunker_mt + fw_mt + constant_mt
    tank_98    = v["tank_m3_98"]
    tld        = v["draft_full"]

    # Displacement at this draft
    total_disp  = v["block_coeff"] * v["loa"] * v["beam"] * draft_m * SEAWATER_DENSITY_NG
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
    <div style="margin:0.6rem 0">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
        <span style="font-size:0.78rem;font-family:var(--mono);color:var(--muted)">{label}</span>
        <div>
          <span style="font-size:1.1rem;font-weight:600;font-family:var(--mono);color:{color}">{pct:.1f}%</span>
          &nbsp;<span class="badge {sb}">{sl}</span>
        </div>
      </div>
      <div class="score-bar-bg">
        <div class="score-bar-fill" style="width:{min(pct,100):.1f}%;background:{color}"></div>
      </div>
    </div>""", unsafe_allow_html=True)

def ukc_badge(status: str, ukc: float, required: float) -> None:
    cls  = {"ADEQUATE":"badge-ok","MARGINAL":"badge-warn"}.get(status,"badge-risk")
    icon = {"ADEQUATE":"✓","MARGINAL":"⚠"}.get(status,"✕")
    tc   = {"ADEQUATE":"#6ee7b7","MARGINAL":"#fde68a"}.get(status,"#fca5a5")
    bc   = {"ADEQUATE":"#065f46","MARGINAL":"#92400e"}.get(status,"#991b1b")
    st.markdown(f"""
    <div class="metric-card" style="border-color:{bc}">
      <div class="metric-label">Under Keel Clearance (UKC)</div>
      <div style="display:flex;align-items:center;gap:10px;margin-top:4px">
        <span style="font-size:1.5rem;font-family:var(--mono);font-weight:600;color:{tc}">{ukc:.2f} m</span>
        <span class="badge {cls}">{icon} {status}</span>
      </div>
      <div style="font-size:0.78rem;color:var(--muted);font-family:var(--mono);margin-top:4px">
        Required minimum: {required:.2f} m
      </div>
    </div>""", unsafe_allow_html=True)

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


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        "<h1 style='font-size:1.1rem;margin-bottom:0.2rem'>&#9875; STOWAGE CALCULATOR</h1>",
        unsafe_allow_html=True)
    st.markdown(
        "<p style='font-size:0.72rem;color:var(--muted);font-family:var(--mono);margin-top:0'>"
        "Nigerian Offshore Crude Oil Loading Tool</p>", unsafe_allow_html=True)
    st.markdown("<hr style='border-color:var(--border);margin:0.5rem 0 1rem'>",
                unsafe_allow_html=True)

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
    st.markdown("<span style='font-size:0.75rem;color:var(--muted);font-family:var(--mono)'>CARGO API GRAVITY</span>",
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
    st.markdown("<span style='font-size:0.75rem;color:var(--muted);font-family:var(--mono)'>BREAKWATER DEPTH AT LOADING POINT</span>",
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
    st.markdown("<span style='font-size:0.75rem;color:var(--muted);font-family:var(--mono)'>DEDUCTIONS (non-cargo weight)</span>",
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

    # Fresh water — MT or Litres
    fw_unit = st.radio("Fresh water unit", ["MT", "Litres"], horizontal=True, key="fw_unit_radio")
    if fw_unit == "MT":
        fw_mt = st.number_input("Fresh water on board (MT)", 0.0, 2000.0,
                                 round(default_fw_mt, 0), 10.0,
                                 help="Potable + distilled water. Density = 1.000 t/m\u00b3.")
    else:
        def_fw_L = mt_to_litres(default_fw_mt, FRESHWATER_DENSITY)
        fw_L = st.number_input("Fresh water on board (Litres)", 0.0, 2_000_000.0,
                                round(def_fw_L, 0), 500.0,
                                help="Fresh water: 1.000 t/m\u00b3 (1 litre = 1 kg exactly).")
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
# VESSEL HEADER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(f"<h1>&#9875; Vessel Stowage Calculator \u2014 {selected_name}</h1>",
            unsafe_allow_html=True)
tld_val = vessel['draft_full']
st.markdown(f"""
<div style="display:flex;gap:8px;margin-bottom:1rem;flex-wrap:wrap">
  <span class="badge badge-ok">Class: {vessel['class']}</span>
  <span class="badge badge-ok">Tropical DWT: {vessel['dwt']:,.0f} MT</span>
  <span class="badge badge-ok">Tank 98%: {m3_to_bbl(vessel['tank_m3_98']):,.0f} bbl</span>
  <span class="badge badge-ok">LOA: {vessel['loa']} m</span>
  <span class="badge badge-ok">Beam: {vessel['beam']} m</span>
  <span class="badge badge-warn">TLD: {tld_val} m</span>
  <span class="badge badge-warn">Breakwater LAT: {vessel['breakwater_lat']} m</span>
  <span class="badge badge-lock">\u03c1_sw = {SEAWATER_DENSITY_NG} t/m\u00b3 &#128274;</span>
</div>""", unsafe_allow_html=True)

if vessel.get("note"):
    info(f"&#128204; {vessel['note']}")

# Pre-compute limits for use in both tabs
lims = compute_limits(vessel, bunker_mt, fw_mt, constant_mt, api)

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "&#128230;  Volume \u2192 Draft",
    "&#128208;  Draft \u2192 Volume",
    "&#128203;  Fleet Browser",
    "&#10133;  Add Vessel",
    "&#9881;&#65039;  Master Data",
])


# ════════════════════════════════════════════════════════════════════════════
# TAB 1  —  Volume → Draft
# ════════════════════════════════════════════════════════════════════════════
with tab1:
    section("Enter Cargo Volume \u2192 Predicted Draft")
    info(
        "Enter cargo quantity. The calculator predicts the loaded draft using the "
        "<strong>block coefficient method</strong> (IACS). "
        f"Seawater density locked at <strong>{SEAWATER_DENSITY_NG} t/m\u00b3</strong> (Nigerian waters). "
        "<strong>Both loading limits are enforced simultaneously</strong>: "
        "volume is capped at the 98% tank capacity, and cargo mass is capped at "
        "the available Tropical DWT after deductions. The input is automatically "
        "reduced to the binding limit if exceeded."
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
          <div class="result-primary" style="color:{dc}">{res['draft_m']:.3f} m{ol}</div>
          <div class="result-secondary">Tropical Load Line Draft limit: {res['tld_m']} m</div>
          <div style="font-size:0.78rem;font-family:var(--mono);color:var(--muted);margin-top:6px">
            Cargo loaded: <strong style="color:var(--text)">{res['volume_loaded_bbl']:,} Bbls
            &nbsp;/&nbsp; {res['volume_loaded_m3']:,.1f} m\u00b3
            &nbsp;/&nbsp; {res['cargo_mass_mt']:,.1f} MT</strong>
          </div>
        </div>""", unsafe_allow_html=True)

        score_bar(res["tank_util_pct"], "Tank Utilisation (vs 98% capacity)")
        score_bar(res["dwt_util_pct"],  "Tropical DWT Utilisation")
        ukc_badge(ukc["ukc_status"], ukc["ukc_m"], ukc["ukc_required_m"])

        st.markdown("<hr class='sec-div'>", unsafe_allow_html=True)
        st.markdown("<h3>Loading Calculation Summary</h3>", unsafe_allow_html=True)
        summary_df([
            ("Cargo Volume (loaded)",  f"{res['volume_loaded_m3']:,.1f} m\u00b3  /  {res['volume_loaded_bbl']:,} Bbls"),
            ("Cargo API",              f"{api:.1f}\u00b0  (SG {res['sg']:.4f})"),
            ("Cargo Mass",             f"{res['cargo_mass_mt']:,.1f} MT"),
            ("Lightship Mass",         f"{res['lightship_mt']:,.1f} MT"),
            ("Bunker on board",        f"{bunker_mt:,.1f} MT"),
            ("Fresh water on board",   f"{fw_mt:,.1f} MT"),
            ("Ship\u2019s Constant",   f"{constant_mt:,.0f} MT"),
            ("Total Deductions",       f"{res['deductions_mt']:,.1f} MT"),
            ("Total Displacement",     f"{res['total_displacement_mt']:,.1f} MT"),
            ("Seawater Density",       f"{SEAWATER_DENSITY_NG} t/m\u00b3  &#128274; Nigerian waters"),
            ("Predicted Draft",        f"{res['draft_m']:.3f} m"),
            ("Tropical Load Line Draft (TLD)", f"{res['tld_m']} m"),
            ("Breakwater Depth",       f"{water_depth:.2f} m"),
            ("UKC",                    f"{ukc['ukc_m']:.2f} m  [{ukc['ukc_status']}]"),
            ("Limit 1 — 98% Tank",     f"{lims['vol_cap_bbl']:,.0f} Bbls  /  {lims['vol_cap_m3']:,.1f} m\u00b3"),
            ("Limit 2 — Tropical DWT", f"{lims['dwt_cap_bbl']:,.0f} Bbls  /  {lims['dwt_cap_mt']:,.0f} MT"),
            ("Binding Limit",          lims['binding']),
            ("Tank Utilisation",       f"{res['tank_util_pct']}%  of 98% capacity"),
            ("Tropical DWT Util.",     f"{res['dwt_util_pct']}%"),
        ])


# ════════════════════════════════════════════════════════════════════════════
# TAB 2  —  Draft → Volume
# ════════════════════════════════════════════════════════════════════════════
with tab2:
    section("Enter Target Draft \u2192 Calculated Cargo Volume")
    info(
        "Enter the <strong>maximum permissible draft</strong> (tide-constrained or bar-crossing draft). "
        "The calculator back-calculates achievable cargo volume, then applies both hard limits: "
        "volume is capped at 98% tank capacity and mass is capped at available Tropical DWT. "
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
          <div class="result-primary">{res2['volume_bbl']:,} <span style="font-size:1.2rem">US Bbls</span></div>
          <div class="result-secondary">{res2['volume_m3']:,.1f} m\u00b3 &nbsp;\u00b7&nbsp; {res2['cargo_mass_mt']:,.0f} MT cargo</div>
        </div>""", unsafe_allow_html=True)

        score_bar(res2["tank_util_pct"], "Tank Utilisation (vs 98% capacity)")
        score_bar(res2["dwt_util_pct"],  "Tropical DWT Utilisation")
        ukc_badge(ukc2["ukc_status"], ukc2["ukc_m"], ukc2["ukc_required_m"])

        st.markdown("<hr class='sec-div'>", unsafe_allow_html=True)
        st.markdown("<h3>Loading Calculation Summary</h3>", unsafe_allow_html=True)
        summary_df([
            ("Input Draft",            f"{draft_inp:.3f} m"),
            ("Cargo API",              f"{api:.1f}\u00b0  (SG {res2['sg']:.4f})"),
            ("Cargo Volume",           f"{res2['volume_m3']:,.1f} m\u00b3  /  {res2['volume_bbl']:,} US Bbls"),
            ("Cargo Mass",             f"{res2['cargo_mass_mt']:,.1f} MT"),
            ("Lightship Mass",         f"{res2['lightship_mt']:,.1f} MT"),
            ("Bunker on board",        f"{bunker_mt:,.1f} MT"),
            ("Fresh water on board",   f"{fw_mt:,.1f} MT"),
            ("Ship\u2019s Constant",   f"{constant_mt:,.0f} MT"),
            ("Total Deductions",       f"{res2['deductions_mt']:,.1f} MT"),
            ("Total Displacement",     f"{res2['total_displacement_mt']:,.1f} MT"),
            ("Seawater Density",       f"{SEAWATER_DENSITY_NG} t/m\u00b3  &#128274; Nigerian waters"),
            ("Tropical Load Line Draft (TLD)", f"{res2['tld_m']} m"),
            ("Breakwater Depth",       f"{water_depth:.2f} m"),
            ("UKC",                    f"{ukc2['ukc_m']:.2f} m  [{ukc2['ukc_status']}]"),
            ("Tank 98% Capacity",      f"{res2['tank_98_bbl']:,} Bbls  /  {res2['tank_98_m3']:,.1f} m\u00b3"),
            ("Limit 1 — 98% Tank",     f"{lims['vol_cap_bbl']:,.0f} Bbls  /  {lims['vol_cap_m3']:,.1f} m\u00b3"),
            ("Limit 2 — Tropical DWT", f"{lims['dwt_cap_bbl']:,.0f} Bbls  /  {lims['dwt_cap_mt']:,.0f} MT"),
            ("Binding Limit",          lims['binding']),
            ("Tank Utilisation",       f"{res2['tank_util_pct']}%  of 98% capacity"),
            ("Tropical DWT Util.",     f"{res2['dwt_util_pct']}%"),
        ])


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
