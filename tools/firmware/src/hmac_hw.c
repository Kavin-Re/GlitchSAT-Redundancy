/* mac_image() using the HMAC-SHA-256 engine at HMAC_BASE (see INTERFACE.md).
 * The engine loads the key from OTP itself; software never sees it. */
#include <stdint.h>
#include "mmio.h"
#include "image.h"

void mac_image(uint32_t len, uint32_t mac[8]) {
  REG32(HMAC_BASE + HMAC_CTRL) = 1;                    /* START */
  for (uint32_t i = 0; i < 16; i += 4)
    REG32(HMAC_BASE + HMAC_MSG) = REG32(FLASH_BASE + i);
  for (uint32_t i = 0; i < len; i += 4)
    REG32(HMAC_BASE + HMAC_MSG) = REG32(PAYLOAD_ADDR + i);
  REG32(HMAC_BASE + HMAC_CTRL) = 2;                    /* FINISH */
  while ((REG32(HMAC_BASE + HMAC_STATUS) & 1u) == 0) {
  }
  for (int i = 0; i < 8; i++)
    mac[i] = REG32(HMAC_BASE + HMAC_DIGEST + 4 * i);
}
