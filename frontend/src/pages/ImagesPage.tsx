/**
 * 그림 배치 페이지 (워크플로 4단계) — Figma 그림 80% ERAI UI.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import type { ImageCatalogItem, ImagePlacement, TranslationSegment } from "../api/client";
import {
  detectImagePlacements,
  getImageCatalog,
  searchWebImages,
  updateTranslation,
} from "../api/client";
import { DraggableCatalogItem, EasyReadDocumentView } from "../components/EasyReadDocumentView";
import { PromptBar } from "../components/PromptBar";
import { WorkflowLayout, WorkflowTwoPaneColumn, WorkflowTwoPaneGrid } from "../components/ui/WorkflowLayout";
import { IconSpinner } from "../components/ui/icons";
import { buildEnsureContext, loadDocumentWithRecovery } from "../utils/documentLoader";
import { filterPlacementsRespectingClears } from "../utils/imageSlotPrefs";
import { sanitizeTranslationText } from "../utils/sanitizeTranslation";
import { filterPlacementsForExport } from "../utils/translationSections";
import { useDebouncedSave, useFlushSaveOnUnmount } from "../utils/useDebouncedSave";
import {
  getWorkflowSnapshot,
  resolveTranslationSegments,
  saveWorkflowSnapshot,
} from "../utils/workflowCache";

function sanitizeSegments(segments: TranslationSegment[]): TranslationSegment[] {
  return segments.map((s) => {
    const easy_text = s.easy_text ? sanitizeTranslationText(s.easy_text) : s.easy_text;
    return {
      ...s,
      easy_text,
      image_placements: filterPlacementsForExport(
        easy_text ?? "",
        s.image_placements ?? [],
      ),
    };
  });
}

function segmentsToText(segments: TranslationSegment[]): string {
  return segments.map((s) => s.easy_text).filter(Boolean).join("\n\n");
}

function placementsChanged(before: ImagePlacement[], after: ImagePlacement[]): boolean {
  if (before.length !== after.length) return true;
  const keys = new Set(before.map((p) => `${p.line_index}:${p.image_file}:${p.auto_filled ? 1 : 0}`));
  return after.some((p) => !keys.has(`${p.line_index}:${p.image_file}:${p.auto_filled ? 1 : 0}`));
}

export function ImagesPage() {
  const { id } = useParams<{ id: string }>();
  const [segments, setSegments] = useState<TranslationSegment[]>([]);
  const [filename, setFilename] = useState("");
  const [error, setError] = useState("");
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved">("idle");
  const [catalogQuery, setCatalogQuery] = useState("");
  const [catalogItems, setCatalogItems] = useState<ImageCatalogItem[]>([]);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [promptLoading, setPromptLoading] = useState(false);
  const [webSearchActive, setWebSearchActive] = useState(false);
  const [catalogVisibleCount, setCatalogVisibleCount] = useState(48);
  const [autoPlacing, setAutoPlacing] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const catalogScrollRef = useRef<HTMLDivElement>(null);

  const CATALOG_PAGE_SIZE = 48;

  const mainSegment = segments[0];
  const translationText = useMemo(() => segmentsToText(segments), [segments]);
  const placements = mainSegment?.image_placements ?? [];

  const load = useCallback(async () => {
    if (!id) return;
    setError("");
    setPageLoading(true);
    const workflow = getWorkflowSnapshot(id);
    const cachedSegs = workflow?.translation_segments ?? [];
    if (cachedSegs.length) {
      setSegments(sanitizeSegments(cachedSegs));
      if (workflow?.filename) setFilename(workflow.filename);
    }

    try {
      const doc = await loadDocumentWithRecovery(id);
      setFilename(doc.filename);
      let segs = sanitizeSegments(resolveTranslationSegments(id, doc.translation_segments));
      const main = segs[0];
      if (main?.easy_text) {
        setAutoPlacing(true);
        try {
          const ensurePayload = buildEnsureContext(id);
          const clearedExisting = filterPlacementsRespectingClears(
            id,
            main.image_placements ?? [],
          );
          let filled = await detectImagePlacements(id, {
            ...(ensurePayload ?? {}),
            translationText: main.easy_text,
            existingPlacements: clearedExisting,
          });
          filled = filterPlacementsRespectingClears(id, filled);
          if (placementsChanged(clearedExisting, filled)) {
            segs = segs.map((s, i) =>
              i === 0 ? { ...s, image_placements: filled } : s,
            );
          } else if (clearedExisting.length !== (main.image_placements ?? []).length) {
            segs = segs.map((s, i) =>
              i === 0 ? { ...s, image_placements: clearedExisting } : s,
            );
          }
        } catch (err) {
          console.error("auto-fill image placements failed", err);
          setError(
            err instanceof Error
              ? `그림 자동 배치 실패: ${err.message}`
              : "그림 자동 배치에 실패했습니다.",
          );
        } finally {
          setAutoPlacing(false);
        }
      }
      setSegments(segs);
      if (segs.length) {
        saveWorkflowSnapshot(id, { translation_segments: segs, filename: doc.filename });
      }
      const updatedMain = segs[0];
      if (
        updatedMain?.image_placements?.length &&
        updatedMain.image_placements.some((p) => p.auto_filled)
      ) {
        try {
          const ensurePayload = buildEnsureContext(id);
          if (ensurePayload) {
            await updateTranslation(id, segs, ensurePayload);
          } else {
            await updateTranslation(id, segs);
          }
        } catch (err) {
          console.error("save auto-filled placements failed", err);
        }
      }
    } catch (err) {
      const cachedSegments = workflow?.translation_segments ?? [];
      if (cachedSegments.length) {
        setFilename(workflow?.filename ?? "");
        setSegments(sanitizeSegments(cachedSegments));
        return;
      }
      setError(err instanceof Error ? err.message : "문서를 불러오지 못했습니다");
    } finally {
      setPageLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load().catch(console.error);
  }, [load]);

  useEffect(() => {
    if (webSearchActive) return;
    let cancelled = false;
    setCatalogLoading(true);
    setCatalogVisibleCount(CATALOG_PAGE_SIZE);
    getImageCatalog(catalogQuery)
      .then((data) => {
        if (!cancelled) setCatalogItems(data);
      })
      .catch(console.error)
      .finally(() => {
        if (!cancelled) setCatalogLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [catalogQuery, webSearchActive]);

  const visibleCatalogItems = useMemo(
    () => catalogItems.slice(0, catalogVisibleCount),
    [catalogItems, catalogVisibleCount],
  );

  const handleCatalogScroll = useCallback(() => {
    const el = catalogScrollRef.current;
    if (!el) return;
    if (el.scrollTop + el.clientHeight >= el.scrollHeight - 80) {
      setCatalogVisibleCount((prev) =>
        Math.min(prev + CATALOG_PAGE_SIZE, catalogItems.length),
      );
    }
  }, [catalogItems.length]);

  const persistSegments = useCallback(
    async (nextSegments: TranslationSegment[]) => {
      if (!id || nextSegments.length === 0) return;
      setSaveStatus("saving");
      try {
        const ensure = buildEnsureContext(id);
        if (ensure) {
          await updateTranslation(id, nextSegments, ensure);
        } else {
          await updateTranslation(id, nextSegments);
        }
        saveWorkflowSnapshot(id, { translation_segments: nextSegments });
        setSaveStatus("saved");
      } catch (err) {
        setSaveStatus("idle");
        setError(err instanceof Error ? err.message : "저장 실패");
      }
    },
    [id],
  );

  const persistTranslation = useCallback(async () => {
    await persistSegments(segments);
  }, [persistSegments, segments]);

  const { flush: flushTranslationSave } = useDebouncedSave(segments, persistTranslation);
  useFlushSaveOnUnmount(flushTranslationSave);

  async function applyImagePrompt() {
    if (!prompt.trim()) return;
    setPromptLoading(true);
    setError("");
    setWebSearchActive(true);
    try {
      const results = await searchWebImages(prompt.trim());
      setCatalogItems(results.slice(0, 40));
      if (results.length === 0) {
        setError("웹에서 찾은 그림이 없습니다. 다른 키워드로 시도해 보세요.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "웹 그림 검색 실패");
    } finally {
      setPromptLoading(false);
    }
  }

  function handleCatalogSearchChange(value: string) {
    setCatalogQuery(value);
    setWebSearchActive(false);
    setError("");
  }

  function editPlacements(next: ImagePlacement[]) {
    setSegments((prev) => {
      if (!prev.length) return prev;
      const updated = prev.map((s, i) =>
        i === 0 ? { ...s, image_placements: next } : s,
      );
      if (id) {
        saveWorkflowSnapshot(id, { translation_segments: updated });
      }
      void persistSegments(updated);
      return updated;
    });
  }

  const showPlacementBusy = pageLoading || autoPlacing;

  const filenameLabel = [
    filename || "파일명",
    saveStatus === "saving" ? "저장 중..." : saveStatus === "saved" ? "저장됨" : "",
  ]
    .filter(Boolean)
    .join(" · ");

  const translationPlaceholder = translationText.trim() ? "" : "번역 결과";

  return (
    <WorkflowLayout
      step="images"
      docId={id}
      headerVariant="compact"
      projectTitle={
        <>
          ER<span className="text-primary-60">AI</span>
        </>
      }
      filename={filenameLabel}
      error={error || undefined}
    >
      <WorkflowTwoPaneGrid>
        <WorkflowTwoPaneColumn className="gap-3">
          <p className="shrink-0 text-center text-base text-primary-90">번역문</p>
          <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden border border-coolgray-40 bg-white">
            {showPlacementBusy ? (
              <div className="flex min-h-[200px] flex-1 flex-col items-center justify-center gap-3 px-4 py-8 text-primary-60 text-sm">
                <IconSpinner className="size-10" />
                {autoPlacing
                  ? "AI가 그림을 배치하고 있습니다..."
                  : "번역문을 불러오는 중..."}
              </div>
            ) : segments.length === 0 ? (
              <pre className="flex min-h-0 w-full flex-1 items-center justify-center overflow-auto px-4 py-3 text-center text-base leading-relaxed whitespace-pre-wrap text-coolgray-60">
                {translationPlaceholder}
              </pre>
            ) : (
              <div className="min-h-0 flex-1 overflow-auto px-4 py-4">
                <EasyReadDocumentView
                  text={translationText}
                  placements={placements}
                  mode="images"
                  docId={id}
                  fill
                  onPlacementsChange={editPlacements}
                />
              </div>
            )}
          </div>
        </WorkflowTwoPaneColumn>

        <WorkflowTwoPaneColumn side="right">
          <p className="shrink-0 text-center text-base text-primary-90">그림 DB</p>

          <div className="flex-1 min-h-0 flex flex-col border border-coolgray-40 overflow-hidden bg-coolgray-10">
            <input
              type="search"
              placeholder="제목 또는 파일명 검색"
              value={catalogQuery}
              onChange={(e) => handleCatalogSearchChange(e.target.value)}
              className="w-full h-12 px-4 bg-coolgray-10 border-b border-coolgray-30 text-base text-coolgray-90 placeholder:text-coolgray-60 outline-none focus:border-primary-60 shrink-0"
            />
            <div
              ref={catalogScrollRef}
              onScroll={handleCatalogScroll}
              className="flex-1 min-h-0 overflow-auto px-4 py-3"
            >
              {webSearchActive && (
                <p className="text-xs text-primary-60 mb-2 text-center">
                  AI 프롬프트 웹 검색 결과 · 그림 DB로 돌아가려면 위 검색창을 사용하세요
                </p>
              )}
              {catalogLoading ? (
                <p className="text-base text-coolgray-60 text-center py-8">불러오는 중...</p>
              ) : catalogItems.length === 0 ? (
                <p className="text-base text-coolgray-60 text-center py-8">검색 결과가 없습니다.</p>
              ) : (
                <>
                  <ul className="grid grid-cols-2 gap-3">
                    {visibleCatalogItems.map((item) => (
                      <DraggableCatalogItem key={item.image_file} item={item}>
                        <img
                          src={item.url}
                          alt={item.title}
                          className="mx-auto h-24 w-full object-contain pointer-events-none"
                          loading="lazy"
                        />
                        <p className="mt-2 text-xs text-coolgray-90 line-clamp-2 text-center pointer-events-none">
                          {item.title}
                        </p>
                      </DraggableCatalogItem>
                    ))}
                  </ul>
                  {visibleCatalogItems.length < catalogItems.length && (
                    <p className="text-xs text-coolgray-60 text-center py-3">
                      {visibleCatalogItems.length} / {catalogItems.length} · 스크롤하면 더 불러옵니다
                    </p>
                  )}
                </>
              )}
            </div>
          </div>

          <div className="shrink-0">
            <PromptBar
              value={prompt}
              onChange={setPrompt}
              onSubmit={applyImagePrompt}
              loading={promptLoading}
              loadingLabel="그림 검색 중..."
              placeholder="찾을 그림을 설명하세요 (예: 각하, 징역, 무죄)"
            />
          </div>
        </WorkflowTwoPaneColumn>
      </WorkflowTwoPaneGrid>
    </WorkflowLayout>
  );
}
