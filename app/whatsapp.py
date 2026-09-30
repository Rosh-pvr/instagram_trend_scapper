from __future__ import annotations

import logging
import os
from typing import Any

import requests

log = logging.getLogger(__name__)


def _chunks(text: str, limit: int = 4096) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    remaining = text
    while remaining:
        split_at = remaining.rfind("\n", 0, limit)
        if split_at < 1:
            split_at = limit
        chunks.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    return chunks


def send_whatsapp(text: str, dry_run: bool = False) -> list[dict[str, Any]]:
    token = os.getenv("WHATSAPP_ACCESS_TOKEN", "").strip()
    phone = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()
    recipient = os.getenv("WHATSAPP_RECIPIENT", "").strip()
    version = os.getenv("WHATSAPP_GRAPH_VERSION", "").strip()

    if dry_run:
        print("\n----- WHATSAPP DRY RUN -----\n")
        print(text)
        print("\n----- END DRY RUN -----\n")
        return []

    missing = [name for name, value in {
        "WHATSAPP_ACCESS_TOKEN": token,
        "WHATSAPP_PHONE_NUMBER_ID": phone,
        "WHATSAPP_RECIPIENT": recipient,
        "WHATSAPP_GRAPH_VERSION": version,
    }.items() if not value]
    if missing:
        raise RuntimeError("Missing WhatsApp settings: " + ", ".join(missing))

    url = f"https://graph.facebook.com/{version}/{phone}/messages"
    results = []
    for chunk in _chunks(text):
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient,
            "type": "text",
            "text": {"preview_url": True, "body": chunk},
        }
        r = requests.post(
            url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        if not r.ok:
            log.error("WhatsApp API error %s: %s", r.status_code, r.text[:1000])
        r.raise_for_status()
        results.append(r.json())
    return results
