# Overview

GloveXR qualification gathers reproducible evidence for acquisition scheduling, USB transport, RGB/depth streaming, clock estimation and experimental recording. It does not replace production firmware or the future Daemon 1.1 Rust implementation.

H01 = sensor acquisition; H02 = synthetic USB transport; H03 = independent RGB/depth; H04 = clock observations and estimator; H05 = combined recording. PHYSICAL describes actual device observations. SIMULATED describes generated data, including raw protocol captures and all MCAP messages created by simulated sources. BLOCKED is a prerequisite failure, not a successful test.

The default duration is two seconds to limit storage. Longer stability tests require explicit duration. Rates, queue budgets, segment thresholds and 30% headroom are provisional. Only physical evidence can validate hardware limits.

Current external gates: approved glove wiring, qualified sensor drivers, diagnostic firmware approved for deployment, actual D435/MCU access, and physical-event equipment. Read README for setup and BUILD_REPORT for executed verification. No production sensor register is written by the current firmware.
