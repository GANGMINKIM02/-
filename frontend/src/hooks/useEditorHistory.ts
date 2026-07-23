import { useCallback, useRef } from "react";

const MAX_HISTORY = 100;

/** contentEditable 로컬 undo/redo — 자동 저장과 독립 */
export function useEditorHistory(initial: string) {
  const undoStackRef = useRef<string[]>([]);
  const redoStackRef = useRef<string[]>([]);
  const lastCommittedRef = useRef(initial);
  const isApplyingRef = useRef(false);

  const resetHistory = useCallback((baseline: string) => {
    undoStackRef.current = [];
    redoStackRef.current = [];
    lastCommittedRef.current = baseline;
  }, []);

  const recordChange = useCallback((next: string) => {
    if (isApplyingRef.current) return;
    if (next === lastCommittedRef.current) return;

    undoStackRef.current.push(lastCommittedRef.current);
    if (undoStackRef.current.length > MAX_HISTORY) {
      undoStackRef.current.shift();
    }
    redoStackRef.current = [];
    lastCommittedRef.current = next;
  }, []);

  const undo = useCallback((current: string): string | null => {
    if (undoStackRef.current.length === 0) return null;
    redoStackRef.current.push(current);
    const prev = undoStackRef.current.pop()!;
    lastCommittedRef.current = prev;
    return prev;
  }, []);

  const redo = useCallback((current: string): string | null => {
    if (redoStackRef.current.length === 0) return null;
    undoStackRef.current.push(current);
    const next = redoStackRef.current.pop()!;
    lastCommittedRef.current = next;
    return next;
  }, []);

  const runApplying = useCallback((fn: () => void) => {
    isApplyingRef.current = true;
    try {
      fn();
    } finally {
      requestAnimationFrame(() => {
        isApplyingRef.current = false;
      });
    }
  }, []);

  const isApplying = useCallback(() => isApplyingRef.current, []);

  return {
    resetHistory,
    recordChange,
    undo,
    redo,
    runApplying,
    isApplying,
    canUndo: () => undoStackRef.current.length > 0,
    canRedo: () => redoStackRef.current.length > 0,
  };
}
