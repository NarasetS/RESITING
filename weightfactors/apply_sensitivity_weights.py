import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd

from sensitivity_validation import ALL_TECHS, CRITERIA_NAMES, build_weight_scenarios


PROXY_TECH = {
    "BGWW": "BGEC",
    "IEW": "MSW",
}


def weights_as_named_dict(weights):
    return {
        tech: {
            criteria: float(value)
            for criteria, value in zip(CRITERIA_NAMES, values)
        }
        for tech, values in weights.items()
    }


def choose_best_scenarios(summary_path, metric):
    if not summary_path.exists():
        raise FileNotFoundError(
            f"Could not find {summary_path}. Run weightfactors/sensitivity_validation.py first."
        )

    summary = pd.read_csv(summary_path)
    if metric not in summary.columns:
        raise ValueError(f"Metric '{metric}' is not in {summary_path}.")

    choices = {}
    report_rows = []

    for tech in ALL_TECHS:
        validation_tech = PROXY_TECH.get(tech, tech)
        candidates = summary[
            (summary["tech"] == validation_tech)
            & (summary["existing_plant_count"].fillna(0) > 0)
            & summary[metric].notna()
        ].copy()

        if candidates.empty:
            scenario = "empirical"
            score = None
            note = "No validation data; fallback to empirical."
        else:
            candidates = candidates.sort_values(metric, ascending=False)
            best = candidates.iloc[0]
            scenario = str(best["scenario"])
            score = float(best[metric])
            if validation_tech == tech:
                note = "Selected directly from validation results."
            else:
                note = f"Selected using {validation_tech} as validation proxy."

        choices[tech] = scenario
        report_rows.append(
            {
                "tech": tech,
                "validation_tech": validation_tech,
                "selected_scenario": scenario,
                "selection_metric": metric,
                "selection_score": score,
                "note": note,
            }
        )

    return choices, pd.DataFrame(report_rows)


def build_selected_weights(choices, scenarios):
    selected = {}
    for tech, scenario in choices.items():
        if scenario not in scenarios:
            raise ValueError(f"Scenario '{scenario}' is not available in build_weight_scenarios().")
        selected[tech] = scenarios[scenario][tech]
    return selected


def write_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)


def apply_sensitivity_weights(metric, apply_to_empirical):
    sensitivity_dir = Path("Output") / "sensitivity"
    summary_path = sensitivity_dir / "scenario_summary_all.csv"
    selected_weights_path = Path("weightfactors") / "sensitivity_selected_weights.json"
    report_path = Path("weightfactors") / "sensitivity_selection_report.csv"
    empirical_weights_path = Path("weightfactors") / "empirical_weights.json"

    scenarios = build_weight_scenarios()
    choices, report = choose_best_scenarios(summary_path, metric)
    selected_weights = build_selected_weights(choices, scenarios)
    named_weights = weights_as_named_dict(selected_weights)

    write_json(selected_weights_path, named_weights)
    report.to_csv(report_path, index=False)

    print("Selected sensitivity scenarios:")
    print(report.to_string(index=False))
    print(f"\nSelected weights written to: {selected_weights_path}")
    print(f"Selection report written to: {report_path}")

    if apply_to_empirical:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = empirical_weights_path.with_name(f"empirical_weights.backup_{timestamp}.json")
        if empirical_weights_path.exists():
            shutil.copy2(empirical_weights_path, backup_path)
            print(f"Previous empirical weights backed up to: {backup_path}")
        write_json(empirical_weights_path, named_weights)
        print(f"Applied selected weights to: {empirical_weights_path}")
        print("Next step: rerun 11_SI_Farmarea.py so the main SI map uses these weights.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Select and optionally apply weight scenarios using sensitivity validation results."
    )
    parser.add_argument(
        "--metric",
        default="median_existing_plant_percentile",
        help="Column in Output/sensitivity/scenario_summary_all.csv used to select the best scenario per technology.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Overwrite weightfactors/empirical_weights.json after creating a timestamped backup.",
    )
    args = parser.parse_args()
    apply_sensitivity_weights(metric=args.metric, apply_to_empirical=args.apply)
