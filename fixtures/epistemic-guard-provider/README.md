# Synthetic Unmodified MCP Provider (`epistemic-guard` proxy evaluation)

This directory contains a stdlib-only synthetic MCP Streamable HTTP server (`naive_mcp_provider.py`)
used to evaluate **out-of-process proxy mediation** (`epistemic-guard mcp-http-proxy`) against the
Lost-Response Test Contract (`A1`–`A5`) alongside an **unwrapped control run**.

- **No built-in idempotency in the upstream server:** Every `POST /mcp` `create_ticket` call inserts
  a new SQLite row (`T-1`, `T-2`, ...). Running `lost_response.py` directly against `naive_mcp_provider.py`
  serves as the negative control (`external_effect_count == 2` on `A1` and `A2`).
- **Independent external effect counter:** `GET /tickets?title_prefix=<K>` reads the SQLite table
  directly, bypassing both MCP and `epistemic-guard`'s receipt log. `epistemic-guard` receipts are
  never counted as external effects.
- Synthetic fixture only; never connect to production credentials or external services.
