"""
Streamlit Dashboard for Renewal Risk Intelligence.

A BizOps-facing executive intelligence tool featuring:
1. Executive Overview & Portfolio Metrics (ARR at Risk, Tier Distribution, Attention Flags)
2. Interactive Account List (Filterable, Searchable, Signal Drilldowns, AI Explanations)
3. Non-Obvious Portfolio Insights (SDK Deprecation Impact & Trapped Usage Patterns)

Run: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import json
from pathlib import Path

# --- Page Config ---
st.set_page_config(
    page_title="Renewal Risk Intelligence",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- SAFE TYPE CASTING & FORMATTING HELPERS ---
def to_float(val, default=0.0):
    if val is None or pd.isna(val):
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

def to_int(val, default=0):
    if val is None or pd.isna(val):
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default

def fmt_curr(val):
    """Format currency safely escaping $ so Streamlit Markdown does not parse it as KaTeX LaTeX math."""
    return f"\\${to_float(val):,.0f}"

def fmt_curr_plain(val):
    return f"${to_float(val):,.0f}"

def fmt_num(val, decimals=1):
    return f"{to_float(val):.{decimals}f}"

def fmt_pct(val, decimals=1):
    f_val = to_float(val)
    prefix = "+" if f_val > 0 else ""
    return f"{prefix}{f_val:.{decimals}f}%"

# Non-English NPS verbatim human translations map
VERBATIM_TRANSLATIONS = {
    1013: "The product is good, but support in Spanish is non-existent.",
    1014: "The product is good, but the interface is not intuitive for our marketing team.",
    1016: "The product is good, but the interface is not intuitive for our marketing team.",
    1017: "Product features are okay, but the support team's communication efficiency is too low. We have repeatedly asked to change our CSM with no response. Very disappointed.",
    1022: "Product features are okay, but the admin interface lacks a Chinese option. Our team has to rely on machine translation, which drops efficiency.",
}

# --- CUSTOM CSS (PREMIUM BIZOPS DESIGN SYSTEM & ANIMATIONS) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;800&family=Plus+Jakarta+Sans:wght@400;600;700&display=swap');

    html, body, [class*="css"], .stApp { font-family: 'Inter', sans-serif; }
    .stApp { background-color: #0a0b10; }

    /* Ensure Streamlit icons render using Material Symbols instead of text ligatures */
    span[data-testid="stIcon"], 
    [data-testid="stExpander"] summary span:first-child,
    [data-testid="stSidebarCollapseButton"] button {
        font-family: "Material Symbols Outlined", "Material Symbols Rounded", "Material Icons" !important;
    }

    .kpi-card:hover {
        transform: translateY(-4px) !important;
        box-shadow: 0 12px 24px rgba(0,0,0,0.35) !important;
    }

    /* Keyframe Animations */
    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(14px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    @keyframes countPulse {
        0% { transform: scale(0.98); opacity: 0.8; }
        50% { transform: scale(1.02); opacity: 1; }
        100% { transform: scale(1); opacity: 1; }
    }

    .main .block-container {
        padding-top: 1.5rem;
        padding-bottom: 3rem;
        max-width: 1280px;
        animation: fadeInUp 0.35s cubic-bezier(0.16, 1, 0.3, 1);
    }

    /* Metric Cards */
    .metric-card {
        background: rgba(15, 23, 42, 0.75);
        backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 22px 24px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4), 0 8px 10px -6px rgba(0, 0, 0, 0.4);
        transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.25s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.25s ease;
        animation: countPulse 0.4s ease-out;
    }

    .metric-card:hover {
        transform: translateY(-4px);
        border-color: rgba(99, 102, 241, 0.4);
        box-shadow: 0 20px 30px -10px rgba(0, 0, 0, 0.6), 0 0 18px rgba(99, 102, 241, 0.25);
    }

    .metric-eyebrow {
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #94a3b8;
        margin-bottom: 8px;
    }

    .metric-value {
        font-size: 2.2rem;
        font-weight: 800;
        color: #f8fafc;
        line-height: 1.2;
        letter-spacing: -0.02em;
    }

    .metric-subtext {
        font-size: 0.82rem;
        color: #cbd5e1;
        margin-top: 8px;
        font-weight: 500;
    }

    /* Risk Color Language */
    .color-high { color: #f43f5e; }
    .color-medium { color: #f59e0b; }
    .color-low { color: #10b981; }

    /* Rounded Pill Controls */
    .stTextInput input, .stSelectbox div[data-baseweb="select"], .stMultiSelect div[data-baseweb="select"] {
        border-radius: 20px !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        background: rgba(15, 23, 42, 0.6) !important;
    }

    .stButton button {
        border-radius: 20px !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        transition: all 0.2s ease !important;
    }

    /* Custom Badges */
    .badge {
        display: inline-flex;
        align-items: center;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.78rem;
        font-weight: 600;
        margin: 2px 4px 2px 0;
        letter-spacing: 0.02em;
    }

    .badge-high {
        background: rgba(244, 63, 94, 0.15);
        color: #fb7185;
        border: 1px solid rgba(244, 63, 94, 0.3);
    }

    .badge-medium {
        background: rgba(245, 158, 11, 0.15);
        color: #fbbf24;
        border: 1px solid rgba(245, 158, 11, 0.3);
    }

    .badge-low {
        background: rgba(16, 185, 129, 0.15);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }

    .badge-contradiction {
        background: rgba(217, 119, 6, 0.2);
        color: #fcd34d;
        border: 1px solid rgba(245, 158, 11, 0.4);
    }

    .badge-low-conf {
        background: rgba(99, 102, 241, 0.18);
        color: #a5b4fc;
        border: 1px solid rgba(99, 102, 241, 0.35);
    }

    .badge-override {
        background: rgba(225, 29, 72, 0.2);
        color: #fda4af;
        border: 1px solid rgba(244, 63, 94, 0.5);
    }

    /* Container Glass Cards */
    .glass-card {
        background: rgba(15, 23, 42, 0.75);
        backdrop-filter: blur(14px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 26px;
        margin-bottom: 24px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.35);
        transition: border-color 0.25s ease, box-shadow 0.25s ease;
    }

    .glass-card:hover {
        border-color: rgba(255, 255, 255, 0.15);
        box-shadow: 0 15px 30px -5px rgba(0, 0, 0, 0.45);
    }

    .glass-card-header {
        font-size: 1.2rem;
        font-weight: 700;
        color: #f8fafc;
        margin-bottom: 18px;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    /* Attention Item Cards */
    .attention-card {
        background: rgba(30, 41, 59, 0.4);
        border-left: 3px solid #6366f1;
        border-radius: 0 10px 10px 0;
        padding: 12px 16px;
        margin-bottom: 10px;
        transition: transform 0.2s ease, background 0.2s ease;
    }

    .attention-card:hover {
        background: rgba(30, 41, 59, 0.75);
        transform: translateX(3px);
    }

    .attention-card-high { border-left-color: #f43f5e; }
    .attention-card-medium { border-left-color: #f59e0b; }
    .attention-card-low { border-left-color: #10b981; }

    /* Disable and hide Streamlit auto-generated heading anchor links and slug elements */
    a.anchor, .anchor, [data-testid="stMarkdownContainer"] a.anchor, div[data-testid="stExpander"] a.anchor, header a.anchor {
        display: none !important;
        visibility: hidden !important;
        opacity: 0 !important;
        pointer-events: none !important;
        width: 0 !important;
        height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
    }

    /* Expanders styling */
    div[data-testid="stExpander"] {
        background: rgba(15, 23, 42, 0.65) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 12px !important;
        margin-bottom: 12px !important;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
        transition: border-color 0.25s ease, transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.25s ease;
    }

    div[data-testid="stExpander"]:hover {
        border-color: rgba(99, 102, 241, 0.4) !important;
        transform: translateY(-2px);
        box-shadow: 0 12px 24px -6px rgba(0, 0, 0, 0.4);
    }

    /* Target only the actual title text paragraph inside expander summary */
    div[data-testid="stExpander"] details summary [data-testid="stMarkdownContainer"] p {
        font-size: 1.05rem !important;
        font-weight: 600 !important;
        color: #f1f5f9 !important;
        display: inline-block !important;
        margin: 0 !important;
    }

    /* Sidebar Navigation styling */
    section[data-testid="stSidebar"] {
        background-color: #090d16 !important;
        border-right: 1px solid rgba(255, 255, 255, 0.06);
    }

    /* Clean Streamlit elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

PROCESSED_DIR = Path("data/processed")


def recursively_clean_numbers(obj):
    """
    Recursively walk dicts/lists from loaded JSON files and convert string-encoded
    numbers into float or int so string formatting won't crash.
    """
    if isinstance(obj, dict):
        cleaned = {}
        for k, v in obj.items():
            cleaned[k] = recursively_clean_numbers(v)
        return cleaned
    elif isinstance(obj, list):
        return [recursively_clean_numbers(item) for item in obj]
    elif isinstance(obj, str):
        s = obj.strip()
        if s.isdigit():
            return int(s)
        try:
            val = float(s)
            return val
        except ValueError:
            return obj
    return obj


@st.cache_data
def load_data():
    """Load all processed data files with defensive type cleaning."""
    scored = pd.read_csv(PROCESSED_DIR / "scored_accounts.csv")
    scored['contract_end_date'] = pd.to_datetime(scored['contract_end_date'])
    
    explanations = {}
    exp_path = PROCESSED_DIR / "account_explanations.json"
    if exp_path.exists():
        with open(exp_path, 'r', encoding='utf-8') as f:
            raw_exps = json.load(f)
            for exp in raw_exps:
                acct_id = to_int(exp.get('account_id', 0))
                explanations[acct_id] = exp
    
    insights = []
    ins_path = PROCESSED_DIR / "insights.json"
    if ins_path.exists():
        with open(ins_path, 'r', encoding='utf-8') as f:
            raw_insights = json.load(f)
            insights = recursively_clean_numbers(raw_insights)
    
    csm_extractions = {}
    csm_path = PROCESSED_DIR / "csm_extractions.json"
    if csm_path.exists():
        with open(csm_path, 'r', encoding='utf-8') as f:
            raw_csms = json.load(f)
            for ext in raw_csms:
                acct_id = ext.get('er_matched_account_id')
                if acct_id and not pd.isna(acct_id):
                    csm_extractions[to_int(acct_id)] = ext
    
    er_log = pd.read_csv(PROCESSED_DIR / "entity_resolution_log.csv")
    
    return scored, explanations, insights, csm_extractions, er_log


def tier_color(tier):
    """Returns refined palette colors matching design system."""
    colors = {
        'High': '#f43f5e',    # Muted Coral/Rose
        'Medium': '#f59e0b',  # Warm Amber
        'Low': '#10b981',     # Emerald
    }
    return colors.get(tier, '#94a3b8')


def tier_emoji(tier):
    emojis = {'High': '🔴', 'Medium': '🟡', 'Low': '🟢'}
    return emojis.get(tier, '⚪')


def render_score_gauge(score_val, label):
    """Render a modern sleek bar-style gauge for a dimension score."""
    score = to_float(score_val)
    color = '#f43f5e' if score >= 65 else ('#f59e0b' if score >= 40 else '#10b981')
    width_pct = min(100, max(0, score))
    return f"""
    <div style="margin-bottom: 10px;">
        <div style="display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 4px;">
            <span style="color: #cbd5e1; font-weight: 500;">{label}</span>
            <span style="color: {color}; font-weight: 700;">{score:.1f}/100</span>
        </div>
        <div style="background: rgba(255, 255, 255, 0.08); border-radius: 6px; height: 7px; overflow: hidden; position: relative;">
            <div style="background: {color}; width: {width_pct}%; height: 100%; border-radius: 6px; transition: width 0.4s ease;"></div>
        </div>
    </div>
    """


# === LOAD DATA ===
scored, explanations, insights, csm_extractions, er_log = load_data()
renewal = scored[scored['renewing_in_window'] == True].sort_values('risk_score', ascending=False)

# === SIDEBAR ===
st.sidebar.markdown("## 🎯 Renewal Risk Intelligence")
st.sidebar.markdown("<p style='color: #64748b; font-size: 0.85rem; margin-top: -10px;'>BizOps Decision Engine</p>", unsafe_allow_html=True)
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigation",
    ["📊 Dashboard Overview", "📋 Account Risk Roster", "🔍 Non-Obvious Insights"],
    index=0,
)

# Sidebar Filter Controls
if page == "📋 Account Risk Roster":
    st.sidebar.markdown("### 🎛️ Filter Roster")
    tier_filter = st.sidebar.multiselect(
        "Risk Tier",
        options=['High', 'Medium', 'Low'],
        default=['High', 'Medium', 'Low'],
    )
    search = st.sidebar.text_input("🔍 Search Account / ID", "", key="sidebar_search_input")
    sort_by = st.sidebar.selectbox(
        "Sort Order",
        ["Risk Score (High → Low)", "ARR (High → Low)", "Days to Renewal", "Account Name"],
    )


# ==============================================================================
# PAGE 1: DASHBOARD OVERVIEW
# ==============================================================================
if page == "📊 Dashboard Overview":
    st.title("Renewal Risk Overview")
    st.markdown("<p style='color: #94a3b8; font-size: 1.05rem; margin-top: -12px;'>Executive intelligence for accounts renewing within the 90-day window (Apr 15 – Jul 14, 2026)</p>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    high_risk = renewal[renewal['risk_tier'] == 'High']
    medium_risk = renewal[renewal['risk_tier'] == 'Medium']
    low_risk = renewal[renewal['risk_tier'] == 'Low']
    
    # --- Top Metrics Row (Part 2 KPI Cards) ---
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        st.markdown(f"""
        <div class="kpi-card" style="background:linear-gradient(145deg,#14161f,#0a0b10);
          border:1px solid rgba(255,255,255,0.06);border-radius:16px;
          padding:24px;transition:transform .2s ease, box-shadow .2s ease;">
          <div style="font-size:12px;letter-spacing:1px;text-transform:uppercase;
            opacity:.6;margin-bottom:8px;">RENEWING PORTFOLIO</div>
          <div style="font-size:44px;font-weight:800;line-height:1;
            margin-bottom:8px;">{len(renewal)}</div>
          <div style="font-size:13px;opacity:.7;">Total ARR: ${renewal['arr'].sum():,.0f}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with c2:
        st.markdown(f"""
        <div class="kpi-card" style="background:linear-gradient(145deg,#14161f,#0a0b10);
          border:1px solid rgba(244,63,94,0.3);border-radius:16px;
          padding:24px;transition:transform .2s ease, box-shadow .2s ease;">
          <div style="font-size:12px;letter-spacing:1px;text-transform:uppercase;
            color:#f43f5e;margin-bottom:8px;font-weight:700;">HIGH RISK TIER</div>
          <div style="font-size:44px;font-weight:800;line-height:1;color:#f43f5e;
            margin-bottom:8px;">{len(high_risk)}</div>
          <div style="font-size:13px;color:#fda4af;">${high_risk['arr'].sum():,.0f} ARR at risk</div>
        </div>
        """, unsafe_allow_html=True)
        
    with c3:
        st.markdown(f"""
        <div class="kpi-card" style="background:linear-gradient(145deg,#14161f,#0a0b10);
          border:1px solid rgba(245,158,11,0.3);border-radius:16px;
          padding:24px;transition:transform .2s ease, box-shadow .2s ease;">
          <div style="font-size:12px;letter-spacing:1px;text-transform:uppercase;
            color:#f59e0b;margin-bottom:8px;font-weight:700;">MEDIUM RISK TIER</div>
          <div style="font-size:44px;font-weight:800;line-height:1;color:#f59e0b;
            margin-bottom:8px;">{len(medium_risk)}</div>
          <div style="font-size:13px;color:#fde68a;">${medium_risk['arr'].sum():,.0f} ARR at risk</div>
        </div>
        """, unsafe_allow_html=True)
        
    with c4:
        st.markdown(f"""
        <div class="kpi-card" style="background:linear-gradient(145deg,#14161f,#0a0b10);
          border:1px solid rgba(16,185,129,0.3);border-radius:16px;
          padding:24px;transition:transform .2s ease, box-shadow .2s ease;">
          <div style="font-size:12px;letter-spacing:1px;text-transform:uppercase;
            color:#10b981;margin-bottom:8px;font-weight:700;">LOW RISK TIER</div>
          <div style="font-size:44px;font-weight:800;line-height:1;color:#10b981;
            margin-bottom:8px;">{len(low_risk)}</div>
          <div style="font-size:13px;color:#a7f3d0;">${low_risk['arr'].sum():,.0f} ARR stable</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # --- Charts Row ---
    col_a, col_b = st.columns([1, 1])
    
    with col_a:
        st.markdown("<div class='glass-card'><div class='glass-card-header'>💰 ARR at Risk by Tier</div>", unsafe_allow_html=True)
        fig_pie = go.Figure(data=[go.Pie(
            labels=['High Risk', 'Medium Risk', 'Low Risk'],
            values=[to_float(high_risk['arr'].sum()), to_float(medium_risk['arr'].sum()), to_float(low_risk['arr'].sum())],
            marker_colors=['#f43f5e', '#f59e0b', '#10b981'],
            hole=0.45,
            textinfo='label+percent',
            hovertemplate="<b>%{label}</b><br>ARR: $%{value:,.0f}<br>Share: %{percent}<extra></extra>",
            textfont=dict(family="Inter, sans-serif", size=13, color="#f8fafc")
        )])
        fig_pie.update_layout(
            height=320,
            margin=dict(t=10, b=10, l=10, r=10),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5, font=dict(color="#cbd5e1")),
            transition_duration=400
        )
        st.plotly_chart(fig_pie, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
    
    with col_b:
        st.markdown("<div class='glass-card'><div class='glass-card-header'>🔥 Top 10 Priority Accounts by Risk Score</div>", unsafe_allow_html=True)
        top10 = renewal.head(10)
        
        # Build text and custom colors strictly matching tier & critical override
        bar_colors = []
        bar_texts = []
        hover_texts = []
        
        for _, r in top10.iterrows():
            tier = r['risk_tier']
            score = to_float(r['risk_score'])
            override = bool(r.get('critical_override', False))
            
            bar_colors.append(tier_color(tier))
            
            if override:
                bar_texts.append(f"{score:.0f} 🚨")
                hover_texts.append(f"<b>{r['account_name']}</b><br>Score: {score:.1f}/100<br>Tier: {tier}<br>ARR: {fmt_curr_plain(r['arr'])}<br>🚨 Critical Override: {r.get('override_reason','')}")
            else:
                bar_texts.append(f"{score:.0f}")
                hover_texts.append(f"<b>{r['account_name']}</b><br>Score: {score:.1f}/100<br>Tier: {tier}<br>ARR: {fmt_curr_plain(r['arr'])}")
                
        fig_bar = go.Figure(data=[go.Bar(
            y=top10['account_name'],
            x=top10['risk_score'].apply(to_float),
            orientation='h',
            marker=dict(
                color=bar_colors,
                line=dict(color='rgba(255,255,255,0.1)', width=1),
            ),
            text=bar_texts,
            textposition='outside',
            hoverinfo='text',
            hovertext=hover_texts,
            textfont=dict(family="Inter, sans-serif", size=12, color="#f8fafc")
        )])
        fig_bar.update_layout(
            height=300,
            margin=dict(t=10, b=10, l=10, r=40),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color='#f8fafc',
            transition_duration=400,
            xaxis=dict(
                range=[0, 110],
                title=dict(text="Composite Risk Score (0-100)", font=dict(color="#94a3b8", size=12)),
                gridcolor='rgba(255,255,255,0.06)',
                zerolinecolor='rgba(255,255,255,0.1)'
            ),
            yaxis=dict(
                autorange='reversed',
                gridcolor='rgba(255,255,255,0.03)',
                tickfont=dict(family="Inter, sans-serif", size=12, color="#e2e8f0")
            )
        )
        st.plotly_chart(fig_bar, use_container_width=True)
        st.markdown("<p style='font-size: 0.78rem; color: #94a3b8; margin-top: 4px;'>"
                    "🚨 <b>Critical Override Indicator:</b> Flags accounts placed in High Risk tier due to active competitor evaluation, explicit churn threat, or alternative migration in CSM notes regardless of raw composite score.</p>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    
    # --- Attention Flags Row ---
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.markdown("<div class='glass-card-header'>⚠️ Key Signals & Attention Flags</div>", unsafe_allow_html=True)
    
    ax, ay, az = st.columns(3)
    
    with ax:
        st.markdown("#### 🔄 Cross-Signal Contradictions")
        contradictions = renewal[renewal['contradiction_count'] > 0]
        st.markdown(f"<p style='color: #94a3b8; font-size: 0.85rem;'>{len(contradictions)} accounts with conflicting indicators</p>", unsafe_allow_html=True)
        
        for _, r in contradictions.iterrows():
            tier = r['risk_tier']
            tier_cls = f"attention-card-{tier.lower()}"
            flags_text = str(r.get('contradiction_flags', ''))
            st.markdown(f"""
            <div class="attention-card {tier_cls}">
                <div style="font-weight: 700; color: #f8fafc; font-size: 0.95rem;">{r['account_name']}</div>
                <div style="font-size: 0.82rem; color: #fbbf24; margin-top: 4px; line-height: 1.4;">
                    ⚠️ {flags_text}
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    with ay:
        st.markdown("#### 🎯 Low-Confidence Assessments")
        low_conf = renewal[renewal['confidence_level'] == 'Low Confidence']
        st.markdown(f"<p style='color: #94a3b8; font-size: 0.85rem;'>{len(low_conf)} accounts requiring specific signal review</p>", unsafe_allow_html=True)
        
        for _, r in low_conf.iterrows():
            tier = r['risk_tier']
            tier_cls = f"attention-card-{tier.lower()}"
            reasons = str(r.get('low_confidence_reasons', 'Data sparsity across signal dimensions'))
            if not reasons or reasons == 'nan':
                reasons = "Missing NPS response or sparse signal coverage"
            st.markdown(f"""
            <div class="attention-card {tier_cls}">
                <div style="font-weight: 700; color: #f8fafc; font-size: 0.95rem;">{r['account_name']}</div>
                <div style="font-size: 0.82rem; color: #a5b4fc; margin-top: 4px; line-height: 1.4;">
                    🔍 <b>Triggers:</b> {reasons}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
    with az:
        st.markdown("#### ⚡ Deprecated SDK Exposure")
        dep_sdk = renewal[renewal['sdk_deprecated'] == True]
        st.markdown(f"<p style='color: #94a3b8; font-size: 0.85rem;'>{len(dep_sdk)} accounts facing April 30 sunset deadline</p>", unsafe_allow_html=True)
        
        for _, r in dep_sdk.iterrows():
            tier = r['risk_tier']
            tier_cls = f"attention-card-{tier.lower()}"
            st.markdown(f"""
            <div class="attention-card {tier_cls}">
                <div style="font-weight: 700; color: #f8fafc; font-size: 0.95rem;">{r['account_name']}</div>
                <div style="font-size: 0.82rem; color: #fb7185; margin-top: 4px; line-height: 1.4;">
                    📦 <b>Version:</b> {r.get('sdk_version', 'v3.x')} (Sunset: April 30, 2026)
                </div>
            </div>
            """, unsafe_allow_html=True)
            
    st.markdown("</div>", unsafe_allow_html=True)


# ==============================================================================
# PAGE 2: ACCOUNT RISK ROSTER
# ==============================================================================
elif page == "📋 Account Risk Roster":
    st.title("Account Risk Roster")
    st.markdown("<p style='color: #94a3b8; font-size: 1.05rem; margin-top: -12px;'>Full breakdown of 90-day renewal accounts with drilldown intelligence & grounded explanations</p>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    def clear_search_cb():
        st.session_state["main_roster_search_bar"] = ""
        st.session_state["sidebar_search_input"] = ""

    # Main Page Search Bar + Controls
    col_search, col_clear = st.columns([4, 1])
    with col_search:
        main_search = st.text_input(
            "🔍 Search Account Roster",
            value=search,
            key="main_roster_search_bar",
            placeholder="Type account name (e.g. Zenith), account ID (e.g. 1007), plan tier, or risk signal...",
            label_visibility="collapsed"
        )
    with col_clear:
        st.button("❌ Clear Search", on_click=clear_search_cb, use_container_width=True)

    active_query = (main_search or search or "").strip().lower()

    # Filtering Logic
    filtered = renewal[renewal['risk_tier'].isin(tier_filter)].copy()

    if active_query:
        # Search across multiple columns safely
        name_mask = filtered['account_name'].astype(str).str.lower().str.contains(active_query, na=False)
        id_mask = filtered['account_id'].astype(str).str.lower().str.contains(active_query, na=False)
        tier_mask = filtered['risk_tier'].astype(str).str.lower().str.contains(active_query, na=False)
        
        plan_mask = filtered['plan_tier'].astype(str).str.lower().str.contains(active_query, na=False) if 'plan_tier' in filtered.columns else False
        expl_mask = filtered['explanation'].astype(str).str.lower().str.contains(active_query, na=False) if 'explanation' in filtered.columns else False
        
        combined_mask = name_mask | id_mask | tier_mask | plan_mask | expl_mask
        filtered = filtered[combined_mask]

    sort_map = {
        "Risk Score (High → Low)": ('risk_score', False),
        "ARR (High → Low)": ('arr', False),
        "Days to Renewal": ('days_to_renewal', True),
        "Account Name": ('account_name', True),
    }
    sort_col, sort_asc = sort_map[sort_by]
    filtered = filtered.sort_values(sort_col, ascending=sort_asc)

    if len(filtered) == 0:
        st.warning(f"⚠️ No accounts found matching query '{active_query}'. Try clearing search or checking your Risk Tier filters.")
    else:
        st.markdown(f"<p style='color: #cbd5e1; font-weight: 600; margin-top: 8px;'>Displaying {len(filtered)} accounts matching filters</p>", unsafe_allow_html=True)
    
    # Account Roster Items
    for _, row in filtered.iterrows():
        acct_id = to_int(row['account_id'])
        tier = str(row['risk_tier'])
        score = to_float(row['risk_score'])
        days_rem = to_int(row['days_to_renewal'])
        arr_val = to_float(row['arr'])
        
        # Build badge header
        tier_icon = tier_emoji(tier)
        badge_html = f"<span class='badge badge-{tier.lower()}'>{tier_icon} {tier} ({score:.1f})</span>"
        
        override_flag = ""
        if bool(row.get('critical_override', False)):
            override_flag = f" <span class='badge badge-override'>🚨 OVERRIDE</span>"
            
        conf_badge = ""
        if str(row.get('confidence_level')) == 'Low Confidence':
            conf_badge = f" <span class='badge badge-low-conf'>⚠️ Low Confidence</span>"
            
        # Expander header title string
        expander_title = f"{row['account_name']}  —  Score: {score:.1f}/100  |  ARR: \\${arr_val:,.0f}  |  Renews in {days_rem}d  |  {row.get('plan_tier','')} Plan"
        
        # Explicit key prevents Streamlit from slugifying _arr into an internal summary element
        with st.expander(expander_title, key=f"expander_{acct_id}"):
            st.markdown(f"<div>{badge_html}{override_flag}{conf_badge}</div><br>", unsafe_allow_html=True)
            
            d_col1, d_col2 = st.columns([1, 1])
            
            with d_col1:
                st.markdown("#### 📊 Risk Dimension Breakdown")
                
                dims = {
                    'Usage Trend (25%)': row.get('usage_trend_score', 0),
                    'Support Health (20%)': row.get('support_health_score', 0),
                    'Platform Risk (15%)': row.get('platform_risk_score', 0),
                    'CSM Sentiment (15%)': row.get('csm_sentiment_score', 0),
                    'NPS Signal (15%)': row.get('nps_signal_score', 0),
                    'Contract Proximity (10%)': row.get('contract_proximity_score', 0),
                }
                
                for label, val in dims.items():
                    st.markdown(render_score_gauge(val, label), unsafe_allow_html=True)
                    
                st.markdown(f"<div style='background: rgba(255,255,255,0.05); padding: 12px; border-radius: 8px; margin-top: 12px;'>"
                            f"<b>Composite Risk Score:</b> <span class='color-{tier.lower()}' style='font-size: 1.2rem; font-weight: 800;'>{score:.1f}/100</span> "
                            f"(Tier: <b>{tier}</b>)</div>", unsafe_allow_html=True)
                            
                if bool(row.get('critical_override', False)):
                    st.markdown(f"<div style='margin-top: 8px; color: #fb7185; font-size: 0.88rem;'>"
                                f"🚨 <b>Critical Override Triggered:</b> {row.get('override_reason', '')}</div>", unsafe_allow_html=True)
                                
                if str(row.get('confidence_level')) == 'Low Confidence':
                    reasons = str(row.get('low_confidence_reasons', 'Sparse data coverage'))
                    st.markdown(f"<div style='margin-top: 8px; color: #a5b4fc; font-size: 0.88rem;'>"
                                f"🔍 <b>Low Confidence Triggers:</b> {reasons}</div>", unsafe_allow_html=True)
            
            with d_col2:
                st.markdown("#### 💬 Grounded AI Risk Assessment")
                
                exp = explanations.get(acct_id, {})
                explanation_text = exp.get('explanation', 'No explanation generated.')
                action = exp.get('recommended_action', 'Manual review required.')
                
                st.markdown(f"<div style='background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(255, 255, 255, 0.08); padding: 16px; border-radius: 10px; line-height: 1.6; font-size: 0.93rem; color: #e2e8f0;'>"
                            f"{explanation_text}</div>", unsafe_allow_html=True)
                            
                st.markdown(f"<div style='background: rgba(99, 102, 241, 0.15); border-left: 3px solid #6366f1; padding: 12px 16px; border-radius: 0 8px 8px 0; margin-top: 12px; font-size: 0.9rem; color: #e0e7ff;'>"
                            f"🎯 <b>Recommended Action:</b> {action}</div>", unsafe_allow_html=True)
                            
                # Contradictions
                c_flags = str(row.get('contradiction_flags', ''))
                if c_flags and c_flags != 'nan':
                    st.markdown("<br><b>⚠️ Detected Contradictions:</b>", unsafe_allow_html=True)
                    for flag in c_flags.split(' | '):
                        if flag.strip():
                            st.markdown(f"<span class='badge badge-contradiction'>⚠️ {flag.strip()}</span>", unsafe_allow_html=True)
            
            # --- Raw Data Detail Grid ---
            st.markdown("<hr style='border-color: rgba(255,255,255,0.08); margin: 20px 0 15px 0;'>", unsafe_allow_html=True)
            st.markdown("#### 📈 Verified Source Signals")
            
            r1, r2, r3 = st.columns(3)
            
            with r1:
                st.markdown("<div style='font-size: 0.9rem; color: #94a3b8; font-weight: 700;'>USAGE METRICS</div>", unsafe_allow_html=True)
                api_calls_cnt = to_int(row.get('api_calls_last_month'))
                st.markdown(f"• **API Calls (Last Mo):** {api_calls_cnt:,}")
                st.markdown(f"• **API Trend (MoM):** {fmt_pct(row.get('api_calls_trend_pct'))}")
                st.markdown(f"• **Active Users:** {to_int(row.get('active_users_last_month'))}")
                st.markdown(f"• **User Trend (MoM):** {fmt_pct(row.get('active_users_trend_pct'))}")
                sdk_str = str(row.get('sdk_version', 'N/A'))
                is_dep = bool(row.get('sdk_deprecated', False))
                dep_tag = " <span style='color: #f43f5e; font-weight:700;'>⚠️ DEPRECATED</span>" if is_dep else ""
                st.markdown(f"• **SDK Version:** {sdk_str}{dep_tag}", unsafe_allow_html=True)
                
            with r2:
                st.markdown("<div style='font-size: 0.9rem; color: #94a3b8; font-weight: 700;'>SUPPORT HISTORY</div>", unsafe_allow_html=True)
                st.markdown(f"• **Total Tickets:** {to_int(row.get('ticket_count'))}")
                st.markdown(f"• **P1/P2 Severities:** {to_int(row.get('p1_p2_count'))}")
                st.markdown(f"• **Open / Escalated:** {to_int(row.get('open_escalated_count'))}")
                st.markdown(f"• **Ticket Trend:** {str(row.get('ticket_trend', 'none')).title()}")
                if bool(row.get('has_blocking_issue', False)):
                    st.markdown("• 🚨 <span style='color:#f43f5e;'>Has Blocking Issues</span>", unsafe_allow_html=True)
                    
            with r3:
                st.markdown("<div style='font-size: 0.9rem; color: #94a3b8; font-weight: 700;'>NPS & CSM INTELLIGENCE</div>", unsafe_allow_html=True)
                nps_val = row.get('nps_score')
                if pd.notna(nps_val):
                    st.markdown(f"• **NPS Score:** {to_int(nps_val)}")
                    verb = str(row.get('nps_verbatim', ''))
                    if verb and verb != 'nan':
                        st.markdown(f"• **Verbatim:** *\"{verb}\"*")
                        if acct_id in VERBATIM_TRANSLATIONS:
                            st.markdown(f"  🌐 **English Translation:** *\"{VERBATIM_TRANSLATIONS[acct_id]}\"*")
                else:
                    st.markdown("• **NPS Score:** *No response recorded*")
                    
                csm_ext = csm_extractions.get(acct_id)
                if csm_ext:
                    st.markdown(f"• **CSM Sentiment:** {str(csm_ext.get('sentiment','N/A')).title()}")
                    sig_list = csm_ext.get('churn_signals', [])
                    if sig_list:
                        st.markdown(f"• **Signals:** {', '.join(sig_list)}")
                    comp_list = csm_ext.get('competitor_names', [])
                    if comp_list:
                        st.markdown(f"• **Competitors:** {', '.join(comp_list)}")


# ==============================================================================
# PAGE 3: NON-OBVIOUS INSIGHTS
# ==============================================================================
elif page == "🔍 Non-Obvious Insights":
    st.title("Non-Obvious Portfolio Insights")
    st.markdown("<p style='color: #94a3b8; font-size: 1.05rem; margin-top: -12px;'>Cross-source patterns surfacing root causes a simple rule-based engine would misread</p>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    if not insights:
        st.warning("No processed insights found. Please ensure pipeline has completed.")
    else:
        for idx, ins in enumerate(insights):
            st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
            st.markdown(f"<div class='glass-card-header'>💡 {ins.get('title', 'Insight')}</div>", unsafe_allow_html=True)
            
            st.markdown(f"<div style='font-size: 1rem; line-height: 1.65; color: #e2e8f0; margin-bottom: 20px;'>"
                        f"{ins.get('summary', '')}</div>", unsafe_allow_html=True)
                        
            evidence = ins.get('evidence', {})
            
            # --- INSIGHT TYPE 1: SDK DEPRECATION ---
            if ins.get('type') == 'sdk_deprecation_impact':
                st.markdown("#### Portfolio-Level Exposure Metrics")
                
                mc1, mc2, mc3, mc4 = st.columns(4)
                
                with mc1:
                    dep_accts = to_int(evidence.get('deprecated_sdk_accounts', 0))
                    dep_pct = to_float(evidence.get('deprecated_sdk_pct', 0))
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-eyebrow">Deprecated SDK Accounts</div>
                        <div class="metric-value color-high">{dep_accts}</div>
                        <div class="metric-subtext">{dep_pct:.1f}% of total portfolio</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                with mc2:
                    dep_arr = to_float(evidence.get('deprecated_sdk_arr', 0))
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-eyebrow">ARR on Deprecated SDKs</div>
                        <div class="metric-value">{fmt_curr(dep_arr)}</div>
                        <div class="metric-subtext">Exposure facing April 30 sunset</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                with mc3:
                    ren_data = evidence.get('renewal_window', {})
                    ren_dep_cnt = to_int(ren_data.get('deprecated_count', 0))
                    ren_dep_arr = to_float(ren_data.get('deprecated_arr', 0))
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-eyebrow">Renewing in 90 Days</div>
                        <div class="metric-value color-high">{ren_dep_cnt}</div>
                        <div class="metric-subtext">{fmt_curr(ren_dep_arr)} ARR at stake</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                with mc4:
                    tr_comp = evidence.get('usage_trend_comparison', {})
                    delta_val = to_float(tr_comp.get('delta', 0))
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-eyebrow">Monthly Usage Decline Gap</div>
                        <div class="metric-value color-high">{delta_val:.1f}%/mo</div>
                        <div class="metric-subtext">Deprecated vs Current SDKs</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown("#### 📊 Comparative Usage Trajectory")
                
                dep_api_tr = to_float(tr_comp.get('deprecated_api_trend_pct_per_month', 0))
                cur_api_tr = to_float(tr_comp.get('current_api_trend_pct_per_month', 0))
                dep_usr_tr = to_float(tr_comp.get('deprecated_user_trend_pct_per_month', 0))
                cur_usr_tr = to_float(tr_comp.get('current_user_trend_pct_per_month', 0))
                dep_6m = to_float(tr_comp.get('deprecated_6m_api_change_pct', 0))
                cur_6m = to_float(tr_comp.get('current_6m_api_change_pct', 0))
                
                fig_comp = go.Figure()
                fig_comp.add_trace(go.Bar(
                    x=['API Calls MoM Trend', 'Active Users MoM Trend', '6-Month API Total Change'],
                    y=[dep_api_tr, dep_usr_tr, dep_6m],
                    name='Deprecated SDK v3.x',
                    marker=dict(color='#f43f5e', line=dict(color='rgba(255,255,255,0.1)', width=1)),
                    text=[f"{dep_api_tr:.1f}%", f"{dep_usr_tr:.1f}%", f"{dep_6m:.1f}%"],
                    textposition='auto',
                ))
                fig_comp.add_trace(go.Bar(
                    x=['API Calls MoM Trend', 'Active Users MoM Trend', '6-Month API Total Change'],
                    y=[cur_api_tr, cur_usr_tr, cur_6m],
                    name='Current SDK v4.x',
                    marker=dict(color='#10b981', line=dict(color='rgba(255,255,255,0.1)', width=1)),
                    text=[f"{cur_api_tr:.1f}%", f"{cur_usr_tr:.1f}%", f"{cur_6m:.1f}%"],
                    textposition='auto',
                ))
                
                fig_comp.update_layout(
                    title=dict(text="Monthly Usage Trends (% Change): Deprecated vs Current SDK Cohorts", font=dict(size=14, color="#f8fafc")),
                    yaxis_title="% Change",
                    barmode='group',
                    height=340,
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font_color='#f8fafc',
                    transition_duration=400,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    xaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
                    yaxis=dict(gridcolor='rgba(255,255,255,0.05)', zerolinecolor='rgba(255,255,255,0.1)')
                )
                st.plotly_chart(fig_comp, use_container_width=True)
                
                # Table of affected accounts
                dep_accts_list = evidence.get('deprecated_accounts', [])
                if dep_accts_list:
                    st.markdown("#### 📋 Deprecated SDK Accounts Renewing in 90 Days")
                    dep_df = pd.DataFrame(dep_accts_list)
                    if 'renewing_in_window' in dep_df.columns:
                        dep_df = dep_df[dep_df['renewing_in_window'] == True]
                    if len(dep_df) > 0:
                        dep_df['ARR ($)'] = dep_df['arr'].apply(fmt_curr_plain)
                        dep_df['API Trend (%/mo)'] = dep_df['api_calls_trend_pct'].apply(fmt_pct)
                        dep_df['6M API Change (%)'] = dep_df['api_calls_6m_change_pct'].apply(fmt_pct)
                        dep_df['Days to Renewal'] = dep_df['days_to_renewal'].apply(to_int)
                        
                        st.dataframe(
                            dep_df[['account_id', 'account_name', 'ARR ($)', 'sdk_version',
                                   'API Trend (%/mo)', '6M API Change (%)', 'Days to Renewal']].rename(
                                columns={'account_id': 'ID', 'account_name': 'Account Name', 'sdk_version': 'SDK'}
                            ),
                            use_container_width=True,
                            hide_index=True,
                        )
            
            # --- INSIGHT TYPE 2: TRAPPED USAGE ---
            elif ins.get('type') == 'trapped_usage':
                accts_list = evidence.get('accounts', [])
                if accts_list:
                    st.markdown("#### 📋 Trapped Usage Accounts (High Usage, Negative Stated Sentiment)")
                    trap_df = pd.DataFrame(accts_list)
                    trap_df['ARR ($)'] = trap_df['arr'].apply(fmt_curr_plain)
                    trap_df['API Trend (%/mo)'] = trap_df['api_calls_trend_pct'].apply(fmt_pct)
                    trap_df['NPS Score'] = trap_df['nps_score'].apply(to_int)
                    
                    # Add English translations for non-English verbatims in dataframe
                    trans_list = []
                    for _, r in trap_df.iterrows():
                        aid = to_int(r['account_id'])
                        if aid in VERBATIM_TRANSLATIONS:
                            trans_list.append(f"{r['nps_verbatim']} (🇬🇧 {VERBATIM_TRANSLATIONS[aid]})")
                        else:
                            trans_list.append(str(r['nps_verbatim']))
                    trap_df['NPS Verbatim Comment'] = trans_list
                    
                    st.dataframe(
                        trap_df[['account_id', 'account_name', 'ARR ($)',
                                'API Trend (%/mo)', 'NPS Score', 'NPS Verbatim Comment']].rename(
                            columns={'account_id': 'ID', 'account_name': 'Account Name'}
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )
            
            # Recommendation
            rec = ins.get('recommendation', '')
            if rec:
                st.markdown(f"<div style='background: rgba(16, 185, 129, 0.12); border-left: 4px solid #10b981; padding: 14px 18px; border-radius: 0 10px 10px 0; margin-top: 18px; color: #d1fae5; font-size: 0.93rem;'>"
                            f"🎯 <b>Actionable Recommendation:</b> {rec}</div>", unsafe_allow_html=True)
                            
            st.markdown("</div>", unsafe_allow_html=True)


# ==============================================================================
# FOOTER
# ==============================================================================
st.sidebar.markdown("---")
st.sidebar.markdown(
    "<div style='font-size: 0.78rem; color: #64748b; font-weight: 500; line-height: 1.5;'>"
    "⚡ <b>Renewal Intelligence Pipeline</b><br>"
    "Reference Date: April 15, 2026<br>"
    "Evaluation Window: 90 Days<br>"
    "LLM Provider: Groq (OpenAI-compatible)"
    "</div>",
    unsafe_allow_html=True
)
