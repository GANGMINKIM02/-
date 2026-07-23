from __future__ import annotations

"""일러스트 파일 경로 해석.

역할: 로컬 images/ 또는 Vercel CDN·웹 URL에서 PNG 파일 경로를 반환한다.
주요 기능: resolve_image_path, resolve_placement_image.
관계: config(IMAGES_DIR, IS_VERCEL), word_export·pdf_export(삽입 시 사용).
"""

import hashlib
import os
from pathlib import Path

import httpx

from backend.config import DATA_DIR, IMAGES_DIR, IS_VERCEL

_CACHE_DIR = DATA_DIR / "image-cache"
_WEB_CACHE_DIR = DATA_DIR / "web-image-cache"


def resolve_image_path(image_file: str) -> Path | None:
    candidates = [
        IMAGES_DIR / image_file,
        Path(__file__).resolve().parent.parent.parent / "images" / image_file,
    ]
    for local in candidates:
        if local.is_file():
            return local

    if not IS_VERCEL:
        cached_web = _WEB_CACHE_DIR / image_file
        if cached_web.is_file():
            return cached_web
        return None

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached = _CACHE_DIR / image_file
    if cached.is_file():
        return cached

    host = os.getenv("VERCEL_URL", "").strip()
    if not host:
        return None

    url = f"https://{host}/images/{image_file}"
    try:
        response = httpx.get(url, timeout=15.0, follow_redirects=True)
        if response.status_code == 200 and response.content:
            cached.write_bytes(response.content)
            return cached
    except httpx.HTTPError:
        return None
    return None


def resolve_placement_image(*, image_file: str, image_url: str | None = None) -> Path | None:
    """Resolve a placement to a local file path (local DB or downloaded web image)."""
    if image_url and image_url.startswith("http"):
        return _download_web_image(image_url, image_file)
    return resolve_image_path(image_file)


def _download_web_image(url: str, image_file: str) -> Path | None:
    _WEB_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    ext = ".png"
    lower = url.lower().split("?", 1)[0]
    for candidate in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        if lower.endswith(candidate):
            ext = candidate
            break
    safe_name = image_file if image_file.startswith("web_") else f"web_{hashlib.sha256(url.encode()).hexdigest()[:16]}"
    cached = _WEB_CACHE_DIR / f"{safe_name}{ext}"
    if cached.is_file():
        return cached
    try:
        response = httpx.get(url, timeout=20.0, follow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0 (compatible; ERAI/1.0)",
        })
        if response.status_code == 200 and response.content:
            cached.write_bytes(response.content)
            return cached
    except httpx.HTTPError:
        return None
    return None
