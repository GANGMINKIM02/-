/**
 * 플로팅 FAB + 챗 패널 통합 위젯.
 */
import { useState } from "react";
import { useLocation } from "react-router-dom";
import { ChatbotFab } from "./ChatbotFab";
import { ChatbotPanel } from "./ChatbotPanel";

interface ChatbotWidgetProps {
  docId?: string;
}

function getPageContext(pathname: string): string {
  if (pathname === "/") {
    return [
      "현재 화면: 업로드 페이지",
      "주요 구성: 파일 업로드 카드, 사건 유형 선택 팝업, 기존 프로젝트 목록, 상단 저장소 관리 링크(관리자만).",
      "버튼/동작: Browse Files로 파일 선택, 업로드로 사건 유형 팝업 열기와 업로드 진행, 사건 유형 버튼으로 민사·형사·가정·행정 선택, 팝업의 취소/업로드로 닫기 또는 확정.",
      "기능: 파일을 드래그하거나 선택해 새 프로젝트를 시작하고, 기존 프로젝트에서 이전 문서를 열거나 삭제할 수 있습니다.",
    ].join("\n");
  }

  if (pathname.includes("/summary")) {
    return [
      "현재 화면: 요약 페이지",
      "주요 구성: 왼쪽 원문 미리보기, 오른쪽 요약문 편집 영역, 상단 파일명 표시, 하단 AI 프롬프트 입력 바.",
      "버튼/동작: PageNavigator의 왼쪽/오른쪽 화살표로 원문 페이지 이동, AI 프롬프트 입력 후 화살표 버튼 또는 Enter로 요약 수정 요청, 요약은 수정 후 자동 저장.",
      "기능: 원문을 보면서 요약을 생성하거나 다시 다듬을 수 있습니다.",
    ].join("\n");
  }

  if (pathname.includes("/translate")) {
    return [
      "현재 화면: 번역 페이지",
      "주요 구성: 왼쪽 요약문, 오른쪽 이지리드 번역문 편집 영역, 하단 AI 프롬프트 입력 바.",
      "버튼/동작: AI 프롬프트의 화살표 버튼 또는 Enter로 번역문 AI 수정 요청, 편집기 툴바의 되돌리기/다시 실행/굵게/글자 크기 버튼으로 본문 서식 조정.",
      "기능: 요약을 확인하면서 이지리드 번역을 직접 편집하고 자동 저장할 수 있습니다.",
    ].join("\n");
  }

  if (pathname.includes("/images")) {
    return [
      "현재 화면: 그림 페이지",
      "주요 구성: 왼쪽 번역문, 오른쪽 그림 DB 검색/목록, 하단 그림 검색 프롬프트.",
      "버튼/동작: 그림 DB 검색창으로 제목/파일명 검색, 카드 드래그로 번역문 항목에 그림 배치, 배치된 그림의 X 버튼으로 삭제, 그림 검색 프롬프트의 화살표 버튼 또는 Enter로 웹 그림 검색.",
      "기능: 번역문 각 항목에 맞는 이미지를 찾고 배치하거나 제거할 수 있습니다.",
    ].join("\n");
  }

  if (pathname.includes("/export")) {
    return [
      "현재 화면: 내보내기 페이지",
      "주요 구성: 최종 PDF/Word 미리보기, 하단 추출 버튼 3개.",
      "버튼/동작: PDF 추출하기로 PDF 다운로드, Word 추출하기로 DOCX 다운로드, 업로드 화면으로 돌아가기로 처음 화면 복귀.",
      "기능: 완성된 이지리드를 확인한 뒤 필요한 형식으로 내보냅니다.",
    ].join("\n");
  }

  if (pathname.includes("/admin/storage")) {
    return [
      "현재 화면: 관리자 저장소 페이지",
      "주요 구성: 계정별 저장 프로젝트 표, 각 행의 삭제 버튼, 상단 업로드로 돌아가기 링크.",
      "버튼/동작: 각 행의 X 버튼으로 해당 계정의 문서 저장 항목 삭제, 업로드로 돌아가기로 메인 화면 이동.",
      "기능: 관리자 계정이 사용자별 저장 현황을 확인하고 삭제할 수 있습니다.",
    ].join("\n");
  }

  return [
    `현재 화면 경로: ${pathname}`,
    "이 화면의 구성과 버튼 기능을 질문하면, 화면에 보이는 요소를 기준으로 설명하세요.",
  ].join("\n");
}

export function ChatbotWidget({ docId }: ChatbotWidgetProps) {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const pageContext = getPageContext(location.pathname);

  return (
    <>
      <ChatbotFab onClick={() => setOpen(true)} />
      <ChatbotPanel open={open} onClose={() => setOpen(false)} docId={docId} pageContext={pageContext} />
    </>
  );
}
