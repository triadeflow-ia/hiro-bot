# Hiro Bot — Atendente IA do Sushi da Hora

## O que eh
Bot de atendimento WhatsApp para o Sushi da Hora (5 unidades em Fortaleza).
Baseado na arquitetura da MIA (Mwove Bot) — LangGraph ReAct + FastAPI + Stevo.
Modo DEMO com keyword activation (#hiro / #parar).

## Stack
- **Motor IA:** OpenAI GPT-4.1 (function calling / tool use)
- **Framework:** LangGraph ReAct Agent (create_react_agent)
- **API:** FastAPI + uvicorn
- **WhatsApp:** Stevo.chat SM v2 (smv2-3)
- **CRM:** GoHighLevel (Sushi da Hora subconta)
- **Deploy:** Railway (Docker)

## IDs
- GHL Location: `MuGDMOL7giKp788E0rRk`
- GHL Token: `pit-4332be68-31ca-42af-b2b3-2445232adb57`
- Stevo Server: `smv2-3.stevo.chat`
- Stevo Instance: `hiro`
- Stevo Instance ID: `c38c32a0-3d61-4c0d-aed2-b87b`
- Stevo API Key: `1773179077544bUGzaJrFL2yfqkUM`
- WhatsApp: 558584551176

## Como funciona (Demo Mode)
1. Alguem manda `#hiro` para o numero 558584551176
2. Bot ativa e responde como atendente do Sushi da Hora
3. Conversa normalmente — responde sobre unidades, cardapio, horarios, pagamento
4. Alguem manda `#parar` — bot desativa

## Estrutura
```
hiro-bot/
├── src/
│   ├── main.py              # FastAPI + webhook + keyword activation
│   ├── config.py            # Settings (env vars)
│   ├── agent/
│   │   ├── graph.py         # LangGraph ReAct agent
│   │   ├── tools.py         # 5 tools (enviar_msg, buscar, tags, transferir, nota)
│   │   ├── prompts.py       # System prompt Hiro (FAQ completa 5 unidades)
│   │   └── nodes.py         # Preprocessing (Whisper, Vision)
│   └── integrations/
│       ├── stevo.py         # Stevo WhatsApp client
│       └── ghl.py           # GHL CRM client
├── scripts/
│   └── setup-stevo-webhook.py  # Registrar webhook no Stevo
├── requirements.txt
├── Dockerfile
├── railway.toml
└── .env
```

## Endpoints
```
GET  /health              -> Status + sessoes ativas
GET  /sessions            -> Listar sessoes ativas
POST /webhook/stevo       -> Webhook Stevo (WhatsApp inbound)
POST /webhook/test        -> Teste sem Stevo
POST /bot/activate/{phone}   -> Ativar bot via API
POST /bot/deactivate/{phone} -> Desativar bot via API
```

## Comandos
```bash
pip install -r requirements.txt
python run.py                    # Local (porta 8000)

# Registrar webhook no Stevo (apos deploy)
python scripts/setup-stevo-webhook.py https://URL/webhook/stevo
```

## Estado (2026-03-10)
- [x] Projeto criado baseado na MIA
- [x] LangGraph ReAct Agent com 5 tools
- [x] Stevo integration (webhook + send)
- [x] GHL CRM integration (contacts, tags, notes, tasks)
- [x] Keyword activation (#hiro / #parar)
- [x] Preprocessamento media (Whisper, Vision)
- [x] Prompt Hiro completo (FAQ 5 unidades, fluxo atendimento)
- [ ] OPENAI_API_KEY — precisa setar no .env
- [ ] Deploy Railway
- [ ] Registrar webhook no Stevo
- [ ] Testar fluxo completo
- [ ] Proposta HTML criada: C:\tmp\sushi-da-hora-proposta.html

## Cliente
- **Empresa:** Sushi da Hora (5 unidades Fortaleza/CE)
- **Instagram:** @sushidahora (80K+ seguidores)
- **Horario:** 17h-23h
- **Pagamento:** Cartao, PIX, Dinheiro
