import builtins
import json
from types import SimpleNamespace
from xrdiag.devices import glove, camera
from xrdiag.protocol import Packet, HELLO


def test_passive_ports(monkeypatch):
    from serial.tools import list_ports

    monkeypatch.setattr(
        list_ports,
        "comports",
        lambda: [
            SimpleNamespace(
                device="TESTPORT",
                description="USB",
                vid=1,
                pid=2,
                serial_number="abc",
                manufacturer="test",
            )
        ],
    )
    assert glove.ports()[0]["status"] == "NOT_RUN"


def test_handshake(monkeypatch):
    import serial

    class Fake:
        def __init__(self, **kw):
            self.in_waiting = 1
            self.buffer = b""

        def open(self):
            assert not self.dtr and not self.rts

        def write(self, raw):
            packet = Packet.decode(raw[:-1])
            self.buffer = Packet(
                HELLO,
                packet.request,
                payload=json.dumps(
                    dict(product="GloveXR diagnostic", protocol=1, state="IDLE")
                ).encode(),
            ).encode()

        def read(self, n):
            data, self.buffer = self.buffer, b""
            return data

        def close(self):
            pass

    monkeypatch.setattr(serial, "Serial", Fake)
    assert glove.probe("TESTPORT")["status"] == "READY"


def test_busy(monkeypatch):
    monkeypatch.setattr(
        glove, "Glove", lambda port: (_ for _ in ()).throw(PermissionError("busy"))
    )
    assert glove.probe("TESTPORT")["status"] == "BUSY"


def test_disappeared_during_probe(monkeypatch):
    monkeypatch.setattr(
        glove,
        "Glove",
        lambda port: (_ for _ in ()).throw(FileNotFoundError("device disappeared")),
    )
    assert glove.probe("TESTPORT")["status"] == "NOT_CONNECTED"


def test_reset_in_final_command_response_is_detected(monkeypatch):
    import serial
    from xrdiag.protocol import DATA, STATUS

    class Fake:
        def __init__(self, **kwargs):
            self.buffer = (
                Packet(DATA, boot=11).encode()
                + Packet(STATUS, request=1, boot=22).encode()
            )

        @property
        def in_waiting(self):
            return len(self.buffer)

        def open(self):
            pass

        def read(self, n):
            data, self.buffer = self.buffer, b""
            return data

        def close(self):
            pass

    monkeypatch.setattr(serial, "Serial", Fake)
    device = glove.Glove("TESTPORT")
    assert len(device.read()) == 2
    assert device.boot_changes == 1 and device.last_boot_id == 22


def test_missing_wrapper(monkeypatch):
    original = builtins.__import__

    def missing(name, *args, **kw):
        if name == "pyrealsense2":
            raise ImportError("not installed")
        return original(name, *args, **kw)

    monkeypatch.setattr(builtins, "__import__", missing)
    result = camera.discover()
    assert result["status"] == "NOT_INSTALLED"
    assert "Python" in result["reason"] and "setup_windows.ps1" in result["reason"]


def test_interleaved_ack_and_partial_telemetry(monkeypatch):
    import serial
    import io
    from xrdiag.protocol import START, STOP, DATA

    class Fake:
        def __init__(self, **kwargs):
            self.chunks = []

        @property
        def in_waiting(self):
            return len(self.chunks[0]) if self.chunks else 0

        def open(self):
            pass

        def close(self):
            pass

        def write(self, raw):
            packet = Packet.decode(raw[:-1])
            ack = Packet(packet.kind, packet.request).encode()
            if packet.kind == START:
                first = Packet(DATA, sequence=0, payload=b"abc").encode()
                self.chunks += [
                    ack + first[:8],
                    first[8:] + Packet(DATA, sequence=1).encode(),
                ]
            else:
                self.chunks += [
                    Packet(DATA, sequence=2).encode()
                    + ack
                    + Packet(DATA, sequence=3).encode()
                ]

        def read(self, n):
            return self.chunks.pop(0) if self.chunks else b""

    monkeypatch.setattr(serial, "Serial", Fake)
    device = glove.Glove("TESTPORT")
    capture = io.BytesIO()
    device.start_capture(capture)
    device.command(START)
    assert [p.sequence for p in device.read()] == [0, 1]
    device.command(STOP)
    assert [p.sequence for p, _ in device.pending] == [2, 3]
    assert len(capture.getvalue()) == device.received_bytes
    assert not device.decoder.errors
