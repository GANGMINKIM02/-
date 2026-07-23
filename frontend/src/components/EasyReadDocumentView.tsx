/**
 * 이지리드 2단 레이아웃 — 양식: <소제목> + 항목마다 왼쪽 그림 / 오른쪽 본문.
 */
import { useMemo, useState, type DragEvent, type ReactNode } from "react";
import type { ImageCatalogItem, ImagePlacement } from "../api/client";
import { StyledLine } from "./BoldText";
import { RichTextEditor } from "./RichTextEditor";
import {
  alignPlacementsToItems,
  findSectionForLineIndex,
  parseSectionItems,
  parseTranslationSections,
  splitStandardClosing,
  type TranslationItem,
  type TranslationSection,
} from "../utils/translationSections";
import { addClearedImageSlot } from "../utils/imageSlotPrefs";
import { EASY_READ_COURT_FONT_CLASS } from "../utils/exportTypography";

export const IMAGE_DRAG_MIME = "application/x-easyread-image";

export function parseDraggedImageItem(dataTransfer: DataTransfer): ImageCatalogItem | null {
  const raw = dataTransfer.getData(IMAGE_DRAG_MIME);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as ImageCatalogItem;
  } catch {
    return null;
  }
}

interface EasyReadDocumentViewProps {
  text: string;
  placements?: ImagePlacement[];
  mode: "translate" | "images";
  docId?: string;
  onTextChange?: (text: string) => void;
  onPlacementsChange?: (placements: ImagePlacement[]) => void;
  fill?: boolean;
  placeholder?: string;
  disabled?: boolean;
  /** 미리보기 — 드래그·삭제 비활성 */
  readOnly?: boolean;
}

export function EasyReadDocumentView({
  text,
  placements = [],
  mode,
  docId,
  onTextChange,
  onPlacementsChange,
  fill = false,
  placeholder = "번역 결과",
  disabled = false,
  readOnly = false,
}: EasyReadDocumentViewProps) {
  const { body: documentBody, closing } = useMemo(() => splitStandardClosing(text), [text]);
  const sections = useMemo(() => parseTranslationSections(documentBody), [documentBody]);
  const alignedPlacements = useMemo(
    () => alignPlacementsToItems(documentBody, placements),
    [documentBody, placements],
  );
  const [dragOverKey, setDragOverKey] = useState<string | null>(null);

  function setItemPlacement(
    startLineIndex: number,
    item: ImageCatalogItem,
    sectionHeading: string | null,
  ) {
    if (!onPlacementsChange) return;
    const section = findSectionForLineIndex(documentBody, startLineIndex);
    const without = placements.filter((p) => p.line_index !== startLineIndex);
    onPlacementsChange([
      ...without,
      {
        id: crypto.randomUUID(),
        image_file: item.image_file,
        line_index: startLineIndex,
        title: item.title,
        section_heading: sectionHeading ?? section?.heading ?? null,
        image_url:
          item.source_url || (item.url.startsWith("http") ? item.url : null) || null,
        auto_filled: false,
      },
    ]);
  }

  function removeItemPlacement(startLineIndex: number, placement?: ImagePlacement) {
    if (!onPlacementsChange) return;
    if (docId) addClearedImageSlot(docId, startLineIndex);
    onPlacementsChange(
      placements.filter((p) =>
        placement?.id ? p.id !== placement.id : p.line_index !== startLineIndex,
      ),
    );
  }

  if (!text.trim()) {
    return (
      <div
        className={`flex min-h-0 flex-1 items-center justify-center text-base text-coolgray-60 ${
          fill ? "" : "min-h-[200px]"
        }`}
      >
        {placeholder}
      </div>
    );
  }

  if (mode === "translate") {
    return (
      <div className={`${EASY_READ_COURT_FONT_CLASS} ${fill ? "flex min-h-0 min-w-0 flex-1 flex-col" : "min-w-0"}`}>
        <RichTextEditor
          value={text}
          onChange={(v) => onTextChange?.(v)}
          disabled={disabled}
          layout="export-preview"
          fill={fill}
          minHeight={fill ? "100%" : "360px"}
        />
      </div>
    );
  }

  return (
    <div className={`${EASY_READ_COURT_FONT_CLASS} space-y-8 ${fill ? "min-h-0 flex-1" : ""}`}>
      {sections.map((section, sectionIndex) => (
        <SectionBlock
          key={`${section.startLineIndex}-${sectionIndex}`}
          section={section}
          alignedPlacements={alignedPlacements}
          dragOverKey={dragOverKey}
          readOnly={readOnly}
          onDragOverKey={setDragOverKey}
          onDropItem={(lineIndex, item) => {
            if (readOnly) return;
            setDragOverKey(null);
            setItemPlacement(lineIndex, item, section.heading);
          }}
          onRemoveItem={(lineIndex, placement) => {
            if (readOnly) return;
            removeItemPlacement(lineIndex, placement);
          }}
        />
      ))}
      {closing && (
        <p className="text-[12px] leading-[2] text-coolgray-90 pt-2">
          <StyledLine text={closing} />
        </p>
      )}
    </div>
  );
}

function SectionBlock({
  section,
  alignedPlacements,
  dragOverKey,
  readOnly,
  onDragOverKey,
  onDropItem,
  onRemoveItem,
}: {
  section: TranslationSection;
  alignedPlacements: Map<number, ImagePlacement>;
  dragOverKey: string | null;
  readOnly?: boolean;
  onDragOverKey: (key: string | null) => void;
  onDropItem: (lineIndex: number, item: ImageCatalogItem) => void;
  onRemoveItem: (lineIndex: number, placement?: ImagePlacement) => void;
}) {
  const items = useMemo(() => parseSectionItems(section), [section]);

  return (
    <article className="space-y-4">
      {section.heading && (
        <h3 className="leading-snug">
          <StyledLine text={section.heading} heading />
        </h3>
      )}

      <div className="space-y-5">
        {items.map((item) => {
          const placement = alignedPlacements.get(item.startLineIndex);
          return (
            <ItemRow
              key={item.startLineIndex}
              item={item}
              placement={placement}
              dragOver={dragOverKey === String(item.startLineIndex)}
              onDragEnter={() => onDragOverKey(String(item.startLineIndex))}
              onDragLeave={() => onDragOverKey(null)}
              onDrop={(catalogItem) => onDropItem(item.startLineIndex, catalogItem)}
              onRemove={() => onRemoveItem(item.startLineIndex, placement)}
              readOnly={readOnly}
            />
          );
        })}
      </div>
    </article>
  );
}

function ItemRow({
  item,
  placement,
  dragOver,
  onDragEnter,
  onDragLeave,
  onDrop,
  onRemove,
  readOnly = false,
}: {
  item: TranslationItem;
  placement?: ImagePlacement;
  dragOver: boolean;
  onDragEnter: () => void;
  onDragLeave: () => void;
  onDrop: (item: ImageCatalogItem) => void;
  onRemove: () => void;
  readOnly?: boolean;
}) {
  return (
    <div className="grid grid-cols-[minmax(120px,32%)_1fr] gap-4 items-start">
      <ImageSlot
        placement={placement}
        dragOver={readOnly ? false : dragOver}
        readOnly={readOnly}
        onDragEnter={onDragEnter}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        onRemove={onRemove}
      />
      <div className="min-w-0 text-[12px] leading-[2] text-coolgray-90 space-y-1">
        {item.lines.map((line, i) => (
          <p key={i}>
            <StyledLine text={line} />
          </p>
        ))}
      </div>
    </div>
  );
}

function ImageSlot({
  placement,
  dragOver,
  readOnly = false,
  onDragEnter,
  onDragLeave,
  onDrop,
  onRemove,
}: {
  placement?: ImagePlacement;
  dragOver: boolean;
  readOnly?: boolean;
  onDragEnter: () => void;
  onDragLeave: () => void;
  onDrop: (item: ImageCatalogItem) => void;
  onRemove: () => void;
}) {
  function handleDragOver(e: DragEvent) {
    if (readOnly) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
    onDragEnter();
  }

  function handleDrop(e: DragEvent) {
    if (readOnly) return;
    e.preventDefault();
    onDragLeave();
    const item = parseDraggedImageItem(e.dataTransfer);
    if (item) onDrop(item);
  }

  const url = placement
    ? placement.image_url?.startsWith("http")
      ? placement.image_url
      : `/images/${placement.image_file}`
    : null;

  return (
    <div
      onDragOver={readOnly ? undefined : handleDragOver}
      onDragLeave={readOnly ? undefined : onDragLeave}
      onDrop={readOnly ? undefined : handleDrop}
      className={`relative rounded-lg border min-h-[120px] flex items-center justify-center p-2 ${
        placement
          ? "border-coolgray-30 bg-[#f5f0e8]"
          : readOnly
            ? "border-coolgray-20 bg-coolgray-10"
            : dragOver
              ? "border-primary-60 border-dashed bg-primary-60/5 text-primary-60"
              : "border-dashed border-coolgray-40 bg-[#f5f0e8] text-coolgray-60"
      } ${dragOver && placement && !readOnly ? "ring-2 ring-primary-60 ring-offset-1" : ""}`}
    >
      {placement ? (
        <>
          {url ? (
            <img
              src={url}
              alt={placement.title || "시각자료"}
              className="max-h-32 w-full object-contain pointer-events-none"
            />
          ) : (
            <span className="text-xs text-center text-coolgray-60 px-2 pointer-events-none">
              {placement.title || placement.image_file}
            </span>
          )}
          {!readOnly && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onRemove();
              }}
              className="absolute top-1 right-1 z-10 size-6 rounded-full bg-white/90 border border-coolgray-30 text-coolgray-60 hover:text-alert text-sm leading-none shadow-sm"
              aria-label="그림 제거"
            >
              ×
            </button>
          )}
        </>
      ) : readOnly ? null : (
        <span className="text-sm text-center px-2 pointer-events-none">
          그림 DB에서
          <br />
          드래그하여 배치
        </span>
      )}
    </div>
  );
}

/** 그림 DB 카드 — 드래그 소스 */
export function DraggableCatalogItem({
  item,
  children,
}: {
  item: ImageCatalogItem;
  children: ReactNode;
}) {
  return (
    <li
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData(IMAGE_DRAG_MIME, JSON.stringify(item));
        e.dataTransfer.effectAllowed = "copy";
      }}
      className="rounded border border-coolgray-20 p-2 bg-white cursor-grab active:cursor-grabbing hover:border-primary-60 transition-colors"
    >
      {children}
    </li>
  );
}
