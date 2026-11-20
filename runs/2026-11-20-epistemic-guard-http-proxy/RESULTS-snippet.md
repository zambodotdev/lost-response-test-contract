Run 8b6d1995c5 against http://127.0.0.1:47411/mcp (tool create_ticket), started 2026-11-20T14:11:24.190813Z.

| Assertion | Outcome | Evidence |
|---|---|---|
| A1 | pass | external effect count for the logical operation is exactly 1 |
| A2 | pass | mismatched retry produced no new effect and was explicitly refused |
| A3 | pass | contract pass condition is the K-only leg: recovered digest equals committed digest using only K; run-id leg scored pass separately in the evidence |
| A4 | pass | every recorded retry resolved to the original outcome, a digest-verifiable record of it, or an explicit non-success state |
| A5 | unproven | the 24 hour delayed leg cannot complete on the planting day; attempt 1 is planted with its commit timestamp recorded and the delayed leg is runnable later by run id and by K |
