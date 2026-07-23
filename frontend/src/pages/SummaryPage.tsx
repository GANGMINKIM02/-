/**
 * AI 요약 편집 페이지 (워크플로 2단계) — Figma 요약 80% UI.
 */
import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  getPage,
  refineSummary,
  summarize,
  updateSummary,
} from "../api/client";
import { PromptBar } from "../components/PromptBar";
import { RichTextEditor } from "../components/RichTextEditor";
import { PageNavigator } from "../components/PageNavigator";
import { WorkflowLayout, WorkflowTwoPaneColumn, WorkflowTwoPaneGrid } from "../components/ui/WorkflowLayout";
import {
  ensurePayload,
  getCachedUpload,
  summarizeFallbackBody,
} from "../utils/docCache";
import { loadDocumentWithRecovery } from "../utils/documentLoader";
import { getSourceObjectUrl } from "../utils/sourceStore";
import { useDebouncedSave, useFlushSaveOnUnmount } from "../utils/useDebouncedSave";
import {
  getWorkflowSnapshot,
  resolveSummary,
  saveWorkflowSnapshot,
} from "../utils/workflowCache";

function getFileExt(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot >= 0 ? name.slice(dot + 1).toLowerCase() : "";
}

function canPreviewSource(filename: string, mimeType?: string): boolean {
  const ext = getFileExt(filename);
  if (mimeType?.startsWith("image/")) return true;
  return ["pdf", "txt", "png", "jpg", "jpeg", "doc", "docx", "hwp", "hwpx"].includes(ext);
}

export function SummaryPage() {
  const { id } = useParams<{ id: string }>();
  const [originalPage, setOriginalPage] = useState("");
  const [sourcePreviewUrl, setSourcePreviewUrl] = useState<string | null>(null);
  const [sourceReady, setSourceReady] = useState(false);
  const [sourceFilename, setSourceFilename] = useState<string>("");
  const [pageNum, setPageNum] = useState(1);
  const [pageCount, setPageCount] = useState(1);
  const [summary, setSummary] = useState("");
  const [prompt, setPrompt] = useState("");
  const [generating, setGenerating] = useState(false);
  const [refining, setRefining] = useState(false);
  const [error, setError] = useState("");
  const [filename, setFilename] = useState("");
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved">("idle");

  async function loadDocumentWithRetry(docId: string) {
    return loadDocumentWithRecovery(docId);
  }

  const persistSummary = useCallback(async () => {
    if (!id || !summary.trim()) return;
    setSaveStatus("saving");
    try {
      const cached = getCachedUpload(id);
      await updateSummary(id, summary, ensurePayload(cached));
      saveWorkflowSnapshot(id, { summary });
      setSaveStatus("saved");
    } catch (err) {
      setSaveStatus("idle");
      setError(err instanceof Error ? err.message : "저장 실패");
    }
  }, [id, summary]);

  const { flush: flushSummarySave } = useDebouncedSave(summary, persistSummary);
  useFlushSaveOnUnmount(flushSummarySave);

  const load = useCallback(async () => {
    if (!id) return;
    setError("");
    const cached = getCachedUpload(id);
    const workflow = getWorkflowSnapshot(id);

    try {
      const doc = await loadDocumentWithRetry(id);
      setFilename(doc.filename);
      setPageCount(doc.page_count);
      const existingSummary = resolveSummary(id, doc.summary);
      setSummary(existingSummary);
      if (existingSummary) {
        saveWorkflowSnapshot(id, { summary: existingSummary, filename: doc.filename });
      } else {
        setGenerating(true);
        try {
          const updated = await summarize(
            id,
            false,
            cached ? summarizeFallbackBody(cached) : undefined,
          );
          const text = updated.summary || "";
          setSummary(text);
          if (text) {
            saveWorkflowSnapshot(id, { summary: text, filename: updated.filename });
          }
        } catch (err) {
          setError(err instanceof Error ? err.message : "요약 생성 실패");
        } finally {
          setGenerating(false);
        }
      }
    } catch {
      const fallbackSummary = resolveSummary(id, workflow?.summary);
      if (fallbackSummary) {
        setFilename(workflow?.filename || cached?.filename || "");
        setPageCount(cached?.page_count ?? 1);
        setSummary(fallbackSummary);
        return;
      }
      if (cached) {
        setFilename(cached.filename);
        setPageCount(cached.page_count);
        setGenerating(true);
        try {
          const updated = await summarize(id, false, summarizeFallbackBody(cached));
          const text = updated.summary || "";
          setSummary(text);
          if (text) {
            saveWorkflowSnapshot(id, { summary: text, filename: cached.filename });
          }
        } catch (err) {
          setError(err instanceof Error ? err.message : "요약 생성 실패");
        } finally {
          setGenerating(false);
        }
      } else {
        setError("문서를 불러오지 못했습니다. 잠시 후 자동으로 다시 시도하거나 새로고침해 주세요.");
      }
    }
  }, [id]);

  useEffect(() => {
    load().catch(console.error);
  }, [load]);

  useEffect(() => {
    if (!id) return;
    const cached = getCachedUpload(id);
    const previewName = filename || cached?.filename || "";
    setSourceFilename(previewName);
    setSourceReady(false);
    setSourcePreviewUrl(null);

    let ownedBlobUrl: string | null = null;
    let cancelled = false;

    const loadTextFallback = () => {
      if (cached?.pages?.length) {
        setOriginalPage(cached.pages[pageNum - 1] || "");
        return;
      }
      getPage(id, pageNum)
        .then(setOriginalPage)
        .catch(() => setOriginalPage("(페이지를 불러오지 못했습니다)"));
    };

    const useClientPreview = (url: string, revokeOnCleanup = false) => {
      if (cancelled) return;
      if (revokeOnCleanup) ownedBlobUrl = url;
      setSourcePreviewUrl(url);
      setSourceReady(true);
    };

    (async () => {
      if (previewName && canPreviewSource(previewName, cached?.source_mime_type)) {
        const storedUrl = await getSourceObjectUrl(id);
        if (storedUrl) {
          useClientPreview(storedUrl, true);
          return;
        }
        if (cached?.source_blob_url) {
          useClientPreview(cached.source_blob_url);
          return;
        }
      }

      try {
        await loadDocumentWithRecovery(id);
      } catch {
        loadTextFallback();
        return;
      }

      const serverUrl = `/api/documents/${id}/source`;
      try {
        const res = await fetch(serverUrl, { method: "HEAD" });
        if (res.ok) {
          useClientPreview(serverUrl);
          return;
        }
      } catch {
        /* fall through */
      }

      if (cancelled) return;
      setSourcePreviewUrl(null);
      loadTextFallback();
    })();

    return () => {
      cancelled = true;
      if (ownedBlobUrl) {
        URL.revokeObjectURL(ownedBlobUrl);
      }
    };
  }, [id, pageNum, filename]);

  async function applyPrompt() {
    if (!id || !prompt.trim() || !summary.trim()) return;
    setRefining(true);
    setError("");
    try {
      await flushSummarySave();
      const doc = await refineSummary(id, prompt, summary);
      const text = doc.summary || "";
      setSummary(text);
      if (text) saveWorkflowSnapshot(id, { summary: text });
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

  const summaryPlaceholder = generating
    ? "요약 생성 중..."
    : summary.trim()
      ? ""
      : "요약 결과";

  return (
    <WorkflowLayout
      step="summary"
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
        <WorkflowTwoPaneColumn className="h-full min-h-0">
          <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-sm border border-coolgray-30 bg-white">
            {sourcePreviewUrl && sourceReady ? (
              <>
                <iframe
                  title="업로드 원문"
                  src={sourcePreviewUrl}
                  className="min-h-0 w-full flex-1 border-0"
                />
                <div className="flex shrink-0 justify-between border-t border-coolgray-20 px-3 py-2 text-xs text-coolgray-60">
                  <span className="truncate">{sourceFilename || filename}</span>
                  <a
                    href={sourcePreviewUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="ml-2 shrink-0 text-primary-60 hover:underline"
                  >
                    새 탭
                  </a>
                </div>
              </>
            ) : (
              <div className="flex min-h-0 flex-1 flex-col border border-coolgray-30 bg-white">
                <PageNavigator current={pageNum} total={pageCount} onChange={setPageNum} />
                <pre className="min-h-0 flex-1 overflow-auto whitespace-pre-wrap p-4 text-base leading-relaxed">
                  {originalPage}
                </pre>
              </div>
            )}
          </div>
        </WorkflowTwoPaneColumn>

        <WorkflowTwoPaneColumn side="right">
          <p className="text-center text-base text-primary-90 shrink-0">요약문</p>

          <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden border border-coolgray-40 bg-coolgray-10">
            {refining && (
              <div className="absolute inset-0 z-10 flex items-center justify-center bg-white/70 text-primary-60 text-sm gap-2">
                <span className="inline-block size-5 border-2 border-primary-60 border-t-transparent rounded-full animate-spin" />
                AI가 요약문을 수정하고 있습니다...
              </div>
            )}
            <div className="flex min-h-0 flex-1 flex-col overflow-hidden px-4 py-4">
              {!summary.trim() && summaryPlaceholder ? (
                <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-lg border border-coolgray-30 bg-white">
                  <div className="flex flex-1 items-center justify-center px-4 text-center text-[12px] leading-[2] text-coolgray-60">
                    {summaryPlaceholder}
                  </div>
                </div>
              ) : (
                <RichTextEditor
                  value={summary}
                  onChange={setSummary}
                  layout="full"
                  fill
                  disabled={refining || generating}
                />
              )}
            </div>
          </div>

          <div className="shrink-0">
            <PromptBar
              value={prompt}
              onChange={setPrompt}
              onSubmit={applyPrompt}
              loading={refining}
              loadingLabel="요약 수정 중..."
            />
          </div>
        </WorkflowTwoPaneColumn>
      </WorkflowTwoPaneGrid>
    </WorkflowLayout>
  );
}
