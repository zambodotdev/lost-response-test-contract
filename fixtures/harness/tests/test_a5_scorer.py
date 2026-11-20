#!/usr/bin/env python3
"""Regression tests for the pure A5 scorer (score_a5) and its wiring
into delayed_leg().

All observations are synthetic and recorded in the shapes the harness
itself writes: fetch_record() records carry "http_status", "digests"
and "fetched_at"; count_effects() evidence carries
"external_effect_count", "session_id" and "at"; retry records carry
"at", "session_id" and "K". No network is touched: delayed_leg() is
exercised against a fake adapter that only implements fetch_record()
and raises if anything tries to dispatch or count.

Run:
    python3 -m unittest discover -s fixtures/harness/tests -v
"""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import lost_response
from lost_response import delayed_leg, score_a5

COMMITTED = "sha256:" + "a" * 64
OTHER = "sha256:" + "b" * 64
PLANTED_AT = "2026-11-17T17:12:46Z"
DUE_AT = "2026-11-18T17:12:46Z"
AFTER_DUE = "2026-11-18T17:47:00Z"
AFTER_DUE_LATER = "2026-11-18T17:48:00Z"
BEFORE_DUE = "2026-11-17T18:00:00Z"
K = "lr-op-test-a1"
SESSION = "lr-test-a1"


def passing_observations():
    """A complete, timely, passing A5 observation set."""
    return {
        "committed_digest": COMMITTED,
        "due_at": DUE_AT,
        "planted_at": PLANTED_AT,
        "delay_hours": 24,
        "K": K,
        "session_id": SESSION,
        "observed_at": AFTER_DUE,
        "k_only": {
            "http_status": 200,
            "digests": {"output_hash": COMMITTED,
                        "input_hash": "sha256:" + "c" * 64},
            "fetched_at": AFTER_DUE,
            "recomputation": {"status": "matched"},
        },
        "run_id": {
            "http_status": 200,
            "digests": {"output_hash": COMMITTED},
            "fetched_at": AFTER_DUE,
            "recomputation": {"status": "matched"},
        },
        "protection": {
            "session_id": SESSION,
            "K": K,
            "counts_before": {
                "external_effect_count": 1,
                "execution_record_ids": ["receipt-1"],
                "session_id": SESSION,
                "at": AFTER_DUE,
                "label": "a5_delayed_before_protection",
            },
            "identical_retry": {
                "label": "a5_delayed_retry_identical",
                "at": AFTER_DUE,
                "session_id": SESSION,
                "K": K,
                "arguments_sent": {"action": "lost_response_probe",
                                   "job_id": K, "_session_id": SESSION},
                "call": {"response_class": "tool_error:idempotency_conflict",
                         "body": {"id": "req-identical-1"}},
            },
            "mismatched_retry": {
                "label": "a5_delayed_retry_mismatched",
                "at": AFTER_DUE,
                "session_id": SESSION,
                "K": K,
                "arguments_sent": {"action": "lost_response_probe_altered",
                                   "job_id": K, "_session_id": SESSION},
                "call": {"response_class": "tool_error:idempotency_conflict",
                         "body": {"id": "req-mismatched-1"}},
            },
            "counts_after": {
                "external_effect_count": 1,
                "execution_record_ids": ["receipt-1"],
                "session_id": SESSION,
                "at": AFTER_DUE_LATER,
                "label": "a5_delayed_after_protection",
            },
        },
    }


class ScoreA5Tests(unittest.TestCase):

    def test_full_pass(self):
        verdict = score_a5(passing_observations())
        self.assertEqual(verdict["checks"]["recovery"]["score"], "pass")
        self.assertEqual(verdict["checks"]["retry_protection"]["score"], "pass")
        self.assertEqual(verdict["score"], "pass")
        # The checks are also exposed under their own names.
        self.assertEqual(verdict["recovery"]["score"], "pass")
        self.assertEqual(verdict["retry_protection"]["score"], "pass")
        self.assertEqual(
            verdict["retry_protection"]["effect_count_before"], 1)
        self.assertEqual(
            verdict["retry_protection"]["effect_count_final"], 1)

    def test_http_200_without_key_path_digest_is_unproven(self):
        obs = passing_observations()
        # The K-only path returns 200 but no digest. The run-id
        # diagnostic still matches; it must not rescue recovery.
        obs["k_only"] = {"http_status": 200, "digests": {},
                         "fetched_at": AFTER_DUE}
        verdict = score_a5(obs)
        recovery = verdict["checks"]["recovery"]
        self.assertEqual(recovery["score"], "unproven")
        self.assertIn("HTTP 200 alone is insufficient", recovery["reason"])
        self.assertTrue(recovery["run_id"]["run_id_digest_equal"])
        self.assertEqual(verdict["checks"]["retry_protection"]["score"], "pass")
        self.assertEqual(verdict["score"], "unproven")

    def test_mismatched_digest_fails_recovery(self):
        obs = passing_observations()
        obs["k_only"]["digests"] = {"output_hash": OTHER}
        verdict = score_a5(obs)
        recovery = verdict["checks"]["recovery"]
        self.assertEqual(recovery["score"], "fail")
        self.assertEqual(recovery["recovered_digest"], OTHER)
        self.assertEqual(verdict["checks"]["retry_protection"]["score"], "pass")
        self.assertEqual(verdict["score"], "fail")

    def test_k_only_not_found_fails_recovery(self):
        obs = passing_observations()
        obs["k_only"] = {"http_status": 404, "digests": {},
                         "fetched_at": AFTER_DUE}
        verdict = score_a5(obs)
        self.assertEqual(verdict["checks"]["recovery"]["score"], "fail")
        self.assertEqual(verdict["score"], "fail")

    def test_run_id_mismatch_is_diagnostic_only(self):
        obs = passing_observations()
        obs["run_id"]["digests"] = {"output_hash": OTHER}
        verdict = score_a5(obs)
        self.assertEqual(verdict["checks"]["recovery"]["score"], "pass")
        self.assertFalse(
            verdict["checks"]["recovery"]["run_id"]["run_id_digest_equal"])
        self.assertEqual(verdict["score"], "pass")

    def test_successful_recovery_with_rising_effect_count_fails(self):
        obs = passing_observations()
        obs["protection"]["counts_after"]["external_effect_count"] = 2
        obs["protection"]["counts_after"]["execution_record_ids"] = [
            "receipt-1", "receipt-2"]
        verdict = score_a5(obs)
        self.assertEqual(verdict["checks"]["recovery"]["score"], "pass")
        protection = verdict["checks"]["retry_protection"]
        self.assertEqual(protection["score"], "fail")
        self.assertIn("rose from 1 to 2", protection["reason"])
        self.assertEqual(verdict["score"], "fail")

    def test_missing_observations_are_unproven(self):
        verdict = score_a5({})
        self.assertEqual(verdict["checks"]["recovery"]["score"], "unproven")
        self.assertEqual(
            verdict["checks"]["retry_protection"]["score"], "unproven")
        self.assertEqual(verdict["score"], "unproven")

        # Recovery evidence present, protection evidence absent:
        # recovery can pass, A5 as a whole still cannot.
        obs = passing_observations()
        del obs["protection"]
        verdict = score_a5(obs)
        self.assertEqual(verdict["checks"]["recovery"]["score"], "pass")
        self.assertEqual(
            verdict["checks"]["retry_protection"]["score"], "unproven")
        self.assertEqual(verdict["score"], "unproven")

    def test_early_observations_are_unproven(self):
        obs = passing_observations()
        obs["k_only"]["fetched_at"] = BEFORE_DUE
        obs["protection"]["counts_before"]["at"] = BEFORE_DUE
        obs["protection"]["counts_after"]["at"] = BEFORE_DUE
        obs["protection"]["identical_retry"]["at"] = BEFORE_DUE
        obs["protection"]["mismatched_retry"]["at"] = BEFORE_DUE
        obs["observed_at"] = BEFORE_DUE
        verdict = score_a5(obs)
        self.assertEqual(verdict["checks"]["recovery"]["score"], "unproven")
        self.assertIn("early", verdict["checks"]["recovery"]["reason"])
        self.assertEqual(
            verdict["checks"]["retry_protection"]["score"], "unproven")
        self.assertIn("early",
                      verdict["checks"]["retry_protection"]["reason"])
        self.assertEqual(verdict["score"], "unproven")

    def test_incomparable_counts_are_unproven(self):
        obs = passing_observations()
        obs["protection"]["counts_after"]["session_id"] = "lr-other-a1"
        verdict = score_a5(obs)
        protection = verdict["checks"]["retry_protection"]
        self.assertEqual(protection["score"], "unproven")
        self.assertIn("incomparable", protection["reason"])
        self.assertEqual(verdict["score"], "unproven")

    def test_missing_retry_record_is_unproven(self):
        obs = passing_observations()
        del obs["protection"]["mismatched_retry"]
        verdict = score_a5(obs)
        self.assertEqual(
            verdict["checks"]["retry_protection"]["score"], "unproven")
        self.assertEqual(verdict["score"], "unproven")

    def test_scorer_is_pure_and_does_not_mutate_input(self):
        obs = passing_observations()
        snapshot = copy.deepcopy(obs)
        score_a5(obs)
        self.assertEqual(obs, snapshot)


class ScoreA5ReviewCaseTests(unittest.TestCase):
    """The three review cases added after the first patch round:
    stale evidence, evidence for both retries, and recomputation."""

    # -- Case 1: stale evidence ------------------------------------
    def test_stale_retries_with_fresh_final_count_are_unproven(self):
        # Retries and the before count are from before due_at (e.g. a
        # plant-time short-range battery); only the final count is
        # fresh. A scorer run after due_at must not pass this.
        obs = passing_observations()
        obs["protection"]["counts_before"]["at"] = BEFORE_DUE
        obs["protection"]["identical_retry"]["at"] = BEFORE_DUE
        obs["protection"]["mismatched_retry"]["at"] = BEFORE_DUE
        obs["observed_at"] = AFTER_DUE_LATER  # re-run time: irrelevant
        verdict = score_a5(obs)
        protection = verdict["checks"]["retry_protection"]
        self.assertEqual(protection["score"], "unproven")
        self.assertIn("stale", protection["reason"])
        self.assertEqual(verdict["checks"]["recovery"]["score"], "pass")
        self.assertEqual(verdict["score"], "unproven")

    def test_untimestamped_protection_files_are_unproven_on_rerun(self):
        # Counts as bare ints and retries with no timestamps of their
        # own: the re-run's own time must not be substituted.
        obs = passing_observations()
        obs["protection"]["counts_before"] = 1
        obs["protection"]["counts_after"] = 1
        del obs["protection"]["identical_retry"]["at"]
        del obs["protection"]["mismatched_retry"]["at"]
        obs["observed_at"] = AFTER_DUE_LATER
        verdict = score_a5(obs)
        self.assertEqual(
            verdict["checks"]["retry_protection"]["score"], "unproven")
        self.assertEqual(verdict["score"], "unproven")

    def test_counts_must_bracket_both_attempts(self):
        # Before count recorded after both retries: not a bracket.
        obs = passing_observations()
        obs["protection"]["counts_before"]["at"] = "2026-11-18T17:49:00Z"
        obs["protection"]["counts_after"]["at"] = "2026-11-18T17:50:00Z"
        verdict = score_a5(obs)
        protection = verdict["checks"]["retry_protection"]
        self.assertEqual(protection["score"], "unproven")
        self.assertIn("do not bracket", protection["reason"])

        # Final count recorded before the changed-argument retry ran.
        obs = passing_observations()
        obs["protection"]["mismatched_retry"]["at"] = AFTER_DUE_LATER
        obs["protection"]["counts_after"]["at"] = AFTER_DUE
        verdict = score_a5(obs)
        protection = verdict["checks"]["retry_protection"]
        self.assertEqual(protection["score"], "unproven")
        self.assertIn("do not bracket", protection["reason"])

    # -- Case 2: evidence for both retries --------------------------
    def test_retry_blocked_before_retry_logic_is_unproven(self):
        # payment_required is a metering-layer refusal before any
        # commit: the binding/retry logic was never exercised (the
        # harness's A2 rule), even though the count is unchanged.
        for which in ("identical_retry", "mismatched_retry"):
            obs = passing_observations()
            obs["protection"][which]["call"]["response_class"] = (
                "payment_required")
            verdict = score_a5(obs)
            protection = verdict["checks"]["retry_protection"]
            self.assertEqual(protection["score"], "unproven", which)
            self.assertIn("payment_required", protection["reason"])
            self.assertEqual(verdict["score"], "unproven", which)

    def test_dropped_retry_is_unproven(self):
        obs = passing_observations()
        obs["protection"]["identical_retry"]["call"] = {"dropped": True}
        verdict = score_a5(obs)
        self.assertEqual(
            verdict["checks"]["retry_protection"]["score"], "unproven")

    def test_both_files_recording_the_same_attempt_are_unproven(self):
        # The mismatched file is a copy of the identical file.
        obs = passing_observations()
        obs["protection"]["mismatched_retry"] = copy.deepcopy(
            obs["protection"]["identical_retry"])
        verdict = score_a5(obs)
        protection = verdict["checks"]["retry_protection"]
        self.assertEqual(protection["score"], "unproven")
        self.assertIn("same attempt", protection["reason"])

        # Distinct labels, but identical arguments and the same
        # transport request id: still the same attempt, and no
        # changed-argument attempt is evidenced.
        obs = passing_observations()
        obs["protection"]["mismatched_retry"]["arguments_sent"] = (
            copy.deepcopy(
                obs["protection"]["identical_retry"]["arguments_sent"]))
        obs["protection"]["mismatched_retry"]["call"]["body"]["id"] = (
            obs["protection"]["identical_retry"]["call"]["body"]["id"])
        verdict = score_a5(obs)
        self.assertEqual(
            verdict["checks"]["retry_protection"]["score"], "unproven")

    # -- Receipt identity and the configured argument change --------
    def test_new_receipt_at_unchanged_count_fails_protection(self):
        obs = passing_observations()
        obs["protection"]["counts_after"]["execution_record_ids"] = [
            "receipt-2"]
        verdict = score_a5(obs)
        protection = verdict["checks"]["retry_protection"]
        self.assertEqual(protection["score"], "fail")
        self.assertIn("new execution receipt", protection["reason"])
        self.assertEqual(verdict["score"], "fail")

    def test_original_receipt_missing_from_before_count_is_unproven(self):
        obs = passing_observations()
        obs["execution_receipt_ids"] = ["receipt-original"]
        verdict = score_a5(obs)
        protection = verdict["checks"]["retry_protection"]
        self.assertEqual(protection["score"], "unproven")
        self.assertIn("not present in the before count",
                      protection["reason"])

    def test_changed_argument_must_change_exactly_the_configured_field(self):
        # Two fields changed: not the single-parameter change.
        obs = passing_observations()
        obs["protection"]["mismatched_retry"]["arguments_sent"][
            "executor_identity"] = "someone-else"
        verdict = score_a5(obs)
        self.assertEqual(
            verdict["checks"]["retry_protection"]["score"], "unproven")

        # Exactly one field, but not the configured mismatch field.
        obs = passing_observations()
        obs["plant"] = {"adapter_config": {
            "mismatch": {"field": "action",
                         "altered_value": "lost_response_probe_altered"}}}
        obs["protection"]["mismatched_retry"]["arguments_sent"] = dict(
            obs["protection"]["identical_retry"]["arguments_sent"],
            executor_identity="someone-else")
        verdict = score_a5(obs)
        protection = verdict["checks"]["retry_protection"]
        self.assertEqual(protection["score"], "unproven")
        self.assertIn("configured mismatch field", protection["reason"])

    # -- Case 3: matching digest, failed recomputation --------------
    def test_matching_digest_with_mismatched_recomputation_fails(self):
        obs = passing_observations()
        obs["k_only"]["recomputation"] = {"status": "mismatched"}
        verdict = score_a5(obs)
        recovery = verdict["checks"]["recovery"]
        self.assertEqual(recovery["score"], "fail")
        self.assertIn("recomput", recovery["reason"])
        self.assertEqual(recovery["recovered_digest"], COMMITTED)
        self.assertEqual(verdict["score"], "fail")

    def test_not_computable_recomputation_does_not_fail_recovery(self):
        obs = passing_observations()
        obs["k_only"]["recomputation"] = {"status": "not_computable"}
        verdict = score_a5(obs)
        self.assertEqual(verdict["checks"]["recovery"]["score"], "pass")


class FakeAdapter:
    """Only fetch_record exists. Any dispatch or counting attempt
    raises AttributeError, proving delayed_leg adds neither."""

    def __init__(self, records):
        self.records = records
        self.fetched = []

    def fetch_record(self, record_id):
        self.fetched.append(record_id)
        return self.records[record_id]


def _record(digest, fetched_at=AFTER_DUE, http_status=200):
    return {"http_status": http_status,
            "digests": {"output_hash": digest} if digest else {},
            "digests_found": {"output_hash": digest} if digest else {},
            "fetched_at": fetched_at,
            "recomputation": {"status": "matched"}}


def _plant():
    return {"assertion": "A5", "K": K, "session_id": SESSION,
            "committed_digest": COMMITTED, "delay_hours": 24,
            "planted_at": PLANTED_AT, "due_at": DUE_AT,
            "execution_receipt_ids": ["receipt-1"],
            "adapter": "fake", "adapter_config": {}}


class DelayedLegWiringTests(unittest.TestCase):

    def _run_delayed_leg(self, tmp, adapter, extra_files=None):
        plant = _plant()
        (Path(tmp) / "a5_plant.json").write_text(
            json.dumps(plant), encoding="utf-8")
        for name, obj in (extra_files or {}).items():
            (Path(tmp) / name).write_text(json.dumps(obj), encoding="utf-8")
        with mock.patch.object(lost_response, "load_adapter",
                               return_value=adapter):
            return delayed_leg(str(Path(tmp) / "a5_plant.json"))

    def test_delayed_leg_scores_recovery_and_uses_recorded_protection(self):
        obs = passing_observations()
        adapter = FakeAdapter({"receipt-1": _record(COMMITTED),
                               K: _record(COMMITTED)})
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run_delayed_leg(tmp, adapter, {
                "count_a5_delayed_before_protection.json":
                    obs["protection"]["counts_before"],
                "count_a5_delayed_final.json":
                    obs["protection"]["counts_after"],
                "a5_delayed_retry_identical.json":
                    obs["protection"]["identical_retry"],
                "a5_delayed_retry_mismatched.json":
                    obs["protection"]["mismatched_retry"],
            })
            written = json.loads(
                (Path(tmp) / "a5_delayed_result.json").read_text(
                    encoding="utf-8"))
        self.assertEqual(result["score"], "pass")
        self.assertEqual(result["checks"]["recovery"]["score"], "pass")
        self.assertEqual(
            result["checks"]["retry_protection"]["score"], "pass")
        self.assertEqual(written["score"], "pass")
        # Exactly the two pre-existing reads, in order: run-id, then K.
        self.assertEqual(adapter.fetched, ["receipt-1", K])
        # The K-only record as fetched is now part of the report.
        self.assertEqual(
            result["legs"]["k_only_direct_lookup"]["recovered_digest"],
            COMMITTED)
        self.assertTrue(
            result["legs"]["k_only_direct_lookup"]["digest_equal"])

    def test_delayed_leg_without_recorded_protection_is_unproven(self):
        adapter = FakeAdapter({"receipt-1": _record(COMMITTED),
                               K: _record(COMMITTED)})
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run_delayed_leg(tmp, adapter)
        self.assertEqual(result["checks"]["recovery"]["score"], "pass")
        self.assertEqual(
            result["checks"]["retry_protection"]["score"], "unproven")
        self.assertEqual(result["score"], "unproven")
        self.assertEqual(adapter.fetched, ["receipt-1", K])

    def test_delayed_leg_rerun_does_not_refresh_stale_protection_files(self):
        # Protection files on disk are all timestamped before due_at
        # (a plant-time battery). The leg itself runs now (after
        # due_at, with fresh K/run-id fetches); the stale files must
        # not qualify for a pass.
        obs = passing_observations()
        stale_before = dict(obs["protection"]["counts_before"],
                            at=BEFORE_DUE)
        stale_final = dict(obs["protection"]["counts_after"],
                           at=BEFORE_DUE)
        stale_ident = dict(obs["protection"]["identical_retry"],
                           at=BEFORE_DUE)
        stale_mism = dict(obs["protection"]["mismatched_retry"],
                          at=BEFORE_DUE)
        adapter = FakeAdapter({"receipt-1": _record(COMMITTED),
                               K: _record(COMMITTED)})
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run_delayed_leg(tmp, adapter, {
                "count_a5_delayed_before_protection.json": stale_before,
                "count_a5_delayed_final.json": stale_final,
                "a5_delayed_retry_identical.json": stale_ident,
                "a5_delayed_retry_mismatched.json": stale_mism,
            })
        self.assertEqual(result["checks"]["recovery"]["score"], "pass")
        self.assertEqual(
            result["checks"]["retry_protection"]["score"], "unproven")
        self.assertEqual(result["score"], "unproven")
        self.assertEqual(adapter.fetched, ["receipt-1", K])

    def test_delayed_leg_matching_digest_failed_recomputation_fails(self):
        k_record = _record(COMMITTED)
        k_record["recomputation"] = {"status": "mismatched"}
        adapter = FakeAdapter({"receipt-1": _record(COMMITTED),
                               K: k_record})
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run_delayed_leg(tmp, adapter)
        self.assertEqual(result["checks"]["recovery"]["score"], "fail")
        self.assertEqual(result["score"], "fail")

    def test_delayed_leg_200_without_digest_is_unproven_despite_run_id(self):
        adapter = FakeAdapter({"receipt-1": _record(COMMITTED),
                               K: _record(None)})
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run_delayed_leg(tmp, adapter)
        self.assertEqual(result["checks"]["recovery"]["score"], "unproven")
        self.assertEqual(result["score"], "unproven")
        self.assertTrue(result["legs"]["run_id"]["digest_equal"])
        self.assertFalse(
            result["legs"]["k_only_direct_lookup"]["digest_equal"])


class ScoreA5StaticReviewTests(unittest.TestCase):
    """Regressions for the static review of the staged diff: four
    paths where the scorer could reach a verdict without the
    evidence that verdict requires."""

    # Finding 1: retry identity and arguments.
    def test_retry_scope_arguments_and_configured_value(self):
        # A retry recorded under a different K is not a retry of
        # this operation, even with unchanged counts.
        obs = passing_observations()
        obs["protection"]["mismatched_retry"]["K"] = "lr-op-other"
        verdict = score_a5(obs)
        self.assertEqual(
            verdict["checks"]["retry_protection"]["score"], "unproven")

        # A retry recorded under a different session likewise.
        obs = passing_observations()
        obs["protection"]["identical_retry"]["session_id"] = "lr-other"
        verdict = score_a5(obs)
        self.assertEqual(
            verdict["checks"]["retry_protection"]["score"], "unproven")

        # The changed value must be the configured replacement
        # value, not just any change to the configured field.
        obs = passing_observations()
        obs["plant"] = {"adapter_config": {"mismatch": {
            "field": "action",
            "altered_value": "lost_response_probe_altered"}}}
        obs["protection"]["mismatched_retry"]["arguments_sent"][
            "action"] = "some_other_action"
        verdict = score_a5(obs)
        protection = verdict["checks"]["retry_protection"]
        self.assertEqual(protection["score"], "unproven")
        self.assertIn("configured replacement value",
                      protection["reason"])

        # The identical retry must match the original arguments
        # where those are recorded.
        obs = passing_observations()
        original = dict(
            obs["protection"]["identical_retry"]["arguments_sent"],
            executor_identity="someone-else")
        obs["original_arguments"] = original
        verdict = score_a5(obs)
        protection = verdict["checks"]["retry_protection"]
        self.assertEqual(protection["score"], "unproven")
        self.assertIn("original arguments as recorded",
                      protection["reason"])

        # Labels alone leave the argument check unproven.
        obs = passing_observations()
        for rec in (obs["protection"]["identical_retry"],
                    obs["protection"]["mismatched_retry"]):
            del rec["arguments_sent"]
        verdict = score_a5(obs)
        protection = verdict["checks"]["retry_protection"]
        self.assertEqual(protection["score"], "unproven")
        self.assertIn("labels alone", protection["reason"])

    # Finding 2: effect attribution before any fail.
    def test_rise_is_not_fail_until_attribution_and_bracketing_hold(self):
        # Rising count, but the planted original receipt was never
        # counted: the increase cannot be attributed to the retries.
        obs = passing_observations()
        obs["execution_receipt_ids"] = ["receipt-original"]
        obs["protection"]["counts_after"]["external_effect_count"] = 2
        obs["protection"]["counts_after"]["execution_record_ids"] = [
            "receipt-1", "receipt-2"]
        verdict = score_a5(obs)
        protection = verdict["checks"]["retry_protection"]
        self.assertEqual(protection["score"], "unproven")
        self.assertIn("attribution to this operation is not "
                      "established", protection["reason"])

        # Rising count, but the final count predates the retries:
        # no bracketing, so the increase is not evidence against
        # them either.
        obs = passing_observations()
        obs["protection"]["counts_after"]["external_effect_count"] = 2
        obs["protection"]["counts_after"]["execution_record_ids"] = [
            "receipt-1", "receipt-2"]
        obs["protection"]["counts_after"]["at"] = BEFORE_DUE
        verdict = score_a5(obs)
        protection = verdict["checks"]["retry_protection"]
        self.assertEqual(protection["score"], "unproven")
        self.assertIn("do not bracket", protection["reason"])

    # Finding 3: missing deadline.
    def test_missing_deadline_keeps_both_checks_unproven(self):
        obs = passing_observations()
        for key in ("due_at", "planted_at", "delay_hours"):
            obs.pop(key, None)
        verdict = score_a5(obs)
        self.assertEqual(verdict["checks"]["recovery"]["score"],
                         "unproven")
        self.assertIn("deadline (due_at) is missing",
                      verdict["checks"]["recovery"]["reason"])
        self.assertEqual(
            verdict["checks"]["retry_protection"]["score"], "unproven")
        self.assertIn("deadline (due_at) is missing",
                      verdict["checks"]["retry_protection"]["reason"])
        self.assertEqual(verdict["score"], "unproven")

    # Finding 4: recovery response coherence.
    def test_recovery_requires_successful_same_response(self):
        # Matching digest served on an HTTP error: no pass.
        obs = passing_observations()
        obs["k_only"]["http_status"] = 500
        verdict = score_a5(obs)
        recovery = verdict["checks"]["recovery"]
        self.assertEqual(recovery["score"], "unproven")
        self.assertIn("not a successful lookup", recovery["reason"])

        # Digest, timestamp and recomputation all come from the
        # response that served the digest — here an attempt that
        # ran before the deadline, under a wrapper stamped after
        # it: the attempt's own early time decides.
        obs = passing_observations()
        obs["k_only"] = {
            "http_status": 200,
            "fetched_at": AFTER_DUE_LATER,
            "recomputation": {"status": "matched"},
            "attempts": [{
                "response_class": "found",
                "digests": {"output_hash": COMMITTED},
                "fetched_at": BEFORE_DUE,
                "recomputation": {"status": "matched"},
            }],
        }
        verdict = score_a5(obs)
        recovery = verdict["checks"]["recovery"]
        self.assertEqual(recovery["score"], "unproven")
        self.assertIn("early", recovery["reason"])

        # Same shape, timely attempt, but the attempt's own
        # recomputation mismatched while the wrapper's matched:
        # the serving response's verdict decides — fail.
        obs["k_only"]["attempts"][0]["fetched_at"] = AFTER_DUE
        obs["k_only"]["attempts"][0]["recomputation"] = {
            "status": "mismatched"}
        verdict = score_a5(obs)
        recovery = verdict["checks"]["recovery"]
        self.assertEqual(recovery["score"], "fail")
        self.assertIn("recomputing", recovery["reason"])


class ScoreA5ScopeAndErrorResponseTests(unittest.TestCase):
    """Regressions for the second static review of the staged diff."""

    # Unattributed retry evidence: the retry record itself carries
    # no scope, and scope on the protection wrapper (as delayed_leg
    # used to stamp it) does not transfer to the record.
    def test_unattributed_retry_evidence_is_unproven(self):
        obs = passing_observations()
        retry = obs["protection"]["identical_retry"]
        del retry["session_id"]
        del retry["K"]
        # The wrapper still claims the plant's scope; that must not
        # rescue the record.
        self.assertEqual(obs["protection"]["session_id"], SESSION)
        verdict = score_a5(obs)
        protection = verdict["checks"]["retry_protection"]
        self.assertEqual(protection["score"], "unproven")
        self.assertIn("not established by the record itself",
                      protection["reason"])
        self.assertEqual(verdict["score"], "unproven")

        # Same gap on a count, with a rise that would otherwise be
        # attributed to the retries: still unproven, not fail.
        obs = passing_observations()
        del obs["protection"]["counts_after"]["session_id"]
        obs["protection"]["counts_after"]["external_effect_count"] = 2
        obs["protection"]["counts_after"]["execution_record_ids"] = [
            "receipt-1", "receipt-2"]
        verdict = score_a5(obs)
        protection = verdict["checks"]["retry_protection"]
        self.assertEqual(protection["score"], "unproven")
        self.assertIn("attribution", protection["reason"])

    # An error response's digest is not evidence, matching or not:
    # HTTP 500 carrying a DIFFERENT digest is unproven, not fail.
    # (A genuine not-found remains a fail — covered by
    # test_konly_not_found_fails.)
    def test_http_500_with_different_digest_is_unproven(self):
        obs = passing_observations()
        obs["k_only"]["http_status"] = 500
        obs["k_only"]["digests"] = {"output_hash": "sha256:" + "b" * 64}
        verdict = score_a5(obs)
        recovery = verdict["checks"]["recovery"]
        self.assertEqual(recovery["score"], "unproven")
        self.assertIn("not a successful lookup", recovery["reason"])
        self.assertEqual(verdict["score"], "unproven")


if __name__ == "__main__":
    unittest.main()
