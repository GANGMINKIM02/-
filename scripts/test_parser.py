"""사건번호 기반 doc_type 분류 단위 테스트."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.services.parser import (  # noqa: E402
    classify_case_number,
    classify_doc_type,
    extract_case_numbers,
)


def assert_eq(label: str, got, expected) -> None:
    if got != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {got!r}")


def main() -> int:
    assert_eq("형사 고합", classify_case_number("2025고합1234"), "criminal")
    assert_eq("민사 가합", classify_case_number("2026가합4567"), "civil")
    assert_eq("가사 드단", classify_case_number("2024드단7890"), "family")
    assert_eq("행정 구합", classify_case_number("2026구합5678"), "administrative")
    assert_eq("공백 허용", classify_case_number(" 2026 구합 5678 "), "administrative")
    assert_eq("재심 접미", classify_case_number("2026구합5678재심"), "administrative")
    assert_eq("무효 번호", classify_case_number("invalid"), None)

    text = "울산지방법원 2026구합5548 판결"
    assert_eq("본문 추출", extract_case_numbers(text), ["2026구합5548"])
    assert_eq("본문 분류", classify_doc_type(text), "administrative")

    keyword_text = "피고인은 범죄사실이 있다. 주문 징역 3년."
    assert_eq("키워드 폴백", classify_doc_type(keyword_text), "criminal")

    print("test_parser: all passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
