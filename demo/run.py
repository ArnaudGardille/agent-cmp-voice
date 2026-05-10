#!/usr/bin/env python3
"""
Script de démo complet — agent vocal CMP.

Modes :
  Nova Sonic (Twilio) : python run.py --phone +33XXXXXXXXX --nova-sonic
  AWS Connect (Polly) : python run.py --phone +33XXXXXXXXX
  Simulation          : python run.py --skip-call
  Sans AWS            : python run.py --skip-call --mock-analysis

Variables pour Nova Sonic (Twilio) :
  TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER
  BRIDGE_BASE_URL (URL publique ngrok du bridge, e.g. https://xxxx.ngrok-free.app)
    → si absent, ngrok est démarré automatiquement
  AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN
  AWS_DEFAULT_REGION=us-east-1  (Nova Sonic)

Variables pour AWS Connect (Polly) :
  CONNECT_INSTANCE_ID, CONTACT_FLOW_ID, CONNECT_SOURCE_PHONE
"""
import argparse
import json
import os
import sys
import threading
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent))

from analysis import analyse_transcript
from call_sheet import build_call_sheet
from prompt import build_system_prompt
from seed import DEMO_ORDER, seed
from trigger import trigger_call


def main() -> None:
    parser = argparse.ArgumentParser(description="Démo agent vocal CMP")
    parser.add_argument("--order-id", default=DEMO_ORDER["order_id"])
    parser.add_argument(
        "--phone",
        help="Numéro de téléphone cible au format E.164 (écrase la BDD)",
    )
    parser.add_argument(
        "--nova-sonic",
        action="store_true",
        help="Utilise Nova Sonic + Twilio (voix naturelle) au lieu d'AWS Connect + Polly",
    )
    parser.add_argument(
        "--skip-call",
        action="store_true",
        help="Utilise un transcript fictif au lieu de déclencher un vrai appel",
    )
    parser.add_argument(
        "--mock-analysis",
        action="store_true",
        help="Retourne un résultat d'analyse fictif (sans appel Bedrock)",
    )
    args = parser.parse_args()

    # 1. Seed
    print("\n=== 1. Préparation des données ===")
    seed()

    # 2. Fiche d'appel
    print("\n=== 2. Fiche d'appel ===")
    cs = build_call_sheet(args.order_id)
    if args.phone:
        cs.phone_number = args.phone
    print(cs.to_json())

    # 3. System prompt
    print("\n=== 3. System prompt Nova Sonic 2 ===")
    prompt = build_system_prompt(cs)
    print(prompt)

    # 4. Appel
    if args.skip_call:
        print("\n=== 4. [Simulation] Transcript fictif ===")
        transcript = _demo_transcript(cs)
        print(transcript)
        _register_simulated_call(cs)

    elif args.nova_sonic:
        if not cs.phone_number or "XXXX" in cs.phone_number:
            print("\n⚠ Numéro cible non défini. Utilise --phone +33XXXXXXXXX")
            sys.exit(1)
        transcript = _run_nova_sonic_call(cs)

    else:
        instance_id = os.environ.get("CONNECT_INSTANCE_ID", "")
        flow_id = os.environ.get("CONTACT_FLOW_ID", "")
        source_phone = os.environ.get("CONNECT_SOURCE_PHONE", "")
        if not all([instance_id, flow_id, source_phone]):
            print(
                "\n⚠ Variables manquantes : CONNECT_INSTANCE_ID, CONTACT_FLOW_ID, "
                "CONNECT_SOURCE_PHONE.\n"
                "Lance avec --skip-call pour tester sans AWS Connect, "
                "ou --nova-sonic pour Nova Sonic + Twilio."
            )
            sys.exit(1)
        if not cs.phone_number or "XXXX" in cs.phone_number:
            print("\n⚠ Numéro cible non défini. Utilise --phone +33XXXXXXXXX")
            sys.exit(1)

        print("\n=== 4. Déclenchement de l'appel (AWS Connect + Polly) ===")
        trigger_call(cs, instance_id, flow_id, source_phone)
        print("Appel en cours. En attente de la fin de l'appel...")
        print("(En prod, le webhook de fin d'appel déclenche l'analyse automatiquement.)")
        input("Appuie sur Entrée une fois l'appel terminé pour lancer l'analyse...")
        transcript = _demo_transcript(cs)  # remplacer par le vrai transcript S3

    # 5. Analyse post-appel
    print("\n=== 5. Analyse post-appel ===")
    if args.mock_analysis:
        result = _mock_analysis(cs)
        print("[Mode mock — résultat fictif]")
    else:
        result = analyse_transcript(cs.call_id, transcript, cs.to_json())
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # 6. Résumé lisible
    print("\n=== Résultat final ===")
    _print_summary(result)


def _run_nova_sonic_call(cs) -> str:
    """Start bridge server + ngrok, trigger Twilio call, wait for transcript."""
    import importlib

    import uvicorn
    from trigger_twilio import trigger_call as twilio_trigger

    bridge_mod = importlib.import_module("demo.nova_sonic_bridge")
    call_sheet_text = cs.to_json()
    delivery_date = cs.proposed_delivery_date or "lundi prochain"
    token = bridge_mod.set_call_context(cs.order_id, call_sheet_text, delivery_date)

    # Start uvicorn in a background thread
    print("\n=== 4a. Démarrage du bridge Nova Sonic ===")
    port = int(os.environ.get("BRIDGE_PORT", "8080"))
    server_config = uvicorn.Config(
        bridge_mod.app, host="0.0.0.0", port=port, log_level="warning"
    )
    server = uvicorn.Server(server_config)
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()
    time.sleep(2)  # wait for server to be ready
    print(f"   Bridge démarré sur le port {port}")

    # Resolve public URL (ngrok if BRIDGE_BASE_URL not set or is a placeholder)
    _raw = os.environ.get("BRIDGE_BASE_URL", "").strip()
    bridge_base = _raw.rstrip("/") if _raw.startswith("http") else ""
    if not bridge_base:
        print("\n=== 4b. Démarrage du tunnel ngrok ===")
        from pyngrok import ngrok

        tunnel = ngrok.connect(port, "http")
        bridge_base = tunnel.public_url.replace("http://", "https://")
        print(f"   URL publique : {bridge_base}")

    ws_url = bridge_base.replace("https://", "wss://") + "/media"
    twiml_url = bridge_base + "/twiml"
    os.environ["BRIDGE_WS_URL"] = ws_url
    os.environ["BRIDGE_BASE_URL"] = bridge_base
    print(f"   WebSocket  : {ws_url}")
    print(f"   TwiML      : {twiml_url}")

    # Trigger outbound Twilio call
    print("\n=== 4c. Déclenchement de l'appel Twilio → Nova Sonic ===")
    twilio_trigger(
        phone=cs.phone_number,
        call_sheet=call_sheet_text,
        delivery_date=delivery_date,
    )

    # Wait for call to complete (bridge sets call_complete=True)
    print("   Appel en cours — attente de la fin de la conversation...")
    timeout = int(os.environ.get("CALL_TIMEOUT", "180"))
    for _ in range(timeout):
        time.sleep(1)
        if bridge_mod.is_call_complete(token):
            break
    else:
        print("   ⚠ Timeout — l'appel n'a pas terminé dans le délai imparti.")

    transcript = bridge_mod.get_transcript(token) or _demo_transcript(cs)
    print(f"\n=== 4d. Transcript capturé ({len(transcript.splitlines())} lignes) ===")
    print(transcript)
    return transcript


def _demo_transcript(cs) -> str:
    c = cs.known_constraints
    cartons = c.get("cartons", 48)
    product = c.get("product", "marchandises")
    return f"""
Agent : Bonjour, je suis l'assistant vocal de CMP. Je vous appelle au sujet d'une livraison prévue pour {cs.customer_name}. Je suis bien au service réception ou logistique ?

Client : Oui, c'est moi. Jean-Pierre Morin, responsable réception.

Agent : Bonjour Jean-Pierre. Nous avons une livraison de {cartons} cartons de {product} prévue le jeudi 15 mai. Est-ce que cette date vous convient ?

Client : Oui, le 15 mai c'est bon pour nous.

Agent : Parfait. Vous préférez un créneau le matin, entre 8h et 12h, ou l'après-midi, entre 13h et 17h ?

Client : Le matin, avant 10h si possible.

Agent : Noté, matin avant 10h. L'adresse de livraison est bien ZAC des Châtelets, 22000 Saint-Brieuc, entrée par le portail nord, quai numéro 3 ?

Client : Exactement, quai 3. Attention, la rue d'accès est assez étroite, il faut pas venir avec un très grand camion.

Agent : Bien noté. Notre camion sera équipé d'un hayon élévateur. C'est compatible avec votre quai ?

Client : Oui, pas de problème avec un hayon, on n'a pas de quai rehaussé ici.

Agent : Très bien. Pour récapituler : livraison le jeudi 15 mai, le matin avant 10h, à Saint-Brieuc ZAC des Châtelets quai 3, camion avec hayon. Votre contact sur place sera Jean-Pierre Morin. C'est bien ça ?

Client : C'est parfait.

Agent : Excellent. Je transmets la confirmation à nos équipes. Merci Jean-Pierre, bonne journée !

Client : Merci, bonne journée.
""".strip()


def _mock_analysis(cs) -> dict:
    """Résultat fictif pour la démo sans Bedrock."""
    import sqlite3
    from call_sheet import DB_PATH

    result = {
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
            "Livraison confirmée le 15 mai, matin avant 10h. "
            "Adresse validée, hayon requis. Contact : Jean-Pierre Morin."
        ),
    }
    with sqlite3.connect(DB_PATH) as conn:
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
    return result


def _register_simulated_call(cs) -> None:
    """Enregistre un appel simulé en base pour que l'analyse puisse écrire le résultat."""
    import sqlite3
    from call_sheet import DB_PATH

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """INSERT OR REPLACE INTO delivery_call_results
               (call_id, order_id, phone_number, call_status, processing_status,
                created_at, updated_at)
               VALUES (?, ?, ?, 'completed', 'pending', datetime('now'), datetime('now'))""",
            (cs.call_id, cs.order_id, cs.phone_number),
        )
        conn.commit()


def _print_summary(result: dict) -> None:
    icons = {
        "confirmed": "✅",
        "reschedule_needed": "📅",
        "constraints_detected": "⚠️",
        "human_review_required": "👤",
    }
    icon = icons.get(result.get("call_status", ""), "❓")
    window_labels = {"morning": "matin", "afternoon": "après-midi"}
    window = window_labels.get(result.get("delivery_window", ""), "—")

    print(f"{icon} Statut      : {result.get('call_status')}")
    print(f"   Date       : {result.get('confirmed_delivery_date', '—')} ({window})")
    print(f"   Contact    : {result.get('contact_name', '—')}")
    print(f"   Hayon      : {result.get('tail_lift_required', '—')}")
    print(f"   Accès      : {result.get('access_notes', '—')}")
    print(f"   Confiance  : {result.get('confidence_score', 0):.0%}")
    print(f"   Résumé     : {result.get('business_summary', '—')}")
    if result.get("human_review_required"):
        print("   ⚠ Revue humaine requise")


if __name__ == "__main__":
    main()
