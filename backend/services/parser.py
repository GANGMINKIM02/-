from __future__ import annotations

"""판결문 유형 분류 및 섹션 파싱.

역할: OCR 텍스트에서 형사·민사·가사·행정 등 doc_type을 추정하고 섹션을 분리한다.
주요 기능: classify_doc_type(사건번호 우선), classify_case_number, extract_sections.
관계: models/schemas(DocType), routers/documents(업로드 시), prompts(유형별 프롬프트).
"""

import re
from collections import Counter

from backend.models.schemas import DocType

CRIMINAL_MARKERS = ["피고인", "범죄사실", "주문", "징역", "벌금", "무죄"]
CIVIL_MARKERS = ["원고", "피고", "청구", "소송", "손해배상"]
FAMILY_MARKERS = ["이혼", "친권", "양육", "부양", "가사"]
ADMIN_MARKERS = ["처분", "행정", "취소", "무효", "행정청", "행정법원", "구합", "장애등록", "등급외"]

CASE_NUM_PATTERN = re.compile(r"\d{2,4}\s*[가-힣]{1,4}\s*\d+")

CIVIL_SYMBOLS = frozenset({
    "가", "가단", "가합", "가소", "나", "다", "재가단", "재가합", "재가소", "재나", "재다", "상",
    "카", "카단", "카합", "카공", "카담", "카조", "카구", "카경", "카정", "카단조", "카합조",
    "타경", "타채", "타기", "타인", "타배", "타집",
    "머", "자", "차", "차전", "라", "마", "비", "비단", "비합", "과", "과단", "과합", "동", "인", "전", "지",
})

CRIMINAL_SYMBOLS = frozenset({
    "고", "고단", "고합", "고약", "고약정", "노", "도", "오",
    "재고단", "재고합", "재노", "재도",
    "모", "초", "초기", "초적", "초재", "로",
    "감고", "치고", "전고", "보", "버", "어", "치노", "치도",
})

FAMILY_SYMBOLS = frozenset({
    "드", "드단", "드합", "르", "므", "느", "느단", "느합",
    "재드단", "재드합", "재르", "재므", "재느단", "재느합",
    "너", "스", "정", "정단", "정합",
})

ADMIN_SYMBOLS = frozenset({
    "구", "구단", "구합", "누", "두", "아", "아단", "아합",
    "재구단", "재구합", "재누", "재두", "재아단", "재아합",
})


def classify_case_number(case_num: str) -> DocType | None:
    """사건번호 문자열에서 대법원 사건부호 기준 doc_type을 반환한다."""
    cleaned = re.sub(r"[^0-9가-힣]", "", case_num.strip())
    match = re.match(r"^\d{2,4}([가-힣]{1,4})\d+", cleaned)
    if not match:
        return None

    symbol = match.group(1)
    if symbol in CIVIL_SYMBOLS:
        return "civil"
    if symbol in CRIMINAL_SYMBOLS:
        return "criminal"
    if symbol in FAMILY_SYMBOLS:
        return "family"
    if symbol in ADMIN_SYMBOLS:
        return "administrative"
    return None


def extract_case_numbers(text: str) -> list[str]:
    """본문에서 사건번호 후보를 추출한다 (공백·특수문자 허용)."""
    found: list[str] = []
    seen: set[str] = set()
    for m in CASE_NUM_PATTERN.finditer(text):
        raw = m.group(0)
        normalized = re.sub(r"[^0-9가-힣]", "", raw)
        if normalized and normalized not in seen:
            seen.add(normalized)
            found.append(raw.strip())
    return found


def classify_doc_type(text: str) -> DocType:
    """사건번호 우선 분류, 실패 시 키워드 점수 폴백."""
    votes: Counter[DocType] = Counter()
    for case_num in extract_case_numbers(text):
        kind = classify_case_number(case_num)
        if kind:
            votes[kind] += 1
    if votes:
        return votes.most_common(1)[0][0]
    return _classify_by_keywords(text)


def _classify_by_keywords(text: str) -> DocType:
    scores = {
        "criminal": _score(text, CRIMINAL_MARKERS),
        "civil": _score(text, CIVIL_MARKERS),
        "family": _score(text, FAMILY_MARKERS),
        "administrative": _score(text, ADMIN_MARKERS),
    }
    if "행정법원" in text or "구합" in text:
        scores["administrative"] += 3
    if "피고인" in text and "범죄사실" in text:
        scores["criminal"] += 2
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "unknown"
    return best  # type: ignore[return-value]


def _score(text: str, markers: list[str]) -> int:
    return sum(1 for m in markers if m in text)


def extract_sections(text: str) -> dict[str, str]:
    headers = ["주문", "범죄사실", "이유", "청구취지", "공소사실", "판시", "결론"]
    sections: dict[str, str] = {}
    pattern = "|".join(re.escape(h) for h in headers)
    splits = re.split(rf"(?=(?:{pattern})\s*\n)", text)
    for part in splits:
        part = part.strip()
        if not part:
            continue
        for h in headers:
            if part.startswith(h):
                body = part[len(h) :].strip()
                sections[h] = body
                break
    if not sections:
        sections["전문"] = text
    return sections
