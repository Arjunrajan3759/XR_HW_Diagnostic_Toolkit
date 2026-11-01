# Agent operating instructions

Read this file before changing or running the toolkit. Work from the repository root; never hardcode the clone location. This is Python 3.11 host software and ESP-IDF firmware, not the production daemon.

## Safety boundaries

- Never flash unknown hardware without explicit operator approval. Never erase production firmware or camera configuration. Obtain a recovery image first.
- Never guess sensor pins, addresses, mux paths or electrical connections. H01 and physical H05 remain BLOCKED_CONFIG until verified wiring and qualified drivers exist.
- Never fabricate hardware results, call simulation physical, mark blocked tests successful, or hide failures.
- Never install/update system drivers silently, reset a device automatically, or perform irreversible operations without authorization.
- Never silently change the requested camera profile. Keep RGB and native Z16 independent.
- Stop at an approval boundary before firmware changes, rewiring or disruptive operations. Complete available safe work first.
- Never skip evidence/checksum validation. Do not regenerate a manifest to conceal corruption.

## Execution

1. Inspect README.md and BUILD_REPORT.md for current limitations. Preserve existing `.venv` and user files.
2. Run `powershell -NoProfile -File .\scripts\setup_windows.ps1 -Camera -Recording -Dev`. This does not install drivers or flash. If execution policy blocks scripts, use a process-scoped policy as described in README.
3. Run `.\.venv\Scripts\python.exe -m pip check`, `pio --version`, and `.\.venv\Scripts\python.exe -m pytest -q`. Build with `.\scripts\build_firmware.ps1`; a build is not hardware qualification.
4. Run `.\.venv\Scripts\python.exe -m xrdiag doctor`. Enumeration is passive. Do not probe arbitrary ports. Select the operator-confirmed ESP32 USB port and use `doctor --probe-port <port>`; only a protocol-compatible HELLO identifies diagnostic firmware. Opening a port on some drivers can still have side effects despite DTR/RTS being disabled; do not probe a device in use.
5. Run `.\.venv\Scripts\python.exe -m xrdiag simulate --duration 2` for software validation. Preserve SIMULATED labels.
6. Run `.\.venv\Scripts\python.exe -m xrdiag run-all --port <confirmed-port> --duration 10` when the operator has selected the port. Without that selection, run `run-all` and preserve blocked glove results. D435 discovery requires no SDK directory.
7. Individual commands are `run H01`, `run H02 --port <port> --sweep --duration 10`, `run H03 --duration 10`, `run H04 --port <port> --duration 10`, and `run H05`. Use `--help` for exact flags. H01 and physical H05 currently block safely. Physical event alignment is a separate BLOCKED_SETUP procedure; clock fitting does not validate it.
8. Use `analyze <results-folder>` then `package <results-folder>`. Add `--include-raw` only when requested; recordings can be large. Validate ZIP PACKAGE_CHECKSUMS when transferring. Exit 0=completed, 1=failure, 2=blocked; blocked is never successful qualification.

## Repository map

`xrdiag/protocol` framing; `devices` physical adapters; `simulation` fixed-seed sources; `analysis` shared metrics; `experiments` prerequisite gates; `recording` bounded single-writer pipeline; `reporting` evidence and packaging. `config` contains proposed hardware inventory and reference defaults. `firmware/xiao_esp32c6_diagnostics` is the PlatformIO project. `.docs` contains detailed procedures. `tests` are hardware-free. `results` is generated evidence, ignored by Git.

## Required final agent report

State commands executed and exit codes, software test count, firmware build result, device identities/status, each H01–H05 status and reason, physical versus simulated mode, evidence folders, validation/checksum results, package name/size/hash, missing prerequisites, and outstanding physical validation. Never equate a firmware build or simulated pass with physical success. See `.docs/09_AGENT_EXECUTION.md`.
