# On-site agent workflow

1. Read root AGENTS.md and BUILD_REPORT. Inspect local changes and preserve user files/environment. Explain the intended non-destructive checks.
2. Run setup with approved optional groups; pip check; doctor; pytest. Resolve missing package/network issues without system driver changes. Build firmware without flashing.
3. Read actual discovery JSON. Passive COM presence is not diagnostic identification. Request operator selection for an unknown port. Probe only a confirmed idle device. If firmware is wrong, leave physical tests blocked until explicit approval and recovery preparation exist.
4. Run full simulation and validate its evidence. Do not reuse simulator metrics in physical reports.
5. Run all available physical experiments with explicit port/camera choice where necessary. Unknown wiring blocks H01/H05. Unsupported profiles fail; do not silently retry downgraded. Missing devices block; continue independent experiments.
6. Preserve source data, failures, blockers, cumulative counters and exact requests. Use analyze on the combined run; inspect MCAP read-back counts and SHA-256. Package reports by default and include raw only when requested. Reject incomplete/corrupt evidence.
7. Report actual commands, exit codes, software test count, build state, device identities, every experiment status/reason, mode, evidence paths, package size/hash and unanswered physical questions. Explain which architecture choices the evidence can support.

Approval boundaries: firmware upload/erase/restore, eFuses, sensor rewiring, device resets, system driver installation, camera firmware/configuration changes and any potentially disruptive operation. A test agent must stop dependent work there and ask the operator with a concrete explanation; continue safe independent analysis/package work. Scripts never provide blanket permission. Existing user approval may authorize a specific selected action, not unrelated devices.

Physical-event equipment and a verified detector are external prerequisites. No software clock fit resolves that gate. Physical H05 is intentionally unavailable until actual acquisition is qualified; report the current limitation candidly instead of feeding benchmark packets to /glove/samples.
