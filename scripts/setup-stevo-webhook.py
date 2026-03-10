"""Register webhook URL on Stevo instance for Hiro bot."""

import httpx
import sys

STEVO_SERVER = "https://smv2-3.stevo.chat"
STEVO_API_KEY = "1773179077544bUGzaJrFL2yfqkUM"
INSTANCE_NAME = "hiro"


def setup_webhook(webhook_url: str):
    """Register webhook on Stevo instance."""
    print(f"Registrando webhook: {webhook_url}")

    resp = httpx.put(
        f"{STEVO_SERVER}/webhook/set/{INSTANCE_NAME}",
        headers={
            "apikey": STEVO_API_KEY,
            "Content-Type": "application/json",
        },
        json={
            "webhook": {
                "url": webhook_url,
                "enabled": True,
                "events": ["Message"],
            }
        },
    )

    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")

    if resp.status_code == 200:
        print("✅ Webhook registrado com sucesso!")
    else:
        print("❌ Erro ao registrar webhook")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python setup-stevo-webhook.py <WEBHOOK_URL>")
        print("Ex:  python setup-stevo-webhook.py https://hiro-bot-production.up.railway.app/webhook/stevo")
        sys.exit(1)

    setup_webhook(sys.argv[1])
