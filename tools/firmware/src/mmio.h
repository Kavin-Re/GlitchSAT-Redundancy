/* Memory map and MMIO registers of the GlitchSAT boot SoC model.
 * The same numbers are in rv32sim/cpu.py and INTERFACE.md; change all three together. */
#ifndef MMIO_H
#define MMIO_H
#include <stdint.h>

#define ROM_BASE      0x00000000u  /* 16 KiB boot ROM: code + constants, execute/read only  */
#define RAM_BASE      0x10000000u  /* 4 KiB SRAM: data, stack                               */
#define FLASH_BASE    0x20000000u  /* 4 KiB external flash: boot image, read + execute (XIP) */
#define SYSCTRL_BASE  0x30000000u
#define OTP_BASE      0x40000000u  /* one-time-programmable fuses, read only                 */
#define HMAC_BASE     0x50000000u  /* optional MAC engine, 128 B window (INTERFACE.md):
                                      HMAC-SHA-256 model (hmac_hw.c) or SHA3-256 engine of
                                      secboot_hw (mac_sha3_hw.c)                             */
#define HMAC_SIZE     0x80u

/* SYSCTRL */
#define SYSCTRL_BOOT_STATUS 0x00u  /* W: boot status code; bit 31 set = boot failed, core halts */
#define SYSCTRL_ALARM       0x04u  /* W: fault alarm (a redundant check disagreed), core halts  */
#define SYSCTRL_TRNG        0x08u  /* R: 32-bit random word                                    */
#define SYSCTRL_EXEC_EN     0x0Cu  /* W: write FLASH_EXEC_KEY to allow instruction fetch from
                                      flash (until then a flash fetch traps); sticky until reset */
#define FLASH_EXEC_KEY      0xA5C3B007u

/* OTP (32-bit words) */
#define OTP_HMAC_KEY        0x00u  /* 8 words: HMAC key bytes 0..31, little-endian words        */
#define OTP_MIN_VERSION     0x20u  /* anti-rollback: lowest image version allowed to boot       */
#define OTP_MIN_VERSION_INV 0x24u  /* bitwise complement of OTP_MIN_VERSION (integrity copy)    */

/* HMAC engine */
#define HMAC_CTRL    0x00u  /* W: 1 = START (load key from OTP, begin message), 2 = FINISH          */
#define HMAC_STATUS  0x04u  /* R: bit0 DONE (digest valid)                                          */
#define HMAC_MSG     0x08u  /* W: append 4 message bytes (the word's bytes in little-endian order)  */
#define HMAC_DIGEST  0x20u  /* R: 8 words, digest bytes 0..31 as little-endian words                */
/* SHA3-256 engine only (secboot_hw/rtl/secboot_mmio.v): */
#define HMAC_VERDICT 0x40u  /* R: hardware boot word, 0x96 ACCEPT, 0x69 REJECT, 0x5A ALARM           */
#define HMAC_TOKEN   0x44u  /* R: FLASH_EXEC_KEY after a hardware ACCEPT, another value otherwise     */
#define HMAC_INFO    0x48u  /* R: bits 31:16 message blocks expected, bits 15:0 words per block       */
#define HMAC_EXPECTED 0x60u /* W: 8 words, expected tag (the image header mac), latched at FINISH     */
#define HMAC_ST_DONE   1u
#define HMAC_ST_ERR    2u
#define HMAC_ST_ACCEPT 4u

/* boot status codes */
#define BS_JUMP        0x0000B007u  /* written just before jumping to the image */
#define BS_FAIL        0x80000000u  /* | reason                                  */
#define BS_BAD_MAGIC   1u
#define BS_BAD_LENGTH  2u
#define BS_ROLLBACK    3u
#define BS_BAD_MAC     4u
#define BS_ENGINE      5u   /* MAC engine reports an error or cannot hold the message */

#define REG32(a) (*(volatile uint32_t *)(a))
#endif
