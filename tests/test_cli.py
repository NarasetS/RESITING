import unittest

from resiting.cli import _build_stage_command


class CliTests(unittest.TestCase):
    def test_build_stage_command_uses_scenario(self):
        command = _build_stage_command("investment-map", "base")

        self.assertEqual(command[-2:], ["--scenario", "base"])
        self.assertTrue(command[1].endswith("12_SI_InvestmentMap.py"))


if __name__ == "__main__":
    unittest.main()
