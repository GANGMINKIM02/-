/**
 * 업로드 전 파일명(·짧은 힌트)에서 사건부호로 doc_type 추정 — backend parser.classify_case_number와 동일 기준.
 */
import type { DocType } from "../api/client";

export type KnownDocType = Exclude<DocType, "unknown">;

const CIVIL_SYMBOLS = new Set([
  "가", "가단", "가합", "가소", "나", "다", "재가단", "재가합", "재가소", "재나", "재다",
  "카", "카단", "카합", "카공", "카담", "카조", "카구", "카경", "카정", "카단조", "카합조",
  "타경", "타채", "타기", "타인", "타배", "타집",
  "머", "자", "차", "차전", "라", "마", "비", "비단", "비합", "과", "과단", "과합", "동", "인", "전", "지",
]);

const CRIMINAL_SYMBOLS = new Set([
  "고", "고단", "고합", "고약", "고약정", "노", "도", "오",
  "재고단", "재고합", "재노", "재도",
  "모", "초", "초기", "초적", "초재", "로",
  "감고", "치고", "전고", "보", "버", "어", "치노", "치도",
]);

const FAMILY_SYMBOLS = new Set([
  "드", "드단", "드합", "르", "므", "느", "느단", "느합",
  "재드단", "재드합", "재르", "재므", "재느단", "재느합",
  "너", "스", "정", "정단", "정합",
]);

const ADMIN_SYMBOLS = new Set([
  "구", "구단", "구합", "누", "두", "아", "아단", "아합",
  "재구단", "재구합", "재누", "재두", "재아단", "재아합",
]);

const CASE_NUM_PATTERN = /\d{2,4}[\s\n]*[가-힣]{1,4}[\s\n]*\d+/g;

function classifyCaseNumber(caseNum: string): KnownDocType | null {
  const cleaned = caseNum.replace(/[^0-9가-힣]/g, "");
  const match = /^(\d{2,4})([가-힣]{1,4})\d+/.exec(cleaned);
  if (!match) return null;
  const symbol = match[2];
  if (CIVIL_SYMBOLS.has(symbol)) return "civil";
  if (CRIMINAL_SYMBOLS.has(symbol)) return "criminal";
  if (FAMILY_SYMBOLS.has(symbol)) return "family";
  if (ADMIN_SYMBOLS.has(symbol)) return "administrative";
  return null;
}

function voteFromText(hint: string): KnownDocType | null {
  const votes = new Map<KnownDocType, number>();
  const bump = (t: KnownDocType) => votes.set(t, (votes.get(t) ?? 0) + 1);
  for (const m of hint.matchAll(CASE_NUM_PATTERN)) {
    const kind = classifyCaseNumber(m[0]);
    if (kind) bump(kind);
  }
  if (votes.size === 0) return null;
  let best: KnownDocType = "civil";
  let bestN = 0;
  for (const [t, n] of votes) {
    if (n > bestN) {
      bestN = n;
      best = t;
    }
  }
  return best;
}

/** 파일명 등에서 사건부호를 읽어 초기 선택 유형을 반환한다. */
export function guessDocTypeFromFilename(filename: string): KnownDocType {
  return voteFromText(filename) ?? "civil";
}
