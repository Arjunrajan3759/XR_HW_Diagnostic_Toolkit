# GloveXR Hardware Diagnostic Toolkit

This portable Windows command-line toolkit collects evidence for five experiments before choosing a GloveXR recording architecture. It saves measurements, configurations, reports, raw serial captures and optional MCAP recordings. It also runs without hardware using clearly labeled deterministic simulation.

The application is implemented, but physical sensor acquisition is intentionally blocked: the proposed glove inventory has no verified pin-to-pin wiring reference, and no sensor drivers have been qualified for that assembly. Physical combined glove/camera recording has the same prerequisite. USB benchmarking, camera capture and clock exchange have physical adapters; they still require on-site validation. Read [BUILD_REPORT.md](BUILD_REPORT.md) for actual verification results.

| Experiment | Question | Evidence |
|---|---|---|
| H01 | How fast can the glove read its sensors? | Inventory, per-read timing, percentiles; blocked checklist until wiring/drivers are verified |
| H02 | How much native USB data arrives intact? | Raw binary, sequence/CRC checks, throughput, firmware counters, rate sweeps |
| H03 | Can D435 RGB and depth run at the exact requested settings? | Capabilities, frame metadata CSV, independent stream metrics, optional raw MCAP |
| H04 | What clock drift and offset does software exchange estimate? | Raw four-timestamp observations, fit, residuals and rejection count; physical alignment remains separate |
| H05 | Can the experimental pipeline record both sources without loss? | Bounded queue metrics, MCAP segments, topic counts, hashes and readability checks |

## What you need

For software simulation: Windows 11, 64-bit Python 3.11, internet access for initial packages, and free disk space. Python 3.12/3.13 can remain installed alongside 3.11. No administrator rights are required for ordinary tests.

For physical tests: a Seeed Studio XIAO ESP32-C6, USB **data** cable, an Intel RealSense D435 and suitable USB 3 connection. H01/H05 additionally need the assembled glove, approved wiring, confirmed electrical prerequisites and qualified sensor drivers. Do not connect guessed wiring.

Official downloads:

- [Python 3.11](https://www.python.org/downloads/release/python-3119/) — install the 64-bit Windows installer and Python launcher.
- [VS Code](https://code.visualstudio.com/download) — optional editor.
- [PlatformIO Core installation](https://docs.platformio.org/en/latest/core/installation/index.html) or the [PlatformIO IDE extension](https://platformio.org/install/ide?install=vscode).
- [RealSense SDK and Viewer](https://github.com/realsenseai/librealsense/releases) — optional Viewer helps check USB/camera behavior. The Python wrapper is installed separately by this toolkit; SDK directories are never entered manually.
- [Microsoft Python extension](https://marketplace.visualstudio.com/items?itemName=ms-python.python) for VS Code. PlatformIO IDE is useful for firmware; neither editor extension is needed to execute the CLI.

## Fresh-clone setup

Open PowerShell in the cloned repository. All commands below use project-relative paths. If the folder contains spaces, use quotes when changing into it. Do not copy a `.venv` from another computer.

```powershell
py -0p
py -3.11 --version
# If local policy blocks scripts, this affects only this PowerShell process:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup_windows.ps1 -Recording -Dev
```

On the on-site camera computer, install the optional wrapper too:

```powershell
.\scripts\setup_windows.ps1 -Camera -Recording -Dev
.\scripts\check_environment.ps1
```

Setup preserves an existing `.venv`, checks Python 3.11, installs only into that environment, reports PlatformIO and writes a doctor report. A missing PlatformIO returns exit 2 after host setup; install it before building firmware. An existing incompatible environment must be preserved and resolved manually. No system drivers are installed. You never need to activate the environment.

Equivalent manual Python setup, if preferred (create `.venv` only if absent):

```powershell
if (-not (Test-Path .venv)) { py -3.11 -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-recording.txt -r requirements-dev.txt
# Optional camera support:
.\.venv\Scripts\python.exe -m pip install -r requirements-camera.txt
.\.venv\Scripts\python.exe -m pip check
pio --version
```

`requirements.txt` provides the physical serial adapter and pytest runner. `requirements-dev.txt` adds Ruff and the recording dependencies needed by the complete software suite. Camera and MCAP are optional for core CLI import/doctor. Full five-experiment simulation requires recording dependencies. Dependencies are pinned to versions installed and exercised during development. For upgrades, use a separate new Python 3.11 environment, install all groups together, run pip check, the test suite, simulation, MCAP verification and firmware build; update pins and BUILD_REPORT only after success. Do not update another operator's environment silently.

## Verify software and firmware

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check xrdiag tests
.\.venv\Scripts\python.exe -m xrdiag simulate --duration 2
.\scripts\build_firmware.ps1
# Equivalent firmware command:
pio run -d .\firmware\xiao_esp32c6_diagnostics
```

Simulation uses virtual time for H01/H02/H04 and paced sources for H05. It checks software behavior, not sustainable hardware performance. The default recording is short (2 seconds); do not start long high-rate recordings until disk capacity is checked. A compiler build does not access or qualify hardware.

## Discover devices safely

```powershell
.\.venv\Scripts\python.exe -m xrdiag list-devices
.\.venv\Scripts\python.exe -m xrdiag doctor
```

These commands list COM USB descriptions and camera capabilities. They do not open arbitrary serial ports. Identify the XIAO port from Windows Device Manager and USB identity, close any serial monitor, then select it explicitly:

```powershell
$GlovePort = Read-Host 'Enter the confirmed XIAO COM port'
.\.venv\Scripts\python.exe -m xrdiag doctor --probe-port $GlovePort
```

Only a matching HELLO product and protocol identifies diagnostic firmware; a COM number alone proves nothing. The probe disables DTR/RTS before opening and sends no reset command. Driver behavior cannot be guaranteed on unknown devices; never probe a port in use. Passive listing is the default for this reason. With multiple D435s, pass `--camera-serial` to choose one. Camera discovery uses `pyrealsense2.context()`, never a hardcoded SDK path. `NOT_INSTALLED` means wrapper/import trouble; `NOT_CONNECTED` means the wrapper works but sees no camera. `BUSY`, `WRONG_FIRMWARE`, `UNSUPPORTED_VERSION`, `READY` and `ERROR` explain other probe outcomes. A detailed JSON report accompanies doctor output.

## Safe firmware replacement and recovery

Normal tests never flash, erase or reset. Before replacing firmware, obtain the exact production recovery image and its approved restoration procedure from the hardware owner. Alternatively have a firmware engineer create and verify a complete backup with the correct chip/flash size, security settings and tool version. Encrypted flash and eFuses can prevent a portable backup; a generic binary copy is not a guaranteed recovery image. Do not change eFuses, erase flash, calibration or camera firmware.

After the owner confirms recovery and approves replacing this specific board:

```powershell
.\scripts\flash_firmware.ps1 -Port $GlovePort -RecoveryImageConfirmed
```

The script still requires typing `FLASH <selected-port>` interactively. It builds and uploads only after confirmation. It cannot back up unknown production firmware automatically. To restore, stop diagnostics, obtain explicit approval again, and follow the hardware owner's image-specific restoration instructions using their verified image and offsets. Do not upload the diagnostic binary as a substitute for a production recovery image. If recovery is unavailable, leave flashing BLOCKED.

## Run experiments

```powershell
.\.venv\Scripts\python.exe -m xrdiag run H01
.\.venv\Scripts\python.exe -m xrdiag run H02 --port $GlovePort --duration 10 --frame-size 256 --rate 500
.\.venv\Scripts\python.exe -m xrdiag run H02 --port $GlovePort --sweep --repetitions 2 --duration 10
# Sustained stability: explicitly request a longer run at a previously successful rate.
.\.venv\Scripts\python.exe -m xrdiag run H02 --port $GlovePort --duration 300 --frame-size 512 --rate 500
.\.venv\Scripts\python.exe -m xrdiag run H03 --duration 10
.\.venv\Scripts\python.exe -m xrdiag run H03 --duration 2 --record-camera
.\.venv\Scripts\python.exe -m xrdiag run H04 --port $GlovePort --duration 10
.\.venv\Scripts\python.exe -m xrdiag run H05 --duration 2
.\.venv\Scripts\python.exe -m xrdiag run-all --port $GlovePort --duration 10
```

H01 prints an exact missing-configuration checklist. Even an approved map remains blocked until drivers are qualified against actual hardware. Do not set `approved=true` merely to bypass the gate. `--sensor-map` preserves the supplied inventory snapshot. H02 payload size excludes the 26-byte decoded envelope; maximum payload is 998 bytes. Firmware supports offered rates 1–1000 packets/s and rejects other rates. The sweep requests payloads 64,128,256,512 at 100,500,1000 packets/s. It never adjusts them silently. Compare H02 measured throughput to a physically established H01 requirement with `--sensor-bytes-per-second`; 30% headroom is provisional, not a guarantee.

H03 explicitly requests RGB8 and Z16 at 640×480/30 FPS. Unsupported combinations fail with SDK error and a saved capability list; the CLI never downgrades. Metadata-only capture is the default; `--record-camera` saves original raw pixels in independent topics. Raw depth is never colorized. Close RealSense Viewer before capture. H04 estimates MCU-host clocks and saves available camera observations separately; overall physical H04 remains BLOCKED_SETUP until approved physical-event validation exists. USB asymmetry and physical glove-camera alignment remain unmeasured. H05 physical mode is blocked until real sensor acquisition exists; its recorder and simultaneous simulated sources are implemented and tested.

Use `--mode simulated` with any individual experiment. To exercise intentional errors:

```powershell
.\.venv\Scripts\python.exe -m xrdiag run H02 --mode simulated --faults --duration 1
.\.venv\Scripts\python.exe -m xrdiag run H05 --mode simulated --interrupt-after 3 --duration 1
.\.venv\Scripts\python.exe -m xrdiag run H05 --mode simulated --rgb-queue-mib 1 --writer-delay-ms 100 --duration 1
```

These commands are expected to return FAIL and preserve evidence. `.partial` files signal an interrupted/unfinalized recording and must never be treated as finalized MCAP. The standard combined script runs unit tests before diagnostics:

```powershell
.\scripts\run_all_tests.ps1 -Simulated -Duration 2
.\scripts\run_all_tests.ps1 -Port $GlovePort -Duration 10
```

## Read and share evidence

Every execution creates a unique timestamp/test/UUID directory. `summary.json` is machine readable; `report.md` is the human report. `configuration.json` keeps requested parameters; `environment.json` keeps software versions without interpreter/user paths. CSV stores measurements; raw binary and MCAP exist only when actually captured. Missing artifacts are explained in the report. Each run has SHA-256 records. Combined sessions contain child runs and `experiments.json`.

Statuses: PASS means that experiment's implemented physical criteria passed with physical observations. FAIL means errors, loss or a software/runtime failure. BLOCKED means a prerequisite prevents qualification. NOT_RUN means an operation was not attempted (for example passive serial discovery). SIMULATED_PASS means software behavior passed using simulated data. Exit codes are 0 completed, 1 failed, 2 blocked. A combined session with any blocker remains BLOCKED. Doctor's PASS means discovery completed, never hardware qualification.

```powershell
$ResultsFolder = Read-Host 'Paste the results folder printed by the command'
.\.venv\Scripts\python.exe -m xrdiag analyze $ResultsFolder
.\.venv\Scripts\python.exe -m xrdiag package $ResultsFolder
# Explicitly include potentially large recordings only when needed:
.\.venv\Scripts\python.exe -m xrdiag package $ResultsFolder --include-raw
# Script equivalent:
.\scripts\package_results.ps1 -ResultsFolder $ResultsFolder
```

Packaging validates original checksums before export, excludes raw/MCAP by default, uses an extension allowlist, and excludes hidden directories. `PACKAGE_CHECKSUMS.sha256` validates actual exported bytes after username redaction. Original manifests describe original evidence; redacted text can differ. Keep originals locally. Shared summaries retain necessary device identities, but avoid entering secrets in configuration paths. Review evidence before sharing. The ZIP path/name, size and SHA-256 are printed.

The receiving computer can verify the ZIP directly using `python -m xrdiag analyze <handoff.zip>` in its toolkit environment. This checks ZIP CRCs and every exported SHA-256 without extracting the recording.

Choose another drive or a path with spaces using `--output 'D:\Glove Evidence'`. Queue budgets (`--rgb-queue-mib 128`, `--depth-queue-mib 96`, `--glove-queue-mib 8`) and rotation thresholds (`--segment-mib 1024`, `--segment-seconds 60`) are configurable provisional defaults. JSON/base64 adds storage and CPU overhead. H05 qualifies this experimental Python pipeline only, never a future Rust recorder.

## Troubleshooting and AI operation

Use a known data cable, a direct USB port and adequate power. Bluetooth COM ports are unrelated. Close programs holding the selected port. If a device vanishes, preserve the failed run and retry discovery; do not reset automatically. For camera DLL failures verify 64-bit Python 3.11, reinstall pinned camera requirements into `.venv`, and repair the official Microsoft Visual C++ x64 runtime if needed. A separately installed SDK does not guarantee the Python wrapper is installed in this environment. Unsupported camera profiles are listed by doctor; changing one requires an explicit new request.

PlatformIO downloads can take minutes. If a mirror certificate fails, allow a verified alternate mirror or repair network certificates; never disable TLS verification. `$env:PYTHONUTF8='1'` fixes a Windows terminal Unicode error in PlatformIO output. Re-run the build after resolving network access. Low disk, queue overflow, or a partial MCAP fails explicitly; reduce the requested workload only in a new, documented run.

An on-site AI agent can be told: **“Read AGENTS.md and run all available GloveXR hardware diagnostic tests, then package the results.”** [AGENTS.md](AGENTS.md) contains real commands, prerequisite gates and final reporting requirements. The agent must stop for explicit approval before firmware replacement, rewiring, driver installation, device reset or other disruptive operations. It must preserve blocked tests, failures and simulation labels.

Detailed specifications and procedures are in [.docs/00_OVERVIEW.md](.docs/00_OVERVIEW.md), with the binary protocol, wiring template, metric definitions, portability acceptance and architecture decisions in the numbered documents.
