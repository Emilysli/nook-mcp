#!/usr/bin/env python3
"""nook-mcp：共读小屋 MCP 服务器——Streamable HTTP 版"""

import os, json, urllib.request, urllib.parse
from mcp.server.fastmcp import FastMCP

NOOK_URL = os.environ.get("NOOK_URL", "").rstrip("/")
NOOK_PASS = os.environ.get("NOOK_PASS", "")
PORT = int(os.environ.get("PORT", 8001))

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
    """列出所有还没回应的批注"""
    try:
        pending = nook_get("/api/pending")
        return json.dumps({"ok": True, "pending": pending}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

@mcp.tool()
def list_books() -> str:
    """列出共读小屋里的所有书"""
    try:
        books = nook_get("/api/books")
        return json.dumps({"ok": True, "books": books}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

@mcp.tool()
def get_chapter(book: str, chapter: str = "") -> str:
    """读取指定章节的内容"""
    try:
        ch = nook_get(f"/api/chapter/{book}/{chapter}")
        return json.dumps({"ok": True, "chapter": ch}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

@mcp.tool()
def get_note(book: str, chapter: str = "") -> str:
    """读取剧情笔记"""
    try:
        note = nook_get(f"/api/note/{book}/{chapter}")
        return json.dumps({"ok": True, "note": note}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

@mcp.tool()
def reply_annotation(book: str, chapter: str, annotation_id: str, reply: str) -> str:
    """回应对应批注"""
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

if __name__ == "__main__":
    print(f"nook-mcp (Streamable HTTP) starting on :{PORT}")
    mcp.run(transport="sse", host="0.0.0.0", port=PORT)