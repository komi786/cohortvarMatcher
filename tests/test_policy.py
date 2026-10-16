"""policy.decide() when the LLM was consulted: scenarios S1-S9.

Rule under test: the LLM decides meaning, the structural layer bounds what the
representation allows.

  final level    = the LLM level, capped by any binding structural ceiling
  disagreement   = structural NOT_APPLICABLE vs LLM COMPLETE/COMPATIBLE
                   -> PARTIAL + manual review (no veto)
  transformation = consistent with the final level (IDENTICAL -> NONE)

Run from the repository root:  python -m unittest tests.test_policy
"""
import itertools
import unittest

from src.data_model import MappingType, MatchLevel, TransformationType, MappingRelation
from src.policy import decide
from src.verdict import LLMEvidence, StructuralEvidence, TimepointInfo

TP = TimepointInfo(aligned=True, status="aligned")
LLM_MODES = (MappingType.OEH.value, MappingType.NE.value)
LLM_LEVEL = {"COMPLETE": MatchLevel.IDENTICAL, "COMPATIBLE": MatchLevel.COMPATIBLE,
             "PARTIAL": MatchLevel.PARTIAL, "IMPOSSIBLE": MatchLevel.NOT_APPLICABLE}


def structural(level, transformation=TransformationType.MANUAL_REVIEW, *,
               ceiling=None, needs_review=True, reason="structural reason", **extra):
    return StructuralEvidence(level=level, transformation=transformation, reason=reason,
                              needs_review=needs_review, ceiling=ceiling, extra=extra)


def llm(verdict, reason="llm reason", transform=""):
    return LLMEvidence(verdict=verdict, confidence=0.9, reason=reason, transform=transform)


class Scenarios(unittest.TestCase):

    def run_all_modes(self, s, ev):
        return [decide(mode, s, ev, True, TP) for mode in LLM_MODES]

    # S1: deferred PARTIAL (same units, semantics pending) + COMPLETE.
    # Real: supraventricular extrasystole (yes/no) vs sves (yes/no).
    def test_s1_deferred_partial_complete_is_identical_without_review(self):
        s = structural(MatchLevel.PARTIAL, reason="Same raw 0/1 codes; semantic equivalence unverified.")
        for v in self.run_all_modes(s, llm("COMPLETE")):
            self.assertEqual(v.level, MatchLevel.IDENTICAL)
            self.assertEqual(v.transformation, TransformationType.NONE)

    # S2: unit strings differ but denote the same quantity + COMPLETE.
    # Real: leukocytes 10*3/uL vs WBC /nL.
    def test_s2_equivalent_units_complete_is_identical(self):
        s = structural(MatchLevel.PARTIAL, unit_relation="equivalent",
                       source_unit="ucum:10*3/uL", target_unit="ucum:/nL")
        for v in self.run_all_modes(s, llm("COMPLETE")):
            self.assertEqual(v.level, MatchLevel.IDENTICAL)
            self.assertEqual(v.transformation, TransformationType.NONE)

    # S3: units really differ (fixed factor) + COMPLETE -> the conversion stands.
    # Example: hemoglobin g/dL vs g/L.
    def test_s3_scalable_units_cap_complete_at_compatible(self):
        s = structural(MatchLevel.PARTIAL, TransformationType.UNIT_CONVERSION,
                       ceiling=MatchLevel.COMPATIBLE, unit_relation="scalable",
                       transformation_rule="multiply source values by 10")
        for v in self.run_all_modes(s, llm("COMPLETE", transform="x10")):
            self.assertEqual(v.level, MatchLevel.COMPATIBLE)
            self.assertEqual(v.transformation, TransformationType.UNIT_CONVERSION)
            # The deterministic factor wins over the LLM's free-text rule.
            self.assertEqual(v.extra["transformation_rule"], "multiply source values by 10")

    def test_s3_incommensurable_units_cap_at_partial(self):
        # Real: dose beta blocker % of target dose vs dose metoprolol (mg).
        s = structural(MatchLevel.PARTIAL, ceiling=MatchLevel.PARTIAL,
                       unit_relation="incommensurable")
        for verdict in ("COMPLETE", "COMPATIBLE"):
            for v in self.run_all_modes(s, llm(verdict)):
                self.assertEqual(v.level, MatchLevel.PARTIAL, verdict)
                self.assertEqual(v.transformation, TransformationType.MANUAL_REVIEW)

    def test_s3_molar_mass_is_a_fixed_constant_conversion(self):
        # Real: LDL mmol/L vs mg/dL. The constant is the analyte's molar mass,
        # so the conversion is deterministic (ground truth: compatible match).
        s = structural(MatchLevel.PARTIAL, TransformationType.UNIT_CONVERSION,
                       ceiling=MatchLevel.COMPATIBLE, unit_relation="molar_mass_dependent")
        for verdict in ("COMPLETE", "COMPATIBLE"):
            for v in self.run_all_modes(s, llm(verdict)):
                self.assertEqual(v.level, MatchLevel.COMPATIBLE, verdict)
                self.assertEqual(v.transformation, TransformationType.UNIT_CONVERSION)

    # S4: structural COMPATIBLE (transformation NONE, context pending) + COMPATIBLE.
    # Real: type mitral valve replacement vs type of devices -> was IDENTICAL.
    def test_s4_compatible_llm_never_becomes_identical(self):
        # Same-type qualitative pairs come out of the handler as IDENTICAL with
        # reason "Variables are compatible."; the real S4 row was this case.
        for lvl in (MatchLevel.IDENTICAL, MatchLevel.COMPATIBLE):
            s = structural(lvl, TransformationType.NONE, reason="Variables are compatible.")
            for v in self.run_all_modes(s, llm("COMPATIBLE")):
                self.assertEqual(v.level, MatchLevel.COMPATIBLE, lvl)
                self.assertNotEqual(v.transformation, TransformationType.NONE)

    # S5: structural COMPATIBLE (recoding found) + COMPLETE -> recoding stands.
    def test_s5_structural_compatible_caps_complete(self):
        s = structural(MatchLevel.COMPATIBLE, TransformationType.VALUE_NORMALIZATION)
        for v in self.run_all_modes(s, llm("COMPLETE")):
            self.assertEqual(v.level, MatchLevel.COMPATIBLE)
            self.assertEqual(v.transformation, TransformationType.VALUE_NORMALIZATION)

    # S6: deferred PARTIAL + COMPATIBLE, including the transformation-NONE case
    # that used to come out IDENTICAL.
    def test_s6_deferred_partial_compatible_is_compatible(self):
        for t in (TransformationType.MANUAL_REVIEW, TransformationType.NONE):
            s = structural(MatchLevel.PARTIAL, t)
            for v in self.run_all_modes(s, llm("COMPATIBLE")):
                self.assertEqual(v.level, MatchLevel.COMPATIBLE, t)

    def test_s6_scalable_units_label_unit_conversion(self):
        s = structural(MatchLevel.PARTIAL, ceiling=MatchLevel.COMPATIBLE,
                       unit_relation="scalable", source_unit="ucum:g/L", target_unit="ucum:g/dL")
        for v in self.run_all_modes(s, llm("COMPATIBLE")):
            self.assertEqual(v.transformation, TransformationType.UNIT_CONVERSION)

    def test_s6_equivalent_units_are_not_a_unit_conversion(self):
        # ng/mL vs ug/L differ as strings only; a COMPATIBLE verdict here comes
        # from something else (recoding), not from a unit conversion.
        s = structural(MatchLevel.PARTIAL, unit_relation="equivalent",
                       source_unit="ucum:ng/mL", target_unit="ucum:ug/L")
        for v in self.run_all_modes(s, llm("COMPATIBLE")):
            self.assertEqual(v.transformation, TransformationType.VALUE_NORMALIZATION)

    # S7: structural NOT_APPLICABLE vs LLM acceptance -> PARTIAL + review.
    # Real: time from baseline to month 6 visit vs number of days to endpoint.
    def test_s7_structural_na_vs_llm_accept_is_partial_review(self):
        s = structural(MatchLevel.NOT_APPLICABLE, TransformationType.NONE,
                       reason="Continuous vs qualitative free-text; no structural harmonization possible.")
        for verdict in ("COMPLETE", "COMPATIBLE"):
            for v in self.run_all_modes(s, llm(verdict)):
                self.assertEqual(v.level, MatchLevel.PARTIAL, verdict)
                self.assertEqual(v.transformation, TransformationType.MANUAL_REVIEW)
                self.assertTrue(v.extra.get("structural_llm_disagreement"))
                self.assertIn("disagree", v.description.lower())

    def test_s7_structural_na_with_llm_partial_stays_partial(self):
        s = structural(MatchLevel.NOT_APPLICABLE, TransformationType.NONE)
        for v in self.run_all_modes(s, llm("PARTIAL")):
            self.assertEqual(v.level, MatchLevel.PARTIAL)

    # S8: hierarchical relation + COMPLETE -> trust the LLM.
    def test_s8_hierarchical_trusts_llm(self):
        for rel in (MappingRelation.SymbolicBroadMatch.value, MappingRelation.SymbolicNarrowMatch.value):
            s = structural(MatchLevel.PARTIAL, mapping_relation=rel)
            for v in self.run_all_modes(s, llm("COMPLETE")):
                self.assertEqual(v.level, MatchLevel.IDENTICAL, rel)

    # S9: LLM PARTIAL / IMPOSSIBLE are taken as given.
    def test_s9_llm_partial_and_impossible(self):
        s = structural(MatchLevel.IDENTICAL, TransformationType.NONE)
        for v in self.run_all_modes(s, llm("PARTIAL")):
            self.assertEqual(v.level, MatchLevel.PARTIAL)
            self.assertEqual(v.transformation, TransformationType.MANUAL_REVIEW)
        for v in self.run_all_modes(s, llm("IMPOSSIBLE")):
            self.assertEqual(v.level, MatchLevel.NOT_APPLICABLE)


class Invariants(unittest.TestCase):
    """Properties that must hold for every structural x LLM combination."""

    def test_grid(self):
        levels = list(MatchLevel)
        ceilings = [None, MatchLevel.COMPATIBLE, MatchLevel.PARTIAL]
        transforms = [TransformationType.NONE, TransformationType.MANUAL_REVIEW,
                      TransformationType.UNIT_CONVERSION, TransformationType.VALUE_NORMALIZATION]
        for mode, lvl, ceil, tr, verdict in itertools.product(
                LLM_MODES, levels, ceilings, transforms, LLM_LEVEL):
            s = structural(lvl, tr, ceiling=ceil)
            v = decide(mode, s, llm(verdict), True, TP)
            with self.subTest(mode=mode, structural=lvl, ceiling=ceil, transformation=tr, llm=verdict):
                # Never better than the LLM said.
                self.assertGreaterEqual(int(v.level), int(LLM_LEVEL[verdict]))
                # Never better than a binding ceiling allows.
                if ceil is not None:
                    self.assertGreaterEqual(int(v.level), int(ceil))
                # Identical means values merge as-is.
                if v.level == MatchLevel.IDENTICAL:
                    self.assertEqual(v.transformation, TransformationType.NONE)
                else:
                    self.assertNotEqual(v.transformation, TransformationType.NONE)


if __name__ == "__main__":
    unittest.main()
