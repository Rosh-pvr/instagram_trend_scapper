from __future__ import annotations

import logging
import os

import requests

from app.models import TrendItem

log = logging.getLogger(__name__)


def _fallback(items: list[TrendItem]) -> str:
    lines = ["🔥 DAILY TREND REPORT", "", "Top rising topics based on collected public/authorized signals:", ""]
    for i, t in enumerate(items, 1):
        meta = t.metadata or {}
        lines.append(f"{i}. {t.title}")
        lines.append(
            f"   Source: {t.source} | Score: {meta.get('score', 0):.2f} | "
            f"Velocity: {meta.get('velocity', 0):.2f}"
        )
        if t.keyword:
            lines.append(f"   Keyword: {t.keyword}")
        if t.url:
            lines.append(f"   {t.url}")
    return "\n".join(lines)


def _build_prompt(items: list[TrendItem]) -> str:
    rows = []
    for x in items:
        meta = x.metadata or {}
        rows.append(
            f"- title={x.title} | source={x.source} | score={meta.get('score', 0)} "
            f"| velocity={meta.get('velocity', 0)} | frequency={meta.get('frequency', 0)} "
            f"| engagement_signal={meta.get('engagement_signal', 0)} "
            f"| keyword={x.keyword} | url={x.url} | caption={meta.get('caption', '')}"
        )
    return "Trend data collected by Apify/Google Trends:\n" + "\n".join(rows)


def _call_openai_compatible(
    *,
    api_key: str,
    base_url: str,
    model: str,
    prompt: str,
) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "reasoning_effort": "low",
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a trend analyst for a WhatsApp digest. Use only the supplied evidence. "
                    "Do not invent engagement, causes, people, events, or rankings. "
                    "Explain trends in plain language and keep the report concise. "
                    "For each trend: state the topic, source, why the signal is notable based on score/velocity, "
                    "and include its link when available. End with 'Data note:' explaining that the scores are "
                    "heuristic signals from the configured collectors, not official Instagram rankings."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    # Google's docs recommend client identification for partner/library traffic.
    if "generativelanguage.googleapis.com" in base_url:
        headers["x-goog-api-client"] = "instagram-trend-whatsapp/4.0"

    response = requests.post(url, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    body = response.json()
    content = body["choices"][0]["message"]["content"]
    if not isinstance(content, str) or not content.strip():
        raise ValueError("AI response contained no text content")
    return content.strip()


def summarize(items: list[TrendItem]) -> str:
    if not items:
        return "No new trends found today."

    prompt = _build_prompt(items)

    # Gemini 3.8 Flash is the preferred provider.
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if gemini_key:
        base = os.getenv(
            "GEMINI_BASE_URL",
            "https://generativelanguage.googleapis.com/v1beta/openai/",
        ).strip()
        model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
        try:
            log.info("Generating trend digest with Gemini model %s", model)
            return _call_openai_compatible(
                api_key=gemini_key,
                base_url=base,
                model=model,
                prompt=prompt,
            )
        except Exception as exc:
            log.warning("Gemini summarization failed; trying legacy AI provider: %s", exc)

    # Backward-compatible generic OpenAI-compatible provider.
    key = os.getenv("AI_API_KEY", "").strip()
    if key:
        base = os.getenv("AI_BASE_URL", "https://api.openai.com/v1").strip()
        model = os.getenv("AI_MODEL", "gpt-4o-mini").strip()
        try:
            log.info("Generating trend digest with fallback AI model %s", model)
            return _call_openai_compatible(
                api_key=key,
                base_url=base,
                model=model,
                prompt=prompt,
            )
        except Exception as exc:
            log.warning("Fallback AI summarization failed; using deterministic report: %s", exc)

    return _fallback(items)
