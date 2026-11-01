"""Best-effort host process metrics without additional dependencies."""

import ctypes
import os
import time


def process_metrics(cpu_start, wall_start):
    elapsed = time.perf_counter() - wall_start
    cpu = time.process_time() - cpu_start
    result = dict(
        process_cpu_seconds=cpu,
        elapsed_seconds=elapsed,
        process_cpu_percent=100 * cpu / elapsed if elapsed else None,
        peak_working_set_bytes=None,
    )
    if os.name == "nt":
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
                (name, ctypes.c_size_t)
                for name in (
                    "peak",
                    "working",
                    "quota_peak_paged",
                    "quota_paged",
                    "quota_peak_nonpaged",
                    "quota_nonpaged",
                    "pagefile",
                    "peak_pagefile",
                )
            ]

        values = Counters()
        values.cb = ctypes.sizeof(values)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(Counters),
            wintypes.DWORD,
        ]
        if psapi.GetProcessMemoryInfo(
            kernel.GetCurrentProcess(), ctypes.byref(values), values.cb
        ):
            result["peak_working_set_bytes"] = values.peak
    return result
