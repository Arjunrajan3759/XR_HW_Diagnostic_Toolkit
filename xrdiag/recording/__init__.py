"""Bounded byte queues and single-writer MCAP pipeline."""

from collections import deque, Counter
import json
from pathlib import Path
import threading
import time

TOPICS = ("/glove/samples", "/RGB", "/DEPTH", "/sync/observations", "/system/events")


class ByteQueue:
    def __init__(self, budget):
        if budget <= 0:
            raise ValueError("queue budget must be positive")
        self.budget = budget
        self.items = deque()
        self.occupancy = self.maximum = self.overflows = 0

    def put(self, item):
        size = len(item)
        if self.occupancy + size > self.budget:
            self.overflows += 1
            raise BufferError(
                "Required-stream queue overflow; recording stopped explicitly"
            )
        self.items.append(item)
        self.occupancy += size
        self.maximum = max(self.maximum, self.occupancy)

    def get(self):
        item = self.items.popleft()
        self.occupancy -= len(item)
        return item


def verify(path):
    from mcap.reader import make_reader

    counts = Counter()
    with Path(path).open("rb") as stream:
        reader = make_reader(stream, validate_crcs=True)
        if reader.get_summary() is None:
            raise ValueError("MCAP missing summary/footer; incomplete file")
        for _, channel, message in reader.iter_messages():
            value = json.loads(message.data)
            if "mode" not in value:
                raise ValueError("Message missing provenance")
            counts[channel.topic] += 1
    return dict(counts)


class Recorder:
    def __init__(
        self,
        folder,
        mode,
        budgets=None,
        segment_bytes=1024**3,
        segment_seconds=60,
        delay=0,
        interrupt_after=0,
    ):
        from mcap.writer import (
            Writer,
        )  # fail before starting worker if optional dependency absent

        self.writer_type = Writer
        self.folder, self.mode = Path(folder), mode.upper()
        budgets = budgets or {
            "/RGB": 128 * 1024**2,
            "/DEPTH": 96 * 1024**2,
            "/glove/samples": 8 * 1024**2,
        }
        self.queues = {t: ByteQueue(budgets.get(t, 1024**2)) for t in TOPICS}
        self.segment_bytes, self.segment_seconds = segment_bytes, segment_seconds
        self.delay, self.interrupt_after = delay, interrupt_after
        self.condition = threading.Condition()
        self.done = False
        self.error = None
        self.incoming, self.recorded = Counter(), Counter()
        self.latencies = []
        self.files = []
        self.finalization_seconds = 0
        self.start_ns = time.perf_counter_ns()
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def submit(self, topic, metadata, raw=b""):
        import base64

        value = dict(
            metadata, mode=self.mode, raw_base64=base64.b64encode(raw).decode("ascii")
        )
        encoded = json.dumps(value, separators=(",", ":")).encode()
        if len(encoded) + 4096 > self.segment_bytes:
            raise BufferError(
                "One encoded message exceeds segment budget; increase --segment-mib explicitly"
            )
        with self.condition:
            if self.error:
                raise RuntimeError(self.error)
            self.incoming[topic] += 1
            self.queues[topic].put(encoded)
            self.condition.notify()

    def _open(self):
        from mcap.writer import CompressionType

        path = self.folder / f"segment_{len(self.files):04d}.mcap.partial"
        self.stream = path.open("wb")
        self.writer = self.writer_type(
            self.stream, compression=CompressionType.NONE, enable_crcs=True
        )
        self.writer.start(profile="glovexr-json-v1")
        schema = self.writer.register_schema(
            "glovexr.record.v1",
            "jsonschema",
            json.dumps(
                {
                    "type": "object",
                    "required": ["mode", "raw_base64"],
                    "properties": {
                        "mode": {"enum": ["PHYSICAL", "SIMULATED"]},
                        "raw_base64": {"type": "string"},
                    },
                }
            ).encode(),
        )
        self.channels = {
            t: self.writer.register_channel(t, "json", schema) for t in TOPICS
        }
        self.path, self.segment_start = path, time.perf_counter()
        self.segment_written = 0
        self.segment_payload_bytes = 0

    def _finalize(self):
        start = time.perf_counter()
        self.writer.finish()
        self.stream.flush()
        import os

        os.fsync(self.stream.fileno())
        self.stream.close()
        final = self.path.with_suffix("")
        verify(self.path)
        self.path.rename(final)
        self.files.append(final)
        self.finalization_seconds += time.perf_counter() - start

    def _worker(self):
        try:
            self._open()
            while True:
                with self.condition:
                    self.condition.wait_for(
                        lambda: self.done or any(q.items for q in self.queues.values())
                    )
                    item = next(
                        ((t, q.get()) for t, q in self.queues.items() if q.items), None
                    )
                    if item is None and self.done:
                        break
                if item:
                    topic, data = item
                    if (
                        self.interrupt_after
                        and sum(self.recorded.values()) >= self.interrupt_after
                    ):
                        raise RuntimeError(
                            "SIMULATED interrupted recording; .partial preserved"
                        )
                    if self.segment_written and (
                        self.segment_payload_bytes + len(data) + 4096
                        >= self.segment_bytes
                        or time.perf_counter() - self.segment_start
                        >= self.segment_seconds
                    ):
                        self._finalize()
                        self._open()
                    stamp = json.loads(data).get("host_ns", time.perf_counter_ns())
                    start = time.perf_counter()
                    if self.delay:
                        time.sleep(self.delay)
                    self.writer.add_message(
                        self.channels[topic],
                        stamp,
                        data,
                        publish_time=stamp,
                        sequence=self.recorded[topic],
                    )
                    self.latencies.append((time.perf_counter() - start) * 1000)
                    self.recorded[topic] += 1
                    self.segment_written += 1
                    self.segment_payload_bytes += len(data) + 64
            self._finalize()
        except Exception as error:
            self.error = str(error)
            if hasattr(self, "stream"):
                self.stream.close()

    def close(self):
        with self.condition:
            self.done = True
            self.condition.notify_all()
        self.thread.join()
        from xrdiag.analysis import stats

        counts = Counter()
        for file in self.files:
            counts.update(verify(file))
        elapsed_seconds = max((time.perf_counter_ns() - self.start_ns) / 1e9, 1e-9)
        output_bytes = sum(f.stat().st_size for f in self.files)
        return dict(
            incoming=dict(self.incoming),
            recorded=dict(self.recorded),
            verified=dict(counts),
            queues={
                t: dict(maximum_bytes=q.maximum, overflows=q.overflows, budget=q.budget)
                for t, q in self.queues.items()
            },
            writer_error=self.error,
            write_latency_ms=stats(self.latencies),
            finalization_seconds=self.finalization_seconds,
            bytes=output_bytes,
            writer_elapsed_seconds=elapsed_seconds,
            writer_output_bytes_per_second=output_bytes / elapsed_seconds,
            files=[f.name for f in self.files],
            recording_encoding="JSON with base64 raw pixels; log_time=host monotonic ns, no alignment claim",
        )
