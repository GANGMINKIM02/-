/**
 * 관리자 — 계정별 회원 저장소 조회·삭제.
 */
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  adminDeleteUserProject,
  listAdminUserStorage,
  type AdminUserStorageBlock,
} from "../api/client";
import { isAdminUser } from "../utils/auth";

export function AdminStoragePage() {
  const [blocks, setBlocks] = useState<AdminUserStorageBlock[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deletingKey, setDeletingKey] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await listAdminUserStorage();
      setBlocks(data.users);
    } catch (err) {
      setError(err instanceof Error ? err.message : "저장 내역을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!isAdminUser()) return;
    void load();
  }, [load]);

  if (!isAdminUser()) {
    return (
      <div className="min-h-screen bg-coolgray-10 flex items-center justify-center p-6">
        <p className="text-coolgray-90">관리자만 접근할 수 있습니다.</p>
      </div>
    );
  }

  async function handleDelete(storageUserId: string, docId: string, filename: string) {
    const ok = window.confirm(`[${storageUserId}] '${filename}' 저장 항목을 삭제할까요?`);
    if (!ok) return;
    const key = `${storageUserId}:${docId}`;
    setDeletingKey(key);
    setError("");
    try {
      await adminDeleteUserProject(storageUserId, docId);
      setBlocks((prev) =>
        prev
          .map((block) =>
            block.user_id === storageUserId
              ? {
                  ...block,
                  projects: block.projects.filter((p) => p.doc_id !== docId),
                }
              : block,
          )
          .filter((block) => block.projects.length > 0),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "삭제에 실패했습니다.");
    } finally {
      setDeletingKey(null);
    }
  }

  return (
    <div className="min-h-screen bg-coolgray-10 flex flex-col">
      <header className="px-6 pt-6 pb-4 flex items-center justify-between gap-4">
        <h1 className="text-2xl font-bold text-coolgray-90">
          저장소 관리 <span className="text-sm font-normal text-coolgray-60">(관리자)</span>
        </h1>
        <Link to="/" className="text-sm font-medium text-primary-60 hover:underline">
          업로드로 돌아가기
        </Link>
      </header>

      <main className="flex-1 mx-6 mb-6 overflow-auto">
        {loading && <p className="text-coolgray-60 py-8 text-center">불러오는 중...</p>}

        {!loading && blocks.length === 0 && (
          <p className="text-coolgray-60 py-8 text-center border border-coolgray-20 bg-white">
            저장된 회원 프로젝트가 없습니다.
          </p>
        )}

        {!loading &&
          blocks.map((block) => (
            <section key={block.user_id} className="mb-8 border border-coolgray-20 bg-white">
              <h2 className="px-4 py-3 text-base font-bold text-coolgray-90 border-b border-coolgray-20 bg-coolgray-10">
                계정: {block.user_id}
                <span className="ml-2 text-sm font-normal text-coolgray-60">
                  ({block.projects.length}건)
                </span>
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[720px] text-sm">
                  <thead>
                    <tr className="border-b border-coolgray-20 text-coolgray-70">
                      <th className="px-3 py-2 text-left font-medium">파일명</th>
                      <th className="px-3 py-2 text-left font-medium w-24">원문</th>
                      <th className="px-3 py-2 text-left font-medium w-24">요약문</th>
                      <th className="px-3 py-2 text-left font-medium w-24">번역문</th>
                      <th className="px-3 py-2 text-left font-medium w-24">최종본</th>
                      <th className="px-3 py-2 text-center font-medium w-16">삭제</th>
                    </tr>
                  </thead>
                  <tbody>
                    {block.projects.map((row) => {
                      const delKey = `${block.user_id}:${row.doc_id}`;
                      return (
                        <tr key={row.doc_id} className="border-b border-coolgray-20">
                          <td className="px-3 py-2 text-coolgray-90">{row.filename}</td>
                          <td className="px-3 py-2">{row.has_source ? "○" : "—"}</td>
                          <td className="px-3 py-2">{row.has_summary ? "○" : "—"}</td>
                          <td className="px-3 py-2">{row.has_translation ? "○" : "—"}</td>
                          <td className="px-3 py-2">{row.has_easyread_pdf ? "○" : "—"}</td>
                          <td className="px-3 py-2 text-center">
                            <button
                              type="button"
                              disabled={deletingKey === delKey}
                              onClick={() => handleDelete(block.user_id, row.doc_id, row.filename)}
                              className="inline-flex h-7 w-7 items-center justify-center rounded border border-[#ff8389] text-[#da1e28] hover:bg-[#fff1f1] disabled:opacity-50"
                              aria-label="삭제"
                            >
                              X
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </section>
          ))}

        {error && <p className="mt-4 text-sm text-alert">{error}</p>}
      </main>
    </div>
  );
}
