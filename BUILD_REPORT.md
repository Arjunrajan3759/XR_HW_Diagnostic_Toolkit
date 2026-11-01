# GloveXR implementation and final verification report

Verified on 2026-11-02 local time (Asia/Calcutta). Evidence directory timestamps use UTC, so these runs begin with 20261101. Host: Windows AMD64, OS build 10.0.26200, Python 3.11.9 in the preserved original .venv, PlatformIO Core 6.2.0.

## Implementation delivered

The repository contains the Python CLI, passive device discovery, selected-port diagnostic HELLO, matching Python/C COBS and CRC protocol, deterministic simulation and faults, H01?H05 workflows, raw evidence collection, shared statistical/clock analysis, bounded MCAP queues and one writer, rotation, finalization/readback, SHA-256 validation, ZIP export/verification, all six requested PowerShell scripts, root AGENTS.md, beginner README and eleven knowledge-base documents. Source/configuration fingerprints accompany experiment results.

Firmware targets seeed_xiao_esp32c6 with espressif32@8.0.0 and ESP-IDF. It implements explicit IDLE/USB_BENCH/FAULT states, identity/status, request ACK/errors, synthetic USB payload generation, a bounded TX queue, timestamp exchange and cumulative diagnostics. Byte-level serialization avoids structure padding. The application console is disabled; the startup self-test checks CRC and a shared encoded HELLO vector.

**Real sensor acquisition is not implemented against guessed wiring.** H01 has a complete proposed inventory, copyable bus/mux record templates, exact missing-value checklist and BLOCKED_CONFIG gate. Actual drivers require verified electrical/register configuration and assembly validation. Physical H05 is deliberately unavailable until that acquisition exists; synthetic USB data is never relabeled as physical glove samples. H04 stores available clock observations but physical alignment remains BLOCKED_SETUP.

## Final executed checks

| Check | Observed outcome |
|---|---|
| Python tests through run_all_tests.ps1, simulated branch | **43 passed in 12.60 seconds**, script exit 0 |
| Python tests through run_all_tests.ps1, physical branch | **43 passed in 11.07 seconds**, script exit 2 after hardware prerequisites were found blocked |
| Separate fresh environment in a relocated folder with spaces | **43 passed in 13.01s**; setup/simulation/repeated setup all exited 0 |
| Optional camera dependency in that fresh environment | NOT_INSTALLED, with useful repair instructions; full software suite still passed |
| Pinned requirement groups in original environment | Installed together; pip check reported no broken requirements |
| Ruff and Python byte compilation | Passed |
| PowerShell syntax parsing | All scripts passed |
| Setup, environment check, build, run-all and packaging scripts | Executed successfully; both run-all exit 0 and blocked exit 2 were verified |
| Native command logging | stdout/stderr retained and intentional exit 7 preserved; transcripts are supplemented by .native.txt logs |
| Flash script safety | Refusal without recovery confirmation tested before any port access/upload; no actual flash attempted |
| Complete two-second simulation | H01?H05 all **SIMULATED_PASS** |
| Hardware-absent run | H01?H05 all **BLOCKED**; no hardware PASS |
| MCAP readback | CRCs/footer/readability valid; 200 glove, 60 RGB, 60 depth, 1 sync observation, 1 system event |
| Original evidence integrity | Required files, completion flags and SHA-256 validated |
| ZIP integrity | ZIP CRCs plus every PACKAGE_CHECKSUMS entry verified, with and without explicit raw inclusion |
| Deliberate bad CRC/missing/duplicate/reset transport | FAIL with exit 1, as expected; CRC failures explicitly verified |
| Deliberately interrupted recording | FAIL with exit 1; .partial retained and detected as incomplete |
| Deliberate queue overload/slow writer | FAIL with exit 1; incoming/recorded mismatch and overflow explicit |
| Firmware | **Compiled successfully**, including final 4 MiB configuration and logged incremental rebuild |

The 43 tests cover COBS edge cases, CRC/golden vectors, partial/multiple/corrupt/oversized frames, sequence wrap/gaps/duplicates/reordering/resets, interleaved ACK/telemetry framing, resets visible only in final command responses, partial metrics after disconnect, safe mocked discovery/disappearance, deterministic sources/timestamps, clock estimation against known parameters, percentiles, invalid CLI requests, missing devices/dependencies, queue overload, MCAP writing/reading/rotation/interruption, report provenance, retained observations, manifests, packaging, privacy redaction (including usernames with spaces), unrelated-file exclusion, flash refusal and source relocation.

No unresolved unit/integration test or firmware compilation failure remains. Intentionally injected experiment failures remain FAIL in their evidence; they were never converted into successful qualification.

## Firmware build verification

The installed pinned platform selected ESP-IDF 6.1.0 (framework package 4.60100.0), GCC 15.2.0+20251204, CMake 3.30.2 and esptool 5.4.0. The initial tool/SDK installation and first successful build took 1993.25 seconds. Some package mirrors failed TLS hostname checks; verified alternate mirrors succeeded with TLS verification left enabled.

ESP-IDF initially generated a 2 MiB image configuration while the pinned board definition specifies 4 MiB. The project default and only this session-generated SDK configuration were corrected to 4 MiB. No original user configuration was removed, and no device was accessed. The corrected full build succeeded in 495.09 seconds, and the final explicitly logged incremental build succeeded in 5.96 seconds without that mismatch warning. Upstream Bluetooth/FAT Kconfig boolean-default notes remain informational; the application does not initialize those subsystems.

Static linker RAM is 10276 bytes and program usage is 149682 bytes in the 1 MiB factory app partition. These are build-time figures, not measured runtime heap usage. The device image configuration is 4 MiB; primary/secondary consoles are disabled, main-task stack is 8192 bytes and FreeRTOS is configured at 1000 Hz.

Final firmware.bin is **150288 bytes** with SHA-256 **211b6a75126f96facb7f1fecac69e1ed221329bc950dd21ca6af8ddaf2093c85**. ELF, bootloader, partition hashes and native build log names are in results/firmware_build.json. Binaries are under the ignored PlatformIO build directory. **A build is not physical MCU validation; nothing was flashed, erased or reset.**

## Final evidence and transfer packages

Machine-readable acceptance: `results/FINAL_VERIFICATION.json`.

Simulated release: `results/release/20261101T201624_qualification_a3d2754a`.

Blocked physical release: `results/physical release/20261101T201844_qualification_b71d5eca`.

Each contains its qualification report, experiment summaries, environment, exact request configuration, source hashes and original evidence manifests. No physical camera or glove measurements were invented. Earlier development runs remain separately identifiable by their own timestamps and source hashes.

| Package mode | Relative location | Bytes | SHA-256 |
|---|---|---:|---|
| SIMULATED_PASS reports | `results/release/20261101T201624_qualification_a3d2754a/20261101T201624_qualification_a3d2754a_handoff_b2b240e6.zip` | 98452 | `769b542addfea8de835ce33bf12d3083b52a2dffe81fa36e25e1a87b85ce9228` |
| SIMULATED with raw | `results/release/20261101T201624_qualification_a3d2754a/20261101T201624_qualification_a3d2754a_handoff_fdfa9a05.zip` | 302770 | `6175d000169907010b65837a2ac80a84d616bc9260b283a4209cec00dc8bedcf` |
| BLOCKED reports | `results/physical release/20261101T201844_qualification_b71d5eca/20261101T201844_qualification_b71d5eca_handoff_d9f63621.zip` | 44664 | `5daaf2ef4b9c23889506478ab828485fcb1275f0bddf29b391428d052ca13293` |

The reports-only simulated ZIP validates 60 exported files; its explicit raw-inclusive counterpart validates 63. The blocked physical ZIP validates 51. Synthetic uniform pixels compress unusually well; these ZIP sizes predict neither real-camera storage nor production performance. Exported text is privacy-redacted, so PACKAGE_CHECKSUMS validates exported bytes while original manifests describe originals.

Portable fresh-environment evidence: `results/relocated_windows_setup.json`; the generated test clone is `results/portability clone with spaces b9671519`. Its environment was created separately and left in place; the original .venv was never removed or replaced. This verifies relocation and fresh dependencies on this Windows machine, not every possible laptop/driver installation.

## Physical work still blocked or unvalidated

- **H01:** Supply an owner-approved pin/bus/address/mux/electrical profile, implement and review appropriate sensor drivers, then validate initialization, every sensor's actual readings, rate, timing/skew, I2C errors and buffering. The proposed 13 sensor components and two muxes are not confirmation of assembled wiring.
- **H02:** Obtain a production recovery image and explicit approval before deploying diagnostics to a selected XIAO. Validate actual HELLO/USB behavior, short sweeps, sustained repeated zero-loss cases, disconnect/reset behavior and real H01 bandwidth headroom. Only unrelated Bluetooth COM ports appeared here; none were opened.
- **H03:** Connect the D435 on site, verify the exact profile, capture RGB8/Z16, inspect USB/counters/domains/intrinsics/depth scale and test sustained optional recording. The wrapper imported here but returned NOT_CONNECTED; no physical camera frames were captured.
- **H04:** Collect actual MCU-host exchanges and camera clock observations. Shared physical-event equipment, approved wiring and a validated event detector remain external prerequisites. Camera and MCU observation capture is currently sequential, not a simultaneous multi-clock mapping. Clock-fit residuals cannot prove physical alignment.
- **H05:** Qualify real H01 acquisition before enabling a real glove sample adapter. Then validate both physical sources together, queues, disk behavior, interruptions and counts. The implemented simulated pipeline qualifies only this experimental Python recorder, never a future Rust daemon.

## Known limits and repaired development issues

The sensor profile is a checklist, not an electrical validation system. Existing production calibration/settings are never changed. Serial opening cannot guarantee the behavior of every Windows driver even with DTR/RTS disabled; therefore discovery is passive unless an idle port is explicitly selected. Firmware offers 1?1000 benchmark packets/s, rejects unsupported parameters, and never truncates a payload. Maximum decoded frame is 1024 bytes including the 26-byte envelope; maximum payload is 998.

Camera requests never silently downgrade. Metadata-only H03 is the default; authoritative pixels are saved only when recording is requested. Physical adapters remain untested on actual target devices. Physical synchronization is unqualified even when an MCU clock fit exists.

MCAP JSON/base64 adds CPU/storage overhead. Queue budgets count serialized bytes, not whole-process memory. Writer latency includes library buffering; output throughput includes producer waiting and verification, not isolated disk speed. The 128/96/8 MiB queue budgets, 1 GiB/60-second segment thresholds and 30% headroom are provisional. Long runs retain metadata rows in memory; begin short, check disk and monitor resources. Static firmware sizes do not validate runtime heap or scheduler behavior.

An early test exposed rotation undercounting due to MCAP chunk buffering; serialized-byte accounting fixed it. Serial review corrected shared decoder state across START/STOP ACKs and telemetry. Endpoint boot tracking catches resets with no later DATA packet. Disconnect tests preserve partial metrics and prevent missing final counters from canceling historical errors. A wall-time-sensitive mocked clock test failed under compiler load because it captured fewer than four observations; the product correctly rejected that fit, and the test now uses a deterministic clock. Native transcript omission was repaired with explicit native-output logging. All final checks pass.

Privacy export redacts conventional Windows home paths and includes only manifest-listed allowed evidence. It cannot recognize arbitrary operator-supplied secrets/custom paths; review before sharing. Script transcripts/native logs can contain local paths and stay outside experiment packages. Keep mode sidecars with simulated raw binary; never present raw simulator packets alone as physical data.

## Exact setup and operating commands

Run from the repository root in normal PowerShell; no environment activation or administrator privileges are required:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup_windows.ps1 -Camera -Recording -Dev
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check xrdiag tests
.\scripts\build_firmware.ps1
.\.venv\Scripts\python.exe -m xrdiag doctor
.\.venv\Scripts\python.exe -m xrdiag simulate --duration 2
.\.venv\Scripts\python.exe -m xrdiag run-all --duration 10
# Only after the operator confirms the idle diagnostic MCU port:
$GlovePort = Read-Host 'Confirmed XIAO COM port'
.\.venv\Scripts\python.exe -m xrdiag doctor --probe-port $GlovePort
.\.venv\Scripts\python.exe -m xrdiag run-all --port $GlovePort --duration 10
$ResultsFolder = Read-Host 'Results folder printed by the run'
.\.venv\Scripts\python.exe -m xrdiag analyze $ResultsFolder
.\.venv\Scripts\python.exe -m xrdiag package $ResultsFolder
```

Use `analyze <handoff.zip>` to validate exported ZIP CRCs/hashes directly. Add `--include-raw` to package only when requested. Exit 0 means completed, 1 means failed and 2 means blocked; a blocked hardware run is not successful qualification. AGENTS.md contains the on-site agent workflow, README contains individual experiment commands, and .docs contains detailed procedures. Firmware replacement, recovery, hardware rewiring, driver installation and camera changes remain operator approval boundaries.
