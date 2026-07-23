/**
 * React 렌더링 오류 경계 컴포넌트.
 *
 * 역할: 하위 트리 렌더 오류를 잡아 앱 전체 크래시를 방지한다.
 * 주요 기능: 오류 메시지 표시, 새로고침 버튼 제공.
 * 연관 파일: main.tsx
 */
import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("App render error:", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="max-w-lg mx-auto mt-16 p-8 bg-white rounded-xl shadow-sm border border-red-200">
          <h1 className="text-xl font-bold text-red-700 mb-2">화면을 불러오지 못했습니다</h1>
          <p className="text-slate-600 text-sm mb-4">
            배포 직후 예전 파일이 남아 있을 수 있습니다. 아래 버튼으로 새로고침해 주세요.
          </p>
          <button
            type="button"
            className="px-4 py-2 bg-slate-800 text-white rounded-lg text-sm hover:bg-slate-700"
            onClick={() => window.location.reload()}
          >
            새로고침
          </button>
          <pre className="mt-4 p-3 bg-slate-100 rounded text-xs overflow-auto text-red-800">
            {this.state.error.message}
          </pre>
        </div>
      );
    }
    return this.props.children;
  }
}
