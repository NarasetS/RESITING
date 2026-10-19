from __future__ import annotations

import sys
from pathlib import Path

from .config import PROJECT_ROOT, ConfigError, load_config
from .validation import CheckResult, has_failures


REQUIRED_PROJECT_FILES = [
    "START_RESITING.bat",
    "requirements.txt",
    "README.md",
    "WORKFLOW.md",
    "config/default.yaml",
    "config/data_manifest.yaml",
    "config/scenarios/base.yaml",
]


def portable_check(root: Path = PROJECT_ROOT) -> list[CheckResult]:
    results: list[CheckResult] = []

    for rel_path in REQUIRED_PROJECT_FILES:
        path = root / rel_path
        status = "OK" if path.exists() else "FAIL"
        message = f"Found {rel_path}" if path.exists() else f"Missing {rel_path}"
        results.append(CheckResult(status, "project_files", message))

    data_dir = root / "Data"
    output_dir = root / "Output"
    env_python = root / ".env" / "Scripts" / "python.exe"

    if data_dir.exists():
        results.append(CheckResult("OK", "copy_layout", "Data/ is present"))
    else:
        results.append(CheckResult("WARN", "copy_layout", "Data/ is missing; add input data before running workflow"))

    if output_dir.exists():
        results.append(CheckResult("OK", "copy_layout", "Output/ is present"))
    else:
        results.append(CheckResult("WARN", "copy_layout", "Output/ is missing; workflow scripts will create outputs as needed"))

    if env_python.exists():
        results.append(CheckResult("OK", "python_env", ".env/Scripts/python.exe is present"))
    else:
        results.append(CheckResult("WARN", "python_env", ".env is missing; run launcher option 1 to create it"))

    version = sys.version_info
    if version.major == 3 and version.minor in {10, 11, 12}:
        results.append(CheckResult("OK", "python_env", f"Current Python is {version.major}.{version.minor}.{version.micro}"))
    else:
        results.append(CheckResult("WARN", "python_env", f"Current Python is {version.major}.{version.minor}.{version.micro}; expected 3.10-3.12"))

    try:
        load_config("base")
        results.append(CheckResult("OK", "scenario", "Base scenario config is valid"))
    except ConfigError as exc:
        results.append(CheckResult("FAIL", "scenario", f"Base scenario config is invalid: {exc}"))

    if has_failures(results):
        results.append(CheckResult("FAIL", "portable_copy", "Portable copy check found blocking issues"))
    else:
        results.append(CheckResult("OK", "portable_copy", "Folder is ready for setup/validation on this machine"))

    return results
