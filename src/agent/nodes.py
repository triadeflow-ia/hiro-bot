"""Audio/image preprocessing utilities."""

from __future__ import annotations

import base64
import logging

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


async def transcribe_audio(audio_base64: str, mimetype: str = "audio/ogg") -> str:
    """Transcribe audio using OpenAI Whisper API."""
    audio_bytes = base64.b64decode(audio_base64)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            files={"file": ("audio.ogg", audio_bytes, mimetype)},
            data={"model": "whisper-1", "language": "pt"},
        )
        resp.raise_for_status()
        return resp.json().get("text", "[Audio nao transcrito]")


async def analyze_image(image_url: str) -> str:
    """Analyze image using GPT-4o Vision."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o",
                "max_tokens": 512,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Analise esta imagem enviada por um cliente do Sushi da Hora (restaurante japones em Fortaleza). Descreva o conteudo relevante em portugues.",
                            },
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    }
                ],
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "Imagem nao identificada")
