Run 11d26bb926 against http://127.0.0.1:47410/mcp (tool create_ticket), started 2026-11-20T14:11:23.885327Z.

| Assertion | Outcome | Evidence |
|---|---|---|
| A1 | fail | external effect count for the logical operation is 2, not 1 |
| A2 | fail | mismatched retry executed as a new call: effect count rose from 1 to 2, response class success |
| A3 | fail | contract pass condition is the K-only leg: K-only recovery did not return the original committed outcome; the direct record lookup by K returned not found and no K-keyed lookup returned the committed digest; run-id leg scored fail separately in the evidence |
| A4 | pass | every recorded retry resolved to the original outcome, a digest-verifiable record of it, or an explicit non-success state |
| A5 | unproven | the 24 hour delayed leg cannot complete on the planting day; attempt 1 is planted with its commit timestamp recorded and the delayed leg is runnable later by run id and by K |
