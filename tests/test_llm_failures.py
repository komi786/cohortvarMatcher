"""LLM failures must never read as the LLM rejecting a pair (issue 3a-3f).

Real cases: in the article run biolord+gemini-3.1-flash-lite_ng/OEH, 14 pairs
got no LLM answer and were saved as "LLM rejected pair: pending_after_assess_retries",
including Aachen-HF Nierenerkrankungen -> ckd (GT partial) and ViennaHF Lc ->
leukozyten (GT compatible).

Run from the repository root:  python -m unittest tests.test_llm_failures
"""
import json
import logging
import unittest
from unittest import mock

# Keep test runs from creating llm_logs.log: setup_logger() leaves a logger
# that already has a handler alone. Must run before src.llm_call is imported.
logging.getLogger("cohortvarlinker.llm_logs").addHandler(logging.NullHandler())

from src.data_model import ContextMatchType, MappingType, MatchLevel, TransformationType
from src.llm_call import (
    CircuitBreaker, LLMCallError, LLMConceptMatcher, LLMUnavailableError,
    _parse_single, classify_call_error,
)
from src.policy import decide
from src.verdict import (
    LLM_NOT_REACHED, LLM_OK, LLM_SKIPPED, LLM_UNREADABLE,
    LLMEvidence, StructuralEvidence, TimepointInfo, llm_evidence_from_tuple,
)

TP = TimepointInfo(aligned=True, status="aligned")
MODES = (MappingType.OEH.value, MappingType.NE.value)
VALID = json.dumps({"status_code": 3, "status": "PARTIAL", "confidence": 0.8, "reason": "r",
                    "transform": "", "harmonized_variable": "x", "alignment_direction": ""})


def http_error(status, name="APIStatusError"):
    cls = type(name, (Exception,), {})
    e = cls(f"HTTP {status}")
    e.status_code = status
    return e


# ── 3c: parser ──────────────────────────────────────────────────────────────

class Parser(unittest.TestCase):

    def verdict(self, payload):
        return _parse_single(json.dumps(payload) if not isinstance(payload, str) else payload)

    def test_full_answer_unchanged(self):
        matched, ctx, conf, reason = self.verdict(VALID)
        self.assertTrue(matched)
        self.assertEqual(ctx, ContextMatchType.PARTIAL.value)
        self.assertEqual(conf, 0.8)
        self.assertTrue(json.loads(reason)["confidence_reported"])

    def test_only_the_verdict_is_required(self):
        matched, ctx, _, _ = self.verdict({"status": "PARTIAL"})
        self.assertTrue(matched)
        self.assertEqual(ctx, ContextMatchType.PARTIAL.value)
        self.assertEqual(self.verdict({"status_code": 2})[1], ContextMatchType.COMPATIBLE.value)
        self.assertEqual(self.verdict({"status_code": "3.0"})[1], ContextMatchType.PARTIAL.value)
        self.assertEqual(self.verdict({"status": "partial"})[1], ContextMatchType.PARTIAL.value)

    def test_non_numeric_confidence_does_not_discard_the_verdict(self):
        matched, ctx, conf, reason = self.verdict({"status_code": 3, "status": "PARTIAL", "confidence": "high"})
        self.assertTrue(matched)
        self.assertEqual(conf, 0.0)
        self.assertFalse(json.loads(reason)["confidence_reported"])

    def test_unusable_answers(self):
        for payload, cause in [
            ({"status_code": 1, "status": "PARTIAL"}, "status_conflict"),
            ({"status": "MAYBE"}, "invalid_status"),
            ({"status_code": 7}, "invalid_status_code"),
            ({"reason": "no verdict"}, "missing_status"),
            ("[1, 2]", "json_not_an_object"),
            ("not json", "json_parse_fail"),
            ("", "empty_response"),
        ]:
            with self.subTest(cause=cause):
                matched, ctx, _, why = self.verdict(payload)
                self.assertIsNone(matched)
                self.assertEqual(ctx, ContextMatchType.PENDING.value)
                self.assertTrue(str(why).startswith(cause), why)


# ── 3a: error classification ────────────────────────────────────────────────

class ErrorClassification(unittest.TestCase):

    def test_http_statuses(self):
        for status, kind, retryable in [
            (401, "authentication", False), (403, "authentication", False),
            (404, "model_not_found", False), (400, "bad_request", False),
            (429, "rate_limit", True), (408, "timeout", True),
            (500, "server_error", True), (503, "server_error", True),
        ]:
            with self.subTest(status=status):
                e = classify_call_error(http_error(status))
                self.assertEqual((e.kind, e.retryable), (kind, retryable))

    def test_status_on_response_or_code_attribute(self):
        e = Exception("x")
        e.response = type("R", (), {"status_code": 429})()
        self.assertEqual(classify_call_error(e).kind, "rate_limit")
        g = Exception("quota")
        g.code = 429                               # google-genai style
        self.assertEqual(classify_call_error(g).kind, "rate_limit")

    def test_by_exception_name(self):
        for name, kind in [("APITimeoutError", "timeout"), ("ReadTimeout", "timeout"),
                           ("APIConnectionError", "connection"), ("RateLimitError", "rate_limit"),
                           ("AuthenticationError", "authentication"), ("NotFoundError", "model_not_found"),
                           ("ServiceUnavailableError", "server_error")]:
            with self.subTest(name=name):
                self.assertEqual(classify_call_error(type(name, (Exception,), {})("x")).kind, kind)

    def test_unknown_errors_are_retryable_and_named(self):
        e = classify_call_error(KeyError("choices"))
        self.assertEqual((e.kind, e.retryable), ("unknown_error", True))
        self.assertIn("KeyError", e.detail)


# ── 3b: circuit breaker ─────────────────────────────────────────────────────

class FakeClock:
    def __init__(self):
        self.now, self.slept = 0.0, []

    def __call__(self):
        return self.now

    def sleep(self, s):
        self.slept.append(s)
        self.now += s


class Breaker(unittest.TestCase):

    def make(self):
        clock = FakeClock()
        return CircuitBreaker(threshold=5, cooldown_s=30, max_cooldowns=3, clock=clock, sleep=clock.sleep), clock

    def test_opens_after_threshold_and_pauses(self):
        b, clock = self.make()
        for _ in range(4):
            b.record_failure()
        b.before_call()
        self.assertEqual(clock.slept, [])          # 4 failures: no pause yet
        b.record_failure()
        b.before_call()
        self.assertEqual(clock.slept, [30])        # 5th failure: pause 30 s

    def test_success_resets(self):
        b, clock = self.make()
        for _ in range(4):
            b.record_failure()
        b.record_success()
        for _ in range(4):
            b.record_failure()
        b.before_call()
        self.assertEqual(clock.slept, [])

    def test_failure_after_cooldown_reopens_then_gives_up(self):
        b, clock = self.make()
        for _ in range(5):
            b.record_failure()                     # cooldown 1
        for _ in range(3):
            b.before_call()                        # wait out the cooldown
            b.record_failure()                     # first failure after it reopens
        self.assertEqual(clock.slept, [30, 30, 30])
        self.assertTrue(b.gave_up)
        with self.assertRaises(LLMCallError) as ctx:
            b.before_call()
        self.assertEqual(ctx.exception.kind, "circuit_open")

    def test_in_flight_failures_do_not_count_twice(self):
        b, clock = self.make()
        for _ in range(5):
            b.record_failure()
        for _ in range(10):
            b.record_failure()                     # other threads, same burst
        self.assertFalse(b.gave_up)


# ── 3a/3b/3d: _eval_pair ────────────────────────────────────────────────────

class FakeCache:
    def __init__(self):
        self.stored = []

    def get_record(self, *a, **k):
        return None

    def put_record(self, model, prompt, text, **k):
        self.stored.append(text)


def make_matcher(script, breaker=None):
    """LLMConceptMatcher whose calls follow `script` (exceptions or reply texts)."""
    with mock.patch.object(LLMConceptMatcher, "__post_init__", lambda self: None):
        m = LLMConceptMatcher(models=["test-model"])
    clock = FakeClock()
    m._breaker = breaker or CircuitBreaker(clock=clock, sleep=clock.sleep)
    m._cache = FakeCache()
    m._system_prompt = ""
    m.calls = []
    replies = iter(script)

    def call_one(model, prompt, force_freeform=False):
        m.calls.append(force_freeform)
        item = next(replies)
        if isinstance(item, BaseException):
            raise classify_call_error(item)
        return item, {}

    m._call_one = call_one
    return m


class EvalPair(unittest.TestCase):

    def setUp(self):
        patcher = mock.patch("src.llm_call.time.sleep")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_rate_limited_every_time_is_not_reached(self):
        m = make_matcher([http_error(429)] * 5)
        matched, ctx, _, reason = m._eval_pair("test-model", "p")
        self.assertIsNone(matched)
        d = json.loads(reason)
        self.assertEqual(d["status"], "NOT_REACHED")
        self.assertTrue(d["reason"].startswith("LLM not reached after 5 attempts (rate_limit"), d["reason"])
        self.assertEqual(len(m.calls), 5)

    def test_transient_error_then_answer(self):
        m = make_matcher([http_error(503), VALID])
        matched, ctx, _, _ = m._eval_pair("test-model", "p")
        self.assertTrue(matched)
        self.assertEqual(m._cache.stored, [VALID])

    def test_authentication_error_stops_the_run(self):
        m = make_matcher([http_error(401), VALID])
        with self.assertRaises(LLMUnavailableError) as ctx:
            m._eval_pair("test-model", "p")
        self.assertIn("authentication", str(ctx.exception))
        self.assertEqual(len(m.calls), 1)

    def test_rejected_json_mode_retries_free_form(self):
        m = make_matcher([http_error(400), VALID])
        self.assertTrue(m._eval_pair("test-model", "p")[0])
        self.assertEqual(m.calls, [False, True])

    def test_rejected_in_free_form_too_stops_the_run(self):
        m = make_matcher([http_error(400), http_error(400)])
        with self.assertRaises(LLMUnavailableError):
            m._eval_pair("test-model", "p")

    def test_unreadable_answers(self):
        m = make_matcher(["not json", "not json", "not json"])
        d = json.loads(m._eval_pair("test-model", "p")[3])
        self.assertEqual(d["status"], "UNREADABLE")
        self.assertEqual(d["reason"], "LLM answer unreadable after 3 attempts (json_parse_fail)")
        self.assertEqual(m.calls, [False, False, True])     # last try free-form

    def test_breaker_that_gave_up_blocks_without_calling(self):
        b = CircuitBreaker()
        b.give_up()
        m = make_matcher([VALID], breaker=b)
        d = json.loads(m._eval_pair("test-model", "p")[3])
        self.assertEqual(d["status"], "NOT_REACHED")
        self.assertEqual(d["reason"], "LLM not reached (calls stopped after repeated API failures)")
        self.assertEqual(m.calls, [])

    def test_breaker_pauses_between_pairs(self):
        clock = FakeClock()
        b = CircuitBreaker(threshold=5, cooldown_s=30, clock=clock, sleep=clock.sleep)
        m = make_matcher([http_error(429)] * 5 + [VALID], breaker=b)
        m._eval_pair("test-model", "p1")                       # 5 failures open the breaker
        self.assertTrue(m._eval_pair("test-model", "p2")[0])   # waits, then succeeds
        self.assertEqual(clock.slept, [30])


# ── 3b/3f: assess ───────────────────────────────────────────────────────────

class Assess(unittest.TestCase):
    GROUPS = [{"src_desc": "a", "targets": [{"desc": "b"}, {"desc": "c"}]}]

    def test_failures_keep_their_cause_and_are_counted(self):
        m = make_matcher([])
        script = {"b": [http_error(429)] * 15, "c": ["not json"] * 3}
        replies = {k: iter(v) for k, v in script.items()}

        def call_one(model, prompt, force_freeform=False):
            item = next(replies["b" if "description: b" in prompt else "c"])
            if isinstance(item, BaseException):
                raise classify_call_error(item)
            return item, {}

        m._call_one = call_one
        m._breaker = CircuitBreaker(threshold=10**6)          # isolate from the breaker here
        with mock.patch("src.llm_call.time.sleep"):
            grouped, stats = m.assess(self.GROUPS)
        b, c = (json.loads(r[3]) for r in grouped[0])
        self.assertEqual(b["status"], "NOT_REACHED")
        self.assertTrue(b["reason"].startswith("LLM not reached after 15 attempts (rate_limit"), b["reason"])
        self.assertEqual(c["status"], "UNREADABLE")             # not re-run in later rounds
        self.assertEqual(c["reason"], "LLM answer unreadable after 3 attempts (json_parse_fail)")
        self.assertEqual((stats["not_reached"], stats["unreadable"]), (1, 1))

    def test_permanent_error_stops_the_run(self):
        m = make_matcher([])
        m._call_one = mock.Mock(side_effect=classify_call_error(http_error(401)))
        with self.assertRaises(LLMUnavailableError):
            m.assess(self.GROUPS)


# ── 3d: tuple -> LLMEvidence ────────────────────────────────────────────────

class Evidence(unittest.TestCase):

    def test_failures_are_not_rejections(self):
        ev = llm_evidence_from_tuple((None, ContextMatchType.PENDING.value, 0.0, json.dumps(
            {"status": "NOT_REACHED", "reason": "LLM not reached after 15 attempts (rate_limit: 429)"})))
        self.assertEqual((ev.status, ev.verdict), (LLM_NOT_REACHED, ""))
        self.assertIn("rate_limit", ev.reason)
        ev = llm_evidence_from_tuple((None, ContextMatchType.PENDING.value, 0.0, json.dumps(
            {"status": "UNREADABLE", "reason": "LLM answer unreadable after 3 attempts (json_parse_fail)"})))
        self.assertEqual(ev.status, LLM_UNREADABLE)

    def test_failures_written_by_the_old_code(self):
        # Exactly what the article run saved for the 14 failed pairs.
        old = (None, ContextMatchType.PENDING.value, 0.0, json.dumps(
            {"status": "PARSE_ERROR", "reason": "pending_after_assess_retries"}))
        self.assertEqual(llm_evidence_from_tuple(old).status, LLM_NOT_REACHED)
        old_parse = (None, ContextMatchType.PENDING.value, 0.0, json.dumps(
            {"status": "IMPOSSIBLE", "reason": "parse_failed_after_retries"}))
        self.assertEqual(llm_evidence_from_tuple(old_parse).status, LLM_UNREADABLE)
        # The empty-result placeholder used to carry NOT_APPLICABLE.
        self.assertNotEqual(llm_evidence_from_tuple((None, ContextMatchType.NOT_APPLICABLE.value, 0.0, "")).status, LLM_OK)

    def test_real_verdicts_unchanged(self):
        ok = llm_evidence_from_tuple(_parse_single(VALID))
        self.assertEqual((ok.status, ok.verdict), (LLM_OK, "PARTIAL"))
        reject = llm_evidence_from_tuple((False, ContextMatchType.NOT_APPLICABLE.value, 0.9, "{}"))
        self.assertEqual((reject.status, reject.verdict), (LLM_OK, "IMPOSSIBLE"))

    def test_unknown_verdict_is_unreadable(self):
        ev = LLMEvidence("MAYBE", 0.5)
        self.assertEqual((ev.status, ev.verdict), (LLM_UNREADABLE, ""))

    def test_bad_confidence_in_reason_json(self):
        ev = llm_evidence_from_tuple((True, ContextMatchType.PARTIAL.value, 0.7,
                                      json.dumps({"llm_self_reported_confidence": "high"})))
        self.assertEqual(ev.confidence, 0.7)


# ── 3e: policy without an LLM verdict ───────────────────────────────────────

def structural(level, transformation=TransformationType.MANUAL_REVIEW, reason="structural", needs_review=True, **extra):
    return StructuralEvidence(level=level, transformation=transformation, reason=reason,
                              needs_review=needs_review, extra=extra)


NOT_REACHED = LLMEvidence("", 0.0, reason="LLM not reached after 15 attempts (rate_limit: HTTP 429)",
                          status=LLM_NOT_REACHED)


class Fallback(unittest.TestCase):

    def test_nierenerkrankungen_ckd_keeps_partial(self):
        # Article: saved Not Applicable ("LLM rejected pair"); GT partial match.
        s = structural(MatchLevel.PARTIAL, reason="Same raw 0/1 codes; semantic equivalence unverified.")
        for mode in MODES:
            v = decide(mode, s, NOT_REACHED, True, TP)
            self.assertEqual(v.level, MatchLevel.PARTIAL)
            self.assertEqual(v.extra["llm_status"], LLM_NOT_REACHED)
            self.assertIn("Semantic check not performed (LLM not reached after 15 attempts", v.description)

    def test_lc_leukozyten_keeps_compatible(self):
        # Article: saved Not Applicable; GT compatible match.
        s = structural(MatchLevel.COMPATIBLE, TransformationType.UNIT_CONVERSION, unit_relation="scalable")
        unreadable = LLMEvidence("", 0.0, reason="LLM answer unreadable after 3 attempts (json_parse_fail)",
                                 status=LLM_UNREADABLE)
        v = decide(MappingType.OEH.value, s, unreadable, True, TP)
        self.assertEqual(v.level, MatchLevel.COMPATIBLE)
        self.assertEqual(v.transformation, TransformationType.UNIT_CONVERSION)
        self.assertEqual(v.extra["llm_status"], LLM_UNREADABLE)

    def test_a_failure_never_produces_not_applicable(self):
        for mode in MODES:
            for level in (MatchLevel.IDENTICAL, MatchLevel.COMPATIBLE, MatchLevel.PARTIAL):
                for status in (LLM_NOT_REACHED, LLM_UNREADABLE):
                    with self.subTest(mode=mode, level=level, status=status):
                        ev = LLMEvidence("", 0.0, reason="x", status=status)
                        v = decide(mode, structural(level), ev, True, TP)
                        self.assertNotEqual(v.level, MatchLevel.NOT_APPLICABLE)

    def test_missing_verdict_is_no_longer_not_applicable(self):
        for mode in MODES:
            v = decide(mode, structural(MatchLevel.PARTIAL), None, True, TP)
            self.assertEqual(v.level, MatchLevel.PARTIAL)
            self.assertEqual(v.extra["llm_status"], "missing")

    def test_early_exit_skip_still_drops_the_candidate(self):
        skipped = LLMEvidence("", 0.0, reason="Not sent to the LLM: source already matched.",
                              status=LLM_SKIPPED)
        for mode in MODES:
            v = decide(mode, structural(MatchLevel.PARTIAL), skipped, True, TP)
            self.assertEqual(v.level, MatchLevel.NOT_APPLICABLE)
            self.assertEqual(v.extra["llm_status"], LLM_SKIPPED)

    def test_status_recorded_for_every_path(self):
        decisive = structural(MatchLevel.IDENTICAL, TransformationType.NONE, needs_review=False)
        self.assertEqual(decide(MappingType.OEH.value, decisive, None, True, TP).extra["llm_status"], "not_needed")
        self.assertEqual(decide(MappingType.OEH.value, structural(MatchLevel.PARTIAL), None, False, TP).extra["llm_status"],
                         "not_configured")
        ok = LLMEvidence("PARTIAL", 0.9)
        self.assertEqual(decide(MappingType.OEH.value, structural(MatchLevel.PARTIAL), ok, True, TP).extra["llm_status"],
                         LLM_OK)
        self.assertEqual(decide(MappingType.OO.value, structural(MatchLevel.PARTIAL), None, False, TP).level,
                         MatchLevel.PARTIAL)


if __name__ == "__main__":
    unittest.main()
