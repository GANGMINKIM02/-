"""API 요청·응답 Pydantic 스키마.

역할: FastAPI 엔드포인트와 서비스 계층 간 데이터 계약을 정의한다.
주요 기능: DocumentResponse, TranslationSegment, ChecklistReport 등 타입·모델.
관계: routers/documents(요청·응답), database(직렬화), services(내부 전달).
"""

from typing import Literal

from pydantic import BaseModel, Field

DocType = Literal["criminal", "civil", "family", "administrative", "unknown"]
DocumentStage = Literal["uploaded", "summarized", "translated"]


class ImagePlacement(BaseModel):
    id: str
    image_file: str
    line_index: int = 0
    title: str | None = None
    image_url: str | None = None
    section_heading: str | None = None
    image_base64: str | None = None  # export POST 전용 (브라우저에서 인코딩)
    auto_filled: bool = False  # 그림 탭 자동 배치 — X 삭제 불가


class TranslationSegment(BaseModel):
    id: str
    original: str
    easy_text: str
    image_file: str | None = None
    image_url: str | None = None
    title: str | None = None
    source: Literal["db", "solar", "manual"] = "db"
    image_placements: list[ImagePlacement] = Field(default_factory=list)


class ChecklistItemResult(BaseModel):
    id: str
    category: str
    label: str
    status: Literal["pass", "warn", "fail", "manual"]
    detail: str | None = None


class ChecklistReport(BaseModel):
    overall: Literal["pass", "warn", "fail"]
    summary: dict[str, int]
    items: list[ChecklistItemResult] = Field(default_factory=list)


class DocumentResponse(BaseModel):
    id: str
    filename: str
    doc_type: DocType
    stage: DocumentStage
    page_count: int
    full_text: str
    summary: str | None = None
    translation_segments: list[TranslationSegment] = Field(default_factory=list)
    translation_text: str | None = None
    checklist: ChecklistReport | None = None


class SummaryUpdate(BaseModel):
    summary: str
    full_text: str | None = None
    pages: list[str] | None = None
    filename: str | None = None
    doc_type: DocType | None = None


class RefineRequest(BaseModel):
    prompt: str
    summary: str | None = None
    segments: list[TranslationSegment] | None = None


class TranslationUpdate(BaseModel):
    segments: list[TranslationSegment]
    full_text: str | None = None
    pages: list[str] | None = None
    filename: str | None = None
    doc_type: DocType | None = None
    summary: str | None = None


class ExportRequest(BaseModel):
    summary: str | None = None
    segments: list[TranslationSegment] | None = None
    translation_text: str | None = None
    filename: str | None = None
    doc_type: DocType | None = None
    full_text: str | None = None
    pages: list[str] | None = None
    source_pdf_base64: str | None = None  # 서버 원본 유실 시 브라우저 IndexedDB PDF


class SummarizeRequest(BaseModel):
    full_text: str | None = None
    doc_type: DocType | None = None
    filename: str | None = None
    pages: list[str] | None = None


class DocumentEnsureRequest(BaseModel):
    """서버리스 환경에서 문서 메타가 유실됐을 때 클라이언트가 복구하는 페이로드."""

    full_text: str | None = None
    doc_type: DocType | None = None
    filename: str | None = None
    pages: list[str] | None = None
    summary: str | None = None


class DetectPlacementsRequest(DocumentEnsureRequest):
    """이미지 배치 추천 — 기존 배치 유지, 빈 항목만 자동 채움."""

    existing_placements: list[ImagePlacement] = Field(default_factory=list)
    translation_text: str | None = None


class DocTypeUpdate(BaseModel):
    doc_type: DocType


class UploadResponse(BaseModel):
    id: str
    filename: str
    doc_type: DocType
    page_count: int
    message: str
    pages: list[str] = Field(default_factory=list)
    full_text: str = ""


class UserProjectItem(BaseModel):
    doc_id: str
    filename: str
    created_at: str = ""
    updated_at: str = ""
    has_source: bool = False
    has_summary: bool = False
    has_translation: bool = False
    has_easyread_pdf: bool = False
    has_easyread: bool = False


class AdminUserStorageBlock(BaseModel):
    user_id: str
    projects: list[UserProjectItem] = Field(default_factory=list)


class AdminStorageOverview(BaseModel):
    users: list[AdminUserStorageBlock] = Field(default_factory=list)


class ArtifactTextResponse(BaseModel):
    content: str


class ImageCatalogItem(BaseModel):
    image_file: str
    title: str
    url: str
    source_url: str | None = None


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = Field(default_factory=list)
    page_context: str | None = None


class ChatResponse(BaseModel):
    reply: str
    sources: list[str] = Field(default_factory=list)


class ChatPromptResponse(BaseModel):
    system_prompt: str


class ChatPromptUpdate(BaseModel):
    system_prompt: str
