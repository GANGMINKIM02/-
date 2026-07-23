/**
 * 문서 조회·서버 복구 유틸 (Vercel 서버리스 DB 유실 대응).
 */
import type { Document, EnsurePayload } from "../api/client";
import { getDocument, updateSummary, updateTranslation } from "../api/client";
import { ensurePayload, getCachedUpload } from "./docCache";
import { getWorkflowSnapshot } from "./workflowCache";

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export type DocumentEnsureContext = EnsurePayload & { summary?: string };
/** sessionStorage 캐시로 서버에 문서 메타를 복구할 때 쓰는 페이로드 */
export function buildEnsureContext(docId: string): DocumentEnsureContext | undefined {
  const cached = getCachedUpload(docId);
  const payload = ensurePayload(cached);
  if (!payload) return undefined;
  const workflow = getWorkflowSnapshot(docId);
  return {
    ...payload,
    summary: workflow?.summary ?? undefined,
  };
}

export async function recoverDocumentOnServer(docId: string): Promise<Document> {
  const ensure = buildEnsureContext(docId);
  if (!ensure) {
    throw new Error("문서를 찾을 수 없습니다.");
  }

  const summary = ensure.summary ?? "";
  await updateSummary(docId, summary, ensure);

  const workflow = getWorkflowSnapshot(docId);
  if (workflow?.translation_segments?.length) {
    await updateTranslation(docId, workflow.translation_segments, {
      ...ensure,
      summary: summary || undefined,
    });
  }

  return getDocument(docId);
}

/** GET 재시도 후 실패 시 클라이언트 캐시로 서버 문서 복구 */
export async function loadDocumentWithRecovery(docId: string): Promise<Document> {
  let lastErr: unknown;
  for (let i = 0; i < 5; i += 1) {
    try {
      return await getDocument(docId);
    } catch (err) {
      lastErr = err;
      await delay(250 * (i + 1));
    }
  }

  try {
    return await recoverDocumentOnServer(docId);
  } catch (recoverErr) {
    if (lastErr instanceof Error) throw lastErr;
    throw recoverErr;
  }
}
