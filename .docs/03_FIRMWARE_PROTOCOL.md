# Binary protocol v1

Every wire frame is COBS(decoded bytes) followed by one 00 delimiter. All multibyte integers are unsigned little-endian. There is no raw C structure serialization. The common envelope is:

| Offset | Bytes | Meaning |
|---|---|---|
| 0 | 1 | Version, exactly 1 |
| 1 | 1 | Message type |
| 2 | 2 | Request ID; 0 for unsolicited DATA |
| 4 | 4 | Packet sequence; DATA sequence increments per generated packet |
| 8 | 4 | Random MCU boot ID, stable until reset |
| 12 | 8 | MCU monotonic microseconds since boot |
| 20 | 2 | Payload length N |
| 22 | N | Payload |
| 22+N | 4 | CRC-32/ISO-HDLC over bytes [0,22+N), excluding CRC |

CRC uses reflected polynomial 0xEDB88320, init 0xFFFFFFFF, xorout 0xFFFFFFFF, refin/refout true. Check `123456789` = 0xCBF43926 (wire CRC bytes 26 39 F4 CB). Python zlib.crc32 matches. Decoder maximum is 1024 bytes, payload maximum 998. This raises the initial provisional 512-byte decoded limit so a full 512-byte benchmark payload fits. Both constants must change together for a future sensor schema; never truncate data. Maximum encoded size including delimiter fits 1032 bytes.

| Type | Name | Request payload | Response |
|---|---|---|---|
| 1 | HELLO | empty | UTF-8 JSON product, firmware, protocol, boot_id, state, max_decoded, sensor_driver |
| 2 | STATUS | empty | JSON current size/rate/state, uptime and cumulative counters |
| 3 | START | u16 payload_size, u32 packets_per_second | empty ACK; requires IDLE, size 1–998, rate 1–1000 |
| 4 | STOP | empty | empty ACK, returns IDLE; no reset/erase |
| 5 | SYNC | empty | u64 MCU receive us, u64 MCU transmit-enqueue us; requires IDLE |
| 6 | DATA | unsolicited only | Pattern byte i = (sequence+i) modulo 256; benchmark only |
| 127 | ERROR | not a host command | u16 error: 1 bad parameters, 2 invalid state, 3 unsupported command |

Responses echo the request ID and type, except ERROR. Command response sequence is currently the incoming sequence, normally zero; only DATA sequence participates in the throughput tracker. START resets DATA sequence, not counters. HELLO exposes sensor_driver=BLOCKED_CONFIG. STATUS state codes 0=IDLE, 1=USB_BENCH, 2=FAULT. Queue overflows halt generation and remain visible after STOP. New modes require protocol review; no unverified acquisition command exists.

The receive timestamp is sampled when the complete delimited request is parsed. The transmit timestamp is sampled in the TX task just before frame encoding and the first write, not at the USB wire edge; firmware buffering and encoding contribute uncertainty. Both are software observations. Host send/receive use perf_counter_ns around the command exchange. USB asymmetry is unmeasured. No physical alignment precision follows from this exchange.

Python Decoder accepts partial/multiple frames, counts corrupt/oversized frames and discards to the next delimiter. Unsupported version is explicit; a boot-ID change breaks sequence continuity and invalidates a clock fit across resets. Serial bytes are retained even when decoding fails. Glove.command retains interleaved telemetry while waiting for ACKs. Discovery opens only an explicitly selected port; unsolicited output is never taken as HELLO identity.

Simulated raw binary intentionally uses this identical wire format. Its accompanying metadata/report identifies it as SIMULATED; always retain that sidecar when transferring raw frames. MCAP and measurement records carry an explicit mode field.

Golden encoded vectors are in tests/fixtures/protocol_vectors.json. Firmware checks CRC and the shared encoded HELLO vector at startup before enabling telemetry. Tests verify the firmware's embedded vector matches the Python fixture; target compilation is checked by the ESP32 build. Startup checks have not been executed on a physical MCU here. Firmware version 0.1.0 and protocol version 1 are separate compatibility identifiers. Do not connect a production ASCII console and assume compatibility.
