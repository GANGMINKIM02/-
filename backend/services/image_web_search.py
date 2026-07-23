from __future__ import annotations

"""웹 이미지 검색 — 그림 탭 AI 프롬프트용 (Openverse + Wikimedia)."""

import hashlib
import logging
from html import unescape

import httpx

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ERAI-EasyRead/1.0; +https://github.com/mingpang1197/final)",
    "Accept": "application/json",
}


def _image_id(url: str) -> str:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    return f"web_{digest}"


def _to_item(*, image_url: str, thumb_url: str, title: str) -> dict[str, str]:
    return {
        "image_file": _image_id(image_url),
        "title": title[:120],
        "url": thumb_url or image_url,
        "source_url": image_url,
    }


async def search_web_images(query: str, *, max_results: int = 20) -> list[dict[str, str]]:
    query = query.strip()
    if not query:
        return []

    items: list[dict[str, str]] = []
    seen: set[str] = set()

    for fetcher in (_search_openverse, _search_wikimedia):
        try:
            batch = await fetcher(query, max_results=max_results)
        except Exception as exc:
            logger.warning("%s failed: %s", fetcher.__name__, exc)
            continue
        for item in batch:
            key = item.get("source_url") or item.get("url")
            if not key or key in seen:
                continue
            seen.add(key)
            items.append(item)
            if len(items) >= max_results:
                return items

    return items


async def _search_openverse(query: str, *, max_results: int) -> list[dict[str, str]]:
    async with httpx.AsyncClient(timeout=25.0, headers=_HEADERS, follow_redirects=True) as client:
        response = await client.get(
            "https://api.openverse.org/v1/images/",
            params={"q": query, "page_size": min(max_results, 20), "license_type": "commercial,modification"},
        )
        response.raise_for_status()
        data = response.json()

    items: list[dict[str, str]] = []
    for row in data.get("results") or []:
        if not isinstance(row, dict):
            continue
        image_url = (row.get("url") or "").strip()
        thumb = (row.get("thumbnail") or image_url).strip()
        title = unescape((row.get("title") or query).strip())
        if not image_url.startswith("http"):
            continue
        items.append(_to_item(image_url=image_url, thumb_url=thumb, title=title or query))
    return items


async def _search_wikimedia(query: str, *, max_results: int) -> list[dict[str, str]]:
    async with httpx.AsyncClient(timeout=25.0, headers=_HEADERS, follow_redirects=True) as client:
        response = await client.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "format": "json",
                "generator": "search",
                "gsrsearch": f"filetype:bitmap {query}",
                "gsrlimit": min(max_results, 20),
                "prop": "imageinfo",
                "iiprop": "url|thumburl",
                "iiurlwidth": 320,
            },
        )
        response.raise_for_status()
        data = response.json()

    pages = (data.get("query") or {}).get("pages") or {}
    items: list[dict[str, str]] = []
    for page in pages.values():
        if not isinstance(page, dict):
            continue
        info = (page.get("imageinfo") or [{}])[0]
        image_url = (info.get("url") or "").strip()
        thumb = (info.get("thumburl") or image_url).strip()
        title = unescape((page.get("title") or query).replace("File:", "").strip())
        if not image_url.startswith("http"):
            continue
        items.append(_to_item(image_url=image_url, thumb_url=thumb, title=title or query))
    return items
