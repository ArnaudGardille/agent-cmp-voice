"""
Lambda invoquée par le contact flow AWS Connect au début de chaque appel.
Elle lit les attributs de contact et retourne le system prompt Nova Sonic 2.

Déploiement : packager ce fichier + call_sheet.py + prompt.py dans un zip Lambda.
Handler : lambda_prompt.lambda_handler
"""
import json

from call_sheet import CallSheet
from prompt import build_system_prompt


def lambda_handler(event: dict, context) -> dict:
    """
    event["Details"]["ContactData"]["Attributes"] contient les attributs
    passés par trigger.py via start_outbound_voice_contact.
    """
    attrs = event["Details"]["ContactData"]["Attributes"]

    cs = CallSheet(
        call_id=attrs["call_id"],
        order_id=attrs["order_id"],
        customer_name=attrs["customer_name"],
        phone_number="",  # non nécessaire ici
        delivery_address=attrs["delivery_address"],
        proposed_delivery_date=attrs["proposed_delivery_date"],
        known_constraints={
            "cartons": int(attrs.get("cartons", 0)),
            "product": attrs.get("product", ""),
            "tail_lift_required": attrs.get("tail_lift_required") == "true",
            "small_truck_required": attrs.get("small_truck_required") == "true",
            "access_comment": attrs.get("access_comment", ""),
        },
    )

    system_prompt = build_system_prompt(cs)

    return {
        "system_prompt": system_prompt,
        "call_id": cs.call_id,
    }
