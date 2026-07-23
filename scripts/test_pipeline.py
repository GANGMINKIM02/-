"""Quick end-to-end API smoke test."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
BASE = "http://127.0.0.1:8001/api"
SAMPLE = ROOT / "samples" / "sample_judgment.txt"


def main() -> int:
    if not SAMPLE.exists():
        print("sample not found:", SAMPLE)
        return 1

    with httpx.Client(timeout=120.0) as client:
        r = client.get(f"{BASE}/health")
        r.raise_for_status()
        print("health:", r.json())

        with SAMPLE.open("rb") as f:
            r = client.post(
                f"{BASE}/documents/upload",
                files={"file": ("sample_judgment.txt", f, "text/plain")},
            )
        r.raise_for_status()
        up = r.json()
        print("upload:", up)
        doc_id = up["id"]

        r = client.post(f"{BASE}/documents/{doc_id}/summarize")
        r.raise_for_status()
        doc = r.json()
        print("summarize stage:", doc["stage"])
        print("--- summary ---")
        print(doc.get("summary") or "(empty)")

        r = client.post(f"{BASE}/documents/{doc_id}/translate")
        r.raise_for_status()
        doc = r.json()
        print("translate stage:", doc["stage"])
        print("--- translation ---")
        print(doc.get("translation_text") or "(empty)")
        print("segments:", len(doc.get("translation_segments") or []))

        cl = doc.get("checklist")
        if cl:
            print("--- checklist ---")
            print("overall:", cl.get("overall"), "|", cl.get("summary"))
            for item in cl.get("items") or []:
                if item.get("status") in ("warn", "fail"):
                    print(f"  [{item['status']}] {item['label']}: {item.get('detail')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
