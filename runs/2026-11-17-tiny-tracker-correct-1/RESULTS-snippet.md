Run 409891e807 against http://127.0.0.1:47310/mcp (tool create_ticket), started 2026-11-17T02:13:28.514342Z.

| Assertion | Outcome | Evidence |
|---|---|---|
| A1 | pass | external effect count for the logical operation is exactly 1 |
| A2 | pass | mismatched retry produced no new effect and was explicitly refused |
| A3 | unproven | contract pass condition is the K-only leg: no committed digest exists, so K-only recovery cannot be scored; run-id leg scored fail separately in the evidence |
| A4 | pass | every recorded retry resolved to the original outcome, a digest-verifiable record of it, or an explicit non-success state |
| A5 | fail | scored by the driver: the delayed leg at 2026-11-18T02:16:00Z resolved T-1 by run id (HTTP 200) but digest_equal is false (no digest is served) and the lookup by K answered 404 (no K-addressable record in 0.1.0); a K-only replay beside it held at +24 h (replayed: true, count 1 to 1), recorded in a5_supplementary_konly.json, not a score |
