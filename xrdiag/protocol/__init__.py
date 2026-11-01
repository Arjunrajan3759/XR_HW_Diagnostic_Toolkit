"""Protocol v1; see .docs/03_FIRMWARE_PROTOCOL.md."""

from dataclasses import dataclass
import struct
import zlib

VERSION = 1
MAX_DECODED = 1024
HEADER = struct.Struct("<BBHIIQH")
HELLO, STATUS, START, STOP, SYNC, DATA, ERROR = 1, 2, 3, 4, 5, 6, 127


def cobs_encode(data: bytes) -> bytes:
    out = bytearray([0])
    index, code = 0, 1
    for value in data:
        if value == 0:
            out[index] = code
            index, code = len(out), 1
            out.append(0)
        else:
            out.append(value)
            code += 1
            if code == 255:
                out[index] = code
                index, code = len(out), 1
                out.append(0)
    out[index] = code
    return bytes(out)


def cobs_decode(data: bytes) -> bytes:
    out, index = bytearray(), 0
    while index < len(data):
        code = data[index]
        if not code or index + code > len(data):
            raise ValueError("invalid COBS")
        out.extend(data[index + 1 : index + code])
        index += code
        if code != 255 and index < len(data):
            out.append(0)
    return bytes(out)


@dataclass(frozen=True)
class Packet:
    kind: int
    request: int = 0
    sequence: int = 0
    boot: int = 0
    timestamp_us: int = 0
    payload: bytes = b""

    def encode(self) -> bytes:
        raw = (
            HEADER.pack(
                VERSION,
                self.kind,
                self.request,
                self.sequence,
                self.boot,
                self.timestamp_us,
                len(self.payload),
            )
            + self.payload
        )
        if len(raw) + 4 > MAX_DECODED:
            raise ValueError("payload exceeds protocol maximum; never truncated")
        return cobs_encode(raw + struct.pack("<I", zlib.crc32(raw))) + b"\0"

    @classmethod
    def decode(cls, encoded: bytes) -> "Packet":
        raw = cobs_decode(encoded)
        if not HEADER.size + 4 <= len(raw) <= MAX_DECODED:
            raise ValueError("invalid frame length")
        if zlib.crc32(raw[:-4]) != struct.unpack("<I", raw[-4:])[0]:
            raise ValueError("CRC mismatch")
        version, kind, request, seq, boot, stamp, size = HEADER.unpack_from(raw)
        if version != VERSION:
            raise ValueError("unsupported protocol version")
        if size != len(raw) - HEADER.size - 4:
            raise ValueError("payload length mismatch")
        return cls(kind, request, seq, boot, stamp, raw[HEADER.size : -4])


class Decoder:
    def __init__(self):
        self.buffer = bytearray()
        self.errors = []
        self.discarding = False

    def feed(self, data: bytes) -> list[Packet]:
        packets = []
        for byte in data:
            if byte == 0:
                if self.buffer and not self.discarding:
                    try:
                        packets.append(Packet.decode(bytes(self.buffer)))
                    except ValueError as error:
                        self.errors.append(str(error))
                self.buffer.clear()
                self.discarding = False
            elif not self.discarding:
                self.buffer.append(byte)
                if len(self.buffer) > MAX_DECODED + 8:
                    self.errors.append("oversized frame discarded")
                    self.buffer.clear()
                    self.discarding = True
        return packets


def pattern(sequence: int, size: int) -> bytes:
    return bytes((sequence + i) & 255 for i in range(size))
