import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useEditorHistory } from "../hooks/useEditorHistory";
import {
  clampFontSize,
  DEFAULT_FONT_SIZE,
  FONT_SIZE_PRESETS,
  htmlToMarkers,
  htmlToMarkersExportPreview,
  exportPreviewBodyToHtml,
  markersToHtml,
  type FontSizePt,
} from "../utils/richText";
import { EASY_READ_COURT_FONT_CLASS } from "../utils/exportTypography";
import { mergeWithStandardClosing, splitStandardClosing, STANDARD_CLOSING } from "../utils/translationSections";

export type RichTextEditorLayout = "full" | "export-preview";

type EditorSurface = "body" | "closing";

interface RichTextEditorProps {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  /** true면 툴바 없이 export-preview/ full 카드·타이포만 (번역 탭 요약 참고용) */
  readOnly?: boolean;
  minHeight?: string;
  layout?: RichTextEditorLayout;
  fill?: boolean;
}

function FontSizeCombo({
  value,
  disabled,
  onApply,
}: {
  value: FontSizePt;
  disabled?: boolean;
  onApply: (size: FontSizePt) => void;
}) {
  const [input, setInput] = useState(String(value));
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setInput(String(value));
  }, [value]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function commitInput() {
    const parsed = clampFontSize(Number(input));
    setInput(String(parsed));
    onApply(parsed);
  }

  function pickPreset(size: FontSizePt) {
    setInput(String(size));
    onApply(size);
    setOpen(false);
  }

  return (
    <div ref={rootRef} className="relative flex items-stretch h-8">
      <input
        type="text"
        inputMode="numeric"
        disabled={disabled}
        value={input}
        onChange={(e) => setInput(e.target.value.replace(/[^\d]/g, ""))}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            commitInput();
          }
        }}
        onBlur={commitInput}
        aria-label="글자 크기"
        className="w-11 rounded-l border border-coolgray-30 border-r-0 bg-white px-1.5 text-sm text-center text-coolgray-90 outline-none focus:border-primary-60 disabled:opacity-50"
      />
      <button
        type="button"
        disabled={disabled}
        onMouseDown={(e) => e.preventDefault()}
        onClick={() => setOpen((v) => !v)}
        aria-label="글자 크기 목록"
        className="w-7 rounded-r border border-coolgray-30 bg-white text-[10px] text-coolgray-60 hover:bg-coolgray-10 disabled:opacity-50"
      >
        ▼
      </button>
      {open && (
        <ul className="absolute left-0 top-full z-20 mt-0.5 max-h-52 w-16 overflow-y-auto rounded border border-coolgray-30 bg-white py-1 shadow-md">
          {FONT_SIZE_PRESETS.map((pt) => (
            <li key={pt}>
              <button
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => pickPreset(pt)}
                className={`w-full px-2 py-1 text-left text-sm hover:bg-coolgray-10 ${
                  pt === value ? "bg-coolgray-10 font-medium" : ""
                }`}
              >
                {pt}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function EditorToolbar({
  disabled,
  fontSize,
  onBold,
  onFontSize,
  onUndo,
  onRedo,
  canUndo,
  canRedo,
  onToolbarMouseDown,
}: {
  disabled?: boolean;
  fontSize: FontSizePt;
  onBold: () => void;
  onFontSize: (size: FontSizePt) => void;
  onUndo: () => void;
  onRedo: () => void;
  canUndo: boolean;
  canRedo: boolean;
  onToolbarMouseDown: (e: React.MouseEvent) => void;
}) {
  return (
    <div
      className="flex items-center gap-2 px-2 py-1.5 border-b border-coolgray-20 bg-coolgray-10 shrink-0"
      onMouseDown={onToolbarMouseDown}
    >
      <button
        type="button"
        disabled={disabled || !canUndo}
        onClick={onUndo}
        title="되돌리기 (Ctrl+Z)"
        aria-label="되돌리기"
        className="min-w-8 h-8 px-2 rounded border border-coolgray-30 bg-white text-sm text-coolgray-80 hover:border-coolgray-50 disabled:opacity-40"
      >
        ↶
      </button>
      <button
        type="button"
        disabled={disabled || !canRedo}
        onClick={onRedo}
        title="다시 실행 (Ctrl+Y)"
        aria-label="다시 실행"
        className="min-w-8 h-8 px-2 rounded border border-coolgray-30 bg-white text-sm text-coolgray-80 hover:border-coolgray-50 disabled:opacity-40"
      >
        ↷
      </button>
      <span className="w-px h-6 bg-coolgray-30 shrink-0" aria-hidden />
      <button
        type="button"
        disabled={disabled}
        onClick={onBold}
        title="굵게"
        aria-label="굵게"
        className="min-w-8 h-8 px-2 rounded border border-coolgray-30 bg-white hover:border-coolgray-50 disabled:opacity-50"
      >
        <span className="text-base font-bold text-coolgray-90 leading-none">가</span>
      </button>
      <FontSizeCombo value={fontSize} disabled={disabled} onApply={onFontSize} />
      <span className="text-[11px] text-coolgray-60 ml-auto hidden sm:inline">
        Ctrl+Z/Y · 드래그 후 굵게·크기
      </span>
    </div>
  );
}

export function RichTextEditor({
  value,
  onChange,
  disabled = false,
  readOnly = false,
  minHeight = "120px",
  layout = "full",
  fill = false,
}: RichTextEditorProps) {
  const editorRef = useRef<HTMLDivElement>(null);
  const closingEditorRef = useRef<HTMLDivElement>(null);
  const savedRangeRef = useRef<Range | null>(null);
  const activeSurfaceRef = useRef<EditorSurface>("body");
  const savedValueRef = useRef("");
  const initializedRef = useRef(false);
  const closingInitializedRef = useRef(false);
  const [fontSize, setFontSize] = useState<FontSizePt>(DEFAULT_FONT_SIZE);
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);

  const history = useEditorHistory(value);
  const { closing: standardClosing } = useMemo(() => splitStandardClosing(value), [value]);
  const closingText = standardClosing ?? STANDARD_CLOSING;

  const toEditorMarkers = useCallback(
    (markers: string) =>
      layout === "export-preview" ? splitStandardClosing(markers).body : markers,
    [layout],
  );

  const readClosingMarkers = useCallback(() => {
    if (layout !== "export-preview" || !closingEditorRef.current) {
      return closingText;
    }
    return htmlToMarkers(closingEditorRef.current.innerHTML).trim() || closingText;
  }, [closingText, layout]);

  const toStoredMarkers = useCallback(
    (bodyMarkers: string, closingOverride?: string | null) => {
      if (layout !== "export-preview") return bodyMarkers;
      const closing = closingOverride ?? readClosingMarkers();
      return mergeWithStandardClosing(bodyMarkers, closing);
    },
    [layout, readClosingMarkers],
  );

  const refreshHistoryFlags = useCallback(() => {
    setCanUndo(history.canUndo());
    setCanRedo(history.canRedo());
  }, [history]);

  const toEditorHtml = useCallback(
    (markers: string) => {
      const body = toEditorMarkers(markers);
      return layout === "export-preview" ? exportPreviewBodyToHtml(body) : markersToHtml(body);
    },
    [layout, toEditorMarkers],
  );

  const applyMarkersToEditor = useCallback(
    (markers: string, notifyParent: boolean) => {
      if (editorRef.current) {
        editorRef.current.innerHTML = toEditorHtml(markers);
      }
      if (layout === "export-preview" && closingEditorRef.current) {
        const { closing } = splitStandardClosing(markers);
        closingEditorRef.current.innerHTML = markersToHtml(closing ?? STANDARD_CLOSING);
        closingInitializedRef.current = true;
      }
      savedValueRef.current = markers;
      if (notifyParent) onChange(markers);
    },
    [layout, onChange, toEditorHtml],
  );

  const bodyMarkersFromEditor = useCallback(() => {
    if (!editorRef.current) return "";
    const html = editorRef.current.innerHTML;
    return layout === "export-preview" ? htmlToMarkersExportPreview(html) : htmlToMarkers(html);
  }, [layout]);

  const syncFromDom = useCallback(() => {
    if (!editorRef.current || history.isApplying()) return;
    const bodyMarkers = bodyMarkersFromEditor();
    const markers = toStoredMarkers(bodyMarkers);
    if (markers === savedValueRef.current) return;
    history.recordChange(markers);
    savedValueRef.current = markers;
    onChange(markers);
    refreshHistoryFlags();
  }, [bodyMarkersFromEditor, history, onChange, refreshHistoryFlags, toStoredMarkers]);

  const syncClosingFromDom = useCallback(() => {
    if (!closingEditorRef.current || history.isApplying()) return;
    const closingMarkers = htmlToMarkers(closingEditorRef.current.innerHTML).trim();
    const bodyMarkers = editorRef.current ? bodyMarkersFromEditor() : splitStandardClosing(savedValueRef.current).body;
    const markers = mergeWithStandardClosing(bodyMarkers, closingMarkers || STANDARD_CLOSING);
    if (markers === savedValueRef.current) return;
    history.recordChange(markers);
    savedValueRef.current = markers;
    onChange(markers);
    refreshHistoryFlags();
  }, [bodyMarkersFromEditor, history, onChange, refreshHistoryFlags, toStoredMarkers]);

  const syncActiveSurfaceFromDom = useCallback(() => {
    if (activeSurfaceRef.current === "closing") {
      syncClosingFromDom();
    } else {
      syncFromDom();
    }
  }, [syncClosingFromDom, syncFromDom]);

  const saveSelection = useCallback((surface: EditorSurface = activeSurfaceRef.current) => {
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0) return;
    const root = surface === "closing" ? closingEditorRef.current : editorRef.current;
    if (!root) return;
    const range = sel.getRangeAt(0);
    if (!root.contains(range.commonAncestorContainer)) return;
    activeSurfaceRef.current = surface;
    savedRangeRef.current = range.cloneRange();
  }, []);

  const restoreSelection = useCallback(() => {
    const range = savedRangeRef.current;
    const root =
      activeSurfaceRef.current === "closing" ? closingEditorRef.current : editorRef.current;
    if (!range || !root) return false;
    root.focus();
    const sel = window.getSelection();
    if (!sel) return false;
    sel.removeAllRanges();
    sel.addRange(range);
    return !sel.isCollapsed;
  }, []);

  const performUndo = useCallback(() => {
    if (disabled) return;
    const prev = history.undo(savedValueRef.current);
    if (prev === null) return;
    history.runApplying(() => {
      applyMarkersToEditor(prev, true);
      editorRef.current?.focus();
    });
    refreshHistoryFlags();
  }, [applyMarkersToEditor, disabled, history, refreshHistoryFlags]);

  const performRedo = useCallback(() => {
    if (disabled) return;
    const next = history.redo(savedValueRef.current);
    if (next === null) return;
    history.runApplying(() => {
      applyMarkersToEditor(next, true);
      editorRef.current?.focus();
    });
    refreshHistoryFlags();
  }, [applyMarkersToEditor, disabled, history, refreshHistoryFlags]);

  useEffect(() => {
    if (!editorRef.current || history.isApplying()) return;

    if (!initializedRef.current) {
      editorRef.current.innerHTML = toEditorHtml(value);
      savedValueRef.current = value;
      history.resetHistory(value);
      initializedRef.current = true;
      refreshHistoryFlags();
      return;
    }

    if (value !== savedValueRef.current) {
      editorRef.current.innerHTML = toEditorHtml(value);
      savedValueRef.current = value;
      history.resetHistory(value);
      refreshHistoryFlags();
      if (layout === "export-preview") {
        closingInitializedRef.current = false;
      }
    }
  }, [value, history, layout, refreshHistoryFlags, toEditorHtml]);

  useEffect(() => {
    if (layout !== "export-preview" || !closingEditorRef.current || history.isApplying()) return;
    if (value === savedValueRef.current && closingInitializedRef.current) return;
    const { closing } = splitStandardClosing(value);
    closingEditorRef.current.innerHTML = markersToHtml(closing ?? STANDARD_CLOSING);
    closingInitializedRef.current = true;
  }, [value, layout, history]);

  function wrapRangeWithFontSize(range: Range, size: FontSizePt) {
    const span = document.createElement("span");
    span.style.fontSize = `${size}px`;
    span.dataset.fontPt = String(size);

    try {
      range.surroundContents(span);
    } catch {
      const fragment = range.extractContents();
      span.appendChild(fragment);
      range.insertNode(span);
    }

    const sel = window.getSelection();
    if (sel) {
      sel.removeAllRanges();
      const next = document.createRange();
      next.selectNodeContents(span);
      sel.addRange(next);
      savedRangeRef.current = next.cloneRange();
    }
  }

  function applyBold() {
    if (disabled) return;
    const root =
      activeSurfaceRef.current === "closing" ? closingEditorRef.current : editorRef.current;
    if (!root) return;
    if (!restoreSelection()) return;
    document.execCommand("bold");
    saveSelection(activeSurfaceRef.current);
    syncActiveSurfaceFromDom();
  }

  function applyFontSize(size: FontSizePt) {
    const pt = clampFontSize(size);
    setFontSize(pt);
    if (disabled) return;
    const root =
      activeSurfaceRef.current === "closing" ? closingEditorRef.current : editorRef.current;
    if (!root) return;
    if (!restoreSelection()) return;

    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0) return;
    wrapRangeWithFontSize(sel.getRangeAt(0), pt);
    syncActiveSurfaceFromDom();
  }

  function handleToolbarMouseDown(e: React.MouseEvent) {
    const target = e.target as HTMLElement;
    if (target.closest("input")) return;
    e.preventDefault();
  }

  function handleEditorKeyDown(e: React.KeyboardEvent) {
    if (disabled) return;
    const mod = e.ctrlKey || e.metaKey;
    if (!mod) return;

    if (e.key === "z" && !e.shiftKey) {
      e.preventDefault();
      performUndo();
    } else if (e.key === "y" || (e.key === "z" && e.shiftKey) || (e.key === "Z" && e.shiftKey)) {
      e.preventDefault();
      performRedo();
    }
  }

  const editorScrollClass =
    fill && layout === "export-preview"
      ? "min-w-0 outline-none"
      : "min-w-0 min-h-0 flex-1 overflow-y-auto outline-none";

  const editorClassName =
    `${editorScrollClass} px-2 py-2 text-[12px] leading-[2] text-coolgray-90 [&_strong]:font-bold` +
    (layout === "export-preview"
      ? " [&_.er-export-item-row]:grid [&_.er-export-item-row]:grid-cols-[minmax(120px,32%)_1fr] [&_.er-export-item-row]:gap-4 [&_.er-export-item-row]:items-start [&_.er-export-item-row]:mb-5 [&_.er-export-img-slot]:rounded-lg [&_.er-export-img-slot]:border [&_.er-export-img-slot]:border-dashed [&_.er-export-img-slot]:border-coolgray-40 [&_.er-export-img-slot]:bg-[#f5f0e8] [&_.er-export-img-slot]:min-h-[120px] [&_.er-export-img-slot]:flex [&_.er-export-img-slot]:items-center [&_.er-export-img-slot]:justify-center [&_.er-export-img-slot]:text-xs [&_.er-export-img-slot]:text-center [&_.er-export-img-slot]:text-coolgray-60 [&_.er-export-img-slot]:px-2 [&_.er-export-img-slot]:select-none"
      : "") +
    (disabled && !readOnly ? " disabled:opacity-60" : "");

  const editor = (
    <div
      ref={editorRef}
      contentEditable={!disabled && !readOnly}
      suppressContentEditableWarning
      onInput={syncFromDom}
      onBlur={syncFromDom}
      onFocus={() => {
        activeSurfaceRef.current = "body";
      }}
      onMouseUp={() => saveSelection("body")}
      onKeyUp={() => saveSelection("body")}
      onKeyDown={handleEditorKeyDown}
      className={editorClassName}
      style={fill ? undefined : { minHeight }}
      aria-label="번역문 편집"
    />
  );

  return (
    <div
      className={`rounded-lg border border-coolgray-30 overflow-hidden bg-white flex flex-col ${
        fill ? "h-full min-h-0" : ""
      } ${layout === "export-preview" ? EASY_READ_COURT_FONT_CLASS : ""}`}
    >
      {!readOnly && (
        <EditorToolbar
          disabled={disabled}
          fontSize={fontSize}
          onBold={applyBold}
          onFontSize={applyFontSize}
          onUndo={performUndo}
          onRedo={performRedo}
          canUndo={canUndo}
          canRedo={canRedo}
          onToolbarMouseDown={handleToolbarMouseDown}
        />
      )}
      {layout === "export-preview" ? (
        <div className={`flex min-h-0 flex-col ${fill ? "min-h-0 flex-1 overflow-hidden" : ""}`}>
          <div
            className={`min-h-0 p-3 ${fill ? "flex-1 overflow-y-auto overscroll-contain" : "max-h-[60vh] overflow-y-auto"}`}
          >
            {editor}
          </div>
          <div className="shrink-0 border-t border-coolgray-20 px-3 py-3">
            <div
              ref={closingEditorRef}
              contentEditable={!disabled && !readOnly}
              suppressContentEditableWarning
              onInput={syncClosingFromDom}
              onBlur={syncClosingFromDom}
              onFocus={() => {
                activeSurfaceRef.current = "closing";
              }}
              onMouseUp={() => saveSelection("closing")}
              onKeyUp={() => saveSelection("closing")}
              className="min-w-0 text-[12px] leading-[2] text-coolgray-90 outline-none [&_strong]:font-bold disabled:opacity-60"
              aria-label="마무리 문장 편집"
            />
          </div>
        </div>
      ) : (
        editor
      )}
    </div>
  );
}
