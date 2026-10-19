from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import xarray as xr
import yaml

from .config import PROJECT_ROOT


MANIFEST_PATH = PROJECT_ROOT / "config" / "data_manifest.yaml"
STATUS_ORDER = {"OK": 0, "WARN": 1, "FAIL": 2}


@dataclass(frozen=True)
class CheckResult:
    status: str
    dataset: str
    message: str


def load_data_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Data manifest not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        manifest = yaml.safe_load(f) or {}
    if not isinstance(manifest, dict) or "datasets" not in manifest:
        raise ValueError(f"Data manifest must contain a datasets mapping: {path}")
    return manifest


def validate_data_manifest(
    manifest_path: Path = MANIFEST_PATH,
    root: Path = PROJECT_ROOT,
) -> list[CheckResult]:
    manifest = load_data_manifest(manifest_path)
    results: list[CheckResult] = []

    datasets = manifest.get("datasets", {})
    for name, spec in datasets.items():
        if not isinstance(spec, dict):
            results.append(CheckResult("FAIL", name, "Dataset spec must be a mapping"))
            continue
        results.extend(validate_dataset(name, spec, root))

    return results


def validate_dataset(name: str, spec: dict[str, Any], root: Path) -> list[CheckResult]:
    dtype = spec.get("type", "file")
    required = bool(spec.get("required", True))
    rel_path = spec.get("path")
    if not rel_path:
        return [CheckResult("FAIL", name, "Missing path in manifest")]

    path = root / rel_path
    missing_status = "FAIL" if required else "WARN"
    if not path.exists():
        return [CheckResult(missing_status, name, f"Missing {dtype}: {rel_path}")]

    if dtype == "directory":
        return _validate_directory(name, path, rel_path)
    if dtype == "csv":
        return _validate_csv(name, path, spec, rel_path)
    if dtype == "excel":
        return _validate_excel(name, path, spec, rel_path)
    if dtype == "vector":
        return _validate_vector(name, path, spec, rel_path)
    if dtype == "netcdf":
        return _validate_netcdf(name, path, rel_path)

    return [CheckResult("OK", name, f"Found {rel_path}")]


def has_failures(results: list[CheckResult]) -> bool:
    return any(result.status == "FAIL" for result in results)


def summarize_results(results: list[CheckResult]) -> dict[str, int]:
    counts = {"OK": 0, "WARN": 0, "FAIL": 0}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    return counts


def _validate_directory(name: str, path: Path, rel_path: str) -> list[CheckResult]:
    files = [p for p in path.rglob("*") if p.is_file()]
    if not files:
        return [CheckResult("WARN", name, f"Directory is empty: {rel_path}")]
    return [CheckResult("OK", name, f"Found directory {rel_path} ({len(files)} files)")]


def _validate_csv(
    name: str,
    path: Path,
    spec: dict[str, Any],
    rel_path: str,
) -> list[CheckResult]:
    results: list[CheckResult] = []
    try:
        header = pd.read_csv(path, nrows=0)
    except Exception as exc:
        return [CheckResult("FAIL", name, f"Cannot read CSV {rel_path}: {exc}")]

    results.append(CheckResult("OK", name, f"Readable CSV: {rel_path}"))
    results.extend(_check_columns(name, header.columns, spec.get("required_columns", [])))
    return results


def _validate_excel(
    name: str,
    path: Path,
    spec: dict[str, Any],
    rel_path: str,
) -> list[CheckResult]:
    try:
        workbook = pd.ExcelFile(path)
    except Exception as exc:
        return [CheckResult("FAIL", name, f"Cannot read Excel {rel_path}: {exc}")]

    results = [CheckResult("OK", name, f"Readable Excel: {rel_path}")]
    sheets = spec.get("sheets", [])
    if not sheets:
        results.append(CheckResult("WARN", name, "No sheet expectations defined"))
        return results

    for sheet_spec in sheets:
        sheet_name = sheet_spec.get("name")
        if sheet_name not in workbook.sheet_names:
            results.append(CheckResult("FAIL", name, f"Missing sheet: {sheet_name}"))
            continue
        results.append(CheckResult("OK", name, f"Found sheet: {sheet_name}"))
        try:
            header = pd.read_excel(path, sheet_name=sheet_name, nrows=0)
        except Exception as exc:
            results.append(CheckResult("FAIL", name, f"Cannot read sheet {sheet_name}: {exc}"))
            continue
        results.extend(_check_columns(name, header.columns, sheet_spec.get("required_columns", [])))

    return results


def _validate_vector(
    name: str,
    path: Path,
    spec: dict[str, Any],
    rel_path: str,
) -> list[CheckResult]:
    try:
        import geopandas as gpd

        gdf = gpd.read_file(path)
    except Exception as exc:
        return [CheckResult("FAIL", name, f"Cannot read vector {rel_path}: {exc}")]

    results = [CheckResult("OK", name, f"Readable vector: {rel_path} ({len(gdf)} features)")]
    results.extend(_check_columns(name, gdf.columns, spec.get("required_columns", [])))

    expected_crs = spec.get("expected_crs")
    if expected_crs:
        actual_crs = str(gdf.crs) if gdf.crs is not None else None
        if actual_crs == expected_crs:
            results.append(CheckResult("OK", name, f"CRS is {expected_crs}"))
        else:
            results.append(CheckResult("WARN", name, f"CRS is {actual_crs}; expected {expected_crs}"))

    expected_geom = set(spec.get("geometry_types", []))
    if expected_geom:
        actual_geom = set(str(value) for value in gdf.geom_type.dropna().unique())
        unexpected = sorted(actual_geom - expected_geom)
        if unexpected:
            results.append(CheckResult("WARN", name, f"Unexpected geometry types: {', '.join(unexpected)}"))
        else:
            results.append(CheckResult("OK", name, "Geometry types match expectations"))

    return results


def _validate_netcdf(name: str, path: Path, rel_path: str) -> list[CheckResult]:
    try:
        with xr.open_dataset(path) as ds:
            variables = len(ds.data_vars)
    except Exception as exc:
        return [CheckResult("FAIL", name, f"Cannot read NetCDF {rel_path}: {exc}")]
    return [CheckResult("OK", name, f"Readable NetCDF: {rel_path} ({variables} variables)")]


def _check_columns(
    name: str,
    actual_columns: Any,
    required_columns: list[str],
) -> list[CheckResult]:
    actual = {str(column) for column in actual_columns}
    results = []
    for column in required_columns:
        if column in actual:
            results.append(CheckResult("OK", name, f"Found column: {column}"))
        else:
            results.append(CheckResult("FAIL", name, f"Missing column: {column}"))
    return results
