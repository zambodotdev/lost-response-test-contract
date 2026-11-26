# epistemic-guard proxy adapter contribution

This contribution adds an out-of-process Streamable HTTP MCP proxy adapter (`epistemic-guard`
`McpStreamableHttpProxy`, MIT License, https://github.com/AlienatedAliens/epistemic-guard,
tested at commit `b6397e9` on `v0.6-dev`) alongside a stdlib-only synthetic non-idempotent MCP
provider (`fixtures/epistemic-guard-provider/naive_mcp_provider.py`) and two recorded loopback runs.

## Scope & Neutrality

- `fixtures/epistemic-guard-provider/naive_mcp_provider.py` is an unmodified, idempotency-unaware
  Streamable HTTP MCP server backed by a local SQLite `tickets` table exposed separately via
  `GET /tickets?title_prefix=<K>`.
- `count_effects()` reads `GET <backend_url>/tickets?title_prefix=<K>` directly against the
  SQLite provider, bypassing MCP and `epistemic-guard`. Proxy receipt rows are never counted as
  external effects.
- Two local loopback runs executed with the unmodified `fixtures/harness/lost_response.py` driver
  are included:
  1. `runs/2026-11-20-epistemic-guard-unwrapped-control/` (calling `naive_mcp_provider.py`
     directly without the proxy): `A1: fail` (`effect_count == 2`), `A2: fail` (`effect_count == 2`),
     `A3: fail` (`404` / no committed digest), `A4: pass`, `A5: unproven` (planted).
  2. `runs/2026-11-20-epistemic-guard-http-proxy/` (wrapping the exact same `naive_mcp_provider.py`
     behind `epistemic-guard mcp-http-proxy --aer1`): `A1: pass` (`effect_count == 1`), `A2: pass`
     (`effect_count == 1`, `HTTP 409` / `jsonrpc_error:-32602` refusal), `A3: pass` (both `run_id`
     and `K-only` `GET /receipts/<K>` legs return `HTTP 200` with Section 6 `sha256(canonical_bytes)`
     `recomputation.status == "matched"`), `A4: pass`, `A5: unproven` (`a5_plant.json` recorded).

## Limits

These runs are local loopback evaluations (`127.0.0.1`) against the synthetic SQLite provider, not
runs against a remote hosted multi-tenant deployment; `A5` requires the 24-hour delayed leg after
`due_at`. No third-party certification is claimed.
