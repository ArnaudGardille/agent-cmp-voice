"""
Bridge Twilio Media Streams ↔ Amazon Nova Sonic (Strands BidiAgent).

Architecture:
  Twilio appel sortant
    → WebSocket /media (µ-law 8kHz, base64)
    → transcode µ-law → PCM 16kHz (numpy)
    → Strands BidiAgent → Nova Sonic (us-east-1)
    → transcode PCM 16kHz → µ-law 8kHz
    → WebSocket Twilio

Usage:
  export AWS_DEFAULT_REGION=us-east-1
  eval $(aws configure export-credentials --format env)
  uvicorn demo.nova_sonic_bridge:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import threading
import uuid
from collections import deque

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response
from strands.experimental.bidi import BidiAgent
from strands.experimental.bidi.models import BidiNovaSonicModel
from strands.experimental.bidi.types.events import (
    BidiAudioInputEvent,
    BidiAudioStreamEvent,
    BidiTextInputEvent,
    BidiTranscriptStreamEvent,
)

from .tools_cmp import make_cmp_tools

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI()

NOVA_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
NOVA_VOICE = os.environ.get("NOVA_VOICE", "matthew")

# Per-call contexts keyed by a token returned by set_call_context().
# A Lock guards both structures across threads (uvicorn event loop + run.py main thread).
_context_lock = threading.Lock()
_pending_tokens: deque[str] = deque()   # FIFO of unclaimed tokens
_contexts: dict[str, dict] = {}         # token → call data

# ---------------------------------------------------------------------------
# µ-law 8kHz ↔ PCM 16kHz transcoding (numpy, no audioop)
# ---------------------------------------------------------------------------

_ULAW_BIAS = 132  # ITU-T G.711 bias constant
_ULAW_CLIP = 32767

# Exponent lookup table for µ-law encoding (ITU-T G.711)
_EXP_LUT = np.array([
    0, 0, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
    5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5,
    5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5,
    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
], dtype=np.int32)

_ULAW_TABLE: np.ndarray | None = None


def _build_ulaw_table() -> np.ndarray:
    """ITU-T G.711 µ-law decode table: wire byte → int16 PCM."""
    table = np.zeros(256, dtype=np.int16)
    for i in range(256):
        u = ~i & 0xFF
        exp = (u >> 4) & 0x07
        mantissa = u & 0x0F
        sample = (((mantissa << 3) + _ULAW_BIAS) << exp) - _ULAW_BIAS
        table[i] = np.int16(-sample if (u & 0x80) else sample)
    return table


def ulaw_to_pcm16(ulaw_bytes: bytes) -> np.ndarray:
    """Convert µ-law 8kHz bytes to PCM int16 samples (ITU-T G.711)."""
    global _ULAW_TABLE
    if _ULAW_TABLE is None:
        _ULAW_TABLE = _build_ulaw_table()
    return _ULAW_TABLE[np.frombuffer(ulaw_bytes, dtype=np.uint8)]


def pcm16_to_ulaw(samples: np.ndarray) -> bytes:
    """Convert PCM int16 samples to µ-law bytes (ITU-T G.711)."""
    s = samples.astype(np.int32)
    sign = np.where(s < 0, np.int32(0x80), np.int32(0))
    s = np.abs(s)
    s = np.minimum(s + _ULAW_BIAS, _ULAW_CLIP)
    exp = _EXP_LUT[(s >> 7) & 0xFF]
    mantissa = ((s >> (exp + 3)) & 0x0F).astype(np.int32)
    ulaw = (~(sign | (exp << 4) | mantissa)) & 0xFF
    return ulaw.astype(np.uint8).tobytes()


def resample_8k_to_16k(samples_8k: np.ndarray) -> np.ndarray:
    """Simple linear upsampling 8kHz → 16kHz."""
    return np.repeat(samples_8k, 2)


def resample_16k_to_8k(samples_16k: np.ndarray) -> np.ndarray:
    """Simple decimation 16kHz → 8kHz."""
    return samples_16k[::2]


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_TEMPLATE = """\
Tu es l'assistant vocal de CMP, distributeur logistique B2B.
Tu effectues un appel sortant pour confirmer une livraison client.

Informations commande :
{call_sheet}

Conduis la conversation en français, de façon naturelle et professionnelle.
Tes objectifs dans l'ordre :
1. Te présenter : "Bonjour, CMP Distribution, je vous appelle pour confirmer une livraison."
2. Vérifier que tu parles bien au bon interlocuteur (service réception ou logistique).
3. Confirmer la date proposée : {delivery_date}.
4. Demander s'il y a des contraintes d'accès (hayon, créneau, camion taille limitée...).
5. Reformuler le récapitulatif et demander confirmation.
6. Appeler l'outil confirmer_livraison pour enregistrer la confirmation.
7. Prendre congé poliment.

En cas de refus de date, mécontentement ou situation complexe : appeler escalader.
Pour chaque contrainte mentionnée : appeler signaler_contrainte.
Réponds en 1-2 phrases courtes. Ne pose qu'une seule question à la fois."""


# ---------------------------------------------------------------------------
# Twilio WebSocket /media
# ---------------------------------------------------------------------------


@app.websocket("/media")
async def media_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    log.info("Twilio WebSocket connecté")

    with _context_lock:
        token = _pending_tokens.popleft() if _pending_tokens else None
        ctx = _contexts.get(token, {}).copy() if token else {}

    order_id = ctx.get("order_id", "CMD-DEMO-001")
    call_sheet_text = ctx.get("call_sheet", "Commande démo")
    delivery_date = ctx.get("delivery_date", "lundi prochain")

    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
        call_sheet=call_sheet_text,
        delivery_date=delivery_date,
    )

    model = BidiNovaSonicModel(
        model_id="amazon.nova-2-sonic-v1:0",
        client_config={"region": NOVA_REGION},
        provider_config={"audio": {"voice": NOVA_VOICE}},
    )
    tools = make_cmp_tools(order_id)
    agent = BidiAgent(model=model, tools=tools, system_prompt=system_prompt)

    transcript_parts: list[str] = []
    stream_sid: str | None = None
    media_count = 0

    async def recv_from_nova() -> None:
        nonlocal stream_sid
        try:
            async for event in agent.receive():
                if isinstance(event, BidiAudioStreamEvent):
                    pcm_bytes = base64.b64decode(event.audio)
                    pcm_16k = np.frombuffer(pcm_bytes, dtype=np.int16)
                    pcm_8k = resample_16k_to_8k(pcm_16k)
                    ulaw = pcm16_to_ulaw(pcm_8k)
                    if stream_sid:
                        await ws.send_text(
                            json.dumps({
                                "event": "media",
                                "streamSid": stream_sid,
                                "media": {"payload": base64.b64encode(ulaw).decode()},
                            })
                        )
                elif isinstance(event, BidiTranscriptStreamEvent) and event.is_final:
                    tag = "[agent]" if event.role == "assistant" else "[client]"
                    log.info("%s %s", tag, event.text)
                    transcript_parts.append(f"{tag} {event.text}")
        except asyncio.CancelledError:
            pass
        except Exception:
            log.error("recv_from_nova error", exc_info=True)

    async with agent:
        receiver_task = asyncio.create_task(recv_from_nova())
        try:
            async for message in ws.iter_text():
                data = json.loads(message)
                event_type = data.get("event")

                if event_type == "start":
                    stream_sid = data["start"]["streamSid"]
                    log.info("Stream démarré : %s", stream_sid)
                    await agent.send(
                        BidiTextInputEvent(
                            text=(
                                "[SYSTEM: L'appel vient d'être décroché. "
                                "Commence immédiatement la conversation en français.]"
                            )
                        )
                    )

                elif event_type == "media":
                    ulaw_bytes = base64.b64decode(data["media"]["payload"])
                    media_count += 1
                    if media_count % 50 == 0:
                        log.info("Audio Twilio→Nova: %d paquets reçus", media_count)
                    pcm_8k = ulaw_to_pcm16(ulaw_bytes)
                    pcm_16k = resample_8k_to_16k(pcm_8k)
                    b64 = base64.b64encode(pcm_16k.astype(np.int16).tobytes()).decode()
                    await agent.send(
                        BidiAudioInputEvent(audio=b64, format="pcm", sample_rate=16000, channels=1)
                    )

                elif event_type == "stop":
                    log.info("Stream Twilio arrêté")
                    break

        except WebSocketDisconnect:
            log.info("WebSocket Twilio déconnecté")
        finally:
            receiver_task.cancel()
            await asyncio.gather(receiver_task, return_exceptions=True)

    transcript = "\n".join(transcript_parts)
    log.info("Transcript final (%d lignes):\n%s", len(transcript_parts), transcript)
    with _context_lock:
        if token and token in _contexts:
            _contexts[token]["transcript"] = transcript
            _contexts[token]["call_complete"] = True


@app.post("/twiml")
async def twiml_endpoint() -> Response:
    ws_url = os.environ.get("BRIDGE_WS_URL", "wss://localhost:8080/media")
    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f'<Connect><Stream url="{ws_url}" /></Connect>'
        "</Response>"
    )
    return Response(content=twiml, media_type="application/xml")


@app.get("/ping")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


# ---------------------------------------------------------------------------
# Call context helpers (called from run.py)
# ---------------------------------------------------------------------------


def set_call_context(order_id: str, call_sheet: str, delivery_date: str) -> str:
    """Register context for the next outbound call. Returns a token for tracking."""
    token = str(uuid.uuid4())
    with _context_lock:
        _contexts[token] = {
            "order_id": order_id,
            "call_sheet": call_sheet,
            "delivery_date": delivery_date,
            "transcript": None,
            "call_complete": False,
        }
        _pending_tokens.append(token)
    return token


def get_transcript(token: str) -> str | None:
    with _context_lock:
        return _contexts.get(token, {}).get("transcript")


def is_call_complete(token: str) -> bool:
    with _context_lock:
        return bool(_contexts.get(token, {}).get("call_complete"))
