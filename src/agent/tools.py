"""LangGraph tools — actions Hiro can take via Stevo and GHL."""

from __future__ import annotations

import asyncio
import logging
import random

from langchain_core.tools import tool

from src.integrations import stevo, ghl

logger = logging.getLogger(__name__)

_send_locks: dict[str, asyncio.Lock] = {}


def _get_lock(phone: str) -> asyncio.Lock:
    if phone not in _send_locks:
        _send_locks[phone] = asyncio.Lock()
    return _send_locks[phone]


@tool
async def enviar_mensagem(phone: str, message: str) -> str:
    """Envia uma mensagem de texto para o cliente via WhatsApp.
    As mensagens sao enviadas em sequencia com delay para parecer natural.

    Args:
        phone: Numero do cliente (ex: 558584551176)
        message: Texto da mensagem. Use formatacao WhatsApp: *negrito*, _italico_.
    """
    lock = _get_lock(phone)
    async with lock:
        try:
            char_count = len(message)
            base_delay = min(max(char_count / 50, 1.5), 3.5)
            jitter = random.uniform(0.5, 1.5)
            await asyncio.sleep(base_delay + jitter)

            await stevo.send_text(phone, message)
            logger.info(f"[HIRO→{phone}] {message}")
            return f"Mensagem enviada para {phone}."
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem para {phone}: {e}")
            return f"ERRO ao enviar mensagem: {e}"


@tool
async def buscar_contato(phone: str) -> str:
    """Busca informacoes do contato no CRM (GHL) pelo telefone.

    Args:
        phone: Numero do cliente (ex: 558584551176)
    """
    try:
        contact = await ghl.search_contact_by_phone(phone)
        if not contact:
            return "Contato NAO encontrado no CRM. Lead novo."
        tags = ", ".join(contact.get("tags", [])) or "nenhuma"
        name = f"{contact.get('firstName', '')} {contact.get('lastName', '')}".strip()
        return (
            f"Contato encontrado:\n"
            f"- ID: {contact.get('id')}\n"
            f"- Nome: {name or 'nao informado'}\n"
            f"- Email: {contact.get('email', 'nao informado')}\n"
            f"- Tags: {tags}\n"
            f"- Origem: {contact.get('source', 'desconhecida')}"
        )
    except Exception as e:
        logger.error(f"Erro ao buscar contato: {e}")
        return f"ERRO ao buscar contato: {e}"


@tool
async def adicionar_tags(contact_id: str, tags: list[str]) -> str:
    """Adiciona tags ao contato no CRM.

    Args:
        contact_id: ID do contato no GHL
        tags: Lista de tags (ex: ["interesse_delivery", "unidade_maraponga"])
    """
    try:
        await ghl.add_tags(contact_id, tags)
        return f"Tags adicionadas: {', '.join(tags)}"
    except Exception as e:
        logger.error(f"Erro ao adicionar tags: {e}")
        return f"ERRO ao adicionar tags: {e}"


@tool
async def transferir_humano(contact_id: str, motivo: str) -> str:
    """Transfere o atendimento para um humano. Cria task urgente no GHL.

    Args:
        contact_id: ID do contato no GHL
        motivo: Motivo da transferencia (ex: "reclamacao", "cliente pediu atendente")
    """
    try:
        await ghl.create_task(
            contact_id=contact_id,
            title="🚨 Lead para atendimento humano",
            body=f"Motivo: {motivo}. Atender com urgencia.",
        )
        await ghl.add_tags(contact_id, ["escalado_humano", "hiro_bot"])
        return f"Task criada para humano. Motivo: {motivo}"
    except Exception as e:
        logger.error(f"Erro no handoff: {e}")
        return f"ERRO ao transferir: {e}"


@tool
async def adicionar_nota(contact_id: str, nota: str) -> str:
    """Adiciona uma nota interna ao contato no CRM (nao visivel para o cliente).

    Args:
        contact_id: ID do contato no GHL
        nota: Texto da nota interna
    """
    try:
        await ghl.add_note(contact_id, nota)
        return "Nota adicionada ao contato."
    except Exception as e:
        logger.error(f"Erro ao adicionar nota: {e}")
        return f"ERRO ao adicionar nota: {e}"


ALL_TOOLS = [
    enviar_mensagem,
    buscar_contato,
    adicionar_tags,
    transferir_humano,
    adicionar_nota,
]
