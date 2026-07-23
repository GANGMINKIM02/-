/**
 * 번역 세그먼트 편집·미리보기 컴포넌트.
 *
 * 역할: 쉬운 글 한 블록을 편집하고 줄 단위로 법률 일러스트를 배치한다.
 * 주요 기능: 미리보기 렌더, textarea 편집, ImagePicker·PlacementBlock.
 * 연관 파일: api/client.ts, utils/sanitizeTranslation.ts, pages/TranslatePage.tsx
 */
import { useEffect, useMemo, useState } from "react";
import type { ImageCatalogItem, ImagePlacement, TranslationSegment } from "../api/client";
import { getImageCatalog } from "../api/client";
import { filterPreviewLines } from "../utils/sanitizeTranslation";

interface TranslationSegmentViewProps {
  segment: TranslationSegment;
  onEdit: (id: string, text: string) => void;
  onPlacementsChange: (id: string, placements: ImagePlacement[]) => void;
  fill?: boolean;
  /** 그림 탭: 미리보기·배치만 표시, 본문 textarea 숨김 */
  imagesOnly?: boolean;
}

function renderBoldText(text: string) {
  const parts = text.split(/(\*\*.+?\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      return (
        <strong key={i} className="font-semibold">
          {part.slice(2, -2)}
        </strong>
      );
    }
    return <span key={i}>{part.replace(/\*\*/g, "")}</span>;
  });
}

function isHeadingLine(line: string) {
  const s = line.trim();
  return (
    (s.startsWith("<") && s.endsWith(">")) ||
    s.startsWith("■") ||
    s.startsWith("#")
  );
}

function groupByLine(placements: ImagePlacement[]): Map<number, ImagePlacement[]> {
  const map = new Map<number, ImagePlacement[]>();
  for (const p of placements) {
    const list = map.get(p.line_index) ?? [];
    list.push(p);
    map.set(p.line_index, list);
  }
  return map;
}

function ImagePicker({
  onSelect,
  onClose,
}: {
  onSelect: (item: ImageCatalogItem) => void;
  onClose: () => void;
}) {
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<ImageCatalogItem[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getImageCatalog(query)
      .then((data) => {
        if (!cancelled) setItems(data.slice(0, 40));
      })
      .catch(console.error)
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [query]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-lg max-h-[80vh] flex flex-col rounded-xl bg-white shadow-xl border border-coolgray-20">
        <div className="flex items-center justify-between border-b border-coolgray-20 px-4 py-3">
          <h3 className="font-semibold text-coolgray-90">그림 선택</h3>
          <button type="button" onClick={onClose} className="text-coolgray-60 hover:text-coolgray-90">
            닫기
          </button>
        </div>
        <div className="p-4 border-b border-coolgray-20">
          <input
            type="search"
            placeholder="제목 또는 파일명 검색"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full h-10 px-3 bg-coolgray-10 border-b border-coolgray-30 text-sm outline-none focus:border-primary-60"
            autoFocus
          />
        </div>
        <div className="flex-1 overflow-auto p-4">
          {loading ? (
            <p className="text-sm text-slate-500">불러오는 중...</p>
          ) : items.length === 0 ? (
            <p className="text-sm text-slate-500">검색 결과가 없습니다.</p>
          ) : (
            <ul className="grid grid-cols-2 gap-3">
              {items.map((item) => (
                <li key={item.image_file}>
                  <button
                    type="button"
                    onClick={() => onSelect(item)}
                    className="w-full rounded-lg border border-coolgray-20 p-2 text-left hover:border-primary-60 hover:bg-coolgray-10"
                  >
                    <img
                      src={item.url}
                      alt={item.title}
                      className="mx-auto h-24 w-full object-contain"
                    />
                    <p className="mt-2 text-xs text-slate-700 line-clamp-2">{item.title}</p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

function PlacementBlock({
  placement,
  lineCount,
  onMove,
  onRemove,
  onChangeImage,
}: {
  placement: ImagePlacement;
  lineCount: number;
  onMove: (delta: number) => void;
  onRemove: () => void;
  onChangeImage: () => void;
}) {
  const url = `/images/${placement.image_file}`;

  return (
    <div className="my-2 flex gap-3 rounded-lg border border-primary-60/20 bg-coolgray-10 p-2">
      <img
        src={url}
        alt={placement.title || "시각자료"}
        className="h-28 w-28 shrink-0 object-contain bg-white rounded"
      />
      <div className="flex min-w-0 flex-1 flex-col justify-between">
        <p className="text-xs text-slate-600 line-clamp-2">
          {placement.title || placement.image_file}
        </p>
        <div className="flex flex-wrap gap-1">
          <button
            type="button"
            disabled={placement.line_index <= 0}
            onClick={() => onMove(-1)}
            className="rounded border border-coolgray-30 bg-white px-2 py-0.5 text-xs disabled:opacity-40"
          >
            ↑ 위 줄
          </button>
          <button
            type="button"
            disabled={placement.line_index >= lineCount - 1}
            onClick={() => onMove(1)}
            className="rounded border border-coolgray-30 bg-white px-2 py-0.5 text-xs disabled:opacity-40"
          >
            ↓ 아래 줄
          </button>
          <button
            type="button"
            onClick={onChangeImage}
            className="rounded border border-slate-300 bg-white px-2 py-0.5 text-xs"
          >
            그림 변경
          </button>
          <button
            type="button"
            onClick={onRemove}
            className="rounded border border-red-200 bg-white px-2 py-0.5 text-xs text-red-600"
          >
            삭제
          </button>
        </div>
      </div>
    </div>
  );
}

export function TranslationSegmentView({
  segment,
  onEdit,
  onPlacementsChange,
  fill = false,
  imagesOnly = false,
}: TranslationSegmentViewProps) {
  const previewLines = useMemo(
    () => filterPreviewLines(segment.easy_text),
    [segment.easy_text],
  );
  const placements = segment.image_placements ?? [];
  const byLine = useMemo(() => groupByLine(placements), [placements]);
  const [pickerTarget, setPickerTarget] = useState<
    { mode: "add"; lineIndex: number } | { mode: "change"; placementId: string } | null
  >(null);

  function updatePlacements(next: ImagePlacement[]) {
    onPlacementsChange(segment.id, next);
  }

  function movePlacement(placementId: string, delta: number) {
    updatePlacements(
      placements.map((p) =>
        p.id === placementId
          ? {
              ...p,
              line_index: Math.max(0, Math.min(previewLines.length - 1, p.line_index + delta)),
            }
          : p,
      ),
    );
  }

  function removePlacement(placementId: string) {
    updatePlacements(placements.filter((p) => p.id !== placementId));
  }

  function addPlacement(lineIndex: number, item: ImageCatalogItem) {
    if (placements.some((p) => p.image_file === item.image_file)) return;
    updatePlacements([
      ...placements,
      {
        id: crypto.randomUUID(),
        image_file: item.image_file,
        line_index: lineIndex,
        title: item.title,
      },
    ]);
  }

  function changePlacementImage(placementId: string, item: ImageCatalogItem) {
    updatePlacements(
      placements.map((p) =>
        p.id === placementId
          ? { ...p, image_file: item.image_file, title: item.title }
          : p,
      ),
    );
  }

  function handlePickerSelect(item: ImageCatalogItem) {
    if (!pickerTarget) return;
    if (pickerTarget.mode === "add") {
      addPlacement(pickerTarget.lineIndex, item);
    } else {
      changePlacementImage(pickerTarget.placementId, item);
    }
    setPickerTarget(null);
  }

  return (
    <div
      className={`flex flex-col gap-3 p-3 border border-coolgray-20 rounded-lg bg-white ${
        fill ? "flex-1 min-h-0 h-full" : ""
      }`}
    >
      <div className={`flex-1 min-w-0 flex flex-col ${fill ? "min-h-0" : ""}`}>
        {segment.title && (
          <div className="text-sm font-semibold text-slate-700 mb-1 shrink-0">
            {segment.title}
          </div>
        )}
        {segment.easy_text && (
          <div
            className={`overflow-auto rounded-lg border border-slate-100 bg-slate-50 p-3 text-[15px] leading-relaxed text-slate-800 ${
              imagesOnly || fill ? "flex-1 min-h-0" : "mb-2 max-h-64"
            }`}
          >
            {previewLines.map((line, idx) => (
              <div key={idx} className="mb-2 last:mb-0">
                <p
                  className={
                    isHeadingLine(line) ? "text-[17px] font-bold text-slate-900" : ""
                  }
                >
                  {renderBoldText(line.replace(/^#+\s*/, ""))}
                </p>
                {(byLine.get(idx) ?? []).map((placement) => (
                  <PlacementBlock
                    key={placement.id}
                    placement={placement}
                    lineCount={previewLines.length}
                    onMove={(delta) => movePlacement(placement.id, delta)}
                    onRemove={() => removePlacement(placement.id)}
                    onChangeImage={() =>
                      setPickerTarget({ mode: "change", placementId: placement.id })
                    }
                  />
                ))}
                <button
                  type="button"
                  onClick={() => setPickerTarget({ mode: "add", lineIndex: idx })}
                  className="mt-1 text-xs text-primary-60 hover:underline"
                >
                  + 이 줄에 그림 추가
                </button>
              </div>
            ))}
          </div>
        )}
        {!imagesOnly && (
          <textarea
            className={`w-full p-3 border border-coolgray-30 rounded-lg text-[15px] leading-relaxed resize-none ${
              fill ? "flex-1 min-h-0" : "min-h-[120px]"
            }`}
            value={segment.easy_text}
            onChange={(e) => onEdit(segment.id, e.target.value)}
          />
        )}
        {!imagesOnly && !fill && segment.original && (
          <div className="text-xs text-slate-400 mt-1 truncate shrink-0">
            원문: {segment.original}
          </div>
        )}
      </div>

      {pickerTarget && (
        <ImagePicker onSelect={handlePickerSelect} onClose={() => setPickerTarget(null)} />
      )}
    </div>
  );
}
