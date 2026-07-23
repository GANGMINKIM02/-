from __future__ import annotations

"""원문 판결문과 이지리드 본문 병합 — '이유' 직후 삽입."""

import re

# 형사 등 — 장애인 대상 Easy-Read 제공 고지 (가·나 항)
EASY_READ_PROVISION_PARAGRAPHS: list[str] = [
    "※ 장애인 등을 위한 이해하기 쉬운(Easy-Read) 판결의 제공",
    (
        "지적장애를 가진 피고인 OOO이 통상의 방식으로 작성한 판결서 내용을 "
        "충실하게 이해하기 어렵다고 보이므로, 아래 가.항과 같은 법적 근거에 따라 "
        "피고인에게 아래 나.항과 같은 ‘이해하기 쉬운(Easy-Read) 판결’을 제공합니다."
    ),
    "가. 제공의 법적 근거",
    (
        "- 헌법 제10조, 제11조, 제27조 제1항, 제34조 제5항\n"
        "- 장애인차별금지 및 권리구제 등에 관한 법률 제21조 제1항, 제26조 제1항, "
        "제4항, 제5항, 제8항 및 같은 법 시행령 제14조 제2항, 제17조 제1항\n"
        "- 발달장애인 권리보장 및 지원에 관한 법률 제10조 제1항\n"
        "- 유엔 장애인의 권리에 관한 협약 제5조, 제9조, 제13조, 제21조 등"
    ),
    "나. 제공하는 “이해하기 쉬운 판결”",
    "아래와 같습니다.",
]

_REASON_HEADING = re.compile(r"^이\s*유\s*$", re.MULTILINE)


def split_judgment_at_reason(full_text: str) -> tuple[str, str] | None:
    """(이유 포함 앞부분, 이유 다음 나머지 원문) 또는 None."""
    text = full_text.replace("\r\n", "\n").strip()
    if not text:
        return None

    match = _REASON_HEADING.search(text)
    if not match:
        return None

    prefix = text[: match.end()].rstrip()
    suffix = text[match.end() :].lstrip("\n")
    return prefix, suffix


def can_merge_original_with_easy_read(full_text: str | None) -> bool:
    return bool(full_text and split_judgment_at_reason(full_text))
