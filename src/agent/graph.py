"""LangGraph ReAct agent — Hiro (Sushi da Hora)."""

from __future__ import annotations

import logging

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from src.config import settings
from src.agent.tools import ALL_TOOLS
from src.agent.prompts import build_system_prompt

logger = logging.getLogger(__name__)

_agent = None


def get_agent():
    """Lazy-load the LangGraph ReAct agent."""
    global _agent
    if _agent is None:
        llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0.7,
            max_tokens=1024,
        )
        _agent = create_react_agent(
            model=llm,
            tools=ALL_TOOLS,
        )
    return _agent


async def run_agent(
    phone: str,
    contact_name: str,
    text: str,
) -> str:
    """Run the agent for an incoming message. Returns the last AI message."""
    import asyncio

    agent = get_agent()
    system_prompt = build_system_prompt(phone=phone, contact_name=contact_name)

    from langchain_core.messages import HumanMessage, SystemMessage

    all_messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=text),
    ]

    try:
        result = await asyncio.wait_for(
            agent.ainvoke({"messages": all_messages}),
            timeout=90,
        )
    except asyncio.TimeoutError:
        logger.error(f"Timeout ao processar mensagem de {phone}: {text[:50]}...")
        return "Timeout ao processar mensagem."
    except Exception as e:
        logger.error(f"Erro no agente para {phone}: {e}", exc_info=True)
        return f"Erro no agente: {e}"

    messages = result.get("messages", [])
    for msg in reversed(messages):
        if hasattr(msg, "content") and msg.content and not hasattr(msg, "tool_calls"):
            if not msg.content.startswith("{"):
                return msg.content

    return "Mensagem processada."
