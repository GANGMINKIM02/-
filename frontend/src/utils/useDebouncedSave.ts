/**
 * 입력 변경 후 지연 저장 React 훅.
 *
 * 역할: 요약·번역 textarea 변경 시 debounce로 자동 저장을 트리거한다.
 * 주요 기능: 초기 마운트 스킵, delayMs(기본 800ms) 후 save 콜백 실행, flush().
 * 연관 파일: pages/SummaryPage.tsx, pages/TranslatePage.tsx
 */
import { useCallback, useEffect, useRef } from "react";

/** 값 변경 후 delayMs만큼 대기한 뒤 save를 호출한다. skipInitial이 true면 첫 실행을 건너뛴다. */
export function useDebouncedSave(
  value: unknown,
  save: () => void | Promise<void>,
  delayMs = 800,
  skipInitial = true,
) {
  const ready = useRef(!skipInitial);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const saveRef = useRef(save);
  saveRef.current = save;

  useEffect(() => {
    if (!ready.current) {
      ready.current = true;
      return;
    }
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      void Promise.resolve(saveRef.current()).catch(console.error);
    }, delayMs);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [value, delayMs]);

  const flush = useCallback(async () => {
    if (timer.current) {
      clearTimeout(timer.current);
      timer.current = null;
    }
    await Promise.resolve(saveRef.current());
  }, []);

  return { flush };
}

/** 라우트 이탈 시 debounce 저장 즉시 반영 (회원 저장소·기존 프로젝트 목록용) */
export function useFlushSaveOnUnmount(flush: () => void | Promise<void>) {
  const flushRef = useRef(flush);
  flushRef.current = flush;

  useEffect(() => {
    return () => {
      void Promise.resolve(flushRef.current()).catch(console.error);
    };
  }, []);
}
