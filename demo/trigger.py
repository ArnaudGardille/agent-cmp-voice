"""
Déclenche l'appel sortant via AWS Connect et enregistre le statut initial en base.

AWS Connect passe les attributs de contact à la Lambda (lambda_prompt.py),
qui génère le system prompt injecté dans Nova Sonic 2.
"""
import sqlite3

import boto3

from call_sheet import DB_PATH, CallSheet


def trigger_call(
    cs: CallSheet,
    connect_instance_id: str,
    contact_flow_id: str,
    source_phone_number: str,
) -> str:
    """Lance l'appel sortant. Retourne le ContactId AWS Connect."""
    client = boto3.client("connect")

    response = client.start_outbound_voice_contact(
        DestinationPhoneNumber=cs.phone_number,
        ContactFlowId=contact_flow_id,
        InstanceId=connect_instance_id,
        SourcePhoneNumber=source_phone_number,
        Attributes=cs.to_connect_attributes(),
    )

    contact_id = response["ContactId"]
    _register_call(cs, contact_id)
    print(f"✓ Appel déclenché — call_id={cs.call_id}  contact_id={contact_id}")
    return contact_id


def _register_call(cs: CallSheet, contact_id: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """INSERT INTO delivery_call_results
           (call_id, order_id, phone_number, call_status, processing_status,
            created_at, updated_at)
           VALUES (?, ?, ?, 'calling', 'pending', datetime('now'), datetime('now'))""",
        (cs.call_id, cs.order_id, cs.phone_number),
    )
    conn.commit()
    conn.close()
