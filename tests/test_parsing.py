import unittest

from harness.parsing import exact_protocol_following, parse_candidate, parse_first_token


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


if __name__ == "__main__":
    unittest.main()
