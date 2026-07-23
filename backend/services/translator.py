from __future__ import annotations

"""쉬운 글(이지리드) 번역 오케스트레이션.

역할: 요약 → LEGAL_DB 매칭 + Solar 번역 + 체크리스트 검사·자동 수정을 조율한다.
주요 기능: translate_summary, refine_translation, run_checklist.
관계: matcher, prompts, upstage, checklist, image_matcher, routers/documents.
"""

import uuid

from backend.models.schemas import ChecklistReport, DocType, TranslationSegment
from backend.services import checklist, matcher, prompts, upstage
from backend.services.easy_read_sanitize import extract_refined_translation, sanitize_translation_text
from backend.services.image_matcher import fill_missing_item_placements_async


async def _attach_placements(segments: list[TranslationSegment], text: str) -> list[TranslationSegment]:
    if not segments:
        return segments
    segments[0].image_placements = await fill_missing_item_placements_async(text, [])
    return segments


def _build_checklist_report(text: str) -> ChecklistReport:
    raw = checklist.validate_easy_read(text)
    return ChecklistReport(**raw)


async def _revise_for_checklist(
    text: str,
    report: ChecklistReport,
    doc_type: DocType,
) -> str:
    issues = checklist.format_checklist_for_prompt(report.model_dump())
    if not issues.strip():
        return text
    system = prompts.build_translation_system_prompt(doc_type)
    user = (
        "다음 이지리드 번역본을 체크리스트에 맞게 **수정**하세요.\n"
        "의미는 유지하고, 아래 문제만 고치세요.\n"
        "**수정된 이지리드 번역본**, **수정 사항 설명** 같은 메타 제목·설명은 출력하지 마세요.\n"
        "번역본 본문만 출력하세요.\n\n"
        f"## 체크리스트 지적 사항\n{issues}\n\n"
        f"## 현재 번역본\n{text}"
    )
    revised = await upstage.chat_completion(system, user)
    return sanitize_translation_text(revised)


def _merge_db_images(
    db_segments: list[TranslationSegment],
    easy_text: str,
) -> list[TranslationSegment]:
    """Keep a single main translation segment; images are inserted at export time."""
    return [
        TranslationSegment(
            id=str(uuid.uuid4()),
            original=db_segments[0].original if db_segments else easy_text[:80],
            easy_text=easy_text,
            source="solar",
        )
    ]


async def translate_summary(
    summary: str,
    full_text: str,
    doc_type: DocType,
) -> tuple[list[TranslationSegment], str, ChecklistReport]:
    db_segments = matcher.translate_with_db(summary, full_context=full_text)
    db_hits = [s for s in db_segments if s.source == "db"]
    needs_solar = any(s.source == "solar" for s in db_segments) or not db_hits

    if needs_solar:
        system = prompts.build_translation_system_prompt(doc_type)
        source_excerpt = prompts.excerpt_full_text_for_translation(full_text)
        user = (
            "아래 **발췌 요약**을 바탕으로 **판결문 원문 발췌**를 참고하여 이지리드(Easy-Read) 전체를 작성하세요.\n"
            "요약·원문에 없는 사건·형량·인물을 invent하지 마세요.\n"
            "공통 작성 규칙·판결 유형 규칙·예시를 따르세요.\n"
            "`<○○판결 이지리드 — …>` 같은 **문서 제목·표지 줄은 출력하지 마세요**.\n"
            "첫 소제목은 **반드시 `<이 판결의 결론>`**(또는 청구·결론 합친 제목)으로 시작하고, "
            "청구(`<…가 요구하는 것>`)는 결론 **다음**에 작성하세요.\n\n"
            "## 발췌 요약 (번역용 메모 — 이지리드 아님)\n"
            f"{summary.strip()}\n\n"
            "## 판결문 원문 발췌\n"
            f"{source_excerpt}"
        )
        easy_text = await upstage.chat_completion(system, user)
        easy_text = sanitize_translation_text(easy_text)
        segments = _merge_db_images(db_hits, easy_text)
    else:
        segments = db_hits
        easy_text = "\n\n".join(s.easy_text for s in segments)

    text = easy_text if needs_solar else "\n\n".join(s.easy_text for s in segments)
    report = _build_checklist_report(text)

    if report.overall in ("fail", "warn"):
        revised = await _revise_for_checklist(text, report, doc_type)
        revised_report = _build_checklist_report(revised)
        if revised_report.overall != "fail" or report.overall == "fail":
            text = revised
            report = revised_report
            segments[0].easy_text = text
            segments[0].source = "solar"

    segments = await _attach_placements(segments, text)
    return segments, text, report


async def refine_translation(
    segments: list[TranslationSegment],
    instruction: str,
    doc_type: DocType,
) -> tuple[list[TranslationSegment], str, ChecklistReport]:
    current = "\n\n".join(s.easy_text for s in segments if s.easy_text)
    if not current.strip():
        raise ValueError("수정할 번역본이 없습니다.")
    preserved_placements = segments[0].image_placements if segments else []
    base_id = segments[0].id if segments else "1"
    base_original = segments[0].original if segments else ""
    system = prompts.build_translation_system_prompt(doc_type)
    user = (
        f"현재 번역:\n{current}\n\n"
        f"다음 지시에 따라 번역을 **수정**하세요:\n{instruction}\n\n"
        "규칙:\n"
        "- 사용자 지시를 **반드시 반영**해 전체 번역본을 다시 작성하세요.\n"
        "- **수정된 이지리드 번역본**, **수정 사항 설명** 같은 메타 제목·설명은 출력하지 마세요.\n"
        "- 번역본 본문만 출력하세요."
    )
    revised = await upstage.chat_completion(system, user, max_tokens=8000, temperature=0.45)
    revised = extract_refined_translation(revised, fallback=current)
    if revised.strip() == current.strip():
        revised = await upstage.chat_completion(
            system,
            f"{user}\n\n**중요**: 이전 출력은 지시가 반영되지 않았습니다. "
            f"지시({instruction})를 **확실히 반영**해 다시 작성하세요.",
            max_tokens=8000,
            temperature=0.55,
        )
        revised = extract_refined_translation(revised, fallback=current)

    new_segments = [
        TranslationSegment(
            id=base_id,
            original=base_original,
            easy_text=revised,
            source="solar",
            image_placements=preserved_placements,
        )
    ]
    report = _build_checklist_report(revised)
    return new_segments, revised, report


def run_checklist(text: str) -> ChecklistReport:
    return _build_checklist_report(text)
