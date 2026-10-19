import unittest

from resiting.config import ConfigError, deep_merge, load_config, validate_config
from resiting.scenario import get_farm_area_settings, get_investment_settings, get_scenario_output_paths


class ConfigTests(unittest.TestCase):
    def test_load_base_config(self):
        config = load_config("base")

        self.assertEqual(config["scenario"]["name"], "base")
        self.assertEqual(config["assumptions"]["coarsen_scale"], 2)
        self.assertEqual(config["quotas"]["wind"]["R10"], 1900)

    def test_deep_merge_preserves_nested_defaults(self):
        merged = deep_merge(
            {"assumptions": {"si_threshold": 0, "coarsen_scale": 2}},
            {"assumptions": {"si_threshold": 1}},
        )

        self.assertEqual(merged["assumptions"]["si_threshold"], 1)
        self.assertEqual(merged["assumptions"]["coarsen_scale"], 2)

    def test_validate_config_rejects_negative_quota(self):
        config = load_config("base")
        config["quotas"]["wind"]["R10"] = -1

        with self.assertRaises(ConfigError):
            validate_config(config)

    def test_scenario_helpers_preserve_base_defaults(self):
        config = load_config("base")
        investment = get_investment_settings(config)
        farm_area = get_farm_area_settings(config)

        self.assertEqual(investment["investment_run_name"], "SSI_0_CS_2")
        self.assertEqual(investment["input_final_si"], "Output\\xr_final_SI_all_existing_committed_cutoff.nc")
        self.assertEqual(investment["quotas"]["wind"]["R10"], 1900)
        self.assertEqual(farm_area["Wind"], 4.0)
        self.assertEqual(farm_area["Solar"], 0.4)

    def test_non_base_scenario_gets_identifiable_output_paths(self):
        config = load_config("PDP2026_PH_Case4H")
        investment = get_investment_settings(config)
        paths = get_scenario_output_paths(config)

        self.assertEqual(str(paths["output_dir"]), "Output\\scenarios\\PDP2026_PH_Case4H")
        self.assertEqual(
            investment["input_final_si"],
            "Output\\scenarios\\PDP2026_PH_Case4H\\xr_final_SI_all_existing_committed_cutoff.nc",
        )
        self.assertEqual(investment["investment_run_name"], "SSI_0_CS_3_PDP2026_PH_Case4H")


if __name__ == "__main__":
    unittest.main()
