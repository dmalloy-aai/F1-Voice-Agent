#!/usr/bin/env python3
"""F1 Voice Agent — server: mints tokens, searches KB, serves frontend."""

import os
import re
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

API_KEY = os.environ.get("ASSEMBLYAI_API_KEY")
if not API_KEY:
    print("⚠  ASSEMBLYAI_API_KEY not set — /api/token will return 401")

SCRIPT_DIR = Path(__file__).parent
KB_PATH = SCRIPT_DIR / "knowledge-base.md"
if not KB_PATH.exists():
    print(f"✗ Knowledge base not found: {KB_PATH}")
    sys.exit(1)

KB_TEXT = KB_PATH.read_text(encoding="utf-8")
KB_LINES = len(KB_TEXT.splitlines())

NUMERIC_KW = {
    "number", "numbers", "how many", "how much", "percent", "%", "mw", "kw",
    "kg", "bar", "rpm", "second", "seconds", "stat", "stats", "figure",
    "figures", "data", "metric",
}


def _parse_sections(text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    cur_h, cur_l = "", []
    for line in text.splitlines():
        if line.startswith("## "):
            if cur_l:
                sections.append((cur_h, "\n".join(cur_l)))
            cur_h, cur_l = line, [line]
        else:
            cur_l.append(line)
    if cur_l:
        sections.append((cur_h, "\n".join(cur_l)))
    return sections


KB_SECTIONS = _parse_sections(KB_TEXT)


def search_kb(query: str) -> str:
    ql = query.lower()
    qw = set(re.findall(r"\w+", ql))
    scored: list[tuple[int, str]] = []
    kn_section: str | None = None
    for h, b in KB_SECTIONS:
        if "key numbers" in h.lower():
            kn_section = b
        scored.append((sum(1 for w in qw if w in b.lower()), b))
    scored.sort(reverse=True, key=lambda x: x[0])
    top3 = [b for s, b in scored[:3] if scored[0][0] > 0]
    is_numeric = bool(qw & NUMERIC_KW) or any(k in ql for k in NUMERIC_KW)
    if is_numeric and kn_section and kn_section not in top3:
        top3.append(kn_section)
    return "\n\n---\n\n".join(top3) if top3 else "No relevant sections found."


app = FastAPI()


@app.get("/api/token")
async def get_token():
    if not API_KEY:
        raise HTTPException(status_code=401, detail="ASSEMBLYAI_API_KEY not configured on server.")
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://agents.assemblyai.com/v1/token",
            params={"expires_in_seconds": "300", "max_session_duration_seconds": "3600"},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
    if not resp.is_success:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@app.get("/api/search")
async def search(query: str = ""):
    return {"result": search_kb(query) if query else "No query provided."}


@app.get("/")
async def index():
    return HTMLResponse((SCRIPT_DIR / "index.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8081))
    print(f"✓ Knowledge base loaded ({KB_LINES} lines)")
    print(f"✓ Server starting at http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
