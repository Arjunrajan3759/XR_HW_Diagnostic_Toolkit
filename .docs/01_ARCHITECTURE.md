# Architecture

| Subsystem | Input | Output and purpose |
|---|---|---|
| CLI | Explicit arguments | Validated request, status and evidence folder; no automatic flash |
| Environment | Python/package/platform data | Path-free provenance and PlatformIO version |
| Serial adapter | Selected port | COBS packets, exact received bytes and HELLO identity; DTR/RTS disabled |
| Camera adapter | D435 identity and exact profile | Independent RGB8/Z16 frames with camera/host timestamps and calibration |
| Protocol | Byte stream | Validated packets plus explicit decode errors; bounded resynchronization |
| Simulation | Fixed seed, count, configuration | Labeled packets/frames/clock observations and intentional faults |
| Analysis | Raw observations | Percentiles, gaps/resets, throughput and midpoint clock fit |
| Experiments | Config and adapters | Prerequisite gates, measurements, criteria and status |
| Recorder | Per-topic messages | Byte-bounded queues, one writer, rotated MCAP, verification and explicit overflow |
| Reporting | Measurements and metadata | JSON/CSV/Markdown, manifests and validated ZIP handoff |

Firmware has a receive/command/scheduler task and separate USB transmit task joined by a 16-entry queue. Queue overflow enters FAULT and is counted. STOP returns to IDLE, without resetting cumulative counters. HELLO/STATUS remain available. Timing uses esp_timer_get_time microseconds; no ASCII console is configured on the binary stream. Boot ROM output before application startup can still exist and must resynchronize at a delimiter.

The byte codec is separate from scheduling and USB. Sensor drivers are deliberately absent until wiring and initialization prerequisites are verified; host and firmware expose this limitation instead of writing guessed I2C registers. The configuration template is evidence, not proof that sensors exist.

The recorder encodes raw bytes as base64 in JSON with an MCAP JSON schema. This is interoperable but adds approximately one third payload overhead before JSON. MCAP log_time/publish_time are host monotonic observations, not Unix epoch or synchronized device time. Source timestamps remain separate fields. No preview path exists. Bounded authoritative queues never overwrite data; overflow stops the source workflow with FAIL and preserves whatever finalized evidence is readable.

H05 simultaneous simulated sources use two producers. The physical camera and serial adapters are implemented individually, but physical H05 is gated before streaming because the only current firmware DATA source is a synthetic transport benchmark. It must never appear as real glove acquisition.
