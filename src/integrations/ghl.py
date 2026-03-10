"""GoHighLevel CRM API client — Sushi da Hora."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://services.leadconnectorhq.com"


def _headers(version: str = "2021-07-28") -> dict:
    return {
        "Authorization": f"Bearer {settings.ghl_api_token}",
        "Content-Type": "application/json",
        "Version": version,
    }


async def get_contact(contact_id: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{BASE_URL}/contacts/{contact_id}", headers=_headers())
        resp.raise_for_status()
        data = resp.json()
        return data.get("contact", data)


async def search_contact_by_phone(phone: str) -> dict | None:
    search_phone = f"+{phone}" if phone and not phone.startswith("+") else phone
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{BASE_URL}/contacts/",
            headers=_headers(),
            params={"locationId": settings.ghl_location_id, "query": search_phone, "limit": 1},
        )
        resp.raise_for_status()
        contacts = resp.json().get("contacts", [])
        return contacts[0] if contacts else None


async def create_contact(phone: str, first_name: str = "", last_name: str = "", source: str = "hiro_bot", tags: list[str] | None = None) -> dict:
    body: dict = {
        "locationId": settings.ghl_location_id,
        "phone": f"+{phone}" if not phone.startswith("+") else phone,
        "source": source,
    }
    if first_name:
        body["firstName"] = first_name
    if last_name:
        body["lastName"] = last_name
    if tags:
        body["tags"] = tags
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(f"{BASE_URL}/contacts/", headers=_headers(), json=body)
        resp.raise_for_status()
        return resp.json().get("contact", resp.json())


async def update_contact(contact_id: str, tags: list[str] | None = None, custom_fields: dict[str, str] | None = None) -> dict:
    body: dict = {}
    if tags is not None:
        body["tags"] = tags
    if custom_fields:
        body["customFields"] = [{"key": k, "field_value": v} for k, v in custom_fields.items()]
    if not body:
        return {}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.put(f"{BASE_URL}/contacts/{contact_id}", headers=_headers(), json=body)
        resp.raise_for_status()
        return resp.json()


async def add_tags(contact_id: str, new_tags: list[str]) -> dict:
    contact = await get_contact(contact_id)
    existing = contact.get("tags", [])
    merged = list(set(existing + new_tags))
    return await update_contact(contact_id, tags=merged)


async def remove_tags(contact_id: str, tags_to_remove: list[str]) -> dict:
    contact = await get_contact(contact_id)
    existing = contact.get("tags", [])
    filtered = [t for t in existing if t not in tags_to_remove]
    return await update_contact(contact_id, tags=filtered)


async def create_task(contact_id: str, title: str, body: str, due_date: str | None = None) -> dict:
    task_body: dict = {"title": title, "body": body, "completed": False}
    task_body["dueDate"] = due_date or (datetime.utcnow() + timedelta(hours=1)).isoformat()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(f"{BASE_URL}/contacts/{contact_id}/tasks", headers=_headers(), json=task_body)
        resp.raise_for_status()
        return resp.json()


async def add_note(contact_id: str, body: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(f"{BASE_URL}/contacts/{contact_id}/notes", headers=_headers(), json={"body": body})
        resp.raise_for_status()
        return resp.json()
