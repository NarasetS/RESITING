from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "default.yaml"
SCENARIOS_DIR = PROJECT_ROOT / "config" / "scenarios"


class ConfigError(ValueError):
    """Raised when a scenario configuration is invalid."""


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"Config file must contain a YAML mapping: {path}")
    return data


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def resolve_scenario_path(name_or_path: str | Path | None) -> Path:
    if name_or_path is None:
        return SCENARIOS_DIR / "base.yaml"

    raw = Path(name_or_path)
    if raw.exists():
        return raw

    if raw.suffix in {".yaml", ".yml"}:
        candidate = SCENARIOS_DIR / raw.name
    else:
        candidate = SCENARIOS_DIR / f"{raw.name}.yaml"

    return candidate


def load_config(scenario: str | Path | None = None) -> dict[str, Any]:
    base = read_yaml(DEFAULT_CONFIG_PATH)
    scenario_path = resolve_scenario_path(scenario)
    override = read_yaml(scenario_path)
    config = deep_merge(base, override)
    config["_scenario_path"] = str(scenario_path)
    config["_scenario_key"] = scenario_path.stem
    validate_config(config)
    return config


def list_scenarios() -> list[Path]:
    if not SCENARIOS_DIR.exists():
        return []
    return sorted(SCENARIOS_DIR.glob("*.y*ml"))


def validate_config(config: dict[str, Any]) -> None:
    required_sections = [
        "scenario",
        "assumptions",
        "capacity_density",
        "plant_size",
        "weights",
        "farm_area",
        "exclusions",
        "solver",
        "output",
        "quotas",
    ]
    for section in required_sections:
        if section not in config or not isinstance(config[section], dict):
            raise ConfigError(f"Missing required section: {section}")

    scenario_name = config["scenario"].get("name")
    if not isinstance(scenario_name, str) or not scenario_name.strip():
        raise ConfigError("scenario.name must be a non-empty string")

    _require_number(config, ("assumptions", "si_threshold"), minimum=0)
    _require_int(config, ("assumptions", "coarsen_scale"), minimum=1)
    _require_number(config, ("capacity_density", "wind_mw_per_km2"), minimum=0)
    _require_number(config, ("capacity_density", "solar_mw_per_km2"), minimum=0)
    _require_number(config, ("plant_size", "wind_mw"), minimum=0)
    _require_number(config, ("plant_size", "solar_mw"), minimum=0)
    _require_number(config, ("plant_size", "biomass_area_km2"), minimum=0)
    _require_number(config, ("plant_size", "bgec_area_km2"), minimum=0)
    _require_number(config, ("plant_size", "msw_area_km2"), minimum=0)
    _require_number(config, ("farm_area", "wind_min_km2"), minimum=0)
    _require_number(config, ("farm_area", "solar_min_km2"), minimum=0)
    _require_number(config, ("exclusions", "existing_committed_buffer_m"), minimum=0)
    _require_number(config, ("solver", "mip_abs_gap"), minimum=0)
    _require_number(config, ("solver", "mip_rel_gap"), minimum=0)

    weight_source = config["weights"].get("source")
    if weight_source not in {"default", "empirical"}:
        raise ConfigError("weights.source must be either 'default' or 'empirical'")

    quotas = config["quotas"]
    if not quotas:
        raise ConfigError("quotas must contain at least one technology")

    for tech, region_values in quotas.items():
        if not isinstance(region_values, dict) or not region_values:
            raise ConfigError(f"quotas.{tech} must contain region values")
        for region, value in region_values.items():
            if not isinstance(region, str) or not region:
                raise ConfigError(f"quotas.{tech} has an invalid region name")
            if not isinstance(value, (int, float)):
                raise ConfigError(f"quotas.{tech}.{region} must be numeric")
            if value < 0:
                raise ConfigError(f"quotas.{tech}.{region} must be >= 0")


def _require_number(
    config: dict[str, Any],
    path: tuple[str, str],
    minimum: float | None = None,
) -> None:
    section, key = path
    value = config.get(section, {}).get(key)
    if not isinstance(value, (int, float)):
        raise ConfigError(f"{section}.{key} must be numeric")
    if minimum is not None and value < minimum:
        raise ConfigError(f"{section}.{key} must be >= {minimum}")


def _require_int(
    config: dict[str, Any],
    path: tuple[str, str],
    minimum: int | None = None,
) -> None:
    section, key = path
    value = config.get(section, {}).get(key)
    if not isinstance(value, int):
        raise ConfigError(f"{section}.{key} must be an integer")
    if minimum is not None and value < minimum:
        raise ConfigError(f"{section}.{key} must be >= {minimum}")
