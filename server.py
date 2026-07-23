#!/usr/bin/env python3
"""nook-mcp：共读小屋 MCP 服务器——Starlette SSE 版"""

import os, json, urllib.request, traceback
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import (
    TextContent,
    Tool,
    CallToolResult,
)
from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from sse_starlette.sse import EventSourceResponse
import uvicorn

NOOK_URL = os.environ.get("NOOK_URL", "").rstrip("/")
NOOK_PASS = os.environ.get("NOOK_PASS", "")
PORT = int(os.environ.get("PORT", 8001))

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

server = Server("nook-mcp")

@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return [
        Tool(
            name="list_pending",
            description="列出所有还没回应的批注",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="list_books",
            description="列出共读小屋里的所有书",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="get_chapter",
            description="读取指定章节的内容",
            inputSchema={
                "type": "object",
                "properties": {
                    "book": {"type": "string"},
                    "chapter": {"type": "string"}
                },
                "required": ["book"]
            }
        ),
        Tool(
            name="get_note",
            description="读取剧情笔记",
            inputSchema={
                "type": "object",
                "properties": {
                    "book": {"type": "string"},
                    "chapter": {"type": "string"}
                },
                "required": ["book"]
            }
        ),
        Tool(
            name="reply_annotation",
            description="回应对应批注",
            inputSchema={
                "type": "object",
                "properties": {
                    "book": {"type": "string"},
                    "chapter": {"type": "string"},
                    "annotation_id": {"type": "string"},
                    "reply": {"type": "string"}
                },
                "required": ["book", "annotation_id", "reply"]
            }
        ),
    ]

def _run_tool(name: str, args: dict) -> str:
    try:
        if name == "list_pending":
            pending = nook_get("/api/pending")
            return json.dumps({"ok": True, "pending": pending}, ensure_ascii=False)
        elif name == "list_books":
            books = nook_get("/api/books")
            return json.dumps({"ok": True, "books": books}, ensure_ascii=False)
        elif name == "get_chapter":
            ch = nook_get(f"/api/chapter/{args['book']}/{args.get('chapter', '')}")
            return json.dumps({"ok": True, "chapter": ch}, ensure_ascii=False)
        elif name == "get_note":
            note = nook_get(f"/api/note/{args['book']}/{args.get('chapter', '')}")
            return json.dumps({"ok": True, "note": note}, ensure_ascii=False)
        elif name == "reply_annotation":
            url = f"/api/annotations/{args['book']}/{args.get('chapter', '')}"
            annos = nook_get(url)
            for a in annos:
                if a["id"] == args["annotation_id"]:
                    a.setdefault("replies", []).append({
                        "who": "ai",
                        "text": args["reply"],
                        "ts": __import__("time").strftime("%Y-%m-%d %H:%M")
                    })
                    break
            nook_post(url, annos)
            return json.dumps({"ok": True, "msg": "已写入回复"}, ensure_ascii=False)
        else:
            return json.dumps({"ok": False, "error": f"unknown tool: {name}"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e), "trace": traceback.format_exc()}, ensure_ascii=False)

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    result = _run_tool(name, arguments)
    return [TextContent(type="text", text=result)]

# SSE transport setup
from mcp.server.sse import SseServerTransport
sse = SseServerTransport("/messages")

async def handle_sse(request: Request):
    async with sse.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        await server.run(
            streams[0], streams[1],
            InitializationOptions(
                server_name="nook-mcp",
                server_version="1.0.0"
            )
        )

async def handle_messages(request: Request):
    await sse.handle_post_message(request.scope, request.receive, request._send)

async def root(request: Request):
    return PlainTextResponse("ok")

app = Starlette(routes=[
    Route("/", endpoint=root),
    Route("/sse", endpoint=handle_sse),
    Mount("/messages", routes=[
        Route("/", endpoint=handle_messages, methods=["POST"]),
    ]),
])

if __name__ == "__main__":
    print(f"nook-mcp (Starlette SSE) starting on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)