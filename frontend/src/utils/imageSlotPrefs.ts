/**
 * 사용자가 그림 탭에서 제거한 슬롯(섹션 첫 항목 line_index) — AI 자동 배치 재적용 방지.
 */
import type { ImagePlacement } from "../api/client";

const PREFIX = "easyread:cleared-image-slots:";

function key(docId: string): string {
  return `${PREFIX}${docId}`;
}

export function getClearedImageSlots(docId: string): number[] {
  try {
    const raw = sessionStorage.getItem(key(docId));
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((n): n is number => typeof n === "number" && Number.isFinite(n));
  } catch {
    return [];
  }
}

export function addClearedImageSlot(docId: string, firstItemLineIndex: number): void {
  const set = new Set(getClearedImageSlots(docId));
  set.add(firstItemLineIndex);
  try {
    sessionStorage.setItem(key(docId), JSON.stringify([...set].sort((a, b) => a - b)));
  } catch {
    /* ignore */
  }
}

export function filterPlacementsRespectingClears(
  docId: string,
  placements: ImagePlacement[],
): ImagePlacement[] {
  const cleared = new Set(getClearedImageSlots(docId));
  if (!cleared.size) return placements;
  return placements.filter((p) => !cleared.has(p.line_index));
}
