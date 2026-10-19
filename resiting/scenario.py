from __future__ import annotations

from pathlib import Path
import json
import re
from typing import Any


def get_scenario_name(config: dict[str, Any]) -> str:
    scenario_name = config.get("scenario", {}).get("name", "base")
    scenario_key = config.get("_scenario_key")
    if scenario_key and scenario_key != "base" and scenario_name == "base":
        return scenario_key
    return scenario_name


def safe_scenario_name(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name).strip())
    return safe.strip("._-") or "scenario"


def is_base_scenario(config: dict[str, Any]) -> bool:
    return get_scenario_name(config) == "base"


def get_scenario_output_dir(config: dict[str, Any]) -> Path:
    if is_base_scenario(config):
        return Path("Output")
    return Path("Output") / "scenarios" / safe_scenario_name(get_scenario_name(config))


def get_scenario_output_paths(config: dict[str, Any]) -> dict[str, Path]:
    output_dir = get_scenario_output_dir(config)
    return {
        "output_dir": output_dir,
        "final_si": output_dir / "xr_final_SI_all.nc",
        "farmarea": output_dir / "xr_SI_Farmarea.nc",
        "cutoff_prefeedstock": output_dir / "xr_SI_Landcover_beforefeedstock_existing_committed_cutoff.nc",
        "cutoff_landcover": output_dir / "xr_SI_Landcover_existing_committed_cutoff.nc",
        "cutoff_final_si": output_dir / "xr_final_SI_all_existing_committed_cutoff.nc",
        "cutoff_farmarea": output_dir / "xr_SI_Farmarea_existing_committed_cutoff.nc",
    }


def write_stage_metadata(
    path: Path,
    config: dict[str, Any],
    stage: str,
    outputs: dict[str, str | Path],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "stage": stage,
                "scenario": get_scenario_name(config),
                "scenario_file": config.get("_scenario_path"),
                "outputs": {key: str(value) for key, value in outputs.items()},
            },
            f,
            indent=2,
            ensure_ascii=False,
        )


def get_weight_settings(config: dict[str, Any]) -> tuple[str, str | None]:
    weights = config.get("weights", {})
    source = weights.get("source", "empirical")
    path = weights.get("file")
    return source, str(path) if path else None


def get_farm_area_settings(config: dict[str, Any]) -> dict[str, float]:
    farm_area = config.get("farm_area", {})
    return {
        "Wind": float(farm_area.get("wind_min_km2", 4.0)),
        "Solar": float(farm_area.get("solar_min_km2", 0.4)),
    }


def get_exclusion_settings(config: dict[str, Any]) -> dict[str, float]:
    exclusions = config.get("exclusions", {})
    return {
        "existing_committed_buffer_m": float(exclusions.get("existing_committed_buffer_m", 2900)),
    }


def get_investment_settings(config: dict[str, Any]) -> dict[str, Any]:
    assumptions = config.get("assumptions", {})
    density = config.get("capacity_density", {})
    plant_size = config.get("plant_size", {})
    solver = config.get("solver", {})
    output = config.get("output", {})
    scenario = config.get("scenario", {})
    quotas = config.get("quotas", {})

    si_threshold = assumptions.get("si_threshold", 0)
    coarsen_scale = assumptions.get("coarsen_scale", 2)
    scenario_name = get_scenario_name(config)
    scenario_paths = get_scenario_output_paths(config)
    run_name = output.get("investment_run_name")
    if not run_name:
        run_name = f"SSI_{si_threshold}_CS_{coarsen_scale}"
        if scenario_name != "base":
            run_name = f"{run_name}_{scenario_name}"

    input_final_si = output.get("input_final_si") or scenario_paths["cutoff_final_si"]

    return {
        "scenario_name": scenario_name,
        "scenario_output_dir": str(scenario_paths["output_dir"]),
        "si_threshold": si_threshold,
        "coarsen_scale": int(coarsen_scale),
        "wind_mw_per_km2": float(density.get("wind_mw_per_km2", 4.5)),
        "solar_mw_per_km2": float(density.get("solar_mw_per_km2", 15.0)),
        "wind_mw": float(plant_size.get("wind_mw", 50.0)),
        "solar_mw": float(plant_size.get("solar_mw", 10.0)),
        "biomass_area_km2": float(plant_size.get("biomass_area_km2", 100.0)),
        "bgec_area_km2": float(plant_size.get("bgec_area_km2", 100.0)),
        "msw_area_km2": float(plant_size.get("msw_area_km2", 100.0)),
        "solver_name": solver.get("name", "highs"),
        "mip_abs_gap": float(solver.get("mip_abs_gap", 0.1)),
        "mip_rel_gap": float(solver.get("mip_rel_gap", 0.1)),
        "enforce_total_quota": bool(solver.get("enforce_total_quota", True)),
        "enforce_regional_quota": bool(solver.get("enforce_regional_quota", True)),
        "quotas": quotas,
        "input_final_si": str(input_final_si),
        "investment_run_name": run_name,
    }
