from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from .config import (
    PROJECT_ROOT,
    SCENARIOS_DIR,
    ConfigError,
    list_scenarios,
    load_config,
    resolve_scenario_path,
)
from .validation import STATUS_ORDER, has_failures, summarize_results, validate_data_manifest
from .portable import portable_check
from .scenario import get_scenario_name, get_weight_settings


RUN_STAGES = ["weights", "farm-area", "apply-exclusions", "visualize-si", "investment-map"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RESITING workflow helper commands.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list-scenarios", help="List available scenario YAML files.")
    subparsers.add_parser("portable-check", help="Check whether this copied folder has the expected layout.")

    validate_config_parser = subparsers.add_parser(
        "validate-config",
        help="Validate a scenario YAML file after merging defaults.",
    )
    validate_config_parser.add_argument(
        "scenario",
        nargs="?",
        default="base",
        help="Scenario name or YAML path. Defaults to base.",
    )

    new_scenario_parser = subparsers.add_parser(
        "new-scenario",
        help="Copy an existing scenario to a new scenario YAML file.",
    )
    new_scenario_parser.add_argument("name", help="New scenario name, without .yaml.")
    new_scenario_parser.add_argument(
        "--from",
        dest="source",
        default="base",
        help="Scenario name or YAML path to copy. Defaults to base.",
    )
    new_scenario_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the destination scenario if it already exists.",
    )

    validate_data_parser = subparsers.add_parser(
        "validate-data",
        help="Validate replace-in-place files under Data/.",
    )
    validate_data_parser.add_argument(
        "--manifest",
        default=str(PROJECT_ROOT / "config" / "data_manifest.yaml"),
        help="Manifest YAML path.",
    )

    run_stage_parser = subparsers.add_parser(
        "run-stage",
        help="Run one scenario-aware workflow stage.",
    )
    run_stage_parser.add_argument(
        "stage",
        choices=RUN_STAGES + ["all"],
        help="Stage to run. Use all for the scenario-aware downstream stages.",
    )
    run_stage_parser.add_argument(
        "--scenario",
        default="base",
        help="Scenario name or YAML path. Defaults to base.",
    )
    run_stage_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the command(s) without running them.",
    )

    args = parser.parse_args(argv)

    if args.command == "list-scenarios":
        return _list_scenarios()
    if args.command == "portable-check":
        return _portable_check()
    if args.command == "validate-config":
        return _validate_config(args.scenario)
    if args.command == "new-scenario":
        return _new_scenario(args.name, args.source, args.force)
    if args.command == "validate-data":
        return _validate_data(Path(args.manifest))
    if args.command == "run-stage":
        return _run_stage(args.stage, args.scenario, args.dry_run)

    parser.error(f"Unknown command: {args.command}")
    return 2


def _list_scenarios() -> int:
    scenarios = list_scenarios()
    if not scenarios:
        print("No scenarios found.")
        return 0

    print("Available scenarios:")
    for path in scenarios:
        print(f"  {path.stem} ({path.relative_to(PROJECT_ROOT)})")
    return 0


def _validate_config(scenario: str) -> int:
    try:
        config = load_config(scenario)
    except ConfigError as exc:
        print(f"FAIL  {exc}")
        return 1

    scenario_name = get_scenario_name(config)
    print(f"OK    Scenario config is valid: {scenario_name}")
    print(f"      SI threshold: {config['assumptions']['si_threshold']}")
    print(f"      Coarsen scale: {config['assumptions']['coarsen_scale']}")
    return 0


def _new_scenario(name: str, source: str, force: bool) -> int:
    safe_name = Path(name).stem
    if not safe_name:
        print("FAIL  Scenario name cannot be empty.")
        return 1

    source_path = resolve_scenario_path(source)
    if not source_path.exists():
        print(f"FAIL  Source scenario not found: {source_path}")
        return 1

    SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)
    dest_path = SCENARIOS_DIR / f"{safe_name}.yaml"
    if dest_path.exists() and not force:
        print(f"FAIL  Scenario already exists: {dest_path}")
        print("      Use --force to overwrite it.")
        return 1

    shutil.copyfile(source_path, dest_path)
    print(f"OK    Created scenario: {dest_path.relative_to(PROJECT_ROOT)}")
    print("      Edit this YAML file, then run validate-config.")
    return 0


def _validate_data(manifest_path: Path) -> int:
    results = validate_data_manifest(manifest_path=manifest_path)
    width = max((len(result.dataset) for result in results), default=0)
    for result in sorted(results, key=lambda item: (item.dataset, STATUS_ORDER[item.status], item.message)):
        print(f"{result.status:<5} {result.dataset:<{width}}  {result.message}")

    counts = summarize_results(results)
    print("")
    print(f"Summary: {counts['OK']} OK, {counts['WARN']} WARN, {counts['FAIL']} FAIL")
    return 1 if has_failures(results) else 0


def _portable_check() -> int:
    results = portable_check()
    width = max((len(result.dataset) for result in results), default=0)
    for result in sorted(results, key=lambda item: (item.dataset, STATUS_ORDER[item.status], item.message)):
        print(f"{result.status:<5} {result.dataset:<{width}}  {result.message}")

    counts = summarize_results(results)
    print("")
    print(f"Summary: {counts['OK']} OK, {counts['WARN']} WARN, {counts['FAIL']} FAIL")
    return 1 if has_failures(results) else 0


def _run_stage(stage: str, scenario: str, dry_run: bool) -> int:
    stages = RUN_STAGES if stage == "all" else [stage]
    for stage_name in stages:
        command = _build_stage_command(stage_name, scenario)
        if command is None:
            continue

        printable = " ".join(str(part) for part in command)
        if dry_run:
            print(printable)
            continue

        print(f"Running {stage_name}: {printable}")
        result = subprocess.run(command, cwd=PROJECT_ROOT)
        if result.returncode != 0:
            print(f"FAIL  Stage failed: {stage_name}")
            return result.returncode

    return 0


def _build_stage_command(stage: str, scenario: str) -> list[str] | None:
    scenario_arg = scenario or "base"
    if stage == "weights":
        config = load_config(scenario_arg)
        weight_source, weights_file = get_weight_settings(config)
        if weight_source != "empirical":
            print("Scenario uses default weights; skipping empirical weight generation.")
            return None
        command = [sys.executable, "10a_SI_WeightFactors.py"]
        if weights_file:
            command.extend(["--output-file", weights_file])
        return command
    if stage == "farm-area":
        return [sys.executable, "11_SI_Farmarea.py", "--scenario", scenario_arg]
    if stage == "apply-exclusions":
        return [sys.executable, "11a_SI_ApplyPlantExclusions.py", "--scenario", scenario_arg]
    if stage == "visualize-si":
        return [sys.executable, "11b_Visualize_SI.py"]
    if stage == "investment-map":
        return [sys.executable, "12_SI_InvestmentMap.py", "--scenario", scenario_arg]
    raise ConfigError(f"Unknown stage: {stage}")


if __name__ == "__main__":
    sys.exit(main())
