import csv
import hashlib
import json
from pathlib import Path
import re
import zipfile
import subprocess
import os
from datetime import datetime, timezone
from uuid import uuid4
from xrdiag.environment import snapshot


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")


def checksum(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def seal(folder):
    folder = Path(folder)
    entries = [
        f"{checksum(p)}  {p.relative_to(folder).as_posix()}"
        for p in sorted(folder.rglob("*"))
        if p.is_file() and p != folder / "checksums.sha256"
    ]
    (folder / "checksums.sha256").write_text(
        "\n".join(entries) + "\n", encoding="utf-8"
    )


def validate(folder):
    folder = Path(folder).resolve()
    errors = []
    manifest = folder / "checksums.sha256"
    if not manifest.exists():
        return ["Missing checksums.sha256; incomplete run"]
    for line in manifest.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        target = (folder / relative).resolve()
        if not target.is_relative_to(folder) or not target.is_file():
            errors.append(f"Missing/unsafe evidence: {relative}")
        elif checksum(target) != expected:
            errors.append(f"Checksum mismatch: {relative}")
    for name in ("summary.json", "configuration.json", "metadata.json", "report.md"):
        if not (folder / name).is_file():
            errors.append(f"Missing {name}")
    for metadata in folder.rglob("metadata.json"):
        try:
            if not json.loads(metadata.read_text(encoding="utf-8")).get("complete"):
                errors.append(f"Incomplete run: {metadata.parent.name}")
        except (ValueError, OSError):
            errors.append(f"Unreadable metadata: {metadata.parent.name}")
    for file in folder.rglob("*.partial"):
        errors.append(f"Interrupted recording: {file.name}")
    for file in folder.rglob("*.mcap"):
        try:
            from xrdiag.recording import verify

            verify(file)
        except Exception as error:
            errors.append(f"MCAP validation failed: {file.name}: {error}")
    return errors


class Run:
    def __init__(self, root, test, config):
        self.start = datetime.now(timezone.utc)
        self.folder = (
            Path(root) / f"{self.start:%Y%m%dT%H%M%S}_{test}_{uuid4().hex[:8]}"
        )
        self.folder.mkdir(parents=True)
        self.test, self.config = test, config
        source_root = Path(__file__).resolve().parents[2]
        try:
            revision = subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=source_root,
                stderr=subprocess.DEVNULL,
                timeout=5,
                text=True,
            ).strip()
        except (OSError, subprocess.SubprocessError):
            revision = "unavailable"
        source_hashes = {}
        for directory in ("xrdiag", "firmware", "config", "scripts"):
            for current, directories, filenames in os.walk(source_root / directory):
                directories[:] = sorted(
                    d for d in directories if d not in (".pio", "__pycache__")
                )
                for filename in sorted(filenames):
                    source = Path(current) / filename
                    source_hashes[source.relative_to(source_root).as_posix()] = (
                        checksum(source)
                    )
        write_json(
            self.folder / "source_versions.json",
            dict(
                version="0.1.0",
                git_revision=revision,
                working_tree_sha256=source_hashes,
            ),
        )

        write_json(self.folder / "configuration.json", config)
        write_json(self.folder / "environment.json", snapshot())
        write_json(
            self.folder / "metadata.json",
            dict(
                test=test,
                mode=config["mode"],
                start=self.start.isoformat(),
                complete=False,
                source_version="0.1.0",
            ),
        )

    def observe(self, row: dict) -> None:
        """Persist raw observations immediately, including when a later adapter call fails."""
        with (self.folder / "observations.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, default=str) + "\n")

    def finish(self, status, metrics, rows=(), reason=None):
        end = datetime.now(timezone.utc)
        criteria = {
            "H01": "Physical acquisition requires approved wiring and qualified drivers. Simulation validates the timing analysis only.",
            "H02": "Zero integrity/sequence/reset/TX/queue/deadline errors and >=99% requested payload delivery. Provisional 30% headroom requires physical H01.",
            "H03": "Both exact streams, >=90% expected frames, no counter/domain/interval errors or SDK capture exception; optional recordings must verify.",
            "H04": "Retain software clock observations; physical qualification remains BLOCKED_SETUP without approved shared-event validation.",
            "H05": "No source/queue/writer errors; required streams present; incoming, recorded and verified MCAP counts agree.",
            "doctor": "Discovery completed; this is not physical hardware qualification.",
            "qualification": "Every required experiment must qualify; any failure or blocked prerequisite is retained.",
        }.get(self.test, "See experiment measurements and prerequisite gates")
        identities = {}
        for name, filename in (
            ("glove", "firmware.json"),
            ("camera", "camera_capabilities.json"),
        ):
            artifact = self.folder / filename
            if artifact.exists():
                identities[name] = {
                    key: value
                    for key, value in json.loads(
                        artifact.read_text(encoding="utf-8")
                    ).items()
                    if key != "profiles"
                }
        environment = snapshot()
        summary = dict(
            test=self.test,
            mode=self.config["mode"],
            status=status,
            reason=reason,
            metrics=metrics,
            start=self.start.isoformat(),
            end=end.isoformat(),
            duration_seconds=(end - self.start).total_seconds(),
            environment=environment,
            configuration=self.config,
            device_identities=identities,
            source_version="0.1.0; exact source hashes in source_versions.json",
            criteria=criteria,
            unanswered=[
                "Physical glove-camera alignment requires separate event validation"
            ],
            architecture_decision="Use physical sustained evidence before selecting production budgets",
        )
        write_json(self.folder / "summary.json", summary)
        write_json(
            self.folder / "metadata.json",
            dict(
                test=self.test,
                mode=self.config["mode"],
                start=self.start.isoformat(),
                end=end.isoformat(),
                complete=True,
                source_version="0.1.0",
            ),
        )
        rows = list(rows)
        if rows:
            keys = list(dict.fromkeys(k for row in rows for k in row))
            with (self.folder / "measurements.csv").open(
                "w", newline="", encoding="utf-8"
            ) as stream:
                writer = csv.DictWriter(stream, fieldnames=keys)
                writer.writeheader()
                writer.writerows(rows)
        (self.folder / "logs.txt").write_text(
            reason
            or f"Execution finished with status {status}; see summary and raw evidence.",
            encoding="utf-8",
        )
        (self.folder / "report.md").write_text(
            f"# {self.test}: {status}\n\nMode: **{self.config['mode'].upper()}**\n\n"
            f"Start: {self.start.isoformat()}  End: {end.isoformat()}\n\n"
            f"Host: {environment['os']}, build {environment['os_build']}; Python {environment['python']}; "
            f"{environment['platformio']}.\n\n"
            f"Criteria: {criteria}\n\n"
            f"{reason or 'Execution complete.'}\n\n```json\n{json.dumps(summary, indent=2)}\n```\n\n"
            "Configuration and environment are preserved in adjacent JSON files. "
            "Artifacts not present were not produced (blocked tests have no measurements).\n",
            encoding="utf-8",
        )
        seal(self.folder)
        return summary


def package(folder, include_raw=False):
    folder = Path(folder).resolve()
    errors = validate(folder)
    if errors:
        raise ValueError("; ".join(errors))
    destination = folder.with_name(folder.name + f"_handoff_{uuid4().hex[:8]}.zip")
    selected = []
    allowed = {
        line.split("  ", 1)[1]
        for line in (folder / "checksums.sha256")
        .read_text(encoding="utf-8")
        .splitlines()
    }
    allowed.add("checksums.sha256")
    for path in folder.rglob("*"):
        relative = path.relative_to(folder)
        if relative.as_posix() not in allowed or path.is_symlink():
            continue
        if not path.is_file() or any(p.startswith(".") for p in relative.parts):
            continue
        if path.suffix not in (
            ".json",
            ".md",
            ".csv",
            ".txt",
            ".sha256",
            ".bin",
            ".mcap",
            ".jsonl",
        ):
            continue
        if not include_raw and path.suffix in (".bin", ".mcap"):
            continue
        selected.append(path)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        hashes = []
        for path in selected:
            relative = path.relative_to(folder).as_posix()
            if path.suffix in (".bin", ".mcap"):
                archive.write(path, relative)
                hashes.append(f"{checksum(path)}  {relative}")
                continue
            data = path.read_bytes()
            if path.suffix in (".md", ".txt", ".json", ".jsonl", ".csv"):
                text = data.decode("utf-8")
                text = re.sub(
                    r'[A-Za-z]:[\\/]+Users[\\/]+[^\\/\r\n"<>]+',
                    "<USER_HOME>",
                    text,
                    flags=re.I,
                )
                data = text.encode("utf-8")
            archive.writestr(relative, data)
            hashes.append(f"{hashlib.sha256(data).hexdigest()}  {relative}")
        archive.writestr("PACKAGE_CHECKSUMS.sha256", "\n".join(hashes) + "\n")
        archive.writestr(
            "HANDOFF.md",
            "# GloveXR evidence\n\nSee summary.json for PHYSICAL versus SIMULATED status.\n"
            "Raw files omitted unless explicitly requested. PACKAGE_CHECKSUMS validates exported bytes; "
            "original manifests describe original evidence before privacy redaction.\n",
        )
    return dict(
        package=destination.name,
        location=str(destination),
        bytes=destination.stat().st_size,
        sha256=checksum(destination),
    )


def verify_package(path: str | Path) -> dict:
    """Validate exported bytes directly, without extracting a handoff ZIP."""
    with zipfile.ZipFile(path) as archive:
        failure = archive.testzip()
        if failure:
            raise ValueError(f"ZIP CRC failure: {failure}")
        lines = archive.read("PACKAGE_CHECKSUMS.sha256").decode("utf-8").splitlines()
        for line in lines:
            expected, name = line.split("  ", 1)
            digest = hashlib.sha256()
            with archive.open(name) as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() != expected:
                raise ValueError(f"ZIP evidence checksum mismatch: {name}")
        summary = json.loads(archive.read("summary.json"))
        return dict(
            verified_files=len(lines),
            status=summary["status"],
            mode=summary["mode"],
            package_sha256=checksum(path),
        )
