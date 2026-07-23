from __future__ import annotations

"""챗봇 — LEGAL_DB·문서 맥락 우선, 부족 시 웹 검색 후 Solar 응답."""

import sys
import re
from pathlib import Path

from rapidfuzz import fuzz, process

from backend.config import ROOT_DIR
from backend.database import get_document
from backend.models.schemas import ChatMessage, ChatResponse
from backend.services.image_matcher import load_easy_text_catalog
from backend.services import upstage
from backend.services.prompts import load_chatbot_prompt
from backend.services.web_search import search_web

sys.path.insert(0, str(ROOT_DIR))
from db_rules import LEGAL_DB  # noqa: E402

NEED_WEB_MARKER = "NEED_WEB_SEARCH"
DB_MATCH_THRESHOLD = 55
DB_RESULT_LIMIT = 6
IMAGE_TITLE_RECOMMEND_LIMIT = 5
FRONTEND_CONTEXT = """
## 화면 정보
- 공통: 오른쪽 아래 챗봇 버튼을 누르면 대화창이 열립니다.
- 업로드 페이지: 파일을 드래그/선택해서 업로드하고, 업로드 버튼으로 다음 단계로 이동합니다. 관리자이면 저장소 관리 링크가 보입니다.
- 요약 페이지: 왼쪽에는 원문 페이지, 오른쪽에는 요약문이 보입니다. AI 프롬프트로 요약을 다시 다듬을 수 있습니다.
- 번역 페이지: 왼쪽에는 요약문, 오른쪽에는 번역문 편집 영역이 있습니다. AI 프롬프트로 번역을 수정할 수 있습니다.
- 그림 페이지: 왼쪽에는 번역문, 오른쪽에는 그림 DB가 있습니다. 검색창으로 그림을 찾고 드래그해서 배치합니다. 배치된 그림은 X 버튼으로 삭제할 수 있습니다.
- 내보내기 페이지: 완성된 이지리드 결과를 미리 보고 DOCX/PDF로 내보냅니다.
- 관리자 저장소 페이지: 계정별 저장 프로젝트를 확인하고 X 버튼으로 삭제할 수 있습니다.
""".strip()

SOURCE_REQUEST_RE = re.compile(
    r"(출처|근거|참고|어디서|어떤\s*자료|무슨\s*근거|source|reference|citat)",
    re.IGNORECASE,
)
IMAGE_REQUEST_RE = re.compile(
    r"(이미지|그림|삽화|일러스트|사진|아이콘|제목|title|추천)",
    re.IGNORECASE,
)

SOURCE_SENTENCE_RE = re.compile(
    r"[^.?!\n]*?(출처|근거|참고|웹\s*검색|DB\s*자료|문서\s*맥락|자료를\s*바탕|바탕으로)[^.?!\n]*[.?!]?",
    re.IGNORECASE,
)


def _strip_quote_markers(text: str) -> str:
    cleaned_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line == ">":
            continue
        # Remove markdown blockquote prefixes like "> 내용".
        line = re.sub(r"^>+\s*", "", line)
        cleaned_lines.append(line)
    cleaned = "\n".join(cleaned_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _sanitize_reply(reply: str) -> str:
    lines: list[str] = []
    for raw_line in reply.splitlines():
        line = raw_line.strip()
        if not line:
            lines.append("")
            continue
        if re.match(r"^(출처|참고|근거|웹 검색 결과|DB 자료|문서 맥락)\s*[:：]", line):
            continue
        line = line.replace("웹 검색 결과에 따르면", "")
        line = line.replace("웹 검색 결과를 보면", "")
        line = line.replace("DB 자료에 따르면", "")
        line = line.replace("DB 자료를 보면", "")
        line = line.replace("문서 맥락상", "")
        line = line.replace("현재 문서 기준으로", "")
        line = line.replace("현재 화면 기준으로", "")
        lines.append(line.strip())

    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return _strip_quote_markers(cleaned)


def _remove_source_sentences(reply: str) -> str:
    text = SOURCE_SENTENCE_RE.sub("", reply)
    text = re.sub(r"(?:^|\n)\s*(?:출처|참고|근거|웹 검색 결과|DB 자료|문서 맥락)\s*[:：].*(?:\n|$)", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return _strip_quote_markers(text)


def _wants_source(question: str) -> bool:
    return bool(SOURCE_REQUEST_RE.search(question))


def _wants_image_help(question: str) -> bool:
    return bool(IMAGE_REQUEST_RE.search(question))


def _is_short_keyword_query(question: str) -> bool:
    normalized = re.sub(r"\s+", " ", question).strip(" ?!.,")
    if not normalized:
        return False
    return len(normalized) <= 20 and len(normalized.split()) <= 3


def _should_include_image_context(question: str, hits: list[dict[str, str]]) -> bool:
    if not hits:
        return False
    return _wants_image_help(question) or _is_short_keyword_query(question)


def search_image_catalog(query: str, *, limit: int = 8) -> list[dict[str, str]]:
    if not query.strip():
        return []

    catalog = load_easy_text_catalog()
    if not catalog:
        return []

    choices = [
        (
            f"{item.get('title', '')} {item.get('easy_text', '')} {item.get('original', '')}".strip(),
            item,
        )
        for item in catalog
    ]
    matches = process.extract(
        query,
        choices,
        scorer=fuzz.token_set_ratio,
        processor=lambda entry: entry[0],
        limit=limit * 2,
    )

    results: list[dict[str, str]] = []
    seen_titles: set[str] = set()
    for choice, score, _ in matches:
        if score < 45:
            continue
        item = choice[1]
        title = (item.get("title") or "").strip()
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)
        results.append(
            {
                "title": title,
                "image_file": str(item.get("image_file") or "").strip(),
                "easy_text": str(item.get("easy_text") or "").strip(),
                "original": str(item.get("original") or "").strip(),
            }
        )
        if len(results) >= limit:
            break
    return results


def search_image_titles(query: str, *, limit: int | None = None) -> list[dict[str, str]]:
    if not query.strip():
        return []

    catalog = load_easy_text_catalog()
    if not catalog:
        return []

    titled = [item for item in catalog if (item.get("title") or "").strip()]
    matches = process.extract(
        query,
        titled,
        scorer=fuzz.token_set_ratio,
        processor=lambda item: str(item.get("title") or ""),
        limit=len(titled),
    )

    results: list[dict[str, str]] = []
    seen_titles: set[str] = set()
    for item, score, _ in matches:
        if score < 35:
            continue
        title = str(item.get("title") or "").strip()
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)
        results.append(
            {
                "title": title,
                "image_file": str(item.get("image_file") or "").strip(),
            }
        )
        if limit is not None and len(results) >= limit:
            break
    return results


def _build_image_title_reply(hits: list[dict[str, str]]) -> str:
    if not hits:
        return _fallback_unresolved_reply()
    lines = ["관련된 이미지 title 후보는 아래와 같습니다."]
    for hit in hits:
        image_file = hit.get("image_file") or ""
        if image_file:
            lines.append(f"- {hit['title']} ({image_file})")
        else:
            lines.append(f"- {hit['title']}")
    return "\n".join(lines)


def _sanitize_reply_for_request(reply: str, *, wants_source: bool) -> str:
    if wants_source:
        return reply.replace(NEED_WEB_MARKER, "").strip()
    cleaned = _sanitize_reply(reply).replace(NEED_WEB_MARKER, "").strip()
    return _remove_source_sentences(cleaned)


def _fallback_unresolved_reply() -> str:
    return (
        "답변에 필요한 정보를 찾지 못했습니다. "
        "질문을 조금 더 구체적으로 말씀해 주세요."
    )


def search_legal_db(query: str, *, limit: int = DB_RESULT_LIMIT) -> list[dict[str, str]]:
    """LEGAL_DB에서 질의와 관련된 이지리드 사례 검색."""
    if not query.strip() or not LEGAL_DB:
        return []

    matches = process.extract(
        query,
        LEGAL_DB.keys(),
        scorer=fuzz.token_set_ratio,
        limit=limit,
    )

    hits: list[dict[str, str]] = []
    seen: set[str] = set()
    for key, score, _ in matches:
        if score < DB_MATCH_THRESHOLD:
            continue
        if key in seen:
            continue
        seen.add(key)
        entries = LEGAL_DB.get(key) or []
        if not entries:
            continue
        entry = entries[0]
        hits.append(
            {
                "original": key,
                "easy_text": (entry.get("easy_text") or "").strip(),
                "title": (entry.get("title") or "").strip(),
                "score": str(score),
            }
        )
    return hits


async def build_document_context(doc_id: str | None) -> str:
    if not doc_id:
        return ""
    doc = await get_document(doc_id)
    if not doc:
        return ""

    parts = [
        f"파일명: {doc.filename}",
        f"사건 유형: {doc.doc_type}",
        f"진행 단계: {doc.stage}",
    ]
    if doc.summary:
        parts.append(f"요약:\n{doc.summary[:4000]}")
    translation = doc.translation_text
    if not translation and doc.translation_segments:
        translation = "\n\n".join(s.easy_text for s in doc.translation_segments if s.easy_text)
    if translation:
        parts.append(f"이지리드 번역:\n{translation[:4000]}")
    if doc.full_text and not doc.summary:
        parts.append(f"원문 발췌:\n{doc.full_text[:2000]}")
    return "\n\n".join(parts)


def _format_db_context(hits: list[dict[str, str]]) -> str:
    if not hits:
        return ""
    blocks: list[str] = []
    for i, hit in enumerate(hits, 1):
        title = f" — {hit['title']}" if hit.get("title") else ""
        blocks.append(
            f"{i}. [원문] {hit['original']}{title}\n   [이지리드] {hit['easy_text']}"
        )
    return "\n\n".join(blocks)


def _build_user_payload(
    question: str,
    *,
    db_context: str,
    doc_context: str,
    page_context: str = "",
    image_context: str = "",
    web_context: str = "",
    wants_source: bool = False,
) -> str:
    sections = [
        "## 사용자 질문",
        question.strip(),
        "",
        FRONTEND_CONTEXT,
    ]
    if db_context.strip():
        sections.extend(["", "## DB 자료 (법률·이지리드 사례)", db_context])
    if doc_context.strip():
        sections.extend(["", "## 현재 작업 중인 문서", doc_context.strip()])
    if page_context.strip():
        sections.extend(["", "## 현재 화면 맥락", page_context.strip()])
    if image_context.strip():
        sections.extend(["", "## 이미지 후보", image_context.strip()])
    if web_context.strip():
        sections.extend(["", "## 웹 검색 결과", web_context.strip()])
    sections.extend(
        [
            "",
            "## 지시",
            "위 자료를 우선 활용해 질문에 바로 답하세요. 사용자에게 출처, 참고, 근거, 검색 과정은 언급하지 마세요.",
            "질문이 화면 구성이나 버튼 기능에 관한 것이라면 위 화면 정보를 기준으로 설명하세요.",
            "현재 화면 맥락이 있으면 버튼 이름, 위치, 동작을 그 맥락에 맞게 설명하세요.",
            "질문이 그림·이미지 추천에 관한 것이라면 이미지 후보의 title을 우선 추천하세요.",
        ]
    )
    if wants_source:
        sections.extend(
            [
                "",
                "## 출처 응답 허용",
                "사용자가 출처를 요구한 경우에만, 답변 끝에 간단히 출처를 알려도 됩니다.",
                "가능하면 짧게 '출처: DB 자료', '출처: 현재 문서', '출처: 웹 검색 결과'처럼 적으세요.",
            ]
        )
    return "\n".join(sections)


def _messages_for_solar(
    system: str,
    history: list[ChatMessage],
    user_payload: str,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    for msg in history[-10:]:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": user_payload})
    return messages


def _format_image_context(hits: list[dict[str, str]]) -> str:
    if not hits:
        return ""
    lines: list[str] = []
    for idx, hit in enumerate(hits, 1):
        lines.append(f"{idx}. 제목: {hit['title']} | 파일: {hit['image_file']}")
    return "\n\n".join(lines)


def _needs_web_fallback(reply: str, db_hits: list[dict], doc_context: str) -> bool:
    if db_hits or doc_context.strip():
        return False
    return not reply.strip()


async def answer_chat(
    question: str,
    *,
    doc_id: str | None = None,
    history: list[ChatMessage] | None = None,
    page_context: str | None = None,
) -> ChatResponse:
    history = history or []
    wants_source = _wants_source(question)
    wants_image_help = _wants_image_help(question)

    if wants_image_help:
        image_hits = search_image_titles(question, limit=IMAGE_TITLE_RECOMMEND_LIMIT)
        return ChatResponse(reply=_build_image_title_reply(image_hits), sources=["db_rules"])

    system = load_chatbot_prompt()
    db_hits = [] if wants_image_help else search_legal_db(question)
    db_context = _format_db_context(db_hits)
    image_hits = search_image_titles(question) if wants_image_help else search_image_catalog(question)
    image_context = _format_image_context(image_hits) if _should_include_image_context(question, image_hits) else ""
    doc_context = await build_document_context(doc_id)
    sources: list[str] = []

    payload = _build_user_payload(
        question,
        db_context=db_context,
        doc_context=doc_context,
        page_context=page_context or "",
        image_context=image_context,
        wants_source=wants_source,
    )
    messages = _messages_for_solar(system, history, payload)
    reply = await upstage.chat_completion_messages(messages, max_tokens=2048)
    reply = _sanitize_reply_for_request(reply, wants_source=wants_source)
    reply = reply.replace(NEED_WEB_MARKER, "").strip()
    if not reply:
        reply = _fallback_unresolved_reply()

    if _needs_web_fallback(reply, db_hits, doc_context):
        web_context = await search_web(question)
        if web_context.strip():
            sources.append("web")
            payload = _build_user_payload(
                question,
                db_context=db_context,
                doc_context=doc_context,
                page_context=page_context or "",
                web_context=web_context,
                wants_source=wants_source,
            )
            messages = _messages_for_solar(system, history, payload)
            reply = await upstage.chat_completion_messages(messages, max_tokens=2048)
            reply = _sanitize_reply_for_request(reply, wants_source=wants_source)
            reply = reply.replace(NEED_WEB_MARKER, "").strip()
            if not reply:
                reply = _fallback_unresolved_reply()
        elif not db_hits and not doc_context.strip():
            reply = _fallback_unresolved_reply()
    else:
        if db_hits:
            sources.append("db")
        if doc_context.strip():
            sources.append("document")

    if not sources:
        sources.append("solar")

    return ChatResponse(reply=reply.strip(), sources=sources)
