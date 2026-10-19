import unittest

from resiting.validation import CheckResult, has_failures, summarize_results, validate_dataset


class ValidationTests(unittest.TestCase):
    def test_validate_missing_required_file_fails(self):
        results = validate_dataset(
            "missing_csv",
            {"type": "csv", "path": "missing.csv", "required": True},
            self._tmp_path(),
        )

        self.assertEqual(results, [CheckResult("FAIL", "missing_csv", "Missing csv: missing.csv")])

    def test_validate_missing_optional_file_warns(self):
        results = validate_dataset(
            "optional_csv",
            {"type": "csv", "path": "missing.csv", "required": False},
            self._tmp_path(),
        )

        self.assertEqual(results, [CheckResult("WARN", "optional_csv", "Missing csv: missing.csv")])

    def test_summary_and_failure_helpers(self):
        results = [
            CheckResult("OK", "a", "fine"),
            CheckResult("WARN", "b", "check"),
            CheckResult("FAIL", "c", "broken"),
        ]

        self.assertTrue(has_failures(results))
        self.assertEqual(summarize_results(results), {"OK": 1, "WARN": 1, "FAIL": 1})

    def _tmp_path(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory

        if not hasattr(self, "_tmp_dir"):
            self._tmp_dir = TemporaryDirectory()
            self.addCleanup(self._tmp_dir.cleanup)
        return Path(self._tmp_dir.name)


if __name__ == "__main__":
    unittest.main()
