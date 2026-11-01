#include "protocol.h"
#include "golden_vector.h"
#include "driver/usb_serial_jtag.h"
#include "esp_timer.h"
#include "esp_random.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include <stdio.h>
#include <string.h>

enum {HELLO=1,STATUS=2,START=3,STOP=4,SYNC=5,DATA=6,ERROR=127};
enum {IDLE,USB_BENCH,FAULT};
static QueueHandle_t tx_queue;
static uint32_t boot_id,seq,generated,queue_overflows,tx_errors,rx_errors,missed_deadlines,tx_packets,queue_max;
static uint16_t frame_size=128;
static uint32_t rate=100;
static int state=IDLE;
static int64_t next_us;
static portMUX_TYPE counter_lock=portMUX_INITIALIZER_UNLOCKED;

static int enqueue(xr_packet *p) {
    p->boot=boot_id;
    if(!p->timestamp_us) p->timestamp_us=esp_timer_get_time();
    if(xQueueSend(tx_queue,p,0)!=pdTRUE) {queue_overflows++;state=FAULT;return 0;}
    uint32_t occupied=uxQueueMessagesWaiting(tx_queue);
    if(occupied>queue_max) queue_max=occupied;
    return 1;
}
static void transmit(void *arg) {
    (void)arg; xr_packet p; uint8_t encoded[XR_MAX_DECODED+8];
    for(;;) {
        xQueueReceive(tx_queue,&p,portMAX_DELAY);
        if(p.kind==SYNC) xr_put(p.payload+8,esp_timer_get_time(),8);
        size_t n=xr_encode(&p,encoded), offset=0;
        while(offset<n) {
            int sent=usb_serial_jtag_write_bytes(encoded+offset,n-offset,pdMS_TO_TICKS(100));
            if(sent<=0) {
                portENTER_CRITICAL(&counter_lock);tx_errors++;portEXIT_CRITICAL(&counter_lock);
                break;
            }
            offset+=sent;
        }
        if(offset==n) {portENTER_CRITICAL(&counter_lock);tx_packets++;portEXIT_CRITICAL(&counter_lock);}
        else { // delimiter recovers framing after a partial write; no silent truncation
            uint8_t zero=0;usb_serial_jtag_write_bytes(&zero,1,pdMS_TO_TICKS(10));
        }
    }
}
static void error_reply(xr_packet *p,uint16_t code) {p->kind=ERROR;p->size=2;xr_put(p->payload,code,2);enqueue(p);}
static void command(xr_packet *p,int64_t received) {
    p->timestamp_us=received;
    if(p->kind!=START&&p->size) {error_reply(p,1);return;}
    switch(p->kind) {
    case HELLO:
        p->size=snprintf((char*)p->payload,sizeof(p->payload),
            "{\"product\":\"GloveXR diagnostic\",\"firmware\":\"0.1.0\",\"protocol\":1,\"boot_id\":%lu,\"state\":\"%s\",\"max_decoded\":1024,\"sensor_driver\":\"BLOCKED_CONFIG\"}",
            (unsigned long)boot_id,state==IDLE?"IDLE":state==USB_BENCH?"USB_BENCH":"FAULT");
        enqueue(p);break;
    case STATUS: {
        uint32_t errors,sent;
        portENTER_CRITICAL(&counter_lock);errors=tx_errors;sent=tx_packets;portEXIT_CRITICAL(&counter_lock);
        p->size=snprintf((char*)p->payload,sizeof(p->payload),
            "{\"state\":%d,\"frame_size\":%u,\"rate\":%lu,\"generated\":%lu,\"tx_packets\":%lu,\"tx_errors\":%lu,\"queue_overflows\":%lu,\"queue_max\":%lu,\"rx_errors\":%lu,\"missed_deadlines\":%lu,\"uptime_us\":%lld}",
            state,frame_size,(unsigned long)rate,(unsigned long)generated,(unsigned long)sent,
            (unsigned long)errors,(unsigned long)queue_overflows,(unsigned long)queue_max,
            (unsigned long)rx_errors,(unsigned long)missed_deadlines,(long long)esp_timer_get_time());
        enqueue(p);break;}
    case START:
        if(state!=IDLE) {error_reply(p,2);break;}
        if(p->size!=6) {error_reply(p,1);break;}
        {
            uint16_t requested_size=xr_get(p->payload,2);uint32_t requested_rate=xr_get(p->payload+2,4);
            if(!requested_size||requested_size>XR_MAX_PAYLOAD||!requested_rate||requested_rate>1000) {error_reply(p,1);break;}
            frame_size=requested_size;rate=requested_rate;seq=0;state=USB_BENCH;
            next_us=esp_timer_get_time()+1000;p->size=0;enqueue(p);
        }break;
    case STOP:
        state=IDLE;p->size=0;enqueue(p);break;
    case SYNC:
        if(state!=IDLE) {error_reply(p,2);break;}
        p->size=16;xr_put(p->payload,received,8);xr_put(p->payload+8,0,8);enqueue(p);break;
    default:error_reply(p,3);break;
    }
}
void app_main(void) {
    // CRC golden vector also used by Python tests. Never start telemetry if codec is invalid.
    if(xr_crc((const uint8_t*)"123456789",9)!=0xcbf43926) return;
    {
        xr_packet test={.kind=HELLO,.request=1};uint8_t bytes[XR_MAX_DECODED+8];
        size_t count=xr_encode(&test,bytes);
        if(count!=sizeof(xr_hello_vector)||memcmp(bytes,xr_hello_vector,count)) return;
    }
    boot_id=esp_random();
    usb_serial_jtag_driver_config_t cfg={.tx_buffer_size=4096,.rx_buffer_size=2048};
    if(usb_serial_jtag_driver_install(&cfg)!=ESP_OK) return;
    tx_queue=xQueueCreate(16,sizeof(xr_packet));if(!tx_queue) return;
    if(xTaskCreate(transmit,"xr_tx",6144,NULL,4,NULL)!=pdPASS) return;
    uint8_t encoded[XR_MAX_DECODED+8],input[256];size_t size=0;int discard=0;
    for(;;) {
        int n=usb_serial_jtag_read_bytes(input,sizeof(input),0);
        for(int i=0;i<n;i++) {
            if(!input[i]) {
                if(size&&!discard) {
                    xr_packet packet;
                    if(xr_decode(encoded,size,&packet)==0) command(&packet,esp_timer_get_time());
                    else rx_errors++;
                }
                size=0;discard=0;
            } else if(!discard) {
                if(size<sizeof(encoded)) encoded[size++]=input[i];
                else {rx_errors++;discard=1;}
            }
        }
        int64_t now=esp_timer_get_time();
        if(state==USB_BENCH&&now>=next_us) {
            int64_t period=1000000/rate;
            if(now-next_us>=period) {missed_deadlines+=(now-next_us)/period;next_us=now;}
            xr_packet packet={.kind=DATA,.sequence=seq++,.timestamp_us=now,.size=frame_size};
            for(unsigned i=0;i<frame_size;i++) packet.payload[i]=(packet.sequence+i)&255;
            generated++;enqueue(&packet);next_us+=period;
        }
        vTaskDelay(1);
    }
}
