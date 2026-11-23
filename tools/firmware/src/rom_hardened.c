/* (b8) combined, in the style of the OpenTitan ROM: OTP double read with a
 * complement copy, constant-time compare, multi-bit boolean, flow counter,
 * assembly checks that trap on mismatch, and an infective jump address. */
#include "rom.h"

#define CFI_INIT 0x100u
#define CFI_STEP 0x5au
static RES uint32_t cfi;
#define CFI_INC() (cfi = LAUNDER(cfi + CFI_STEP))

static uint32_t ct_diff_cfi(const uint32_t *a, SRC uint32_t *b) {
  uint32_t d = 0;
  for (int i = 0; i < 8; i++) {
    d |= a[i] ^ b[i];
    CFI_INC();
  }
  return d;
}

void rom_main(void) {
  uint32_t mac[8];
  cfi = LAUNDER(CFI_INIT);
  if (HDR->magic != IMG_MAGIC)
    rom_fail(BS_BAD_MAGIC);
  uint32_t len = HDR->length;
  if (len > IMG_MAX_PAYLOAD || (len & 3u) || HDR->entry >= len)
    rom_fail(BS_BAD_LENGTH);
  mac_image(len, mac);
  uint32_t minv = otp_read(OTP_MIN_VERSION);
  uint32_t minv2 = otp_read(OTP_MIN_VERSION);
  uint32_t minvi = otp_read(OTP_MIN_VERSION_INV);
  HCHECK_EQ(minv, minv2);
  HCHECK_EQ(minv ^ minvi, 0xFFFFFFFFu);
  RES uint32_t ver = HDR->version;
  if (LAUNDER(ver) < LAUNDER(minv))
    rom_fail(BS_ROLLBACK);
  CFI_INC();
  RES uint32_t d = ct_diff_cfi(mac, HDR->mac);
  RES uint32_t ok = (LAUNDER(d) == 0) ? HTRUE : HFALSE;
  CFI_INC();
  if (LAUNDER(ok) != HTRUE)
    rom_fail(BS_BAD_MAC);
  HCHECK_EQ(ok, HTRUE);
  HCHECK_EQ(d, 0);
  HCHECK_EQ(LAUNDER(ver) >= LAUNDER(minv2), 1);
  HCHECK_EQ(cfi, CFI_INIT + 10u * CFI_STEP);
  rom_jump(PAYLOAD_ADDR + HDR->entry + LAUNDER(d) * 0x9E3779B1u + (LAUNDER(ok) ^ HTRUE));
}
