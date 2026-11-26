# Run notes: tiny-tracker 0.3.0, correct build, A5 across a restart

Pinned versions:
- **Contract and driver:** zambodotdev/lost-response-test-contract at b2f2c64. That commit has the A5 scorer from #3; CONTRACT.md is unchanged.
- **System under test:** @mcp-write-safety/tiny-tracker 0.3.0 (tag `tiny-tracker-v0.3.0`, b3f1bf4), run locally with `tiny-tracker all --features evidence,strict-input,ledger,durable,inflight,retention`, bound to 127.0.0.1 only, build_hash 40695279….
- **Harness:** tiny-tracker's adapter and `a5_durable.sh`, as merged in isokron-ai/mcp-write-safety#37 (f22e1d1).
- **Environment:** Python 3.9.6, requests 2.32.5.

Timeline (UTC):
- **2026-11-23T18:11:06Z:** A1–A4 run, and the A5 operation planted (K `lr-op-42514abd5d-a1`, execution X-1, committed digest 66b027b4…). due_at is 2026-11-24T18:11:06Z.
- **2026-11-24T16:14:59Z:** the server is stopped (SIGTERM) and started again on the same data directory and ports, inside the window.
  - `boot_id` moved from 7733a896c1739d42 to 889b99f5738a5ad6, and build_hash is unchanged.
  - tiny-tracker's `restart_count` stays 0, because it counts only restarts by its own supervisor (`--supervise`), and this was a full stop and start.
- **2026-11-24T18:34:52Z:** the delayed leg runs once.

How the delayed leg's records were made:
- **The driver records nothing for protection.** `lost_response.py --delayed-leg` scores retry protection from `count_a5_delayed_*.json` and `a5_delayed_retry_*.json`, but the driver does not make those calls.
- **The harness probe made them,** live, just before `--delayed-leg` ran, through the same adapter and in the driver's own shapes. The order was:
  1. count;
  2. identical retry;
  3. count;
  4. retry with one argument changed (priority 3 → 4, the configured mismatch);
  5. count.
- **Everything else is the driver's:** the K-only lookup and run-id lookup in `a5_delayed_result.json` are the driver's own legs, and the score comes from `score_a5`.

Counting after the restart:
- **The ledger doesn't survive a restart.** tiny-tracker's ledger is kept in memory for one boot, so after the restart it no longer held X-1.
- **The count also reads the durable execution records** (`GET /executions`, saved as `executions_<label>.json`), with the same attribution: operation tag equal to the session and key equal to K. Each execution is counted once.
- **Recount after the run:** the journal and the execution records agree on X-1 and X-2. The ledger is empty for writes made before the restart, as expected.

Edits to the files:
- **One edit, everywhere:** the local path prefix of the run directory is replaced with `<run-root>`. It appears in the plant's adapter_config (start_command, token_dir) and in the data directory paths. No other byte is changed.
- **The token files are not included.** A search for both tokens across every file in this directory found nothing.

Result: A1 pass, A2 pass, A3 pass, A4 pass. A5: recovery pass, retry protection pass, overall pass.
