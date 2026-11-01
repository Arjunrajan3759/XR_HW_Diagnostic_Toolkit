"""Beginner-oriented CLI; no implicit device opening or flashing."""

import argparse
import json
from pathlib import Path
import sys

from xrdiag.devices import camera, glove
from xrdiag.environment import snapshot
from xrdiag.experiments import execute
from xrdiag.reporting import Run, write_json, validate, package, verify_package

TESTS = ("H01", "H02", "H03", "H04", "H05")


def positive(value):
    number = float(value)
    if not 0 < number < float("inf"):
        raise argparse.ArgumentTypeError("must be finite and greater than zero")
    return number


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def options(parser):
    parser.add_argument("--mode", choices=("physical", "simulated"), default="physical")
    parser.add_argument(
        "--duration",
        type=positive,
        default=2,
        help="Seconds per test; simulation H01/H02/H04 use virtual time",
    )
    parser.add_argument(
        "--port",
        help="Explicit serial port, authorizes diagnostic HELLO without DTR/RTS reset",
    )
    parser.add_argument(
        "--camera-serial", help="Select one D435 when multiple are connected"
    )
    parser.add_argument("--output", default="results", help="Evidence parent directory")
    parser.add_argument(
        "--sensor-map", help="Verified sensor profile JSON; unknown wiring blocks H01"
    )
    parser.add_argument(
        "--frame-size",
        type=positive_int,
        default=128,
        help="H02/H05 payload bytes, maximum 998",
    )
    parser.add_argument(
        "--rate", type=positive_int, default=100, help="Offered USB packets per second"
    )
    parser.add_argument(
        "--sensor-bytes-per-second",
        type=positive,
        help="Measured H01 requirement for provisional headroom calculation",
    )
    parser.add_argument("--width", type=positive_int, default=640)
    parser.add_argument("--height", type=positive_int, default=480)
    parser.add_argument("--fps", type=positive_int, default=30)
    parser.add_argument(
        "--record-camera",
        action="store_true",
        help="Save H03 raw pixels in MCAP (optional recording dependencies)",
    )
    parser.add_argument(
        "--faults",
        action="store_true",
        help="Simulation fault injection; intentionally causes FAIL",
    )
    parser.add_argument(
        "--writer-delay-ms",
        type=float,
        default=0,
        help="Simulated slow writer, milliseconds per message",
    )
    parser.add_argument(
        "--interrupt-after",
        type=int,
        default=0,
        help="Simulation only: leave partial MCAP after N messages",
    )
    parser.add_argument("--rgb-queue-mib", type=positive_int, default=128)
    parser.add_argument("--depth-queue-mib", type=positive_int, default=96)
    parser.add_argument("--glove-queue-mib", type=positive_int, default=8)
    parser.add_argument(
        "--segment-mib",
        type=positive_int,
        default=1024,
        help="Rotation threshold; oversized single messages explicitly rejected",
    )
    parser.add_argument("--segment-seconds", type=positive, default=60)
    parser.add_argument(
        "--repetitions", type=positive_int, default=1, help="Repeat H02 cases"
    )
    parser.add_argument(
        "--sweep",
        action="store_true",
        help="H02: sweep payloads 64/128/256/512 and rates 100/500/1000",
    )


def combined(config, tests=TESTS):
    parent = Run(config["output"], "qualification", config)
    summaries = []
    for test in tests:
        sizes = (
            (64, 128, 256, 512)
            if test == "H02" and config["sweep"]
            else (config["frame_size"],)
        )
        rates = (
            (100, 500, 1000) if test == "H02" and config["sweep"] else (config["rate"],)
        )
        for size in sizes:
            for rate in rates:
                for _ in range(config["repetitions"] if test == "H02" else 1):
                    case = dict(
                        config, output=str(parent.folder), frame_size=size, rate=rate
                    )
                    folder, summary = execute(test, case)
                    summaries.append(dict(folder=folder.name, **summary))
                    print(f"{test}: {summary['status']} ({folder.name})")
    write_json(parent.folder / "experiments.json", summaries)
    table = [
        "# GloveXR qualification",
        "",
        f"Mode: **{config['mode'].upper()}**",
        "",
        "| Test | Status | Reason |",
        "|---|---|---|",
    ]
    table.extend(
        f"| {s['test']} | {s['status']} | {s.get('reason') or 'See child metrics'} |"
        for s in summaries
    )
    table.extend(
        [
            "",
            "Architecture evidence: H01 is required to set acquisition rate and glove bandwidth; "
            "H02 sustained physical cases can bound USB capacity; H03 physical evidence can validate the exact camera profile. "
            "H04 validates only software clock observations, with physical alignment still BLOCKED_SETUP. "
            "H05 qualifies the experimental recorder only. Simulation cannot select production performance budgets.",
        ]
    )
    (parent.folder / "qualification.md").write_text(
        "\n".join(table) + "\n", encoding="utf-8"
    )
    statuses = [s["status"] for s in summaries]
    status = (
        "FAIL"
        if "FAIL" in statuses
        else (
            "BLOCKED"
            if "BLOCKED" in statuses
            else "SIMULATED_PASS"
            if config["mode"] == "simulated"
            else "PASS"
        )
    )
    parent.finish(
        status,
        dict(
            tests=[dict(test=s["test"], status=s["status"]) for s in summaries],
            architecture="No production budgets qualified by simulation; H01/physical alignment remain gates",
        ),
    )
    return parent.folder, status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="GloveXR hardware qualification and clearly labeled simulation"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("doctor", "list-devices"):
        sub = commands.add_parser(
            command, help="Passive discovery; optional explicitly selected HELLO probe"
        )
        sub.add_argument(
            "--probe-port",
            help="Open only this port for diagnostic HELLO; no reset requested",
        )
        sub.add_argument("--output", default="results")
    for command in ("run", "run-all", "simulate"):
        sub = commands.add_parser(
            command, help="Run diagnostic experiments and preserve evidence"
        )
        if command == "run":
            sub.add_argument("test", choices=TESTS)
        options(sub)
        if command == "simulate":
            sub.set_defaults(mode="simulated")
    for command in ("analyze", "package"):
        sub = commands.add_parser(
            command, help="Verify evidence integrity and summarize or package"
        )
        sub.add_argument("folder", type=Path)
        if command == "package":
            sub.add_argument(
                "--include-raw",
                action="store_true",
                help="Include raw .bin and MCAP files; can be large",
            )
    args = parser.parse_args(argv)
    try:
        if args.command in ("doctor", "list-devices"):
            config = dict(mode="physical", probe_port=args.probe_port)
            run = Run(args.output, "doctor", config)
            report = dict(
                environment=snapshot(),
                serial_ports=glove.ports(),
                camera=camera.discover(),
                glove=glove.probe(args.probe_port)
                if args.probe_port
                else dict(
                    status="NOT_RUN",
                    reason="Passive discovery avoids interrupting arbitrary devices",
                ),
            )
            report["serial_dependency"] = dict(
                status="NOT_INSTALLED"
                if snapshot()["packages"]["pyserial"] == "NOT_INSTALLED"
                else "READY",
                repair="Install requirements.txt into the Python 3.11 toolkit environment",
            )
            write_json(run.folder / "devices.json", report)
            run.finish(
                "PASS",
                report,
                reason="Discovery completed; PASS here qualifies discovery software only, not hardware",
            )
            print(json.dumps(report, indent=2))
            print(f"Evidence: {run.folder}")
            return 0
        if args.command in ("analyze", "package"):
            if (
                args.command == "analyze"
                and args.folder.is_file()
                and args.folder.suffix.lower() == ".zip"
            ):
                print(json.dumps(verify_package(args.folder), indent=2))
                return 0
            errors = validate(args.folder)
            if errors:
                raise ValueError("; ".join(errors))
            if args.command == "package":
                print(json.dumps(package(args.folder, args.include_raw), indent=2))
            else:
                for file in sorted(args.folder.rglob("summary.json")):
                    summary = json.loads(file.read_text())
                    print(f"{summary['test']}: {summary['status']} [{summary['mode']}]")
                print("Checksums and required artifacts verified.")
            return 0
        config = vars(args).copy()
        config.pop("command")
        if args.command == "simulate":
            if config["mode"] != "simulated":
                parser.error(
                    "simulate requires simulated mode; use run-all for physical tests"
                )
        if (
            config["frame_size"] > 998
            or config["writer_delay_ms"] < 0
            or config["interrupt_after"] < 0
        ):
            parser.error(
                "frame-size must be <=998; delay and interruption count must be nonnegative"
            )
        if config["mode"] == "physical" and (
            config["faults"] or config["writer_delay_ms"] or config["interrupt_after"]
        ):
            parser.error("fault injection requires --mode simulated")
        if args.command == "run" and not (
            args.test == "H02" and (args.sweep or args.repetitions > 1)
        ):
            folder, summary = execute(args.test, config)
            status = summary["status"]
        else:
            folder, status = combined(
                config, (args.test,) if args.command == "run" else TESTS
            )
        print(f"{status}: {folder}")
        return 1 if status == "FAIL" else 2 if status == "BLOCKED" else 0
    except (ValueError, OSError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
