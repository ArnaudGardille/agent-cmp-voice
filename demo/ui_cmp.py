"""Design system CMP — helpers UI Streamlit brandés.

Palette, CSS, et composants réutilisables pour l'interface de démo.
"""

from __future__ import annotations

import streamlit as st

# ── Palette ─────────────────────────────────────────────────────────────────
NAVY = "#0E344A"
NAVY_DARK = "#092638"
WHITE = "#FFFFFF"
OFFWHITE = "#F7F5F1"
LIGHT_GRAY = "#E8E8E8"
GRAY = "#6B7280"
CHARCOAL = "#1F2933"
ACCENT = "#D9B15F"
GREEN = "#7BAE6A"

# ── Status ───────────────────────────────────────────────────────────────────
STATUS_COLORS: dict[str, tuple[str, str]] = {
    "confirmed": (GREEN, "#F0F7ED"),
    "reschedule_needed": (ACCENT, "#FBF6EA"),
    "constraints_detected": ("#D97706", "#FEF3C7"),
    "unreachable": (GRAY, "#F3F4F6"),
    "human_review_required": ("#DC2626", "#FEE2E2"),
    "escalated": ("#DC2626", "#FEE2E2"),
    "pending_call": (NAVY, "#EBF2F7"),
    "in_progress": (NAVY, "#EBF2F7"),
    "completed": (GREEN, "#F0F7ED"),
    "analysed": (GREEN, "#F0F7ED"),
    "human_review": ("#DC2626", "#FEE2E2"),
}

STATUS_LABELS: dict[str, str] = {
    "confirmed": "✅ Confirmée",
    "reschedule_needed": "📅 Report nécessaire",
    "constraints_detected": "⚠️ Contraintes détectées",
    "unreachable": "📵 Injoignable",
    "human_review_required": "👤 Revue humaine",
    "escalated": "🔺 Escaladée",
    "pending_call": "⏳ En attente d'appel",
    "in_progress": "📞 En cours",
    "completed": "✅ Terminé",
    "analysed": "🤖 Analysé",
    "human_review": "👤 Revue humaine",
}

# ── CSS ──────────────────────────────────────────────────────────────────────
CMP_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800;900&display=swap');

html, body, [class*="css"] {
    font-family: 'Montserrat', 'Inter', 'Helvetica Neue', Arial, sans-serif !important;
}

/* Hide default Streamlit chrome */
#MainMenu { visibility: hidden; }
footer    { visibility: hidden; }
header    { visibility: hidden; }

/* App background */
.stApp { background-color: #F7F5F1; }

/* Content width */
.block-container {
    padding-top: 2rem;
    padding-bottom: 3rem;
    max-width: 1140px;
}

/* ── Sidebar ─────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background-color: #0E344A !important;
}
[data-testid="stSidebar"] * {
    color: #FFFFFF !important;
}
[data-testid="stSidebar"] .stTextInput > label,
[data-testid="stSidebar"] .stNumberInput > label,
[data-testid="stSidebar"] .stRadio > label,
[data-testid="stSidebar"] .stCheckbox > label {
    color: rgba(255,255,255,0.65) !important;
    font-size: 0.78rem !important;
    font-weight: 700 !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}
[data-testid="stSidebar"] input,
[data-testid="stSidebar"] .stTextInput input {
    background: rgba(255,255,255,0.1) !important;
    border: 1px solid rgba(255,255,255,0.2) !important;
    color: white !important;
    border-radius: 10px !important;
}
[data-testid="stSidebar"] hr {
    border-color: rgba(255,255,255,0.12) !important;
}

/* ── Buttons ─────────────────────────────────────────────────────────── */
.stButton > button[kind="primary"] {
    background-color: #0E344A !important;
    color: white !important;
    border: none !important;
    border-radius: 999px !important;
    font-weight: 700 !important;
    font-family: 'Montserrat', sans-serif !important;
    padding: 0.55rem 1.5rem !important;
    transition: background 0.18s ease;
}
.stButton > button[kind="primary"]:hover {
    background-color: #092638 !important;
}
.stButton > button:not([kind="primary"]) {
    background-color: transparent !important;
    color: #0E344A !important;
    border: 2px solid rgba(14,52,74,0.25) !important;
    border-radius: 999px !important;
    font-weight: 700 !important;
    font-family: 'Montserrat', sans-serif !important;
}
.stButton > button:not([kind="primary"]):hover {
    border-color: #0E344A !important;
}

/* ── Progress bar ────────────────────────────────────────────────────── */
.stProgress > div > div > div > div {
    background-color: #0E344A !important;
}

/* ── CMP components ──────────────────────────────────────────────────── */
.cmp-header {
    background: linear-gradient(135deg, #0E344A 0%, #092638 100%);
    border-radius: 24px;
    padding: 2.25rem 2.5rem 2rem;
    margin-bottom: 2rem;
    color: white;
}
.cmp-logo {
    font-size: 2.4rem;
    font-weight: 900;
    letter-spacing: -0.05em;
    color: white;
    line-height: 1;
    margin-bottom: 0.4rem;
}
.cmp-header-eyebrow {
    font-size: 0.72rem;
    font-weight: 700;
    color: rgba(255,255,255,0.5);
    text-transform: uppercase;
    letter-spacing: 0.14em;
    margin-bottom: 0.35rem;
}
.cmp-header-title {
    font-size: 1.45rem;
    font-weight: 800;
    color: white;
    letter-spacing: -0.02em;
    margin-bottom: 0.2rem;
}
.cmp-header-subtitle {
    font-size: 0.9rem;
    color: rgba(255,255,255,0.58);
    font-weight: 400;
}
.cmp-header-accent {
    display: inline-block;
    margin-top: 1rem;
    padding: 0.28rem 0.85rem;
    border-radius: 999px;
    background: rgba(217,177,95,0.18);
    color: #D9B15F;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}

.cmp-card {
    background: white;
    border-radius: 20px;
    padding: 1.5rem 1.6rem;
    box-shadow: 0 6px 20px rgba(14,52,74,0.06);
    border: 1px solid rgba(14,52,74,0.07);
    margin-bottom: 1rem;
    height: 100%;
}
.cmp-card-label {
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: #0E344A;
    opacity: 0.5;
    margin-bottom: 0.55rem;
}
.cmp-card-value {
    font-size: 1.25rem;
    font-weight: 800;
    color: #0E344A;
    letter-spacing: -0.02em;
    line-height: 1.25;
}
.cmp-card-sub {
    font-size: 0.8rem;
    color: #6B7280;
    margin-top: 0.25rem;
    line-height: 1.4;
}

.cmp-section-eyebrow {
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: #0E344A;
    opacity: 0.45;
    margin-bottom: 0.3rem;
}
.cmp-section-title {
    font-size: 1.35rem;
    font-weight: 800;
    color: #1F2933;
    letter-spacing: -0.025em;
    margin-bottom: 1.1rem;
}

.cmp-badge {
    display: inline-block;
    padding: 0.3rem 0.9rem;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.03em;
}

.cmp-transcript {
    background: #F7F5F1;
    border-radius: 16px;
    padding: 1.4rem 1.6rem;
    font-size: 0.86rem;
    line-height: 1.75;
    color: #1F2933;
    white-space: pre-wrap;
    max-height: 380px;
    overflow-y: auto;
    border: 1px solid rgba(14,52,74,0.06);
}

.cmp-empty-state {
    text-align: center;
    padding: 2.5rem 1.5rem;
    background: white;
    border-radius: 20px;
    border: 1px dashed rgba(14,52,74,0.15);
}
.cmp-empty-icon { font-size: 2.2rem; margin-bottom: 0.6rem; }
.cmp-empty-title {
    font-size: 1rem;
    font-weight: 700;
    color: #0E344A;
    margin-bottom: 0.2rem;
}
.cmp-empty-sub { font-size: 0.82rem; color: #6B7280; }

.cmp-summary-card {
    background: white;
    border-radius: 20px;
    padding: 1.5rem 1.6rem;
    border-left: 4px solid #0E344A;
    box-shadow: 0 6px 20px rgba(14,52,74,0.06);
    margin-bottom: 1rem;
}

.cmp-conf-wrap {
    background: #E8E8E8;
    border-radius: 999px;
    height: 7px;
    overflow: hidden;
    margin-top: 0.5rem;
}
.cmp-conf-bar {
    height: 100%;
    border-radius: 999px;
    transition: width 0.4s ease;
}

.cmp-divider {
    border: none;
    border-top: 1px solid rgba(14,52,74,0.09);
    margin: 1.75rem 0;
}
</style>
"""


# ── Public helpers ────────────────────────────────────────────────────────────

def inject_cmp_theme() -> None:
    """Inject the CMP design system CSS."""
    st.markdown(CMP_CSS, unsafe_allow_html=True)


def render_header(
    *,
    title: str = "Agent Vocal de Confirmation de Livraison",
    subtitle: str = "Nova Sonic 2 · AWS Connect · Analyse LLM post-appel",
    badge: str = "Démo",
) -> None:
    st.markdown(
        f"""
        <div class="cmp-header">
          <div class="cmp-logo">CMP</div>
          <div class="cmp-header-eyebrow">Confirmation de livraison — IA vocale</div>
          <div class="cmp-header-title">{title}</div>
          <div class="cmp-header-subtitle">{subtitle}</div>
          <div class="cmp-header-accent">{badge}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section(eyebrow: str, title: str) -> None:
    st.markdown(
        f"""
        <div class="cmp-section-eyebrow">{eyebrow}</div>
        <div class="cmp-section-title">{title}</div>
        """,
        unsafe_allow_html=True,
    )


def render_card(label: str, value: str, sub: str = "") -> str:
    sub_html = f'<div class="cmp-card-sub">{sub}</div>' if sub else ""
    return f"""
    <div class="cmp-card">
        <div class="cmp-card-label">{label}</div>
        <div class="cmp-card-value">{value}</div>
        {sub_html}
    </div>
    """


def render_status_badge(status: str) -> str:
    label = STATUS_LABELS.get(status, status)
    fg, bg = STATUS_COLORS.get(status, (NAVY, OFFWHITE))
    return f'<span class="cmp-badge" style="color:{fg};background:{bg};">{label}</span>'


def render_confidence_bar(score: float) -> str:
    pct = int(score * 100)
    color = GREEN if score >= 0.8 else ACCENT if score >= 0.6 else "#DC2626"
    return f"""
    <div>
        <span style="font-size:1.6rem;font-weight:900;color:{NAVY};">{pct}%</span>
        <span style="font-size:0.72rem;color:{GRAY};font-weight:700;
                     text-transform:uppercase;letter-spacing:0.08em;margin-left:0.4rem;">
            Confiance
        </span>
        <div class="cmp-conf-wrap">
            <div class="cmp-conf-bar" style="width:{pct}%;background:{color};"></div>
        </div>
    </div>
    """


def render_empty_state(icon: str, title: str, sub: str) -> None:
    st.markdown(
        f"""
        <div class="cmp-empty-state">
            <div class="cmp-empty-icon">{icon}</div>
            <div class="cmp-empty-title">{title}</div>
            <div class="cmp-empty-sub">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
