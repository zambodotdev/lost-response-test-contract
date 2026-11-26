#!/usr/bin/env python3
"""Minimal synthetic Streamable HTTP MCP provider + independent SQLite effect ledger.

Synthetic test fixture ONLY (modeled after fixtures/apc-test-provider/):
- POST /mcp: naive MCP server exposing `create_ticket` and `list_tickets` with NO built-in
  idempotency cache. Every `create_ticket` call inserts one new SQLite row (`T-1`, `T-2`, ...).
- GET /tickets?title_prefix=<K>: direct REST read over the SQLite table (outside MCP and
  outside any proxy) used as the shared external effect counter.
- GET /tickets/<ticket_id>: direct REST read of a single SQLite row.
"""

from __future__ import annotations

import argparse
import datetime
import http.server
import json
import sqlite3
import threading
import urllib.parse


class TicketStore:
    def __init__(self, db_path: str) -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                priority TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def create(self, title: str, description: str, priority: str) -> dict[str, object]:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO tickets (ticket_id, title, description, priority, created_at) "
                "VALUES ('PENDING', ?, ?, ?, ?)",
                (title, description, priority, now),
            )
            seq = int(cur.lastrowid or 1)
            tid = f"T-{seq}"
            self._conn.execute("UPDATE tickets SET ticket_id = ? WHERE seq = ?", (tid, seq))
            self._conn.commit()
        return {
            "id": tid,
            "title": title,
            "description": description,
            "priority": priority,
            "created_at": now,
            "version": 1,
        }

    def list_by_prefix(self, prefix: str) -> list[dict[str, object]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT ticket_id, title, description, priority, created_at FROM tickets "
                "WHERE title LIKE ? ORDER BY seq ASC",
                (prefix + "%",),
            ).fetchall()
        return [
            {
                "id": r[0],
                "title": r[1],
                "description": r[2],
                "priority": r[3],
                "created_at": r[4],
                "version": 1,
            }
            for r in rows
        ]

    def get(self, ticket_id: str) -> dict[str, object] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT ticket_id, title, description, priority, created_at FROM tickets "
                "WHERE ticket_id = ?",
                (ticket_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "id": row[0],
            "title": row[1],
            "description": row[2],
            "priority": row[3],
            "created_at": row[4],
            "version": 1,
        }


def make_handler(store: TicketStore):
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: object) -> None:
            return

        def _send_json(self, code: int, doc: object) -> None:
            raw = json.dumps(doc, sort_keys=True).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:
            parsed = urllib.parse.urlsplit(self.path)
            if parsed.path == "/tickets":
                qs = urllib.parse.parse_qs(parsed.query)
                prefix = (qs.get("title_prefix") or [""])[0]
                self._send_json(200, {"tickets": store.list_by_prefix(prefix)})
                return
            if parsed.path.startswith("/tickets/"):
                tid = urllib.parse.unquote(parsed.path[len("/tickets/") :]).strip("/")
                t = store.get(tid)
                if t is None:
                    self._send_json(404, {"error": "not_found"})
                else:
                    self._send_json(200, {"ticket": t})
                return
            self._send_json(404, {"error": "not_found"})

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0") or "0")
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            rid = body.get("id")
            method = body.get("method")
            if method == "initialize":
                self._send_json(
                    200,
                    {
                        "jsonrpc": "2.0",
                        "id": rid,
                        "result": {
                            "protocolVersion": "2025-03-26",
                            "capabilities": {"tools": {}},
                            "serverInfo": {"name": "naive-sqlite-ticket-mcp", "version": "0.1.0"},
                        },
                    },
                )
                return
            if method == "notifications/initialized":
                self._send_json(200, {"ok": True})
                return
            if method == "tools/list":
                self._send_json(
                    200,
                    {
                        "jsonrpc": "2.0",
                        "id": rid,
                        "result": {
                            "tools": [
                                {
                                    "name": "create_ticket",
                                    "description": "Create one durable ticket row (non-idempotent upstream).",
                                    "inputSchema": {
                                        "type": "object",
                                        "properties": {
                                            "title": {"type": "string"},
                                            "description": {"type": "string"},
                                            "priority": {"type": "string"},
                                        },
                                        "required": ["title", "description", "priority"],
                                    },
                                }
                            ]
                        },
                    },
                )
                return
            if method == "tools/call":
                params = body.get("params") or {}
                tname = params.get("name")
                args = params.get("arguments") or {}
                if tname == "create_ticket":
                    ticket = store.create(
                        str(args.get("title", "")),
                        str(args.get("description", "")),
                        str(args.get("priority", "normal")),
                    )
                    self._send_json(
                        200,
                        {
                            "jsonrpc": "2.0",
                            "id": rid,
                            "result": {
                                "content": [{"type": "text", "text": json.dumps(ticket, sort_keys=True)}],
                                "structuredContent": ticket,
                                "isError": False,
                            },
                        },
                    )
                    return
            self._send_json(
                200,
                {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "Method not found"}},
            )

    return Handler


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=47410)
    ap.add_argument("--db", default="provider_tickets.sqlite")
    args = ap.parse_args()
    store = TicketStore(args.db)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(store))
    print(json.dumps({"mcp_url": f"http://127.0.0.1:{args.port}/mcp", "backend_url": f"http://127.0.0.1:{args.port}"}), flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
