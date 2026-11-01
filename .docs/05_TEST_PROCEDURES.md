# Test procedures

Before any physical test, run doctor, review device identities, close programs holding devices, and approve any required firmware replacement separately. Save every failed/blocked run. Exact CLI arguments are in `python -m xrdiag run --help`. Default duration 2 seconds is a smoke test, not stability qualification.

## H01 acquisition

Run `run H01 --sensor-map <approved-copy.json>`. Without verified wiring, report BLOCKED_CONFIG with the missing-value checklist. Complete wiring alone is insufficient: the current firmware has no qualified sensor driver. Simulation `run H01 --mode simulated` generates labeled per-read rows (three synthetic sources, 1 kHz), start/end us, durations, intervals, deadlines and errors. It exercises the report/statistics path only. Physical acceptance must eventually cover every required sensor, initialization failures, actual rate, read-time p50/p95/p99, skew, errors and buffer occupancy under sustained load. Unknown wiring never triggers I2C writes.

## H02 transport

Select a confirmed idle diagnostic MCU with `--port`. Run exact payload/rate cases and `--sweep`; firmware rejects unsupported values. Use `--repetitions` and an explicit long `--duration` for stability after short cases pass. No sensor or I2C hardware is needed. START generates deterministic patterns through a bounded 16-packet queue. STOP drains queued data and ACKs; STATUS counters are saved. Record requested/achieved payload and encoded bytes/s, packet rate, host receive times, CRC/decode errors, gaps/duplicates/reordering/resets, firmware counters and delivered fraction. All raw read bytes survive in captures. A disconnect/timeout fails and leaves evidence.

Physical PASS requires nonzero telemetry, >=99% requested payload delivery, no corruption, sequence errors, resets, firmware TX errors/overflows or missed scheduler deadlines during the case. This is a case result, not a global sustainable-rate guarantee. Compare successful sustained cases and repetitions; failed high-rate cases remain visible. A 30% throughput/H01-rate headroom criterion is provisional. If no physical H01 requirement exists, headroom is undetermined. `--sensor-bytes-per-second` records an explicit operator-supplied requirement, not proof of H01.

## H03 D435

Run `run H03 --duration 10`; use `--camera-serial` for multiple D435s. The default exact request is RGB8 + native Z16, 640x480 at 30 FPS. Capabilities, firmware, USB info, intrinsics, depth scale and available metadata are saved. Unsupported profiles fail; consult capabilities and explicitly request a different profile in a new run. Each stream has separate counts, original timestamp/domain, host reception timestamp and intervals. PASS requires both streams, no frame-number gaps/duplicates/reordering, >=90% expected count (startup/end tolerance), and no SDK exception/timeout. This count tolerance is provisional. With `--record-camera`, MCAP must also finalize/read/count correctly. Metadata-only mode does not save raw pixels and says so. No authoritative depth conversion or colorization occurs.

## H04 clocks and physical validation

Run `run H04 --port <selected-port> --duration 10` on an idle MCU. Save host t1, MCU t2/t3 and host t4. Fit on the lowest-RTT half, minimum four points; reject reset-spanning fits. A completed MCU-host fit is retained as OBSERVED; overall physical H04 remains BLOCKED_SETUP until physical alignment is validated. Missing camera observations are marked separately. If a D435 is available collect source timestamp/domain and host receipt in a separate file. Camera and exchange capture currently happen sequentially; this does not establish a simultaneous multi-clock mapping.

For a separate physical-event validation, first obtain hardware-owner approval of equipment and wiring. One candidate setup needs a visible LED driven by a verified GPIO (with appropriate current limiting), a sensor/event input whose response is recorded, and camera visibility of the same event; another may use a documented shared mechanical event detectable by actual sensors and camera. Neither setup is presumed present. Document event detectability, exposure/rolling-shutter latency, sensor filtering, detector threshold, and repeated event residuals. Until approved equipment and a validated event detector exist, physical alignment is BLOCKED_SETUP. Never infer sub-millisecond physical precision from the clock-fit residual alone.

## H05 combined recording

Physical mode checks D435 and then blocks on unqualified acquisition; it never relabels synthetic DATA as sensor evidence. Simulation `run H05 --mode simulated --duration 2` runs paced glove and camera sources together. Required topics are /glove/samples, /RGB, /DEPTH, /sync/observations and /system/events. Queue budgets count serialized JSON bytes, including base64 overhead, and do not overwrite. Overflow explicitly fails and stops producers. `--writer-delay-ms`, `--faults`, and `--interrupt-after` are simulated failure tools, forbidden in physical mode.

Before recording check free disk against raw estimated rate times 1.5 plus 64 MiB reserve. Rotation thresholds default to 1 GiB and 60 seconds; accounting includes serialized bytes plus conservative envelope reserve. A message larger than the segment budget fails before enqueue. Writer emits .partial until finish/fsync/readback succeeds, then renames .mcap. Verify finalized topic counts, source-versus-recorded counts, overflow counters and SHA-256. An interrupted .partial remains incomplete and packaging refuses it. Stress tests qualify the Python experimental recorder, never Rust performance.
