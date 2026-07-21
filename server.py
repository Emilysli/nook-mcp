#!/usr/bin/env python3
"""nook-mcp：共读小屋 MCP 服务器——让归思凛可以直接读写批注"""

import json, os, sys, urllib.request, urllib.parse
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
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        try:
            params = json.loads(body) if body else {}
        except json.JSONDecodeError:
            params = {}
        
        result = self.handle(params)
        resp = json.dumps(result, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(resp)
    
    def handle(self, params):
        action = params.get("action", "")
        
        if action == "list_pending":
            return self.list_pending()
        elif action == "reply_annotation":
            return self.reply_annotation(params)
        elif action == "get_note":
            return self.get_note(params)
        elif action == "list_books":
            return self.list_books()
        elif action == "get_chapter":
            return self.get_chapter(params)
        else:
            return {"error": f"unknown action: {action}"}
    
    def list_pending(self):
        """列出所有还没回应的批注"""
        try:
            pending = nook_get("/api/pending")
            return {"ok": True, "pending": pending}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def reply_annotation(self, params):
        """回应对应批注"""
        book = params.get("book")
        chapter = params.get("chapter")
        annotation_id = params.get("annotation_id")
        reply_text = params.get("reply", "")
        
        if not all([book, annotation_id, reply_text]):
            return {"ok": False, "error": "缺少必要参数"}
        
        try:
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
            resp = nook_post(url, annos)
            return {"ok": True, "msg": "已写入回复"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def get_note(self, params):
        """读取剧情笔记"""
        try:
            note = nook_get(f"/api/note/{params['book']}/{params['chapter']}")
            return {"ok": True, "note": note}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def list_books(self):
        """列出共读小屋里的所有书"""
        try:
            books = nook_get("/api/books")
            return {"ok": True, "books": books}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def get_chapter(self, params):
        """读取指定章节的内容"""
        try:
            ch = nook_get(f"/api/chapter/{params['book']}/{params['chapter']}")
            return {"ok": True, "chapter": ch}
        except Exception as e:
            return {"ok": False, "error": str(e)}

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), MCPHandler)
    print(f"nook-mcp running on :{PORT}")
    server.serve_forever()