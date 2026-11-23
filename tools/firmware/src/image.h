/* Boot image layout in flash (all fields little-endian):
 *   0x00 magic   'GSBI' = 0x49425347
 *   0x04 version (anti-rollback counter)
 *   0x08 length  payload bytes, multiple of 4, at most IMG_MAX_PAYLOAD
 *   0x0C entry   offset of the first instruction inside the payload
 *   0x10 mac     HMAC-SHA-256(OTP key, bytes 0x00..0x0F || payload), 32 bytes
 *   0x30 payload                                                            */
#ifndef IMAGE_H
#define IMAGE_H
#include <stdint.h>
#include "mmio.h"

#define IMG_MAGIC        0x49425347u
#define IMG_HDR_SIZE     0x30u
#define IMG_MAX_PAYLOAD  1024u

typedef struct {
  uint32_t magic;
  uint32_t version;
  uint32_t length;
  uint32_t entry;
  uint32_t mac[8];
} img_hdr_t;

#define PAYLOAD_ADDR (FLASH_BASE + IMG_HDR_SIZE)

/* computes the HMAC over the header's first 16 bytes and `len` payload bytes,
 * with the key in OTP; result as 8 little-endian words (hmac_sw.c or hmac_hw.c) */
void mac_image(uint32_t len, uint32_t mac[8]);
#endif
