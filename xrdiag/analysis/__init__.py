"""Shared physical and simulated analysis."""

import math
import statistics


def stats(values):
    values = sorted(values)
    if not values:
        return {key: None for key in ("mean", "min", "max", "p50", "p95", "p99")}

    def percentile(p):
        pos = (len(values) - 1) * p
        lower = math.floor(pos)
        return values[lower] + (values[math.ceil(pos)] - values[lower]) * (pos - lower)

    return dict(
        mean=statistics.mean(values),
        min=values[0],
        max=values[-1],
        p50=percentile(0.5),
        p95=percentile(0.95),
        p99=percentile(0.99),
    )


class SequenceTracker:
    def __init__(self):
        self.boot = self.last = None
        self.gaps = self.duplicates = self.out_of_order = self.resets = 0

    def add(self, boot, seq):
        if self.boot is not None and boot != self.boot:
            self.resets += 1
            self.last = None
        if self.last is not None:
            delta = (seq - self.last) & 0xFFFFFFFF
            if delta == 0:
                self.duplicates += 1
            elif delta > 0x80000000:
                self.out_of_order += 1
                return
            else:
                self.gaps += delta - 1
        self.boot, self.last = boot, seq


def fit_clock(rows: list[dict]) -> dict:
    """Midpoint affine fit in ns, low-RTT half; no physical alignment claim."""
    if len(rows) < 4:
        raise ValueError("at least four clock observations required")
    ranked = sorted(
        rows,
        key=lambda r: (r["host_receive_ns"] - r["host_send_ns"])
        - (r["mcu_transmit_us"] - r["mcu_receive_us"]) * 1000,
    )
    accepted = ranked[: max(4, len(rows) // 2)]
    x = [(r["host_send_ns"] + r["host_receive_ns"]) / 2 for r in accepted]
    y = [(r["mcu_receive_us"] + r["mcu_transmit_us"]) * 500 for r in accepted]
    x0, y0 = x[0], y[0]
    xx, yy = [v - x0 for v in x], [v - y0 for v in y]
    mx, my = statistics.mean(xx), statistics.mean(yy)
    denom = sum((v - mx) ** 2 for v in xx)
    if denom == 0:
        raise ValueError("clock observations have no time span")
    slope = sum((a - mx) * (b - my) for a, b in zip(xx, yy)) / denom
    intercept = my - slope * mx
    residual = [b - (slope * a + intercept) for a, b in zip(xx, yy)]
    return dict(
        drift_ppm=(slope - 1) * 1e6,
        offset_at_reference_ns=y0 + intercept - x0,
        reference_host_ns=x0,
        residual_ns=stats(residual),
        rejected=len(rows) - len(accepted),
        round_trip_ns=stats([r["host_receive_ns"] - r["host_send_ns"] for r in rows]),
        physical_alignment="BLOCKED_SETUP",
        uncertainty="transport asymmetry unmeasured",
    )
