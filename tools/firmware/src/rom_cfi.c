/* (b5) flow-integrity counter: every step of the check adds a constant to a
 * counter; jump only if the counter shows that every step ran. */
#include "rom.h"

#define CFI_INIT 0x100u
#define CFI_STEP 0x5au
static RES uint32_t cfi;
#define CFI_INC() (cfi = LAUNDER(cfi + CFI_STEP))

static int mac_cmp_cfi(const uint32_t *a, SRC uint32_t *b) {
  for (int i = 0; i < 8; i++) {
    CFI_INC();
    if (a[i] != b[i])
      return 1;
  }
  return 0;
}

void rom_main(void) {
  uint32_t mac[8];
  cfi = LAUNDER(CFI_INIT);
  if (HDR->magic != IMG_MAGIC)
    rom_fail(BS_BAD_MAGIC);
  uint32_t len = HDR->length;
  if (len > IMG_MAX_PAYLOAD || (len & 3u) || HDR->entry >= len)
    rom_fail(BS_BAD_LENGTH);
  CFI_INC();
  mac_image(len, mac);
  if (HDR->version < otp_read(OTP_MIN_VERSION))
    rom_fail(BS_ROLLBACK);
  CFI_INC();
  if (mac_cmp_cfi(mac, HDR->mac) != 0)
    rom_fail(BS_BAD_MAC);
  CFI_INC();
  if (LAUNDER(cfi) != CFI_INIT + 11u * CFI_STEP)
    rom_alarm(0xCF1);
  rom_jump(PAYLOAD_ADDR + HDR->entry);
}
