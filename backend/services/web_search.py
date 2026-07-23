from __future__ import annotations

"""웹 검색 (DuckDuckGo) — DB에 없을 때 보조 자료 수집."""

import logging
import re
from html import unescape
from urllib.parse import quote_plus

import httpx

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ERAI-Chatbot/1.0)",
}


async def search_web(query: str, *, max_results: int = 5) -> str:
    """질의어로 웹 검색 후 요약 가능한 텍스트 블록 반환."""
    snippets: list[str] = []

    instant = await _duckduckgo_instant(query)
    if instant:
        snippets.append(instant)

    lite = await _duckduckgo_lite(query, max_results=max_results)
    snippets.extend(lite)

    if not snippets:
        return ""

    seen: set[str] = set()
    unique: list[str] = []
    for s in snippets:
        key = s.strip()[:120]
        if key and key not in seen:
            seen.add(key)
            unique.append(s.strip())

    return "\n\n".join(unique[:max_results])


async def _duckduckgo_instant(query: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=15.0, headers=_HEADERS) as client:
            response = await client.get(
                "https://api.duckduckgo.com/",
                params={
                    "q": query,
                    "format": "json",
                    "no_redirect": 1,
                    "no_html": 1,
                    "skip_disambig": 1,
                },
            )
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        logger.warning("DuckDuckGo instant search failed: %s", exc)
        return ""

    parts: list[str] = []
    abstract = (data.get("AbstractText") or "").strip()
    if abstract:
        heading = (data.get("Heading") or "").strip()
        parts.append(f"{heading}: {abstract}" if heading else abstract)

    for topic in data.get("RelatedTopics") or []:
        if isinstance(topic, dict):
            text = (topic.get("Text") or "").strip()
            if text:
                parts.append(text)
        elif isinstance(topic, list):
            for sub in topic:
                if isinstance(sub, dict):
                    text = (sub.get("Text") or "").strip()
                    if text:
                        parts.append(text)
        if len(parts) >= 3:
            break

    return "\n".join(parts[:3])


async def _duckduckgo_lite(query: str, *, max_results: int) -> list[str]:
    try:
        async with httpx.AsyncClient(timeout=20.0, headers=_HEADERS, follow_redirects=True) as client:
            response = await client.post(
                "https://lite.duckduckgo.com/lite/",
                data={"q": query},
            )
            response.raise_for_status()
            html = response.text
    except Exception as exc:
        logger.warning("DuckDuckGo lite search failed: %s", exc)
        return []

    results: list[str] = []
    for match in re.finditer(
        r'class="result-link"[^>]*>([^<]+)</a>.*?class="result-snippet"[^>]*>([^<]+)',
        html,
        flags=re.DOTALL | re.IGNORECASE,
    ):
        title = unescape(re.sub(r"\s+", " ", match.group(1)).strip())
        snippet = unescape(re.sub(r"\s+", " ", match.group(2)).strip())
        if title or snippet:
            results.append(f"{title}\n{snippet}".strip())
        if len(results) >= max_results:
            break

    if results:
        return results

    # Fallback: simpler link/snippet pattern
    for match in re.finditer(r"<a[^>]+href=\"[^\"]+\"[^>]*>([^<]{4,200})</a>", html):
        text = unescape(re.sub(r"\s+", " ", match.group(1)).strip())
        if text and "duckduckgo" not in text.lower():
            results.append(text)
        if len(results) >= max_results:
            break

    return results[:max_results]
