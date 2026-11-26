"""epistemic-guard Streamable HTTP proxy adapter for the lost-response harness.

Evaluates an unmodified, non-idempotent upstream MCP server (`naive_mcp_provider.py`)
in two configurations:
  1. Unwrapped control (`receipt_base_url` omitted): caller talks directly to the
     upstream MCP server (`A1` and `A2` double-execute; no signed receipts exist).
  2. Proxied (`epistemic-guard mcp-http-proxy --aer1`): caller talks to the
     out-of-process proxy, which binds caller operation identity `K` via
     `params._meta.operation_key` (and `Idempotency-Key`), signs Ed25519 + RFC 6962
     Merkle + AER-1 receipts to an append-only JSONL log, refuses mismatched-arg
     retries (`HTTP 409` / JSON-RPC `-32602`), and serves `GET /receipts/<id_or_K>`.

External effect counter:
  Reads `GET <backend_url>/tickets?title_prefix=<K>` directly from the upstream
  SQLite provider, never from `epistemic-guard`'s receipt log.
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone

from .base import SystemAdapter

ADAPTER_VERSION = "0.1.0"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def substitute(template, values):
    if isinstance(template, str):
        out = template
        for k, v in values.items():
            out = out.replace("{" + k + "}", v)
        return out
    if isinstance(template, dict):
        return {k: substitute(v, values) for k, v in template.items()}
    if isinstance(template, list):
        return [substitute(v, values) for v in template]
    return template


def _http_request(url: str, *, method: str = "GET", payload: object = None, extra_headers: dict | None = None):
    started = time.time()
    sent_at = utcnow()
    hdrs = {"Accept": "application/json"}
    data = None
    if payload is not None:
        hdrs["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    if extra_headers:
        hdrs.update(extra_headers)
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            status = int(resp.status)
            resp_hdrs = {k.lower(): v for k, v in resp.headers.items()}
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        status = int(exc.code)
        resp_hdrs = {k.lower(): v for k, v in exc.headers.items()}
    text = raw.decode("utf-8", errors="replace")
    try:
        body_json = json.loads(text) if text else None
    except ValueError:
        body_json = {"_non_json_body": text[:4000]}
    meta = {
        "url": url,
        "method": method,
        "sent_at": sent_at,
        "received_at": utcnow(),
        "elapsed_ms": round((time.time() - started) * 1000),
        "http_status": status,
        "content_type": resp_hdrs.get("content-type"),
        "response_bytes": len(raw),
        "headers": resp_hdrs,
    }
    return meta, body_json, text


def _classify(meta: dict, body: object) -> str:
    if meta["http_status"] not in (200, 409) and not isinstance(body, dict):
        return f"http_error:{meta['http_status']}"
    if not isinstance(body, dict) or body.get("_non_json_body"):
        return "unparseable"
    if body.get("error"):
        code = (body.get("error") or {}).get("code", "unknown")
        return f"jsonrpc_error:{code}"
    res = body.get("result")
    if not isinstance(res, dict):
        return "empty_result"
    if res.get("isError"):
        return "tool_error:isError"
    return "success"


def _recompute_aer1_output_hash(aer1_doc: object) -> dict[str, object]:
    if not isinstance(aer1_doc, dict):
        return {"status": "not_computable", "reason": "no AER-1 envelope present on record"}
    cb = aer1_doc.get("canonical_bytes")
    oh = aer1_doc.get("output_hash")
    if not isinstance(cb, str) or not isinstance(oh, str):
        return {"status": "not_computable", "reason": "missing canonical_bytes or output_hash"}
    try:
        raw = base64.b64decode(cb, validate=True)
    except Exception as exc:
        return {"status": "mismatched", "reason": f"invalid base64: {exc}"}
    want = "sha256:" + hashlib.sha256(raw).hexdigest()
    return {
        "status": "matched" if want == oh else "mismatched",
        "served_output_hash": oh,
        "recomputed_output_hash": want,
    }


class Adapter(SystemAdapter):
    name = "epistemic_guard"

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self.endpoint = self.config["mcp_url"]
        self.backend_url = self.config["backend_url"].rstrip("/")
        self.receipt_base_url = (self.config.get("receipt_base_url") or "").rstrip("/")
        self.tool_name = self.config.get("tool", "create_ticket")

    def _build_args(self, session_id: str, operation_key: str, mismatched: bool) -> dict:
        tmpl = dict(self.config["args_template"])
        if mismatched:
            m = self.config["mismatch"]
            tmpl[m["field"]] = m["altered_value"]
        return substitute(tmpl, {"K": operation_key, "SESSION": session_id})

    def initialize(self):
        init_req = {
            "jsonrpc": "2.0",
            "id": uuid.uuid4().hex,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "lost-response-harness", "version": "1.0.0"},
            },
        }
        imeta, ibody, _ = _http_request(self.endpoint, method="POST", payload=init_req)
        tl_req = {"jsonrpc": "2.0", "id": uuid.uuid4().hex, "method": "tools/list", "params": {}}
        tmeta, tbody, _ = _http_request(self.endpoint, method="POST", payload=tl_req)
        evidence = {
            "adapter": self.name,
            "adapter_version": ADAPTER_VERSION,
            "at": utcnow(),
            "mcp_url": self.endpoint,
            "backend_url": self.backend_url,
            "receipt_base_url": self.receipt_base_url or None,
            "mode": self.config.get("mode", "proxied"),
            "initialize": {"request": init_req, "transport": imeta, "body": ibody},
            "tools_list": {"request": tl_req, "transport": tmeta, "body": tbody},
        }
        summary = {
            "http_status": imeta["http_status"],
            "mode": self.config.get("mode", "proxied"),
            "proxied_by_epistemic_guard": bool(self.receipt_base_url),
        }
        return evidence, summary

    def execute(self, *, session_id, operation_key, mismatched=False, drop_response=False):
        args = self._build_args(session_id, operation_key, mismatched)
        rpc_payload = {
            "jsonrpc": "2.0",
            "id": uuid.uuid4().hex,
            "method": "tools/call",
            "params": {
                "name": self.tool_name,
                "arguments": args,
                "_meta": {"operation_key": operation_key, "session_id": session_id},
            },
        }
        meta, body, _ = _http_request(
            self.endpoint,
            method="POST",
            payload=rpc_payload,
            extra_headers={"Idempotency-Key": operation_key},
        )
        # Strip response headers that carry receipt ids/hashes before recording dropped metadata
        clean_meta = {
            k: v for k, v in meta.items() if k != "headers"
        }
        if drop_response:
            del body
            return {
                "arguments_sent": args,
                "call": {
                    "dropped": True,
                    "transport": clean_meta,
                    "note": (
                        "Full HTTP response read off the wire so the upstream execution and "
                        "proxy receipt commit completed, then discarded client-side. No body, "
                        "receipt id, or digest from attempt 1 is retained."
                    ),
                },
            }
        hdrs = meta.get("headers") or {}
        rcpt_id = hdrs.get("x-epistemic-guard-receipt-id")
        return {
            "arguments_sent": args,
            "call": {
                "dropped": False,
                "transport": clean_meta,
                "body": body,
                "response_class": _classify(meta, body),
                "replayed": hdrs.get("x-epistemic-guard-replayed") == "true",
                "receipt_ids": [rcpt_id] if rcpt_id else [],
            },
        }

    def count_effects(self, *, session_id, operation_key, label):
        q = urllib.parse.quote(operation_key, safe="")
        meta, body, _ = _http_request(f"{self.backend_url}/tickets?title_prefix={q}")
        tickets = ((body or {}).get("tickets") or []) if isinstance(body, dict) else []
        attributed = []
        ticket_ids = []
        for t in tickets:
            if not isinstance(t, dict):
                continue
            title_ok = str(t.get("title", "")).startswith(operation_key)
            sess_ok = session_id is None or session_id in str(t.get("description", ""))
            counted = meta["http_status"] == 200 and title_ok and sess_ok
            attributed.append(
                {
                    "ticket_id": t.get("id"),
                    "title": t.get("title"),
                    "priority": t.get("priority"),
                    "counted_as_execution": counted,
                }
            )
            if counted:
                ticket_ids.append(str(t.get("id")))

        # Note: external_effect_count is strictly len(ticket_ids) from the independent SQLite
        # provider. When proxied, we also record the server-issued receipt call_id for A3's
        # run-id leg if and only if external_effect_count >= 1.
        exec_ids = list(ticket_ids)
        if self.receipt_base_url and len(ticket_ids) == 1:
            rmeta, rbody, _ = _http_request(
                f"{self.receipt_base_url}/receipts/{urllib.parse.quote(operation_key, safe='')}"
            )
            if rmeta["http_status"] == 200 and isinstance(rbody, dict) and rbody.get("call_id"):
                exec_ids = [str(rbody["call_id"])]

        evidence = {
            "label": label,
            "session_id": session_id,
            "K": operation_key,
            "at": utcnow(),
            "method": (
                "GET <backend_url>/tickets?title_prefix=<K> directly against the independent "
                "SQLite provider (bypassing MCP and epistemic-guard). external_effect_count "
                "is strictly the number of provider SQLite rows created for (session_id, K)."
            ),
            "listing_http_status": meta["http_status"],
            "attributed_records": attributed,
            "backend_ticket_ids": ticket_ids,
            "execution_record_ids": exec_ids,
            "external_effect_count": len(ticket_ids),
        }
        return {"evidence": evidence, "files": {f"backend_{label}_tickets.json": {"transport": meta, "body": body}}}

    def fetch_record(self, record_id):
        q = urllib.parse.quote(str(record_id), safe="")
        if not self.receipt_base_url:
            meta, body, text = _http_request(f"{self.backend_url}/tickets/{q}")
            return {
                "record_id": record_id,
                "http_status": meta["http_status"],
                "url": meta["url"],
                "fetched_at": meta["received_at"],
                "body_text": text,
                "record_json": body,
                "digests": {},
                "recomputation": {
                    "status": "not_computable",
                    "reason": "unwrapped upstream MCP provider emits no signed receipts or digests",
                },
            }

        meta, body, text = _http_request(f"{self.receipt_base_url}/receipts/{q}")
        aer1_doc = (body or {}).get("aer1") if isinstance(body, dict) else None
        digests = {}
        if isinstance(aer1_doc, dict) and aer1_doc.get("output_hash"):
            digests["output_hash"] = aer1_doc["output_hash"]
        recomp = _recompute_aer1_output_hash(aer1_doc) if meta["http_status"] == 200 else {
            "status": "not_computable",
            "reason": f"HTTP {meta['http_status']}",
        }
        return {
            "record_id": record_id,
            "http_status": meta["http_status"],
            "url": meta["url"],
            "fetched_at": meta["received_at"],
            "body_text": text,
            "record_json": body,
            "digests": digests,
            "recomputation": recomp,
        }

    def recover_by_key(self, *, operation_key):
        q = urllib.parse.quote(operation_key, safe="")
        if not self.receipt_base_url:
            return {
                "attempts": [
                    {
                        "path": "direct K lookup (unwrapped server offers none)",
                        "http_status": 404,
                        "response_class": "not_found",
                        "digest_returned": None,
                        "note": "unwrapped upstream MCP server has no K-indexed recovery endpoint",
                    }
                ],
                "files": {},
            }

        meta, body, _text = _http_request(f"{self.receipt_base_url}/receipts/{q}")
        aer1_doc = (body or {}).get("aer1") if isinstance(body, dict) else None
        recomp = _recompute_aer1_output_hash(aer1_doc) if meta["http_status"] == 200 else {"status": "not_computable"}
        digest_ret = (aer1_doc or {}).get("output_hash") if isinstance(aer1_doc, dict) else None
        found_ok = meta["http_status"] == 200 and recomp.get("status") == "matched"
        attempt = {
            "path": "GET /receipts/<K> on epistemic-guard McpStreamableHttpProxy (using ONLY K)",
            "http_status": meta["http_status"],
            "response_class": "found" if found_ok else "not_found",
            "digest_returned": digest_ret,
            "recomputation": recomp,
            "depends_on_caller_convention": False,
        }
        return {
            "attempts": [attempt],
            "files": {"a3_konly_proxy_receipt_lookup.json": {"transport": meta, "body": body}},
        }
