"""Configuration (env vars)."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1"

    # Anthropic (Claude)
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5-20251001"

    # GHL CRM
    ghl_api_token: str = ""
    ghl_location_id: str = ""

    # Stevo WhatsApp
    stevo_server_url: str = "https://smv2-3.stevo.chat"
    stevo_api_key: str = ""
    stevo_instance_name: str = "hiro"

    # Demo mode
    keyword_activate: str = "#hiro"
    keyword_deactivate: str = "#parar"

    # App
    port: int = 8000

    # Promo images
    promo_base_url: str = "https://hiro-bot-production.up.railway.app/static/promos"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
