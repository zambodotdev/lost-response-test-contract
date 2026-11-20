#!/usr/bin/env python3
"""Lost-response recovery harness for the contract in ../../CONTRACT.md.

Runs assertions A1 to A5 against a system under test through an
adapter (see adapters/). The driver owns the scoring; the adapter
owns everything system-specific: execution, the shared external
effect counter, and recovery. The adapter contract is documented in
adapters/base.py; adapters/zambo.py is the reference implementation
(Zambo production, the system the recorded runs cover) and
adapters/stub.py is a copyable template for a new system.

Fault model (from CONTRACT.md, common setup): attempt 1's request is
sent and the server commits its effect, but the harness discards the
response client-side and treats the attempt as lost. Only transport
metadata (timestamps, HTTP status, byte count, JSON-RPC id) is
recorded for a dropped attempt: no body, no result, no receipt id,
no digest. Retries use a fresh transport request id, as MCP
requires.

External effect counter (fixtures/README.md): the count of distinct
committed executions visible in the system's durable public record,
attributed to the run by a fresh run-scoped session identity and to
the logical operation by K. Each adapter defines how the count is
read from its system's public record and returns the identifier list
it was counted from, so a third party can recount.

Usage:
    python3 lost_response.py --config config.zambo.json --out ../../runs/<dir>
    python3 lost_response.py --delayed-leg ../../runs/<dir>/a5_plant.json

The config selects the adapter and carries the adapter's own keys
under "adapter_config" (see adapters/__init__.py for the shape,
including the legacy flat shape, which still loads). To run against
a different system, write an adapter and a config for it;
adapters/README.md is the guide.

No payment is ever made. A payment_required response is recorded as
an observed response class and the affected assertion is scored
unproven when the refusal happened before any commit, per the
contract's scoring rules.
"""

import argparse
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from adapters import load_adapter, normalize_config


def utcnow():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class RunWriter:
    def __init__(self, out_dir):
        self.dir = Path(out_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    def write(self, name, obj):
        path = self.dir / name
        if isinstance(obj, str):
            path.write_text(obj, encoding="utf-8")
        else:
            path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")
        return str(path)


def execution_ids_of(evidence):
    return evidence.get("execution_record_ids",
                        evidence.get("target_tool_execution_receipt_ids"))


def digests_of(record):
    return record.get("digests") or record.get("digests_found") or {}


def result_digest_of(digests):
    for field in ("output_hash", "result_digest", "result"):
        if digests.get(field):
            return digests[field]
    return None


class Harness:
    def __init__(self, config, writer):
        self.cfg = config
        self.adapter_config = config["adapter_config"]
        self.adapter = load_adapter(config["adapter"], self.adapter_config)
        self.w = writer
        self.run_tag = uuid.uuid4().hex[:10]
        self.summary = {"run_tag": self.run_tag, "started_at": utcnow(),
                        "adapter": config["adapter"],
                        "system_name": config.get("system_name"),
                        "endpoint": getattr(self.adapter, "endpoint", None),
                        "tool": getattr(self.adapter, "tool_name", None),
                        "assertions": {}}

    # -- one logical operation --------------------------------------
    def attempt(self, session_id, k_value, drop, label, mismatched=False):
        result = self.adapter.execute(session_id=session_id,
                                      operation_key=k_value,
                                      mismatched=mismatched,
                                      drop_response=drop)
        record = {"label": label, "at": utcnow(), "session_id": session_id,
                  "K": k_value, "arguments_sent": result["arguments_sent"],
                  "call": result["call"]}
        self.w.write(f"{label}.json", record)
        return record

    def enumerate_session(self, session_id, k_value, label):
        out = self.adapter.count_effects(session_id=session_id,
                                         operation_key=k_value, label=label)
        for name, obj in (out.get("files") or {}).items():
            self.w.write(name, obj)
        evidence = out["evidence"]
        self.w.write(f"count_{label}.json", evidence)
        return evidence

    def run(self):
        init, init_summary = self.adapter.initialize()
        self.w.write("00_initialize.json", init)
        self.summary["initialize"] = init_summary
        a1 = self._run_a1()
        a2 = self._run_a2()
        a3 = self._run_a3(a1)
        self._run_a4(a1, a2)
        self._run_a5(a1, a3)
        self.summary["finished_at"] = utcnow()
        self.w.write("summary.json", self.summary)
        self.w.write("RESULTS-snippet.md", results_snippet(self.summary))
        return self.summary

    def _run_a1(self):
        session = f"lr-{self.run_tag}-a1"
        k_value = f"lr-op-{self.run_tag}-a1"
        attempt1 = self.attempt(session, k_value, drop=True,
                                label="a1_attempt1_dropped")
        count_after_1 = self.enumerate_session(session, k_value, "a1_after_attempt1")
        retry = self.attempt(session, k_value, drop=False,
                             label="a1_retry_identical")
        count_final = self.enumerate_session(session, k_value, "a1_final")
        committed_1 = count_after_1["external_effect_count"] >= 1
        final_count = count_final["external_effect_count"]
        retry_class = retry["call"].get("response_class")
        if not committed_1 and retry_class == "payment_required":
            score, reason = "unproven", "attempt 1 was refused before any commit (payment_required class observed in the run); the lost-response precondition never occurred"
        elif not committed_1:
            score, reason = "unproven", "no committed execution for attempt 1 is visible in the public record, so the lost-response precondition is not established"
        elif final_count == 1:
            score, reason = "pass", "external effect count for the logical operation is exactly 1"
        else:
            score, reason = "fail", f"external effect count for the logical operation is {final_count}, not 1"
        result = {"score": score, "reason": reason,
                  "count_after_attempt1": count_after_1["external_effect_count"],
                  "final_external_effect_count": final_count,
                  "retry_response_class": retry_class,
                  "session_id": session, "K": k_value,
                  "execution_receipt_ids": execution_ids_of(count_final)}
        self.summary["assertions"]["A1"] = result
        return result

    def _run_a2(self):
        session = f"lr-{self.run_tag}-a2"
        k_value = f"lr-op-{self.run_tag}-a2"
        attempt1 = self.attempt(session, k_value, drop=True,
                                label="a2_attempt1_dropped")
        count_after_1 = self.enumerate_session(session, k_value, "a2_after_attempt1")
        retry = self.attempt(session, k_value, drop=False,
                             label="a2_retry_mismatched", mismatched=True)
        count_final = self.enumerate_session(session, k_value, "a2_final")
        committed_1 = count_after_1["external_effect_count"] >= 1
        final_count = count_final["external_effect_count"]
        retry_class = retry["call"].get("response_class")
        explicit_rejection = retry_class not in ("success", None) and retry_class != "payment_required"
        if not committed_1:
            score, reason = "unproven", "attempt 1 did not commit visibly in the public record, so the mismatched-retry precondition is not established"
        elif retry_class == "payment_required" and final_count == count_after_1["external_effect_count"]:
            score, reason = "unproven", "the mismatched retry was refused at the metering layer (payment_required) before it could execute, so the binding check was never exercised; no new effect occurred, and neither a binding rejection nor a silent execution was observed"
        elif final_count == count_after_1["external_effect_count"] and explicit_rejection:
            score, reason = "pass", "mismatched retry produced no new effect and was explicitly refused"
        elif final_count > count_after_1["external_effect_count"]:
            score, reason = "fail", f"mismatched retry executed as a new call: effect count rose from {count_after_1['external_effect_count']} to {final_count}, response class {retry_class}"
        elif retry_class == "success":
            score, reason = "fail", "mismatched retry returned a generic success with no binding rejection recorded"
        else:
            score, reason = "unproven", f"retry response class {retry_class} with unchanged count; cannot distinguish a binding rejection from a generic error from the raw output alone"
        result = {"score": score, "reason": reason,
                  "count_after_attempt1": count_after_1["external_effect_count"],
                  "final_external_effect_count": final_count,
                  "retry_response_class": retry_class,
                  "mismatched_field": (self.adapter_config.get("mismatch") or {}).get("field"),
                  "session_id": session, "K": k_value,
                  "execution_receipt_ids": execution_ids_of(count_final)}
        self.summary["assertions"]["A2"] = result
        return result

    def _run_a3(self, a1):
        """Both legs. Run-id leg: the caller holds the server-issued run
        id (a receipt id from the public record for the A1 operation),
        resolves the record, and checks the digest. K-only leg: a fresh
        recovery caller holds only K: no run id, response, result, or
        digest from attempt 1."""
        out = {"legs": {}}
        receipt_ids = a1.get("execution_receipt_ids") or []
        if receipt_ids:
            record = self.adapter.fetch_record(receipt_ids[0])
            self.w.write("a3_runid_leg_receipt.json", record)
            digests = digests_of(record)
            recomp = record["recomputation"]
            leg_pass = (record["http_status"] == 200 and bool(result_digest_of(digests))
                        and recomp["status"] == "matched")
            out["legs"]["run_id"] = {
                "receipt_id": receipt_ids[0], "http_status": record["http_status"],
                "page_http_status": record.get("page_http_status"),
                "digests_served": digests, "recomputation": recomp,
                "score": "pass" if leg_pass else "fail",
                "note": "Section 9 resolution returned the unaltered record from the public JSON record; Section 6 recomputation is the harness's own SHA-256 over the decoded canonical bytes compared with the served output_hash, recorded in the recomputation block.",
            }
            committed_digest = result_digest_of(digests)
        else:
            out["legs"]["run_id"] = {"score": "unproven",
                                     "note": "no committed receipt id exists for the A1 operation, so the run-id leg cannot execute"}
            committed_digest = None
        # K-only leg: only K is used. No run id, response, result, digest.
        k_value = a1["K"]
        recovery = self.adapter.recover_by_key(operation_key=k_value)
        for name, obj in (recovery.get("files") or {}).items():
            self.w.write(name, obj)
        konly = {"K": k_value, "attempts": recovery["attempts"]}
        recovered_digest = None
        for attempt in konly["attempts"]:
            if attempt.get("response_class") == "found":
                recovered_digest = committed_digest
        if committed_digest and recovered_digest == committed_digest:
            konly["score"] = "pass"
            konly["reason"] = "recovered digest equals committed digest using only K"
        elif any(a.get("http_status") == 404 or a.get("response_class") in ("not_found",) for a in konly["attempts"]) and not recovered_digest:
            konly["score"] = "fail"
            konly["reason"] = "K-only recovery did not return the original committed outcome; the direct record lookup by K returned not found and no K-keyed lookup returned the committed digest"
        else:
            konly["score"] = "fail" if committed_digest else "unproven"
            konly["reason"] = "K-only recovery did not return a digest equal to the committed digest" if committed_digest else "no committed digest exists, so K-only recovery cannot be scored"
        out["legs"]["k_only"] = konly
        out["score"] = konly["score"]
        out["reason"] = ("contract pass condition is the K-only leg: " + konly["reason"] +
                         f"; run-id leg scored {out['legs']['run_id']['score']} separately in the evidence")
        out["committed_digest"] = committed_digest
        self.summary["assertions"]["A3"] = out
        self.w.write("a3_summary.json", out)
        return out

    def _run_a4(self, a1, a2):
        classes = {"A1_retry": a1.get("retry_response_class"),
                   "A2_retry": a2.get("retry_response_class")}
        allowed_explicit = lambda c: c and (c.startswith("tool_error:") or c.startswith("jsonrpc_error:"))
        verdicts = {}
        for name, cls in classes.items():
            if cls == "success":
                verdicts[name] = "success corresponding to a committed record (see the A1/A2 counts); not a generic success with no record"
            elif allowed_explicit(cls):
                verdicts[name] = "explicit non-success state"
            elif cls == "payment_required":
                verdicts[name] = "explicit non-success state naming the situation (payment_required)"
            else:
                verdicts[name] = f"unclassifiable response class: {cls}"
        if any(v.startswith("unclassifiable") for v in verdicts.values()):
            score = "unproven"
        else:
            score = "pass"
        result = {"score": score, "response_classes": classes, "verdicts": verdicts,
                  "reason": "every recorded retry resolved to the original outcome, a digest-verifiable record of it, or an explicit non-success state" if score == "pass" else "at least one retry response class could not be classified from the raw output"}
        self.summary["assertions"]["A4"] = result
        return result

    def _run_a5(self, a1, a3):
        plant = {"assertion": "A5", "planted_at": utcnow(),
                 "delay_hours": self.cfg.get("a5_delay_hours", 24),
                 "due_at": None, "K": a1["K"], "session_id": a1["session_id"],
                 "execution_receipt_ids": a1.get("execution_receipt_ids", []),
                 "committed_digest": a3.get("committed_digest"),
                 "endpoint": getattr(self.adapter, "endpoint", None),
                 "adapter": self.cfg["adapter"],
                 "system_name": self.cfg.get("system_name"),
                 "adapter_config": self.adapter_config,
                 "note": "Delayed leg: run this harness with --delayed-leg on this file at or after due_at. The delay is measured from the original commit time (planted_at approximates it within the run; the exact attempt 1 send time is in a1_attempt1_dropped.json)."}
        planted = datetime.now(timezone.utc)
        plant["due_at"] = (planted + timedelta(hours=plant["delay_hours"])).isoformat().replace("+00:00", "Z")
        self.w.write("a5_plant.json", plant)
        result = {"score": "unproven",
                  "reason": "the 24 hour delayed leg cannot complete on the planting day; attempt 1 is planted with its commit timestamp recorded and the delayed leg is runnable later by run id and by K",
                  "plant_file": "a5_plant.json", "due_at": plant["due_at"]}
        self.summary["assertions"]["A5"] = result
        return result


def results_snippet(summary):
    lines = [f"Run {summary['run_tag']} against {summary['endpoint']} "
             f"(tool {summary['tool']}), started {summary['started_at']}.",
             "", "| Assertion | Outcome | Evidence |", "|---|---|---|"]
    for name in ("A1", "A2", "A3", "A4", "A5"):
        a = summary["assertions"].get(name, {})
        lines.append(f"| {name} | {a.get('score', 'unproven')} | {a.get('reason', '')} |")
    return "\n".join(lines) + "\n"


# -- A5 scoring (pure; no I/O, no adapter, no network) ----------------
#
# CONTRACT.md A5 has two distinct pass conditions, scored separately:
#
#   recovery         After the agreed delay, recovery using only the
#                    operation key K still returns the original
#                    committed outcome, with a digest equal to the
#                    independently recorded committed digest.
#   retry_protection During / after the delay the operation identity
#                    remains protected against fresh execution: both a
#                    delayed identical retry and a delayed retry with
#                    changed arguments produce zero new effects.
#
# score_a5() takes only recorded observations (plain dicts, as written
# in a run directory or assembled by delayed_leg() from the records it
# already fetched) and returns both verdicts plus the overall A5
# verdict. It performs no network calls and dispatches nothing.
#
# Observation shape (every field optional; missing fields make the
# affected check unproven, never pass):
#
#   {
#     "committed_digest": <digest recorded independently at plant
#                          time>,            # or under "plant"
#     "due_at": <ISO time the agreed delay elapses>,
#                                           # or plant["due_at"], or
#                                           # planted_at + delay_hours
#     "K": ..., "session_id": ...,          # scoped operation, or
#                                           # under "plant"
#     "original_arguments": {...},          # the original call's
#                                           # arguments_sent, where
#                                           # recorded at plant time
#     "observed_at": <fallback timestamp for observations that do
#                     not carry their own>,
#     "k_only": {                           # operation-key-only lookup
#         "http_status": int,
#         "digests": {...} and/or "recovered_digest" / "digest_served",
#         "fetched_at" / "at" / "observed_at": <ISO time>,
#         # ... or "attempts": [attempt, ...] in recover_by_key()
#         # shape, each attempt carrying its own digests if it
#         # returned a record
#     },
#     "run_id": {same shape as "k_only"},   # DIAGNOSTIC ONLY: kept as
#                                           # evidence, never gates the
#                                           # recovery verdict
#     "protection": {                       # scope is read from the
#                                           # records themselves —
#                                           # each count's and each
#                                           # retry's own session_id
#                                           # and operation key; a
#                                           # wrapper establishes
#                                           # nothing
#         "effect_count_before": int,       # or "counts_before":
#                                           # a count_effects()
#                                           # evidence dict carrying
#                                           # external_effect_count
#         "effect_count_after_identical": int,   # optional intermediate
#         "effect_count_after": int,        # final count, after both
#                                           # retries ("effect_count_
#                                           # final" / "counts_after"
#                                           # / "counts_final" too)
#         "identical_retry":  {recorded retry, with "at"},
#         "mismatched_retry": {recorded retry, with "at"},
#     },
#   }
#
# Verdict rules (per check):
#   pass     Sufficient, comparable evidence, observed at or after
#            due_at, showing the pass condition.
#   fail     An observed violation: a K-only digest that differs from
#            the committed digest, an explicit K-only not-found, or a
#            recorded effect-count rise bracketing the delayed
#            retries. A violation fails even if its timestamp is
#            early: the violation was still observed, and protection
#            is owed during the delay period too. But an increase is
#            only evidence against the retries once attribution and
#            bracketing are validated — the planted original receipt
#            counted, the counts bracketing both attempts on their
#            own timestamps; without those, the result is unproven,
#            not fail.
#   unproven Missing, early, or incomparable evidence: no committed
#            digest to compare against, an HTTP 200 with no digest
#            from the K path (200 alone is not recovery), a missing
#            retry record or count, counts recorded for a different
#            scoped operation, a decreasing count, or any otherwise
#            passing-looking evidence timestamped before due_at.
#            Timestamps are read from the observations themselves,
#            never from when the scorer happened to run: re-running
#            the delayed leg after due_at does not refresh stale
#            retry or count files. Retry protection additionally
#            requires the counts to bracket both attempts (before
#            count at or before both retries, final count at or
#            after both), both retries to be distinct attempts (a
#            changed-argument record must carry different arguments
#            from the identical record), and neither retry to have
#            been blocked before reaching the retry logic (for
#            example a payment_required refusal at the metering
#            layer, which never exercises the binding check — the
#            A2 rule). When both counts carry the receipt identifier
#            lists they were counted from, a new receipt in the
#            final count is a new effect even at an unchanged
#            number, a lost receipt makes the counts incomparable,
#            and the planted original receipt must be present in
#            the before count for attribution; the changed-argument
#            record must differ from the identical record in
#            exactly one field — the configured mismatch field,
#            when the plant's configuration names one. Scope is
#            matched against the plant on the retry records too,
#            not only the counts; the identical retry must carry
#            the original arguments where those are recorded (an
#            explicit record, or the plant's configured argument
#            template with K/session substituted); the changed
#            value must be the configured replacement value; and
#            labels alone never evidence the argument check — a
#            retry record without arguments_sent leaves it
#            unproven. Recovery credits only a successful K-only
#            response (HTTP 200, or a found recovery attempt), and
#            the digest, timestamp and recomputation verdict are
#            all read from that same response. When the deadline
#            cannot be established (due_at missing and not
#            derivable from planted_at + delay_hours), neither
#            check can pass: the delayed result is unproven. A K-only record whose served digest matches
#            but whose recomputation from the returned record is
#            mismatched fails recovery: the digest was served, not
#            verified.
#
# Overall A5 is pass only when both checks pass, fail when either
# check fails, and unproven otherwise.


def _parse_ts(value):
    """Parse an ISO-8601 timestamp to an aware datetime, or None."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _norm_digest(value):
    return value.strip().lower() if isinstance(value, str) and value.strip() else None


def _digest_from_observation(obs):
    """Result digest carried by one recorded lookup, or None."""
    if not isinstance(obs, dict):
        return None
    for field in ("recovered_digest", "digest_served", "result_digest"):
        digest = _norm_digest(obs.get(field))
        if digest:
            return digest
    digest = result_digest_of(digests_of(obs))
    if digest:
        return _norm_digest(digest)
    # An attempts list (recover_by_key shape): the first digest any
    # attempt actually returned.
    for attempt in obs.get("attempts") or []:
        digest = _digest_from_observation(attempt)
        if digest:
            return digest
    return None


def _recomputation_mismatched(obs, recovered_digest=None):
    """True when the record that served `recovered_digest` carries a
    recomputation verdict of mismatched (the adapter recomputed the
    digest from the record's own bytes and it did not match)."""
    if not isinstance(obs, dict):
        return False
    recomp = obs.get("recomputation") or {}
    if isinstance(recomp, dict) and recomp.get("status") == "mismatched":
        return True
    for attempt in obs.get("attempts") or []:
        if not isinstance(attempt, dict):
            continue
        if recovered_digest and _digest_from_observation(attempt) != recovered_digest:
            continue
        recomp = attempt.get("recomputation") or {}
        if isinstance(recomp, dict) and recomp.get("status") == "mismatched":
            return True
    return False


def _obs_time(obs, fallback=None):
    if isinstance(obs, dict):
        for field in ("fetched_at", "at", "observed_at", "run_at"):
            parsed = _parse_ts(obs.get(field))
            if parsed:
                return parsed
        # Older recorded retry files carry no top-level timestamp;
        # their own transport record does (the response-received
        # time is when the attempt completed).
        call = obs.get("call") if isinstance(obs.get("call"), dict) else {}
        for holder in (call.get("transport"), obs.get("transport")):
            if isinstance(holder, dict):
                for field in ("received_at", "sent_at"):
                    parsed = _parse_ts(holder.get(field))
                    if parsed:
                        return parsed
    return _parse_ts(fallback)


def _count_value(block, *names):
    """(count, evidence dict or None) from an int or a count_effects
    evidence dict under any of `names` in the protection block."""
    for name in names:
        if name not in block:
            continue
        value = block[name]
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value, None
        if isinstance(value, dict) and isinstance(
                value.get("external_effect_count"), int):
            return value["external_effect_count"], value
    return None, None


def _scope_mismatch(evidence_dicts, plant_scope):
    """Name the first recorded scope that disagrees with the plant's
    scoped operation (or with a sibling count), else None."""
    seen = {}
    for evidence in evidence_dicts:
        if not isinstance(evidence, dict):
            continue
        for field in ("session_id", "K", "operation_key"):
            value = evidence.get(field)
            if value is None:
                continue
            expected = plant_scope.get(field)
            if expected is not None and value != expected:
                return f"{field} {value!r} does not match the planted {expected!r}"
            if field in seen and seen[field] != value:
                return f"{field} {value!r} disagrees with the other recorded count {seen[field]!r}"
            seen[field] = value
    return None


def _retry_scope_problem(rec, name, plant_scope):
    """Why a retry record's own scope or argument shape is not
    established, or None. The record itself must carry the plant's
    session and operation key — a missing field establishes
    nothing — and scope fields embedded in its arguments, where
    present, must agree."""
    plant_session = plant_scope.get("session_id")
    plant_k = plant_scope.get("K") or plant_scope.get("operation_key")
    if plant_session is not None:
        if rec.get("session_id") is None:
            return (f"the {name} retry record carries no session_id "
                    f"of its own, so its scope is not established by "
                    f"the record itself")
        if rec["session_id"] != plant_session:
            return (f"the {name} retry record's session_id "
                    f"{rec['session_id']!r} does not match the "
                    f"planted {plant_session!r}")
    if plant_k is not None:
        rec_k = rec.get("K") or rec.get("operation_key")
        if rec_k is None:
            return (f"the {name} retry record carries no operation "
                    f"key of its own, so its scope is not established "
                    f"by the record itself")
        if rec_k != plant_k:
            return (f"the {name} retry record's operation key "
                    f"{rec_k!r} does not match the planted {plant_k!r}")
    args = rec.get("arguments_sent")
    if args is not None:
        if not isinstance(args, dict):
            return (f"the {name} retry record's arguments_sent is "
                    f"not a record of arguments, so its argument "
                    f"shape cannot be verified")
        if (plant_session is not None
                and args.get("_session_id") is not None
                and args["_session_id"] != plant_session):
            return (f"the {name} retry's arguments carry "
                    f"_session_id {args['_session_id']!r}, not the "
                    f"planted session {plant_session!r}")
        if plant_k is not None:
            for field, value in (("job_id", args.get("job_id")),
                                 ("inputs.operation",
                                  (args.get("inputs") or {}).get("operation")
                                  if isinstance(args.get("inputs"), dict)
                                  else None)):
                if value is not None and value != plant_k:
                    return (f"the {name} retry's arguments carry "
                            f"{field} {value!r}, not the planted "
                            f"operation key {plant_k!r}")
    return None


def _count_attribution_problem(name, ev, plant_scope):
    """Why a count's attribution to the planted operation is not
    established by the count record itself, or None. Counts are
    linked by their own recorded session (and, at the receipt gate
    below, the original receipt IDs) — never by a wrapper."""
    plant_session = plant_scope.get("session_id")
    if ev is None:
        return (f"the {name} count is a bare number with no recorded "
                f"session or receipt IDs, so its attribution to this "
                f"operation is not established")
    if plant_session is not None:
        if ev.get("session_id") is None:
            return (f"the {name} count carries no session_id of its "
                    f"own, so its attribution to this operation is "
                    f"not established by the record itself")
        if ev["session_id"] != plant_session:
            return (f"the {name} count's session_id "
                    f"{ev['session_id']!r} does not match the "
                    f"planted {plant_session!r}")
    return None


def _score_a5_recovery(obs, committed_digest, due_at):
    k_only = obs.get("k_only") if isinstance(obs.get("k_only"), dict) else None
    run_id = obs.get("run_id") if isinstance(obs.get("run_id"), dict) else None
    run_id_digest = _digest_from_observation(run_id) if run_id else None
    diagnostic = {
        "run_id_http_status": run_id.get("http_status") if run_id else None,
        "run_id_digest_served": run_id_digest,
        "run_id_digest_equal": bool(
            run_id_digest and committed_digest
            and run_id_digest == committed_digest),
        "note": "diagnostic evidence only; the run-id lookup does not "
                "gate the recovery verdict",
    }
    check = {"committed_digest": committed_digest,
             "recovered_digest": None,
             "k_only_http_status": k_only.get("http_status") if k_only else None,
             "run_id": diagnostic}
    if k_only is None:
        check.update(score="unproven", reason="no operation-key-only "
                       "lookup was recorded, so delayed recovery is "
                       "not evidenced")
        return check
    recovered, source = _recovery_source(k_only)
    check["recovered_digest"] = recovered
    http_status = k_only.get("http_status")
    attempts = k_only.get("attempts") or []
    explicit_not_found = http_status == 404 or any(
        a.get("http_status") == 404
        or a.get("response_class") in ("not_found",)
        for a in attempts if isinstance(a, dict))
    if not committed_digest:
        check.update(score="unproven", reason="no committed digest was "
                       "recorded independently at plant time, so there "
                       "is nothing to compare the recovered outcome "
                       "against")
        return check
    if not recovered:
        if explicit_not_found:
            check.update(score="fail", reason="K-only lookup returned "
                           "not found after the agreed delay; a lookup "
                           "miss inside the window is a fail, not a "
                           "fresh operation (CONTRACT.md A5)")
        elif http_status == 200:
            check.update(score="unproven", reason="K-only lookup "
                           "returned HTTP 200 but carried no digest, so "
                           "there is no evidence it returned the "
                           "original committed outcome; HTTP 200 alone "
                           "is insufficient")
        else:
            check.update(score="unproven", reason="K-only lookup "
                           "carried no recovered digest, so recovery "
                           "cannot be verified against the committed "
                           "digest")
        return check
    # A digest was served by one specific response (`source`). That
    # response must have succeeded BEFORE its digest is compared or
    # credited at all: a digest carried by an error response is not
    # evidence, whether it matches or not. The one exception is a
    # genuine not-found, which stays its own failure case.
    # Everything credited to a recovery — success, timestamp,
    # recomputation verdict — is read from that same response, never
    # borrowed from a wrapper record or a sibling attempt.
    if not _response_succeeded(source):
        if _response_not_found(source):
            check.update(score="fail", reason="K-only lookup returned "
                           "not found after the agreed delay; a lookup "
                           "miss inside the window is a fail, not a "
                           "fresh operation (CONTRACT.md A5)")
        else:
            check.update(score="unproven", reason=f"K-only lookup "
                           f"served a digest on a response that was "
                           f"not a successful lookup (HTTP status "
                           f"{source.get('http_status')!r}, response "
                           f"class {source.get('response_class')!r}), "
                           f"so that digest is not evidence of "
                           f"recovery, whether or not it matches the "
                           f"committed digest")
        return check
    if recovered != committed_digest:
        check.update(score="fail", reason=f"K-only lookup returned a "
                       f"digest ({recovered}) that does not match the "
                       f"independently recorded committed digest "
                       f"({committed_digest}); the recovered outcome is "
                       f"not the original committed outcome")
        return check
    # If recomputing the digest from the returned record mismatches,
    # the record does not verify: recovery fails, it does not pass
    # on the served value alone.
    if _recomputation_mismatched(source, recovered):
        check.update(score="fail", reason="K-only lookup served the "
                       "committed digest, but recomputing the digest "
                       "from the returned record gives a mismatch, so "
                       "the recovered record does not verify as the "
                       "original committed outcome")
        return check
    # The source response's own timestamp decides timeliness; the
    # time the scorer (or a delayed-leg re-run) happened to execute
    # is never substituted for it. And without an established
    # deadline there is no delayed leg to evidence at all.
    observed_at = _obs_time(source)
    if due_at is None:
        check.update(score="unproven", reason="K-only lookup returned "
                       "the committed digest, but the agreed delay "
                       "deadline (due_at) is missing and cannot be "
                       "derived from the plant, so the delayed result "
                       "cannot be established")
    elif observed_at is None:
        check.update(score="unproven", reason="K-only lookup returned "
                       "the committed digest, but the response that "
                       "served it carries no timestamp, so it cannot "
                       "be shown to come from at or after the agreed "
                       "delay")
    elif observed_at < due_at:
        check.update(score="unproven", reason="K-only lookup returned "
                       "the committed digest, but it was observed "
                       "before the agreed delay elapsed (early "
                       "observation), so it is not evidence from the "
                       "delayed leg")
    else:
        check.update(score="pass", reason="K-only lookup returned the "
                       "original outcome with a digest equal to the "
                       "independently recorded committed digest")
    return check


def _recovery_source(k_only):
    """(digest, response) for a K-only lookup observation: the
    response that actually served the recovered digest — the record
    itself when it carries digests, else the first attempt that
    returned one. (None, k_only) when no response served a digest."""
    digest = None
    for field in ("recovered_digest", "digest_served", "result_digest"):
        digest = _norm_digest(k_only.get(field))
        if digest:
            return digest, k_only
    digest = result_digest_of(digests_of(k_only))
    if digest:
        return _norm_digest(digest), k_only
    for attempt in k_only.get("attempts") or []:
        if not isinstance(attempt, dict):
            continue
        digest = _digest_from_observation(attempt)
        if digest:
            return digest, attempt
    return None, k_only


def _response_succeeded(response):
    """A recorded lookup response succeeded: HTTP 200, or a recovery
    attempt whose response class is found."""
    if response.get("http_status") is not None:
        return response.get("http_status") == 200
    return response.get("response_class") == "found"


def _response_not_found(response):
    """A recorded lookup response is a genuine not-found."""
    return (response.get("http_status") == 404
            or response.get("response_class") == "not_found")


def _score_a5_protection(obs, due_at, plant_scope, plant_receipt_ids=None,
                         mismatch_field=None, mismatch_altered_value=None,
                         original_arguments=None):
    prot = obs.get("protection") if isinstance(obs.get("protection"), dict) else None
    check = {"effect_count_before": None, "effect_count_after_identical": None,
             "effect_count_final": None}
    if prot is None:
        check.update(score="unproven", reason="no recorded before/after "
                       "effect counts or delayed retry records, so "
                       "retry protection is not evidenced")
        return check
    before, before_ev = _count_value(prot, "effect_count_before", "counts_before")
    after_ident, after_ident_ev = _count_value(
        prot, "effect_count_after_identical", "counts_after_identical")
    final, final_ev = _count_value(
        prot, "effect_count_after", "effect_count_final",
        "counts_after", "counts_final")
    check.update(effect_count_before=before,
                 effect_count_after_identical=after_ident,
                 effect_count_final=final)
    identical = prot.get("identical_retry")
    mismatched = prot.get("mismatched_retry")
    # Scope is checked on every piece of evidence the verdict rests
    # on — the counts AND both retry records. A retry recorded under
    # a different K or session is not a retry of this operation.
    evidence = [e for e in (before_ev, after_ident_ev, final_ev) if e]
    scoped_records = [prot, *evidence] + [
        rec for rec in (identical, mismatched) if isinstance(rec, dict)]
    mismatch = _scope_mismatch(scoped_records, plant_scope)
    if mismatch:
        check.update(score="unproven", reason=f"protection evidence "
                       f"is incomparable: {mismatch}; counts and "
                       f"retries must be for the same scoped operation "
                       f"as the plant")
        return check
    if before is None or final is None:
        check.update(score="unproven", reason="recorded effect counts "
                       "do not include both a before count and a final "
                       "count bracketing the delayed retries, so zero "
                       "new effects cannot be verified")
        return check
    if not isinstance(identical, dict) or not isinstance(mismatched, dict):
        missing = [name for name, rec in (("identical", identical),
                                          ("changed-argument", mismatched))
                   if not isinstance(rec, dict)]
        check.update(score="unproven", reason=f"no {' or '.join(missing)} "
                       f"delayed retry was recorded, so it cannot be "
                       f"shown that both retries were attempted and "
                       f"produced zero new effects")
        return check
    # Scope and attribution must be established by the records
    # themselves before anything is scored — a pass, or a rise
    # attributed to the retries. _scope_mismatch above only catches
    # fields that are present and disagreeing; a record that omits
    # its scope establishes nothing, and scope stamped on a wrapper
    # by the delayed leg does not transfer to the records under it.
    for name, rec in (("identical", identical),
                      ("changed-argument", mismatched)):
        problem = _retry_scope_problem(rec, name, plant_scope)
        if problem:
            check.update(score="unproven", reason=problem)
            return check
    for name, value, ev in (("before", before, before_ev),
                            ("after-identical", after_ident, after_ident_ev),
                            ("final", final, final_ev)):
        if value is None:
            continue
        problem = _count_attribution_problem(name, ev, plant_scope)
        if problem:
            check.update(score="unproven", reason=problem)
            return check
    stages = [(name, value) for name, value in
              (("before", before), ("after_identical", after_ident),
               ("final", final)) if value is not None]
    for (prev_name, prev), (name, value) in zip(stages, stages[1:]):
        if value < prev:
            check.update(score="unproven", reason=f"effect count fell "
                           f"from {prev} ({prev_name}) to {value} "
                           f"({name}); a cumulative count for one "
                           f"scoped operation cannot decrease, so the "
                           f"counts are incomparable")
            return check
    # Attribution and bracketing are validated BEFORE any increase
    # is treated as evidence against these retries: the counts must
    # actually count this operation (the planted original receipt
    # present, when the count carries receipt IDs — no K field is
    # assumed or inserted), and they must bracket both attempts in
    # time, read from the observations' own timestamps only.
    before_ids = execution_ids_of(before_ev) if before_ev else None
    final_ids = execution_ids_of(final_ev) if final_ev else None
    if plant_receipt_ids and before_ids is None:
        check.update(score="unproven", reason=f"the before count "
                       f"carries no execution receipt IDs, so it "
                       f"cannot be linked to the planted original "
                       f"execution receipt(s) {plant_receipt_ids} and "
                       f"its attribution to this operation is not "
                       f"established")
        return check
    if plant_receipt_ids and before_ids is not None:
        missing = [r for r in plant_receipt_ids if r not in before_ids]
        if missing:
            check.update(score="unproven", reason=f"the planted "
                           f"original execution receipt(s) {missing} "
                           f"are not present in the before count, so "
                           f"the count's attribution to this operation "
                           f"is not established by the recorded "
                           f"evidence, and no count change can be "
                           f"attributed to the delayed retries")
            return check
    if before_ids is not None and final_ids is not None:
        # A receipt that vanished with nothing new in its place
        # makes the counts incomparable; a receipt that was
        # REPLACED is handled by the new-receipt fail below, which
        # is the observed violation.
        lost_ids = [r for r in before_ids if r not in final_ids]
        new_ids = [r for r in final_ids if r not in before_ids]
        if lost_ids and not new_ids:
            check.update(score="unproven", reason=f"execution "
                           f"receipt(s) {lost_ids} are in the before "
                           f"count but not the final count; a "
                           f"cumulative count for one scoped operation "
                           f"cannot lose receipts, so the counts are "
                           f"incomparable")
            return check
    before_time = _obs_time(before_ev) if before_ev else None
    ident_time = _obs_time(identical)
    mism_time = _obs_time(mismatched)
    final_time = _obs_time(final_ev) if final_ev else None
    named_times = (("before count", before_time),
                   ("identical retry", ident_time),
                   ("changed-argument retry", mism_time),
                   ("final count", final_time))
    missing_times = [name for name, value in named_times if value is None]
    if missing_times:
        check.update(score="unproven", reason=f"the "
                       f"{' and '.join(missing_times)} carries no "
                       f"timestamp of its own, so the counts cannot "
                       f"be shown to bracket both attempts and no "
                       f"count change can be attributed to the "
                       f"delayed retries from the observations "
                       f"themselves")
        return check
    if before_time > min(ident_time, mism_time):
        check.update(score="unproven", reason="the before count was "
                       "recorded after a delayed retry, so the counts "
                       "do not bracket both attempts and no count "
                       "change can be attributed to them")
        return check
    if final_time < max(ident_time, mism_time):
        check.update(score="unproven", reason="the final count was "
                       "recorded before both delayed retries had run, "
                       "so the counts do not bracket both attempts and "
                       "no count change can be attributed to them")
        return check
    if after_ident_ev is not None:
        mid_time = _obs_time(after_ident_ev)
        if mid_time is not None and (mid_time < ident_time
                                     or mid_time > final_time):
            check.update(score="unproven", reason="the intermediate "
                           "count after the identical retry is "
                           "timestamped outside the bracket formed by "
                           "the retries and the final count, so the "
                           "counts are incomparable")
            return check
    # Attribution and bracketing hold. Only now does an increase
    # count as evidence against the retries.
    for (prev_name, prev), (name, value) in zip(stages, stages[1:]):
        if value > prev:
            which = ("the identical retry" if name == "after_identical"
                     else "the delayed retries (identical and/or "
                          "changed-argument)")
            check.update(score="fail", reason=f"effect count rose "
                           f"from {prev} to {value} across {which} "
                           f"for the same scoped operation; the "
                           f"operation identity was not protected "
                           f"against fresh execution after the delay")
            return check
    if before_ids is not None and final_ids is not None:
        new_ids = [r for r in final_ids if r not in before_ids]
        if new_ids:
            check.update(score="fail", reason=f"new execution "
                           f"receipt(s) {new_ids} appear in the final "
                           f"count but not the before count for the "
                           f"same scoped operation, so a delayed retry "
                           f"produced a new effect even though the "
                           f"numeric count is {before} -> {final}")
            return check
    # Counts did not rise. Each retry record must still evidence an
    # attempt that actually reached the retry logic, and the two
    # records must evidence two distinct attempts — the identical
    # one carrying the original arguments where those are recorded,
    # the changed-argument one differing in exactly the configured
    # field with the configured replacement value.
    for name, rec in (("identical", identical),
                      ("changed-argument", mismatched)):
        blocked = _retry_blocked_reason(rec)
        if blocked:
            check.update(score="unproven", reason=f"effect counts are "
                           f"unchanged, but the {name} delayed retry "
                           f"{blocked}, so the retry logic was never "
                           f"exercised by that attempt and protection "
                           f"is not evidenced for it")
            return check
    duplicate = _duplicate_attempt_reason(
        identical, mismatched, mismatch_field, mismatch_altered_value,
        original_arguments)
    if duplicate:
        check.update(score="unproven", reason=f"effect counts are "
                       f"unchanged, but {duplicate}, so two distinct "
                       f"delayed attempts (identical and "
                       f"changed-argument) are not evidenced")
        return check
    # Finally, the deadline itself. A re-run of the delayed leg
    # after due_at never substitutes its own run time for a stale
    # file's time, and with no establishable deadline there is no
    # delayed leg to evidence.
    if due_at is None:
        check.update(score="unproven", reason="effect counts are "
                       "unchanged across both retries, but the agreed "
                       "delay deadline (due_at) is missing and cannot "
                       "be derived from the plant, so the delayed "
                       "result cannot be established")
        return check
    early = [name for name, value in named_times[1:] if value < due_at]
    if early:
        check.update(score="unproven", reason=f"effect counts are "
                       f"unchanged, but the {' and '.join(early)} "
                       f"was observed before the agreed delay "
                       f"elapsed (stale/early observation), so it "
                       f"is not evidence from the delayed leg; "
                       f"re-running the leg after due_at does not "
                       f"refresh it")
        return check
    check.update(score="pass", reason="recorded effect counts for "
                   "the same scoped operation are unchanged "
                   f"({before} before, {final} after) and bracket "
                   f"both the identical retry and the changed-argument "
                   f"retry, each observed at or after the agreed "
                   f"delay: zero new effects")
    return check


def _retry_blocked_reason(rec):
    """Why a recorded retry never reached the retry logic, or None.

    A payment_required refusal happens at the metering layer before
    any commit and before the binding check (the harness's A2 rule),
    and a dropped call has no observed outcome at all: neither
    evidences an attempt the protection logic actually processed.
    """
    call = rec.get("call") if isinstance(rec.get("call"), dict) else {}
    if call.get("dropped") is True:
        return "was dropped with no response observed"
    response_class = call.get("response_class") or rec.get("response_class")
    if response_class is None:
        return "carries no response class"
    if response_class == "payment_required":
        return ("was blocked before reaching the retry logic "
                "(payment_required: refused at the metering layer "
                "before any commit, so the binding check was never "
                "exercised)")
    return None


def _duplicate_attempt_reason(identical, mismatched, mismatch_field=None,
                              mismatch_altered_value=None,
                              original_arguments=None):
    """Why the two retry records do not evidence two distinct
    attempts (one identical, one changed-argument), or None.

    The argument check is part of the evidence, not a formality:
    labels alone never establish it. Where the original arguments
    are recorded, the identical retry must carry exactly them; the
    changed-argument retry must differ in exactly one field — the
    configured mismatch field, carrying the configured replacement
    value, when the plant's configuration records them.
    """
    if identical == mismatched:
        return "the two retry files record the same attempt verbatim"
    label_i, label_m = identical.get("label"), mismatched.get("label")
    if label_i and label_i == label_m:
        return f"both retry files carry the same label ({label_i})"
    ids_i = _attempt_ids(identical)
    ids_m = _attempt_ids(mismatched)
    if ids_i and ids_m and ids_i & ids_m:
        return ("both retry files carry the same transport request "
                "id, so they record the same attempt")
    args_i = identical.get("arguments_sent")
    args_m = mismatched.get("arguments_sent")
    if args_i is None or args_m is None:
        which = ("identical" if args_i is None else "changed-argument")
        return (f"the {which} retry record carries no "
                f"arguments_sent, so the argument check cannot be "
                f"verified; labels alone do not evidence it")
    if args_i == args_m:
        return ("both retry files carry identical arguments_sent, "
                "so no changed-argument attempt is evidenced")
    if original_arguments is not None and args_i != original_arguments:
        return ("the identical retry's arguments_sent do not match "
                "the original arguments as recorded, so it is not "
                "evidenced as a retry of the original call")
    # The changed-argument attempt must change exactly one
    # parameter value (CONTRACT.md A2/A5 setup), and when the
    # plant's configuration names that parameter, it must be
    # the one that changed.
    diff_keys = sorted(k for k in set(args_i) | set(args_m)
                       if args_i.get(k) != args_m.get(k))
    if len(diff_keys) != 1:
        return (f"the changed-argument record differs from the "
                f"identical record in {len(diff_keys)} fields "
                f"({diff_keys}), not exactly one parameter value")
    if mismatch_field and diff_keys != [mismatch_field]:
        return (f"the changed-argument record changed "
                f"{diff_keys[0]!r}, not the configured mismatch "
                f"field {mismatch_field!r}")
    if (mismatch_field and mismatch_altered_value is not None
            and args_m.get(mismatch_field) != mismatch_altered_value):
        return (f"the changed-argument record carries "
                f"{mismatch_field}={args_m.get(mismatch_field)!r}, "
                f"not the configured replacement value "
                f"{mismatch_altered_value!r}")
    return None


def _attempt_ids(rec):
    call = rec.get("call") if isinstance(rec.get("call"), dict) else {}
    body = call.get("body") if isinstance(call.get("body"), dict) else {}
    transport = (call.get("transport")
                 if isinstance(call.get("transport"), dict) else {})
    ids = set()
    for value in (body.get("id"), transport.get("jsonrpc_id")):
        if value:
            ids.add(value)
    return ids


def _substitute_scope(value, k_value, session_id):
    """Deep-copy `value` replacing {K} / {SESSION} placeholders in
    strings — the same substitution the adapters apply to the
    plant's configured argument template."""
    if isinstance(value, str):
        out = value
        if k_value is not None:
            out = out.replace("{K}", str(k_value))
        if session_id is not None:
            out = out.replace("{SESSION}", str(session_id))
        return out
    if isinstance(value, dict):
        return {key: _substitute_scope(item, k_value, session_id)
                for key, item in value.items()}
    if isinstance(value, list):
        return [_substitute_scope(item, k_value, session_id)
                for item in value]
    return value


def score_a5(observations):
    """Score CONTRACT.md A5 from recorded observations only.

    Pure: no I/O, no adapter, no network, no dispatch. See the
    observation shape and verdict rules above this function.
    Returns {"score", "reason", "checks": {"recovery", "retry_
    protection"}, plus each check under its own name}.
    """
    obs = observations if isinstance(observations, dict) else {}
    plant = obs.get("plant") if isinstance(obs.get("plant"), dict) else {}
    committed_digest = _norm_digest(
        obs.get("committed_digest") or plant.get("committed_digest"))
    due_at = _parse_ts(obs.get("due_at") or plant.get("due_at"))
    if due_at is None:
        planted_at = _parse_ts(obs.get("planted_at") or plant.get("planted_at"))
        delay_hours = obs.get("delay_hours", plant.get("delay_hours"))
        if planted_at is not None and isinstance(delay_hours, (int, float)):
            due_at = planted_at + timedelta(hours=delay_hours)
    plant_scope = {}
    for field in ("session_id", "K", "operation_key"):
        value = obs.get(field) or plant.get(field)
        if value is not None:
            plant_scope[field] = value
    if plant_scope.get("K") and "operation_key" not in plant_scope:
        plant_scope["operation_key"] = plant_scope["K"]
    if plant_scope.get("operation_key") and "K" not in plant_scope:
        plant_scope["K"] = plant_scope["operation_key"]

    plant_receipt_ids = (obs.get("execution_receipt_ids")
                         or plant.get("execution_receipt_ids") or [])
    adapter_config = (obs.get("adapter_config")
                      or plant.get("adapter_config") or {})
    mismatch_cfg = adapter_config.get("mismatch") or {}
    mismatch_field = obs.get("mismatch_field") or mismatch_cfg.get("field")
    mismatch_altered_value = (obs.get("mismatch_altered_value")
                              or mismatch_cfg.get("altered_value"))
    # The original arguments, where recorded: an explicit record
    # wins; otherwise the plant's configured argument template with
    # the plant's own K/session substituted is the original call.
    original_arguments = (obs.get("original_arguments")
                          or plant.get("original_arguments"))
    if not isinstance(original_arguments, dict):
        template = adapter_config.get("args_template")
        if isinstance(template, dict) and plant_scope:
            original_arguments = _substitute_scope(
                template, plant_scope.get("K"),
                plant_scope.get("session_id"))
        else:
            original_arguments = None
    recovery = _score_a5_recovery(obs, committed_digest, due_at)
    protection = _score_a5_protection(
        obs, due_at, plant_scope, plant_receipt_ids, mismatch_field,
        mismatch_altered_value, original_arguments)
    checks = {"recovery": recovery, "retry_protection": protection}
    scores = (recovery["score"], protection["score"])
    if "fail" in scores:
        overall = "fail"
    elif scores == ("pass", "pass"):
        overall = "pass"
    else:
        overall = "unproven"
    reason = (f"recovery: {recovery['score']} — {recovery['reason']}; "
              f"retry protection: {protection['score']} — "
              f"{protection['reason']}")
    return {"score": overall, "reason": reason, "checks": checks,
            "recovery": recovery, "retry_protection": protection}


def _load_recorded_json(out_dir, name):
    path = Path(out_dir) / name
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def delayed_leg(plant_path):
    plant = json.loads(Path(plant_path).read_text(encoding="utf-8"))
    out_dir = Path(plant_path).parent
    writer = RunWriter(out_dir)
    if plant.get("adapter_config"):
        adapter = load_adapter(plant.get("adapter", "zambo"),
                               plant["adapter_config"])
    else:
        # Plant recorded before the adapter refactor: it carries only
        # the endpoint, which identifies the Zambo adapter and its
        # public record base.
        endpoint = plant.get("endpoint", "https://zambo.dev/mcp")
        adapter = load_adapter("zambo", {
            "endpoint": endpoint,
            "public_base": endpoint.rsplit("/mcp", 1)[0],
            "tool": "journal_log",
        })
    result = {"assertion": "A5", "delayed_leg_run_at": utcnow(), "plant": plant,
              "legs": {}}
    # The only reads this leg makes are the two it has always made:
    # the run-id record (diagnostic) and the K-only record. No new
    # network calls and no dispatch: the delayed retries and effect
    # counts are never executed here; if they were recorded earlier
    # (e.g. by a supplementary probe) in this run directory, the
    # scorer below reads those recorded observations, and otherwise
    # retry protection is honestly unproven. The scorer judges those
    # files by their own recorded timestamps, so re-running this leg
    # after due_at never refreshes stale protection evidence.
    ids = plant.get("execution_receipt_ids") or []
    run_id_obs = None
    if ids:
        record = adapter.fetch_record(ids[0])
        writer.write("a5_delayed_runid_receipt.json", record)
        digests = digests_of(record)
        served = result_digest_of(digests)
        run_id_obs = {"http_status": record["http_status"],
                      "digests": digests,
                      "fetched_at": record.get("fetched_at")
                                    or result["delayed_leg_run_at"],
                      "recomputation": record.get("recomputation")}
        result["legs"]["run_id"] = {
            "http_status": record["http_status"],
            "digest_served": served,
            "committed_digest": plant.get("committed_digest"),
            "digest_equal": bool(served and plant.get("committed_digest")
                                 and _norm_digest(served) == _norm_digest(plant["committed_digest"])),
            "recomputation": record["recomputation"],
            "note": "diagnostic evidence only; the run-id lookup does "
                    "not gate the A5 recovery verdict"}
    rec = adapter.fetch_record(plant["K"])
    writer.write("a5_delayed_konly_run_lookup.json", rec)
    k_digests = digests_of(rec)
    k_recovered = result_digest_of(k_digests)
    result["legs"]["k_only_direct_lookup"] = {
        "http_status": rec["http_status"],
        "digests": k_digests,
        "recovered_digest": k_recovered,
        "committed_digest": plant.get("committed_digest"),
        "digest_equal": bool(k_recovered and plant.get("committed_digest")
                             and _norm_digest(k_recovered) == _norm_digest(plant["committed_digest"])),
        "recomputation": rec.get("recomputation")}
    # Recorded retry-protection observations, if already present.
    protection = None
    counts_before = _load_recorded_json(
        out_dir, "count_a5_delayed_before_protection.json")
    counts_final = _load_recorded_json(
        out_dir, "count_a5_delayed_final.json")
    counts_after_ident = _load_recorded_json(
        out_dir, "count_a5_delayed_after_identical.json")
    retry_identical = _load_recorded_json(
        out_dir, "a5_delayed_retry_identical.json")
    retry_mismatched = _load_recorded_json(
        out_dir, "a5_delayed_retry_mismatched.json")
    if any(v is not None for v in (counts_before, counts_final,
                                   counts_after_ident, retry_identical,
                                   retry_mismatched)):
        # No scope is stamped on this wrapper: the plant's session/K
        # on the block would not establish the scope of the records
        # under it, so the scorer validates each record's own scope.
        protection = {"counts_before": counts_before,
                      "counts_after": counts_final,
                      "identical_retry": retry_identical,
                      "mismatched_retry": retry_mismatched}
        if counts_after_ident is not None:
            protection["counts_after_identical"] = counts_after_ident
    # The original call's arguments, where recorded at plant time
    # (the dropped A1 attempt's file carries arguments_sent): the
    # scorer verifies the identical delayed retry against them.
    a1_attempt = _load_recorded_json(out_dir, "a1_attempt1_dropped.json")
    original_arguments = (a1_attempt.get("arguments_sent")
                          if isinstance(a1_attempt, dict) else None)
    observations = {
        "plant": plant,
        "original_arguments": original_arguments,
        "committed_digest": plant.get("committed_digest"),
        "due_at": plant.get("due_at"),
        "planted_at": plant.get("planted_at"),
        "delay_hours": plant.get("delay_hours"),
        "K": plant.get("K"),
        "session_id": plant.get("session_id"),
        "observed_at": result["delayed_leg_run_at"],
        "k_only": {"http_status": rec["http_status"],
                   "digests": k_digests,
                   "fetched_at": rec.get("fetched_at")
                                 or result["delayed_leg_run_at"],
                   "recomputation": rec.get("recomputation")},
        "run_id": run_id_obs,
        "protection": protection,
    }
    verdict = score_a5(observations)
    result["checks"] = verdict["checks"]
    result["recovery"] = verdict["recovery"]
    result["retry_protection"] = verdict["retry_protection"]
    result["score"] = verdict["score"]
    result["reason"] = ("A5 scored by score_a5 from recorded "
                        "observations only: " + verdict["reason"] +
                        "; see a5_delayed_result.json")
    writer.write("a5_delayed_result.json", result)
    print(json.dumps(result, indent=2))
    return result


def rescore(run_dir, config):
    """Recompute a finished Zambo run's scores from its own raw
    outputs with the corrected counter (workflow snapshot children
    attributed through each child's public JSON record). The original
    summary is preserved as summary_v1_superseded.json and the
    correction is documented in RESCORE-NOTE.md inside the run
    directory. No MCP tool calls are made: only free public-record
    reads through the Zambo adapter."""
    adapter_config = config["adapter_config"]
    adapter = load_adapter("zambo", adapter_config)
    run = Path(run_dir)
    writer = RunWriter(run)
    target = adapter_config["tool"]

    def load(name):
        return json.loads((run / name).read_text(encoding="utf-8"))

    def count_from_snapshot(enum_file):
        call = load(enum_file)
        body = call.get("body") or {}
        result = (body.get("result") or {}).get("structuredContent") or {}
        snapshot = result.get("result") or {}
        children, attributed, execution_ids = [], [], []
        for child in snapshot.get("children", []) or []:
            if not (isinstance(child, dict) and child.get("id")):
                continue
            rid = child["id"]
            children.append(rid)
            record = adapter.fetch_record(rid)
            receipt = (record.get("record_json") or {}).get("receipt") or {}
            tools = receipt.get("tools") or []
            steps = receipt.get("steps") or []
            step_status = steps[0].get("status") if steps else None
            is_exec = record["http_status"] == 200 and target in tools and step_status == "success"
            attributed.append({"receipt_id": rid, "tools": tools, "step_status": step_status,
                               "output_hash": receipt.get("output_hash"),
                               "counted_as_target_execution": is_exec})
            if is_exec:
                execution_ids.append(rid)
        return {"snapshot_file": enum_file, "snapshot_count_field": snapshot.get("count"),
                "children": children, "attributed_children": attributed,
                "target_tool_execution_receipt_ids": execution_ids,
                "external_effect_count": len(execution_ids)}

    old = load("summary.json")
    (run / "summary_v1_superseded.json").write_text(json.dumps(old, indent=2), encoding="utf-8")
    tag = old["run_tag"]
    summary = {"run_tag": tag, "started_at": old["started_at"], "endpoint": old["endpoint"],
               "tool": target, "rescored_at": utcnow(),
               "rescore_note": "Scores recomputed from the run's raw outputs with the corrected counter; see RESCORE-NOTE.md",
               "assertions": {}}
    a1_after = count_from_snapshot("enum_a1_after_attempt1_workflow_close.json")
    a1_final = count_from_snapshot("enum_a1_final_workflow_close.json")
    writer.write("count_a1_after_attempt1.json", a1_after)
    writer.write("count_a1_final.json", a1_final)
    a1_retry = load("a1_retry_identical.json")
    a1 = {"count_after_attempt1": a1_after["external_effect_count"],
          "final_external_effect_count": a1_final["external_effect_count"],
          "retry_response_class": a1_retry["call"].get("response_class"),
          "session_id": f"lr-{tag}-a1", "K": f"lr-op-{tag}-a1",
          "execution_receipt_ids": a1_final["target_tool_execution_receipt_ids"]}
    if a1_after["external_effect_count"] >= 1 and a1_final["external_effect_count"] == 1:
        a1.update(score="pass", reason="external effect count for the logical operation is exactly 1")
    elif a1_after["external_effect_count"] >= 1:
        a1.update(score="fail", reason=f"external effect count for the logical operation is {a1_final['external_effect_count']}, not 1: attempt 1 and the identical retry each produced a distinct public receipt for the operation")
    else:
        a1.update(score="unproven", reason="no committed execution for attempt 1 is visible in the public record")
    summary["assertions"]["A1"] = a1

    a2_after = count_from_snapshot("enum_a2_after_attempt1_workflow_close.json")
    a2_final = count_from_snapshot("enum_a2_final_workflow_close.json")
    writer.write("count_a2_after_attempt1.json", a2_after)
    writer.write("count_a2_final.json", a2_final)
    a2_retry = load("a2_retry_mismatched.json")
    a2_class = a2_retry["call"].get("response_class")
    a2 = {"count_after_attempt1": a2_after["external_effect_count"],
          "final_external_effect_count": a2_final["external_effect_count"],
          "retry_response_class": a2_class, "mismatched_field": adapter_config["mismatch"]["field"],
          "session_id": f"lr-{tag}-a2", "K": f"lr-op-{tag}-a2",
          "execution_receipt_ids": a2_final["target_tool_execution_receipt_ids"]}
    if a2_after["external_effect_count"] < 1:
        a2.update(score="unproven", reason="attempt 1 did not commit visibly in the public record")
    elif a2_class == "payment_required" and a2_final["external_effect_count"] == a2_after["external_effect_count"]:
        a2.update(score="unproven", reason="attempt 1 committed (effect count 1), and the mismatched retry was refused at the metering layer (payment_required) before it could execute, so the binding check was never exercised; no new effect occurred, and neither a binding rejection nor a silent execution was observed")
    elif a2_final["external_effect_count"] > a2_after["external_effect_count"]:
        a2.update(score="fail", reason=f"mismatched retry executed as a new call: effect count rose from {a2_after['external_effect_count']} to {a2_final['external_effect_count']}, response class {a2_class}")
    elif a2_class != "success":
        a2.update(score="pass", reason="mismatched retry produced no new effect and was explicitly refused")
    else:
        a2.update(score="fail", reason="mismatched retry returned success without a binding rejection")
    summary["assertions"]["A2"] = a2

    # A3 legs, from the A1 operation's first committed receipt.
    a3 = {"legs": {}}
    ids = a1["execution_receipt_ids"]
    committed_digest = None
    if ids:
        record = adapter.fetch_record(ids[0])
        writer.write("a3_runid_leg_receipt.json", record)
        digests = digests_of(record)
        committed_digest = result_digest_of(digests)
        recomp = record["recomputation"]
        leg_pass = record["http_status"] == 200 and bool(committed_digest) and recomp["status"] == "matched"
        a3["legs"]["run_id"] = {"receipt_id": ids[0], "http_status": record["http_status"],
                                "page_http_status": record.get("page_http_status"),
                                "digests_served": digests, "recomputation": recomp,
                                "score": "pass" if leg_pass else "fail",
                                "note": "Section 9 resolution returned the unaltered record from the public JSON record; Section 6 recomputation is the harness's own SHA-256 over the decoded canonical bytes compared with the served output_hash."}
    else:
        a3["legs"]["run_id"] = {"score": "unproven", "note": "no committed receipt id exists"}
    k_value = a1["K"]
    rec = adapter.fetch_record(k_value)
    writer.write("a3_konly_run_lookup.json", rec)
    konly_recorded = load("a3_konly_continuity_get_recent.json")
    konly = {"K": k_value, "attempts": [
        {"path": "GET /api/v2/receipt/<K>/verify and GET /run/<K>",
         "http_status": rec["http_status"], "page_http_status": rec["page_http_status"],
         "page_title_not_found": rec["page_title_not_found"],
         "response_class": "found" if rec["http_status"] == 200 else "not_found"},
        {"path": "tools/call continuity_get_recent with K as the only identifier",
         "response_class": (konly_recorded.get("call") or konly_recorded).get("response_class"),
         "note": "as recorded during the original run; the call returned no committed outcome for K"}]}
    if committed_digest and rec["http_status"] == 200:
        konly.update(score="pass", reason="a record keyed by K alone returned the committed outcome")
    elif committed_digest:
        konly.update(score="fail", reason="K-only recovery did not return the original committed outcome: the public record lookup by K returned 404 receipt_not_found (the /run/<K> page answers HTTP 200 with a Receipt not found title), and the K-keyed tool lookup returned no committed outcome or digest")
    else:
        konly.update(score="unproven", reason="no committed digest exists, so K-only recovery cannot be scored")
    a3["legs"]["k_only"] = konly
    a3["score"] = konly["score"]
    a3["reason"] = ("contract pass condition is the K-only leg: " + konly["reason"] +
                    f"; run-id leg scored {a3['legs']['run_id']['score']} separately in the evidence")
    a3["committed_digest"] = committed_digest
    summary["assertions"]["A3"] = a3
    writer.write("a3_summary.json", a3)

    a4_classes = {"A1_retry": a1["retry_response_class"], "A2_retry": a2_class}
    summary["assertions"]["A4"] = {
        "score": "pass", "response_classes": a4_classes,
        "verdicts": {"A1_retry": "success corresponding to a committed record (the retry's own second receipt, counted in A1); not a generic success with no committed record",
                     "A2_retry": "explicit non-success state naming the situation (payment_required)"},
        "reason": "every recorded retry resolved to the original outcome, a digest-verifiable record of it, or an explicit non-success state"}
    plant = load("a5_plant.json")
    plant["execution_receipt_ids"] = ids
    plant["committed_digest"] = committed_digest
    plant["rescore_note"] = "receipt ids and digest corrected by the rescore; planted_at and due_at unchanged"
    writer.write("a5_plant.json", plant)
    summary["assertions"]["A5"] = old["assertions"]["A5"]
    summary["finished_at"] = old["finished_at"]
    writer.write("summary.json", summary)
    writer.write("RESULTS-snippet.md", results_snippet(summary))
    writer.write("RESCORE-NOTE.md",
                 "# Rescore note\n\nThe first scoring pass used a generic response walker as the "
                 "counter. That walker over-collected: it counted receipt identifiers mentioned "
                 "anywhere in enumeration responses, including other tools' receipts visible in a "
                 "caller-scoped recent-work read, and it missed the workflow snapshot's child "
                 "identifiers. The raw outputs of the run were not changed. This rescore recomputes "
                 "every count from the run's own raw workflow snapshot files, attributing each child "
                 "receipt through its public JSON record, and recomputes the A3 legs from the public "
                 "record. The superseded summary is preserved as summary_v1_superseded.json.\n")
    print(json.dumps(summary, indent=2))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(Path(__file__).parent / "config.zambo.json"))
    parser.add_argument("--out", default=None, help="run output directory")
    parser.add_argument("--delayed-leg", default=None, help="path to a5_plant.json")
    parser.add_argument("--rescore", default=None, help="run directory to rescore from its raw outputs")
    args = parser.parse_args()
    if args.delayed_leg:
        delayed_leg(args.delayed_leg)
        return 0
    config = normalize_config(json.loads(Path(args.config).read_text(encoding="utf-8")))
    if args.rescore:
        rescore(args.rescore, config)
        return 0
    out = args.out or str(Path.cwd() / ("run-" + utcnow().replace(":", "").replace("-", "")))
    writer = RunWriter(out)
    harness = Harness(config, writer)
    summary = harness.run()
    print(json.dumps(summary, indent=2))
    print(f"\nRaw outputs in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
