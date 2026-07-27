from __future__ import annotations

import unittest

from notation_inventory import heading_start, inventory


class NotationInventoryTests(unittest.TestCase):
    def test_finds_first_occurrence_and_composite_symbol(self) -> None:
        source = """# Intro
$x=1$

## Gaussian neck
$B_t^c(p,q)=\\omega_{g,n}^G$
$B_t^c=O(1)$
"""
        start = heading_start(source, "Gaussian neck")
        items = {item["symbol"]: item for item in inventory(source, start_line=start)}
        self.assertEqual(items["B_t^c"]["first_line"], 5)
        self.assertEqual(items["B_t^c"]["occurrences"], 2)
        self.assertEqual(items["\\omega_{g,n}^G"]["first_line"], 5)
        self.assertNotIn("x", items)

    def test_missing_heading_fails(self) -> None:
        with self.assertRaises(ValueError):
            heading_start("# One\n", "Two")

    def test_multiline_bracket_display_is_scanned_once(self) -> None:
        source = """# Intro
Text.
\\[
F_g(t,s)=\\omega_{g,n}+H_g(t,s)
\\]
"""
        items = {item["symbol"]: item for item in inventory(source)}
        self.assertEqual(items["F_g"]["first_line"], 3)
        self.assertEqual(items["F_g"]["occurrences"], 1)
        self.assertEqual(items["\\omega_{g,n}"]["first_line"], 3)
        self.assertEqual(items["H_g"]["occurrences"], 1)


if __name__ == "__main__":
    unittest.main()
