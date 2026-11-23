/* (b3) complemented checks: each decision is kept as a multi-bit boolean and
 * as its complement, set by separate compares; the OTP minimum version is
 * read together with its complement copy (an OTP integrity check). */
#include "rom.h"

static int mac_cmp(const uint32_t *a, SRC uint32_t *b) {
  for (int i = 0; i < 8; i++)
    if (a[i] != b[i])
      return 1;
  return 0;
}

void rom_main(void) {
  uint32_t mac[8];
  if (HDR->magic != IMG_MAGIC)
    rom_fail(BS_BAD_MAGIC);
  uint32_t len = HDR->length;
  if (len > IMG_MAX_PAYLOAD || (len & 3u) || HDR->entry >= len)
    rom_fail(BS_BAD_LENGTH);
  mac_image(len, mac);
  uint32_t minv = otp_read(OTP_MIN_VERSION);
  if ((minv ^ otp_read(OTP_MIN_VERSION_INV)) != 0xFFFFFFFFu)
    rom_alarm(BS_ROLLBACK);
  RES uint32_t ok = HFALSE, nok = ~HFALSE;
  if (HDR->version >= minv && mac_cmp(mac, HDR->mac) == 0)
    ok = HTRUE;
  if (HDR->version >= minv && mac_cmp(mac, HDR->mac) == 0)
    nok = ~HTRUE;
  if (LAUNDER(ok) != HTRUE)
    rom_fail(BS_BAD_MAC);
  if ((LAUNDER(ok) ^ LAUNDER(nok)) != 0xFFFFFFFFu)
    rom_alarm(BS_BAD_MAC);
  rom_jump(PAYLOAD_ADDR + HDR->entry);
}
