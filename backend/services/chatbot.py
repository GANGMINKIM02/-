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
## ERAI 서비스 이용 가이드
- 공통 이용 방법: ERAI는 판결문을 업로드한 뒤 업로드 → 요약 → 번역 → 시각자료 → 추출 순서로 이지리드 문서를 만드는 서비스입니다.
- 각 화면 위쪽의 단계 표시를 통해 현재 작업 단계를 확인할 수 있습니다.
- 오른쪽 아래의 챗봇 버튼을 누르면 대화창이 열립니다.
- 챗봇에는 서비스 이용 방법, 법률용어의 쉬운 뜻, 현재 작업 중인 판결문에 관해 질문할 수 있습니다.
- 챗봇은 사용자의 화면을 직접 보거나 버튼을 대신 누를 수 없습니다. 사용자가 현재 보고 있는 페이지나 오류 내용을 함께 알려주면 더 정확하게 안내할 수 있습니다.
- AI가 만든 요약문, 번역문과 시각자료는 반드시 원 판결문과 비교하여 확인해야 합니다.
- 최종 문서를 추출하기 전에 날짜, 금액, 형량, 사람 이름과 판결 결론이 정확한지 확인해야 합니다.

## 로그인과 기존 프로젝트
- 로그인한 사용자는 자신이 이전에 작업한 프로젝트를 업로드 페이지의 기존 프로젝트 대시보드에서 확인할 수 있습니다.
- 다른 계정으로 로그인하면 해당 계정에 저장된 프로젝트만 표시될 수 있습니다.
- 예전에 올린 판결문, 이전에 작업한 문서, 과거 프로젝트는 모두 기존 프로젝트 대시보드에서 찾습니다.
- 기존 프로젝트에서는 원문, 요약문, 번역문과 최종본의 생성 여부를 확인할 수 있습니다.
- 사용자는 각 자료 옆의 열기 버튼을 눌러 내용을 확인할 수 있습니다.

## 1. 업로드 페이지
- Browse Files 버튼을 누르거나 업로드 영역에 파일을 넣어 판결문 PDF 또는 Word 파일을 선택할 수 있습니다.
- 업로드 버튼을 누르면 AI가 판결문에서 글자를 추출하고 사건번호와 내용을 참고하여 사건 유형을 자동 추정합니다.
- 사건 유형 선택 팝업이 나타나면 사용자는 형사·민사·가사·행정 중 올바른 유형을 직접 확인하고 선택해야 합니다.
- AI가 추정한 사건 유형이 틀릴 수 있으므로 사건번호와 판결문 내용을 보고 다시 확인해야 합니다.
- 사건 유형을 선택하면 요약 단계로 이동할 수 있습니다.

### 기존 프로젝트 확인
- 업로드 페이지 하단의 기존 프로젝트 대시보드에서 이전 작업을 확인할 수 있습니다.
- 이전에 첨부한 판결문의 원문을 보려면 해당 프로젝트의 원문 열기 버튼을 누릅니다.
- 이전에 만든 요약문을 보려면 요약문 열기 버튼을 누릅니다.
- 이전에 만든 번역문을 보려면 번역문 열기 버튼을 누릅니다.
- 이전에 만든 최종 이지리드 문서를 보려면 최종본 열기 버튼을 누릅니다.
- 현재 새로 첨부한 판결문이 아니라 예전에 첨부한 판결문도 모두 기존 프로젝트 대시보드에서 찾습니다.

### 기존 프로젝트 상태
- 원문 완료는 판결문 파일이 업로드되었다는 뜻입니다.
- 요약문 완료는 판결문의 핵심 내용을 정리한 요약문이 생성되었다는 뜻입니다.
- 번역문 완료는 요약문을 쉬운 문장으로 바꾼 결과가 생성되었다는 뜻입니다.
- 최종본 완료는 시각자료 배치와 최종 문서 생성이 완료되었다는 뜻입니다.

## 2. 요약 페이지
- 왼쪽 화면에는 사용자가 첨부한 판결문 원문이 표시됩니다.
- 오른쪽 화면에는 선택한 사건 유형에 맞게 AI가 생성한 요약문이 표시됩니다.
- 사용자는 원문과 요약문을 비교하면서 내용이 정확한지 확인해야 합니다.
- 오른쪽 편집 영역에서 요약문 내용을 직접 추가하거나 삭제할 수 있습니다.
- 글자 크기와 강조 여부도 직접 수정할 수 있습니다.
- AI 프롬프트 입력창에 수정 요청을 입력하여 요약문을 다시 다듬을 수 있습니다.

## 3. 번역 페이지
- 왼쪽 화면에는 앞 단계에서 확정한 요약문이 표시됩니다.
- 오른쪽 화면에는 요약문을 쉬운 문장으로 바꾼 이지리드 번역문이 표시됩니다.
- 사용자는 요약문과 번역문을 비교하여 원래 의미가 바뀌지 않았는지 확인해야 합니다.
- 오른쪽 편집 영역에서 번역문 내용을 직접 수정할 수 있습니다.
- 글자 크기와 강조 여부도 직접 수정할 수 있습니다.
- 번역문 왼쪽의 노란색 시각자료 영역은 최종 이지리드에서 그림이 배치될 위치를 미리 보여줍니다.

## 4. 시각자료 페이지
- 왼쪽 화면에는 번역문과 시각자료가 배치될 위치가 표시됩니다.
- 오른쪽 화면에는 ERAI에 저장된 시각자료 목록이 표시됩니다.
- Solar AI는 각 문장이나 항목의 의미를 참고하여 관련 시각자료를 자동으로 추천하고 배치합니다.
- 자동으로 배치된 그림이 문장 의미와 다르면 사용자가 직접 변경해야 합니다.
- 사용자는 오른쪽 시각자료 목록의 그림을 끌어서 원하는 위치에 배치할 수 있습니다.
- AI 프롬프트에 `무죄와 관련된 그림을 찾아줘`, `징역을 설명하는 그림을 찾아줘`처럼 원하는 의미를 구체적으로 입력할 수 있습니다.

## 5. 추출 페이지
- 추출 페이지에서는 완성된 이지리드 문서를 PDF 형태의 미리보기로 확인할 수 있습니다.
- 화면 하단에는 PDF 추출하기, Word 추출하기, 업로드 화면으로 돌아가기 버튼이 있습니다.
- PDF 추출하기: 현재 미리보기와 같은 형태의 이지리드 문서를 PDF 파일로 다운로드합니다.
- Word 추출하기: 내용을 복사하거나 다시 편집하기 쉬운 Word 파일로 다운로드합니다.
- 업로드 화면으로 돌아가기: 업로드 페이지로 이동합니다.

## 자주 묻는 질문
- 사용자가 `예전에 올린 판결문은 어디서 봐요?`, `이전 파일은 어디 있어요?`, `과거 프로젝트를 찾고 싶어요`라고 물으면 업로드 페이지 하단의 기존 프로젝트 대시보드를 안내합니다.
- 사용자가 `원문은 어디서 봐요?`라고 물으면 기존 프로젝트 대시보드의 원문 열기 버튼을 안내합니다.
- 사용자가 `요약문은 어디서 봐요?`라고 물으면 기존 프로젝트 대시보드의 요약문 열기 버튼을 안내합니다.
- 사용자가 `번역문은 어디서 봐요?`라고 물으면 기존 프로젝트 대시보드의 번역문 열기 버튼을 안내합니다.
- 사용자가 `최종본은 어디서 봐요?`라고 물으면 기존 프로젝트 대시보드의 최종본 열기 버튼을 안내합니다.
- 사용자가 `사건 유형이 잘못됐어요`라고 물으면 사건 유형 선택 화면에서 올바른 사건 유형을 다시 확인하도록 안내합니다.
- 사용자가 `그림을 바꾸고 싶어요`라고 물으면 시각자료 페이지에서 오른쪽 그림을 원하는 위치로 끌어 배치하도록 안내합니다.
- 사용자가 `PDF와 Word의 차이가 뭐예요?`라고 물으면 PDF는 최종 모양 유지에 적합하고 Word는 추가 편집과 재사용에 적합하다고 설명합니다.
- 사용자가 특정 화면이나 버튼을 찾지 못하면 현재 보고 있는 페이지와 표시된 오류 문구를 알려 달라고 안내합니다.
""".strip()


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


def _build_service_help_reply(question: str) -> str:
    normalized = re.sub(r"\s+", "", question)

    if any(
        token in normalized
        for token in [
            "원문",
            "이전",
            "저장된문서",
            "저장된문서함",
            "내작업기록",
            "기존프로젝트",
            "기록",
            "히스토리",
            "업로드기록",
            "내문서함",
        ]
    ):
        return (
            "이전에 첨부한 판결문의 원문은 **업로드 페이지 하단의 기존 프로젝트 대시보드**에서 확인할 수 있습니다. "
            "해당 항목의 **원문 열기** 버튼을 누르면 됩니다. "
            "요약문, 번역문, 최종본도 모두 같은 **기존 프로젝트 대시보드**에서 확인할 수 있습니다. "
            "`내 문서함`, `업로드 기록`, `기록`, `히스토리` 같은 메뉴는 안내하지 않습니다."
        )

    if any(token in normalized for token in ["요약문", "번역문", "최종본", "결과", "문서"]):
        return (
            "이전에 첨부한 판결문의 요약문, 번역문, 최종본은 **업로드 페이지 하단의 기존 프로젝트 대시보드**에서 확인할 수 있습니다. "
            "현재 새로 첨부한 문서가 아니더라도, 예전에 작업한 문서의 결과도 그곳에서 찾으면 됩니다. "
            "다른 상단 메뉴를 안내하지 말고, 항상 **기존 프로젝트 대시보드**를 먼저 안내합니다."
        )

    return (
        "서비스 이용 방법은 **업로드 페이지 하단의 기존 프로젝트 대시보드**를 먼저 확인해 주세요. "
        "이곳에서 이전에 첨부한 판결문의 원문, 요약문, 번역문, 최종본을 볼 수 있습니다. "
        "별도 상단 메뉴 이름을 추측해서 안내하지 않습니다."
    )


def _sanitize_reply_for_request(reply: str, *, wants_source: bool) -> str:
    if wants_source:
        return _normalize_reply_markup(reply.replace(NEED_WEB_MARKER, "").strip())
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
    wants_service_help = _wants_service_help(question)

    if wants_image_help:
        image_hits = search_image_titles(question, limit=IMAGE_TITLE_RECOMMEND_LIMIT)
        return ChatResponse(reply=_build_image_title_reply(image_hits), sources=["db_rules"])

    if wants_service_help:
        return ChatResponse(reply=_build_service_help_reply(question), sources=["service_guide"])

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
