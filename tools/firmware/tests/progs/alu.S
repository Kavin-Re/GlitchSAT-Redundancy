/* ISS self-test: each result is stored to RAM at 0x10000000 + 4*i; the
 * expected values are derived by hand from the RISC-V spec in
 * tests/test_iss.py. Ends with ebreak (the simulator traps = stops). */
  .section .text.start, "ax"
  .globl _start
_start:
  li   s0, 0x10000000
  li   a0, -7
  li   a1, 2
  div  t0, a0, a1;      sw t0, 0(s0)     /* -3 (round toward zero) */
  rem  t0, a0, a1;      sw t0, 4(s0)     /* -1 */
  divu t0, a0, a1;      sw t0, 8(s0)     /* 0x7FFFFFFC */
  remu t0, a0, a1;      sw t0, 12(s0)    /* 1 */
  div  t0, a0, zero;    sw t0, 16(s0)    /* -1 (div by zero) */
  rem  t0, a0, zero;    sw t0, 20(s0)    /* -7 */
  li   a2, 0x80000000
  li   a3, -1
  div  t0, a2, a3;      sw t0, 24(s0)    /* 0x80000000 (overflow) */
  rem  t0, a2, a3;      sw t0, 28(s0)    /* 0 */
  mulh t0, a2, a3;      sw t0, 32(s0)    /* 0 : (-2^31)*(-1)=2^31 -> high 0 */
  mulhu t0, a2, a3;     sw t0, 36(s0)    /* 0x7FFFFFFF */
  mulhsu t0, a3, a3;    sw t0, 40(s0)    /* -1 : (-1)*(2^32-1) high word = -1 */
  mul  t0, a0, a0;      sw t0, 44(s0)    /* 49 */
  sra  t0, a2, a1;      sw t0, 48(s0)    /* 0xE0000000 */
  srl  t0, a2, a1;      sw t0, 52(s0)    /* 0x20000000 */
  li   a4, 33
  sll  t0, a1, a4;      sw t0, 56(s0)    /* 4 (shift amount mod 32) */
  slt  t0, a0, a1;      sw t0, 60(s0)    /* 1 */
  sltu t0, a0, a1;      sw t0, 64(s0)    /* 0 */
  sltiu t0, a1, -1;     sw t0, 68(s0)    /* 1 (imm sign-extended then unsigned) */
  li   t1, 0x8081
  sh   t1, 72(s0)
  lb   t0, 72(s0);      sw t0, 76(s0)    /* 0xFFFFFF81 */
  lbu  t0, 73(s0);      sw t0, 80(s0)    /* 0x80 */
  lh   t0, 72(s0);      sw t0, 84(s0)    /* 0xFFFF8081 */
  lhu  t0, 72(s0);      sw t0, 88(s0)    /* 0x8081 */
  c.li a5, -32
  c.srai a5, 1;         sw a5, 92(s0)    /* -16 */
  c.lui a5, 0xfffe0;     sw a5, 96(s0)   /* 0xFFFE0000 */
  auipc t0, 0;          sw t0, 100(s0)   /* address of this auipc */
  la   t2, 1f
  jalr t1, 0(t2)
  li   t0, 0x111                         /* skipped */
1:sw   t1, 104(s0)                       /* return address = after jalr */
  li   t0, 0
  li   s1, 5
2:c.addi t0, 3
  c.addi s1, -1
  c.bnez s1, 2b
  sw   t0, 108(s0)                       /* 15 */
  li   t0, 7
  bge  a0, t0, 3f                        /* -7 >= 7 false */
  bltu a0, t0, 3f                        /* 0xFFFFFFF9 < 7 false */
  blt  a0, t0, 4f                        /* taken */
3:li   t0, 0xBAD
  sw   t0, 112(s0)
  ebreak
4:li   t0, 0x600D
  sw   t0, 112(s0)
  ebreak
