#!/bin/sh
# Rebuilds the ISS self-test ELFs (committed, so tests run without clang).
set -e
cd "$(dirname "$0")"
F="--target=riscv32-unknown-elf -march=rv32imc -mabi=ilp32 -ffreestanding -fno-builtin -nostdlib"
clang $F -c alu.S -o alu.o; ld.lld -T ../../src/link.ld alu.o -o alu.elf
for O in O0 O2 Os; do
  clang $F -$O -c prog.c -o prog.o; ld.lld -T ../../src/link.ld prog.o -o prog-$O.elf
done
rm -f *.o
