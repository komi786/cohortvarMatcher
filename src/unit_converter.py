# """
# unit_conversion.py — Per-OMOP-concept unit conversion lookup.

# Sourced from a curated CSV of (concept_id, unit_a, unit_b, factor) triples.
# Used by ContinuousHandler to decide whether two differing units can be
# deterministically converted (-> COMPATIBLE) or not (-> PARTIAL).

# CSV columns expected:
#     variable omop id, variable concept name, preferred units,
#     conventional units, conv to si, si units, si to conv

# The loader is defensive: it skips rows with truncated units (e.g. "mg/"),
# numeric-only sentinels in the unit columns ("1"), and unparseable factors.
# """
# from __future__ import annotations

# import csv
# import logging
# import re
# from dataclasses import dataclass
# from pathlib import Path
# from typing import Dict, Optional, Tuple, Union

# logger = logging.getLogger(__name__)

# # Concepts whose published interconversion is non-linear (offset + scale).
# # Treat as COMPATIBLE but flag — a single multiplicative factor is wrong.
# # HbA1c IFCC (mmol/mol) ↔ NGSP (%) is the canonical example.
# _NON_LINEAR_CONCEPTS = frozenset({
#     3004410,    # Hemoglobin A1c (Glycated)
#     42869630,   # Hemoglobin A1c/Hemoglobin.total [Pure mass fraction]
#     4197971,    # HbA1c measurement
#     40758583,   # Hemoglobin A1c in Blood
# })

# _NUM_ONLY_RE = re.compile(r'^-?\d+(\.\d+)?([eE][+-]?\d+)?$')


# def _parse_factor(s: str) -> Optional[float]:
#     """Parse a factor cell. Handles plain floats and the '1.67*10*8' form
#     that appears in a few CSV rows (stringified scientific notation)."""
#     s = (s or '').strip().strip('"').strip("'")
#     if not s:
#         return None
#     if '*' in s:
#         try:
#             parts = [float(p) for p in s.split('*')]
#             v = parts[0]
#             for p in parts[1:]:
#                 v *= p
#             return v
#         except ValueError:
#             return None
#     try:
#         return float(s)
#     except ValueError:
#         return None


# def _norm_unit(u: str) -> str:
#     """Lowercase + collapse internal whitespace."""
#     return ' '.join((u or '').lower().split())


# def _is_unit_string(u: str) -> bool:
#     """Reject empty, numeric-only, or truncated unit strings."""
#     u = (u or '').strip().strip('"')
#     if not u:
#         return False
#     if _NUM_ONLY_RE.match(u):       # e.g. "1" in conventional-units column
#         return False
#     if u.endswith('/') or u.endswith('|'):   # e.g. "mg/", "ug/ml|mg/l"
#         # The pipe-separated form is ambiguous; skip rather than guess.
#         if u.endswith('/'):
#             return False
#         if '|' in u:
#             return False
#     return True


# @dataclass(frozen=True)
# class UnitConversion:
#     """Result of a successful conversion lookup."""
#     factor: float                  # multiply src_value by this to get tgt_value
#     non_linear: bool = False       # has known offset; factor is approximate


# class UnitConverter:
#     """Lookup table keyed by (concept_id, src_unit_norm, tgt_unit_norm).

#     The table is symmetric: every loaded (a, b, k) entry is mirrored as
#     (b, a, 1/k) — using the explicit reverse factor from the CSV when
#     available, falling back to 1/k otherwise.
#     """

#     def __init__(self) -> None:
#         self._table: Dict[Tuple[int, str, str], float] = {}

#     # -- Loading -------------------------------------------------------

#     @classmethod
#     def from_csv(cls, path: Union[str, Path]) -> "UnitConverter":
#         inst = cls()
#         path = Path(path)
#         loaded = skipped = conflicts = 0
#         with path.open(newline='', encoding='utf-8') as f:
#             reader = csv.DictReader(f)
#             for row in reader:
#                 added, conflict = inst._add_row(row)
#                 if added:
#                     loaded += 1
#                 else:
#                     skipped += 1
#                 if conflict:
#                     conflicts += 1
#         logger.info(
#             "UnitConverter: %d entries loaded, %d rows skipped, "
#             "%d duplicate-key conflicts (last write wins) from %s",
#             loaded, skipped, conflicts, path,
#         )
#         return inst

#     def _add_row(self, row: Dict[str, str]) -> Tuple[bool, bool]:
#         """Return (added, had_conflict)."""
#         try:
#             concept_id = int((row.get('variable omop id') or '').strip())
#         except (TypeError, ValueError):
#             return False, False

#         unit_a = (row.get('conventional units') or '').strip().strip('"')
#         unit_b = (row.get('si units') or '').strip().strip('"')
#         if not (_is_unit_string(unit_a) and _is_unit_string(unit_b)):
#             return False, False

#         a_to_b = _parse_factor(row.get('conv to si', ''))
#         if a_to_b is None or a_to_b == 0:
#             return False, False

#         ua, ub = _norm_unit(unit_a), _norm_unit(unit_b)
#         if ua == ub:
#             return False, False  # no information

#         b_to_a = _parse_factor(row.get('si to conv', ''))
#         if b_to_a is None or b_to_a == 0:
#             b_to_a = 1.0 / a_to_b

#         had_conflict = False
#         for key, val in [((concept_id, ua, ub), a_to_b),
#                          ((concept_id, ub, ua), b_to_a)]:
#             if key in self._table and abs(self._table[key] - val) > 1e-6:
#                 had_conflict = True
#                 logger.debug("Conflict for %s: %g vs %g (overwriting)",
#                              key, self._table[key], val)
#             self._table[key] = val
#         return True, had_conflict

#     # -- Querying ------------------------------------------------------

#     def lookup(self, concept_id: Optional[int],
#                src_unit: Optional[str],
#                tgt_unit: Optional[str]) -> Optional[UnitConversion]:
#         """Return a UnitConversion if a deterministic conversion exists,
#         else None. Same-unit pairs return factor=1.0 (no transformation)."""
#         if concept_id is None:
#             return None
#         s, t = _norm_unit(src_unit or ''), _norm_unit(tgt_unit or '')
#         if not s or not t:
#             return None
#         if s == t:
#             return UnitConversion(factor=1.0)
#         f = self._table.get((concept_id, s, t))
#         if f is None:
#             return None
#         return UnitConversion(
#             factor=f,
#             non_linear=concept_id in _NON_LINEAR_CONCEPTS,
#         )

#     def __len__(self) -> int:
#         return len(self._table)

#     def __contains__(self, key: Tuple[int, str, str]) -> bool:
#         cid, s, t = key
#         return (cid, _norm_unit(s), _norm_unit(t)) in self._table
