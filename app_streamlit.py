"""Page Streamlit brandée CMP — démo agent vocal de confirmation de livraison.

Lancement : streamlit run app_streamlit.py
"""

from __future__ import annotations

import html
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# ── Make demo helpers importable ─────────────────────────────────────────────
_DEMO_DIR = Path(__file__).parent / "demo"
if str(_DEMO_DIR) not in sys.path:
    sys.path.insert(0, str(_DEMO_DIR))

from call_sheet import CallSheet, build_call_sheet, DB_PATH  # noqa: E402
from seed import seed, DEMO_ORDER  # noqa: E402
from analysis import analyse_transcript  # noqa: E402
from ui_cmp import (  # noqa: E402
    ACCENT,
    CHARCOAL,
    GRAY,
    GREEN,
    NAVY,
    OFFWHITE,
    inject_cmp_theme,
    render_card,
    render_confidence_bar,
    render_empty_state,
    render_header,
    render_section,
    render_status_badge,
    STATUS_LABELS,
)

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="CMP · Agent Vocal",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_cmp_theme()

# ── Session state ─────────────────────────────────────────────────────────────
_DEFAULTS: dict[str, object] = {
    "call_sheet": None,
    "transcript": None,
    "analysis_result": None,
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ── Helpers ───────────────────────────────────────────────────────────────────

def _format_date(date_str: str | None) -> str:
    if not date_str:
        return "—"
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return date_str


def _window_label(w: str | None) -> str:
    return {"morning": "Matin (avant 12h)", "afternoon": "Après-midi (13h–17h)"}.get(w or "", "—")


def _load_orders() -> list[dict]:
    if not DB_PATH.exists():
        return []
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM commandes ORDER BY order_id").fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except sqlite3.Error:
        return []


def _load_call_results() -> list[dict]:
    if not DB_PATH.exists():
        return []
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM delivery_call_results ORDER BY created_at DESC LIMIT 30"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except sqlite3.Error:
        return []


def _build_demo_transcript(cs: CallSheet) -> str:
    c = cs.known_constraints
    cartons = c.get("cartons", 48)
    product = c.get("product", "marchandises")
    date_fr = _format_date(cs.proposed_delivery_date)
    return f"""Agent : Bonjour, je suis l'assistant vocal de CMP. Je vous appelle au sujet d'une livraison prévue pour {cs.customer_name}. Je suis bien au service réception ou logistique ?

Client : Oui, c'est moi. Jean-Pierre Morin, responsable réception.

Agent : Bonjour Jean-Pierre. Nous avons une livraison de {cartons} cartons de {product} prévue le {date_fr}. Est-ce que cette date vous convient ?

Client : Oui, le {date_fr} c'est bon pour nous.

Agent : Parfait. Vous préférez un créneau le matin, entre 8h et 12h, ou l'après-midi, entre 13h et 17h ?

Client : Le matin, avant 10h si possible.

Agent : Noté, matin avant 10h. L'adresse de livraison est bien {cs.delivery_address}, entrée par le portail nord, quai numéro 3 ?

Client : Exactement, quai 3. Attention, la rue d'accès est assez étroite, il ne faut pas venir avec un très grand camion.

Agent : Bien noté. Notre camion sera équipé d'un hayon élévateur. C'est compatible avec votre quai ?

Client : Oui, pas de problème avec un hayon, on n'a pas de quai rehaussé ici.

Agent : Très bien. Pour récapituler : livraison le {date_fr}, le matin avant 10h, à {cs.delivery_address}, quai 3, camion avec hayon. Votre contact sur place sera Jean-Pierre Morin. C'est bien ça ?

Client : C'est parfait.

Agent : Excellent. Je transmets la confirmation à nos équipes. Merci Jean-Pierre, bonne journée !

Client : Merci, bonne journée.""".strip()


def _register_simulated_call(cs: CallSheet) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """INSERT OR REPLACE INTO delivery_call_results
           (call_id, order_id, phone_number, call_status, processing_status,
            created_at, updated_at)
           VALUES (?, ?, ?, 'completed', 'pending', datetime('now'), datetime('now'))""",
        (cs.call_id, cs.order_id, cs.phone_number),
    )
    conn.commit()
    conn.close()


def _mock_analysis(cs: CallSheet) -> dict:
    result: dict = {
        "call_id": cs.call_id,
        "call_status": "confirmed",
        "client_available": True,
        "confirmed_delivery_date": cs.proposed_delivery_date,
        "delivery_window": "morning",
        "address_confirmed": True,
        "tail_lift_required": True,
        "small_truck_required": False,
        "contact_name": "Jean-Pierre Morin",
        "access_notes": "Rue étroite — camion standard max. Quai n°3, portail nord.",
        "human_review_required": False,
        "confidence_score": 0.96,
        "business_summary": (
            f"Livraison confirmée le {_format_date(cs.proposed_delivery_date)}, "
            "matin avant 10h. Adresse validée, hayon requis. Contact : Jean-Pierre Morin."
        ),
    }
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """UPDATE delivery_call_results SET
               final_result_json     = ?,
               confidence_score      = ?,
               human_review_required = ?,
               proposed_action       = ?,
               processing_status     = 'analysed',
               updated_at            = datetime('now')
           WHERE call_id = ?""",
        (
            json.dumps(result, ensure_ascii=False),
            result["confidence_score"],
            0,
            result["call_status"],
            cs.call_id,
        ),
    )
    conn.commit()
    conn.close()
    return result


def _render_transcript(transcript: str) -> None:
    lines = transcript.strip().splitlines()
    html_lines: list[str] = []
    for raw in lines:
        escaped = html.escape(raw)
        if raw.startswith("Agent"):
            html_lines.append(
                f'<span style="color:{NAVY};font-weight:700;">{escaped}</span>'
            )
        elif raw.startswith("Client"):
            html_lines.append(f'<span style="color:{CHARCOAL};">{escaped}</span>')
        else:
            html_lines.append(f'<span style="color:{GRAY};">{escaped}</span>')
    body = "<br>".join(html_lines)
    st.markdown(f'<div class="cmp-transcript">{body}</div>', unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        f"""
        <div style="padding:1rem 0 0.75rem;">
            <div style="font-size:1.8rem;font-weight:900;letter-spacing:-0.05em;color:white;">CMP</div>
            <div style="font-size:0.68rem;font-weight:700;text-transform:uppercase;
                        letter-spacing:0.14em;color:rgba(255,255,255,0.45);margin-top:0.1rem;">
                Agent Vocal
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()

    st.markdown(
        '<div style="font-size:0.68rem;font-weight:700;text-transform:uppercase;'
        'letter-spacing:0.1em;color:rgba(255,255,255,0.5);margin-bottom:0.4rem;">Commande</div>',
        unsafe_allow_html=True,
    )
    order_id = st.text_input(
        "ID commande",
        value=DEMO_ORDER["order_id"],
        label_visibility="collapsed",
    )

    st.divider()

    st.markdown(
        '<div style="font-size:0.68rem;font-weight:700;text-transform:uppercase;'
        'letter-spacing:0.1em;color:rgba(255,255,255,0.5);margin-bottom:0.4rem;">Mode</div>',
        unsafe_allow_html=True,
    )
    run_mode = st.radio(
        "Mode d'exécution",
        ["Simulation", "Appel réel (Nova Sonic)"],
        label_visibility="collapsed",
    )

    phone_number: str | None = None
    if run_mode == "Appel réel (Nova Sonic)":
        phone_number = st.text_input("Numéro (E.164)", placeholder="+33XXXXXXXXX")

    use_mock = st.checkbox(
        "Analyse fictive (sans Bedrock)",
        value=True,
        help="Retourne un résultat pré-défini sans appel AWS Bedrock.",
    )

    st.divider()

    btn_seed = st.button("🗃️ Initialiser la démo", use_container_width=True)
    btn_run = st.button("📞 Lancer la démo", type="primary", use_container_width=True)
    btn_reset = st.button("🔄 Réinitialiser", use_container_width=True)

    if btn_reset:
        for k in _DEFAULTS:
            st.session_state[k] = None
        st.rerun()

# ── Seed ──────────────────────────────────────────────────────────────────────
if btn_seed:
    with st.spinner("Initialisation de la base de données…"):
        seed()
    st.toast("✅ Base de données initialisée")

# ── Run ───────────────────────────────────────────────────────────────────────
if btn_run:
    try:
        with st.spinner("Préparation de la fiche d'appel…"):
            cs = build_call_sheet(order_id)
            if phone_number:
                cs.phone_number = phone_number
            st.session_state.call_sheet = cs

        with st.spinner("Simulation de l'appel…"):
            transcript = _build_demo_transcript(cs)
            _register_simulated_call(cs)
            st.session_state.transcript = transcript

        with st.spinner("Analyse post-appel…"):
            if use_mock:
                result = _mock_analysis(cs)
            else:
                result = analyse_transcript(cs.call_id, transcript, cs.to_json())
            st.session_state.analysis_result = result

        st.toast("✅ Démo terminée — résultats disponibles")

    except Exception as exc:
        st.error(f"Erreur : {exc}")

# ── References ────────────────────────────────────────────────────────────────
cs: CallSheet | None = st.session_state.call_sheet
transcript: str | None = st.session_state.transcript
result: dict | None = st.session_state.analysis_result

# ── Header ────────────────────────────────────────────────────────────────────
render_header()

# ═════════════════════════════════════════════════════════════════════════════
# Étape 1 — Commande
# ═════════════════════════════════════════════════════════════════════════════
render_section("Étape 1 — Préparation", "Commande & fiche d'appel")

if cs is None:
    orders = _load_orders()
    if not orders:
        render_empty_state(
            "🗃️",
            "Base de données vide",
            "Cliquez sur « Initialiser la démo » puis « Lancer la démo ».",
        )
    else:
        for o in orders:
            c = json.loads(o.get("known_constraints", "{}"))
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(
                    render_card("Commande", o["order_id"], o["customer_name"]),
                    unsafe_allow_html=True,
                )
            with col2:
                st.markdown(
                    render_card(
                        "Date proposée",
                        _format_date(o["proposed_delivery_date"]),
                        o["delivery_address"],
                    ),
                    unsafe_allow_html=True,
                )
            with col3:
                st.markdown(
                    render_card(
                        "Produit",
                        c.get("product", "—"),
                        f"{c.get('cartons', '—')} cartons",
                    ),
                    unsafe_allow_html=True,
                )
else:
    c = cs.known_constraints
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(
            render_card("Commande", cs.order_id, cs.customer_name),
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            render_card(
                "Date proposée",
                _format_date(cs.proposed_delivery_date),
                cs.delivery_address,
            ),
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            render_card(
                "Produit",
                c.get("product", "—"),
                f"{c.get('cartons', '—')} cartons",
            ),
            unsafe_allow_html=True,
        )
    with col4:
        flags: list[str] = []
        if c.get("tail_lift_required"):
            flags.append("🔧 Hayon requis")
        if c.get("small_truck_required"):
            flags.append("🚚 Petit camion")
        access = c.get("access_comment", "")
        st.markdown(
            render_card(
                "Contraintes logistiques",
                flags[0] if flags else "Aucune",
                " · ".join(flags[1:]) if len(flags) > 1 else (access or "—"),
            ),
            unsafe_allow_html=True,
        )
    with st.expander("📋 Fiche d'appel complète (JSON)"):
        st.json(json.loads(cs.to_json()))

st.markdown('<hr class="cmp-divider"/>', unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════════════════════
# Étape 2 — Appel
# ═════════════════════════════════════════════════════════════════════════════
render_section("Étape 2 — Appel sortant", "Transcript de la conversation")

if transcript is None:
    render_empty_state(
        "📞",
        "Aucun appel déclenché",
        "Cliquez sur « Lancer la démo » pour simuler un appel.",
    )
else:
    _render_transcript(transcript)

st.markdown('<hr class="cmp-divider"/>', unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════════════════════
# Étape 3 — Analyse post-appel
# ═════════════════════════════════════════════════════════════════════════════
render_section("Étape 3 — Analyse post-appel (LLM)", "Résultat structuré")

if result is None:
    render_empty_state(
        "🤖",
        "Analyse en attente",
        "L'analyse LLM s'exécutera automatiquement après l'appel.",
    )
else:
    status = result.get("call_status", "—")
    score = float(result.get("confidence_score") or 0.0)

    # Row 1 — status / confidence / date / créneau
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(
            f"""
            <div class="cmp-card">
                <div class="cmp-card-label">Statut appel</div>
                <div style="margin-top:0.3rem;">{render_status_badge(status)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f"""
            <div class="cmp-card">
                <div class="cmp-card-label">Score de confiance</div>
                {render_confidence_bar(score)}
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            render_card("Date confirmée", _format_date(result.get("confirmed_delivery_date"))),
            unsafe_allow_html=True,
        )
    with col4:
        st.markdown(
            render_card("Créneau", _window_label(result.get("delivery_window"))),
            unsafe_allow_html=True,
        )

    # Row 2 — contact / access / logistics
    col5, col6, col7 = st.columns(3)
    with col5:
        st.markdown(
            render_card("Contact jour-J", result.get("contact_name") or "—"),
            unsafe_allow_html=True,
        )
    with col6:
        st.markdown(
            render_card("Accès / Contraintes", result.get("access_notes") or "—"),
            unsafe_allow_html=True,
        )
    with col7:
        logi: list[str] = []
        if result.get("tail_lift_required"):
            logi.append("🔧 Hayon requis")
        if result.get("small_truck_required"):
            logi.append("🚚 Petit camion")
        if result.get("address_confirmed"):
            logi.append("✅ Adresse confirmée")
        st.markdown(
            render_card("Logistique", " · ".join(logi) if logi else "—"),
            unsafe_allow_html=True,
        )

    # Business summary
    summary = result.get("business_summary", "")
    if summary:
        st.markdown(
            f"""
            <div class="cmp-summary-card">
                <div class="cmp-card-label">Résumé métier</div>
                <div style="font-size:0.95rem;color:#1F2933;line-height:1.65;margin-top:0.4rem;">
                    {html.escape(summary)}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if result.get("human_review_required"):
        st.warning(
            "⚠️ **Revue humaine requise** — Ce résultat nécessite une validation manuelle "
            "avant mise à jour de la base CMP.",
        )

    with st.expander("🔍 Résultat complet (JSON)"):
        st.json(result)

st.markdown('<hr class="cmp-divider"/>', unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════════════════════
# Étape 4 — Table tampon
# ═════════════════════════════════════════════════════════════════════════════
render_section("Étape 4 — Base de données", "Table tampon des résultats d'appels")

db_rows = _load_call_results()

if not db_rows:
    render_empty_state(
        "🗄️",
        "Table tampon vide",
        "Les résultats d'appels apparaîtront ici après la démo.",
    )
else:
    st.caption(f"{len(db_rows)} résultat(s) enregistré(s)")
    for row in db_rows:
        final = json.loads(row.get("final_result_json") or "{}")
        raw_status = row.get("call_status", "pending_call")
        badge_html = render_status_badge(raw_status)
        score_val = final.get("confidence_score") or row.get("confidence_score") or 0.0
        score_pct = f"{int(float(score_val) * 100)}%" if score_val else "—"

        with st.expander(
            f"📋 {row['call_id']}  ·  {row['order_id']}  ·  {raw_status}",
            expanded=False,
        ):
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.markdown(f"**Call ID**<br>{row['call_id']}", unsafe_allow_html=True)
            with c2:
                st.markdown(f"**Commande**<br>{row['order_id']}", unsafe_allow_html=True)
            with c3:
                st.markdown(f"**Statut**<br>{badge_html}", unsafe_allow_html=True)
            with c4:
                st.markdown(f"**Confiance**<br>{score_pct}", unsafe_allow_html=True)

            if final:
                bs = final.get("business_summary", "")
                if bs:
                    st.caption(bs)
                st.json(final)
