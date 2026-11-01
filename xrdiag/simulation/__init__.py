"""Fixed-seed sources. Every output is simulated, never device evidence."""

import random
from xrdiag.protocol import Packet, DATA, pattern


def glove_packets(count, size=128, faults=False, interval_us=1000):
    for seq in range(count):
        if faults and seq == 3:
            continue
        packet = Packet(
            DATA,
            sequence=seq,
            boot=2 if faults and seq >= 8 else 1,
            timestamp_us=int(seq * interval_us),
            payload=pattern(seq, size),
        )
        raw = packet.encode()
        if faults and seq == 5:
            raw = raw[:-3] + bytes([raw[-3] ^ 1]) + raw[-2:]
        yield raw
        if faults and seq == 6:
            yield raw


def clock_rows(
    count=100, seed=42, drift_ppm=25, offset_ns=5_000_000, interval_ns=100_000_000
):
    rng = random.Random(seed)
    for i in range(count):
        send = 1_000_000_000 + int(i * interval_ns)
        forward, reverse = (
            100_000 + rng.randrange(-5000, 5001),
            100_000 + rng.randrange(-5000, 5001),
        )
        receive = send + forward
        device = (receive * (1 + drift_ppm / 1e6) + offset_ns) / 1000
        yield dict(
            mode="SIMULATED",
            host_send_ns=send,
            mcu_receive_us=device,
            mcu_transmit_us=device + 10,
            host_receive_ns=receive + 10_000 + reverse,
        )


def camera_frames(duration, width=640, height=480, fps=30, gaps=False):
    for i in range(max(1, int(duration * fps))):
        for topic, bpp, fmt in (("/RGB", 3, "RGB8"), ("/DEPTH", 2, "Z16")):
            if gaps and i == 3 and topic == "/DEPTH":
                continue
            yield (
                topic,
                dict(
                    mode="SIMULATED",
                    number=i,
                    source_timestamp_ms=i * 1000 / fps,
                    timestamp_domain="SIMULATED_DEVICE",
                    host_ns=1_000_000_000 + int(i * 1e9 / fps),
                    width=width,
                    height=height,
                    format=fmt,
                    stride=width * bpp,
                    depth_scale=0.001 if topic == "/DEPTH" else None,
                    intrinsics=None,
                ),
                bytes([i % 256]) * (width * height * bpp),
            )
