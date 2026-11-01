#pragma once
#include <stdint.h>
#include <stddef.h>
#define XR_MAX_DECODED 1024
#define XR_HEADER 22
#define XR_MAX_PAYLOAD (XR_MAX_DECODED-XR_HEADER-4)
typedef struct {
    uint8_t kind;
    uint16_t request;
    uint32_t sequence, boot;
    uint64_t timestamp_us;
    uint16_t size;
    uint8_t payload[XR_MAX_PAYLOAD];
} xr_packet;
uint32_t xr_crc(const uint8_t *data, size_t size);
size_t xr_encode(const xr_packet *packet, uint8_t *out);
int xr_decode(const uint8_t *encoded, size_t size, xr_packet *packet);
void xr_put(uint8_t *p, uint64_t value, unsigned size);
uint64_t xr_get(const uint8_t *p, unsigned size);
