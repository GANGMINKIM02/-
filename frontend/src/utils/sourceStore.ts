/**
 * 업로드 원본 파일 IndexedDB 저장 (탭·서버 유실 후에도 원문 미리보기 유지).
 */
const DB_NAME = "easyread-sources";
const STORE = "files";
const DB_VERSION = 1;

interface StoredSource {
  blob: Blob;
  name: string;
  type: string;
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      req.result.createObjectStore(STORE);
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function saveSourceFile(docId: string, file: File): Promise<void> {
  try {
    const db = await openDb();
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE, "readwrite");
      const payload: StoredSource = {
        blob: file,
        name: file.name,
        type: file.type || "application/octet-stream",
      };
      tx.objectStore(STORE).put(payload, docId);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
    db.close();
  } catch {
    /* quota or private mode — ignore */
  }
}

export async function getSourceFile(docId: string): Promise<StoredSource | null> {
  try {
    const db = await openDb();
    const result = await new Promise<StoredSource | undefined>((resolve, reject) => {
      const tx = db.transaction(STORE, "readonly");
      const req = tx.objectStore(STORE).get(docId);
      req.onsuccess = () => resolve(req.result as StoredSource | undefined);
      req.onerror = () => reject(req.error);
    });
    db.close();
    return result ?? null;
  } catch {
    return null;
  }
}

export async function getSourceObjectUrl(docId: string): Promise<string | null> {
  const stored = await getSourceFile(docId);
  if (!stored) return null;
  return URL.createObjectURL(stored.blob);
}
