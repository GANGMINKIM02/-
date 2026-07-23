"""Vercel Serverless Function 진입점.

역할: Vercel 배포 시 api/index.py가 ASGI 앱으로 backend.main.app을 노출한다.
주요 기능: 프로젝트 루트를 sys.path에 추가 후 FastAPI app import.
관계: backend/main.py의 app 객체를 re-export한다.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.main import app  # noqa: F401
