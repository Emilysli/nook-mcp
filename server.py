#!/usr/bin/env python3
"""nook-mcp：共读小屋 MCP 服务器——JSON-RPC 版"""

import json, os, sys, urllib.request, urllib.parse, traceback
from http.server import HTTPServer, BaseHTTPRequestHandler

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

class MCPHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ok")
    
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        try:
            req = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._send_error(-32700, "Parse error")
            return
        
        # 处理 JSON-RPC 协议
        req_id = req.get("id")
        method = req.get("method", "")
        params = req.get("params", {}) or {}
        
        # 根据 method 分发
        if method == "initialize":
            self._send_result(req_id, {
                "protocolVersion": "0.1.0",
                "capabilities": {
                    "tools": {},
                    "resources": {}
                },
                "serverInfo": {
                    "name": "nook-mcp",
                    "version": "1.0.0"
                }
            })
        elif method == "tools/list":
            self._send_result(req_id, {
                "tools": [
                    {
                        "name": "list_pending",
                        "description": "列出所有还没回应的批注",
                        "inputSchema": {
                            "type": "object",
                            "properties": {}
                        }
                    },
                    {
                        "name": "reply_annotation",
                        "description": "回应对应批注",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "book": {"type": "string"},
                                "chapter": {"type": "string"},
                                "annotation_id": {"type": "string"},
                                "reply": {"type": "string"}
                            },
                            "required": ["book", "annotation_id", "reply"]
                        }
                    },
                    {
                        "name": "list_books",
                        "description": "列出共读小屋里的所有书",
                        "inputSchema": {
                            "type": "object",
                            "properties": {}
                        }
                    },
                    {
                        "name": "get_chapter",
                        "description": "读取指定章节的内容",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "book": {"type": "string"},
                                "chapter": {"type": "string"}
                            },
                            "required": ["book", "chapter"]
                        }
                    },
                    {
                        "name": "get_note",
                        "description": "读取剧情笔记",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "book": {"type": "string"},
                                "chapter": {"type": "string"}
                            },
                            "required": ["book", "chapter"]
                        }
                    }
                ]
            })
        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {}) or {}
            result = self._run_tool(tool_name, tool_args)
            self._send_result(req_id, {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]})
        elif method == "resources/list":
            self._send_result(req_id, {"resources": []})
        elif method == "notifications/initialized":
            self._send_result(req_id, {})
        else:
            self._send_error(req_id, -32601, f"Method not found: {method}")
    
    def _run_tool(self, name, args):
        try:
            if name == "list_pending":
                pending = nook_get("/api/pending")
                return {"ok": True, "pending": pending}
            elif name == "reply_annotation":
                book = args.get("book")
                chapter = args.get("chapter", "")
                annotation_id = args.get("annotation_id")
                reply_text = args.get("reply", "")
                if not all([book, annotation_id, reply_text]):
                    return {"ok": False, "error": "缺少必要参数"}
                url = f"/api/annotations/{book}/{chapter}"
                annos = nook_get(url)
                for a in annos:
                    if a["id"] == annotation_id:
                        a.setdefault("replies", []).append({
                            "who": "ai",
                            "text": reply_text,
                            "ts": __import__("time").strftime("%Y-%m-%d %H:%M")
                        })
                        break
                nook_post(url, annos)
                return {"ok": True, "msg": "已写入回复"}
            elif name == "list_books":
                books = nook_get("/api/books")
                return {"ok": True, "books": books}
            elif name == "get_chapter":
                return {"ok": True, "chapter": nook_get(f"/api/chapter/{args['book']}/{args['chapter']}")}
            elif name == "get_note":
                return {"ok": True, "note": nook_get(f"/api/note/{args['book']}/{args['chapter']}")}
            else:
                return {"ok": False, "error": f"unknown tool: {name}"}
        except Exception as e:
            return {"ok": False, "error": str(e), "trace": traceback.format_exc()}
    
    def _send_result(self, req_id, result):
        resp = {"jsonrpc": "2.0", "result": result, "id": req_id}
        self._send_json(resp)
    
    def _send_error(self, req_id, code, message):
        resp = {"jsonrpc": "2.0", "error": {"code": code, "message": message}, "id": req_id}
        self._send_json(resp)
    
    def _send_json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), MCPHandler)
    print(f"nook-mcp (JSON-RPC) running on :{PORT}")
    server.serve_forever()