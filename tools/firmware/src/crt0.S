/* Start-up and exits of the boot ROM. Any trap halts the modelled core. */
#define SYSCTRL 0x30000000
  .section .text.start, "ax"
  .globl _start
_start:
  la   sp, __stack_top
  call rom_main
1:j    1b

  .text
  .globl rom_fail, rom_alarm, rom_jump
rom_fail:                 /* a0 = reason */
  li   t0, SYSCTRL
  li   t1, 0x80000000
  or   t1, t1, a0
  sw   t1, 0(t0)
1:j    1b
rom_alarm:                /* a0 = alarm code */
  li   t0, SYSCTRL
  sw   a0, 4(t0)
1:j    1b
rom_jump:                 /* a0 = entry address in flash */
  li   t0, SYSCTRL
  li   t1, 0xA5C3B007     /* FLASH_EXEC_KEY: unlock instruction fetch from flash */
  sw   t1, 12(t0)
  li   t1, 0xB007         /* BS_JUMP */
  sw   t1, 0(t0)
  jr   a0
