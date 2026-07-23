/**
 * React 애플리케이션 진입점.
 *
 * 역할: DOM에 루트를 마운트하고 전역 스타일·에러 경계를 적용한다.
 * 주요 기능: StrictMode, ErrorBoundary로 App을 렌더링.
 * 연관 파일: App.tsx, components/ErrorBoundary.tsx, index.css
 */
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { ErrorBoundary } from "./components/ErrorBoundary";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
);
