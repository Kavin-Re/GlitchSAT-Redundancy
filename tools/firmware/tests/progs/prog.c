/* ISS self-test in C: a CRC-32 over a pseudo-random buffer, an insertion
 * sort and mixed mul/div/rem; results at 0x10000800 (checked against Python
 * in tests/test_iss.py). */
#include <stdint.h>
#define OUT ((volatile uint32_t *)0x10000800)
static uint32_t buf[48];
void _start(void) __attribute__((naked, section(".text.start")));
void _start(void) { __asm__ volatile("li sp, 0x10001000\n call body_\n ebreak"); }
uint32_t crc32(const uint8_t *p, int n) {
  uint32_t c = 0xFFFFFFFFu;
  for (int i = 0; i < n; i++) {
    c ^= p[i];
    for (int k = 0; k < 8; k++) c = (c >> 1) ^ (0xEDB88320u & (0u - (c & 1u)));
  }
  return ~c;
}
void body_(void) {
  uint32_t x = 12345;
  for (int i = 0; i < 48; i++) { x = x * 1103515245u + 12345u; buf[i] = x; }
  OUT[0] = crc32((const uint8_t *)buf, sizeof buf);
  for (int i = 1; i < 48; i++) {
    uint32_t v = buf[i]; int j = i - 1;
    while (j >= 0 && (int32_t)buf[j] > (int32_t)v) { buf[j + 1] = buf[j]; j--; }
    buf[j + 1] = v;
  }
  uint32_t acc = 0;
  for (int i = 0; i < 48; i++) acc = acc * 31u + buf[i];
  OUT[1] = acc;
  int32_t s = 0;
  for (int i = 0; i < 48; i++) {
    int32_t a = (int32_t)buf[i], b = (int32_t)(buf[(i + 7) % 48] >> 20) - 2048;
    if (b != 0) s += a / b + a % b;
    s ^= (int32_t)((uint32_t)a * (uint32_t)b);
  }
  OUT[2] = (uint32_t)s;
}
