/**
 * 백엔드 REST API 클라이언트 및 공유 타입 정의.
 *
 * 역할: 문서 업로드·요약·번역·체크리스트·Word 출력 등 API 호출을 캡슐화한다.
 * 주요 기능: fetch 래퍼, Document/TranslationSegment 타입, 파일 다운로드.
 * 연관 파일: pages/*.tsx, components/*.tsx, utils/docCache.ts
 */
import { getAuthUserId } from "../utils/auth";
import { getSourceFile } from "../utils/sourceStore";

const API_BASE = "/api";

export type DocType = "criminal" | "civil" | "family" | "administrative" | "unknown";

export const DOC_TYPE_LABELS: Record<Exclude<DocType, "unknown">, string> = {
  criminal: "형사",
  civil: "민사",
  family: "가사",
  administrative: "행정",
};

export const DOC_TYPE_OPTIONS: { value: Exclude<DocType, "unknown">; label: string }[] = [
  { value: "criminal", label: "형사" },
  { value: "civil", label: "민사" },
  { value: "family", label: "가사" },
  { value: "administrative", label: "행정" },
];

export interface ImagePlacement {
  id: string;
  image_file: string;
  line_index: number;
  title?: string | null;
  image_url?: string | null;
  section_heading?: string | null;
  /** PDF 추출 POST body 전용 — 서버 파일 해석 없이 이미지 삽입 */
  image_base64?: string | null;
  /** 그림 탭 자동 배치 — X 삭제 불가 */
  auto_filled?: boolean;
}

export interface ImageCatalogItem {
  image_file: string;
  title: string;
  url: string;
  source_url?: string | null;
}

export interface TranslationSegment {
  id: string;
  original: string;
  easy_text: string;
  image_file?: string | null;
  image_url?: string | null;
  title?: string | null;
  source: "db" | "solar" | "manual";
  image_placements?: ImagePlacement[];
}

export interface ChecklistItemResult {
  id: string;
  category: string;
  label: string;
  status: "pass" | "warn" | "fail" | "manual";
  detail?: string | null;
}

export interface ChecklistReport {
  overall: "pass" | "warn" | "fail";
  summary: Record<string, number>;
  items: ChecklistItemResult[];
}

export interface Document {
  id: string;
  filename: string;
  doc_type: DocType;
  stage: "uploaded" | "summarized" | "translated";
  page_count: number;
  full_text: string;
  summary?: string | null;
  translation_segments: TranslationSegment[];
  translation_text?: string | null;
  checklist?: ChecklistReport | null;
}

export interface UploadResult {
  id: string;
  filename: string;
  doc_type: DocType;
  page_count: number;
  message: string;
  pages?: string[];
  full_text?: string;
}

export interface UserProjectItem {
  doc_id: string;
  filename: string;
  created_at: string;
  updated_at: string;
  has_source: boolean;
  has_summary: boolean;
  has_translation: boolean;
  has_easyread_pdf: boolean;
  has_easyread: boolean;
}

export interface AdminUserStorageBlock {
  user_id: string;
  projects: UserProjectItem[];
}

export interface AdminStorageOverview {
  users: AdminUserStorageBlock[];
}

export type UserProjectArtifactKind = "summary" | "translation" | "easyread";

async function parseErrorResponse(res: Response): Promise<string> {
  const text = await res.text();
  if (!text) return res.statusText;
  try {
    const body = JSON.parse(text) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
    if (body.detail != null) return JSON.stringify(body.detail);
  } catch {
    /* not JSON */
  }
  return text;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  const authUser = getAuthUserId();
  if (authUser) {
    headers.set("X-User-Id", authUser);
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
  });
  if (!res.ok) {
    throw new Error(await parseErrorResponse(res));
  }
  if (res.headers.get("content-type")?.includes("application/json")) {
    return res.json();
  }
  return res as unknown as T;
}

export async function uploadDocument(file: File): Promise<UploadResult> {
  const form = new FormData();
  form.append("file", file);
  return request<UploadResult>("/documents/upload", { method: "POST", body: form });
}

export async function getDocument(id: string): Promise<Document> {
  return request<Document>(`/documents/${id}`);
}

export async function getPage(id: string, pageNum: number): Promise<string> {
  const data = await request<{ page: string }>(`/documents/${id}/pages/${pageNum}`);
  return data.page;
}

export async function summarize(id: string, force = false, fallback?: {
  full_text: string;
  doc_type: DocType;
  filename: string;
  pages: string[];
}): Promise<Document> {
  const q = force ? "?force=true" : "";
  return request<Document>(`/documents/${id}/summarize${q}`, {
    method: "POST",
    headers: fallback ? { "Content-Type": "application/json" } : undefined,
    body: fallback ? JSON.stringify(fallback) : undefined,
  });
}

export interface EnsurePayload {
  full_text: string;
  doc_type: DocType;
  filename: string;
  pages: string[];
}

export async function updateSummary(
  id: string,
  summary: string,
  ensure?: EnsurePayload,
): Promise<Document> {
  return request<Document>(`/documents/${id}/summary`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ summary, ...ensure }),
  });
}

export async function updateDocType(id: string, docType: DocType): Promise<Document> {
  return request<Document>(`/documents/${id}/doc-type`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ doc_type: docType }),
  });
}

export async function refineSummary(
  id: string,
  prompt: string,
  summary?: string,
): Promise<Document> {
  return request<Document>(`/documents/${id}/summary/refine`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, summary }),
  });
}

export async function translate(
  id: string,
  ensure?: EnsurePayload & { summary?: string },
): Promise<Document> {
  return request<Document>(`/documents/${id}/translate`, {
    method: "POST",
    headers: ensure ? { "Content-Type": "application/json" } : undefined,
    body: ensure ? JSON.stringify(ensure) : undefined,
  });
}

export async function updateTranslation(
  id: string,
  segments: TranslationSegment[],
  ensure?: EnsurePayload & { summary?: string },
): Promise<Document> {
  return request<Document>(`/documents/${id}/translation`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ segments, ...ensure }),
  });
}

export async function refineTranslation(
  id: string,
  prompt: string,
  segments?: TranslationSegment[],
): Promise<Document> {
  return request<Document>(`/documents/${id}/translation/refine`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, segments }),
  });
}

export async function runChecklist(id: string): Promise<ChecklistReport> {
  return request<ChecklistReport>(`/documents/${id}/translation/checklist`, {
    method: "POST",
  });
}

export function exportDocxUrl(id: string): string {
  return `${API_BASE}/documents/${id}/export.docx`;
}

export function exportPdfUrl(id: string, download = false): string {
  const q = download ? "?download=true" : "";
  return `${API_BASE}/documents/${id}/export.pdf${q}`;
}

export interface ExportPayload {
  segments: TranslationSegment[];
  translation_text?: string;
  summary?: string;
  filename?: string;
  doc_type?: DocType;
  full_text?: string;
  pages?: string[];
  /** 서버에 원본 PDF가 없을 때 IndexedDB PDF (base64) */
  source_pdf_base64?: string;
}

export async function serverHasDocumentSource(docId: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/documents/${docId}/source`, { method: "HEAD" });
    return res.ok;
  } catch {
    return false;
  }
}

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let i = 0; i < bytes.length; i += 1) {
    binary += String.fromCharCode(bytes[i]!);
  }
  return btoa(binary);
}

/** export 시 pdf2docx 병합을 위해 서버·페이로드에 원본 PDF를 확보한다. */
export async function attachSourcePdfForExport(
  docId: string,
  filename: string,
  payload: ExportPayload,
): Promise<ExportPayload> {
  if (await serverHasDocumentSource(docId)) {
    return payload;
  }
  const stored = await getSourceFile(docId);
  if (!stored) {
    return payload;
  }
  const name = (stored.name || filename || "").toLowerCase();
  if (!name.endsWith(".pdf")) {
    return payload;
  }
  const authUser = getAuthUserId();
  if (authUser) {
    await uploadUserProjectSource(docId, stored.blob, stored.name || filename).catch(() => {
      /* ignore */
    });
    if (await serverHasDocumentSource(docId)) {
      return payload;
    }
  }
  return {
    ...payload,
    source_pdf_base64: arrayBufferToBase64(await stored.blob.arrayBuffer()),
  };
}

function buildExportBody(payload: ExportPayload) {
  return {
    ...payload,
    translation_text:
      payload.translation_text ??
      payload.segments.map((s) => s.easy_text).filter(Boolean).join("\n\n"),
  };
}

function exportRequestHeaders(): HeadersInit {
  const headers = new Headers({ "Content-Type": "application/json" });
  const authUser = getAuthUserId();
  if (authUser) {
    headers.set("X-User-Id", authUser);
  }
  return headers;
}

export async function fetchExportDocx(id: string, payload: ExportPayload): Promise<Blob> {
  const res = await fetch(`${API_BASE}/documents/${id}/export.docx`, {
    method: "POST",
    headers: exportRequestHeaders(),
    body: JSON.stringify(buildExportBody(payload)),
  });
  if (!res.ok) {
    throw new Error(await parseErrorResponse(res));
  }
  return res.blob();
}

export async function fetchExportPdf(id: string, payload: ExportPayload): Promise<Blob> {
  const res = await fetch(`${API_BASE}/documents/${id}/export.pdf?download=false`, {
    method: "POST",
    headers: exportRequestHeaders(),
    body: JSON.stringify(buildExportBody(payload)),
  });
  if (!res.ok) {
    throw new Error(await parseErrorResponse(res));
  }
  return res.blob();
}

export async function downloadPdf(id: string, payload: ExportPayload): Promise<void> {
  const res = await fetch(`${API_BASE}/documents/${id}/export.pdf?download=true`, {
    method: "POST",
    headers: exportRequestHeaders(),
    body: JSON.stringify(buildExportBody(payload)),
  });
  if (!res.ok) {
    throw new Error(await parseErrorResponse(res));
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `easyread_${id.slice(0, 8)}.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export async function downloadDocx(id: string, payload: ExportPayload): Promise<void> {
  const res = await fetch(`${API_BASE}/documents/${id}/export.docx`, {
    method: "POST",
    headers: exportRequestHeaders(),
    body: JSON.stringify(buildExportBody(payload)),
  });
  if (!res.ok) {
    throw new Error(await parseErrorResponse(res));
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `easyread_${id.slice(0, 8)}.docx`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export async function getImageCatalog(query = ""): Promise<ImageCatalogItem[]> {
  const q = query ? `?q=${encodeURIComponent(query)}` : "";
  return request<ImageCatalogItem[]>(`/documents/catalog/images${q}`);
}

export async function listUserProjects(): Promise<UserProjectItem[]> {
  return request<UserProjectItem[]>("/documents/user-projects");
}

export async function deleteUserProject(docId: string): Promise<void> {
  await request<void>(`/documents/user-projects/${docId}`, {
    method: "DELETE",
  });
}

export async function getUserProjectTranslationSegments(
  docId: string,
): Promise<TranslationSegment[]> {
  try {
    return await request<TranslationSegment[]>(
      `/documents/user-projects/${docId}/translation-segments`,
    );
  } catch {
    const doc = await getDocument(docId);
    if (doc.translation_segments?.length) {
      return doc.translation_segments;
    }
    throw new Error("저장된 번역(그림 포함)을 찾을 수 없습니다.");
  }
}

export async function uploadUserProjectSource(
  docId: string,
  file: Blob,
  filename: string,
): Promise<void> {
  const form = new FormData();
  form.append("file", file, filename);
  await request<void>(`/documents/user-projects/${docId}/source`, {
    method: "POST",
    body: form,
  });
}

export async function getUserProjectArtifact(
  docId: string,
  kind: UserProjectArtifactKind,
): Promise<string> {
  try {
    const data = await request<{ content: string }>(
      `/documents/user-projects/${docId}/artifact/${kind}`,
    );
    return data.content;
  } catch (firstErr) {
    try {
      const doc = await getDocument(docId);
      if (kind === "summary" && doc.summary?.trim()) {
        return doc.summary.trim();
      }
      if (kind === "translation" && doc.translation_text?.trim()) {
        return doc.translation_text.trim();
      }
      if (kind === "easyread") {
        const text = (doc.translation_text || doc.summary || "").trim();
        if (text) return text;
      }
    } catch {
      /* ignore secondary failure */
    }
    throw firstErr instanceof Error ? firstErr : new Error("저장된 파일을 찾을 수 없습니다.");
  }
}

async function fetchAuthenticatedBlob(path: string): Promise<Blob> {
  const headers = new Headers();
  const authUser = getAuthUserId();
  if (authUser) {
    headers.set("X-User-Id", authUser);
  }
  const res = await fetch(`${API_BASE}${path}`, { headers });
  if (!res.ok) {
    throw new Error(await parseErrorResponse(res));
  }
  return res.blob();
}

export async function fetchUserProjectEasyreadPdfBlob(docId: string): Promise<Blob> {
  return fetchAuthenticatedBlob(`/documents/user-projects/${docId}/easyread.pdf`);
}

export async function fetchUserProjectSourceBlob(
  docId: string,
  hintFilename?: string,
): Promise<{ blob: Blob; filename: string }> {
  const fallbackName = hintFilename?.trim() || "source.pdf";

  try {
    const blob = await fetchAuthenticatedBlob(`/documents/user-projects/${docId}/source`);
    return { blob, filename: fallbackName };
  } catch {
    /* fall through */
  }

  try {
    const blob = await fetchAuthenticatedBlob(`/documents/${docId}/source`);
    return { blob, filename: fallbackName };
  } catch {
    /* fall through */
  }

  const stored = await getSourceFile(docId);
  if (stored) {
    void uploadUserProjectSource(docId, stored.blob, stored.name).catch(() => {
      /* ignore sync failure */
    });
    return { blob: stored.blob, filename: stored.name || fallbackName };
  }

  throw new Error(
    "원본 파일을 찾을 수 없습니다. 이 기기에서 업로드한 적이 없거나 서버 저장소가 초기화되었을 수 있습니다.",
  );
}

/** @deprecated 인앱 미리보기(fetchUserProjectSourceBlob) 사용 권장 */
export function prepareDocumentPreviewWindow(title = "불러오는 중…"): Window | null {
  const preview = window.open("about:blank", "_blank");
  if (!preview) return null;
  try {
    preview.document.title = title;
    preview.document.body.innerHTML =
      '<p style="font-family:sans-serif;padding:24px;color:#525252">문서를 불러오는 중입니다…</p>';
  } catch {
    /* cross-origin or restricted — location only */
  }
  return preview;
}

function openBlobInPreview(blob: Blob, previewWindow: Window | null): void {
  const url = URL.createObjectURL(blob);
  if (previewWindow && !previewWindow.closed) {
    previewWindow.location.href = url;
    window.setTimeout(() => URL.revokeObjectURL(url), 120_000);
    return;
  }

  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.target = "_blank";
  anchor.rel = "noopener noreferrer";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 120_000);
}

export async function openUserProjectSourceInNewTab(
  docId: string,
  previewWindow: Window | null = null,
): Promise<void> {
  const openBlob = (blob: Blob) => openBlobInPreview(blob, previewWindow);

  try {
    const blob = await fetchAuthenticatedBlob(`/documents/user-projects/${docId}/source`);
    openBlob(blob);
    return;
  } catch {
    /* try fallbacks */
  }

  try {
    const blob = await fetchAuthenticatedBlob(`/documents/${docId}/source`);
    openBlob(blob);
    return;
  } catch {
    /* try local */
  }

  const stored = await getSourceFile(docId);
  if (stored) {
    openBlob(stored.blob);
    void uploadUserProjectSource(docId, stored.blob, stored.name).catch(() => {
      /* 서버 동기화 실패해도 로컬 미리보기는 성공 */
    });
    return;
  }

  throw new Error(
    "원본 파일을 찾을 수 없습니다. 이 기기에서 업로드한 적이 없거나 서버 저장소가 초기화되었을 수 있습니다.",
  );
}

export async function openUserProjectEasyreadPdfInNewTab(
  docId: string,
  previewWindow: Window | null = null,
): Promise<void> {
  const blob = await fetchAuthenticatedBlob(`/documents/user-projects/${docId}/easyread.pdf`);
  openBlobInPreview(blob, previewWindow);
}

export function getUserProjectSourceUrl(docId: string): string {
  const userId = getAuthUserId() ?? "";
  const q = userId ? `?user_id=${encodeURIComponent(userId)}` : "";
  return `${API_BASE}/documents/user-projects/${docId}/source${q}`;
}

export function getUserProjectEasyreadPdfUrl(docId: string): string {
  const userId = getAuthUserId() ?? "";
  const q = userId ? `?user_id=${encodeURIComponent(userId)}` : "";
  return `${API_BASE}/documents/user-projects/${docId}/easyread.pdf${q}`;
}

export async function listAdminUserStorage(): Promise<AdminStorageOverview> {
  return request<AdminStorageOverview>("/documents/admin/user-storage");
}

export async function adminDeleteUserProject(
  storageUserId: string,
  docId: string,
): Promise<void> {
  await request<void>(
    `/documents/admin/user-storage/${encodeURIComponent(storageUserId)}/projects/${encodeURIComponent(docId)}`,
    { method: "DELETE" },
  );
}

export async function searchWebImages(query: string): Promise<ImageCatalogItem[]> {
  return request<ImageCatalogItem[]>(
    `/documents/catalog/images/web?q=${encodeURIComponent(query)}`,
  );
}

export async function detectImagePlacements(
  docId: string,
  options?: Partial<EnsurePayload> & {
    summary?: string;
    existingPlacements?: ImagePlacement[];
    translationText?: string;
  },
): Promise<ImagePlacement[]> {
  const payload = {
    ...(options ?? {}),
    existing_placements: options?.existingPlacements ?? [],
    translation_text: options?.translationText,
  };
  return request<ImagePlacement[]>(`/documents/${docId}/translation/detect-placements`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  reply: string;
  sources: string[];
}

export async function sendChatMessage(
  message: string,
  history: ChatMessage[] = [],
  docId?: string,
  pageContext?: string,
): Promise<ChatResponse> {
  const path = docId ? `/chat/documents/${docId}` : "/chat";
  return request<ChatResponse>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history, page_context: pageContext }),
  });
}

export async function getChatPrompt(): Promise<{ system_prompt: string }> {
  return request<{ system_prompt: string }>("/chat/prompt");
}

export async function updateChatPrompt(systemPrompt: string): Promise<{ system_prompt: string }> {
  return request<{ system_prompt: string }>("/chat/prompt", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ system_prompt: systemPrompt }),
  });
}
