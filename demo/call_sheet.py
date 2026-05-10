"""
Lit une commande en base et génère la fiche d'appel structurée.
"""
import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "demo.db"


@dataclass
class CallSheet:
    call_id: str
    order_id: str
    customer_name: str
    phone_number: str
    delivery_address: str
    proposed_delivery_date: str
    known_constraints: dict
    call_objectives: list = field(
        default_factory=lambda: [
            "confirm_availability",
            "confirm_delivery_window",
            "confirm_address",
            "confirm_access_constraints",
            "get_onsite_contact",
        ]
    )

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    def to_connect_attributes(self) -> dict[str, str]:
        """Retourne les attributs à passer à AWS Connect (valeurs string uniquement)."""
        c = self.known_constraints
        return {
            "call_id": self.call_id,
            "order_id": self.order_id,
            "customer_name": self.customer_name,
            "delivery_address": self.delivery_address,
            "proposed_delivery_date": self.proposed_delivery_date,
            "cartons": str(c.get("cartons", "")),
            "product": c.get("product", ""),
            "tail_lift_required": "true" if c.get("tail_lift_required") else "false",
            "small_truck_required": "true" if c.get("small_truck_required") else "false",
            "access_comment": c.get("access_comment", ""),
        }


def build_call_sheet(order_id: str) -> CallSheet:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM commandes WHERE order_id = ?", (order_id,)
    ).fetchone()
    conn.close()

    if row is None:
        raise ValueError(f"Commande introuvable : {order_id}")

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return CallSheet(
        call_id=f"CALL-{ts}",
        order_id=row["order_id"],
        customer_name=row["customer_name"],
        phone_number=row["phone_number"],
        delivery_address=row["delivery_address"],
        proposed_delivery_date=row["proposed_delivery_date"],
        known_constraints=json.loads(row["known_constraints"]),
    )
