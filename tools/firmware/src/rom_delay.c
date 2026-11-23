/* (b6) random delay stubs: a TRNG-driven number (0..15) of nops before the
 * rollback test and before the MAC compare of the naive routine. */
#include "rom.h"

static int mac_cmp(const uint32_t *a, SRC uint32_t *b) {
  for (int i = 0; i < 8; i++)
    if (a[i] != b[i])
      return 1;
  return 0;
}

static void rand_delay(void) {
  uint32_t n = REG32(SYSCTRL_BASE + SYSCTRL_TRNG) & 15u;
  for (uint32_t i = 0; i < n; i++)
    __asm__ volatile("nop");
}

void rom_main(void) {
  uint32_t mac[8];
  if (HDR->magic != IMG_MAGIC)
    rom_fail(BS_BAD_MAGIC);
  uint32_t len = HDR->length;
  if (len > IMG_MAX_PAYLOAD || (len & 3u) || HDR->entry >= len)
    rom_fail(BS_BAD_LENGTH);
  mac_image(len, mac);
  rand_delay();
  if (HDR->version < otp_read(OTP_MIN_VERSION))
    rom_fail(BS_ROLLBACK);
  rand_delay();
  if (mac_cmp(mac, HDR->mac) != 0)
    rom_fail(BS_BAD_MAC);
  rom_jump(PAYLOAD_ADDR + HDR->entry);
}
