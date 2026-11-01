import pytest
from xrdiag.analysis import stats, fit_clock
from xrdiag.simulation import clock_rows, glove_packets, camera_frames


def test_stats():
    assert stats([1, 2, 3, 4])["p50"] == 2.5
    assert stats([0, 100])["p95"] == 95
    assert stats([])["mean"] is None


def test_clock():
    rows = list(clock_rows())
    assert rows == list(clock_rows())
    fit = fit_clock(rows)
    assert abs(fit["drift_ppm"] - 25) < 2
    expected = 5_000_000 + fit["reference_host_ns"] * 25e-6
    assert abs(fit["offset_at_reference_ns"] - expected) < 20_000
    assert fit["physical_alignment"] == "BLOCKED_SETUP"
    with pytest.raises(ValueError):
        fit_clock([])


def test_simulation_faults():
    from xrdiag.protocol import Decoder
    from xrdiag.analysis import SequenceTracker

    assert list(glove_packets(12, 32, True)) == list(glove_packets(12, 32, True))
    decoder, tracker = Decoder(), SequenceTracker()
    for raw in glove_packets(12, 32, True):
        for p in decoder.feed(raw):
            tracker.add(p.boot, p.sequence)
    assert decoder.errors and tracker.gaps and tracker.duplicates and tracker.resets
    frames = list(camera_frames(0.2, 8, 8, 30, True))
    assert len(frames) == 11
    assert all(meta["mode"] == "SIMULATED" for _, meta, _ in frames)


def test_configurable_simulation_timestamps():
    from xrdiag.protocol import Packet

    packets = [Packet.decode(raw[:-1]) for raw in glove_packets(3, interval_us=10000)]
    assert [p.timestamp_us for p in packets] == [0, 10000, 20000]
    rows = list(clock_rows(4, interval_ns=25000000))
    assert rows[-1]["host_send_ns"] - rows[0]["host_send_ns"] == 75000000
