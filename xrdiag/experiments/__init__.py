"""Experiment orchestration, raw preservation and qualification rules."""

import json
from pathlib import Path
import shutil
import struct
import threading
import time

from xrdiag.analysis import SequenceTracker, stats, fit_clock
from xrdiag.devices import camera
from xrdiag.devices.glove import Glove
from xrdiag.protocol import (
    Decoder,
    DATA,
    START,
    STOP,
    STATUS,
    SYNC,
    pattern,
    MAX_DECODED,
    HEADER,
)
from xrdiag.reporting import Run, write_json
from xrdiag.simulation import glove_packets, camera_frames, clock_rows

ROOT = Path(__file__).resolve().parents[2]


class Blocked(Exception):
    pass


def profile_missing(profile):
    missing = []
    if not profile.get("approved"):
        missing.append("approved=true with wiring reviewer and reference")
    for key in ("wiring_reference", "approved_by"):
        if not profile.get(key):
            missing.append(key)
    if not profile.get("buses"):
        missing.append(
            "buses with verified SDA/SCL GPIO, clock Hz, pullups and voltage"
        )
    for bus in profile.get("buses", []):
        for key in ("id", "sda_gpio", "scl_gpio", "clock_hz", "voltage", "pullups"):
            if bus.get(key) is None:
                missing.append(f"bus {bus.get('id', 'unknown')}.{key}")
    for mux in profile.get("multiplexers", []):
        for key in ("bus", "address", "channels"):
            if mux.get(key) is None:
                missing.append(f"{mux.get('id', 'mux')}.{key}")
    for sensor in profile.get("sensors", []):
        for key in (
            "bus",
            "address",
            "sample_rate_hz",
            "output_format",
            "timing",
            "prerequisites",
            "mux_required",
        ):
            if sensor.get(key) is None:
                missing.append(f"{sensor['id']}.{key}")
        if sensor.get("mux_required") and not sensor.get("mux_path"):
            missing.append(f"{sensor['id']}.mux_path (verified ADG728 address/channel)")
    if not profile.get("sensors"):
        missing.append("sensor inventory")
    return missing


def open_glove(config):
    if not config.get("port"):
        raise Blocked(
            "BLOCKED_HARDWARE: choose --port from list-devices; no ports opened automatically"
        )
    try:
        device = Glove(config["port"])
    except Exception as error:
        raise Blocked(
            f"BLOCKED_HARDWARE: selected serial device unavailable: {error}. Close other programs and rediscover."
        ) from error
    try:
        try:
            identity = device.hello()
        except Exception as error:
            raise Blocked(
                f"BLOCKED_FIRMWARE: diagnostic HELLO prerequisite failed: {error}. No reset or flash attempted."
            ) from error
        if identity.get("state") != "IDLE":
            raise Blocked(
                "BLOCKED_SETUP: device is not IDLE; no running test interrupted"
            )
        return device, identity
    except BaseException:
        device.close()
        raise


def require_camera(config):
    report = camera.discover()
    candidates = [d for d in report["devices"] if "D435" in (d.get("name") or "")]
    if config.get("camera_serial"):
        candidates = [
            d for d in candidates if d["serial_number"] == config["camera_serial"]
        ]
    if not candidates:
        raise Blocked(
            "BLOCKED_HARDWARE: D435 unavailable; "
            + report["status"]
            + " "
            + report.get("reason", "")
        )
    if len(candidates) != 1:
        raise Blocked("BLOCKED_CONFIG: multiple D435 devices; select --camera-serial")
    return candidates[0]


def h01(run, config):
    profile = json.loads(
        Path(
            config.get("sensor_map") or ROOT / "config/sensor_map.example.json"
        ).read_text()
    )
    write_json(run.folder / "sensor_inventory.json", profile)
    missing = profile_missing(profile)
    if config["mode"] == "physical":
        if missing:
            raise Blocked(
                "BLOCKED_CONFIG: verified wiring absent. Required: "
                + "; ".join(missing)
            )
        raise Blocked(
            "BLOCKED_CONFIG: sensor drivers are not qualified for this unverified assembly. "
            "Implement/review drivers against the approved wiring and datasheets before H01."
        )
    rows = [
        dict(
            mode="SIMULATED",
            sensor=f"sensor_{j}",
            start_us=i * 1000 + j * 30,
            end_us=i * 1000 + j * 30 + 20 + (i % 7),
            read_us=20 + (i % 7),
            interval_us=1000,
            missed_deadlines=0,
            i2c_errors=0,
            boot_id=1,
        )
        for i in range(max(1, int(config["duration"] * 1000)))
        for j in range(3)
    ]
    return dict(
        requested_sample_hz=1000,
        achieved_sample_hz=1000,
        read_time_us=stats([r["read_us"] for r in rows]),
        inter_sensor_skew_us=60,
        errors=0,
        sensor_count=3,
        synthetic_profile=True,
        required_payload_bytes_per_second=3 * 1000 * 32,
    ), rows


def h02(run, config):
    size, rate, duration = config["frame_size"], config["rate"], config["duration"]
    if not 1 <= size <= MAX_DECODED - HEADER.size - 4:
        raise ValueError("frame-size exceeds the protocol payload limit")
    decoder, tracker = Decoder(), SequenceTracker()
    rows = []
    payload_bytes = encoded_bytes = bad_pattern = 0
    previous_host = None
    device = None
    started = False
    firmware, baseline = {}, {}
    receiver_errors = []
    usb_disconnects = 0
    rawfile = (run.folder / "raw_capture.bin").open("wb")
    start = time.perf_counter()
    elapsed = duration

    def consume(packet, host):
        nonlocal payload_bytes, bad_pattern, previous_host
        if packet.kind != DATA:
            return
        tracker.add(packet.boot, packet.sequence)
        bad = packet.payload != pattern(packet.sequence, len(packet.payload))
        bad_pattern += bad
        payload_bytes += len(packet.payload)
        row = dict(
            mode=config["mode"].upper(),
            sequence=packet.sequence,
            boot_id=packet.boot,
            mcu_us=packet.timestamp_us,
            host_ns=host,
            payload_bytes=len(packet.payload),
            host_interval_ns=host - previous_host if previous_host else 0,
            pattern_error=bad,
        )
        rows.append(row)
        run.observe(row)
        previous_host = host

    def drain_pending():
        for packet, host in device.pending:
            consume(packet, host)
        device.pending.clear()

    def receiver_error(phase, error):
        nonlocal usb_disconnects
        receiver_errors.append(f"{phase}: {type(error).__name__}: {error}")
        if (
            type(error).__module__.startswith("serial")
            and "Timeout" not in type(error).__name__
        ):
            usb_disconnects = 1  # this session never reconnects automatically

    try:
        if config["mode"] == "physical":
            device, identity = open_glove(config)
            device.start_capture(rawfile)
            decoder = device.decoder  # one framing state through START, DATA and STOP
            write_json(run.folder / "firmware.json", identity)
            baseline = json.loads(device.command(STATUS).payload)
            start = time.perf_counter()
            device.command(START, struct.pack("<HI", size, rate))
            started = True
            drain_pending()
            while time.perf_counter() - start < duration:
                for packet in device.read():
                    consume(packet, device.last_read_ns)
            device.command(STOP)
            started = False
            drain_pending()
            elapsed = time.perf_counter() - start
            firmware = json.loads(device.command(STATUS).payload)
            drain_pending()
            encoded_bytes = device.received_bytes
        else:
            for raw in glove_packets(
                max(1, int(rate * duration)),
                size,
                config.get("faults", False),
                interval_us=1e6 / rate,
            ):
                rawfile.write(raw)
                encoded_bytes += len(raw)
                for packet in decoder.feed(raw):
                    consume(packet, 1_000_000_000 + int(packet.timestamp_us * 1000))
    except Blocked:
        raise
    except Exception as error:
        receiver_error("capture", error)
        if config["mode"] == "physical":
            elapsed = max(time.perf_counter() - start, 1e-9)
    finally:
        if device:
            try:
                if started:
                    device.command(STOP)
                    drain_pending()
            except Exception as error:
                receiver_error("STOP cleanup", error)
            finally:
                encoded_bytes = device.received_bytes
                try:
                    device.close()
                except Exception as error:
                    receiver_error("serial close", error)
        rawfile.close()
    counter_keys = ("tx_errors", "queue_overflows", "missed_deadlines")
    counter_deltas = {
        k: firmware[k] - baseline[k] if k in firmware and k in baseline else None
        for k in counter_keys
    }
    if config["mode"] == "physical" and any(v is None for v in counter_deltas.values()):
        receiver_errors.append(
            "Final firmware counters unavailable; this run cannot qualify"
        )
    observed_resets = max(tracker.resets, getattr(device, "boot_changes", 0))
    errors = (
        len(decoder.errors)
        + tracker.gaps
        + tracker.duplicates
        + tracker.out_of_order
        + observed_resets
        + bad_pattern
        + len(receiver_errors)
    )
    errors += sum(
        max(0, v) + int(v < 0) for v in counter_deltas.values() if v is not None
    )
    delivered = payload_bytes / elapsed
    required = config.get("sensor_bytes_per_second")
    return dict(
        packets=len(rows),
        payload_bytes=payload_bytes,
        encoded_bytes=encoded_bytes,
        payload_bytes_per_second=delivered,
        encoded_bytes_per_second=encoded_bytes / elapsed,
        packets_per_second=len(rows) / elapsed,
        requested_payload_bytes_per_second=rate * size,
        delivered_fraction=delivered / (rate * size),
        crc_or_decode_errors=decoder.errors,
        crc_failures=sum("CRC" in error for error in decoder.errors),
        decode_error_count=len(decoder.errors),
        sequence_gaps=tracker.gaps,
        duplicates=tracker.duplicates,
        out_of_order=tracker.out_of_order,
        reset_events=observed_resets,
        pattern_errors=bad_pattern,
        firmware_counters=firmware,
        firmware_baseline=baseline,
        firmware_counter_deltas=counter_deltas,
        usb_disconnects=usb_disconnects,
        receiver_errors=receiver_errors,
        host_read_interval_ns=stats([r["host_interval_ns"] for r in rows[1:]]),
        errors=errors,
        sensor_bytes_per_second=required,
        headroom_fraction=(delivered / required - 1) if required else None,
        headroom_qualification="UNDETERMINED without physical H01"
        if not required
        else "provisional 30% rule",
        rate_sustainable=errors == 0 and delivered >= rate * size * 0.99,
        elapsed_capture_seconds=elapsed,
        measurement_clock="virtual duration"
        if config["mode"] == "simulated"
        else "host monotonic",
    ), rows


def camera_metrics(rows, config):
    result, errors = {}, 0
    for topic in ("/RGB", "/DEPTH"):
        stream = [r for r in rows if r["topic"] == topic]
        tracker = SequenceTracker()
        for row in stream:
            tracker.add(1, row["number"])
        intervals = [
            b["source_timestamp_ms"] - a["source_timestamp_ms"]
            for a, b in zip(stream, stream[1:])
        ]
        domains = sorted(set(r["timestamp_domain"] for r in stream))
        expected = int(config["duration"] * config["fps"])
        result[topic] = dict(
            received=len(stream),
            expected=expected,
            sequence_gaps=tracker.gaps,
            duplicates=tracker.duplicates,
            out_of_order=tracker.out_of_order,
            interval_ms=stats(intervals),
            timestamp_domains=domains,
            achieved_fps=1000 / stats(intervals)["mean"]
            if intervals and stats(intervals)["mean"]
            else None,
            captured_bytes=sum(r["bytes"] for r in stream),
        )
        errors += tracker.gaps + tracker.duplicates + tracker.out_of_order
        errors += sum(value <= 0 for value in intervals) + max(0, len(domains) - 1)
        result[topic]["host_interval_ns"] = stats(
            [b["host_ns"] - a["host_ns"] for a, b in zip(stream, stream[1:])]
        )
        if len(stream) < max(1, int(expected * 0.90)):
            errors += 1
    result["errors"] = errors
    return result


def h03(run, config):
    if config["mode"] == "physical":
        identity = require_camera(config)
        write_json(run.folder / "camera_capabilities.json", identity)
        source = camera.frames(
            config["duration"],
            identity["serial_number"],
            config["width"],
            config["height"],
            config["fps"],
            log_path=run.folder / "sdk_warnings.txt",
        )
    else:
        source = camera_frames(
            config["duration"],
            config["width"],
            config["height"],
            config["fps"],
            config.get("faults"),
        )
    recorder = None
    rows = []
    capture_error = None
    if config.get("record_camera"):
        from xrdiag.recording import Recorder

        recorder = Recorder(run.folder, config["mode"])
    try:
        for topic, metadata, raw in source:
            rows.append(dict(metadata, topic=topic, bytes=len(raw)))
            run.observe(rows[-1])
            if recorder:
                recorder.submit(topic, metadata, raw)
    except Exception as error:
        capture_error = f"{type(error).__name__}: {error}"
    finally:
        recording = recorder.close() if recorder else None
    metrics = camera_metrics(rows, config)
    metrics["recording"] = recording
    if recording and (
        recording["writer_error"] or recording["incoming"] != recording["recorded"]
    ):
        metrics["errors"] += 1
    metrics["raw_pixels_saved"] = recorder is not None
    metrics["capture_error"] = capture_error
    metrics["sdk_timeouts"] = int(
        bool(
            capture_error
            and any(
                text in capture_error.lower()
                for text in ("timeout", "timed out", "didn't arrive")
            )
        )
    )
    warning_file = run.folder / "sdk_warnings.txt"
    metrics["sdk_warning_lines"] = (
        len(warning_file.read_text(encoding="utf-8", errors="replace").splitlines())
        if warning_file.exists()
        else 0
    )
    if capture_error:
        metrics["errors"] += 1
    return metrics, rows


def h04(run, config):
    rows, device = [], None
    if config["mode"] == "simulated":
        count = max(4, int(config["duration"] * 100))
        rows = list(clock_rows(count, interval_ns=config["duration"] * 1e9 / count))
    else:
        try:
            device, identity = open_glove(config)
            write_json(run.folder / "firmware.json", identity)
            start = time.perf_counter()
            while time.perf_counter() - start < config["duration"]:
                send = time.perf_counter_ns()
                packet = device.command(SYNC)
                receive = time.perf_counter_ns()
                t2, t3 = struct.unpack("<QQ", packet.payload)
                rows.append(
                    dict(
                        mode="PHYSICAL",
                        host_send_ns=send,
                        host_receive_ns=receive,
                        mcu_receive_us=t2,
                        mcu_transmit_us=t3,
                        boot_id=packet.boot,
                    )
                )
                run.observe(rows[-1])
                time.sleep(0.02)
        finally:
            if device:
                (run.folder / "raw_capture.bin").write_bytes(device.raw)
                device.close()
    write_json(run.folder / "clock_observations.json", rows)
    resets = sum(a.get("boot_id") != b.get("boot_id") for a, b in zip(rows, rows[1:]))
    if resets:
        return dict(
            errors=resets, reset_events=resets, fit="REJECTED across device reset"
        ), rows
    result = fit_clock(rows)
    result.update(
        errors=0,
        reset_events=0,
        estimator_validation="OBSERVED" if device else "SIMULATED",
    )
    if not device:
        result.update(
            known_drift_ppm=25,
            known_offset_ns=5_000_000,
            drift_error_ppm=result["drift_ppm"] - 25,
            offset_error_ns=result["offset_at_reference_ns"]
            - (5_000_000 + result["reference_host_ns"] * 25e-6),
        )
    # Camera correlations are observations only, independent from the MCU fit.
    if config["mode"] == "physical":
        try:
            identity = require_camera(config)
            camera_rows = []
            for topic, meta, raw in camera.frames(
                min(2, config["duration"]),
                identity["serial_number"],
                config["width"],
                config["height"],
                config["fps"],
            ):
                camera_rows.append(dict(meta, topic=topic))
            write_json(run.folder / "camera_clock_observations.json", camera_rows)
            result["camera_clock_observations"] = len(camera_rows)
        except Blocked as error:
            result["camera_clock_status"] = str(error)
        result["blocked_reason"] = (
            "BLOCKED_SETUP: software clock fit retained as observations only. "
            "Full H04 alignment requires approved shared-event equipment and a validated detector. "
            + result.get("camera_clock_status", "")
        )
    return result, rows


def h05(run, config):
    from xrdiag.recording import Recorder

    estimated = (
        config["duration"]
        * (
            config["width"] * config["height"] * 5 * config["fps"]
            + config["rate"] * config["frame_size"]
        )
        * 1.5
    )
    if shutil.disk_usage(run.folder).free < estimated + 64 * 1024**2:
        raise Blocked(
            "BLOCKED_STORAGE: insufficient free disk for requested recording plus safety reserve"
        )
    device, identity = None, None
    if config["mode"] == "physical":
        camera_identity = require_camera(config)
        device, identity = open_glove(config)
        write_json(run.folder / "firmware.json", identity)
        write_json(run.folder / "camera_capabilities.json", camera_identity)
    recorder = Recorder(
        run.folder,
        config["mode"],
        budgets={
            "/RGB": config["rgb_queue_mib"] * 1024**2,
            "/DEPTH": config["depth_queue_mib"] * 1024**2,
            "/glove/samples": config["glove_queue_mib"] * 1024**2,
        },
        segment_bytes=config["segment_mib"] * 1024**2,
        segment_seconds=config["segment_seconds"],
        delay=config["writer_delay_ms"] / 1000,
        interrupt_after=config["interrupt_after"],
    )
    rows, producer_errors = [], []
    stop = threading.Event()
    tracker = SequenceTracker()

    def glove_source():
        decoder = Decoder()
        try:
            start = time.perf_counter()
            if device:
                # Real samples require a verified sensor driver; never record benchmark bytes as glove samples.
                raise Blocked(
                    "BLOCKED_CONFIG: physical H05 needs qualified H01 sample driver; synthetic USB DATA is not sensor evidence"
                )
            source = glove_packets(
                max(1, int(config["duration"] * config["rate"])),
                config["frame_size"],
                config.get("faults"),
                interval_us=1e6 / config["rate"],
            )
            with (run.folder / "raw_capture.bin").open("wb") as rawfile:
                for raw in source:
                    if stop.is_set():
                        break
                    rawfile.write(raw)
                    for packet in decoder.feed(raw):
                        tracker.add(packet.boot, packet.sequence)
                        recorder.submit(
                            "/glove/samples",
                            dict(
                                host_ns=1_000_000_000
                                + int(packet.sequence * 1e9 / config["rate"]),
                                sequence=packet.sequence,
                                boot_id=packet.boot,
                                mcu_us=packet.timestamp_us,
                                sample_format="SIMULATED_PATTERN",
                            ),
                            packet.payload,
                        )
                    if config["mode"] == "simulated":
                        target = (
                            start + (packet.sequence + 1) / config["rate"]
                            if decoder.buffer == b""
                            else start
                        )
                        stop.wait(max(0, target - time.perf_counter()))
            if decoder.errors:
                producer_errors.extend(decoder.errors)
        except Exception as error:
            producer_errors.append(str(error))
            stop.set()

    thread = threading.Thread(target=glove_source, daemon=True)
    try:
        recorder.submit(
            "/system/events",
            dict(event="start", configuration=config, host_ns=time.perf_counter_ns()),
        )
        # Simulated synchronization observation is explicitly labeled; no fabricated physical exchange.
        if config["mode"] == "simulated":
            recorder.submit(
                "/sync/observations", dict(next(clock_rows(1)), host_ns=1_000_000_000)
            )
        thread.start()
        if device:
            source = camera.frames(
                config["duration"],
                camera_identity["serial_number"],
                config["width"],
                config["height"],
                config["fps"],
            )
        else:
            source = camera_frames(
                config["duration"],
                config["width"],
                config["height"],
                config["fps"],
                config.get("faults"),
            )
        start = time.perf_counter()
        for topic, meta, raw in source:
            if stop.is_set():
                break
            recorder.submit(topic, meta, raw)
            rows.append(dict(meta, topic=topic, bytes=len(raw)))
            run.observe(rows[-1])
            if config["mode"] == "simulated" and topic == "/DEPTH":
                stop.wait(
                    max(
                        0,
                        start
                        + (meta["number"] + 1) / config["fps"]
                        - time.perf_counter(),
                    )
                )
    except Exception as error:
        producer_errors.append(str(error))
        stop.set()
    finally:
        if thread.ident:
            thread.join()
        if device:
            device.close()
        recording = recorder.close()
    result = camera_metrics(rows, config)
    result.update(
        recording=recording,
        producer_errors=producer_errors,
        glove_gaps=tracker.gaps,
        glove_duplicates=tracker.duplicates,
        glove_out_of_order=tracker.out_of_order,
        reset_events=tracker.resets,
        pipeline_qualification="Experimental Python pipeline only; not production Rust performance",
    )
    result["errors"] += (
        len(producer_errors)
        + tracker.gaps
        + tracker.duplicates
        + tracker.out_of_order
        + tracker.resets
    )
    if recording["writer_error"] or recording["incoming"] != recording["recorded"]:
        result["errors"] += 1
    return result, rows


def execute(test, config):
    run = Run(config["output"], test, config)
    cpu_start, wall_start = time.process_time(), time.perf_counter()
    try:
        if test == "H05" and config["mode"] == "physical":
            # Prerequisites checked without starting either stream.
            require_camera(config)
            raise Blocked(
                "BLOCKED_CONFIG: physical combined recording requires verified sensor wiring "
                "and a qualified H01 acquisition driver. H02 synthetic data cannot substitute."
            )
        metrics, rows = globals()[test.lower()](run, config)
        from xrdiag.analysis.runtime import process_metrics

        metrics["host_process"] = process_metrics(cpu_start, wall_start)
        status = (
            "FAIL"
            if metrics.get("errors", 0)
            else ("SIMULATED_PASS" if config["mode"] == "simulated" else "PASS")
        )
        if test == "H02" and not metrics["rate_sustainable"]:
            status = "FAIL"
        if status != "FAIL" and metrics.get("blocked_reason"):
            status = "BLOCKED"
        summary = run.finish(
            status, metrics, rows, reason=metrics.get("blocked_reason")
        )
    except Blocked as error:
        summary = run.finish("BLOCKED", {}, reason=str(error))
    except KeyboardInterrupt:
        summary = run.finish(
            "FAIL",
            {},
            reason="Operator interrupted execution; inspect partial captures",
        )
    except Exception as error:
        summary = run.finish("FAIL", {}, reason=f"{type(error).__name__}: {error}")
    return run.folder, summary
