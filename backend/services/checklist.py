from __future__ import annotations

"""이지리드 작성 체크리스트 자동 검증.

역할: checklist.yaml 규칙에 따라 번역본의 문장·용어·형식을 점검한다.
주요 기능: validate_easy_read, format_checklist_for_prompt(AI 수정용).
관계: config(PROMPTS_DIR), translator(번역 후·수정 루프).
"""

import re
from pathlib import Path
from typing import Any, Literal

import yaml

from backend.config import PROMPTS_DIR

CheckStatus = Literal["pass", "warn", "fail", "manual"]

LEGAL_TERMS = (
    "주문",
    "청구취지",
    "집행유예",
    "선고유예",
    "공소기각",
    "면소",
    "피고인은",
    "원고는",
    "피해자환부",
    "피해자교부",
    "소멸시효",
    "통정허위",
    "과실상계",
    "양형",
    "범죄사실",
    "증거의 요지",
)

PASSIVE_PATTERNS = (
    r"[^\s]{1,12}되(?:었|였|ㄴ|는|어|아)\s",
    r"[^\s]{1,12}받(?:았|은|는|을|을)\s",
    r"[^\s]{1,12}당하(?:였|는|여|여)\s",
    r"[^\s]{1,12}지(?:었|였|ㄴ|는|어|아)\s(?:않|못)",
)

PRONOUN_PATTERNS = (
    r"\b그(?:가|는|을|를|의|건|녀|들)\b",
    r"\b그것\b",
    r"\b그건\b",
    r"\b이것\b",
    r"\b저것\b",
    r"\b그분\b",
)

ABBREV_PATTERNS = (
    r"방사청",
    r"경찰청\b(?![^.\n]{0,8}경찰)",
    r"[가-힣]{1,2}청\b",
)

SYMBOL_PATTERN = re.compile(r"[%&$]|(?<!\d)\.(?=\d{1,2}(?:[^\d]|$))")


def _load_checklist_config() -> list[dict[str, Any]]:
    path = PROMPTS_DIR / "checklist.yaml"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("items") or []


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _estimate_pages(text: str) -> int:
    # Rough: ~400 Korean chars per page at 12pt with margins
    chars = len(re.sub(r"\s+", "", text))
    return max(1, (chars + 399) // 400)


def _check_no_first_line_indent(text: str) -> tuple[CheckStatus, str | None]:
    for line in text.splitlines():
        if line.startswith("  ") or line.startswith("\t"):
            return "warn", "들여쓰기된 줄이 있습니다."
    return "pass", None


def _check_has_section_headings(text: str) -> tuple[CheckStatus, str | None]:
    if re.search(r"<[^>]{2,30}>", text):
        return "pass", None
    if re.search(r"^\d+\.\s", text, re.M):
        return "pass", None
    return "warn", "소제목(<...> 또는 번호)이 없습니다."


def _check_page_estimate(text: str) -> tuple[CheckStatus, str | None]:
    pages = _estimate_pages(text)
    if pages <= 5:
        return "pass", f"예상 {pages}쪽"
    if pages <= 10:
        return "warn", f"예상 {pages}쪽 — 5쪽 이내 권장"
    return "fail", f"예상 {pages}쪽 — 10쪽 초과"


def _check_conclusion_first(text: str) -> tuple[CheckStatus, str | None]:
    head = text[:400]
    if re.search(r"<이 판결의 결론>|<이 판결의 결론|결론>", head):
        return "pass", None
    if re.search(r"김.{0,4}(?:은|는).{0,20}(?:감옥|벌금|이혼|받아|인용|기각)", head):
        return "pass", None
    return "warn", "핵심 결론이 앞부분에 드러나지 않습니다."


def _check_sentence_length(text: str) -> tuple[CheckStatus, str | None]:
    long_sentences: list[str] = []
    for sent in _split_sentences(text):
        if len(sent) > 120:
            long_sentences.append(sent[:40] + "…")
    if not long_sentences:
        return "pass", None
    return "warn", f"긴 문장 {len(long_sentences)}개 — 짧게 나누세요."


def _check_unexplained_legal_terms(text: str) -> tuple[CheckStatus, str | None]:
    found: list[str] = []
    for term in LEGAL_TERMS:
        if term not in text:
            continue
        if re.search(rf"\*[^*\n]{{0,40}}{re.escape(term)}|{re.escape(term)}[^*\n]{{0,40}}\*", text):
            continue
        if re.search(rf"\([^)]{{0,30}}{re.escape(term)}|{re.escape(term)}[^)]{{0,30}}\)", text):
            continue
        found.append(term)
    if not found:
        return "pass", None
    return "warn", f"설명 없는 어려운 용어: {', '.join(found[:5])}"


def _check_line_break_length(text: str) -> tuple[CheckStatus, str | None]:
    issues = 0
    for line in text.splitlines():
        if not line.strip():
            continue
        if len(line) > 80:
            issues += 1
    if issues == 0:
        return "pass", None
    return "warn", f"한 줄이 80자를 넘는 줄 {issues}개 — 어절 단위로 나누세요."


def _check_number_date_format(text: str) -> tuple[CheckStatus, str | None]:
    issues: list[str] = []
    if re.search(r"\d{4}\.\s*\d{1,2}\.\s*\d{1,2}", text):
        issues.append("날짜 점 표기(2023.2.17)")
    if re.search(r"\d{1,2}:\d{2}", text):
        issues.append("시간 콜론 표기(20:00)")
    if re.search(r"\d{7,}원", text):
        issues.append("큰 금액 — 만·천 단위 권장")
    if re.search(r"\d+\s*%", text):
        issues.append("백분율 기호(%)")
    if not issues:
        return "pass", None
    return "warn", "; ".join(issues)


def _check_passive_voice(text: str) -> tuple[CheckStatus, str | None]:
    hits: list[str] = []
    for pat in PASSIVE_PATTERNS:
        for m in re.finditer(pat, text):
            hits.append(m.group(0).strip())
            if len(hits) >= 3:
                break
    if not hits:
        return "pass", None
    return "warn", f"피동·수동 표현 의심: {', '.join(hits[:3])}"


def _check_double_negative(text: str) -> tuple[CheckStatus, str | None]:
    patterns = (
        r"않[^.\n]{0,30}않",
        r"없[^.\n]{0,30}없",
        r"아니[^.\n]{0,20}않",
        r"못[^.\n]{0,20}않",
    )
    for pat in patterns:
        if re.search(pat, text):
            return "fail", "이중부정 또는 복잡한 부정문이 있습니다."
    neg_count = len(re.findall(r"않(?:습니다|음|다|아|어)", text))
    if neg_count > max(3, len(_split_sentences(text)) // 3):
        return "warn", f"부정문이 많습니다({neg_count}개)."
    return "pass", None


def _check_vague_pronouns(text: str) -> tuple[CheckStatus, str | None]:
    hits: list[str] = []
    for pat in PRONOUN_PATTERNS:
        for m in re.finditer(pat, text):
            hits.append(m.group(0))
    if not hits:
        return "pass", None
    return "warn", f"지시·인칭대명사: {', '.join(sorted(set(hits))[:5])}"


def _check_abbreviations(text: str) -> tuple[CheckStatus, str | None]:
    for pat in ABBREV_PATTERNS:
        if re.search(pat, text):
            return "warn", "축약어 또는 줄임 표현이 있습니다."
    return "pass", None


def _check_ascii_symbols(text: str) -> tuple[CheckStatus, str | None]:
    if SYMBOL_PATTERN.search(text):
        return "warn", "%, &, $ 또는 점 날짜 형식 기호가 있습니다."
    return "pass", None


def _check_outline_only(text: str) -> tuple[CheckStatus, str | None]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return "pass", None
    bullet_like = sum(1 for ln in lines if re.match(r"^[·•\-①②③④⑤]\s", ln))
    if bullet_like > len(lines) * 0.6 and not re.search(r"[다요죠]\.?$", text, re.M):
        return "warn", "개조식 위주 — 서술형 문장을 추가하세요."
    return "pass", None


CHECKERS: dict[str, Any] = {
    "no_first_line_indent": _check_no_first_line_indent,
    "has_section_headings": _check_has_section_headings,
    "page_estimate": _check_page_estimate,
    "conclusion_first": _check_conclusion_first,
    "sentence_length": _check_sentence_length,
    "unexplained_legal_terms": _check_unexplained_legal_terms,
    "line_break_length": _check_line_break_length,
    "number_date_format": _check_number_date_format,
    "passive_voice": _check_passive_voice,
    "double_negative": _check_double_negative,
    "vague_pronouns": _check_vague_pronouns,
    "abbreviations": _check_abbreviations,
    "ascii_symbols": _check_ascii_symbols,
    "outline_only": _check_outline_only,
}


def validate_easy_read(text: str) -> dict[str, Any]:
    """Run checklist on Easy-Read translation text."""
    items_cfg = _load_checklist_config()
    results: list[dict[str, Any]] = []
    fail_count = warn_count = pass_count = manual_count = 0

    for item in items_cfg:
        item_id = item.get("id", "")
        check_name = item.get("check")
        auto = item.get("auto", False)
        participatory = item.get("participatory", False)

        if participatory or not auto:
            status: CheckStatus = "manual"
            detail = item.get("note") or "직접 확인하세요."
            manual_count += 1
        else:
            checker = CHECKERS.get(check_name or "")
            if checker:
                status, detail = checker(text)
            else:
                status, detail = "manual", "자동 검사 미구현"
                manual_count += 1
                results.append(
                    {
                        "id": item_id,
                        "category": item.get("category", ""),
                        "label": item.get("label", ""),
                        "status": status,
                        "detail": detail,
                    }
                )
                continue

            if status == "pass":
                pass_count += 1
            elif status == "fail":
                fail_count += 1
            else:
                warn_count += 1

        results.append(
            {
                "id": item_id,
                "category": item.get("category", ""),
                "label": item.get("label", ""),
                "status": status,
                "detail": detail,
            }
        )

    overall = "pass"
    if fail_count:
        overall = "fail"
    elif warn_count:
        overall = "warn"

    return {
        "overall": overall,
        "summary": {
            "pass": pass_count,
            "warn": warn_count,
            "fail": fail_count,
            "manual": manual_count,
        },
        "items": results,
    }


def format_checklist_for_prompt(report: dict[str, Any]) -> str:
    """Format failed/warn items for Solar revision prompt."""
    lines: list[str] = []
    for item in report.get("items", []):
        if item.get("status") in ("fail", "warn") and item.get("detail"):
            lines.append(f"- [{item['status']}] {item['label']}: {item['detail']}")
    return "\n".join(lines)
