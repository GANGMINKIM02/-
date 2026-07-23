from __future__ import annotations

"""Upstage Solar — 번역문 ↔ LEGAL_DB easy_text 시각자료 매칭."""

import json
import re

from backend.config import settings
from backend.services import upstage
from backend.services.image_matcher import (
    _overlap_score,
    load_easy_text_catalog,
    normalize_match_text,
)

_MIN_OVERLAP_SCORE = 18


def _score_catalog_item(query: str, item: dict[str, str]) -> int:
    q = normalize_match_text(query)
    if not q:
        return 0
    easy = item.get("easy_text") or ""
    title = item.get("title") or ""
    original = item.get("original") or ""
    score = max(
        _overlap_score(q, easy) * 4,
        _overlap_score(q, title) * 2,
        _overlap_score(q, original),
    )
    easy_norm = normalize_match_text(easy)
    if easy_norm and len(easy_norm) >= 8:
        if easy_norm in q or q in easy_norm:
            score = max(score, len(easy_norm) + 200)
    return score


def rank_catalog_candidates(
    translation_text: str,
    used_files: set[str],
    *,
    limit: int = 36,
) -> list[dict[str, str]]:
    """번역문과 easy_text 유사도 상위 후보."""
    scored: list[tuple[int, dict[str, str]]] = []
    for item in load_easy_text_catalog():
        if item["image_file"] in used_files:
            continue
        score = _score_catalog_item(translation_text, item)
        if score > 0:
            scored.append((score, item))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    candidates = [item for score, item in scored if score >= _MIN_OVERLAP_SCORE][:limit]
    if len(candidates) < min(10, limit):
        seen = {c["image_file"] for c in candidates}
        for item in load_easy_text_catalog():
            if item["image_file"] in used_files or item["image_file"] in seen:
                continue
            candidates.append(item)
            seen.add(item["image_file"])
            if len(candidates) >= limit:
                break
    return candidates[:limit]


def resolve_image_by_easy_text_overlap(
    translation_text: str,
    used_files: set[str],
    *,
    min_score: int = _MIN_OVERLAP_SCORE,
) -> tuple[str | None, str | None]:
    """Solar 실패·mock 시 DB easy_text 유사도 1순위."""
    best_score = 0
    best: dict[str, str] | None = None
    for item in load_easy_text_catalog():
        if item["image_file"] in used_files:
            continue
        score = _score_catalog_item(translation_text, item)
        if score > best_score:
            best_score = score
            best = item
    if best is None or best_score < min_score:
        return None, None
    return best["image_file"], best.get("title") or None


def pick_any_catalog_image(
    used_files: set[str],
    translation_text: str,
) -> tuple[str | None, str | None]:
    """미사용 그림 중 유사도 최대(없으면 임의 1장)."""
    best_score = -1
    best: dict[str, str] | None = None
    fallback: dict[str, str] | None = None
    for item in load_easy_text_catalog():
        if item["image_file"] in used_files:
            continue
        if fallback is None:
            fallback = item
        score = _score_catalog_item(translation_text, item)
        if score > best_score:
            best_score = score
            best = item
    chosen = best or fallback
    if chosen is None:
        return None, None
    return chosen["image_file"], chosen.get("title") or None


async def pick_image_with_upstage(
    translation_text: str,
    candidates: list[dict[str, str]],
) -> str | None:
    if not candidates or settings.use_mock:
        return None

    lines = []
    for idx, item in enumerate(candidates):
        easy = (item.get("easy_text") or "").replace('"', "'")[:400]
        title = (item.get("title") or "").replace('"', "'")
        lines.append(
            f'{idx + 1}. file="{item["image_file"]}" '
            f'title="{title}" db_easy_text="{easy}"'
        )
    catalog_block = "\n".join(lines)

    system = (
        "당신은 발달장애인용 이지리드 판결문에 넣을 시각자료(그림)를 고르는 전문가입니다. "
        "부록 시각자료 DB에는 각 그림마다 'db_easy_text'(DB에 저장된 이지리드 예시 문장)가 있습니다. "
        "사용자 번역문의 **의미**와 가장 가까운 db_easy_text에 연결된 그림 1개만 고르세요. "
        "제목(title)만 보고 고르지 말고, 반드시 db_easy_text와 번역문을 비교하세요. "
        'JSON만 출력: {"image_file":"image_XXX.png"}'
    )
    user = (
        "아래 [사용자 번역문]과 의미가 가장 비슷한 db_easy_text를 가진 후보 그림 1개를 고르세요.\n\n"
        f"[사용자 번역문]\n{translation_text[:2800]}\n\n"
        f"[후보 — file / title / db_easy_text]\n{catalog_block}"
    )

    try:
        raw = await upstage.chat_completion(system, user, max_tokens=350, temperature=0.05)
    except Exception:
        return None

    match = re.search(r"\{[^{}]*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group())
    except json.JSONDecodeError:
        return None

    image_file = str(data.get("image_file", "")).strip()
    allowed = {item["image_file"] for item in candidates}
    if image_file in allowed:
        return image_file

    for token in re.findall(r"image_\d+\.png", raw):
        if token in allowed:
            return token
    return None


def candidate_title(candidates: list[dict[str, str]], image_file: str) -> str | None:
    for item in candidates:
        if item["image_file"] == image_file:
            return item.get("title") or None
    return None
