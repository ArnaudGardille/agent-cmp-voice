"""CMP business tools for the BidiAgent."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from strands import tool

DB_PATH = Path(__file__).parent / "demo.db"


def make_cmp_tools(order_id: str) -> list:
    """Return Strands tools bound to a specific order_id (via closure)."""

    @tool
    def confirmer_livraison(date_confirmee: str, contraintes: str = "") -> str:
        """Enregistre la confirmation de livraison par le client.

        Args:
            date_confirmee: Date confirmée par le client (ex: "2026-05-15" ou "jeudi 15 mai").
            contraintes: Contraintes d'accès mentionnées par le client.
        """
        result = {
            "order_id": order_id,
            "status": "confirmed",
            "delivery_date": date_confirmee,
            "constraints": contraintes,
            "confirmed_at": datetime.now().isoformat(),
        }
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO delivery_call_results
                   (call_id, order_id, phone_number, call_status, final_result_json,
                    confidence_score, processing_status, created_at, updated_at)
                   VALUES (?, ?, '', 'completed', ?, 0.95, 'analysed',
                           datetime('now'), datetime('now'))""",
                (
                    f"NOVA-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    order_id,
                    json.dumps(result, ensure_ascii=False),
                ),
            )
            conn.commit()
        return f"Livraison confirmée le {date_confirmee}. Contraintes : {contraintes or 'aucune'}."

    @tool
    def signaler_contrainte(contrainte: str) -> str:
        """Enregistre une contrainte logistique mentionnée par le client.

        Args:
            contrainte: Description de la contrainte (hayon, accès restreint, créneau...).
        """
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO delivery_call_results
                   (call_id, order_id, phone_number, call_status, raw_result_json,
                    processing_status, created_at, updated_at)
                   VALUES (?, ?, '', 'in_progress', ?, 'pending',
                           datetime('now'), datetime('now'))""",
                (
                    f"NOVA-CSTR-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    order_id,
                    json.dumps({"constraint_noted": contrainte}, ensure_ascii=False),
                ),
            )
            conn.commit()
        return f"Contrainte enregistrée : {contrainte}."

    @tool
    def escalader(raison: str) -> str:
        """Escalade l'appel vers un conseiller humain CMP.

        Args:
            raison: Motif de l'escalade (client mécontent, date impossible, refus...).
        """
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO delivery_call_results
                   (call_id, order_id, phone_number, call_status,
                    human_review_required, processing_status, created_at, updated_at)
                   VALUES (?, ?, '', 'escalated', 1, 'human_review',
                           datetime('now'), datetime('now'))""",
                (f"NOVA-ESC-{datetime.now().strftime('%Y%m%d%H%M%S')}", order_id),
            )
            conn.commit()
        return f"Escalade enregistrée : {raison}. Un conseiller CMP rappellera le client."

    return [confirmer_livraison, signaler_contrainte, escalader]
