# Easy-Read 판결문 작성 보조 서비스

발달장애인이 이해할 수 있는 **이지리드(Easy-Read) 판결문** 작성을 돕는 웹 서비스입니다.

## 구조

```
실험4/
├── backend/          FastAPI API 서버
├── frontend/         React + Vite UI
├── db_rules.py       LEGAL_DB (564 규칙 → 661 이지리드+이미지)
├── images/           시각자료 PNG
└── data/             업로드·SQLite (자동 생성)
```

## 빠른 시작

### 1. 백엔드

```bash
cd "실험4"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# .env 에 UPSTAGE_API_KEY 설정 (없으면 MOCK 모드)
uvicorn backend.main:app --reload --port 8001
```

### 2. 프론트엔드

```bash
cd frontend
npm install
npm run dev
```

브라우저: http://localhost:5173  
API 문서: http://localhost:8001/docs

## YAML 규칙 추가 (코드 수정 없음)

- **작성 규칙 (형사)**: `backend/prompts/writing_rules/criminal.yaml`
- **요약 컨셉**: `backend/prompts/summary/criminal.yaml` 등
- 파일 수정 후 백엔드 재시작 → 다음 요약/번역부터 반영

## API 흐름

1. `POST /documents/upload` — PDF/TXT 업로드 → OCR
2. `POST /documents/{id}/summarize` — Solar 요약
3. `PATCH /documents/{id}/summary` — 수동 수정
4. `POST /documents/{id}/summary/refine` — 프롬프트 AI 수정
5. `POST /documents/{id}/translate` — LEGAL_DB + Solar 이지리드
6. `GET /documents/{id}/export.docx` — Word 출력

## Upstage

- Document OCR: 업로드 문서 텍스트 추출
- Solar Pro: 요약·번역·수정
- API 키 없을 때 `MOCK_UPSTAGE=true` 로 데모 가능

## Vercel 배포

저장소: [github.com/mingpang1197/final](https://github.com/mingpang1197/final)

1. [vercel.com](https://vercel.com) → **Add New Project** → `mingpang1197/final` 연결
2. Framework Preset: **Other** (`vercel.json` 사용)
3. **Environment Variables**:
   - `UPSTAGE_API_KEY` — Upstage API 키
   - `MOCK_UPSTAGE` — `false` (실제 AI 사용 시)
4. Deploy

로컬 개발 시에는 `pip install -r requirements-dev.txt` 로 uvicorn·PyMuPDF를 추가 설치하세요.
