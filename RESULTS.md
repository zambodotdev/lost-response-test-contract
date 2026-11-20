# Results

Recorded runs of the contract in CONTRACT.md. One row per assertion, per
system, per run. Outcome is one of: pass, fail, unproven. Raw outputs are
linked, not summarized. Failures are reported as observed.

Run of 2026-11-16: Zambo production (https://zambo.dev/mcp), target tool
journal_log, harness in fixtures/harness/, raw outputs in
runs/2026-11-16-zambo-1/ (summary.json is the scored record; the run was
rescored from its own raw outputs with the corrected counter, see
runs/2026-11-16-zambo-1/RESCORE-NOTE.md). Operation identity K and the
run-scoped session identity for each assertion are recorded in the raw
outputs.

| Assertion | System | Outcome | Evidence | Date |
|---|---|---|---|---|
| A1 | Zambo | fail | External effect count 2, not 1: attempt 1 (response dropped) produced public receipt b49c66f5-5386-4bda-8bd6-2726bdfee7d1 and the identical retry produced a second distinct public receipt 2b8cefc9-72c0-415c-9525-71f6000679f9, each counted from the job's workflow snapshot and attributed through its public record. Raw: runs/2026-11-16-zambo-1/count_a1_final.json, runs/2026-11-16-zambo-1/a1_retry_identical.json | 2026-11-16 |
| A2 | Zambo | unproven | Attempt 1 committed (effect count 1, receipt e8f9f9b8-af48-45cb-8df0-5ce944346e05). The mismatched retry (one parameter changed: action) was refused at the metering layer with response class payment_required before it could execute, so the binding check was never exercised: no new effect occurred, and neither a binding rejection nor a silent execution was observed. Raw: runs/2026-11-16-zambo-1/a2_retry_mismatched.json, runs/2026-11-16-zambo-1/count_a2_final.json | 2026-11-16 |
| A3 | Zambo | fail | K-only leg failed: recovery holding only K (lr-op-498c01b299-a1) returned no committed outcome; the public record lookup by K returned 404 receipt_not_found and the K-keyed tool lookup returned no outcome or digest. Run-id leg passed separately: holding receipt id b49c66f5-5386-4bda-8bd6-2726bdfee7d1, resolution returned the unaltered record and recomputation matched (SHA-256 of the decoded canonical bytes equals the served output_hash sha256:d832cc994b22460549e19f3ee8282de128b23103462c76d078adcc8141113970). Raw: runs/2026-11-16-zambo-1/a3_summary.json, runs/2026-11-16-zambo-1/a3_runid_leg_receipt.json, runs/2026-11-16-zambo-1/a3_konly_run_lookup.json | 2026-11-16 |
| A4 | Zambo | pass | Recorded retry response classes: A1 retry success, corresponding to a committed record (the retry's own second receipt, counted in A1), not a generic success with no record; A2 retry payment_required, an explicit non-success state naming the situation. Raw: runs/2026-11-16-zambo-1/summary.json | 2026-11-16 |
| A5 | Zambo | fail | Delayed leg run 2026-11-17T16:17Z, after the due time 2026-11-17T15:49:33Z. K-only recovery failed: recovery holding only K (lr-op-498c01b299-a1) returned no committed outcome; the public record lookup by K returned 404 receipt_not_found and the K-keyed tool lookup (continuity_get_recent with K as the only identifier) returned no original outcome or digest, so no recovered digest equal to the committed digest was obtained. Run-id leg passed separately: holding receipt id b49c66f5-5386-4bda-8bd6-2726bdfee7d1, resolution returned the unaltered record, the served digest equaled the original committed digest sha256:d832cc994b22460549e19f3ee8282de128b23103462c76d078adcc8141113970, and recomputation matched. Protection against fresh execution failed: before the delayed retries the external effect count for the operation was 2; an identical delayed retry executed as a fresh call (success, new receipt 9eec3d97-ec95-4dfd-a56a-2726e52ff9c3) and a modified-parameter delayed retry (action changed to lost_response_probe_altered) also executed as a fresh call (success, new receipt 388b8cb7-30c9-4f84-a02f-145e92b17f59), raising the count to 4; neither was refused. Raw: runs/2026-11-16-zambo-1/a5_delayed_result.json, runs/2026-11-16-zambo-1/a5_delayed_runid_receipt.json, runs/2026-11-16-zambo-1/a5_delayed_konly_run_lookup.json, runs/2026-11-16-zambo-1/a5_delayed_konly_continuity_get_recent.json, runs/2026-11-16-zambo-1/a5_delayed_extra.json, runs/2026-11-16-zambo-1/count_a5_delayed_before_protection.json, runs/2026-11-16-zambo-1/count_a5_delayed_final.json, runs/2026-11-16-zambo-1/a5_delayed_retry_identical.json, runs/2026-11-16-zambo-1/a5_delayed_retry_mismatched.json | 2026-11-17 |

Run of 2026-11-16 (adapter refactor reproduction): Zambo production
(https://zambo.dev/mcp), target tool journal_log, raw outputs in
runs/2026-11-16-zambo-2/. This run was executed through the adapter
interface in fixtures/harness/adapters/ (the harness refactor that
separates the scoring driver from the per-system adapter; the Zambo
adapter is the original harness behavior, moved unchanged) to prove
the refactor before any other system is run through it. A1, A3, and
A4 reproduce the first run exactly. A2 differs, and the difference
is in the observation, not the code: in the first run the mismatched
retry was refused at the metering layer before it could execute, so
the binding check was never exercised and A2 was unproven; in this
run the mismatched retry executed, so A2 is scored on the exercised
behavior and recorded as observed.

| Assertion | System | Outcome | Evidence | Date |
|---|---|---|---|---|
| A1 | Zambo | fail | External effect count 2, not 1: attempt 1 (response dropped) produced public receipt 6b7d958a-f31b-47d1-8aef-09a868e2e865 and the identical retry produced a second distinct public receipt 1fb3a09e-1029-464c-9872-fb02fcc35a65, each counted from the job's workflow snapshot and attributed through its public record. Raw: runs/2026-11-16-zambo-2/count_a1_final.json, runs/2026-11-16-zambo-2/a1_retry_identical.json | 2026-11-16 |
| A2 | Zambo | fail | Attempt 1 committed (effect count 1, receipt 0c555b90-97fc-4763-a3c6-daa9fe1765dd). The mismatched retry (one parameter changed: action) executed as a normal new call: the effect count rose to 2 (second receipt 5ab9b4c5-3ec4-4598-81c9-8e9f428a17a7), the response class was success, and no binding rejection was returned. This exercises the check the first run could not reach (there the retry was refused with payment_required before executing, and A2 was recorded unproven). Raw: runs/2026-11-16-zambo-2/a2_retry_mismatched.json, runs/2026-11-16-zambo-2/count_a2_final.json | 2026-11-16 |
| A3 | Zambo | fail | K-only leg failed: recovery holding only K (lr-op-f63fe15895-a1) returned no committed outcome; the public record lookup by K returned 404 receipt_not_found and the K-keyed tool lookup returned no outcome or digest. Run-id leg passed separately: holding receipt id 6b7d958a-f31b-47d1-8aef-09a868e2e865, resolution returned the unaltered record and recomputation matched (SHA-256 of the decoded canonical bytes equals the served output_hash sha256:70a8dacb73738cf7e9d62f90e17d40191f42f7360fcb344d78a65753a2cd7fc1). Raw: runs/2026-11-16-zambo-2/a3_summary.json, runs/2026-11-16-zambo-2/a3_runid_leg_receipt.json, runs/2026-11-16-zambo-2/a3_konly_run_lookup.json | 2026-11-16 |
| A4 | Zambo | pass | Recorded retry response classes: A1 retry success, corresponding to a committed record (the retry's own second receipt, counted in A1); A2 retry success, corresponding to a committed record (the mismatched retry's own second execution, counted in A2). Neither is a generic success with no committed record. Raw: runs/2026-11-16-zambo-2/summary.json | 2026-11-16 |
| A5 | Zambo | unproven | The 24 hour delayed leg cannot complete on the planting day. The A1 operation is planted with its commit timestamp recorded in runs/2026-11-16-zambo-2/a5_plant.json (due 2026-11-17T20:33:31Z); the delayed leg runs later with: python3 fixtures/harness/lost_response.py --delayed-leg runs/2026-11-16-zambo-2/a5_plant.json | 2026-11-16 |

Runs of 2026-11-17: tiny-tracker 0.1.0 (npm
@mcp-write-safety/tiny-tracker), a small open-source teaching MCP
server published by IsoKron, run locally on 127.0.0.1 in three builds:
the correct build and two builds with one deliberate defect each.
Target tool create_ticket with K as its idempotency_key; the external
effect counter is the tiny-tracker backend's REST record, read
directly (GET /tickets?title_prefix=<K>), one ticket per execution.
Executed through fixtures/harness/adapters/tiny_tracker.py (adapter
0.1.0) at contract and harness commit 92bf1ba. Fault point:
client-side discard after the full response was read. tiny-tracker
issues no signed receipts and carries no committed result digest, so
A3 cannot reach digest equality on any build; the run-id leg resolved
the record (HTTP 200) and the driver scored that leg fail only because
no digest is served. Limits and per-run details are in each run
directory's RUN-NOTES.md.

Correct build, raw outputs in runs/2026-11-17-tiny-tracker-correct-1/:

| Assertion | System | Outcome | Evidence | Date |
|---|---|---|---|---|
| A1 | tiny-tracker (correct build) | pass | External effect count 1: attempt 1 (response dropped) created ticket T-1; the identical retry answered success with replayed: true and ticket T-1, and the count stayed 1. Raw: runs/2026-11-17-tiny-tracker-correct-1/count_a1_final.json, runs/2026-11-17-tiny-tracker-correct-1/a1_retry_identical.json | 2026-11-17 |
| A2 | tiny-tracker (correct build) | pass | Attempt 1 committed (T-2). The retry with one parameter changed (priority 3 to 4) was refused: isError, code idempotency_key_reused, outcome not_applied; the count stayed 1. Raw: runs/2026-11-17-tiny-tracker-correct-1/a2_retry_mismatched.json, runs/2026-11-17-tiny-tracker-correct-1/count_a2_final.json | 2026-11-17 |
| A3 | tiny-tracker (correct build) | unproven | The read by K (list_tickets by title prefix K, a caller convention, not a K index) returned the original ticket T-1; a same-key replay with the caller's own original arguments (K plus A, a write call) also answered T-1 (replayed: true, count 1 before and after). Neither carries a digest, and the record carries no committed result digest, so digest equality cannot be shown. Run-id leg: T-1 resolved with HTTP 200; scored fail by the driver because no digest is served. Raw: runs/2026-11-17-tiny-tracker-correct-1/a3_summary.json, runs/2026-11-17-tiny-tracker-correct-1/a3_konly_replay_create_ticket.json, runs/2026-11-17-tiny-tracker-correct-1/a3_runid_leg_receipt.json | 2026-11-17 |
| A4 | tiny-tracker (correct build) | pass | Retry response classes: A1 retry success (a replay naming the committed T-1); A2 retry tool_error:idempotency_key_reused, an explicit refusal. Raw: runs/2026-11-17-tiny-tracker-correct-1/summary.json | 2026-11-17 |
| A5 | tiny-tracker (correct build) | fail | Scored fail by the driver at 92bf1ba. The delayed leg ran at 2026-11-18T02:16:00Z against the same process as attempt 1 (up since 2026-11-17T02:12Z, never restarted). Run-id leg: T-1 resolved with HTTP 200, but digest_equal is false because tiny-tracker 0.1.0 serves no committed digest; the lookup by K answered 404 because this version has no record addressable by K. So the fail measures what 0.1.0 exposes, not what it remembers. Beside it, not driver output and not a score: a K-only check at +24 h (a5-supplementary.py) found T-1 by the K title prefix, and a same-key replay with the caller's original arguments answered T-1 with replayed: true, count 1 before and after; under the A3 ruling on issue 3394 that replay counts toward A1/A4, not A3 or A5. Raw: runs/2026-11-17-tiny-tracker-correct-1/a5_delayed_result.json, runs/2026-11-17-tiny-tracker-correct-1/a5_delayed_runid_receipt.json, runs/2026-11-17-tiny-tracker-correct-1/a5_supplementary_konly.json | 2026-11-18 |

Build with --defect idempotency-key-dropped, raw outputs in
runs/2026-11-17-tiny-tracker-key-dropped-1/:

| Assertion | System | Outcome | Evidence | Date |
|---|---|---|---|---|
| A1 | tiny-tracker (idempotency-key-dropped) | fail | External effect count 2, not 1: attempt 1 (response dropped) created T-1 and the identical retry created T-2, answering success with replayed: false. Raw: runs/2026-11-17-tiny-tracker-key-dropped-1/count_a1_final.json, runs/2026-11-17-tiny-tracker-key-dropped-1/a1_retry_identical.json | 2026-11-17 |
| A2 | tiny-tracker (idempotency-key-dropped) | fail | Attempt 1 committed (T-3). The retry with priority changed executed as a new call: the count rose from 1 to 2 (T-4), response class success, no binding rejection. Raw: runs/2026-11-17-tiny-tracker-key-dropped-1/a2_retry_mismatched.json, runs/2026-11-17-tiny-tracker-key-dropped-1/count_a2_final.json | 2026-11-17 |
| A3 | tiny-tracker (idempotency-key-dropped) | unproven | Scored unproven by the driver because no committed digest exists. Observed: list_tickets by title prefix K returned two tickets (T-1, T-2), and the same-key replay executed again, creating T-5 (count 2 before, 3 after); no path returned the original outcome as such. Raw: runs/2026-11-17-tiny-tracker-key-dropped-1/a3_summary.json, runs/2026-11-17-tiny-tracker-key-dropped-1/a3_konly_replay_create_ticket.json | 2026-11-17 |
| A4 | tiny-tracker (idempotency-key-dropped) | pass | Retry response classes: A1 retry success and A2 retry success, each corresponding to a ticket that retry created (counted in A1 and A2). Raw: runs/2026-11-17-tiny-tracker-key-dropped-1/summary.json | 2026-11-17 |
| A5 | tiny-tracker (idempotency-key-dropped) | unproven | Not run: the build was stopped after A1 to A4, and tiny-tracker keeps its record in memory. A5 runs on the correct build only. | 2026-11-17 |

Build with --defect idempotency-key-ignores-args, raw outputs in
runs/2026-11-17-tiny-tracker-ignores-args-1/:

| Assertion | System | Outcome | Evidence | Date |
|---|---|---|---|---|
| A1 | tiny-tracker (idempotency-key-ignores-args) | pass | External effect count 1: attempt 1 (response dropped) created T-1; the identical retry answered success with replayed: true and T-1. Raw: runs/2026-11-17-tiny-tracker-ignores-args-1/count_a1_final.json, runs/2026-11-17-tiny-tracker-ignores-args-1/a1_retry_identical.json | 2026-11-17 |
| A2 | tiny-tracker (idempotency-key-ignores-args) | fail | Attempt 1 committed (T-2, priority 3). The retry with priority 4 was not refused: it answered success with replayed: true and ticket T-2, from a cache keyed by the key alone; no ticket with priority 4 exists and the count stayed 1. Raw: runs/2026-11-17-tiny-tracker-ignores-args-1/a2_retry_mismatched.json, runs/2026-11-17-tiny-tracker-ignores-args-1/count_a2_final.json | 2026-11-17 |
| A3 | tiny-tracker (idempotency-key-ignores-args) | unproven | The read by K and a same-key replay with the caller's own arguments both returned T-1 (replayed: true, count 1 before and after; on this build the replay answer comes from the key-only cache); no digest is carried, so digest equality cannot be shown. Raw: runs/2026-11-17-tiny-tracker-ignores-args-1/a3_summary.json, runs/2026-11-17-tiny-tracker-ignores-args-1/a3_konly_replay_create_ticket.json | 2026-11-17 |
| A4 | tiny-tracker (idempotency-key-ignores-args) | pass | Scored by the driver from the classes success (A1 retry, replay of T-1) and success (A2 retry). Recorded for joint review, not resolved: the A2 retry's success names T-2, a committed record of (K, A), not of the (K, A') it was asked for. Raw: runs/2026-11-17-tiny-tracker-ignores-args-1/summary.json, runs/2026-11-17-tiny-tracker-ignores-args-1/a2_retry_mismatched.json | 2026-11-17 |
| A5 | tiny-tracker (idempotency-key-ignores-args) | unproven | Not run: the build was stopped after A1 to A4, and tiny-tracker keeps its record in memory. A5 runs on the correct build only. | 2026-11-17 |

Run of 2026-11-17 (MWS-RETRY-2 reciprocal run): Zambo production
(https://zambo.dev/mcp), target tool journal_log, raw outputs in
runs/2026-11-17-mws-retry-2-zambo-1/ (summary.json is the scored
record for A1 to A5; MWS-SCORECARD.md scores the MWS-RETRY-2 steps
from the same raw outputs). This is the reciprocal run offered on
MCP issue 3394 (zambodotdev comment 6934532293, accepted by
rafe-walker comment 6935542605): the MWS-RETRY-2 test method run
against Zambo, with the contract harness run beside it on the same
operations. The operation key K is carried as the journal_log job_id
and inputs.operation marker, scoped by the run-scoped session id;
that binding was introduced by the production recovery fix published
earlier the same day (runs/2026-11-17-zambo-fix-verify/), after the
write-tool manifest posted on the thread (comment 6942229307) had
recorded that no tool on the surface accepted a caller-supplied key.
The MWS verdicts, each from the step's own record in
MWS-SCORECARD.md: black-box steps (a), (b) and (c) held (one shared
record); the proxy-assisted step held, run in the contract's
client-side-drop form and recorded as such; step (d), simultaneous
repeat, not observed (10 pairs stated, all overlapped, no pair
applied the write more than once); step (e) and its crash form not
tested (the declaration gives no means to stop and start the hosted
server). The MWS scope is journal_log only; the other write tools
still accept no caller key, so the requirement does not apply to
them and they were not tested.

| Assertion | System | Outcome | Evidence | Date |
|---|---|---|---|---|
| A1 | Zambo | pass | External effect count exactly 1: attempt 1 (response dropped) produced public receipt 2e9ebf1f-5743-48de-a34b-5b3584c4c102 and the identical retry answered as a replay of that same receipt (idempotent_replay: true), counted from the job's workflow snapshot and attributed through its public record. Raw: runs/2026-11-17-mws-retry-2-zambo-1/count_a1_final.json, runs/2026-11-17-mws-retry-2-zambo-1/a1_retry_identical.json | 2026-11-17 |
| A2 | Zambo | pass | Attempt 1 committed (effect count 1). The mismatched retry (one parameter changed: action) was refused as a binding mismatch: tool_error:idempotency_conflict, no new effect, the count stayed 1. Raw: runs/2026-11-17-mws-retry-2-zambo-1/a2_retry_mismatched.json, runs/2026-11-17-mws-retry-2-zambo-1/count_a2_final.json | 2026-11-17 |
| A3 | Zambo | pass | K-only leg passed: recovery holding only K (lr-op-d99166563b-a1) returned the original committed outcome, and the recovered digest equals the committed digest sha256:b57197d5333af492c73260784de351c587545b6837ddab98500386714d931b87. Run-id leg also passed: holding receipt id 2e9ebf1f-5743-48de-a34b-5b3584c4c102, resolution returned the unaltered record and recomputation matched. Raw: runs/2026-11-17-mws-retry-2-zambo-1/a3_summary.json, runs/2026-11-17-mws-retry-2-zambo-1/a3_runid_leg_receipt.json, runs/2026-11-17-mws-retry-2-zambo-1/a3_konly_run_lookup.json | 2026-11-17 |
| A4 | Zambo | pass | Recorded retry response classes: A1 retry success, a replay naming the committed record (receipt 2e9ebf1f-5743-48de-a34b-5b3584c4c102), not a generic success with no record; A2 retry tool_error:idempotency_conflict, an explicit non-success state naming the situation. Raw: runs/2026-11-17-mws-retry-2-zambo-1/summary.json | 2026-11-17 |
| A5 | Zambo | pass | Delayed leg run 2026-11-18T21:30Z, after the due time 2026-11-18T20:58:24Z. K-only recovery passed: a fresh client holding only K (lr-op-d99166563b-a1) recovered the committed outcome through the direct public-record lookup (GET /api/v2/receipt/<K>/verify, HTTP 200, served output_hash equal to the committed digest sha256:b57197d5333af492c73260784de351c587545b6837ddab98500386714d931b87), the K-keyed continuity_get_recent also returned the original receipt id and the committed digest, and the run-id leg returned the unaltered record with digest equal and recomputation matched; the harness delayed leg scored those legs pass. Protection against fresh execution passed: before the delayed retries the external effect count was 1; the identical delayed retry answered as a replay of the original receipt (success, idempotent_replay: true, receipt 2e9ebf1f-5743-48de-a34b-5b3584c4c102, no new execution) and the modified-parameter delayed retry (action changed to lost_response_probe_altered) was refused as a binding conflict (tool_error:idempotency_conflict, executed: false, refusal receipt 6f10bb98-a9df-4ab4-b56e-9af11c3bb1ae, not counted as an execution), so the count stayed 1. The delayed probes ran after the 2026-11-18 key-binding fix (runs/2026-11-18-zambo-3/), which binds replay protection and key-only recovery to the operation key (job_id + parameter digest). Raw: runs/2026-11-17-mws-retry-2-zambo-1/summary_a5.json, runs/2026-11-17-mws-retry-2-zambo-1/a5_delayed_result.json, runs/2026-11-17-mws-retry-2-zambo-1/a5_delayed_runid_receipt.json, runs/2026-11-17-mws-retry-2-zambo-1/a5_delayed_extra.json, runs/2026-11-17-mws-retry-2-zambo-1/a5_delayed_konly_run_lookup.json, runs/2026-11-17-mws-retry-2-zambo-1/a5_delayed_konly_continuity_get_recent.json, runs/2026-11-17-mws-retry-2-zambo-1/count_a5_delayed_before_protection.json, runs/2026-11-17-mws-retry-2-zambo-1/count_a5_delayed_final.json, runs/2026-11-17-mws-retry-2-zambo-1/a5_delayed_retry_identical.json, runs/2026-11-17-mws-retry-2-zambo-1/a5_delayed_retry_mismatched.json | 2026-11-18 |

Delayed-leg note (2026-11-18): the A5 delayed leg for this run ran on 2026-11-18 after its due time and scored pass, as recorded in the A5 row above and in runs/2026-11-17-mws-retry-2-zambo-1/summary_a5.json. With this result, A1 to A5 for this run are all pass. No other run's rows are changed by this note; run 2026-11-16-zambo-1's A5 fail above is historical evidence and stands.

Run of 2026-11-17 (post-fix delayed leg): Zambo production
(https://zambo.dev/mcp), target tool journal_log, raw outputs in
runs/2026-11-17-zambo-2/ (summary_a5.json is the scored record for
A5). This run was planted on 2026-11-17T17:12:46Z, after the
production recovery fix published the same day and after the
short-range verification in runs/2026-11-17-zambo-fix-verify/; its
A5 delayed leg ran on 2026-11-18 after the due time
2026-11-18T17:12:46Z. Operation: K lr-op-13118ee094-a1, session
lr-13118ee094-a1, committed receipt
e3af210e-182f-4c48-9da1-dd954be4ccda, committed digest
sha256:90c4715cfe287641f6145abe9a9cbc074eb85b3c3bf3af2a1022a35f9a44bd1d,
external effect count at planting 1. Run 2026-11-16-zambo-1's A5
FAIL row above is historical evidence and is not edited by this
section.

| Assertion | System | Outcome | Evidence | Date |
|---|---|---|---|---|
| A5 | Zambo | fail | K-only recovery passed: a fresh client holding only K (lr-op-13118ee094-a1) recovered the committed outcome through the direct public-record lookup (GET /api/v2/receipt/<K>/verify, HTTP 200, served output_hash equal to the committed digest sha256:90c4715cfe287641f6145abe9a9cbc074eb85b3c3bf3af2a1022a35f9a44bd1d), and the run-id leg returned the unaltered record with digest equal and recomputation matched; the harness delayed leg scored those two legs pass. Protection against fresh execution failed on the protection probes (run with a fresh client, mirroring runs/2026-11-16-zambo-1/a5_delayed_extra.json): before the delayed retries the external effect count was 1; the identical delayed retry executed as a fresh call (success, new journal entry sequence 2, new receipt f83e0bd2-e387-45fd-aa4d-f43758d21990, no replay marker), raising the count to 2; the modified-parameter delayed retry (action changed to lost_response_probe_altered) was refused as a binding conflict (tool_error:idempotency_conflict, HTTP 409, executed: false, refusal receipt a1a38ef7-912f-4e02-80bf-285bee1d55c3, not counted as an execution), so the count stayed 2. Diagnostic, recorded not scored: the fresh client's initialize on 2026-11-18 issued a new caller_handle, unlike 2026-11-16/17 when initialize returned the stable handle recorded in this run's plant files; an identical retry presenting the plant's persisted caller_handle replayed the original receipt (idempotent_replay: true, no new execution), and the K-keyed continuity_get_recent with that handle returned status found with the original receipt and digest, while the same continuity call under the fresh handle returned the generic recent-events stream with no outcome or digest. Replay and continuity recovery are therefore observed to be scoped to the persisted caller_handle; K-only recovery through the direct lookup is not. Raw: runs/2026-11-17-zambo-2/summary_a5.json, runs/2026-11-17-zambo-2/a5_delayed_result.json, runs/2026-11-17-zambo-2/a5_delayed_runid_receipt.json, runs/2026-11-17-zambo-2/a5_delayed_extra.json, runs/2026-11-17-zambo-2/a5_delayed_konly_run_lookup.json, runs/2026-11-17-zambo-2/a5_delayed_konly_continuity_get_recent.json, runs/2026-11-17-zambo-2/a5_delayed_konly_continuity_samehandle.json, runs/2026-11-17-zambo-2/count_a5_delayed_before_protection.json, runs/2026-11-17-zambo-2/count_a5_delayed_final.json, runs/2026-11-17-zambo-2/a5_delayed_retry_identical.json, runs/2026-11-17-zambo-2/a5_delayed_retry_mismatched.json, runs/2026-11-17-zambo-2/a5_delayed_retry_identical_samehandle.json, runs/2026-11-17-zambo-2/count_a5_delayed_after_samehandle.json | 2026-11-18 |

Run of 2026-11-18 (key-binding fix acceptance): Zambo production
(https://zambo.dev/mcp), target tool journal_log, raw outputs in
runs/2026-11-18-zambo-3/. On 2026-11-18 the crew published the fix
that binds replay protection and key-only recovery to the operation
key (job_id + parameter digest) instead of the caller_handle alone.
Acceptance ran the same day from fresh clients (each initialize
issued a new caller_handle), first against the zambo-2 operation
itself, then against a fresh plant.

Post-publish probes on the zambo-2 operation (K
lr-op-13118ee094-a1, committed receipt
e3af210e-182f-4c48-9da1-dd954be4ccda, committed digest
sha256:90c4715cfe287641f6145abe9a9cbc074eb85b3c3bf3af2a1022a35f9a44bd1d;
its two historical executions stand, history not rewritten):

| Leg | System | Outcome | Evidence | Date |
|---|---|---|---|---|
| K-only recovery (fresh client) | Zambo | pass | continuity_get_recent holding only K returned the original receipt id and the committed digest; the same call under a fresh handle on 2026-11-18 before the publish returned only the fresh caller's own stream. Direct lookup GET /api/v2/receipt/<K>/verify HTTP 200, commitment_matches computed_hash equal to the committed digest. Raw: runs/2026-11-18-zambo-3/p1_konly_continuity.json, runs/2026-11-18-zambo-3/p1_run_lookup.json | 2026-11-18 |
| Identical retry (fresh client) | Zambo | pass | Answered success as a replay of the original receipt e3af210e-182f-4c48-9da1-dd954be4ccda (idempotent_replay marker present); no third execution: the workflow snapshot children before and after differ only by a workflow_close wrap receipt and the refusal record below. Raw: runs/2026-11-18-zambo-3/p1_retry_identical.json, runs/2026-11-18-zambo-3/p1_count_before_raw.json, runs/2026-11-18-zambo-3/p1_count_after_raw.json | 2026-11-18 |
| Modified-parameter retry (fresh client) | Zambo | pass | Refused before execution: "This operation key is already bound to different parameters. No journal entry was added" (idempotency_conflict; refusal receipt 3c091933-6125-42eb-8795-29b2414a96a8, step rejected_before_execution, not an execution). Raw: runs/2026-11-18-zambo-3/p1_retry_mismatched.json | 2026-11-18 |

Fresh plant, short range (K lr-op-bb150ceec1-a1, session
lr-bb150ceec1-a1, planted 2026-11-18T18:37:56Z, committed receipt
e2568939-b651-4150-b059-a1eeebbf7319, committed digest
sha256:c63fbfb9a34b33df4e5d2d821186ba7020c7e67217d8f80958b228710f106818):

| Assertion | System | Outcome | Evidence | Date |
|---|---|---|---|---|
| A1 | Zambo | pass | External effect count exactly 1 at planting (workflow snapshot holds the single journal_log execution e2568939-b651-4150-b059-a1eeebbf7319); the identical retry from a second fresh client answered success as a replay of that same receipt (idempotent_replay marker), and the post-retry snapshot adds only a workflow_close wrap receipt and the A2 refusal record, no new execution. Raw: runs/2026-11-18-zambo-3/p2_attempt1.json, runs/2026-11-18-zambo-3/p2_snapshot1.json, runs/2026-11-18-zambo-3/p2_retry_identical.json, runs/2026-11-18-zambo-3/p2_snapshot2.json | 2026-11-18 |
| A2 | Zambo | pass | The mismatched retry (action changed to lost_response_probe_altered) was refused before execution as a binding conflict (idempotency_conflict; refusal receipt a35a5d03-76fc-48bc-b60e-430a8db6444e); the count stayed 1. Raw: runs/2026-11-18-zambo-3/p2_retry_mismatched.json | 2026-11-18 |
| A3 | Zambo | pass | K-only recovery from a fresh client: continuity_get_recent holding only K returned the committed receipt id and the committed digest sha256:c63fbfb9a34b33df4e5d2d821186ba7020c7e67217d8f80958b228710f106818. Raw: runs/2026-11-18-zambo-3/p2_konly_continuity.json | 2026-11-18 |
| A5 | Zambo | unproven | The 24 hour delayed leg cannot complete on the planting day. The operation is planted with its commit timestamp recorded in runs/2026-11-18-zambo-3/a5_plant.json (due 2026-11-19T18:38:16Z); the delayed leg runs later with the same fresh-client probes used by the zambo-2 delayed leg. | 2026-11-18 |

Run of 2026-11-18 (key-binding fix acceptance, A5 delayed leg): Zambo
production (https://zambo.dev/mcp), target tool journal_log, raw outputs
in runs/2026-11-18-zambo-3/ (summary_a5.json is the scored record for
A5). This run was planted on 2026-11-18T18:37:56Z, after the crew
published the fix binding replay protection and key-only recovery to
the operation key (job_id + parameter digest); its A5 delayed leg ran
on 2026-11-19 after the due time 2026-11-19T18:38:16Z. Operation: K
lr-op-bb150ceec1-a1, session lr-bb150ceec1-a1, committed receipt
e2568939-b651-4150-b059-a1eeebbf7319, committed digest
sha256:c63fbfb9a34b33df4e5d2d821186ba7020c7e67217d8f80958b228710f106818,
external effect count at planting 1. The acceptance section's A5
unproven row above is the planting-day record and is not edited by
this section. Run 2026-11-17-zambo-2's A5 FAIL row above is historical
evidence and is not edited by this section.

| Assertion | System | Outcome | Evidence | Date |
|---|---|---|---|---|
| A5 | Zambo | pass | Delayed leg run 2026-11-19T18:46:48Z, after the due time 2026-11-19T18:38:16Z. K-only recovery passed: a fresh client holding only K (lr-op-bb150ceec1-a1) recovered the committed outcome through the direct public-record lookup (GET /api/v2/receipt/<K>/verify, HTTP 200, served output_hash equal to the committed digest sha256:c63fbfb9a34b33df4e5d2d821186ba7020c7e67217d8f80958b228710f106818), the K-keyed continuity_get_recent also returned the original receipt id and the committed digest, and the run-id leg returned the unaltered record with digest equal and verification_status verified. Protection against fresh execution passed: before the delayed retries the external effect count was 1; the identical delayed retry answered success as a replay of the original receipt (idempotent_replay marker, receipt e2568939-b651-4150-b059-a1eeebbf7319, no new execution) and the modified-parameter delayed retry (action changed to lost_response_probe_altered) was refused before execution (error.code idempotency_conflict, executed: false, outcome rejected_before_execution, refusal receipt d33fc9a7-7f3a-405f-bd98-6dce72983beb, step status rejected_before_execution, not counted as an execution), so the count stayed 1, confirmed by a live adapter recount (count 1). Counter note, recorded not hidden: the first scoring pass used a receipt_id-keyed counter that returned 0/0; the scored counts are the canonical recount (fixtures/harness/adapters/zambo.py count_effects: journal_log tool plus success step per child public record) from the same saved raw snapshots, with the before/after snapshots and the recount in the run folder. Raw: runs/2026-11-18-zambo-3/summary_a5.json, runs/2026-11-18-zambo-3/a5_delayed_extra.json, runs/2026-11-18-zambo-3/a5_delayed_initialize.json, runs/2026-11-18-zambo-3/a5_delayed_konly_run_lookup.json, runs/2026-11-18-zambo-3/a5_delayed_konly_continuity_get_recent.json, runs/2026-11-18-zambo-3/a5_delayed_runid_receipt.json, runs/2026-11-18-zambo-3/a5_delayed_count_before.json, runs/2026-11-18-zambo-3/a5_delayed_count_after.json, runs/2026-11-18-zambo-3/count_a5_delayed_before_protection.json, runs/2026-11-18-zambo-3/count_a5_delayed_final.json, runs/2026-11-18-zambo-3/count_a5_delayed_recount.json, runs/2026-11-18-zambo-3/a5_delayed_retry_identical.json, runs/2026-11-18-zambo-3/a5_delayed_retry_mismatched.json, runs/2026-11-18-zambo-3/a5_delayed_probe.py, runs/2026-11-18-zambo-3/a5_delayed_recount.py | 2026-11-19 |
