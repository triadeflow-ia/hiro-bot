"""Hiro Bot, Sushi da Hora WhatsApp AI Agent (LangGraph + FastAPI + Stevo)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.config import settings
from unittest.mock import AsyncMock, patch

from src.integrations.stevo import parse_stevo_webhook, send_text
from src.agent.graph import run_agent
from src.agent.nodes import transcribe_audio, analyze_image

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Hiro Bot",
    description="Atendente IA do Sushi da Hora, WhatsApp (LangGraph + Stevo)",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (promo images + presentation page)
_assets_dir = Path(__file__).parent.parent / "assets"
if _assets_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_assets_dir)), name="static")

# Serve the presentation page
_public_dir = Path(__file__).parent.parent / "public"
if _public_dir.exists():
    app.mount("/proposta", StaticFiles(directory=str(_public_dir), html=True), name="proposta")

# ─── KEYWORD ACTIVATION SYSTEM ────────────────────────────
# Tracks which phone numbers have the bot active
# Bot only responds to conversations where someone sent the activation keyword
_active_sessions: dict[str, bool] = {}


def is_active(phone: str) -> bool:
    """Check if bot is active for this phone number."""
    return _active_sessions.get(phone, False)


def activate(phone: str):
    """Activate bot for this phone number."""
    _active_sessions[phone] = True
    logger.info(f"🍣 HIRO ATIVADO para {phone}")


def deactivate(phone: str):
    """Deactivate bot for this phone number."""
    _active_sessions.pop(phone, None)
    logger.info(f"⏹️ HIRO DESATIVADO para {phone}")


# ─── ENDPOINTS ─────────────────────────────────────────────

@app.post("/", include_in_schema=False)
async def root_post():
    return JSONResponse({"status": "ok"})


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "hiro-bot",
        "version": "1.0.0",
        "model": settings.anthropic_model if settings.anthropic_api_key else settings.openai_model,
        "active_sessions": len(_active_sessions),
        "keyword_activate": settings.keyword_activate,
        "keyword_deactivate": settings.keyword_deactivate,
    }


@app.get("/sessions")
async def list_sessions():
    """List all active bot sessions."""
    return {"active_sessions": _active_sessions}


@app.post("/webhook/stevo")
async def stevo_webhook(request: Request):
    """Receive Stevo/WhatsApp webhook and process with LangGraph agent."""
    if not settings.openai_api_key and not settings.anthropic_api_key:
        return JSONResponse(
            {"status": "error", "detail": "No LLM API key configured"},
            status_code=503,
        )

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    parsed = parse_stevo_webhook(payload)
    if parsed is None:
        return JSONResponse({"status": "skipped", "reason": "not inbound or filtered"})

    # For outbound (IsFromMe) messages: only process keyword commands, skip everything else
    if parsed.get("is_from_me"):
        # Check if it's a keyword command from the owner
        phone = parsed.get("phone", "")
        # We need to extract text from the raw payload for outbound messages
        raw_msg = payload.get("data", {}).get("Message", {})
        outbound_text = (
            raw_msg.get("conversation")
            or raw_msg.get("extendedTextMessage", {}).get("text")
            or ""
        ).strip().lower()

        if outbound_text == settings.keyword_activate.lower():
            activate(phone)
            logger.info(f"Owner ativou Hiro para {phone} via IsFromMe")
            return JSONResponse({"status": "activated_by_owner", "phone": phone})
        elif outbound_text == settings.keyword_deactivate.lower():
            deactivate(phone)
            logger.info(f"Owner desativou Hiro para {phone} via IsFromMe")
            return JSONResponse({"status": "deactivated_by_owner", "phone": phone})

        return JSONResponse({"status": "skipped", "reason": "outbound"})

    phone = parsed["phone"]
    contact_name = parsed["contact_name"]
    text = parsed["text"]
    content_type = parsed["content_type"]

    logger.info(f"Mensagem recebida: phone={phone} tipo={content_type} msg={text[:50]}...")

    # ─── KEYWORD CHECK ─────────────────────────────────────
    text_lower = text.strip().lower()

    # Check activation keyword
    if text_lower == settings.keyword_activate.lower():
        activate(phone)
        try:
            await send_text(
                phone,
                "Oi! Eu sou o Hiro, assistente do Sushi da Hora 🍣\n\n"
                "Posso te ajudar com informações sobre nossas 5 unidades em Fortaleza, "
                "cardápio, horários, formas de pagamento e muito mais!\n\n"
                "Como posso te ajudar? 😊"
            )
        except Exception as e:
            logger.error(f"Erro ao enviar saudação: {e}")
        return JSONResponse({"status": "activated", "phone": phone})

    # Check deactivation keyword
    if text_lower == settings.keyword_deactivate.lower():
        deactivate(phone)
        try:
            await send_text(
                phone,
                "Atendimento do Hiro encerrado. Obrigado! 🍣\n"
                "Se precisar de novo, é só digitar #hiro"
            )
        except Exception as e:
            logger.error(f"Erro ao enviar despedida: {e}")
        return JSONResponse({"status": "deactivated", "phone": phone})

    # If bot is not active for this phone, ignore
    if not is_active(phone):
        logger.info(f"Bot inativo para {phone}, ignorando mensagem")
        return JSONResponse({"status": "skipped", "reason": "bot not active for this phone"})

    # ─── MEDIA PREPROCESSING ──────────────────────────────
    if content_type == "audio" and parsed.get("audio_base64"):
        try:
            text = await transcribe_audio(
                parsed["audio_base64"], parsed.get("audio_mimetype", "audio/ogg")
            )
            logger.info(f"Audio transcrito: {text[:80]}...")
        except Exception as e:
            logger.error(f"Erro ao transcrever audio: {e}")
            text = "[Audio recebido mas nao transcrito]"

    elif content_type == "image" and parsed.get("image_url"):
        try:
            image_desc = await analyze_image(parsed["image_url"])
            text = f"[IMAGEM] {image_desc}" if not text else f"{text} | [IMAGEM] {image_desc}"
            logger.info(f"Imagem analisada: {text[:80]}...")
        except Exception as e:
            logger.error(f"Erro ao analisar imagem: {e}")
            text = text or "[Imagem recebida]"

    if not text:
        return JSONResponse({"status": "skipped", "reason": "no text content"})

    # ─── RUN LANGGRAPH AGENT ──────────────────────────────
    try:
        result = await run_agent(
            phone=phone,
            contact_name=contact_name,
            text=text,
        )
        logger.info(f"Agente concluiu para {phone}: {result[:80]}...")
        return JSONResponse({"status": "processed", "phone": phone})
    except Exception as e:
        logger.error(f"Erro no agente: {e}", exc_info=True)
        try:
            await send_text(
                phone,
                "Desculpe, tive um problema técnico. Tente novamente em instantes! 🙏",
            )
        except Exception:
            pass
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=500)


@app.post("/webhook/test")
async def test_webhook(request: Request):
    """Test endpoint that simulates a message without Stevo."""
    payload = await request.json()
    phone = payload.get("phone", "5500000000000")
    message = payload.get("message", "Oi")
    contact_name = payload.get("name", "Teste")

    # Auto-activate for test
    activate(phone)

    try:
        result = await run_agent(
            phone=phone,
            contact_name=contact_name,
            text=message,
        )
        return JSONResponse({"result": result})
    except Exception as e:
        logger.error(f"Erro no teste: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)


# ─── ACTIVATE/DEACTIVATE VIA API ──────────────────────────

@app.post("/bot/activate/{phone}")
async def activate_bot(phone: str):
    """Activate bot for a phone number via API."""
    activate(phone)
    return JSONResponse({"status": "activated", "phone": phone})


@app.post("/bot/deactivate/{phone}")
async def deactivate_bot(phone: str):
    """Deactivate bot for a phone number via API."""
    deactivate(phone)
    return JSONResponse({"status": "deactivated", "phone": phone})


# ─── LIVE CHAT API (for presentation page) ─────────────────

@app.post("/api/chat")
async def api_chat(request: Request):
    """Live chat endpoint for the HTML presentation page.

    Runs the agent in dry-run mode, captures messages instead of
    sending them via WhatsApp. Returns captured messages as JSON.
    """
    payload = await request.json()
    message = payload.get("message", "").strip()
    name = payload.get("name", "Visitante")

    if not message:
        return JSONResponse({"messages": []})

    if not settings.openai_api_key and not settings.anthropic_api_key:
        return JSONResponse(
            {"error": "No LLM API key configured"},
            status_code=503,
        )

    # Capture all messages the agent sends via enviar_mensagem
    captured: list[str] = []

    async def fake_send(phone: str, text: str):
        captured.append(text)
        return {"status": "captured"}

    async def fake_send_media(phone: str, media_url: str, caption: str = "", media_type: str = "image"):
        captured.append(f"[IMAGEM: {media_url}]")
        if caption:
            captured.append(caption)
        return {"status": "captured"}

    try:
        import src.agent.tools as _tools
        _tools._skip_delays = True
        try:
            with patch("src.integrations.stevo.send_text", new=fake_send), \
                 patch("src.integrations.stevo.send_media", new=fake_send_media):
                result = await run_agent(
                    phone="5500000000000",
                    contact_name=name,
                    text=message,
                )
        finally:
            _tools._skip_delays = False

        # Fallback: if agent responded directly without calling enviar_mensagem
        if not captured and result and result not in ("Mensagem processada.", "Timeout ao processar mensagem."):
            captured.append(result)

        return JSONResponse({"messages": captured})
    except Exception as e:
        logger.error(f"Erro no /api/chat: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
