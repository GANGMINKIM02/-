/**
 * 업로드 직후 문서 메타데이터 sessionStorage 캐시.
 *
 * 역할: 서버 동기화 전·재시도 시 OCR 결과와 원본 blob URL을 임시 보관한다.
 * 주요 기능: cacheUpload/getCachedUpload, summarize·PATCH용 ensurePayload 변환.
 * 연관 파일: api/client.ts, pages/UploadPage.tsx, pages/SummaryPage.tsx, pages/TranslatePage.tsx
 */
import type { DocType, EnsurePayload, UploadResult } from "../api/client";

export interface CachedUpload extends UploadResult {
  pages: string[];
  full_text: string;
  source_blob_url?: string;
  source_filename?: string;
  source_mime_type?: string;
}

const KEY_PREFIX = "easyread:doc:";
const LOCAL_KEY_PREFIX = "easyread:doc-meta:";

function readSession(id: string): CachedUpload | null {
  try {
    const raw = sessionStorage.getItem(`${KEY_PREFIX}${id}`);
    if (!raw) return null;
    return JSON.parse(raw) as CachedUpload;
  } catch {
    return null;
  }
}

function readLocalMeta(id: string): Omit<CachedUpload, "source_blob_url"> | null {
  try {
    const raw = localStorage.getItem(`${LOCAL_KEY_PREFIX}${id}`);
    if (!raw) return null;
    return JSON.parse(raw) as Omit<CachedUpload, "source_blob_url">;
  } catch {
    return null;
  }
}

function writeLocalMeta(result: CachedUpload): void {
  try {
    const { source_blob_url: _blob, ...meta } = result;
    localStorage.setItem(`${LOCAL_KEY_PREFIX}${result.id}`, JSON.stringify(meta));
  } catch {
    /* quota exceeded — ignore */
  }
}

export function cacheUpload(result: CachedUpload): void {
  try {
    sessionStorage.setItem(`${KEY_PREFIX}${result.id}`, JSON.stringify(result));
    sessionStorage.setItem("easyread:last-doc-id", result.id);
    writeLocalMeta(result);
  } catch {
    /* quota exceeded — ignore */
  }
}

export function getLastDocId(): string | null {
  try {
    return sessionStorage.getItem("easyread:last-doc-id");
  } catch {
    return null;
  }
}

export function getCachedUpload(id: string): CachedUpload | null {
  const session = readSession(id);
  if (session?.full_text) return session;

  const local = readLocalMeta(id);
  if (!local?.full_text) return session;

  return {
    ...local,
    source_blob_url: session?.source_blob_url,
    source_filename: session?.source_filename ?? local.filename,
    source_mime_type: session?.source_mime_type,
  };
}

export function summarizeFallbackBody(cached: CachedUpload) {
  return {
    full_text: cached.full_text,
    doc_type: cached.doc_type as DocType,
    filename: cached.filename,
    pages: cached.pages,
  };
}

export function ensurePayload(cached: CachedUpload | null): EnsurePayload | undefined {
  if (!cached?.full_text) return undefined;
  return {
    full_text: cached.full_text,
    doc_type: cached.doc_type as DocType,
    filename: cached.filename,
    pages: cached.pages,
  };
}
