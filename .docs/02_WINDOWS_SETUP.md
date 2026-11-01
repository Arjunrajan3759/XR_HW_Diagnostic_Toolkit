# Windows setup

Use 64-bit CPython 3.11. The repository scripts resolve their root from PSScriptRoot, not the terminal working directory. They pass paths as PowerShell arguments, including paths with spaces. No activation is required: `.venv/Scripts/python.exe` is resolved relative to the repository. An existing environment is preserved and rejected if incompatible.

Run `powershell -NoProfile -File .\scripts\setup_windows.ps1 -Camera -Recording -Dev`. Camera and Recording are optional flags; Dev supplies pytest, Ruff and recording dependencies. Setup installs core plus all requested groups in one pip invocation then runs pip check. PlatformIO is discovered on PATH or in the standard per-user PlatformIO environment. Missing PlatformIO is reported as a firmware prerequisite, without installing drivers or requiring elevation.

Manual commands and official downloads are in README. `py -0p` lists interpreters; `py -3.11 --version` verifies selection. `check_environment.ps1` runs doctor and the PlatformIO version check. `build_firmware.ps1` logs the entire build in results/script_logs and does not upload. A Unicode error from PlatformIO on a legacy console can be repaired with PYTHONUTF8=1 (scripts already set it).

The camera wrapper is a pinned Windows CPython 3.11 wheel. A system SDK installation alone does not install that wheel in the toolkit environment. No SDK directory is searched or manually edited. Import errors include runtime version, architecture, virtual-environment context in environment.json, the exception, and repair instructions. If DLL import fails, repair the official Microsoft Visual C++ x64 runtime and pinned wrapper; do not copy random DLLs into system directories.

Logs may contain local paths from build/package tooling; do not share raw script transcripts without review. Experiment packages redact conventional Windows home paths from textual evidence. For dependency updates use an isolated environment and execute the clean-machine acceptance in 07_PORTABILITY.md before changing pins.

Scripts write both a PowerShell transcript and an explicit .native.txt command-output log. The latter preserves native stdout/stderr and exit codes even on Windows PowerShell hosts where transcripts omit native program output. A nonzero native status remains a failure (or exit 2 for blocked diagnostics); writing a log does not convert it to success.
