#!/usr/bin/env python3
"""nook-mcp：共读小屋 MCP 服务器——带调试日志版"""

import os, sys, json, urllib.request, traceback
from mcp.server.fastmcp import FastMCP

NOOK_URL = os.environ.get("NOOK_URL", "").rstrip("/")
NOOK_PASS = os.environ.get("NOOK_PASS", "")
PORT = int(os.environ.get("PORT", 8001))

print(f"[boot] NOOK_URL={NOOK_URL}")
print(f"[boot] PORT={PORT}")
print(f"[boot] starting FastMCP...")

mcp = FastMCP("nook-mcp")

def nook_get(path):
    req = urllib.request.Request(
        f"{NOOK_URL}{path}",
        headers={"Cookie": f"rk={NOOK_PASS}"}
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

def nook_post(path, data):
    req = urllib.request.Request(
        f"{NOOK_URL}{path}",
        data=json.dumps(data).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Cookie": f"rk={NOOK_PASS}"
        }
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

@mcp.tool()
def list_pending() -> str:
    try:
        return json.dumps({"ok": True, "pending": nook_get("/api/pending")}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

@mcp.tool()
def list_books() -> str:
    try:
        return json.dumps({"ok": True, "books": nook_get("/api/books")}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

@mcp.tool()
def get_chapter(book: str, chapter: str = "") -> str:
    try:
        return json.dumps({"ok": True, "chapter": nook_get(f"/api/chapter/{book}/{chapter}")}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

@mcp.tool()
def get_note(book: str, chapter: str = "") -> str:
    try:
        return json.dumps({"ok": True, "note": nook_get(f"/api/note/{book}/{chapter}")}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

@mcp.tool()
def reply_annotation(book: str, chapter: str, annotation_id: str, reply: str) -> str:
    try:
        url = f"/api/annotations/{book}/{chapter}"
        annos = nook_get(url)
        for a in annos:
            if a["id"] == annotation_id:
                a.setdefault("replies", []).append({
                    "who": "ai",
                    "text": reply,
                    "ts": __import__("time").strftime("%Y-%m-%d %H:%M")
                })
                break
        nook_post(url, annos)
        return json.dumps({"ok": True, "msg": "已写入回复"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

print(f"[boot] tools registered, starting SSE on port {PORT}...")

if __name__ == "__main__":
    try:
        mcp.run(transport="sse")
    except Exception as e:
        print(f"[fatal] {traceback.format_exc()}", file=sys.stderr)
        sys.exit(1)