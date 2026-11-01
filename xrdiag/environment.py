"""Portable environment provenance without personal paths."""

import importlib.metadata
import platform
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def snapshot() -> dict:
    packages = {}
    for name in ("pyserial", "pyrealsense2", "mcap", "pytest"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = "NOT_INSTALLED"
    pio = shutil.which("pio") or shutil.which("platformio")
    if not pio:
        candidate = Path.home() / ".platformio/penv/Scripts/platformio.exe"
        if candidate.is_file():
            pio = str(candidate)
    version = "NOT_INSTALLED"
    if pio:
        try:
            version = subprocess.check_output(
                [pio, "--version"], timeout=15, text=True
            ).strip()
        except (OSError, subprocess.SubprocessError):
            version = "ERROR"
    return dict(
        os=platform.system(),
        release=platform.release(),
        os_build=platform.version(),
        python=platform.python_version(),
        architecture=platform.machine(),
        virtual_environment=sys.prefix != sys.base_prefix,
        platformio=version,
        packages=packages,
    )
