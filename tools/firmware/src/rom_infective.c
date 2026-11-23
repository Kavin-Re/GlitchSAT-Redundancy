/* (b7) infective compare: the MAC difference d is mixed into the jump
 * address, so skipping the branch alone jumps to a wrong address.
 * Multiplying by an odd constant is a bijection modulo 2^32, so the
 * address is right only if d == 0. */
#include "rom.h"

static uint32_t ct_diff(const uint32_t *a, SRC uint32_t *b) {
  uint32_t d = 0;
  for (int i = 0; i < 8; i++)
    d |= a[i] ^ b[i];
  return d;
}

void rom_main(void) {
  uint32_t mac[8];
  if (HDR->magic != IMG_MAGIC)
    rom_fail(BS_BAD_MAGIC);
  uint32_t len = HDR->length;
  if (len > IMG_MAX_PAYLOAD || (len & 3u) || HDR->entry >= len)
    rom_fail(BS_BAD_LENGTH);
  mac_image(len, mac);
  if (HDR->version < otp_read(OTP_MIN_VERSION))
    rom_fail(BS_ROLLBACK);
  RES uint32_t d = ct_diff(mac, HDR->mac);
  RES uint32_t target = PAYLOAD_ADDR + HDR->entry + LAUNDER(d) * 0x9E3779B1u;
  if (LAUNDER(d) != 0)
    rom_fail(BS_BAD_MAC);
  rom_jump(target);
}
