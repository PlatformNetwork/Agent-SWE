# pylint:disable=C0114,C0116

from unittest import TestCase

import hcl2


class TestObjectKeys(TestCase):
    def test_reverse_transform_invalid_identifier_key(self):
        data = {"config": {":": 1, "ok": 2}}

        text = hcl2.writes(hcl2.reverse_transform(data))
        parsed = hcl2.loads(text)

        self.assertIn(":", parsed["config"])
        self.assertEqual(parsed["config"][":"], 1)
        self.assertEqual(parsed["config"]["ok"], 2)

    def test_parse_interpolated_string_key_strips_quotes(self):
        hcl_text = 'config = {"${var.some}": 1}\n'

        parsed = hcl2.loads(hcl_text)

        self.assertIn("${var.some}", parsed["config"])
        self.assertEqual(parsed["config"]["${var.some}"], 1)
        self.assertNotIn('"${var.some}"', parsed["config"])

    def test_round_trip_expression_key_without_extra_quotes(self):
        data = {"config": {"${var.some}": 2}}

        text = hcl2.writes(hcl2.reverse_transform(data))
        parsed = hcl2.loads(text)

        self.assertIn("var.some", text)
        self.assertIn("${var.some}", parsed["config"])
        self.assertEqual(parsed["config"]["${var.some}"], 2)
