/* Memory map shared with rv32sim/cpu.py. */
ENTRY(_start)
MEMORY {
  ROM (rx) : ORIGIN = 0x00000000, LENGTH = 16K
  RAM (rw) : ORIGIN = 0x10000000, LENGTH = 4K
}
SECTIONS {
  .text : { KEEP(*(.text.start)) *(.text .text.*) } > ROM
  .rodata : { *(.rodata .rodata.* .srodata .srodata.*) } > ROM
  .data : { *(.data .data.* .sdata .sdata.*) } > RAM
  .bss (NOLOAD) : { *(.bss .bss.* .sbss .sbss.* COMMON) } > RAM
  __stack_top = ORIGIN(RAM) + LENGTH(RAM);
  /DISCARD/ : { *(.comment) *(.riscv.attributes) }
}
