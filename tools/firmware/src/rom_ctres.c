/* (b4) constant-time compare with a redundant result: no early exit; the OR
 * of word differences and an independent count of equal words must both
 * say "equal"; the decision is a multi-bit boolean. */
#include "rom.h"

static uint32_t ct_diff(const uint32_t *a, SRC uint32_t *b) {
  uint32_t d = 0;
  for (int i = 0; i < 8; i++)
    d |= a[i] ^ b[i];
  return d;
}

static uint32_t ct_eqcount(const uint32_t *a, SRC uint32_t *b) {
  uint32_t c = 0;
  for (int i = 0; i < 8; i++)
    c += (a[i] == b[i]);
  return c;
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
  RES uint32_t c = ct_eqcount(mac, HDR->mac);
  RES uint32_t ok = (LAUNDER(d) == 0) ? HTRUE : HFALSE;
  if (LAUNDER(ok) != HTRUE)
    rom_fail(BS_BAD_MAC);
  if (LAUNDER(d) != 0 || LAUNDER(c) != 8)
    rom_alarm(BS_BAD_MAC);
  rom_jump(PAYLOAD_ADDR + HDR->entry);
}
