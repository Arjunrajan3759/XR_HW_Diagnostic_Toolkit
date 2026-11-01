import json
import pytest
from xrdiag.recording import ByteQueue, Recorder, verify, TOPICS


def test_queue():
    queue = ByteQueue(4)
    queue.put(b"abcd")
    with pytest.raises(BufferError):
        queue.put(b"x")
    assert queue.overflows == 1 and queue.maximum == 4
    assert queue.get() == b"abcd" and queue.occupancy == 0


def test_roundtrip_rotation(tmp_path):
    recorder = Recorder(tmp_path, "simulated", segment_bytes=5000)
    for topic in TOPICS:
        for i in range(3):
            recorder.submit(topic, dict(number=i, host_ns=100 + i), bytes(300))
    result = recorder.close()
    assert not result["writer_error"]
    assert result["incoming"] == result["recorded"] == result["verified"]
    assert result["writer_output_bytes_per_second"] > 0
    assert len(result["files"]) > 1
    assert not list(tmp_path.glob("*.partial"))
    from mcap.reader import make_reader

    with (tmp_path / result["files"][0]).open("rb") as stream:
        for _, _, message in make_reader(stream).iter_messages():
            assert json.loads(message.data)["mode"] == "SIMULATED"


def test_interrupted(tmp_path):
    recorder = Recorder(tmp_path, "simulated", interrupt_after=1)
    recorder.submit("/RGB", dict(host_ns=1), b"x")
    recorder.submit("/DEPTH", dict(host_ns=2), b"y")
    result = recorder.close()
    assert result["writer_error"] and list(tmp_path.glob("*.partial"))
    with pytest.raises(Exception):
        verify(next(tmp_path.glob("*.partial")))


def test_overload(tmp_path):
    recorder = Recorder(tmp_path, "simulated", budgets={"/RGB": 10}, delay=0.01)
    with pytest.raises(BufferError):
        recorder.submit("/RGB", dict(host_ns=1), bytes(100))
    result = recorder.close()
    assert result["queues"]["/RGB"]["overflows"] == 1
    assert result["incoming"] != result["recorded"]
