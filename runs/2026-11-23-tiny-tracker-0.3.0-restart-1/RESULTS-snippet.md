Run 42514abd5d against http://127.0.0.1:4710/mcp (tool create_ticket), started 2026-11-23T18:11:06.305366Z.

| Assertion | Outcome | Evidence |
|---|---|---|
| A1 | pass | external effect count for the logical operation is exactly 1 |
| A2 | pass | mismatched retry produced no new effect and was explicitly refused |
| A3 | pass | contract pass condition is the K-only leg: recovered digest equals committed digest using only K; run-id leg scored pass separately in the evidence |
| A4 | pass | every recorded retry resolved to the original outcome, a digest-verifiable record of it, or an explicit non-success state |
| A5 | pass | delayed leg 2026-11-24T18:34:52Z, after due 2026-11-24T18:11:06Z and a full server stop and start inside the window; recovery pass (K-only lookup returned the original outcome, recovered digest equals the committed digest recorded at plant time); retry protection pass (effect count 1, 1, 1; identical retry replayed, changed-argument retry refused idempotency_key_reused) |
