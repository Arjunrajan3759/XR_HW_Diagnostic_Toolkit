import json
from pathlib import Path
import re
import subprocess
import shutil
import sys

from xrdiag.reporting import Run, package, validate


def test_shared_firmware_vector():
    root = Path(__file__).resolve().parents[1]
    fixture = json.loads((root / "tests/fixtures/protocol_vectors.json").read_text())[0]
    header = (
        root / "firmware/xiao_esp32c6_diagnostics/include/golden_vector.h"
    ).read_text()
    encoded = bytes(int(v, 16) for v in re.findall(r"0x([0-9a-f]{2})", header))
    assert encoded.hex() == fixture["encoded_hex"]
    source = (root / "firmware/xiao_esp32c6_diagnostics/src/main.c").read_text()
    assert "memcmp(bytes,xr_hello_vector,count)" in source
    assert 'xr_crc((const uint8_t*)"123456789",9)!=0xcbf43926' in source


def test_package_ignores_untracked_secrets(tmp_path):
    import zipfile

    run = Run(
        tmp_path,
        "H01",
        dict(mode="simulated", note=r"C:\Users\Example User\Desktop\evidence"),
    )
    run.finish("SIMULATED_PASS", {})
    (run.folder / "secrets.json").write_text('{"unrelated":"private"}')
    result = package(run.folder)
    with zipfile.ZipFile(run.folder.parent / result["package"]) as archive:
        assert "secrets.json" not in archive.namelist()
        exported = json.loads(archive.read("configuration.json"))
        assert "Example User" not in exported["note"]
        assert exported["note"].startswith("<USER_HOME>")
    from xrdiag.reporting import verify_package

    assert verify_package(run.folder.parent / result["package"])["mode"] == "simulated"


def test_incomplete_metadata_rejected(tmp_path):
    from xrdiag.reporting import write_json, seal

    run = Run(tmp_path, "H01", dict(mode="simulated"))
    run.finish("FAIL", {})
    write_json(run.folder / "metadata.json", dict(complete=False))
    seal(run.folder)
    assert any("Incomplete" in e for e in validate(run.folder))


def test_observation_survives_failure(tmp_path):
    run = Run(tmp_path, "H03", dict(mode="physical"))
    row = dict(mode="PHYSICAL", number=4, source_timestamp_ms=22)
    run.observe(row)
    run.finish("FAIL", {}, reason="Injected disconnect after first frame")
    assert json.loads((run.folder / "observations.jsonl").read_text()) == row
    assert not validate(run.folder)


def test_flash_requires_recovery_before_action():
    if not shutil.which("powershell"):
        return
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-File",
            str(root / "scripts/flash_firmware.ps1"),
            "-Port",
            "INVALID_DIAGNOSTIC_TEST",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0
    assert "recovery" in (result.stdout + result.stderr).lower()


def test_core_without_optional_modules(tmp_path):
    root = Path(__file__).resolve().parents[1]
    code = """
import builtins
original=builtins.__import__
def guarded(name,*args,**kwargs):
    if name.split('.')[0] in ('pyrealsense2','mcap'):
        raise ImportError('deliberately absent for core acceptance')
    return original(name,*args,**kwargs)
builtins.__import__=guarded
from xrdiag.devices.camera import discover
assert discover()['status']=='NOT_INSTALLED'
from xrdiag.cli import main
import sys
assert main(['run','H02','--mode','simulated','--duration','.1','--output',sys.argv[1]])==0
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path)],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
