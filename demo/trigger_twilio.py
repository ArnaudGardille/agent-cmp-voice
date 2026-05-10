"""
Déclenche un appel sortant Twilio avec Media Streams → Nova Sonic bridge.

Usage:
  python -m demo.trigger_twilio --phone +33648740634 [--call-sheet "..."] [--delivery-date "lundi 14 juillet"]
  
Variables d'environnement requises:
  TWILIO_ACCOUNT_SID
  TWILIO_AUTH_TOKEN
  TWILIO_PHONE_NUMBER  (numéro source Twilio, e.g. +14155238886)
  BRIDGE_BASE_URL      (URL publique du bridge, e.g. https://xxxx.ngrok-free.app)
"""

import argparse
import os
import sys

from twilio.rest import Client


def trigger_call(phone: str, call_sheet: str, delivery_date: str) -> str:
    account_sid = os.environ["TWILIO_ACCOUNT_SID"]
    auth_token = os.environ["TWILIO_AUTH_TOKEN"]
    from_number = os.environ["TWILIO_PHONE_NUMBER"]
    bridge_base = os.environ["BRIDGE_BASE_URL"].rstrip("/")

    twiml_url = f"{bridge_base}/twiml"

    client = Client(account_sid, auth_token)

    print(f"📞 Appel sortant Twilio → {phone}")
    print(f"   TwiML: {twiml_url}")

    call = client.calls.create(
        to=phone,
        from_=from_number,
        url=twiml_url,
        method="POST",
    )

    print(f"   Call SID: {call.sid}")
    return call.sid


def main():
    parser = argparse.ArgumentParser(description="Trigger Twilio outbound call with Nova Sonic")
    parser.add_argument("--phone", required=True, help="Numéro cible (e.g. +33648740634)")
    parser.add_argument("--call-sheet", default="Client: Arnaud Gardille, commande #12345, 10 palettes de peinture")
    parser.add_argument("--delivery-date", default="lundi 14 juillet 2025")
    args = parser.parse_args()

    # Mettre à jour le call sheet dans le bridge (si le bridge tourne localement)
    try:
        import requests  # optional
        bridge_base = os.environ.get("BRIDGE_BASE_URL", "http://localhost:8080")
        # Le bridge lit depuis les env vars au démarrage; on peut aussi injecter via API
    except ImportError:
        pass

    sid = trigger_call(
        phone=args.phone,
        call_sheet=args.call_sheet,
        delivery_date=args.delivery_date,
    )
    print(f"\n✅ Appel lancé: {sid}")
    print("   Twilio va appeler le numéro cible et connecter le Media Stream au bridge Nova Sonic.")
    print(f"   Consultez les logs du bridge pour suivre la conversation.")
    return sid


if __name__ == "__main__":
    main()
