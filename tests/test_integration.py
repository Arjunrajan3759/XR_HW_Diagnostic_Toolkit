import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile
import pytest
from xrdiag.cli import main
from xrdiag.experiments import profile_missing
from xrdiag.reporting import Run, validate, package


def test_reports_package_tamper(tmp_path):
    run = Run(tmp_path, "H02", dict(mode="simulated"))
    run.finish("SIMULATED_PASS", dict(errors=0), [dict(sequence=1)])
    summary = json.loads((run.folder / "summary.json").read_text())
    assert summary["environment"]["python"]
    assert summary["configuration"]["mode"] == "simulated"
    assert "99%" in summary["criteria"]
    assert not validate(run.folder)
    result = package(run.folder)
    with zipfile.ZipFile(run.folder.parent / result["package"]) as archive:
        for line in archive.read("PACKAGE_CHECKSUMS.sha256").decode().splitlines():
            digest, name = line.split("  ", 1)
            assert hashlib.sha256(archive.read(name)).hexdigest() == digest
    (run.folder / "summary.json").write_text("{}")
    assert validate(run.folder)
    with pytest.raises(ValueError):
        package(run.folder)


@pytest.mark.parametrize("test", ["H01", "H02", "H03", "H04", "H05"])
def test_simulated_cli(tmp_path, test):
    assert (
        main(
            [
                "run",
                test,
                "--mode",
                "simulated",
                "--duration",
                ".1",
                "--width",
                "8",
                "--height",
                "8",
                "--output",
                str(tmp_path),
            ]
        )
        == 0
    )
    folder = next(tmp_path.iterdir())
    summary = json.loads((folder / "summary.json").read_text())
    assert summary["status"] == "SIMULATED_PASS" and summary["mode"] == "simulated"
    assert not validate(folder)


def test_no_hardware(tmp_path, monkeypatch):
    from xrdiag.devices import camera

    monkeypatch.setattr(
        camera, "discover", lambda: dict(status="NOT_CONNECTED", devices=[])
    )
    assert main(["run-all", "--duration", ".1", "--output", str(tmp_path)]) == 2
    folder = next(tmp_path.iterdir())
    summaries = json.loads((folder / "experiments.json").read_text())
    assert all(s["status"] == "BLOCKED" for s in summaries)
    assert not validate(folder)


def test_mcu_clock_observations_do_not_qualify_alignment(tmp_path, monkeypatch):
    import struct
    import time
    import xrdiag.experiments as experiments
    from xrdiag.protocol import Packet, SYNC

    clock = {"ns": 1_000_000_000}
    monkeypatch.setattr(
        time, "perf_counter", lambda: (clock["ns"] - 1_000_000_000) / 1e9
    )
    monkeypatch.setattr(time, "perf_counter_ns", lambda: clock["ns"])

    def advance(seconds):
        clock["ns"] += int(seconds * 1e9)

    monkeypatch.setattr(time, "sleep", advance)

    class Device:
        raw = b""

        def command(self, kind):
            assert kind == SYNC
            stamp = time.perf_counter_ns() // 1000 + 5000
            advance(0.0002)
            return Packet(SYNC, boot=1, payload=struct.pack("<QQ", stamp, stamp))

        def close(self):
            pass

    monkeypatch.setattr(
        experiments, "open_glove", lambda config: (Device(), dict(state="IDLE"))
    )
    monkeypatch.setattr(
        experiments.camera, "discover", lambda: dict(status="NOT_CONNECTED", devices=[])
    )
    assert (
        main(
            [
                "run",
                "H04",
                "--port",
                "TESTPORT",
                "--duration",
                ".15",
                "--output",
                str(tmp_path),
            ]
        )
        == 2
    )
    summary = json.loads((next(tmp_path.iterdir()) / "summary.json").read_text())
    assert summary["status"] == "BLOCKED"
    assert summary["metrics"]["estimator_validation"] == "OBSERVED"
    assert summary["metrics"]["physical_alignment"] == "BLOCKED_SETUP"
    assert "drift_ppm" in summary["metrics"]


def test_usb_disconnect_retains_metrics_and_cannot_cancel_historical_errors(
    tmp_path, monkeypatch
):
    import time
    import xrdiag.experiments as experiments
    from xrdiag.protocol import Packet, Decoder, DATA, STATUS, START, pattern
    from serial import SerialException

    class Device:
        def __init__(self):
            self.decoder = Decoder()
            self.pending = []
            self.received_bytes = 0
            self.last_read_ns = 0
            self.reads = 0

        def start_capture(self, stream):
            self.stream = stream

        def command(self, kind, payload=b""):
            if kind == STATUS:
                return Packet(
                    STATUS,
                    payload=json.dumps(
                        dict(tx_errors=5, queue_overflows=2, missed_deadlines=1)
                    ).encode(),
                )
            if kind == START:
                return Packet(START)
            raise SerialException("injected disconnect during STOP")

        def read(self):
            self.reads += 1
            if self.reads > 1:
                raise SerialException("injected USB serial disconnect")
            raw = Packet(DATA, boot=1, payload=pattern(0, 128)).encode()
            self.stream.write(raw)
            self.received_bytes += len(raw)
            self.last_read_ns = time.perf_counter_ns()
            return self.decoder.feed(raw)

        def close(self):
            pass

    monkeypatch.setattr(
        experiments, "open_glove", lambda config: (Device(), dict(state="IDLE"))
    )
    assert (
        main(
            [
                "run",
                "H02",
                "--port",
                "TESTPORT",
                "--duration",
                ".1",
                "--output",
                str(tmp_path),
            ]
        )
        == 1
    )
    folder = next(tmp_path.iterdir())
    summary = json.loads((folder / "summary.json").read_text())
    assert summary["status"] == "FAIL" and summary["metrics"]["packets"] == 1
    assert summary["metrics"]["usb_disconnects"] == 1
    assert (
        summary["metrics"]["errors"] > 0 and not summary["metrics"]["rate_sustainable"]
    )
    assert (folder / "raw_capture.bin").stat().st_size > 0
    assert (folder / "observations.jsonl").exists()


def test_configuration_and_cli_errors(tmp_path):
    assert profile_missing({})
    for args in (
        ["run", "H99"],
        ["run", "H02", "--duration", "-1"],
        ["run", "H02", "--frame-size", "999"],
        ["run", "H05", "--faults"],
        ["run", "H03", "--duration", "nan"],
    ):
        with pytest.raises(SystemExit):
            main(args)


def test_relocated_space_path(tmp_path):
    import shutil

    root = Path(__file__).resolve().parents[1]
    moved = tmp_path / "different folder with spaces"
    moved.mkdir()
    shutil.copytree(
        root / "xrdiag", moved / "xrdiag", ignore=shutil.ignore_patterns("__pycache__")
    )
    shutil.copytree(root / "config", moved / "config")
    command = [
        sys.executable,
        "-m",
        "xrdiag",
        "simulate",
        "--duration",
        ".1",
        "--width",
        "8",
        "--height",
        "8",
        "--output",
        "evidence with spaces",
    ]
    result = subprocess.run(
        command, cwd=moved, capture_output=True, text=True, timeout=120
    )
    assert result.returncode == 0, result.stdout + result.stderr
    folder = next((moved / "evidence with spaces").iterdir())
    assert not validate(folder)


def test_no_hardcoded_user_or_sdk_paths():
    root = Path(__file__).resolve().parents[1]
    for directory in ("xrdiag", "scripts", "config", "firmware"):
        for file in (root / directory).rglob("*"):
            if (
                file.is_file()
                and not any(part in (".pio", "__pycache__") for part in file.parts)
                and file.suffix in (".py", ".ps1", ".json", ".ini", ".c", ".h")
            ):
                text = file.read_text()
                assert "C:\\Users\\" not in text
                assert "Intel RealSense SDK 2.0\\" not in text
