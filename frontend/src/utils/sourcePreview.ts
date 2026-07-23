/** 원문·PDF 인라인 미리보기 (팝업 없음) */

export function getFileExt(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot >= 0 ? name.slice(dot + 1).toLowerCase() : "";
}

export type InlinePreviewMode = "iframe" | "image" | "text" | "download";

export function inlinePreviewMode(filename: string, mimeType = ""): InlinePreviewMode {
  const ext = getFileExt(filename);
  const mime = mimeType.toLowerCase();
  if (mime.startsWith("image/") || ["png", "jpg", "jpeg", "gif", "webp"].includes(ext)) {
    return "image";
  }
  if (mime === "application/pdf" || ext === "pdf") return "iframe";
  if (mime.startsWith("text/") || ext === "txt") return "text";
  if (["doc", "docx", "hwp", "hwpx"].includes(ext)) return "download";
  if (mime === "application/octet-stream" && ext === "pdf") return "iframe";
  return "download";
}
