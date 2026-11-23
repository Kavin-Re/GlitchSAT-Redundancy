/* Shared declarations for the boot-ROM variants (rom_*.c).
 * Build modes (one source, three compilations):
 *   plain   : ordinary C
 *   vol     : flash header read through volatile pointers, results held in
 *             volatile locals (the "use volatile" advice)
 *   barrier : values passed through an empty asm with a "+r" constraint
 *             (OpenTitan's launder32 pattern) so the optimiser can neither
 *             prove two computations equal nor a value constant          */
#ifndef ROM_H
#define ROM_H
#include <stdint.h>
#include "mmio.h"
#include "image.h"

#if defined(FW_VOL)
#define SRC const volatile
#define RES volatile
#else
#define SRC const
#define RES
#endif

#if defined(FW_BARRIER)
#define LAUNDER(x) ({ uint32_t v_ = (uint32_t)(x); __asm__ volatile("" : "+r"(v_)); v_; })
#define LAUNDER_PTR(p) ({ __typeof__(p) p_ = (p); __asm__ volatile("" : "+r"(p_)); p_; })
#else
#define LAUNDER(x) ((uint32_t)(x))
#define LAUNDER_PTR(p) (p)
#endif

#define HDR ((SRC img_hdr_t *)LAUNDER_PTR((SRC img_hdr_t *)FLASH_BASE))

/* multi-bit booleans: Hamming distance 8, not complements of each other
 * (the OpenTitan hardened_bool_t idea; these two values are our own) */
#define HTRUE  0x739u
#define HFALSE 0x1d4u

/* OTP is a peripheral: every read is a real bus read (volatile) */
static inline uint32_t otp_read(uint32_t off) { return REG32(OTP_BASE + off); }

/* HARDENED_CHECK_EQ in the OpenTitan style: assembly the compiler cannot
 * remove; tests equality twice with opposite branch senses; executes an
 * illegal instruction (trap, core halts) on mismatch. */
#define HCHECK_EQ(a, b) __asm__ volatile(                \
    "beq %0, %1, 1f\n\tunimp\n1:\n\t"                     \
    "bne %0, %1, 2f\n\tj 3f\n2:\n\tunimp\n3:"             \
    :: "r"((uint32_t)(a)), "r"((uint32_t)(b)))

/* exits, in crt0.S */
void rom_fail(uint32_t reason) __attribute__((noreturn));   /* BOOT_STATUS = BS_FAIL|reason */
void rom_alarm(uint32_t code) __attribute__((noreturn));    /* ALARM = code                 */
void rom_jump(uint32_t addr) __attribute__((noreturn));     /* BOOT_STATUS = BS_JUMP; jr addr */
void rom_main(void) __attribute__((noreturn));
#endif
