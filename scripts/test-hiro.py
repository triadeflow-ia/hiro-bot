"""
Hiro Bot - QA Automatizado com IA
Simula centenas de clientes, avalia respostas, gera relatório e sugere melhorias.

Uso:
    python scripts/test-hiro.py                    # Roda todos os testes
    python scripts/test-hiro.py --category pedido  # Só uma categoria
    python scripts/test-hiro.py --fix              # Roda + aplica sugestões no prompt
    python scripts/test-hiro.py --fast             # Roda só 3 por categoria (rápido)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
import argparse
from dataclasses import dataclass, field
from datetime import datetime
from unittest.mock import AsyncMock, patch

# Fix Windows console encoding for emojis
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openai import AsyncOpenAI

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("test-hiro")


# ─── TEST SCENARIOS ──────────────────────────────────────────

@dataclass
class Scenario:
    id: str
    category: str
    message: str
    expected_behavior: str
    expected_tools: list[str] = field(default_factory=list)
    red_flags: list[str] = field(default_factory=list)
    contact_name: str = ""


SCENARIOS: list[Scenario] = [
    # ═══ SAUDAÇÃO / PRIMEIRO CONTATO ═══
    Scenario(
        id="greet-01", category="saudacao", contact_name="Lucas",
        message="Oi",
        expected_behavior="Se apresentar como Hiro, perguntar como pode ajudar",
        expected_tools=["enviar_mensagem"],
        red_flags=["transferir_humano", "inventar preço", "linguagem robótica"],
    ),
    Scenario(
        id="greet-02", category="saudacao",
        message="boa noite",
        expected_behavior="Responder a saudação de forma simpática, se apresentar",
        expected_tools=["enviar_mensagem"],
    ),
    Scenario(
        id="greet-03", category="saudacao", contact_name="Maria",
        message="eae",
        expected_behavior="Responder informal, se apresentar, perguntar como ajudar",
        expected_tools=["enviar_mensagem"],
    ),
    Scenario(
        id="greet-04", category="saudacao",
        message="olá tudo bem?",
        expected_behavior="Responder de forma amigável sem ser meloso",
        expected_tools=["enviar_mensagem"],
        red_flags=["Olá! Que ótimo", "senhor", "senhora"],
    ),
    Scenario(
        id="greet-05", category="saudacao", contact_name="João",
        message="🤙",
        expected_behavior="Entender como saudação, se apresentar",
        expected_tools=["enviar_mensagem"],
    ),

    # ═══ FAZER PEDIDO ═══
    Scenario(
        id="pedido-01", category="fazer_pedido",
        message="quero pedir sushi",
        expected_behavior="Perguntar qual unidade antes de tudo",
        expected_tools=["enviar_mensagem"],
        red_flags=["mandar cardápio sem perguntar unidade", "inventar preço"],
    ),
    Scenario(
        id="pedido-02", category="fazer_pedido",
        message="quero fazer um pedido pra Maraponga",
        expected_behavior="Mandar link do cardápio + WhatsApp da Maraponga",
        expected_tools=["enviar_mensagem"],
        red_flags=["mandar link de outra unidade"],
    ),
    Scenario(
        id="pedido-03", category="fazer_pedido",
        message="como faço pra pedir?",
        expected_behavior="Explicar que precisa da unidade, perguntar qual",
        expected_tools=["enviar_mensagem"],
    ),
    Scenario(
        id="pedido-04", category="fazer_pedido",
        message="manda o cardapio ai",
        expected_behavior="Perguntar qual unidade antes de mandar cardápio",
        expected_tools=["enviar_mensagem"],
        red_flags=["mandar cardápio genérico sem perguntar unidade"],
    ),
    Scenario(
        id="pedido-05", category="fazer_pedido",
        message="quero sushi na messejana",
        expected_behavior="Mandar link do cardápio + WhatsApp de Messejana",
        expected_tools=["enviar_mensagem"],
    ),
    Scenario(
        id="pedido-06", category="fazer_pedido",
        message="vcs entregam no barra do ceara?",
        expected_behavior="Confirmar que tem unidade na Barra do Ceará, mandar link",
        expected_tools=["enviar_mensagem"],
    ),
    Scenario(
        id="pedido-07", category="fazer_pedido",
        message="quero um combo de 40 peças quanto custa",
        expected_behavior="NÃO inventar preço, direcionar ao cardápio digital, perguntar unidade",
        expected_tools=["enviar_mensagem"],
        red_flags=["inventar preço", "R$", "reais", "custa"],
    ),
    Scenario(
        id="pedido-08", category="fazer_pedido",
        message="qual o preço do temaki",
        expected_behavior="NÃO inventar preço, direcionar ao cardápio",
        expected_tools=["enviar_mensagem"],
        red_flags=["R$", "reais", "custa", "preço é"],
    ),

    # ═══ CONSULTA DE PEDIDO (FLUXO PRINCIPAL) ═══
    Scenario(
        id="status-01", category="consulta_pedido",
        message="cadê meu pedido?",
        expected_behavior="Consultar AUTOMATICAMENTE pelo telefone, informar status",
        expected_tools=["consultar_pedido_por_telefone", "enviar_mensagem"],
        red_flags=["transferir_humano sem consultar", "pedir número do pedido antes de consultar por telefone"],
    ),
    Scenario(
        id="status-02", category="consulta_pedido",
        message="meu pedido ta demorando",
        expected_behavior="Consultar pelo telefone, informar status e previsão, tranquilizar",
        expected_tools=["consultar_pedido_por_telefone", "enviar_mensagem"],
        red_flags=["transferir_humano sem consultar"],
    ),
    Scenario(
        id="status-03", category="consulta_pedido",
        message="onde ta minha comida??",
        expected_behavior="Consultar pelo telefone automaticamente, dar status",
        expected_tools=["consultar_pedido_por_telefone", "enviar_mensagem"],
        red_flags=["transferir_humano sem consultar"],
    ),
    Scenario(
        id="status-04", category="consulta_pedido",
        message="quero saber do pedido 4522",
        expected_behavior="Consultar pedido #4522, informar que saiu para entrega com Carlos",
        expected_tools=["consultar_pedido", "enviar_mensagem"],
    ),
    Scenario(
        id="status-05", category="consulta_pedido",
        message="meu pedido #4525 o que aconteceu?",
        expected_behavior="Consultar pedido #4525, informar que foi cancelado e o motivo",
        expected_tools=["consultar_pedido", "enviar_mensagem"],
    ),
    Scenario(
        id="status-06", category="consulta_pedido",
        message="ja saiu meu pedido?",
        expected_behavior="Consultar por telefone automaticamente, informar status",
        expected_tools=["consultar_pedido_por_telefone", "enviar_mensagem"],
        red_flags=["transferir_humano"],
    ),
    Scenario(
        id="status-07", category="consulta_pedido",
        message="to esperando faz 1 hora ja",
        expected_behavior="Consultar por telefone, dar status e previsão, pedir desculpa pela demora",
        expected_tools=["consultar_pedido_por_telefone", "enviar_mensagem"],
        red_flags=["transferir_humano sem consultar primeiro"],
    ),
    Scenario(
        id="status-08", category="consulta_pedido",
        message="o entregador ja saiu?",
        expected_behavior="Consultar por telefone, informar status do entregador",
        expected_tools=["consultar_pedido_por_telefone", "enviar_mensagem"],
    ),
    Scenario(
        id="status-09", category="consulta_pedido",
        message="quero rastrear meu pedido",
        expected_behavior="Consultar por telefone automaticamente",
        expected_tools=["consultar_pedido_por_telefone", "enviar_mensagem"],
    ),
    Scenario(
        id="status-10", category="consulta_pedido",
        message="pedido 9999",
        expected_behavior="Consultar pedido #9999, informar que não encontrou, pedir nome completo e confirmar número",
        expected_tools=["consultar_pedido", "enviar_mensagem"],
    ),

    # ═══ DÚVIDAS GERAIS ═══
    Scenario(
        id="duvida-01", category="duvidas",
        message="que horas vcs abrem?",
        expected_behavior="Informar horário: 17h às 23h",
        expected_tools=["enviar_mensagem"],
    ),
    Scenario(
        id="duvida-02", category="duvidas",
        message="aceitam cartão?",
        expected_behavior="Informar: cartão, PIX e dinheiro",
        expected_tools=["enviar_mensagem"],
    ),
    Scenario(
        id="duvida-03", category="duvidas",
        message="vcs aceitam pix?",
        expected_behavior="Confirmar que aceita PIX, mencionar outras formas",
        expected_tools=["enviar_mensagem"],
    ),
    Scenario(
        id="duvida-04", category="duvidas",
        message="fazem entrega?",
        expected_behavior="Confirmar delivery em todas as 5 unidades",
        expected_tools=["enviar_mensagem"],
    ),
    Scenario(
        id="duvida-05", category="duvidas",
        message="quanto tempo demora a entrega?",
        expected_behavior="Dizer que varia pela região, aparece no app ao pedir",
        expected_tools=["enviar_mensagem"],
        red_flags=["inventar tempo exato"],
    ),
    Scenario(
        id="duvida-06", category="duvidas",
        message="vcs fazem encomenda pra festa?",
        expected_behavior="Confirmar que fazem, direcionar ao WhatsApp da unidade",
        expected_tools=["enviar_mensagem"],
    ),
    Scenario(
        id="duvida-07", category="duvidas",
        message="tem opção vegetariana?",
        expected_behavior="Confirmar que tem, mencionar hot rolls de legumes, temakis",
        expected_tools=["enviar_mensagem"],
    ),
    Scenario(
        id="duvida-08", category="duvidas",
        message="posso comer no local?",
        expected_behavior="Dizer que algumas unidades têm salão, perguntar qual",
        expected_tools=["enviar_mensagem"],
    ),
    Scenario(
        id="duvida-09", category="duvidas",
        message="tem promoção hj?",
        expected_behavior="Dizer que promoções variam, direcionar ao Instagram @sushidahora",
        expected_tools=["enviar_mensagem"],
        red_flags=["inventar promoção"],
    ),
    Scenario(
        id="duvida-10", category="duvidas",
        message="vcs abrem domingo?",
        expected_behavior="Informar horário 17h-23h, mencionar que feriados podem variar",
        expected_tools=["enviar_mensagem"],
    ),

    # ═══ UNIDADES / LOCALIZAÇÃO ═══
    Scenario(
        id="unidade-01", category="unidades",
        message="quais unidades vcs tem?",
        expected_behavior="Listar as 5: Barra do Ceará, Parquelândia, Maraponga, Maracanaú, Messejana",
        expected_tools=["enviar_mensagem"],
    ),
    Scenario(
        id="unidade-02", category="unidades",
        message="tem sushi da hora em maracanau?",
        expected_behavior="Confirmar que tem unidade em Maracanaú",
        expected_tools=["enviar_mensagem"],
    ),
    Scenario(
        id="unidade-03", category="unidades",
        message="qual o endereço da parquelandia?",
        expected_behavior="Informar: Rua Professor Anacleto, 148 - Parquelândia",
        expected_tools=["enviar_mensagem"],
    ),
    Scenario(
        id="unidade-04", category="unidades",
        message="tem no aldeota?",
        expected_behavior="Informar que não tem unidade no Aldeota, listar as 5 disponíveis",
        expected_tools=["enviar_mensagem"],
        red_flags=["inventar unidade no Aldeota"],
    ),
    Scenario(
        id="unidade-05", category="unidades",
        message="qual unidade mais perto do centro?",
        expected_behavior="Sugerir Parquelândia como mais próxima do centro",
        expected_tools=["enviar_mensagem"],
    ),
    Scenario(
        id="unidade-06", category="unidades",
        message="whatsapp da maraponga",
        expected_behavior="Informar (85) 98554-8493",
        expected_tools=["enviar_mensagem"],
    ),

    # ═══ RECLAMAÇÕES ═══
    Scenario(
        id="reclama-01", category="reclamacao",
        message="meu pedido veio errado",
        expected_behavior="Demonstrar empatia, pedir desculpas, transferir para humano",
        expected_tools=["transferir_humano", "enviar_mensagem"],
    ),
    Scenario(
        id="reclama-02", category="reclamacao",
        message="a comida chegou fria e toda bagunçada",
        expected_behavior="Pedir desculpas, demonstrar empatia, transferir para humano",
        expected_tools=["transferir_humano", "enviar_mensagem"],
    ),
    Scenario(
        id="reclama-03", category="reclamacao",
        message="to muito insatisfeito com vcs, nunca mais peço",
        expected_behavior="Demonstrar empatia, pedir desculpas, transferir para humano",
        expected_tools=["transferir_humano", "enviar_mensagem"],
    ),
    Scenario(
        id="reclama-04", category="reclamacao",
        message="o sushi veio com gosto estranho, tô passando mal",
        expected_behavior="Empatia urgente, transferir para humano IMEDIATO",
        expected_tools=["transferir_humano", "enviar_mensagem"],
    ),
    Scenario(
        id="reclama-05", category="reclamacao",
        message="faltou item no meu pedido",
        expected_behavior="Pedir desculpas, transferir para humano resolver",
        expected_tools=["transferir_humano", "enviar_mensagem"],
    ),

    # ═══ PEDIR HUMANO ═══
    Scenario(
        id="humano-01", category="transferir",
        message="quero falar com um atendente",
        expected_behavior="Transferir IMEDIATAMENTE sem fazer perguntas",
        expected_tools=["transferir_humano", "enviar_mensagem"],
    ),
    Scenario(
        id="humano-02", category="transferir",
        message="me passa pra um humano por favor",
        expected_behavior="Transferir imediatamente",
        expected_tools=["transferir_humano", "enviar_mensagem"],
    ),
    Scenario(
        id="humano-03", category="transferir",
        message="não quero falar com robô",
        expected_behavior="Transferir imediatamente sem insistir",
        expected_tools=["transferir_humano", "enviar_mensagem"],
        red_flags=["insistir em continuar", "tentar convencer a ficar"],
    ),

    # ═══ FORA DE ESCOPO ═══
    Scenario(
        id="fora-01", category="fora_escopo",
        message="qual a previsão do tempo pra hoje?",
        expected_behavior="Dizer que é especialista em sushi e não consegue ajudar com isso",
        expected_tools=["enviar_mensagem"],
        red_flags=["tentar responder sobre clima", "inventar previsão"],
    ),
    Scenario(
        id="fora-02", category="fora_escopo",
        message="me ajuda com meu trabalho de escola",
        expected_behavior="Recusar educadamente, dizer que é do Sushi da Hora",
        expected_tools=["enviar_mensagem"],
        red_flags=["tentar ajudar com dever de casa"],
    ),
    Scenario(
        id="fora-03", category="fora_escopo",
        message="quanto ta o dolar hj?",
        expected_behavior="Recusar, dizer que é do Sushi da Hora",
        expected_tools=["enviar_mensagem"],
        red_flags=["informar cotação"],
    ),
    Scenario(
        id="fora-04", category="fora_escopo",
        message="vc é uma ia né?",
        expected_behavior="Pode confirmar de forma leve, redirecionar para ajudar com sushi",
        expected_tools=["enviar_mensagem"],
    ),
    Scenario(
        id="fora-05", category="fora_escopo",
        message="me conta uma piada",
        expected_behavior="Recusar educadamente ou fazer piada rápida sobre sushi, redirecionar",
        expected_tools=["enviar_mensagem"],
    ),

    # ═══ EDGE CASES - TYPOS, GÍRIAS, MENSAGENS CURTAS ═══
    Scenario(
        id="edge-01", category="edge_cases",
        message="cardapio",
        expected_behavior="Perguntar qual unidade",
        expected_tools=["enviar_mensagem"],
    ),
    Scenario(
        id="edge-02", category="edge_cases",
        message="???",
        expected_behavior="Perguntar como pode ajudar",
        expected_tools=["enviar_mensagem"],
    ),
    Scenario(
        id="edge-03", category="edge_cases",
        message="suhsi",
        expected_behavior="Entender como 'sushi', responder normalmente",
        expected_tools=["enviar_mensagem"],
    ),
    Scenario(
        id="edge-04", category="edge_cases",
        message="oiiii td bm?? quero pedirrr",
        expected_behavior="Entender a intenção, perguntar qual unidade",
        expected_tools=["enviar_mensagem"],
    ),
    Scenario(
        id="edge-05", category="edge_cases",
        message="",
        expected_behavior="Perguntar como pode ajudar ou ignorar graciosamente",
        expected_tools=["enviar_mensagem"],
    ),
    Scenario(
        id="edge-06", category="edge_cases",
        message="kkkkkk",
        expected_behavior="Responder de forma leve, perguntar se precisa de algo",
        expected_tools=["enviar_mensagem"],
    ),
    Scenario(
        id="edge-07", category="edge_cases",
        message="oi boa noite gostaria de saber se vocês fazem entrega na região do mondubim",
        expected_behavior="Listar as 5 unidades, perguntar qual fica mais perto",
        expected_tools=["enviar_mensagem"],
        red_flags=["inventar área de entrega", "confirmar Mondubim sem ter certeza"],
    ),
    Scenario(
        id="edge-08", category="edge_cases", contact_name="Ana",
        message="oi Ana aqui",
        expected_behavior="Chamar pelo nome (Ana), se apresentar",
        expected_tools=["enviar_mensagem"],
    ),

    # ═══ FLUXO COMPLETO - MULTI-TURN SIMULATED ═══
    Scenario(
        id="flow-01", category="fluxo",
        message="oi quero saber sobre meu pedido, ta demorando muito",
        expected_behavior="Consultar por telefone, informar status, se em preparo tranquilizar com previsão",
        expected_tools=["consultar_pedido_por_telefone", "enviar_mensagem"],
        red_flags=["transferir_humano sem consultar pedido"],
    ),
    Scenario(
        id="flow-02", category="fluxo",
        message="boa noite, quero pedir sushi pra entregar no maracanau",
        expected_behavior="Já tem a unidade (Maracanaú), mandar cardápio + WhatsApp direto",
        expected_tools=["enviar_mensagem"],
    ),
    Scenario(
        id="flow-03", category="fluxo",
        message="quanto custa o combo família e qual horario vcs fecham?",
        expected_behavior="NÃO inventar preço, direcionar ao cardápio, informar horário 17h-23h",
        expected_tools=["enviar_mensagem"],
        red_flags=["inventar preço do combo"],
    ),
    Scenario(
        id="flow-04", category="fluxo",
        message="meu pedido 4521 ta pronto? e vcs aceitam pix?",
        expected_behavior="Consultar pedido #4521, informar status em preparo, confirmar PIX",
        expected_tools=["consultar_pedido", "enviar_mensagem"],
    ),

    # ═══ TOM / PERSONALIDADE ═══
    Scenario(
        id="tom-01", category="tom",
        message="oi",
        expected_behavior="Responder de forma curta, informal, sem ser meloso. Sem 'Olá! Que ótimo!'",
        expected_tools=["enviar_mensagem"],
        red_flags=["Olá!", "Que ótimo", "É um prazer", "senhor", "senhora", "Como posso ajudá-lo(a)"],
    ),
    Scenario(
        id="tom-02", category="tom", contact_name="Pedro",
        message="eae mano",
        expected_behavior="Responder no mesmo tom informal, usar nome Pedro se possível",
        expected_tools=["enviar_mensagem"],
        red_flags=["linguagem formal demais", "senhor Pedro"],
    ),
    Scenario(
        id="tom-03", category="tom",
        message="obrigado pela ajuda!",
        expected_behavior="Agradecer de volta de forma natural e breve",
        expected_tools=["enviar_mensagem"],
        red_flags=["resposta longa demais", "Foi um prazer imenso atendê-lo"],
    ),
]


# ─── TEST RUNNER ─────────────────────────────────────────────

@dataclass
class TestResult:
    scenario: Scenario
    messages_sent: list[str]
    tools_called: list[str]
    raw_result: str
    # Evaluation
    accuracy: int = 0        # 0-10
    tone: int = 0            # 0-10
    brevity: int = 0         # 0-10
    tool_usage: int = 0      # 0-10
    rule_compliance: int = 0 # 0-10
    red_flag_violations: list[str] = field(default_factory=list)
    evaluation_notes: str = ""
    passed: bool = False


async def run_single_test(scenario: Scenario) -> TestResult:
    """Run a single test scenario against the agent."""
    captured_messages: list[str] = []
    tools_called: list[str] = []

    # Mock stevo.send_text to capture messages
    async def fake_send_text(phone: str, message: str):
        captured_messages.append(message)

    # Mock GHL calls
    async def fake_search_contact(phone: str):
        return {"id": "test-contact-id", "firstName": scenario.contact_name or "Cliente", "tags": []}

    async def fake_add_tags(contact_id, tags):
        pass

    async def fake_create_task(**kwargs):
        pass

    async def fake_add_note(contact_id, nota):
        pass

    phone = "558500000000"
    text = scenario.message or "[mensagem vazia]"

    with patch("src.integrations.stevo.send_text", side_effect=fake_send_text), \
         patch("src.integrations.ghl.search_contact_by_phone", side_effect=fake_search_contact), \
         patch("src.integrations.ghl.add_tags", side_effect=fake_add_tags), \
         patch("src.integrations.ghl.create_task", side_effect=fake_create_task), \
         patch("src.integrations.ghl.add_note", side_effect=fake_add_note):

        from src.agent.graph import run_agent, get_agent

        # Force fresh agent for consistent results
        try:
            result = await run_agent(
                phone=phone,
                contact_name=scenario.contact_name or "",
                text=text,
            )
        except Exception as e:
            result = f"ERRO: {e}"

    # Extract tool calls from result context
    # We check captured messages and infer tools
    if captured_messages:
        tools_called.append("enviar_mensagem")

    # Check keywords in result to infer tool usage
    result_lower = result.lower() if result else ""
    if "pedido encontrado" in result_lower or "pedido #" in result_lower:
        if scenario.message and any(c.isdigit() for c in scenario.message):
            tools_called.append("consultar_pedido")
        else:
            tools_called.append("consultar_pedido_por_telefone")
    if "task criada" in result_lower or "transferir" in result_lower:
        tools_called.append("transferir_humano")

    return TestResult(
        scenario=scenario,
        messages_sent=captured_messages,
        tools_called=tools_called,
        raw_result=result,
    )


# ─── AI JUDGE ────────────────────────────────────────────────

JUDGE_PROMPT = """Você é um avaliador de qualidade de chatbots de atendimento.

Avalie a resposta do bot "Hiro" (atendente do Sushi da Hora, rede de sushi delivery em Fortaleza) para o cenário abaixo.

## Cenário
- **ID:** {scenario_id}
- **Categoria:** {category}
- **Mensagem do cliente:** "{message}"
- **Nome do cliente:** {contact_name}
- **Comportamento esperado:** {expected_behavior}
- **Tools esperadas:** {expected_tools}
- **Red flags (NÃO deve fazer):** {red_flags}

## Resposta do Bot
**Mensagens enviadas ao cliente:**
{messages_sent}

**Tools chamadas:** {tools_called}

**Resultado interno do agente:** {raw_result}

## Avalie (0-10 cada):

1. **accuracy** - Respondeu corretamente ao que foi perguntado? Seguiu o comportamento esperado?
2. **tone** - Tom informal, simpático, breve? Sem linguagem robótica? Sem "senhor/senhora"?
3. **brevity** - Mensagens curtas (max 3 frases por msg)? Não enrolou?
4. **tool_usage** - Usou as tools certas? Consultou pedido antes de transferir quando deveria?
5. **rule_compliance** - Seguiu as regras de ouro? (não inventou preço, perguntou unidade, etc)

Responda APENAS em JSON válido (sem markdown, sem ```):
{{
    "accuracy": 8,
    "tone": 9,
    "brevity": 7,
    "tool_usage": 10,
    "rule_compliance": 9,
    "red_flag_violations": ["lista de red flags violadas, se houver"],
    "notes": "observação breve sobre o que melhorar",
    "passed": true
}}

"passed" = true se TODOS os scores >= 6 E nenhuma red flag grave violada."""


async def judge_result(client: AsyncOpenAI, result: TestResult) -> TestResult:
    """Use GPT-4.1 to evaluate a test result."""
    messages_text = "\n".join(
        [f"  → \"{m}\"" for m in result.messages_sent]
    ) if result.messages_sent else "  (nenhuma mensagem enviada)"

    prompt = JUDGE_PROMPT.format(
        scenario_id=result.scenario.id,
        category=result.scenario.category,
        message=result.scenario.message,
        contact_name=result.scenario.contact_name or "(não informado)",
        expected_behavior=result.scenario.expected_behavior,
        expected_tools=", ".join(result.scenario.expected_tools) or "nenhuma específica",
        red_flags=", ".join(result.scenario.red_flags) or "nenhuma",
        messages_sent=messages_text,
        tools_called=", ".join(result.tools_called) or "nenhuma detectada",
        raw_result=result.raw_result[:500],
    )

    try:
        response = await client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=500,
        )
        content = response.choices[0].message.content.strip()

        # Parse JSON
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        evaluation = json.loads(content)
        result.accuracy = evaluation.get("accuracy", 0)
        result.tone = evaluation.get("tone", 0)
        result.brevity = evaluation.get("brevity", 0)
        result.tool_usage = evaluation.get("tool_usage", 0)
        result.rule_compliance = evaluation.get("rule_compliance", 0)
        result.red_flag_violations = evaluation.get("red_flag_violations", [])
        result.evaluation_notes = evaluation.get("notes", "")
        result.passed = evaluation.get("passed", False)

    except Exception as e:
        result.evaluation_notes = f"ERRO na avaliação: {e}"
        result.passed = False

    return result


# ─── REPORT GENERATOR ───────────────────────────────────────

def generate_report(results: list[TestResult], elapsed: float) -> str:
    """Generate a detailed test report."""
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    avg = lambda field: sum(getattr(r, field) for r in results) / total if total else 0

    # Category breakdown
    categories: dict[str, list[TestResult]] = {}
    for r in results:
        cat = r.scenario.category
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(r)

    lines = [
        "=" * 60,
        "  HIRO BOT - RELATÓRIO DE QA AUTOMATIZADO",
        "=" * 60,
        f"  Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"  Cenários: {total} | Passou: {passed} | Falhou: {failed}",
        f"  Taxa de sucesso: {passed/total*100:.0f}%",
        f"  Tempo total: {elapsed:.1f}s ({elapsed/total:.1f}s por teste)",
        "",
        "─" * 60,
        "  NOTAS MÉDIAS (0-10)",
        "─" * 60,
        f"  Precisão:     {'█' * int(avg('accuracy'))}{'░' * (10 - int(avg('accuracy')))} {avg('accuracy'):.1f}",
        f"  Tom:          {'█' * int(avg('tone'))}{'░' * (10 - int(avg('tone')))} {avg('tone'):.1f}",
        f"  Brevidade:    {'█' * int(avg('brevity'))}{'░' * (10 - int(avg('brevity')))} {avg('brevity'):.1f}",
        f"  Tool Usage:   {'█' * int(avg('tool_usage'))}{'░' * (10 - int(avg('tool_usage')))} {avg('tool_usage'):.1f}",
        f"  Regras:       {'█' * int(avg('rule_compliance'))}{'░' * (10 - int(avg('rule_compliance')))} {avg('rule_compliance'):.1f}",
        f"  GERAL:        {'█' * int((avg('accuracy')+avg('tone')+avg('brevity')+avg('tool_usage')+avg('rule_compliance'))/5)}{'░' * (10 - int((avg('accuracy')+avg('tone')+avg('brevity')+avg('tool_usage')+avg('rule_compliance'))/5))} {(avg('accuracy')+avg('tone')+avg('brevity')+avg('tool_usage')+avg('rule_compliance'))/5:.1f}",
        "",
    ]

    # Category breakdown
    lines.append("─" * 60)
    lines.append("  POR CATEGORIA")
    lines.append("─" * 60)
    for cat, cat_results in sorted(categories.items()):
        cat_passed = sum(1 for r in cat_results if r.passed)
        cat_total = len(cat_results)
        cat_avg = sum(
            (r.accuracy + r.tone + r.brevity + r.tool_usage + r.rule_compliance) / 5
            for r in cat_results
        ) / cat_total
        status = "✅" if cat_passed == cat_total else "⚠️" if cat_passed > 0 else "❌"
        lines.append(f"  {status} {cat:<20} {cat_passed}/{cat_total} passou  (média: {cat_avg:.1f})")

    # Failed tests detail
    failed_results = [r for r in results if not r.passed]
    if failed_results:
        lines.append("")
        lines.append("─" * 60)
        lines.append("  FALHAS DETALHADAS")
        lines.append("─" * 60)
        for r in failed_results:
            lines.append(f"\n  ❌ {r.scenario.id} [{r.scenario.category}]")
            lines.append(f"     Msg: \"{r.scenario.message}\"")
            lines.append(f"     Esperado: {r.scenario.expected_behavior}")
            scores = f"ACC={r.accuracy} TOM={r.tone} BRV={r.brevity} TOOL={r.tool_usage} REG={r.rule_compliance}"
            lines.append(f"     Scores: {scores}")
            if r.red_flag_violations:
                lines.append(f"     🚩 Red flags: {', '.join(r.red_flag_violations)}")
            if r.evaluation_notes:
                lines.append(f"     Nota: {r.evaluation_notes}")
            if r.messages_sent:
                for m in r.messages_sent[:3]:
                    lines.append(f"     Bot disse: \"{m[:80]}{'...' if len(m)>80 else ''}\"")

    # Red flags summary
    all_violations = []
    for r in results:
        for v in r.red_flag_violations:
            if v and v not in ["", "nenhuma"]:
                all_violations.append(f"{r.scenario.id}: {v}")
    if all_violations:
        lines.append("")
        lines.append("─" * 60)
        lines.append("  🚩 RED FLAGS ENCONTRADAS")
        lines.append("─" * 60)
        for v in all_violations:
            lines.append(f"  • {v}")

    # Suggestions
    lines.append("")
    lines.append("─" * 60)
    lines.append("  💡 SUGESTÕES DE MELHORIA")
    lines.append("─" * 60)

    # Collect unique notes from failed
    seen_notes = set()
    for r in results:
        if r.evaluation_notes and r.evaluation_notes not in seen_notes and not r.passed:
            seen_notes.add(r.evaluation_notes)
            lines.append(f"  • {r.evaluation_notes}")

    if not seen_notes:
        lines.append("  Nenhuma sugestão - tudo passou! 🎉")

    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)


# ─── MAIN ────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="Hiro Bot - QA Automatizado")
    parser.add_argument("--category", "-c", help="Testar só uma categoria")
    parser.add_argument("--fast", action="store_true", help="Modo rápido: 3 testes por categoria")
    parser.add_argument("--id", help="Rodar um cenário específico por ID")
    parser.add_argument("--no-judge", action="store_true", help="Pular avaliação por IA (só executa)")
    parser.add_argument("--output", "-o", help="Salvar relatório em arquivo")
    args = parser.parse_args()

    # Filter scenarios
    scenarios = SCENARIOS
    if args.id:
        scenarios = [s for s in scenarios if s.id == args.id]
        if not scenarios:
            print(f"❌ Cenário '{args.id}' não encontrado")
            return
    elif args.category:
        scenarios = [s for s in scenarios if s.category == args.category]
        if not scenarios:
            cats = sorted(set(s.category for s in SCENARIOS))
            print(f"❌ Categoria '{args.category}' não encontrada")
            print(f"   Categorias: {', '.join(cats)}")
            return

    if args.fast:
        # 3 per category
        by_cat: dict[str, list[Scenario]] = {}
        for s in scenarios:
            if s.category not in by_cat:
                by_cat[s.category] = []
            by_cat[s.category].append(s)
        scenarios = []
        for cat_scenarios in by_cat.values():
            scenarios.extend(cat_scenarios[:3])

    total = len(scenarios)
    cats = sorted(set(s.category for s in scenarios))
    print(f"\n🍣 HIRO QA - {total} cenários em {len(cats)} categorias")
    print(f"   Categorias: {', '.join(cats)}")
    print()

    # Check OpenAI key
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        from src.config import settings
        api_key = settings.openai_api_key
    if not api_key:
        print("❌ OPENAI_API_KEY não configurada")
        return

    client = AsyncOpenAI(api_key=api_key)

    # Run tests
    results: list[TestResult] = []
    start = time.time()

    for i, scenario in enumerate(scenarios, 1):
        status = f"[{i}/{total}]"
        print(f"  {status} {scenario.id:<12} \"{scenario.message[:40]}{'...' if len(scenario.message)>40 else ''}\"", end=" ", flush=True)

        try:
            result = await run_single_test(scenario)

            if not args.no_judge:
                result = await judge_result(client, result)
                icon = "✅" if result.passed else "❌"
                avg = (result.accuracy + result.tone + result.brevity + result.tool_usage + result.rule_compliance) / 5
                print(f"{icon} {avg:.1f}/10")
            else:
                msgs = len(result.messages_sent)
                print(f"📨 {msgs} msgs")

            results.append(result)

        except Exception as e:
            print(f"💥 ERRO: {e}")
            results.append(TestResult(
                scenario=scenario,
                messages_sent=[],
                tools_called=[],
                raw_result=f"ERRO: {e}",
            ))

    elapsed = time.time() - start

    # Generate report
    if not args.no_judge:
        report = generate_report(results, elapsed)
        print(f"\n{report}")

        # Save report
        output_path = args.output or f"scripts/qa-report-{datetime.now().strftime('%Y%m%d-%H%M')}.txt"
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\n📄 Relatório salvo em: {output_path}")
    else:
        print(f"\n✅ {total} testes executados em {elapsed:.1f}s (sem avaliação IA)")


if __name__ == "__main__":
    asyncio.run(main())
