"""LangGraph ReAct agent for Hiro (Sushi da Hora)."""

from __future__ import annotations

import logging
import time
from collections import defaultdict

from langgraph.prebuilt import create_react_agent

from src.config import settings
from src.agent.tools import ALL_TOOLS
from src.agent.prompts import build_system_prompt

logger = logging.getLogger(__name__)

_agents: dict[str, object] = {}

# ─── Conversation memory (in-memory, per phone) ─────────
_MAX_HISTORY = 20
_HISTORY_TTL = 3600  # 1 hour
_conversations: dict[str, dict] = defaultdict(lambda: {"messages": [], "last_active": 0})

# ─── Customer profile cache (in-memory, per phone) ──────
_PROFILE_TTL = 1800  # 30 min cache
_customer_profiles: dict[str, dict] = {}


def _get_history(phone: str):
    conv = _conversations[phone]
    now = time.time()
    if now - conv["last_active"] > _HISTORY_TTL:
        conv["messages"] = []
    conv["last_active"] = now
    return conv["messages"]


def _add_to_history(phone: str, role: str, content: str):
    from langchain_core.messages import HumanMessage, AIMessage
    history = _get_history(phone)
    if role == "human":
        history.append(HumanMessage(content=content))
    else:
        history.append(AIMessage(content=content))
    if len(history) > _MAX_HISTORY:
        _conversations[phone]["messages"] = history[-_MAX_HISTORY:]


async def _fetch_customer_profile(phone: str) -> dict | None:
    """Fetch customer profile from CRM with caching."""
    now = time.time()
    cached = _customer_profiles.get(phone)
    if cached and now - cached.get("_fetched_at", 0) < _PROFILE_TTL:
        return cached

    try:
        from src.integrations import ghl

        contact = await ghl.search_contact_by_phone(phone)
        if not contact:
            return None

        contact_id = contact.get("id", "")
        name = f"{contact.get('firstName', '')} {contact.get('lastName', '')}".strip()
        tags = contact.get("tags", [])
        email = contact.get("email", "")
        source = contact.get("source", "")
        date_added = contact.get("dateAdded", "")

        # Fetch notes for history/preferences
        notes_raw = []
        hiro_notes = []
        try:
            notes_raw = await ghl.get_notes(contact_id)
            # Filter for Hiro bot notes (preferences, patterns)
            for note in notes_raw[:10]:  # last 10 notes
                body = note.get("body", "")
                if body:
                    hiro_notes.append(body)
        except Exception as e:
            logger.warning(f"Erro ao buscar notas de {phone}: {e}")

        profile = {
            "contact_id": contact_id,
            "name": name,
            "tags": tags,
            "email": email,
            "source": source,
            "date_added": date_added,
            "notes": hiro_notes,
            "is_returning": bool(tags) or len(notes_raw) > 0,
            "_fetched_at": now,
        }

        # Detect patterns from tags
        profile["unidade_preferida"] = None
        profile["cliente_recorrente"] = False
        for tag in tags:
            if tag.startswith("unidade_"):
                profile["unidade_preferida"] = tag.replace("unidade_", "").replace("_", " ").title()
            if tag in ("cliente_recorrente", "cliente_vip", "hiro_bot"):
                profile["cliente_recorrente"] = True

        _customer_profiles[phone] = profile
        logger.info(f"Perfil carregado para {phone}: {name}, tags={tags}, returning={profile['is_returning']}")
        return profile

    except Exception as e:
        logger.warning(f"Erro ao buscar perfil de {phone}: {e}")
        return None


def _build_customer_context(profile: dict | None) -> str:
    """Build customer context string for the system prompt."""
    if not profile:
        return "\n## CONTEXTO DO CLIENTE\nCliente novo, nunca interagiu antes. Pergunte o nome e se apresente."

    parts = ["\n## CONTEXTO DO CLIENTE (do CRM)"]

    if profile.get("name"):
        parts.append(f"- Nome: {profile['name']}")
    if profile.get("contact_id"):
        parts.append(f"- ID CRM: {profile['contact_id']}")
    if profile.get("is_returning"):
        parts.append("- CLIENTE RECORRENTE! Trate com carinho extra, mostre que lembra dele(a).")
    if profile.get("cliente_recorrente"):
        parts.append("- É cliente VIP/recorrente. Demonstre que está feliz em atendê-lo(a) de novo!")
    if profile.get("unidade_preferida"):
        parts.append(f"- Unidade preferida: {profile['unidade_preferida']} (use essa como sugestão)")
    if profile.get("tags"):
        relevant_tags = [t for t in profile["tags"] if not t.startswith("_")]
        if relevant_tags:
            parts.append(f"- Tags: {', '.join(relevant_tags)}")
    if profile.get("date_added"):
        parts.append(f"- Cliente desde: {profile['date_added'][:10]}")

    # Add notes as preferences/history
    if profile.get("notes"):
        parts.append("- Histórico de interações:")
        for note in profile["notes"][:5]:  # last 5 notes
            # Truncate long notes
            short = note[:150] + "..." if len(note) > 150 else note
            parts.append(f"  • {short}")

    parts.append("")
    parts.append("USE estas informações para personalizar o atendimento:")
    parts.append("- Se é recorrente, diga algo como 'Que bom te ver de novo!' ou 'Sempre bom atender você!'")
    parts.append("- Se sabe a unidade preferida, sugira ela primeiro")
    parts.append("- Se tem histórico, faça referência sutil: 'Da Maraponga de novo?' ou 'O de sempre?'")
    parts.append("- NÃO repita dados internos (ID, tags) para o cliente")

    return "\n".join(parts)


def _get_llm(provider: str = "anthropic"):
    if provider == "anthropic" and settings.anthropic_api_key:
        from langchain_anthropic import ChatAnthropic
        logger.info(f"Usando Anthropic model={settings.anthropic_model}")
        return ChatAnthropic(
            model=settings.anthropic_model,
            api_key=settings.anthropic_api_key,
            temperature=0.7,
            max_tokens=1024,
        )
    if provider == "openai" and settings.openai_api_key:
        from langchain_openai import ChatOpenAI
        logger.info(f"Usando OpenAI model={settings.openai_model}")
        return ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0.7,
            max_tokens=1024,
        )
    return None


def _get_providers() -> list[str]:
    providers = []
    if settings.anthropic_api_key:
        providers.append("anthropic")
    if settings.openai_api_key:
        providers.append("openai")
    return providers


def get_agent(provider: str = "anthropic"):
    if provider not in _agents:
        llm = _get_llm(provider)
        if llm is None:
            return None
        _agents[provider] = create_react_agent(
            model=llm,
            tools=ALL_TOOLS,
        )
    return _agents[provider]


async def run_agent(
    phone: str,
    contact_name: str,
    text: str,
) -> str:
    """Run the agent with customer profile + conversation memory + provider fallback."""
    import asyncio
    from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

    providers = _get_providers()
    if not providers:
        raise RuntimeError("Nenhuma API key configurada (ANTHROPIC_API_KEY ou OPENAI_API_KEY)")

    # 1. Fetch customer profile from CRM (cached)
    profile = await _fetch_customer_profile(phone)

    # Use CRM name if contact_name is empty
    if profile and profile.get("name") and (not contact_name or contact_name == "Cliente"):
        contact_name = profile["name"]

    # 2. Build system prompt with customer context
    customer_context = _build_customer_context(profile)
    system_prompt = build_system_prompt(phone=phone, contact_name=contact_name) + customer_context

    # 3. Build messages with conversation history
    history = _get_history(phone)
    _add_to_history(phone, "human", text)

    all_messages = [
        SystemMessage(content=system_prompt),
        *history,
    ]

    for i, provider in enumerate(providers):
        agent = get_agent(provider)
        if agent is None:
            continue

        try:
            result = await asyncio.wait_for(
                agent.ainvoke({"messages": all_messages}),
                timeout=90,
            )

            messages = result.get("messages", [])

            # Check if agent already sent messages via enviar_mensagem tool
            sent_via_tool = any(
                getattr(msg, "name", None) == "enviar_mensagem"
                and "Mensagem enviada" in (msg.content or "")
                for msg in messages
                if hasattr(msg, "name")
            )

            ai_response = None
            for msg in reversed(messages):
                if isinstance(msg, AIMessage) and msg.content and not getattr(msg, "tool_calls", None):
                    if not msg.content.startswith("{"):
                        ai_response = msg.content
                        break

            if ai_response:
                _add_to_history(phone, "ai", ai_response)

                # If agent didn't send via tool, send the response now
                if not sent_via_tool:
                    try:
                        from src.integrations.stevo import send_text
                        await send_text(phone, ai_response)
                        logger.info(f"[FALLBACK SEND] {phone}: {ai_response[:80]}...")
                    except Exception as e:
                        logger.error(f"Erro no fallback send para {phone}: {e}")

                return ai_response

            return "Mensagem processada."

        except Exception as e:
            is_last = i == len(providers) - 1
            if is_last:
                logger.error(f"Todos os providers falharam para {phone}: {e}", exc_info=True)
                return f"Erro no agente: {e}"
            else:
                next_provider = providers[i + 1]
                logger.warning(f"{provider} falhou para {phone}: {e}, tentando {next_provider}...")
                continue

    return "Mensagem processada."
