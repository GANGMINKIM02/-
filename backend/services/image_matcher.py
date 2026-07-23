from __future__ import annotations

"""이지리드 텍스트 ↔ LEGAL_DB 이미지 매칭.

역할: 쉬운 글 본문에서 키워드를 찾아 일러스트 배치·카탈로그를 제공한다.
주요 기능: detect_image_placements, list_image_catalog, find_matching_images.
관계: db_rules(LEGAL_DB), easy_read_sanitize, word_export·translator(호출).
"""

import re
import sys
import uuid
from dataclasses import dataclass
from functools import lru_cache

from backend.config import IMAGES_DIR, IS_VERCEL, ROOT_DIR
from backend.models.schemas import ImagePlacement
from backend.services.easy_read_sanitize import sanitize_translation_text, split_standard_closing

sys.path.insert(0, str(ROOT_DIR))
from db_rules import LEGAL_DB  # noqa: E402

MIN_PHRASE_LEN = 8
MIN_TITLE_LEN = 4
MIN_CHUNK_LEN = 6
MAX_IMAGES_PER_TEXT = 8

# Short title-like triggers that are too generic across doc types
_BLOCKED_KEYWORDS = frozenset(
    {
        "소송비용",
        "각하",
        "기각",
        "상계",
        "위자료",
        "재산분할",
    }
)


@dataclass(frozen=True)
class ImageMatch:
    image_file: str
    title: str | None
    trigger: str


def normalize_match_text(text: str) -> str:
    """Strip markdown markers so **장애인 등록** matches 장애인 등록."""
    cleaned = re.sub(r"\*+", "", text)
    cleaned = re.sub(r"#+\s*", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _is_valid_keyword(phrase: str) -> bool:
    phrase = phrase.strip()
    if len(phrase) < MIN_TITLE_LEN:
        return False
    if phrase in _BLOCKED_KEYWORDS:
        return False
    if len(phrase) < MIN_PHRASE_LEN and phrase in _BLOCKED_KEYWORDS:
        return False
    return True


def _chunk_phrases(text: str) -> list[str]:
    """Extract readable Korean phrase chunks for fuzzy in-text matching."""
    normalized = normalize_match_text(text)
    chunks: list[str] = []
    for segment in re.split(r"[.。\n!?]+", normalized):
        segment = segment.strip()
        if len(segment) >= MIN_CHUNK_LEN:
            chunks.append(segment)
        # Also add leading sub-phrases (e.g. '장애인 등록' from longer easy_text)
        words = segment.split()
        for i in range(len(words)):
            for j in range(i + 2, len(words) + 1):
                phrase = " ".join(words[i:j])
                if len(phrase) >= MIN_CHUNK_LEN:
                    chunks.append(phrase)
    return chunks


def _keywords_for_entry(key: str, easy_text: str, title: str | None) -> list[str]:
    words: list[str] = []
    if title:
        flat = normalize_match_text(title.replace("\n", " "))
        if _is_valid_keyword(flat):
            words.append(flat)
        for part in re.split(r"[\n()]+", title):
            part = normalize_match_text(part)
            if _is_valid_keyword(part):
                words.append(part)
    if easy_text:
        phrase = normalize_match_text(easy_text)
        if len(phrase) >= MIN_PHRASE_LEN:
            words.append(phrase)
        words.extend(_chunk_phrases(easy_text))
    phrase = normalize_match_text(key)
    if len(phrase) >= MIN_PHRASE_LEN:
        words.append(phrase)
    # Deduplicate, longest first
    unique = sorted(set(words), key=len, reverse=True)
    return [w for w in unique if _is_valid_keyword(w)]


@lru_cache(maxsize=1)
def load_easy_text_catalog() -> list[dict[str, str]]:
    """LEGAL_DB — image_file, title, easy_text, original(원문 키)."""
    seen: set[str] = set()
    catalog: list[dict[str, str]] = []
    for key, entries in LEGAL_DB.items():
        original = normalize_match_text(key.replace("\n", " "))
        for entry in entries:
            image_file = entry.get("image_file")
            if not image_file or image_file in seen:
                continue
            if not IS_VERCEL and not (IMAGES_DIR / image_file).is_file():
                continue
            seen.add(image_file)
            easy_text = normalize_match_text(entry.get("easy_text", "").replace("\n", " "))
            title = (entry.get("title") or "").replace("\n", " ").strip()
            if not easy_text and not title:
                continue
            catalog.append(
                {
                    "image_file": image_file,
                    "title": title,
                    "easy_text": easy_text,
                    "original": original,
                }
            )
    return catalog


@lru_cache(maxsize=1)
def _load_index() -> list[tuple[str, str | None, list[str]]]:
    seen: set[str] = set()
    index: list[tuple[str, str | None, list[str]]] = []
    for key, entries in LEGAL_DB.items():
        for entry in entries:
            image_file = entry.get("image_file")
            if not image_file or image_file in seen:
                continue
            if not IS_VERCEL and not (IMAGES_DIR / image_file).is_file():
                continue
            seen.add(image_file)
            keywords = _keywords_for_entry(
                key,
                entry.get("easy_text", ""),
                entry.get("title"),
            )
            if keywords:
                index.append((image_file, entry.get("title"), keywords))
    return index


def find_matching_images(text: str, *, max_images: int = MAX_IMAGES_PER_TEXT) -> list[ImageMatch]:
    normalized = normalize_match_text(text)
    if not normalized:
        return []
    matches: list[ImageMatch] = []
    used_files: set[str] = set()
    for image_file, title, keywords in _load_index():
        if len(matches) >= max_images:
            break
        if image_file in used_files:
            continue
        for kw in keywords:
            kw_norm = normalize_match_text(kw)
            if kw_norm and kw_norm in normalized:
                matches.append(
                    ImageMatch(image_file=image_file, title=title, trigger=kw_norm)
                )
                used_files.add(image_file)
                break
    return matches


def _overlap_score(text: str, candidate: str) -> int:
    """공통 문자 n-gram 점수 — 키워드 직접 포함이 없을 때 제목 유사도."""
    text_norm = normalize_match_text(text)
    cand_norm = normalize_match_text(candidate)
    if not text_norm or not cand_norm:
        return 0
    if cand_norm in text_norm or text_norm in cand_norm:
        return max(len(cand_norm), len(text_norm))
    text_tokens = set(re.findall(r"[가-힣]{2,}", text_norm))
    cand_tokens = set(re.findall(r"[가-힣]{2,}", cand_norm))
    return len(text_tokens & cand_tokens) * 10


def _find_best_overlap_image(text: str, used_files: set[str]) -> ImageMatch | None:
    best: ImageMatch | None = None
    best_score = 0
    for image_file, title, keywords in _load_index():
        if image_file in used_files:
            continue
        candidates = [title or "", *keywords]
        score = max(_overlap_score(text, c) for c in candidates if c)
        if score > best_score:
            best_score = score
            best = ImageMatch(image_file=image_file, title=title, trigger="overlap")
    return best if best_score > 0 else None


def _pick_fallback_image(used_files: set[str]) -> ImageMatch | None:
    for image_file, title, _keywords in _load_index():
        if image_file not in used_files:
            return ImageMatch(image_file=image_file, title=title, trigger="fallback")
    return None


def resolve_auto_image(text: str, used_files: set[str]) -> ImageMatch | None:
    """키워드 매칭 → 제목 유사도 → 미사용 이미지 순으로 자동 배치."""
    matches = find_matching_images(text, max_images=1)
    if matches and matches[0].image_file not in used_files:
        return matches[0]
    overlap = _find_best_overlap_image(text, used_files)
    if overlap:
        return overlap
    return _pick_fallback_image(used_files)


def find_images_for_line(
    line: str,
    *,
    exclude: set[str] | None = None,
    max_total: int = MAX_IMAGES_PER_TEXT,
) -> list[ImageMatch]:
    exclude = exclude or set()
    remaining = max(0, max_total - len(exclude))
    if remaining == 0:
        return []
    results: list[ImageMatch] = []
    for match in find_matching_images(line, max_images=remaining):
        if match.image_file not in exclude:
            results.append(match)
    return results


def _placement_source_text(text: str) -> str:
    """프론트 splitStandardClosing + filterPreviewLines 와 동일한 본문."""
    sanitized = sanitize_translation_text(text)
    body, _closing = split_standard_closing(sanitized)
    return body


def _placement_preview_lines(text: str) -> list[str]:
    body = _placement_source_text(text)
    return [
        line
        for line in body.split("\n")
        if line.strip() and not line.strip().startswith("---")
    ]


def preview_lines(text: str) -> list[str]:
    """Lines used for placement indices (matches frontend filterPreviewLines)."""
    return _placement_preview_lines(text)


_NUMBERED_ITEM = re.compile(r"^\s*\d+[\).]\s")


def _is_section_heading(line: str) -> bool:
    s = line.strip()
    return (s.startswith("<") and s.endswith(">")) or s.startswith("■") or s.startswith("#")


def _is_numbered_item_line(line: str) -> bool:
    return bool(_NUMBERED_ITEM.match(line))


def _parse_section_items(
    body_lines: list[str],
    body_start: int,
    section_heading: str | None,
) -> list[tuple[int, str, str | None]]:
    if not body_lines:
        return []

    if not any(_is_numbered_item_line(line) for line in body_lines):
        return [(body_start, "\n".join(body_lines), section_heading)]

    items: list[tuple[int, str, str | None]] = []
    current: list[str] = []
    current_start = body_start

    for offset, line in enumerate(body_lines):
        global_idx = body_start + offset
        if _is_numbered_item_line(line):
            if current:
                items.append((current_start, "\n".join(current), section_heading))
            current = [line]
            current_start = global_idx
        else:
            if not current:
                current_start = global_idx
            current.append(line)

    if current:
        items.append((current_start, "\n".join(current), section_heading))

    return items


def _parse_all_items(text: str) -> list[tuple[int, str, str | None]]:
    """(start_line_index, item_text, section_heading) — mirrors frontend parseSectionItems."""
    lines = preview_lines(text)
    if not lines:
        return []

    results: list[tuple[int, str, str | None]] = []
    i = 0
    while i < len(lines):
        section_heading: str | None = None
        section_start = i
        if _is_section_heading(lines[i]):
            section_heading = lines[i]
            i += 1

        body_lines: list[str] = []
        while i < len(lines) and not _is_section_heading(lines[i]):
            body_lines.append(lines[i])
            i += 1

        if not body_lines:
            continue

        body_start = section_start + (1 if section_heading else 0)
        results.extend(_parse_section_items(body_lines, body_start, section_heading))

    return results


def _parse_all_sections(text: str) -> list[tuple[int, str, str, list[tuple[int, str]]]]:
    """(section_start, heading_match_text, heading, items[(start_idx, item_text)])."""
    lines = preview_lines(text)
    if not lines:
        return []

    results: list[tuple[int, str, str, list[tuple[int, str]]]] = []
    i = 0
    while i < len(lines):
        if not _is_section_heading(lines[i]):
            i += 1
            continue

        heading = lines[i]
        section_start = i
        i += 1
        body_lines: list[str] = []
        while i < len(lines) and not _is_section_heading(lines[i]):
            body_lines.append(lines[i])
            i += 1

        body_start = section_start + 1
        items = [
            (start_idx, item_text)
            for start_idx, item_text, _section_heading in _parse_section_items(
                body_lines, body_start, heading
            )
        ]
        heading_plain = normalize_match_text(heading.strip("<>").strip())
        body_sample = normalize_match_text(" ".join(body_lines[:3]))
        match_text = f"{heading_plain} {body_sample}".strip()
        results.append((section_start, match_text or heading_plain, heading, items))

    return results


def _normalize_existing_placements(
    text: str,
    existing: list[ImagePlacement],
) -> list[ImagePlacement]:
    """예전 line_index·section_heading 배치를 해당 섹션 첫 항목으로 정렬."""
    source = _placement_source_text(text) if text else text
    section_starts = {start for start, *_rest in _parse_all_sections(source)}
    first_item_by_section = {
        start: items[0][0]
        for start, _match, _heading, items in _parse_all_sections(source)
        if items
    }
    heading_to_first: dict[str, int] = {}
    for _start, _match, heading, items in _parse_all_sections(source):
        if items:
            heading_to_first[normalize_match_text(heading.strip("<>").strip())] = items[0][0]

    normalized: list[ImagePlacement] = []
    occupied: set[int] = set()

    for placement in existing:
        line_index = placement.line_index
        if line_index in section_starts and line_index in first_item_by_section:
            line_index = first_item_by_section[line_index]
        if placement.section_heading:
            heading_key = normalize_match_text(placement.section_heading.strip("<>").strip())
            if heading_key in heading_to_first:
                line_index = heading_to_first[heading_key]
        if line_index in occupied:
            continue
        occupied.add(line_index)
        updates: dict[str, object] = {"line_index": line_index}
        if placement.section_heading and line_index != placement.line_index:
            updates["line_index"] = line_index
        if line_index != placement.line_index:
            placement = placement.model_copy(update=updates)
        normalized.append(placement)

    from backend.services.export_layout import align_placements_one_per_section

    collapsed = align_placements_one_per_section(source, normalized)
    return sorted(collapsed.values(), key=lambda p: p.line_index)


def _make_auto_placement(
    *,
    image_file: str,
    line_index: int,
    title: str | None,
    section_heading: str | None,
) -> ImagePlacement:
    return ImagePlacement(
        id=str(uuid.uuid4()),
        image_file=image_file,
        line_index=line_index,
        title=title,
        section_heading=section_heading,
        auto_filled=True,
    )


def _section_match_text(heading: str, items: list[tuple[int, str]]) -> str:
    """소제목 + 섹션 전체 본문(모든 항목)으로 대표 그림 매칭."""
    parts = [normalize_match_text(heading.strip("<>").strip())]
    for _idx, item_text in items:
        parts.append(normalize_match_text(item_text))
    return " ".join(p for p in parts if p)


def _item_match_text(items: list[tuple[int, str]]) -> str:
    """소제목 제외 — 번역 항목 본문만 (DB easy_text와 비교용)."""
    parts = [normalize_match_text(text) for _idx, text in items if text.strip()]
    return " ".join(p for p in parts if p)


def _section_match_text_for_image(heading: str | None, items: list[tuple[int, str]]) -> str:
    parts: list[str] = []
    if heading:
        parts.append(normalize_match_text(heading.strip("<>").strip()))
    parts.append(_item_match_text(items))
    return " ".join(p for p in parts if p)


async def fill_missing_item_placements_async(
    text: str,
    existing: list[ImagePlacement] | None = None,
) -> list[ImagePlacement]:
    """소제목별 첫 항목 1칸 — 번역문 ↔ LEGAL_DB easy_text Solar 매칭."""
    from backend.services.image_ai_select import (
        candidate_title,
        pick_any_catalog_image,
        pick_image_with_upstage,
        rank_catalog_candidates,
        resolve_image_by_easy_text_overlap,
    )

    source = _placement_source_text(text)
    existing = _normalize_existing_placements(text, existing or [])
    by_line = {p.line_index: p for p in existing}
    used_files = {p.image_file for p in existing}
    result = list(existing)

    for _section_start, _heading_match, heading, items in _parse_all_sections(source):
        if not items:
            continue
        first_idx, _first_text = items[0]
        if first_idx in by_line:
            continue

        match_text = _section_match_text_for_image(heading, items)
        if not match_text.strip():
            continue

        candidates = rank_catalog_candidates(match_text, used_files)
        image_file = await pick_image_with_upstage(match_text, candidates)
        title: str | None = None

        if image_file:
            title = candidate_title(candidates, image_file)
        else:
            image_file, title = resolve_image_by_easy_text_overlap(
                match_text, used_files, min_score=10
            )
        if not image_file:
            image_file, title = resolve_image_by_easy_text_overlap(
                match_text, used_files, min_score=0
            )
        if not image_file:
            image_file, title = pick_any_catalog_image(used_files, match_text)
        if not image_file:
            image_file, title = pick_any_catalog_image(set(), match_text)

        if not image_file:
            continue

        placement = _make_auto_placement(
            image_file=image_file,
            line_index=first_idx,
            title=title,
            section_heading=heading,
        )
        result.append(placement)
        by_line[first_idx] = placement
        used_files.add(image_file)

    return sorted(result, key=lambda p: p.line_index)


def ensure_item_placements(text: str, existing: list[ImagePlacement] | None = None) -> list[ImagePlacement]:
    """export 시 빈 섹션 없이 그림 배치."""
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(fill_missing_item_placements_async(text, existing))
    return fill_missing_item_placements(text, existing or [])


def fill_missing_item_placements(
    text: str,
    existing: list[ImagePlacement] | None = None,
) -> list[ImagePlacement]:
    """동기 폴백 — mock/테스트용."""
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            raise RuntimeError("use async")
        return loop.run_until_complete(fill_missing_item_placements_async(text, existing))
    except RuntimeError:
        source = _placement_source_text(text)
        existing = _normalize_existing_placements(text, existing or [])
        by_line = {p.line_index: p for p in existing}
        used_files = {p.image_file for p in existing}
        result = list(existing)

        for _section_start, _heading_match, heading, items in _parse_all_sections(source):
            if not items:
                continue
            first_idx, _first_text = items[0]
            if first_idx in by_line:
                continue
            match_text = _section_match_text_for_image(heading, items)
            from backend.services.image_ai_select import (
                pick_any_catalog_image,
                resolve_image_by_easy_text_overlap,
            )

            image_file, title = resolve_image_by_easy_text_overlap(
                match_text, used_files, min_score=10
            )
            if not image_file:
                image_file, title = resolve_image_by_easy_text_overlap(
                    match_text, used_files, min_score=0
                )
            if not image_file:
                image_file, title = pick_any_catalog_image(used_files, match_text)
            if not image_file:
                image_file, title = pick_any_catalog_image(set(), match_text)
            if not image_file:
                continue
            placement = _make_auto_placement(
                image_file=image_file,
                line_index=first_idx,
                title=title,
                section_heading=heading,
            )
            result.append(placement)
            by_line[first_idx] = placement
            used_files.add(image_file)

        return sorted(result, key=lambda p: p.line_index)


def detect_image_placements(text: str) -> list[ImagePlacement]:
    """Auto-detect illustrations per preview line on first translation."""
    lines = preview_lines(text)
    used: set[str] = set()
    placements: list[ImagePlacement] = []
    for i, line in enumerate(lines):
        if len(placements) >= MAX_IMAGES_PER_TEXT:
            break
        for match in find_images_for_line(line, exclude=used, max_total=MAX_IMAGES_PER_TEXT):
            placements.append(
                ImagePlacement(
                    id=str(uuid.uuid4()),
                    image_file=match.image_file,
                    line_index=i,
                    title=match.title,
                )
            )
            used.add(match.image_file)
    return placements


def _catalog_image_files() -> list[str]:
    if IMAGES_DIR.is_dir():
        return sorted(p.name for p in IMAGES_DIR.glob("*.png"))
    seen: set[str] = set()
    files: list[str] = []
    for _key, entries in LEGAL_DB.items():
        for entry in entries:
            image_file = entry.get("image_file")
            if image_file and image_file not in seen:
                seen.add(image_file)
                files.append(image_file)
    return sorted(files)


def list_image_catalog(query: str = "") -> list[dict[str, str]]:
    """All PNG files on disk with LEGAL_DB titles when available."""
    title_by_file: dict[str, str] = {}
    for image_file, title, _keywords in _load_index():
        if title:
            title_by_file[image_file] = title.replace("\n", " ")

    items: list[dict[str, str]] = []
    for image_file in _catalog_image_files():
        title = title_by_file.get(image_file, image_file)
        if query:
            q = query.lower()
            if q not in title.lower() and q not in image_file.lower():
                continue
        items.append(
            {
                "image_file": image_file,
                "title": title,
                "url": f"/images/{image_file}",
            }
        )
    return items
