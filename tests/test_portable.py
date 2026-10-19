import unittest

from resiting.portable import portable_check


class PortableTests(unittest.TestCase):
    def test_portable_check_reports_project_files(self):
        results = portable_check()

        messages = [result.message for result in results]
        self.assertIn("Found START_RESITING.bat", messages)
        self.assertIn("Base scenario config is valid", messages)


if __name__ == "__main__":
    unittest.main()
