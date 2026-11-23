/* mac_image() for the SHA3-256 engine of secboot_hw (rtl/secboot_mmio.v) at HMAC_BASE.
 * The engine computes SHA3-256(K136 || M): K136 = the 32 OTP key bytes and 104 zero
 * bytes (the engine holds the key; software never sees it), M = exactly
 * blocks * words_per_block message words (register INFO; 8 x 34 words = 1088 B in the
 * SoC build). M = header bytes 0x00..0x0F || payload || zero words up to the end. Zero
 * padding is unambiguous because `length` is inside the hashed header.
 * The header mac is written to EXPECTED so the engine can give its own verdict and
 * TOKEN; the boot ROM variants still compare mac[] in software (see INTERFACE.md). */
#include <stdint.h>
#include "mmio.h"
#include "image.h"
#include "rom.h"

const uint32_t mac_engine_sha3 = 0x53484133u;   /* 'SHA3': marks the ELF for the simulator */

void mac_image(uint32_t len, uint32_t mac[8]) {
  uint32_t info = REG32(HMAC_BASE + HMAC_INFO);
  uint32_t words = (info >> 16) * (info & 0xFFFFu);
  if (words * 4u < 16u + len)
    rom_fail(BS_ENGINE);
  REG32(HMAC_BASE + HMAC_CTRL) = 1;                    /* START */
  uint32_t n = 0;
  for (uint32_t i = 0; i < 16; i += 4, n++)
    REG32(HMAC_BASE + HMAC_MSG) = REG32(FLASH_BASE + i);
  for (uint32_t i = 0; i < len; i += 4, n++)
    REG32(HMAC_BASE + HMAC_MSG) = REG32(PAYLOAD_ADDR + i);
  for (; n < words; n++)
    REG32(HMAC_BASE + HMAC_MSG) = 0;
  for (int i = 0; i < 8; i++)
    REG32(HMAC_BASE + HMAC_EXPECTED + 4 * i) = REG32(FLASH_BASE + 0x10 + 4 * i);
  REG32(HMAC_BASE + HMAC_CTRL) = 2;                    /* FINISH */
  uint32_t st;
  while (((st = REG32(HMAC_BASE + HMAC_STATUS)) & HMAC_ST_DONE) == 0) {
  }
  if (st & HMAC_ST_ERR)
    rom_fail(BS_ENGINE);
  for (int i = 0; i < 8; i++)
    mac[i] = REG32(HMAC_BASE + HMAC_DIGEST + 4 * i);
}
