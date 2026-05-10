"""
Lambda handler invoqué par AWS Connect à chaque tour de conversation.

Reçoit l'action (greet / confirm_receipt / confirm_dock / confirm_time / close)
via Parameters, retourne le message correspondant.  Les messages sont pré-scriptés
pour la démo ; la version production génèrera les réponses via Bedrock Nova Sonic.
"""
import json
import os

import boto3

# Pour la démo, messages pré-scriptés (modifiables sans redéploiement via env vars)
SCRIPTS: dict[str, str] = {
    "greet": (
        "Bonjour, ici CMP, votre distributeur. Je vous appelle concernant "
        "votre livraison prévue le quinze mai. Êtes-vous disponible pour confirmer "
        "les détails ?"
    ),
    "confirm_receipt": (
        "Merci. Vous devez recevoir quarante-huit cartons d'Éclairage LED Pro cent "
        "watts. Pouvez-vous confirmer que vous êtes en mesure de réceptionner cette "
        "livraison ?"
    ),
    "confirm_dock": (
        "Très bien. La livraison nécessite un camion avec hayon. Disposez-vous "
        "d'un quai équipé disponible ce jour-là ?"
    ),
    "confirm_time": (
        "Parfait. Avez-vous une préférence pour l'heure de livraison dans la matinée, "
        "plutôt neuf heures ou onze heures ?"
    ),
    "close": (
        "Noté. La livraison est donc confirmée pour le quinze mai matin à votre "
        "entrepôt de Saint-Brieuc. Nous vous enverrons un récapitulatif par courriel. "
        "Merci et excellente journée !"
    ),
}

BEDROCK_REGION = os.environ.get("BEDROCK_REGION", "us-east-1")
MODEL_ID = os.environ.get("MODEL_ID", "amazon.nova-lite-v1:0")


def _bedrock_response(action: str, call_sheet_json: str) -> str:
    """Génère une réponse contextuelle via Bedrock (optionnel, fallback sur script)."""
    bedrock = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
    try:
        cs = json.loads(call_sheet_json) if call_sheet_json else {}
    except json.JSONDecodeError:
        cs = {}

    system_prompt = (
        "Tu es un agent vocal CMP (distributeur B2B). Tu appelles pour confirmer "
        f"une livraison. Détails : {json.dumps(cs, ensure_ascii=False)}. "
        "Réponds en UNE phrase courte et professionnelle en français."
    )
    user_msg = f"Génère le message pour l'étape : {action}"

    response = bedrock.converse(
        modelId=MODEL_ID,
        system=[{"text": system_prompt}],
        messages=[{"role": "user", "content": [{"text": user_msg}]}],
    )
    return response["output"]["message"]["content"][0]["text"]


def lambda_handler(event: dict, context) -> dict:
    params = event.get("Details", {}).get("Parameters", {})
    attrs = event.get("Details", {}).get("ContactData", {}).get("Attributes", {})

    action = params.get("action", "greet")
    call_sheet_json = attrs.get("call_sheet_json", "")

    # Utilise Bedrock si une call_sheet est fournie, sinon script pré-défini
    if call_sheet_json:
        try:
            message = _bedrock_response(action, call_sheet_json)
        except Exception:
            message = SCRIPTS.get(action, "Merci et bonne journée.")
    else:
        message = SCRIPTS.get(action, "Merci et bonne journée.")

    return {
        "message": message,
        "action": action,
        "done": "true" if action == "close" else "false",
    }
