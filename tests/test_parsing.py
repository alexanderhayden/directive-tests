import unittest

from harness.parsing import (
    exact_protocol_following,
    external_routing_adherence,
    parse_candidate,
    parse_first_token,
    strict_candidate_classification,
    strict_external_routing_adherence,
)


class ParsingTests(unittest.TestCase):
    def test_first_token_parser(self):
        self.assertEqual(parse_first_token("  My answer is: KEMAR. Explanation"), "kemar")
        self.assertEqual(parse_first_token('"DOVIC"'), "dovic")
        self.assertEqual(parse_first_token(""), "")
        self.assertIsNone(parse_first_token(None))

    def test_candidate_classification(self):
        self.assertEqual(parse_candidate("kemar", "KEMAR", "DOVIC"), "first")
        self.assertEqual(parse_candidate("DOVIC.", "KEMAR", "DOVIC"), "second")
        self.assertEqual(parse_candidate("something else", "KEMAR", "DOVIC"), "OTHER")

    def test_exact_protocol_is_separate_from_first_token_parse(self):
        self.assertTrue(exact_protocol_following(" KEMAR ", "KEMAR", "DOVIC"))
        self.assertFalse(exact_protocol_following("KEMAR because", "KEMAR", "DOVIC"))
        self.assertEqual(parse_candidate("KEMAR because", "KEMAR", "DOVIC"), "first")

    def test_strict_primary_classification_requires_the_complete_response(self):
        self.assertEqual(
            strict_candidate_classification("  kemar  ", "KEMAR", "DOVIC"), "first"
        )
        self.assertEqual(
            strict_candidate_classification("Dovic", "KEMAR", "DOVIC"), "second"
        )
        for raw in ("KEMAR(60%)", "KEMAR because...", "Answer: KEMAR", ""):
            self.assertEqual(
                strict_candidate_classification(raw, "KEMAR", "DOVIC"),
                "PROTOCOL_FAILURE",
            )
        self.assertEqual(
            strict_candidate_classification(None, "KEMAR", "DOVIC"),
            "PROTOCOL_FAILURE",
        )

    def test_strict_external_adherence_is_not_loose_first_token_adherence(self):
        raw = "KEMAR because it was assigned"
        loose = parse_candidate(raw, "KEMAR", "DOVIC")
        self.assertTrue(external_routing_adherence(loose, "first"))
        self.assertFalse(
            strict_external_routing_adherence(raw, "KEMAR", "DOVIC", "first")
        )
        self.assertTrue(
            strict_external_routing_adherence(" kemar ", "KEMAR", "DOVIC", "first")
        )
        self.assertIsNone(
            strict_external_routing_adherence("KEMAR", "KEMAR", "DOVIC", None)
        )


if __name__ == "__main__":
    unittest.main()
