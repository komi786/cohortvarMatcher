"""Variable names reach SPARQL as escaped string literals.

Real case: names were pasted as f'"{v}"', so a name with " or \\ broke the
whole chunk of 50 (QueryBadFormed), and \\t silently looked up a tab.

Run from the repository root:  python -m unittest tests.test_sparql_literal
"""
import unittest
from unittest import mock

from src.query_builder import SPARQLQueryBuilder
from src.variable_profile import VariableProfile


class Literal(unittest.TestCase):
    def test_plain_name_unchanged(self):
        self.assertEqual(SPARQLQueryBuilder.literal("@6mwt"), '"@6mwt"')

    def test_quote_escaped(self):
        self.assertEqual(SPARQLQueryBuilder.literal('height"cm'), '"height\\"cm"')

    def test_backslash_escaped(self):
        self.assertEqual(SPARQLQueryBuilder.literal("dose\\day"), '"dose\\\\day"')

    def test_escape_sequence_not_interpreted(self):
        # a\tb must stay backslash + t, not become a tab on the server
        self.assertEqual(SPARQLQueryBuilder.literal("a\\tb"), '"a\\\\tb"')

    def test_backslash_before_quote(self):
        # \ is escaped first, so the \ added for " is not doubled again
        self.assertEqual(SPARQLQueryBuilder.literal('x\\"y'), '"x\\\\\\"y"')


class ProfileQuery(unittest.TestCase):
    def test_values_clause_uses_escaped_names(self):
        sent = []
        empty = {"results": {"bindings": []}}
        with mock.patch("src.variable_profile.execute_query",
                        side_effect=lambda q: sent.append(q) or empty):
            VariableProfile._fetch_chunk(["@6mwt", 'height"cm', "dose\\day"], "time-chf")
        self.assertIn('VALUES ?identifier { "@6mwt" "height\\"cm" "dose\\\\day" }', sent[0])


if __name__ == "__main__":
    unittest.main()
