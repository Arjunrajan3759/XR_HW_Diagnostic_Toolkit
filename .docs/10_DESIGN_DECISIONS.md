# Evidence-driven design decisions

| Question | Provisional value | Evidence needed |
|---|---|---|
| Sensor scheduling | Not selected | Approved map, drivers, H01 sustained per-sensor timing/errors/skew |
| Payload limit | 1024 decoded / 998 payload | Real acquisition schema and frame overhead; no truncation |
| USB offered rate | Sweep 100/500/1000 packets/s | H02 repeated sustained zero-loss cases on target laptops/cables |
| Bandwidth headroom | >=30% above sensor requirement | Physical H01 payload rate and H02 sustained throughput |
| Camera profile | RGB8/Z16 640x480 at 30 FPS | D435 exact capability and H03 sustained capture |
| Clock model | Low-RTT midpoint affine estimate | H04 real exchange, camera domains and reset handling |
| Physical synchronization | Undecided; BLOCKED_SETUP | Approved shared event apparatus and repeated event residuals |
| Queue budgets | RGB128/Depth96/Glove8 MiB | H05 queue occupancy, slow disk/overflow tests and memory |
| Segment thresholds | 1 GiB / 60 seconds | Disk latency, finalization overhead, recovery/transfer needs |
| Recorder architecture | Experimental Python one writer | MCAP integrity and no-loss counts; separate Rust qualification later |

H02 synthetic data isolates transport; it cannot prove sensor acquisition. H03 framesets request both streams but preserve them independently; frameset delivery is not proof of physical exposure simultaneity. H04 fits software clocks without claiming physical alignment. JSON/base64 MCAP is chosen for minimal schema tooling and reader interoperability; its overhead is explicitly part of this experiment, not a production encoding recommendation.

To decide an architecture parameter, record decision/date/owner, exact physical evidence folder and checksums, tested scope, observed result/uncertainty, chosen value, and revalidation triggers (firmware, SDK, hardware, cable, OS, recorder changes). Combined qualification reports point to evidence and retain blockers. Simulated results validate analyzers and failure handling only; they cannot close hardware design decisions.
