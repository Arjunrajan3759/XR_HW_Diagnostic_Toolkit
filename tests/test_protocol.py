import json
from pathlib import Path
import struct
import zlib
import pytest
from xrdiag.protocol import Packet, Decoder, cobs_encode, cobs_decode, pattern, HEADER
from xrdiag.analysis import SequenceTracker


@pytest.mark.parametrize(
    "raw", [b"", b"\0", b"abc", bytes(range(256)), bytes(700), bytes([255]) * 998]
)
def test_cobs(raw):
    assert cobs_decode(cobs_encode(raw)) == raw
    assert b"\0" not in cobs_encode(raw)


def test_vector():
    assert zlib.crc32(b"123456789") == 0xCBF43926
    vectors = json.loads(
        (Path(__file__).parent / "fixtures/protocol_vectors.json").read_text()
    )
    for vector in vectors:
        packet = Packet(
            **{**vector["packet"], "payload": bytes.fromhex(vector["payload_hex"])}
        )
        assert packet.encode().hex() == vector["encoded_hex"]
        assert Packet.decode(packet.encode()[:-1]) == packet


def test_partial_multiple_corrupt_recovery():
    packet = Packet(6, sequence=12, boot=44, payload=pattern(12, 512))
    wire = packet.encode()
    decoder = Decoder()
    assert decoder.feed(wire[:10]) == []
    assert decoder.feed(wire[10:] + wire) == [packet, packet]
    corrupted = bytearray(wire)
    corrupted[-3] ^= 3
    assert decoder.feed(corrupted + wire) == [packet]
    assert decoder.errors
    assert decoder.feed(b"X" * 3000 + b"\0" + wire) == [packet]
    assert "oversized frame discarded" in decoder.errors


def test_invalid_version_length_crc():
    raw = HEADER.pack(2, 1, 1, 0, 0, 0, 0)
    encoded = cobs_encode(raw + struct.pack("<I", zlib.crc32(raw)))
    with pytest.raises(ValueError, match="version"):
        Packet.decode(encoded)
    with pytest.raises(ValueError):
        Packet(6, payload=bytes(999)).encode()
    with pytest.raises(ValueError):
        cobs_decode(b"\x04a")


def test_sequence():
    tracker = SequenceTracker()
    for boot, seq in [(1, 0), (1, 2), (1, 2), (1, 1), (2, 0), (2, 1)]:
        tracker.add(boot, seq)
    assert (tracker.gaps, tracker.duplicates, tracker.out_of_order, tracker.resets) == (
        1,
        1,
        1,
        1,
    )
    wrap = SequenceTracker()
    wrap.add(1, 0xFFFFFFFF)
    wrap.add(1, 0)
    assert wrap.gaps == 0
