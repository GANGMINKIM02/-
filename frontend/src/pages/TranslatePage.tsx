/**
 * 이지리드 번역 편집 페이지 (워크플로 3단계) — Figma 번역 80% ERAI UI.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import type { TranslationSegment } from "../api/client";
import {
  refineTranslation,
  translate,
  updateTranslation,
} from "../api/client";
import { PromptBar } from "../components/PromptBar";
import { RichTextEditor } from "../components/RichTextEditor";
import { EasyReadDocumentView } from "../components/EasyReadDocumentView";
import { WorkflowLayout, WorkflowTwoPaneColumn, WorkflowTwoPaneGrid } from "../components/ui/WorkflowLayout";
import { buildEnsureContext, loadDocumentWithRecovery } from "../utils/documentLoader";
import { sanitizeTranslationText } from "../utils/sanitizeTranslation";
import { useDebouncedSave, useFlushSaveOnUnmount } from "../utils/useDebouncedSave";
import {
  getWorkflowSnapshot,
  resolveSummary,
  resolveTranslationSegments,
  saveWorkflowSnapshot,
} from "../utils/workflowCache";

function sanitizeSegments(segments: TranslationSegment[]): TranslationSegment[] {
  return segments.map((s) => ({
    ...s,
    easy_text: s.easy_text ? sanitizeTranslationText(s.easy_text) : s.easy_text,
  }));
}

function segmentsToText(segments: TranslationSegment[]): string {
  return segments.map((s) => s.easy_text).filter(Boolean).join("\n\n");
}

function mergeRefinedSegments(
  doc: { translation_segments: TranslationSegment[]; translation_text?: string | null },
): TranslationSegment[] {
  const segs = sanitizeSegments(doc.translation_segments);
  const text = sanitizeTranslationText(
    doc.translation_text ?? segmentsToText(segs),
  );
  if (!text.trim()) return segs;
  const base = segs[0] ?? {
    id: "1",
    original: "",
    easy_text: "",
    source: "solar" as const,
  };
  return [
    {
      ...base,
      easy_text: text,
      source: "solar" as const,
      image_placements: base.image_placements ?? [],
    },
  ];
}

export function TranslatePage() {
  const { id } = useParams<{ id: string }>();
  const [summary, setSummary] = useState("");
  const [segments, setSegments] = useState<TranslationSegment[]>([]);
  const [prompt, setPrompt] = useState("");
  const [generating, setGenerating] = useState(false);
  const [refining, setRefining] = useState(false);
  const [error, setError] = useState("");
  const [filename, setFilename] = useState("");
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved">("idle");

  const translationText = useMemo(() => segmentsToText(segments), [segments]);

  const load = useCallback(async () => {
    if (!id) return;
    setError("");
    const workflow = getWorkflowSnapshot(id);
    const ensure = buildEnsureContext(id);

    try {
      const doc = await loadDocumentWithRecovery(id);
      setFilename(doc.filename);
      setSummary(resolveSummary(id, doc.summary));
      const resolved = resolveTranslationSegments(id, doc.translation_segments);
      if (resolved.length) {
        const segs = sanitizeSegments(resolved);
        setSegments(segs);
        saveWorkflowSnapshot(id, {
          translation_segments: segs,
          translation_text: doc.translation_text ?? workflow?.translation_text,
          filename: doc.filename,
        });
      } else {
        setGenerating(true);
        try {
          const updated = await translate(id, ensure);
          const segs = sanitizeSegments(updated.translation_segments);
          setSegments(segs);
          saveWorkflowSnapshot(id, {
            translation_segments: segs,
            translation_text: updated.translation_text ?? undefined,
            filename: updated.filename,
          });
        } catch (err) {
          setError(err instanceof Error ? err.message : "번역 생성 실패");
        } finally {
          setGenerating(false);
        }
      }
    } catch (err) {
      const cachedSegments = workflow?.translation_segments ?? [];
      if (cachedSegments.length) {
        setFilename(workflow?.filename ?? "");
        setSummary(workflow?.summary ?? "");
        setSegments(sanitizeSegments(cachedSegments));
        return;
      }
      setError(err instanceof Error ? err.message : "문서를 불러오지 못했습니다");
    }
  }, [id]);

  useEffect(() => {
    load().catch(console.error);
  }, [load]);

  const persistTranslation = useCallback(async () => {
    if (!id || segments.length === 0) return;
    setSaveStatus("saving");
    try {
      const ensure = buildEnsureContext(id);
      if (ensure) {
        await updateTranslation(id, segments, {
          ...ensure,
          summary: summary || ensure.summary,
        });
      } else {
        await updateTranslation(id, segments);
      }
      saveWorkflowSnapshot(id, {
        translation_segments: segments,
        translation_text: segmentsToText(segments),
      });
      setSaveStatus("saved");
    } catch (err) {
      setSaveStatus("idle");
      setError(err instanceof Error ? err.message : "저장 실패");
    }
  }, [id, segments, summary]);

  const { flush: flushTranslationSave } = useDebouncedSave(segments, persistTranslation);
  useFlushSaveOnUnmount(flushTranslationSave);

  function editTranslationText(text: string) {
    if (segments.length === 0) return;
    if (segments.length === 1) {
      setSegments([{ ...segments[0], easy_text: text, source: "manual" as const }]);
      return;
    }
    setSegments(
      segments.map((s, i) =>
        i === 0 ? { ...s, easy_text: text, source: "manual" as const } : s,
      ),
    );
  }

  async function applyPrompt() {
    if (!id || !prompt.trim() || segments.length === 0) return;
    setRefining(true);
    setError("");
    try {
      await flushTranslationSave();
      const doc = await refineTranslation(id, prompt, segments);
      const segs = mergeRefinedSegments(doc);
      setSegments(segs);
      saveWorkflowSnapshot(id, {
        translation_segments: segs,
        translation_text: segmentsToText(segs),
      });
      setPrompt("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI 수정 실패");
    } finally {
      setRefining(false);
    }
  }

  const filenameLabel = [
    filename || "파일명",
    saveStatus === "saving" ? "저장 중..." : saveStatus === "saved" ? "저장됨" : "",
  ]
    .filter(Boolean)
    .join(" · ");

  const summaryDisplay = summary.trim() || "";
  const summaryPlaceholder = summaryDisplay ? "" : "요약 결과";

  const translationPlaceholder =
    generating && segments.length === 0 ? "번역 생성 중..." : translationText.trim() ? "" : "번역 결과";

  return (
    <WorkflowLayout
      step="translate"
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
          <p className="shrink-0 text-center text-base text-primary-90">요약문</p>
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden border border-coolgray-40 bg-coolgray-10">
            <div className="flex min-h-0 flex-1 flex-col overflow-hidden px-4 py-4">
              {!summaryDisplay.trim() ? (
                <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-lg border border-coolgray-30 bg-white">
                  <div className="flex flex-1 items-center justify-center px-4 text-center text-[12px] leading-[2] text-coolgray-60">
                    {summaryPlaceholder}
                  </div>
                </div>
              ) : (
                <RichTextEditor
                  value={summaryDisplay}
                  onChange={() => {}}
                  layout="full"
                  fill
                  readOnly
                />
              )}
            </div>
          </div>
        </WorkflowTwoPaneColumn>

        <WorkflowTwoPaneColumn side="right">
          <p className="shrink-0 text-center text-base text-primary-90">번역문</p>

          <div className="flex-1 min-h-0 flex flex-col border border-coolgray-40 overflow-hidden bg-coolgray-10 relative">
            {refining && (
              <div className="absolute inset-0 z-10 flex items-center justify-center bg-white/70 text-primary-60 text-sm gap-2">
                <span className="inline-block size-5 border-2 border-primary-60 border-t-transparent rounded-full animate-spin" />
                AI가 번역문을 수정하고 있습니다...
              </div>
            )}
            <div className="flex-1 min-h-0 flex flex-col overflow-hidden px-4 py-4">
              <EasyReadDocumentView
                text={translationText}
                mode="translate"
                fill
                placeholder={translationPlaceholder}
                disabled={(generating && segments.length === 0) || refining}
                onTextChange={editTranslationText}
              />
            </div>
          </div>

          <div className="shrink-0">
            <PromptBar
              value={prompt}
              onChange={setPrompt}
              onSubmit={applyPrompt}
              loading={refining}
              loadingLabel="번역 수정 중..."
            />
          </div>
        </WorkflowTwoPaneColumn>
      </WorkflowTwoPaneGrid>
    </WorkflowLayout>
  );
}
