import platform
import time


def sdk():
    try:
        import pyrealsense2 as rs

        return rs
    except (ImportError, OSError) as error:
        raise RuntimeError(
            f"NOT_INSTALLED: pyrealsense2 import failed ({type(error).__name__}: {error}); "
            f"Python {platform.python_version()} {platform.machine()}. "
            "Run scripts/setup_windows.ps1 -Camera using 64-bit Python 3.11. "
            "Repair the Microsoft Visual C++ x64 runtime if DLL loading fails."
        ) from error


def discover():
    try:
        rs = sdk()
    except RuntimeError as error:
        return dict(status="NOT_INSTALLED", reason=str(error), devices=[])
    try:
        devices = []
        for device in rs.context().query_devices():
            info = {}
            for key in (
                "name",
                "serial_number",
                "firmware_version",
                "usb_type_descriptor",
            ):
                field = getattr(rs.camera_info, key)
                info[key] = device.get_info(field) if device.supports(field) else None
            info["profiles"] = [
                dict(
                    stream=str(p.stream_type()),
                    format=str(p.format()),
                    fps=p.fps(),
                    width=p.as_video_stream_profile().width(),
                    height=p.as_video_stream_profile().height(),
                )
                for sensor in device.query_sensors()
                for p in sensor.get_stream_profiles()
                if p.is_video_stream_profile()
            ]
            devices.append(info)
        return dict(status="READY" if devices else "NOT_CONNECTED", devices=devices)
    except Exception as error:
        return dict(status="ERROR", reason=str(error), devices=[])


def frames(duration, serial=None, width=640, height=480, fps=30, log_path=None):
    rs = sdk()
    if log_path is not None:
        rs.log_to_file(rs.log_severity.warn, str(log_path))
    pipeline, config = rs.pipeline(), rs.config()
    if serial:
        config.enable_device(serial)
    config.enable_stream(rs.stream.color, width, height, rs.format.rgb8, fps)
    config.enable_stream(rs.stream.depth, width, height, rs.format.z16, fps)
    started = False
    try:
        profile = pipeline.start(config)  # exact request; never downgrade
        started = True
        scale = profile.get_device().first_depth_sensor().get_depth_scale()
        deadline = time.perf_counter() + duration
        while time.perf_counter() < deadline:
            batch = pipeline.wait_for_frames(2000)
            host = time.perf_counter_ns()
            for topic, frame in (
                ("/RGB", batch.get_color_frame()),
                ("/DEPTH", batch.get_depth_frame()),
            ):
                if not frame:
                    raise RuntimeError(f"Required stream missing: {topic}")
                intr = frame.profile.as_video_stream_profile().get_intrinsics()
                metadata = {}
                for name in dir(rs.frame_metadata_value):
                    value = getattr(rs.frame_metadata_value, name)
                    try:
                        if frame.supports_frame_metadata(value):
                            metadata[name] = frame.get_frame_metadata(value)
                    except (TypeError, RuntimeError):
                        continue
                yield (
                    topic,
                    dict(
                        mode="PHYSICAL",
                        number=frame.get_frame_number(),
                        source_timestamp_ms=frame.get_timestamp(),
                        timestamp_domain=str(frame.get_frame_timestamp_domain()),
                        host_ns=host,
                        width=frame.get_width(),
                        height=frame.get_height(),
                        stride=frame.get_stride_in_bytes(),
                        format=str(frame.profile.format()),
                        depth_scale=scale if topic == "/DEPTH" else None,
                        intrinsics=dict(
                            fx=intr.fx,
                            fy=intr.fy,
                            ppx=intr.ppx,
                            ppy=intr.ppy,
                            model=str(intr.model),
                            coeffs=intr.coeffs,
                        ),
                        metadata=metadata,
                    ),
                    bytes(frame.get_data()),
                )
    finally:
        if started:
            pipeline.stop()
        if log_path is not None:
            rs.log_to_file(rs.log_severity.none, str(log_path))
