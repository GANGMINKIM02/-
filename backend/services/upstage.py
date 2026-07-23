from __future__ import annotations

"""Upstage OCR·Solar Chat API 클라이언트.

역할: 문서 OCR(텍스트 추출)과 Solar LLM 채팅 완성을 호출한다.
주요 기능: PDF/이미지 OCR, mock 모드 폴백, chat_completion(요약·번역에 사용).
관계: config(settings), pdf_extract(로컬 PDF), routers/documents·services/translator(호출).
"""

import base64
import logging
from pathlib import Path

import httpx

from backend.config import settings
from backend.services.pdf_extract import extract_pdf_pages

logger = logging.getLogger(__name__)

SAMPLE_JUDGMENT = """주문
피고인 갑을 징역 3년에 처한다.

범죄사실
피고인은 2024년 5월 1일 서울 중구에서 피해자 을의 재물을 훔쳤다.

이유
피고인의 범행은 계획적이지 않고 반성하고 있다.
"""


def _parse_upstage_response(data: dict) -> str:
    """Extract plain text from Upstage document-parse / OCR JSON."""
    content = data.get("content")
    if isinstance(content, dict):
        for key in ("text", "markdown", "html"):
            value = content.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    if isinstance(data.get("text"), str) and data["text"].strip():
        return data["text"].strip()

    chunks: list[str] = []
    for element in data.get("elements") or []:
        if not isinstance(element, dict):
            continue
        element_content = element.get("content")
        if isinstance(element_content, dict):
            piece = (
                element_content.get("text")
                or element_content.get("markdown")
                or element_content.get("html")
                or ""
            )
        else:
            piece = element.get("text") or ""
        if piece and str(piece).strip():
            chunks.append(str(piece).strip())

    if chunks:
        return "\n".join(chunks).strip()

    for page in data.get("pages") or []:
        if not isinstance(page, dict):
            continue
        page_text = page.get("text") or ""
        if page_text.strip():
            chunks.append(page_text.strip())

    return "\n\n".join(chunks).strip()


async def extract_text_from_file(file_path: Path, filename: str) -> tuple[list[str], str]:
    if filename.lower().endswith(".txt"):
        text = file_path.read_text(encoding="utf-8", errors="replace")
        pages = _split_pages(text)
        return pages, "\n\n".join(pages)

    if filename.lower().endswith(".pdf"):
        local = extract_pdf_pages(file_path)
        if local:
            return local
        if settings.use_mock:
            raise ValueError(
                "PDF에서 텍스트를 추출하지 못했습니다. "
                "Vercel 배포 시 UPSTAGE_API_KEY와 MOCK_UPSTAGE=false를 설정하세요."
            )

    if settings.use_mock:
        return _mock_pages(filename)

    content = file_path.read_bytes()
    mime = _guess_mime(filename)
    text = await _call_upstage_ocr(content, filename, mime)
    if not text.strip():
        raise ValueError(
            "Upstage OCR에서 텍스트를 추출하지 못했습니다. "
            "스캔 PDF이거나 API 키·요금 한도를 확인하세요."
        )
    pages = _split_pages(text)
    return pages, "\n\n".join(pages)


def _guess_mime(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return "application/pdf"
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".jpg") or lower.endswith(".jpeg"):
        return "image/jpeg"
    return "application/octet-stream"


async def _call_upstage_ocr(content: bytes, filename: str, mime: str) -> str:
    headers = {"Authorization": f"Bearer {settings.upstage_api_key}"}
    form_data = {
        "model": "document-parse",
        "output_formats": '["text"]',
        "ocr": "force",
    }
    files = {"document": (filename, content, mime)}

    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(
            settings.upstage_ocr_url,
            headers=headers,
            files=files,
            data=form_data,
        )
        if response.status_code >= 400:
            logger.error("Upstage OCR failed: %s %s", response.status_code, response.text[:500])
            response.raise_for_status()
        data = response.json()
        text = _parse_upstage_response(data)
        if text:
            return text

        # Some responses nest under result
        if isinstance(data.get("result"), dict):
            text = _parse_upstage_response(data["result"])
            if text:
                return text

        logger.error("Upstage OCR empty payload keys: %s", list(data.keys()))
        return ""


def _mock_pages(filename: str) -> tuple[list[str], str]:
    page1 = "주문\n피고인 갑을 징역 3년에 처한다."
    page2 = "범죄사실\n피고인은 2024년 5월 1일 서울 중구에서 피해자 을의 재물을 훔쳤다."
    page3 = "이유\n피고인의 범행은 계획적이지 않고 반성하고 있다."
    pages = [page1, page2, page3]
    return pages, "\n\n".join(pages)


def _split_pages(text: str) -> list[str]:
    chunks = [c.strip() for c in text.split("\f") if c.strip()]
    if len(chunks) > 1:
        return chunks
    parts = [p.strip() for p in text.split("\n\n\n") if p.strip()]
    if len(parts) > 1:
        return parts
    return [text.strip()] if text.strip() else [""]


async def chat_completion(system: str, user: str, *, max_tokens: int = 4096, temperature: float = 0.2) -> str:
    return await chat_completion_messages(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )


async def chat_completion_messages(
    messages: list[dict[str, str]],
    *,
    max_tokens: int = 4096,
    temperature: float = 0.2,
) -> str:
    if settings.use_mock:
        user_parts = [m["content"] for m in messages if m.get("role") == "user"]
        system_parts = [m["content"] for m in messages if m.get("role") == "system"]
        return _mock_chat(
            system_parts[-1] if system_parts else "",
            user_parts[-1] if user_parts else "",
        )

    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(
            settings.upstage_chat_url,
            headers={
                "Authorization": f"Bearer {settings.upstage_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.solar_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


def _mock_summarize_from_text(text: str) -> str:
    import re

    order = ""
    m = re.search(r"주\s*문([\s\S]{0,2000})", text)
    if m:
        order = re.sub(r"\s+", " ", m.group(1)).strip()[:800]

    heading = "<이 판결의 결론>"
    if "행정법원" in text or "구합" in text or "처분" in text:
        intro = "아래는 업로드한 행정판결 원문에서 추출한 내용입니다. (Solar API 키 설정 시 AI 요약)"
    elif "원고" in text or "피고" in text:
        intro = "아래는 업로드한 판결 원문에서 추출한 내용입니다. (Solar API 키 설정 시 AI 요약)"
    else:
        intro = "아래는 업로드한 판결 원문에서 추출한 내용입니다. (Solar API 키 설정 시 AI 요약)"

    body = order or text[:1200].strip()
    return f"{heading}\n{intro}\n\n{body}"


def _mock_chat(system: str, user: str) -> str:
    if "ERAI" in system or "## 사용자 질문" in user:
        if "웹 검색 결과" in user:
            return (
                "웹 검색을 참고한 답변입니다. (mock)\n\n"
                "이지리드(Easy Read)는 어려운 판결문을 쉬운 말과 그림으로 바꿔 주는 형식입니다. "
                "ERAI 서비스에서는 업로드 → 요약 → 번역 → 그림 → 추출 순서로 진행합니다."
            )
        if "DB 자료" in user and "(DB에서 관련" not in user.split("## DB 자료")[1][:80]:
            return (
                "DB 자료를 바탕으로 답변드립니다. (mock)\n\n"
                "'징역'은 일정 기간 감옥에 머물러야 한다는 뜻입니다. "
                "이지리드에서는 '감옥에 ○년 동안 있어야 합니다'처럼 쉽게 풀어 씁니다."
            )
        if "NEED_WEB_SEARCH" in user.upper():
            return "NEED_WEB_SEARCH"
        return (
            "안녕하세요! ERAI 챗봇입니다. (mock)\n"
            "판결문·이지리드·서비스 사용법을 물어보세요."
        )

    if "체크리스트" in user and "현재 번역본" in user:
        body = user.split("## 현재 번역본")[-1].strip()
        return body.split("\n\n(모의")[0].strip()

    if "수정" in user or "다음 지시" in user or "refine" in system.lower():
        if "현재 요약" in user:
            current = user.split("현재 요약:", 1)[1].split("다음 지시", 1)[0].strip()
            instruction = ""
            if "다음 지시에 따라 요약을 수정하세요:" in user:
                instruction = user.split("다음 지시에 따라 요약을 수정하세요:", 1)[1].split("\n\n")[0].strip()
            if instruction:
                return f"{current}\n\n[{instruction} 반영 — mock]"
            return f"{current}\n\n(모의 AI 수정 반영)"
        if "현재 번역" in user:
            current = user.split("현재 번역:", 1)[1].split("다음 지시", 1)[0].strip()
            instruction = ""
            if "다음 지시에 따라 번역을" in user:
                instruction = user.split("다음 지시에 따라 번역을", 1)[1]
                instruction = instruction.split("수정하세요:", 1)[-1].split("\n\n")[0].strip()
            if instruction:
                return f"{current}\n\n[{instruction} 반영 — mock]"
            return f"{current}\n\n(모의 AI 수정 반영)"

    if "요약" in system or ("요약" in user and "번역" not in user[:80]):
        body = user
        for marker in ("다음 판결문을 요약", "다음 판결문", "요약하세요"):
            if marker in user:
                body = user.split(marker, 1)[-1].strip()
                break
        if len(body) > 150 and ("주문" in body or "행정법원" in body or "원고" in body):
            return _mock_summarize_from_text(body)
        return (
            "<이 판결의 결론>\n"
            "갑은 감옥에 3년 동안 있어야 합니다.\n\n"
            "<이런 결론을 내린 이유>\n"
            "1. 갑이 저지른 범죄는 이렇습니다.\n"
            "· 날짜·시간: 2024년 5월 1일\n"
            "· 장소: 서울 중구\n"
            "· 갑은 을의 재물을 훔쳤습니다.\n\n"
            "2. 갑은 잘못을 반성하고 있습니다."
        )

    if "이지리드" in system or "번역" in system or "번역" in user:
        if "원문:" in user and len(user) < 300:
            orig = user.split("원문:")[-1].strip()
            if "3년" in orig:
                return "갑은 감옥에 3년 동안 있어야 합니다."
            if "훔" in orig:
                return "갑은 2024년 5월 1일 서울 중구에서 을의 재물을 훔쳤습니다."
            if "반성" in orig:
                return "갑은 잘못을 반성하고 있습니다."
            return f"{orig} (쉬운 말로 바꿈)"
        return (
            "<이 판결의 결론>\n"
            "갑은 감옥에 3년 동안 있어야 합니다.\n\n"
            "<이런 결론을 내린 이유>\n"
            "1. 갑이 저지른 범죄는 이렇습니다.\n"
            "· 날짜·시간: 2024년 5월 1일\n"
            "· 장소: 서울 중구\n"
            "· 갑은 을의 재물을 훔쳤습니다.\n\n"
            "2. 갑은 잘못을 반성하고 있습니다."
        )
    return "처리 완료 (mock mode)"


def encode_file_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")
