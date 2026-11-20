# MWS-RETRY-2 re-score of the Zambo reciprocal run (zambo-1), from the raw files

An independent re-score for the shared record, by Joshua Bryan (IsoKron), 18 Nov 2026, as asked on MCP issue 3394. It was checked by a second reader. Where we read a step differently from `MWS-SCORECARD.md`, the difference is stated with the raw values and the spec words that decide it.

- **Run scored:** `runs/2026-11-17-mws-retry-2-zambo-1/` in `zambodotdev/lost-response-test-contract`, pinned at commit `482081f716193fd4caf868419b29daa56532e493`. We read it from a read-only clone.
- **Their scoring:** `MWS-SCORECARD.md`, `RESULTS-snippet.md` and the run's section of `RESULTS.md`. Also the maintainer's comments on MCP issue 3394 at 2026-11-17T07:58:50Z (the write-tool manifest) and 21:05:46Z (the request to re-score).
- **Spec:** MWS 0.9, `spec/mws.md` at isokron-ai `origin/main` `27abb86`. We used the MWS-RETRY-2 entry, sections 4, 6, 7, 8 and Annex E.
- **Method of this re-score:** the verdicts below come from the JSON files, not from the scorecard's prose. We recomputed every count, overlap and digest comparison from the raw fields. We made no calls to the hosted service.

Wording conventions in this document:
- **Spec** marks a rule that the spec's text states.
- **Reading** marks our interpretation, where the text does not decide the point by itself.

## 1. Verdicts by step

| Step (record) | Their verdict | Our verdict | Agree? | Raw files | What decides it |
|---|---|---|---|---|---|
| (a), (b), (c): one black-box record | `held` | `held`, with the qualifications in 2.1 | Yes, qualified | `mws_step_a_blackbox.json`, `enum_mwsa_final_workflow_close.json`, `mws_step_b_newkey.json`, `enum_mwsb_final_workflow_close.json`, `a2_attempt1_dropped.json`, `a2_retry_mismatched.json`, `count_a2_after_attempt1.json`, `count_a2_final.json`, `enum_a2_*` | RETRY-2 Verdicts: the record is "`held` if all three forced their condition and held". The step (a), (b) and (c) clauses are applied in 2.1. |
| Proxy-assisted step: its own record | `held` (client-side drop form) | `not tested`: there was no interposer on the hop between the server and its backend. The A1 trial counts as a second trial of step (a), and its result is consistent with `held` (see 2.2). | **No** | `a1_attempt1_dropped.json`, `a1_retry_identical.json`, `count_a1_after_attempt1.json`, `count_a1_final.json`, `enum_a1_*`; harness `fixtures/harness/adapters/zambo.py` `call_tool` | Section 7.1 defines proxy-assisted. The RETRY-2 proxy-assisted procedure, and its rule that an answered first call "is judged as in step (a)". Section 8.2, rule 4. See 2.2. |
| (d) simultaneous repeat: its own record | `not observed` | `not tested`, reason "too few overlapped pairs". No pair applied the write more than once. | **No** | `mws_step_d_simultaneous.json`, `count_mwsd0..9_final.json`, `enum_mwsd0..9_final_workflow_close.json` | Section 8.2, rule 6, and the RETRY-2 exclusion of pairs in which neither call applied the write. See 2.3. |
| (e) "restart" | `not tested` | `not tested` | Yes | No raw file: no restart was attempted | RETRY-2: "where the declaration gives none, step (e) and its crash form give `not tested`." |
| (e) crash form, "restart during the first call" | `not tested` | `not tested`. It also needs an interposer, which was not available. | Yes | None | Same rule. The crash form is "(proxy-assisted, launch)". |
| Other write tools on the default surface (11 tools) | "does not apply … does not test them" | `not applicable`. Each tool gets its own record, which says "accepts no idempotency key". | Yes (wording note only) | None in the run directory. The claim rests on the 07:58Z manifest | RETRY-2 Applies when. Section 6: "Where the condition is false the verdict is `not applicable`." Sections 8.1 and 5.1. See 2.4. |

The six rows are kept separate on purpose. Section 5.2 forbids any total of them.

## 2. Explanations

### 2.1 Steps (a), (b) and (c): `held`, agreed, with qualifications

**What the raw files show.**

**Step (a).**
- The first call succeeded at 20:59:10.301463Z (client receive time). Receipt `767bd78f-…`, `output_hash` `sha256:919f5b8b…632c`, journal entry `65b0927a-…`, sequence 1.
- The repeat was sent at 20:59:10.302176Z, after the answer had arrived.
- The repeat returned `isError: false`, `idempotent_replay: true`, `status: "replayed"`, the same receipt id, and `output_digest` equal to the first `output_hash`.
- Its `original_outcome.entry` is field-for-field equal to the first answer's `entry`; we checked this programmatically.
- The snapshot `enum_mwsa_final_workflow_close.json` has one child, `767bd78f`, with the same hash, so the count is 1.
- This matches the RETRY-2 rule for step (a). The first call was answered with a success, and "a repeat that gives it, with the write applied once, is `held`".

**Step (b).**
- The new key `lr-op-ef631377b2-mwsb` returned a success with no replay marker and `status: logged`.
- It created a new receipt `6304e38a-…` and a new entry `aafec3c5-…`, and its snapshot count is 1. So it was treated as a new write.

**Step (c).**
- The same K (`lr-op-d99166563b-a2`) was sent with `action` changed to `lost_response_probe_altered`.
- The answer was `isError: true` with `structuredContent.error.code` `idempotency_conflict`, `executed: false`, and the message "No journal entry was added".
- `count_a2_final.json` still counts one execution, `29c6eaa1`. The new receipt `2757da21` has step status `rejected_before_execution` and is correctly not counted.
- Spec: "Where the key is a tool argument the refusal is expected as a tool execution error". The answer meets that.

**Qualifications.** None of these changes the verdict.

1. **Trace reads (spec procedure).** The spec says: "The tester reads the trace before the first call and after each answer".
   - Step (a) has one read only, made after the repeat (label `mwsa_final`).
   - The fresh session and job make a prior count of 0 a matter of construction, but it was not read. Nor was the trace read between the first answer and the repeat.
   - Reading: a final count of 1 still bounds the write to at most one application. The verdict therefore stands, but the record should say which reads were made.
2. **Trace source (reading).** The count is taken from the job's receipt record: the `workflow_close` snapshot children, filtered by the public `/api/v2/receipt/<id>/verify` record to `journal_log` with step status `success`. It is not taken from the journal that `journal_log` appends to.
   - The spec's trace for an append is "the objects or applied changes". The files never read the journal itself; `verify_url` `/api/journal/<K>/verify` is never fetched.
   - The receipt count is a fair proxy, because `fixtures/README.md` rule 1 states "One actual execution produces exactly one durable public record". Every answer also reports journal sequence 1 alongside its one receipt.
   - However, the spec asks the declaration to say that the tool makes no backend write "except one for each application of the write". The fixture statement is about receipts, not about every backend write.
   - Also, `workflow_close` is a write tool: the 07:58Z manifest lists it as state-mutating ("closes the session's job"). Section 7.1 says black-box reads go "through the server's own read tools".
   - In the A1 and A2 legs, this read closed the job between attempt 1 and the retry. The counts are unaffected, because the close receipts are filtered out by attribution. The record should still say that the trace was read with a write tool.
3. **Step (b) varied more than the key.** The step (b) file's note says "Arguments identical to step (a) except the key itself".
   - In the raw arguments `_session_id` also changed, from `lr-ef631377b2-mwsa` to `lr-ef631377b2-mwsb`.
   - Under the stated carrier ("scoped by the session id") this is still a new key, so `held` stands.
   - But the step cannot tell a server that keys replays on K from one that keys them on the session alone. A same-session trial with a new `job_id` would separate the two.
4. **The key scope in effect on 17 Nov (reading, from the repo's own later sections).**
   - The adapter adds the caller handle to every call (`adapters/zambo.py`, `call_tool`). It is absent from every `arguments_sent` block.
   - Every response in the run directory echoes the same caller handle.
   - The repo's 18 Nov section says that fix moved the binding to the operation key (job_id plus a parameter digest), and away from the caller handle alone. The zambo-2 delayed leg also saw a fresh-handle identical retry execute again.
   - So the zambo-1 results describe repeats that presented the same caller handle. The record should state that this handle was held constant and that it formed part of the effective key scope. This does not change any zambo-1 verdict, because no zambo-1 call varied the handle.
5. **Step (c) precondition (not shown).** The spec asks for arguments "that the tool would apply under a fresh key". No fresh-key call with `action: lost_response_probe_altered` is in the files. Reading: `action` looks like a free-text field, so this is very likely met, but it is not shown.
6. **Transport status (observation, not judged by RETRY-2).** The step (c) refusal arrived with HTTP status 409 wrapped around a JSON-RPC result. MWS-RES-2 judges the refusal's form; RETRY-2 accepts "a refusal in any form". We note the 409 because some clients treat a non-2xx status as a transport error.
7. **Who read "replay" (spec, section 7.3, rule 11).** No declared pattern exists for "a replay". The record therefore rests on a person's reading of `idempotent_replay` and `status`, and it should name the reader.

### 2.2 Proxy-assisted step: we read `not tested`, they read `held`

**What the raw files show.**
- `a1_attempt1_dropped.json` records HTTP 200 and `response_bytes` 15527, equal to `content_length_header`. That means the whole response reached the harness.
- The adapter then discards the body client-side. Its own docstring says: "the server committed, the caller perceived a loss".
- The retry replays receipt `2e9ebf1f-…`. Its `output_digest` `sha256:b57197d5…1b87` equals the snapshot child's hash, and the count is 1 before and after the retry.

**Spec words that decide it.**
- **Section 7.1.** The proxy-assisted method means "the tester interposes on the hop between the server and its backend". It needs "a way to route the server's backend traffic through the interposer, or cooperative hooks inside the server".
- **The RETRY-2 procedure.** "let the backend commit the first write, cut the response before the server receives it". That is the backend's response to the server.
- **The RETRY-2 Verdicts.** "In the proxy-assisted step, where the first call was answered with a success, … the repeat is judged as in step (a)."
- **The step (a) rule.** For a first call that applied the write but was answered with neither a success nor an error that identifies the change, "the proxy-assisted step is the forced form of that case".

**Our reading.**
- In the client-side drop, the server received the backend's answer and sent the caller a full success. The server held the outcome, exactly as in step (a).
- The trial therefore did force a condition. Section 8.2, rule 4 ("`held` requires a forced condition") is met, but for step (a)'s condition. The trial adds a second step (a) trial to the black-box record, and its result is consistent with `held`. Two caveats apply:
  - The first answer was not kept, so its success is inferred (see below).
  - A `workflow_close` write ran between attempt 1 and the retry (`enum_a1_after_attempt1_workflow_close.json`).
- It did not force the proxy-assisted condition, in which the server never received the backend's answer. So it cannot be recorded under the proxy-assisted method (section 8.1: one record per method).
- The proxy-assisted record is `not tested`. Its reason: the service is hosted, and no interposer or cooperative hook sat on the hop between the server and its store. Running it would need such an interposer or hook, with the schedule and routing that section 7.3, rule 7 asks for.
- The scorecard applies the rule "held without the note". The spec gives that rule only for a first call "answered neither with a success nor with an error that identifies the applied change". That precondition is not met here.

**Common ground.** The maintainer's comment already says the trial is recorded "as that form, not as the interposer form". The difference between us is only which record it belongs to. MWS has no client-side-drop variant of the proxy-assisted step. The contract's A1 is a valid test in its own terms, and its pass is not in question here.

The first answer's body was discarded by design, so we cannot read its content. That it was a success is an inference from three facts: the HTTP 200, a size (15527 bytes) within the range of the other first-call success bodies in this run (15.3 to 16.5 kB; the largest is pair 3 call 1, at 16,519 bytes), against about 44 kB for the `payment_required` bodies, and the public record's step status `success`.

### 2.3 Step (d): we read `not tested` ("too few overlapped pairs"), they read `not observed`

**Recomputed from `mws_step_d_simultaneous.json`.** Overlap was recomputed from the client's `sent_at` and `received_at` times; all 10 pairs overlapped, and the twins were sent within 2.4 ms of each other. The counts come from the snapshots.

| Pairs | What happened | Count |
|---|---|---|
| 1, 2, 3, 7, 8 | One twin applied the write. The other answered `idempotent_replay: true`, with the same receipt, an equal digest and an equal `entry`. | 1 each |
| 0, 4, 5 | `call1` was refused with `payment_required` (`execution_status: not_executed`; its receipt has step status `payment_required`). `call2` applied the write once. | 1 each |
| 6, 9 | Both twins were refused with `payment_required`. | 0 each |

Pairs applied more than once: 0. Indeterminate trials: 0. The scorecard's 5/3/2 split matches these files.

**Spec words.**
- RETRY-2 says of step (d) that "section 8.2, rules 5 to 7 and 9, apply to it". Rule 5: "Beyond `not tested` and `not applicable`, a simultaneous-pairs test can produce only `violated`, `platform` or `not observed`."
- **Stopping at 10 pairs was allowed.** The procedure runs until 30 pairs have overlapped "or a number of pairs stated in the record has been sent". Only the verdict rule (rule 6) is where we differ.
- RETRY-2 says that where neither call of a pair applied the write, the pair gives `not tested`, and "such a pair is not counted toward section 8.2, rule 6." Pairs 6 and 9 are therefore excluded.
- Section 8.2, rule 6: "With fewer overlapped pairs and no loss seen, the verdict is `not tested`, with the reason 'too few overlapped pairs'."
- **By the spec's words**, 8 overlapped pairs count: pairs 0 to 5, 7 and 8. The step (d) text excludes only pairs in which neither call applied the write.
- **By our reading**, 5 count: pairs 1, 2, 3, 7 and 8. In pairs 0, 4 and 5 the refused twin may not have reached the key check, so the pair may not have tested concurrent handling of the key. The order inside the server is not visible (section 3).
- The spec has an explicit rule for steps (a), (b), (c) and (e): "a refusal that says nothing about the write itself … did not force the condition". Step (d) has no such rule. That gap is in our spec, and we will record it as an open point for 0.9.
- Either count is below 30, so the verdict is `not tested`.

**Record contents** under section 8.1 ("the reason and what would be needed to run it") and section 7.3, rule 8:
- Pairs sent: 10, as stated in the file (`pairs_stated: 10`). All 10 overlapped.
- Pairs in which neither call applied the write: 2. These are not counted.
- Pairs with one twin refused at metering: 3.
- Pairs in which the twin answered as a replay: 5.
- Pairs applied more than once: 0. Indeterminate: 0.
- Counted overlapped pairs: 8 by the spec's words, or 5 by our reading.
- Reason: "too few overlapped pairs".
- What would be needed: at least 30 overlapped pairs in which a call applied the write, on a quota or test allowance that does not refuse the calls.

**On their own verdict.** A `not observed` record would also need the content that section 8.2, rule 7 requires. The scorecard has neither part:
- the 3/n bound. As an illustration, about 37.5% for 8 pairs, or 60% for 5;
- the sentence "that the result does not show the server is safe under concurrency".

**Observation on the trace.** The metering refusals leave `journal_log` receipts with step status `payment_required` in the trace. The counter correctly excludes them.

### 2.4 Scope: the other write tools

The RETRY-2 entry applies "when … the server offers a write tool that accepts an idempotency key". The 07:58Z manifest says no schema had such a parameter. The 21:05Z comment and the scorecard say that only `journal_log` calls carrying an operation marker are bound.

- **Agreed.** For the other 11 state-mutating tools in the manifest, RETRY-2 is `not applicable`. The tools are handover, workflow_close, workflow_seal, memory_remember, continuity_start_thread, continuity_set_prefs, spend_limit_set, handover_accept, day_pass_redeem, day_pass_activate and zambo_universal.
- **Wording note, not a correction.** The scorecard already says the requirement "does not apply" to these tools. When the per-tool records are written, the spec's form is one result per tool (section 5.1), each with the verdict word `not applicable` and the false part of the condition (section 8.1): "accepts no idempotency key". The phrase "does not test them" could be read as `not tested`, so it is better left out of those records.
- **Reading.** A tool's caller-supplied handle is not a key unless the server uses it to recognize a repeat. Section 4 defines an idempotency key as "a caller-chosen value sent with a write so that the server or the backend can recognize a repeat". Examples are `workflow_id` on workflow_seal and day_pass_activate, and `job_id` on doc_intel. The manifest says none of them is a key, and nothing in the run tests otherwise.
- `not applicable` under RETRY-2 does not settle MWS-RETRY-1, which is a SHOULD for create tools with no key. That is a separate requirement and is outside this run.

### 2.5 Other points from the raw files

- **Missing files.** The scorecard cites `count_mwsa_final.json` and `count_mwsb_final.json`, but neither exists at the pinned commit. The same evidence sits inside `mws_step_a_blackbox.json` and `mws_step_b_newkey.json` (under `count_evidence`, labels `mwsa_final` and `mwsb_final`). The raw snapshots `enum_mwsa_final_workflow_close.json` and `enum_mwsb_final_workflow_close.json` agree with it. Nothing is lost; only the citations need correcting.
- **Timing window.** The scorecard says the steps ran from 20:57Z to 21:05Z. The last raw timestamp is 21:01:38Z, in `enum_mwsd9`. 21:05:46Z is when the comment was posted.
- **Clock comparisons.**
  - Server receipt `timestamp` values are often later than the client's receive time for the response that carries them, by up to 520 ms (pair 6, call 2). Others are earlier, by up to 434 ms.
  - So server and client clocks cannot be compared to order events. Every ordering and overlap judgment above uses client times only, which are internally consistent.
- **Parser artifact.** The harness's `receipt_ids` list contains the string `"example"` for the `payment_required` bodies, and in A3. Counts come from snapshot children, so this has no effect on any count.
- **A5 due time (contract, not MWS).** `a5_plant.json` counts the due time from `planted_at` (2026-11-17T20:58:24.10Z). That is about 48.5 s after the commit; the entry's `started_at` is 20:57:35.602Z, on the server clock. The delayed leg therefore runs slightly later than 24 h after the commit. That is conservative, not a fault.
- **No published declaration.** No Annex E declaration is in the repo. The carrier, the trace statement and the absence of a stop/start means are stated in prose (scorecard, fixtures README, comments). Annex E is informative, but several RETRY-2 rules refer to "the declaration". A short declaration file would let a third party check each one.
- **Test-system declaration (spec, section 7.3, rule 1).** Writes must go "in a system its operator has declared to be a test system". This run wrote to production under fresh sessions and jobs created for the test, by the operator itself. The record does not carry that declaration. Only the operator can make it.

## 3. What we could not verify from the files

- **The first A1 answer.** Its content is unknown because the body was discarded by design. That it was a success is inferred (see 2.2).
- **The journal itself.** The applied entries for any K were never read. Counts rest on receipts, together with the fixture statement that each execution writes one receipt.
- **The drivers for steps (a), (b) and (d).** They are not in the repo; only the A1 to A5 harness is published. So we cannot see:
  - how the pairs were released;
  - how `overlapped` was computed, although we recomputed it from the timestamps;
  - whether the MWS steps sent the caller handle. We inferred this from the adapter and from the echoed handle.
- **Server-side overlap in step (d).** The overlap is client-side. Whether the server processed the twins concurrently or one after the other is not visible. In every replay pair the replay answered 0.6 to 1.4 s after its twin.
- **The step (c) precondition.** We cannot show that `action: lost_response_probe_altered` would have been applied under a fresh key.
- **The other write tools.** No `tools/list` output is in this run directory, so the claim that they accept no key rests on the 07:58Z manifest.
- **Whether metering came before the key check.** The answers say `not_executed`, but the order inside the server is not visible. This matters to our reading of pairs 0, 4 and 5.
- **The public records.** The `/api/v2/receipt/<id>/verify` records were not re-fetched, because the instruction was not to call their service. We relied on the copies inside the count files.
- **The test-system declaration.** Whether the operator declared production a test system for this run, as section 7.3, rule 1 requires, is not in the files.

The 2026-11-18 zambo-3 run is out of scope. It matters here only because its text says the 17 Nov binding was scoped to the caller handle (see 2.1, item 4).
