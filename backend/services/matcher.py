from __future__ import annotations

"""LEGAL_DB 퍼지 매칭 및 당사자명 치환.

역할: 판결문 문장을 db_rules와 매칭해 DB 번역·이미지를 찾고, 플레이스홀더 이름을 실명으로 바꾼다.
주요 기능: translate_with_db, match_sentence (rapidfuzz).
관계: db_rules(LEGAL_DB), translator(1차 DB 매칭), models/schemas(TranslationSegment).
"""

import re
import sys
import uuid
from pathlib import Path

from rapidfuzz import fuzz, process

from backend.config import ROOT_DIR
from backend.models.schemas import TranslationSegment

sys.path.insert(0, str(ROOT_DIR))
from db_rules import LEGAL_DB  # noqa: E402

THRESHOLD = 85
PLACEHOLDER_NAMES = ["김이박", "박수춘", "김을동", "병"]


def normalize(text: str) -> str:
    text = re.sub(r"\s+", " ", text.strip())
    text = re.sub(r"\d+", "{N}", text)
    return text


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.。\n])\s*", text)
    return [p.strip() for p in parts if p.strip()]


def match_sentence(sentence: str) -> list[dict] | None:
    if sentence in LEGAL_DB:
        return LEGAL_DB[sentence]

    best = process.extractOne(
        sentence,
        LEGAL_DB.keys(),
        scorer=fuzz.token_sort_ratio,
    )
    if best and best[1] >= THRESHOLD:
        return LEGAL_DB[best[0]]

    normalized = normalize(sentence)
    for key, entries in LEGAL_DB.items():
        if normalize(key) == normalized:
            return entries
    return None


def substitute_names(easy_text: str, name_map: dict[str, str]) -> str:
    result = easy_text
    for placeholder, real in name_map.items():
        result = result.replace(placeholder, real)
    return result


def build_name_map(full_text: str) -> dict[str, str]:
    defendant = _extract_party(full_text, r"피고인\s*([가-힣]{2,4})")
    if defendant:
        return {"김이박": defendant, "박수춘": defendant, "김을동": defendant, "병": defendant}
    plaintiff = _extract_party(full_text, r"원고\s*([가-힣]{2,4})")
    if plaintiff:
        return {"김이박": plaintiff, "박수춘": plaintiff}
    return {}


def _extract_party(text: str, pattern: str) -> str | None:
    m = re.search(pattern, text)
    return m.group(1) if m else None


def translate_with_db(text: str, full_context: str = "") -> list[TranslationSegment]:
    name_map = build_name_map(full_context or text)
    segments: list[TranslationSegment] = []
    for sentence in split_sentences(text):
        entries = match_sentence(sentence)
        if entries:
            for entry in entries:
                easy = substitute_names(entry["easy_text"], name_map)
                image_file = entry.get("image_file")
                segments.append(
                    TranslationSegment(
                        id=str(uuid.uuid4()),
                        original=sentence,
                        easy_text=easy,
                        image_file=image_file,
                        image_url=f"/images/{image_file}" if image_file else None,
                        title=entry.get("title"),
                        source="db",
                    )
                )
        else:
            segments.append(
                TranslationSegment(
                    id=str(uuid.uuid4()),
                    original=sentence,
                    easy_text=sentence,
                    source="solar",
                )
            )
    return segments
