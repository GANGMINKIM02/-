from __future__ import annotations

"""LLM 출력에서 메타 섹션 제거 및 이지리드 형식 정리.

역할: Solar가 추가한 메타 블록·문서 표지 제목을 제거하고, 결론 섹션을 청구보다 앞에 배치한다.
주요 기능: sanitize_translation_text.
관계: translator, image_matcher(미리보기 줄 정리 시).
"""

import re

STANDARD_CLOSING = "더 궁금한 것이 있으면 **소송구조 변호사**님에게 문의해 주세요."

_META_SECTION_START = re.compile(r"^###\s*수정\s*사항")
_IMAGE_PLACEHOLDER = re.compile(r"^\[image\]\s*$", re.I)
_DOC_TITLE_LINE = re.compile(
    r"^#?\s*<[^>]*(?:형사|민사|가사|행정)판결\s*이지리드",
    re.IGNORECASE,
)
_DOC_TITLE_EASY_READ = re.compile(
    r"^#?\s*<[^>]*이지리드\s*[—\-–]",
    re.IGNORECASE,
)
_DOC_META_HEADING = re.compile(
    r"^#?\s*<[^>]*(?:작성\s*요점|작성요점)[^>]*>",
    re.IGNORECASE,
)
_CLOSING_DISCLAIMER = re.compile(r"^※")
_CLOSING_BLANK_MARKER = re.compile(r"이하\s*빈칸|판결\s*본문은\s*다음")
_CLOSING_SUMMARY_NOTE = re.compile(r"이\s*요약은\s*판결문")
_CLOSING_CONTACT = re.compile(r"더\s*궁금한\s*것이\s*있으면.*문의")
_HR_LINE = re.compile(r"^-{3,}\s*$")


def _closing_plain(line: str) -> str:
    return re.sub(r"\*+", "", line.strip())


def _is_trailing_closing_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if _HR_LINE.match(stripped):
        return True
    if _CLOSING_DISCLAIMER.match(stripped):
        return True
    if _CLOSING_BLANK_MARKER.search(stripped):
        return True
    if _CLOSING_SUMMARY_NOTE.search(stripped):
        return True
    if _is_standard_closing_line(stripped):
        return True
    if _CLOSING_CONTACT.search(stripped):
        return True
    return False


def _is_standard_closing_line(line: str) -> bool:
    return _closing_plain(line) == _closing_plain(STANDARD_CLOSING)


def _apply_standard_closing(text: str) -> str:
    if not text.strip():
        return STANDARD_CLOSING

    body, closing = split_standard_closing(text)
    if closing:
        return merge_with_standard_closing(body, closing)

    if not body.strip():
        return STANDARD_CLOSING
    return merge_with_standard_closing(body, STANDARD_CLOSING)


def split_standard_closing(text: str) -> tuple[str, str | None]:
    """본문과 표준 마무리 문장 분리 (export·미리보기에서 2단 레이아웃 제외용)."""
    if not text.strip():
        return text, None

    lines = text.split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        return "", None

    last = lines[-1].strip()
    if _is_standard_closing_line(last) or _CLOSING_CONTACT.search(last):
        lines.pop()
        while lines and not lines[-1].strip():
            lines.pop()
        body = "\n".join(lines).rstrip()
        return body, last

    return text.rstrip(), None


def merge_with_standard_closing(body: str, closing: str | None = STANDARD_CLOSING) -> str:
    """편집 본문 + 표준 마무리 병합."""
    trimmed = body.rstrip()
    if not closing:
        return trimmed
    if not trimmed:
        return closing
    return f"{trimmed}\n\n{closing}"


def _is_section_heading(line: str) -> bool:
    stripped = line.strip().lstrip("#").strip()
    if stripped.startswith("<") and stripped.endswith(">"):
        return True
    return stripped.startswith("■")


def _is_conclusion_heading(line: str) -> bool:
    text = line.strip()
    if "원하는 것과 이 판결의 결론" in text or "요구하는 것과 이 판결의 결론" in text:
        return True
    return "판결의 결론" in text


def _is_claim_heading(line: str) -> bool:
    text = line.strip()
    if _is_conclusion_heading(text):
        return False
    return any(token in text for token in ("요구하는 것", "원하는 것", "청구취지"))


def _strip_doc_title_lines(text: str) -> str:
    lines = text.split("\n")
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if _DOC_TITLE_LINE.match(stripped):
            continue
        if _DOC_TITLE_EASY_READ.match(stripped):
            continue
        if _DOC_META_HEADING.match(stripped):
            continue
        if _IMAGE_PLACEHOLDER.match(stripped):
            continue
        out.append(line)
    return "\n".join(out)


def _parse_sections(text: str) -> list[tuple[str | None, list[str]]]:
    sections: list[tuple[str | None, list[str]]] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    for line in text.split("\n"):
        if _is_section_heading(line):
            if current_heading is not None or current_lines:
                sections.append((current_heading, current_lines))
            current_heading = line.strip()
            current_lines = []
            continue
        current_lines.append(line)

    if current_heading is not None or current_lines:
        sections.append((current_heading, current_lines))
    return sections


def _sections_to_text(sections: list[tuple[str | None, list[str]]]) -> str:
    blocks: list[str] = []
    for heading, body in sections:
        if heading:
            blocks.append(heading)
        if body:
            body_text = "\n".join(body).strip("\n")
            if body_text:
                blocks.append(body_text)
    return "\n\n".join(blocks).strip()


def _reorder_conclusion_before_claim(text: str) -> str:
    sections = _parse_sections(text)
    if len(sections) < 2:
        return text

    conclusion_idx: int | None = None
    claim_idx: int | None = None
    for i, (heading, _) in enumerate(sections):
        if heading is None:
            continue
        if conclusion_idx is None and _is_conclusion_heading(heading):
            conclusion_idx = i
        if claim_idx is None and _is_claim_heading(heading):
            claim_idx = i

    if conclusion_idx is None or claim_idx is None or conclusion_idx < claim_idx:
        return text

    sections[conclusion_idx], sections[claim_idx] = sections[claim_idx], sections[conclusion_idx]
    return _sections_to_text(sections)


def sanitize_translation_text(text: str) -> str:
    lines = text.split("\n")
    out: list[str] = []
    in_meta = False

    for line in lines:
        stripped = line.strip()
        if stripped == "## 수정된 이지리드 번역본":
            continue
        if _META_SECTION_START.match(stripped):
            in_meta = True
            continue
        if in_meta:
            continue
        out.append(line)

    cleaned = "\n".join(out)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    cleaned = _strip_doc_title_lines(cleaned)
    cleaned = _reorder_conclusion_before_claim(cleaned)
    cleaned = _apply_standard_closing(cleaned)
    return cleaned.strip()


def extract_refined_translation(raw: str, *, fallback: str = "") -> str:
    """LLM refine 출력에서 번역 본문만 추출."""
    text = sanitize_translation_text(raw)
    if not text.strip():
        return fallback

    for marker in (
        "다음 지시에 따라 번역을 수정하세요:",
        "다음 지시에 따라 요약을 수정하세요:",
        "번역본 본문만 출력하세요.",
        "**수정된 이지리드 번역본**",
    ):
        if marker in text:
            text = text.split(marker, 1)[0]

    if "현재 번역:" in text:
        text = text.split("현재 번역:", 1)[-1]
    if "현재 요약:" in text:
        text = text.split("현재 요약:", 1)[-1]

    text = text.strip()
    return text or fallback
