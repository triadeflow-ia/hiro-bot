"""Stevo.chat WhatsApp API client (SM v2)."""

from __future__ import annotations

import logging

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


def _headers() -> dict:
    return {
        "apikey": settings.stevo_api_key,
        "Content-Type": "application/json",
    }


def _base_url() -> str:
    return settings.stevo_server_url.rstrip("/")


async def send_text(phone: str, message: str) -> dict:
    """Send a text message via Stevo WhatsApp API."""
    url = f"{_base_url()}/send/text"
    payload = {
        "number": phone,
        "text": message,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, headers=_headers(), json=payload)
        resp.raise_for_status()
        return resp.json()


async def send_media(
    phone: str, media_url: str, caption: str = "", media_type: str = "document"
) -> dict:
    """Send media (image/document/video) via Stevo SM v2."""
    url = f"{_base_url()}/send/media"
    if media_url.lower().endswith(".pdf"):
        media_type = "document"
    elif any(media_url.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp")):
        media_type = "image"
    elif any(media_url.lower().endswith(ext) for ext in (".mp4", ".mov")):
        media_type = "video"
    payload = {
        "number": phone,
        "type": media_type,
        "url": media_url,
        "caption": caption,
    }
    if media_type == "document":
        filename = media_url.split("/")[-1].split("?")[0]
        payload["fileName"] = filename
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, headers=_headers(), json=payload)
        resp.raise_for_status()
        return resp.json()


def parse_stevo_webhook(body: dict) -> dict | None:
    """Parse incoming Stevo webhook payload into normalized format."""
    event = body.get("event", "")
    if event != "Message":
        return None

    info = body.get("data", {}).get("Info", {})
    message = body.get("data", {}).get("Message", {})

    if info.get("IsFromMe"):
        chat = info.get("Chat", "")
        if any(x in chat for x in ["@g.us", "@broadcast", "@newsletter"]):
            return None
        phone = chat.replace("@s.whatsapp.net", "").replace("@c.us", "").replace("@lid", "")
        return {"phone": phone, "is_from_me": True}

    if info.get("IsGroup"):
        return None

    chat = info.get("Chat", "")
    if any(x in chat for x in ["@g.us", "@broadcast", "@newsletter"]):
        return None

    sender = info.get("Sender", "")
    if sender and "@lid" not in sender:
        phone = sender.replace("@s.whatsapp.net", "").replace("@c.us", "")
    else:
        phone = chat.replace("@s.whatsapp.net", "").replace("@c.us", "").replace("@lid", "")

    text = (
        message.get("conversation")
        or message.get("extendedTextMessage", {}).get("text")
        or ""
    )

    media_type = (info.get("MediaType") or "").lower()

    content_type = "text"
    if media_type in ("ptt", "audio") or message.get("audioMessage"):
        content_type = "audio"
    elif media_type == "image" or message.get("imageMessage"):
        content_type = "image"

    audio_b64 = None
    audio_mime = "audio/ogg; codecs=opus"
    if content_type == "audio":
        audio_msg = message.get("audioMessage", {})
        audio_b64 = audio_msg.get("base64")
        audio_mime = audio_msg.get("mimetype", audio_mime)

    image_url = None
    if content_type == "image":
        img_msg = message.get("imageMessage", {})
        image_url = img_msg.get("url")
        image_caption = img_msg.get("caption", "")
        if image_caption and not text:
            text = image_caption

    return {
        "phone": phone,
        "contact_name": (
            info.get("PushName")
            or (info.get("VerifiedName") or {}).get("Details", {}).get("verifiedName")
            or "Cliente"
        ),
        "text": text,
        "content_type": content_type,
        "audio_base64": audio_b64,
        "audio_mimetype": audio_mime,
        "image_url": image_url,
    }
