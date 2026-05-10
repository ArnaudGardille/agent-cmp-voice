"""
Crée la base SQLite de démo et insère une commande fictive crédible.
Usage : python seed.py
"""
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "demo.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS commandes (
    order_id                TEXT PRIMARY KEY,
    customer_name           TEXT NOT NULL,
    phone_number            TEXT NOT NULL,
    delivery_address        TEXT NOT NULL,
    proposed_delivery_date  TEXT NOT NULL,
    known_constraints       TEXT NOT NULL DEFAULT '{}',
    status                  TEXT NOT NULL DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS delivery_call_results (
    call_id                 TEXT PRIMARY KEY,
    order_id                TEXT NOT NULL REFERENCES commandes(order_id),
    phone_number            TEXT NOT NULL,
    call_status             TEXT NOT NULL DEFAULT 'pending_call',
    transcript              TEXT,
    raw_result_json         TEXT,
    final_result_json       TEXT,
    confidence_score        REAL,
    human_review_required   INTEGER DEFAULT 0,
    proposed_action         TEXT,
    applied_action          TEXT,
    processing_status       TEXT DEFAULT 'pending',
    created_at              TEXT DEFAULT (datetime('now')),
    updated_at              TEXT DEFAULT (datetime('now'))
);
"""

# Scénario : CMP livre 48 cartons d'éclairage LED à l'entrepôt Intermarché Saint-Brieuc.
DEMO_ORDER = {
    "order_id": "CMD-20260515-001",
    "customer_name": "Intermarché Saint-Brieuc — Entrepôt logistique",
    "phone_number": "+33XXXXXXXXX",  # À remplacer ou passer via --phone
    "delivery_address": "ZAC des Châtelets, 22000 Saint-Brieuc",
    "proposed_delivery_date": "2026-05-15",
    "known_constraints": json.dumps(
        {
            "cartons": 48,
            "product": "Éclairage LED Pro 100W",
            "tail_lift_required": True,
            "small_truck_required": False,
            "access_comment": "Entrée par le portail nord, quai n°3",
        }
    ),
    "status": "pending",
}


def seed() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.execute(
        """INSERT OR REPLACE INTO commandes
           (order_id, customer_name, phone_number, delivery_address,
            proposed_delivery_date, known_constraints, status)
           VALUES (:order_id, :customer_name, :phone_number, :delivery_address,
                   :proposed_delivery_date, :known_constraints, :status)""",
        DEMO_ORDER,
    )
    conn.commit()
    conn.close()
    print(f"✓ {DEMO_ORDER['order_id']} inséré dans {DB_PATH}")


if __name__ == "__main__":
    seed()
