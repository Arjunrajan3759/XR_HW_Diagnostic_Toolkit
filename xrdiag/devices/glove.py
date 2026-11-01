import json
import time
from xrdiag.protocol import Packet, Decoder, HELLO, ERROR


def ports():
    try:
        from serial.tools import list_ports
    except ImportError:
        return []
    return [
        dict(
            port=p.device,
            description=p.description,
            vid=p.vid,
            pid=p.pid,
            serial_number=p.serial_number,
            manufacturer=p.manufacturer,
            status="NOT_RUN",
            reason="Passive listing; use --probe-port for HELLO",
        )
        for p in list_ports.comports()
    ]


class Glove:
    def __init__(self, port: str) -> None:
        import serial

        self.serial = serial.Serial(
            port=None, baudrate=115200, timeout=0.1, write_timeout=1
        )
        self.serial.dtr = False
        self.serial.rts = False
        self.serial.port = port
        self.serial.open()
        self.decoder = Decoder()
        self.request = 0
        self.raw = bytearray()
        self.pending = []
        self.capture = None
        self.received_bytes = 0
        self.last_read_ns = 0
        self.last_boot_id = None
        self.boot_changes = 0

    def start_capture(self, stream):
        stream.write(self.raw)
        self.raw.clear()
        self.capture = stream

    def close(self):
        self.serial.close()

    def read(self) -> list[Packet]:
        data = self.serial.read(max(1, self.serial.in_waiting))
        self.last_read_ns = time.perf_counter_ns()
        self.received_bytes += len(data)
        if self.capture:
            self.capture.write(data)
        else:
            self.raw.extend(data)
        packets = self.decoder.feed(data)
        for packet in packets:
            if self.last_boot_id is not None and packet.boot != self.last_boot_id:
                self.boot_changes += 1
            self.last_boot_id = packet.boot
        return packets

    def command(self, kind: int, payload: bytes = b"") -> Packet:
        self.request = (self.request + 1) % 65536 or 1
        self.serial.write(Packet(kind, self.request, payload=payload).encode())
        deadline = time.perf_counter() + 2
        while time.perf_counter() < deadline:
            response = None
            for packet in self.read():
                if packet.request == self.request:
                    if packet.kind == ERROR:
                        code = int.from_bytes(packet.payload, "little")
                        explanation = {
                            1: "Invalid parameters: payload 1–998 bytes, rate 1–1000 packets/s",
                            2: "Invalid state: stop the operator-owned test before starting a new one",
                            3: "Unsupported command for this firmware",
                        }.get(code, "Unknown firmware error")
                        raise RuntimeError(f"Firmware error {code}: {explanation}")
                    if packet.kind != kind:
                        raise RuntimeError("Unexpected command response")
                    response = packet
                else:
                    self.pending.append((packet, self.last_read_ns))
            if response is not None:
                return response
        if any("version" in e for e in self.decoder.errors):
            raise RuntimeError("UNSUPPORTED_VERSION")
        raise TimeoutError(
            "Diagnostic firmware handshake/command timed out; no reset attempted"
        )

    def hello(self):
        identity = json.loads(self.command(HELLO).payload)
        if identity.get("product") != "GloveXR diagnostic":
            raise RuntimeError("WRONG_FIRMWARE")
        if identity.get("protocol") != 1:
            raise RuntimeError("UNSUPPORTED_VERSION")
        return identity


def probe(port):
    device = None
    try:
        device = Glove(port)
        identity = device.hello()
        return dict(port=port, status="READY", identity=identity)
    except Exception as error:
        message = str(error)
        lower = message.lower()
        if (
            isinstance(error, PermissionError)
            or "access is denied" in lower
            or "busy" in lower
        ):
            status = "BUSY"
        elif isinstance(error, FileNotFoundError) or any(
            s in lower for s in ("could not open port", "cannot find", "no such file")
        ):
            status = "NOT_CONNECTED"
        elif "unsupported" in lower:
            status = "UNSUPPORTED_VERSION"
        elif (
            isinstance(error, (TimeoutError, json.JSONDecodeError))
            or "wrong_firmware" in lower
        ):
            status = "WRONG_FIRMWARE"
        else:
            status = "ERROR"
        return dict(port=port, status=status, reason=message)
    finally:
        if device:
            device.close()
