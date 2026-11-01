# Troubleshooting

| Symptom | Meaning and repair |
|---|---|
| Python 3.13 runs from PATH | Use py -3.11 and repository .venv; scripts validate the version |
| Existing .venv incompatible | Preserve it; ask its owner to relocate/archive it before a new environment is created |
| pip wheel missing | Verify Windows AMD64 CPython 3.11 and pinned groups; capture install error, do not install random binaries |
| PlatformIO not found | Install Core or VS Code extension; restart terminal; supported per-user penv is checked |
| PlatformIO UnicodeEncodeError | Set PYTHONUTF8=1; scripts do this |
| Compiler download certificate error | Retry verified mirrors/repair network trust; never disable TLS verification |
| COM device BUSY | Close serial monitor/other application; never forcibly reset it |
| WRONG_FIRMWARE | Selected port lacks diagnostic HELLO; do not automatically upload |
| UNSUPPORTED_VERSION | Firmware/host protocol mismatch; coordinate versions with approval |
| Device disappears | Preserve FAIL evidence; reconnect only with operator involvement and rediscover |
| Only Bluetooth ports listed | No diagnostic USB MCU is identified; use a USB data cable and inspect Device Manager |
| H01 BLOCKED_CONFIG | Supply verified wiring, review drivers; do not guess pins/mux channels |
| RealSense NOT_INSTALLED | Install requirements-camera in the exact .venv; review version/architecture/import error |
| RealSense NOT_CONNECTED | SDK wrapper works; check cable, power, USB port and Device Manager |
| Camera profile fails | Read saved capabilities; explicitly choose a supported exact profile in a new run |
| SDK timeout or missing stream | Close Viewer/other capture program; check USB bandwidth; FAIL is preserved |
| Camera clock jumps/domain changes | Preserve original observations; do not assume one affine camera mapping |
| Queue overflow | Required-stream data was not overwritten; failed run retains counters, adjust workload in a new run |
| Insufficient disk | Choose --output on a suitable volume or explicitly shorten duration |
| .mcap.partial remains | Incomplete/interrupted session; do not rename it as successful or package as finalized |
| Checksum mismatch | Evidence changed or is incomplete; investigate originals rather than resealing to hide it |

No troubleshooting command should silently alter drivers, camera firmware, eFuses, production calibration or wiring. Preserve logs before intervention. Scripts log in results/script_logs, outside experiment packages; review personal paths before sharing those transcripts.
