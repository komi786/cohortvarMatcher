"""Unit comparison on the unit pairs observed in the TIME-CHF evaluation outputs.

Run from the repository root:  python -m unittest tests.test_units
"""
import math
import threading
import unittest

from src.units import (
    EQUIVALENT, SCALABLE, MOLAR_MASS_DEPENDENT, INCOMMENSURABLE, UNPARSEABLE,
    RANGE_CONFIRMED, RANGE_CONTRADICTED, RANGE_UNVERIFIED,
    check_ranges, compare_units, parse_unit, to_pint_expression,
)


class EquivalentUnits(unittest.TestCase):
    """Same quantity written differently: values merge unchanged (Identical)."""

    def test_pairs(self):
        for a, b in [
            ("ucum:ng/mL", "ucum:ug/L"),          # ferritin
            ("ucum:pg/mL", "ucum:ng/L"),          # hs-troponin T
            ("ucum:10*3/uL", "ucum:/nL"),         # leukocytes
            ("ucum:10*3/uL", "ucum:10*9/L"),
            ("Ucum:10*6/uL", "ucum:10*12/L"),     # erythrocytes
            ("ucum:/min", "ucum:{counts}/min"),   # heart rate
            ("beats/min", "ucum:/min"),
            ("ucum:%", "%"),
            ("ucum:mg/dl", "ucum:mg/dL"),
            ("ucum:mm[hg]", "ucum:mm[Hg]"),
            ("ucum:[u]/l", "ucum:[U]/L"),
            ("ucum:\tg/l", "ucum:g/L"),
            ("ucum:mL/min/{1.73_m2}", "ucum:mL/min/(173.10*-2.m2)"),
        ]:
            with self.subTest(a=a, b=b):
                r = compare_units(a, b)
                self.assertEqual(r.relation, EQUIVALENT, r.reason)
                self.assertEqual(r.factor, 1.0)


class ScalableUnits(unittest.TestCase):
    """Same dimension, fixed factor: deterministic conversion (Compatible)."""

    def test_pairs(self):
        for a, b, factor in [
            ("ucum:g/l", "ucum:g/dl", 0.1),        # hemoglobin
            ("ucum:mg/L", "ucum:mg/dL", 0.1),      # CRP
            ("ucum:pg/ml", "ucum:ng/ml", 1e-3),    # troponin
            ("ucum:L/L", "ucum:%", 100.0),         # hematocrit
            ("ucum:1", "ucum:%", 100.0),           # HbA1c fraction
            ("ucum:ug/ml", "ucum:mg/dl", 0.1),     # creatinine
            ("ucum:[U]/L", "ukat/L", 1 / 60),      # AST: 1 ukat/L = 60 U/L
            ("ucum:10*6/ml", "ucum:10*12/l", 1e-3),
            ("ucum:a", "ucum:mo", 12.0),
        ]:
            with self.subTest(a=a, b=b):
                r = compare_units(a, b)
                self.assertEqual(r.relation, SCALABLE, r.reason)
                self.assertTrue(math.isclose(r.factor, factor, rel_tol=1e-9), r.factor)

    def test_factor_direction(self):
        # 15 g/dL hemoglobin is 150 g/L.
        r = compare_units("ucum:g/dL", "ucum:g/L")
        self.assertTrue(math.isclose(15 * r.factor, 150.0, rel_tol=1e-9))


class MolarMassUnits(unittest.TestCase):
    """Amount vs mass of substance: deterministic only given the molar mass."""

    def test_ldl_mmol_to_mg_dl(self):
        r = compare_units("ucum:mmol/L", "ucum:mg/dL")
        self.assertEqual(r.relation, MOLAR_MASS_DEPENDENT)
        self.assertFalse(r.is_deterministic)
        self.assertTrue(math.isclose(r.factor_with_molar_mass(386.65), 38.665, rel_tol=1e-6))

    def test_creatinine_umol_to_mg_dl(self):
        r = compare_units("ucum:umol/L", "ucum:mg/dL")
        self.assertTrue(math.isclose(1 / r.factor_with_molar_mass(113.12), 88.40, rel_tol=1e-3))

    def test_reverse_direction(self):
        r = compare_units("ucum:mg/dL", "ucum:mmol/L")
        self.assertEqual(r.relation, MOLAR_MASS_DEPENDENT)
        self.assertTrue(math.isclose(r.factor_with_molar_mass(386.65), 1 / 38.665, rel_tol=1e-6))

    def test_missing_molar_mass(self):
        r = compare_units("ucum:pmol/L", "ucum:pg/mL")   # FGF23
        self.assertIsNone(r.factor_with_molar_mass(0))
        self.assertIsNone(compare_units("ucum:g/L", "ucum:g/dL").factor_with_molar_mass(100))


class IncommensurableUnits(unittest.TestCase):
    """Different dimensions: never Compatible on units alone."""

    def test_pairs(self):
        for a, b in [
            ("ucum:%", "ucum:mg"),                       # % of target dose vs dose
            ("ucum:ml/m2", "ucum:mL"),                   # LVEDV index vs volume
            ("ucum:mL/min/{1.73_m2}", "ucum:mL/min"),     # eGFR vs creatinine clearance
            ("ucum:deg", "ucum:%"),                      # angle is not a fraction
            ("ucum:10*-6.[iu]/ml", "ucum:ng/ml"),        # IU is analyte-specific
            ("ucum:10*-6.[iu]/ml", "ucum:/mL"),
            ("ucum:[u]/l", "ucum:g/l"),                  # [u] is the enzyme unit, not daltons
        ]:
            with self.subTest(a=a, b=b):
                self.assertEqual(compare_units(a, b).relation, INCOMMENSURABLE)


class UnparseableUnits(unittest.TestCase):

    def test_not_units(self):
        for raw in ["DD-MM-YYYY", "dd/mm/yyyy", "YYYY/MM/DD", "", None, "nan", "furlongs-ish"]:
            with self.subTest(raw=raw):
                self.assertEqual(compare_units(raw, "ucum:mg").relation, UNPARSEABLE)

    def test_hostile_input_rejected_before_parser(self):
        # Quotes, separators, control characters and over-long strings are
        # stopped by the whitelist and never handed to pint.
        for raw in ["__import__('os').system('id')", "mg;rm -rf /", "a" * 500,
                    "mg/dL\x00", 'mg"', "mg`id`"]:
            with self.subTest(raw=raw):
                self.assertIsNone(to_pint_expression(raw))
                self.assertEqual(compare_units(raw, "ucum:mg").relation, UNPARSEABLE)

    def test_whitelisted_but_meaningless_input(self):
        for raw in ["eval(1)", "{{7*7}}", "((((", "mg**mg**mg"]:
            with self.subTest(raw=raw):
                self.assertEqual(compare_units(raw, "ucum:mg").relation, UNPARSEABLE)


class LooseSpellings(unittest.TestCase):
    """Spellings found in the article-run outputs and the current dictionaries."""

    def test_equivalent_spellings(self):
        for a, b in [
            ("μmol/l", "ucum:umol/L"),                     # Greek mu
            ("µg/ml", "ucum:ug/mL"),                       # micro sign
            ("mcg/dl", "ucum:ug/dL"),
            ("mmhg", "ucum:mm[Hg]"),                       # lower-cased code
            ("mv", "ucum:mV"),
            ("bpm", "ucum:/min"),
            ("beats per minute", "ucum:/min"),
            ("per 24 hours", "ucum:/(24.h)"),
            ("ml/24h", "ucum:mL/(24.h)"),
            ("ml/min/1.73m2", "ucum:mL/min/{1.73_m2}"),   # three spellings of eGFR
            ("mL/min/1.73m2", "ucum:mL/min/(173.10*-2.m2)"),
            ("kg/m^2", "ucum:kg/m2"),
            ("Kilogram", "kg"),
            ("Years", "ucum:a"),
            ("U/L", "ucum:[U]/L"),
            ("u/l", "ucum:[U]/L"),                         # lower-cased enzyme unit, not dalton
            ("IU/L", "ucum:[iU]/L"),
            ("ucum:wk", "week"),
        ]:
            with self.subTest(a=a, b=b):
                r = compare_units(a, b)
                self.assertEqual(r.relation, EQUIVALENT, r.reason)

    def test_true_dimensionless_unit_is_kept(self):
        self.assertEqual(compare_units("ucum:1", "ucum:%").relation, SCALABLE)


class NotSure(unittest.TestCase):
    """Readings that would be confident and wrong are refused."""

    def test_case_changes_meaning(self):
        # MG megagauss/mg, ML megalitre/mL, G/L gauss/L or giga/L, T/L tesla/L.
        for raw in ["MG", "ML", "G/L", "T/L", "MG-DL", "MmHg"]:
            with self.subTest(raw=raw):
                self.assertIsNone(parse_unit(raw))

    def test_single_letter_case_is_not_guessed(self):
        # "/w" is per week in the dictionaries; a case-blind lookup reads watt.
        self.assertIsNone(parse_unit("UCUM:/w"))
        self.assertIsNone(parse_unit("t/l"))               # lower-cased T/L, not tonnes

    def test_pint_false_friends(self):
        for raw in ["units", "unit/l", "points", "pt", "grade"]:
            with self.subTest(raw=raw):
                self.assertIsNone(parse_unit(raw))

    def test_offset_scales_have_no_factor(self):
        self.assertEqual(compare_units("degC", "degF").relation, UNPARSEABLE)
        self.assertEqual(compare_units("degC", "kelvin").relation, UNPARSEABLE)

    def test_annotation_alone_is_not_a_unit(self):
        self.assertEqual(compare_units("ucum:{score}", "ucum:%").relation, UNPARSEABLE)
        self.assertEqual(compare_units("ucum:{ratio}", "ucum:1").relation, UNPARSEABLE)

    def test_lost_superscript(self):
        self.assertIsNone(parse_unit("109/L"))              # 10^9/L, not 109 per litre
        self.assertIsNone(parse_unit("1012/L"))

    def test_time_format_is_not_a_unit(self):
        # TIM-HF *_ZEIT "next visit time" (DATETIME) uses "hh/mm" as its format;
        # pint would otherwise read hecto-hours per millimetre.
        self.assertIsNone(parse_unit("hh/mm"))
        self.assertIsNone(parse_unit("hh"))                 # rare-prefix guard on its own

    def test_date_pattern_does_not_swallow_units(self):
        self.assertIsNotNone(parse_unit("mm/d"))            # millimetres per day
        self.assertIsNotNone(parse_unit("m/d"))

    def test_not_units(self):
        for raw in ["pack years", "servings/week", "dpw (drinks per week)",
                    "mg (miligram)", "DD.MM.YYYY", "ratio"]:
            with self.subTest(raw=raw):
                self.assertIsNone(parse_unit(raw))


class Ranges(unittest.TestCase):
    """check_ranges on value ranges recorded in the article-run outputs."""

    def test_wrong_label_is_caught(self):
        # TIME-CHF Hb "g/dl" 75-178 vs GISSI-HF EMOGLOB g/dl 5-19.9.
        self.assertEqual(check_ranges(1.0, 75, 178, 5, 19.9), RANGE_CONTRADICTED)
        # TIME-CHF Hct "%" 0.213-0.56 vs GISSI-HF EMATOCRI % 24-57.
        self.assertEqual(check_ranges(1.0, 0.213, 0.56, 24, 57), RANGE_CONTRADICTED)
        # TIME-CHF HbA1c "%" 0.033-0.117 vs Aachen-HF HbA1c percent 3.7-9.9.
        self.assertEqual(check_ranges(1.0, 0.033, 0.117, 3.7, 9.9), RANGE_CONTRADICTED)

    def test_correct_factor_is_confirmed(self):
        # Hb g/L 75-178, x0.1 -> 7.5-17.8 g/dL vs 5-19.9.
        self.assertEqual(check_ranges(0.1, 75, 178, 5, 19.9), RANGE_CONFIRMED)
        # Hct L/L 0.213-0.56, x100 -> 21.3-56 % vs 24-57.
        self.assertEqual(check_ranges(100, 0.213, 0.56, 24, 57), RANGE_CONFIRMED)

    def test_skewed_ranges_are_not_flagged(self):
        # Ferritin: heavy right tails differ a lot between cohorts.
        self.assertEqual(check_ranges(1.0, 0.0, 1838.9, 5, 500), RANGE_CONFIRMED)

    def test_missing_or_bad_ranges_are_unverified(self):
        nan = float("nan")
        for args in [(1.0, None, 10, 1, 2), (1.0, 1, 10, nan, nan), (1.0, 10, 1, 1, 2),
                     (None, 1, 2, 1, 2), (0.0, 1, 2, 1, 2), ("x", 1, 2, 1, 2)]:
            with self.subTest(args=args):
                self.assertEqual(check_ranges(*args), RANGE_UNVERIFIED)


class ThreadSafety(unittest.TestCase):

    def test_concurrent_comparisons_agree(self):
        pairs = [("ucum:ng/mL", "ucum:ug/L"), ("ucum:g/l", "ucum:g/dl"),
                 ("ucum:mmol/L", "ucum:mg/dL"), ("ucum:%", "ucum:mg")]
        expected = [compare_units(a, b) for a, b in pairs]
        errors = []

        def work():
            for _ in range(200):
                for (a, b), exp in zip(pairs, expected):
                    if compare_units(a, b) != exp:
                        errors.append((a, b))

        threads = [threading.Thread(target=work) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
