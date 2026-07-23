/**
 * 기존 프로젝트 대시보드 (로그인 사용자별 저장 항목).
 * 원문·요약문·번역문·최종본은 서버 user_storage에 보관(삭제 전까지 유지).
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import type { TranslationSegment } from "../../api/client";
import {
  deleteUserProject,
  fetchUserProjectEasyreadPdfBlob,
  fetchUserProjectSourceBlob,
  getUserProjectArtifact,
  getUserProjectTranslationSegments,
  listUserProjects,
  type UserProjectArtifactKind,
  type UserProjectItem,
} from "../../api/client";
import { EasyReadDocumentView } from "../EasyReadDocumentView";
import {
  FilePreviewModal,
  type FilePreviewState,
} from "./FilePreviewModal";
import { inlinePreviewMode } from "../../utils/sourcePreview";

export function ExistingProjectsTable() {
  const navigate = useNavigate();
  const location = useLocation();
  const [rows, setRows] = useState<UserProjectItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [modalTitle, setModalTitle] = useState("");
  const [modalText, setModalText] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [modalView, setModalView] = useState<"text" | "translation">("text");
  const [modalSegments, setModalSegments] = useState<TranslationSegment[]>([]);
  const [deletingDocId, setDeletingDocId] = useState<string | null>(null);
  const [openingSourceId, setOpeningSourceId] = useState<string | null>(null);
  const [openingArtifactKey, setOpeningArtifactKey] = useState<string | null>(null);
  const [openingPdfId, setOpeningPdfId] = useState<string | null>(null);
  const [filePreview, setFilePreview] = useState<FilePreviewState | null>(null);

  const closeFilePreview = useCallback(() => {
    setFilePreview((prev) => {
      if (prev?.url.startsWith("blob:")) {
        URL.revokeObjectURL(prev.url);
      }
      return null;
    });
  }, []);

  useEffect(() => {
    return () => {
      if (filePreview?.url.startsWith("blob:")) {
        URL.revokeObjectURL(filePreview.url);
      }
    };
  }, [filePreview?.url]);

  async function buildFilePreview(
    blob: Blob,
    filename: string,
    title: string,
  ): Promise<FilePreviewState> {
    const mode = inlinePreviewMode(filename, blob.type);
    const url = URL.createObjectURL(blob);
    let textContent: string | undefined;
    if (mode === "text") {
      textContent = await blob.text();
    }
    return { url, title, filename, mode, textContent };
  }

  const refreshProjects = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const items = await listUserProjects();
      setRows(items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "기존 프로젝트를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (location.pathname !== "/") return;

    let cancelled = false;
    void refreshProjects();

    // 요약·번역·그림 탭 이탈 직후 flush 저장이 끝난 뒤 목록 반영
    const retryTimer = window.setTimeout(() => {
      if (!cancelled) void refreshProjects();
    }, 1500);

    return () => {
      cancelled = true;
      window.clearTimeout(retryTimer);
    };
  }, [location.pathname, location.key, refreshProjects]);

  async function openArtifact(docId: string, kind: UserProjectArtifactKind) {
    const key = `${docId}:${kind}`;
    setOpeningArtifactKey(key);
    setError("");
    try {
      const titleMap: Record<UserProjectArtifactKind, string> = {
        summary: "요약문",
        translation: "번역문",
        easyread: "최종본(텍스트)",
      };

      if (kind === "translation") {
        try {
          const segments = await getUserProjectTranslationSegments(docId);
          if (segments.some((s) => s.easy_text?.trim())) {
            setModalTitle(titleMap[kind]);
            setModalSegments(segments);
            setModalView("translation");
            setModalText("");
            setModalOpen(true);
            return;
          }
        } catch {
          /* plain text fallback */
        }
      }

      const content = await getUserProjectArtifact(docId, kind);
      setModalTitle(titleMap[kind]);
      setModalText(content);
      setModalSegments([]);
      setModalView("text");
      setModalOpen(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "파일을 열지 못했습니다.");
    } finally {
      setOpeningArtifactKey(null);
    }
  }

  const modalTranslationText = useMemo(
    () => modalSegments.map((s) => s.easy_text).filter(Boolean).join("\n\n"),
    [modalSegments],
  );
  const modalPlacements = modalSegments[0]?.image_placements ?? [];

  async function openSource(docId: string, filename: string) {
    setOpeningSourceId(docId);
    setError("");
    closeFilePreview();
    try {
      const { blob, filename: resolvedName } = await fetchUserProjectSourceBlob(docId, filename);
      const preview = await buildFilePreview(blob, resolvedName, "원문");
      setFilePreview(preview);
    } catch (err) {
      setError(err instanceof Error ? err.message : "원문을 열지 못했습니다.");
    } finally {
      setOpeningSourceId(null);
    }
  }

  async function openFinalPdf(docId: string, filename: string) {
    setOpeningPdfId(docId);
    setError("");
    closeFilePreview();
    try {
      const blob = await fetchUserProjectEasyreadPdfBlob(docId);
      const pdfName = filename.replace(/\.[^.]+$/, "") + "_easyread.pdf";
      const preview = await buildFilePreview(blob, pdfName, "최종본 (PDF)");
      setFilePreview({ ...preview, mode: "iframe" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "최종본 PDF를 열지 못했습니다.");
    } finally {
      setOpeningPdfId(null);
    }
  }

  function canTryOpenSource(row: UserProjectItem): boolean {
    return Boolean(row.has_source || row.has_summary || row.has_translation);
  }

  function canTryOpenSummary(row: UserProjectItem): boolean {
    return Boolean(row.has_summary || row.has_translation || row.has_easyread);
  }

  function editProject(docId: string) {
    try {
      sessionStorage.setItem("easyread:last-doc-id", docId);
    } catch {
      /* ignore */
    }
    navigate(`/documents/${docId}/summary`);
  }

  async function deleteProject(docId: string, filename: string) {
    const ok = window.confirm(`'${filename}' 프로젝트를 삭제할까요?\n(원문·요약문·번역문·최종본이 모두 삭제됩니다.)`);
    if (!ok) return;

    setDeletingDocId(docId);
    setError("");
    try {
      await deleteUserProject(docId);
      setRows((prev) => prev.filter((row) => row.doc_id !== docId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "프로젝트 삭제에 실패했습니다.");
    } finally {
      setDeletingDocId(null);
    }
  }

  function OpenButton({
    disabled,
    loading,
    onClick,
  }: {
    disabled?: boolean;
    loading?: boolean;
    onClick: () => void;
  }) {
    return (
      <button
        type="button"
        disabled={disabled || loading}
        onClick={onClick}
        className="rounded border border-coolgray-30 px-2 py-1 text-xs font-medium text-coolgray-90 hover:bg-coolgray-10 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {loading ? "…" : "열기"}
      </button>
    );
  }

  return (
    <section className="mx-5 mb-6 mt-6">
      <h2 className="text-lg font-bold text-coolgray-90 mb-1">기존 프로젝트</h2>
      <p className="text-xs text-coolgray-60 mb-4">
        로그인 계정에 원문·요약문·번역문·최종본(PDF)이 저장됩니다. 직접 삭제하기 전까지 보관됩니다.
      </p>

      <div className="border border-coolgray-20 bg-white overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[880px] text-sm">
            <thead>
              <tr className="bg-coolgray-10 border-t border-coolgray-20">
                <th className="px-3 py-4 text-left font-medium text-coolgray-90 border-t border-coolgray-20">
                  파일명
                </th>
                <th className="px-3 py-4 text-left font-medium text-coolgray-90 border-t border-coolgray-20 w-32">
                  수정하기
                </th>
                <th className="px-3 py-4 text-left font-medium text-coolgray-90 border-t border-coolgray-20 w-28">
                  원문
                </th>
                <th className="px-3 py-4 text-left font-medium text-coolgray-90 border-t border-coolgray-20 w-28">
                  요약문
                </th>
                <th className="px-3 py-4 text-left font-medium text-coolgray-90 border-t border-coolgray-20 w-28">
                  번역문
                </th>
                <th className="px-3 py-4 text-left font-medium text-coolgray-90 border-t border-coolgray-20 w-28">
                  최종본
                </th>
                <th className="px-3 py-4 text-center font-medium text-coolgray-90 border-t border-coolgray-20 w-16" />
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr className="border-t border-coolgray-20">
                  <td colSpan={7} className="px-3 py-8 text-center text-coolgray-60">
                    불러오는 중...
                  </td>
                </tr>
              )}

              {!loading && rows.length === 0 && (
                <tr className="border-t border-coolgray-20">
                  <td colSpan={7} className="px-3 py-8 text-center text-coolgray-60">
                    저장된 프로젝트가 없습니다.
                  </td>
                </tr>
              )}

              {!loading &&
                rows.map((row) => (
                  <tr key={row.doc_id} className="border-t border-coolgray-20">
                    <td className="px-3 py-3 font-medium text-coolgray-90">{row.filename}</td>
                    <td className="px-3 py-3">
                      <button
                        type="button"
                        onClick={() => editProject(row.doc_id)}
                        className="rounded border border-primary-60 px-2 py-1 text-xs font-medium text-primary-60 hover:bg-blue-50"
                      >
                        수정하기
                      </button>
                    </td>
                    <td className="px-3 py-3">
                      <OpenButton
                        disabled={!canTryOpenSource(row)}
                        loading={openingSourceId === row.doc_id}
                        onClick={() => void openSource(row.doc_id, row.filename)}
                      />
                    </td>
                    <td className="px-3 py-3">
                      <OpenButton
                        disabled={!canTryOpenSummary(row)}
                        loading={openingArtifactKey === `${row.doc_id}:summary`}
                        onClick={() => void openArtifact(row.doc_id, "summary")}
                      />
                    </td>
                    <td className="px-3 py-3">
                      <OpenButton
                        disabled={!row.has_translation && !row.has_easyread}
                        loading={openingArtifactKey === `${row.doc_id}:translation`}
                        onClick={() => void openArtifact(row.doc_id, "translation")}
                      />
                    </td>
                    <td className="px-3 py-3">
                      <OpenButton
                        disabled={!row.has_easyread_pdf}
                        loading={openingPdfId === row.doc_id}
                        onClick={() => void openFinalPdf(row.doc_id, row.filename)}
                      />
                    </td>
                    <td className="px-3 py-3 text-center">
                      <button
                        type="button"
                        onClick={() => deleteProject(row.doc_id, row.filename)}
                        disabled={deletingDocId === row.doc_id}
                        className="inline-flex h-7 w-7 items-center justify-center rounded border border-[#ff8389] text-[#da1e28] hover:bg-[#fff1f1] disabled:opacity-50"
                        aria-label={`${row.filename} 삭제`}
                      >
                        X
                      </button>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </div>

      {error && <p className="mt-3 text-sm text-alert">{error}</p>}

      {modalOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/45 p-4">
          <div
            className={`w-full rounded-xl bg-white shadow-xl ${
              modalView === "translation" ? "max-w-5xl" : "max-w-3xl"
            }`}
          >
            <div className="flex items-center justify-between border-b border-coolgray-20 px-4 py-3">
              <h3 className="text-base font-bold text-coolgray-90">{modalTitle}</h3>
              <button
                type="button"
                onClick={() => setModalOpen(false)}
                className="rounded border border-coolgray-30 px-2 py-1 text-xs text-coolgray-90 hover:bg-coolgray-10"
              >
                닫기
              </button>
            </div>
            {modalView === "translation" ? (
              <div className="max-h-[70vh] overflow-auto px-4 py-4">
                <EasyReadDocumentView
                  text={modalTranslationText}
                  placements={modalPlacements}
                  mode="images"
                  readOnly
                  disabled
                />
              </div>
            ) : (
              <pre className="max-h-[70vh] overflow-auto whitespace-pre-wrap px-4 py-4 text-sm text-coolgray-90">
                {modalText}
              </pre>
            )}
          </div>
        </div>
      )}

      <FilePreviewModal preview={filePreview} onClose={closeFilePreview} />
    </section>
  );
}
