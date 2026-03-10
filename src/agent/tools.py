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


# ─── SISTEMA DE PEDIDOS (SIMULADO P/ DEMO) ───────────────

# Pedidos fake realistas para demonstração
_PEDIDOS_SIMULADOS = {
    "4521": {
        "numero": "#4521",
        "status": "em_preparo",
        "unidade": "Maraponga",
        "itens": "1x Combo Sushi Premium (40 peças), 1x Yakisoba Frango, 2x Refrigerante",
        "valor": "R$ 142,90",
        "pagamento": "PIX",
        "previsao": "45 minutos",
        "horario_pedido": "19:32",
        "entregador": "João",
    },
    "4522": {
        "numero": "#4522",
        "status": "saiu_entrega",
        "unidade": "Parquelândia",
        "itens": "2x Temaki Salmão, 1x Hot Roll (10 peças), 1x Suco Natural",
        "valor": "R$ 89,50",
        "pagamento": "Cartão Crédito 3x",
        "previsao": "15 minutos",
        "horario_pedido": "19:15",
        "entregador": "Carlos",
    },
    "4523": {
        "numero": "#4523",
        "status": "entregue",
        "unidade": "Messejana",
        "itens": "1x Combo Família (60 peças), 1x Yakisoba Camarão",
        "valor": "R$ 198,00",
        "pagamento": "Dinheiro",
        "previsao": "Entregue às 18:45",
        "horario_pedido": "17:50",
        "entregador": "Pedro",
    },
    "4524": {
        "numero": "#4524",
        "status": "em_preparo",
        "unidade": "Barra do Ceará",
        "itens": "1x Sashimi Misto, 2x Hot Roll Filadélfia, 1x Edamame",
        "valor": "R$ 115,00",
        "pagamento": "PIX",
        "previsao": "35 minutos",
        "horario_pedido": "19:40",
        "entregador": "—",
    },
    "4525": {
        "numero": "#4525",
        "status": "cancelado",
        "unidade": "Maracanaú",
        "itens": "1x Combo Casal (30 peças)",
        "valor": "R$ 79,90 (estornado)",
        "pagamento": "Cartão Débito",
        "previsao": "—",
        "horario_pedido": "18:20",
        "entregador": "—",
        "motivo_cancelamento": "Cliente solicitou cancelamento antes do preparo",
    },
}

_STATUS_LABELS = {
    "em_preparo": "🔥 Em preparo na cozinha",
    "saiu_entrega": "🛵 Saiu para entrega",
    "entregue": "✅ Entregue",
    "cancelado": "❌ Cancelado",
    "aguardando": "⏳ Aguardando confirmação",
}


@tool
async def consultar_pedido(numero_pedido: str) -> str:
    """Consulta o status de um pedido no sistema. Use quando o cliente perguntar sobre seu pedido,
    status da entrega, ou onde esta o pedido dele.

    Args:
        numero_pedido: Numero do pedido (ex: "4521" ou "#4521"). Se o cliente nao souber o numero, use o telefone dele para buscar.
    """
    # Limpa o numero
    num = numero_pedido.strip().replace("#", "")

    pedido = _PEDIDOS_SIMULADOS.get(num)
    if not pedido:
        return (
            f"Pedido #{num} NAO encontrado no sistema. "
            "Pode ser que o numero esteja errado. "
            "Pergunte o numero correto ao cliente ou busque pelo telefone. "
            "Se nao conseguir localizar, transfira para um atendente humano."
        )

    status_label = _STATUS_LABELS.get(pedido["status"], pedido["status"])
    info = (
        f"PEDIDO ENCONTRADO:\n"
        f"- Número: {pedido['numero']}\n"
        f"- Status: {status_label}\n"
        f"- Unidade: {pedido['unidade']}\n"
        f"- Itens: {pedido['itens']}\n"
        f"- Valor: {pedido['valor']}\n"
        f"- Pagamento: {pedido['pagamento']}\n"
        f"- Previsão: {pedido['previsao']}\n"
        f"- Horário do pedido: {pedido['horario_pedido']}\n"
    )

    if pedido.get("entregador") and pedido["entregador"] != "—":
        info += f"- Entregador: {pedido['entregador']}\n"

    if pedido.get("motivo_cancelamento"):
        info += f"- Motivo cancelamento: {pedido['motivo_cancelamento']}\n"

    return info


@tool
async def consultar_pedido_por_telefone(phone: str) -> str:
    """Busca pedidos recentes de um cliente pelo numero de telefone.
    Use quando o cliente quer saber do pedido mas nao tem o numero do pedido.

    Args:
        phone: Numero de telefone do cliente (ex: 558599210061)
    """
    # Simulação: retorna um pedido "encontrado" para qualquer telefone
    # Em produção, isso consultaria o sistema real de pedidos
    pedido = _PEDIDOS_SIMULADOS["4521"]  # Sempre retorna o pedido em preparo
    status_label = _STATUS_LABELS.get(pedido["status"], pedido["status"])

    return (
        f"1 pedido encontrado para este telefone:\n\n"
        f"- Número: {pedido['numero']}\n"
        f"- Status: {status_label}\n"
        f"- Unidade: {pedido['unidade']}\n"
        f"- Itens: {pedido['itens']}\n"
        f"- Valor: {pedido['valor']}\n"
        f"- Previsão: {pedido['previsao']}\n"
    )


ALL_TOOLS = [
    enviar_mensagem,
    buscar_contato,
    adicionar_tags,
    consultar_pedido,
    consultar_pedido_por_telefone,
    transferir_humano,
    adicionar_nota,
]
