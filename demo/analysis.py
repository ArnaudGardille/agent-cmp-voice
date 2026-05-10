"""
Analyse post-appel : envoie le transcript à un LLM Bedrock et produit
un résultat métier structuré, écrit en table tampon.
"""
import json
import re
import sqlite3

import boto3

from call_sheet import DB_PATH

SYSTEM_PROMPT = """\
Tu es un analyste post-appel pour CMP, spécialiste de la logistique de distribution.
Tu reçois le transcript d'un appel de confirmation de livraison et la fiche d'appel initiale.

Extrais les informations suivantes et réponds UNIQUEMENT avec un objet JSON valide, sans texte autour :

{
  "call_status": "confirmed | reschedule_needed | constraints_detected | unreachable | human_review_required",
  "client_available": true | false | null,
  "confirmed_delivery_date": "YYYY-MM-DD | null",
  "delivery_window": "morning | afternoon | null",
  "address_confirmed": true | false | null,
  "tail_lift_required": true | false | null,
  "small_truck_required": true | false | null,
  "contact_name": "nom du contact jour-J | null",
  "access_notes": "notes d'accès éventuelles | null",
  "human_review_required": true | false,
  "confidence_score": 0.0,
  "business_summary": "résumé en une phrase"
}

Règles strictes :
- Ne déduis jamais une information absente du transcript : mets null.
- Si la conversation est ambiguë ou contradictoire : human_review_required=true, confidence_score < 0.7.
- call_status = "confirmed" uniquement si le client a explicitement validé la date.
"""


def analyse_transcript(
    call_id: str,
    transcript: str,
    call_sheet_json: str,
    model_id: str = "amazon.nova-lite-v1:0",
) -> dict:
    client = boto3.client("bedrock-runtime")

    response = client.converse(
        modelId=model_id,
        system=[{"text": SYSTEM_PROMPT}],
        messages=[
            {
                "role": "user",
                "content": [{"text": (
                    f"Fiche d'appel initiale :\n{call_sheet_json}\n\n"
                    f"Transcript :\n{transcript}\n\n"
                    "Produis l'analyse JSON."
                )}],
            }
        ],
        inferenceConfig={"maxTokens": 512, "temperature": 0.1},
    )

    raw = response["output"]["message"]["content"][0]["text"]
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError(f"Réponse LLM non parseable :\n{raw}")

    try:
        result = json.loads(match.group())
    except json.JSONDecodeError as e:
        raise ValueError(f"Réponse LLM JSON invalide : {e}\nBrut : {raw}") from e
    result["call_id"] = call_id
    _write_to_buffer(call_id, result)
    return result


def _write_to_buffer(call_id: str, result: dict) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """UPDATE delivery_call_results SET
                   final_result_json       = ?,
                   confidence_score        = ?,
                   human_review_required   = ?,
                   proposed_action         = ?,
                   processing_status       = 'analysed',
                   updated_at              = datetime('now')
               WHERE call_id = ?""",
            (
                json.dumps(result, ensure_ascii=False),
                result.get("confidence_score", 0.0),
                1 if result.get("human_review_required") else 0,
                result.get("call_status"),
                call_id,
            ),
        )
        conn.commit()
    print(f"✓ Résultat écrit en table tampon pour call_id={call_id}")
