#include "protocol.h"
#include <string.h>
void xr_put(uint8_t *p, uint64_t v, unsigned n) { for(unsigned i=0;i<n;i++) p[i]=(uint8_t)(v>>(8*i)); }
uint64_t xr_get(const uint8_t *p, unsigned n) { uint64_t v=0; for(unsigned i=0;i<n;i++) v|=((uint64_t)p[i])<<(8*i); return v; }
uint32_t xr_crc(const uint8_t *p, size_t n) {
    uint32_t crc=0xffffffffu;
    while(n--) { crc^=*p++; for(int i=0;i<8;i++) crc=(crc>>1)^((crc&1)?0xedb88320u:0); }
    return crc^0xffffffffu;
}
size_t xr_encode(const xr_packet *p, uint8_t *out) {
    if(p->size>XR_MAX_PAYLOAD) return 0;
    uint8_t raw[XR_MAX_DECODED]; size_t n=XR_HEADER+p->size;
    raw[0]=1; raw[1]=p->kind; xr_put(raw+2,p->request,2); xr_put(raw+4,p->sequence,4);
    xr_put(raw+8,p->boot,4); xr_put(raw+12,p->timestamp_us,8); xr_put(raw+20,p->size,2);
    memcpy(raw+XR_HEADER,p->payload,p->size); xr_put(raw+n,xr_crc(raw,n),4); n+=4;
    size_t index=0,pos=1; uint8_t code=1;
    for(size_t i=0;i<n;i++) {
        if(!raw[i]) {out[index]=code; index=pos++; code=1;}
        else {out[pos++]=raw[i]; if(++code==255) {out[index]=code;index=pos++;code=1;}}
    }
    out[index]=code; out[pos++]=0; return pos;
}
int xr_decode(const uint8_t *enc, size_t size, xr_packet *p) {
    uint8_t raw[XR_MAX_DECODED]; size_t i=0,n=0;
    while(i<size) {
        uint8_t code=enc[i++]; if(!code||i+code-1>size) return -1;
        for(unsigned k=1;k<code;k++) {if(n>=sizeof(raw)) return -1;raw[n++]=enc[i++];}
        if(code!=255&&i<size) {if(n>=sizeof(raw)) return -1;raw[n++]=0;}
    }
    if(n<XR_HEADER+4||xr_get(raw+n-4,4)!=xr_crc(raw,n-4)) return -2;
    if(raw[0]!=1) return -3;
    p->size=xr_get(raw+20,2); if(n!=XR_HEADER+p->size+4||p->size>XR_MAX_PAYLOAD) return -1;
    p->kind=raw[1];p->request=xr_get(raw+2,2);p->sequence=xr_get(raw+4,4);
    p->boot=xr_get(raw+8,4);p->timestamp_us=xr_get(raw+12,8);
    memcpy(p->payload,raw+XR_HEADER,p->size); return 0;
}
