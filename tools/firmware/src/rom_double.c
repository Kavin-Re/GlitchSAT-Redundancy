/* (b1) double check: the rollback test and the MAC compare are each done
 * twice; if the second disagrees with the first, raise the alarm. */
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
  if (HDR->version < otp_read(OTP_MIN_VERSION))
    rom_fail(BS_ROLLBACK);
  if (HDR->version < otp_read(OTP_MIN_VERSION))
    rom_alarm(BS_ROLLBACK);
  RES int r1 = mac_cmp(mac, HDR->mac);
  if (LAUNDER(r1) != 0)
    rom_fail(BS_BAD_MAC);
  RES int r2 = mac_cmp(mac, HDR->mac);
  if (LAUNDER(r2) != 0)
    rom_alarm(BS_BAD_MAC);
  rom_jump(PAYLOAD_ADDR + HDR->entry);
}
