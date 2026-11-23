"""Minimal ELF32 little-endian loader (PT_LOAD segments, .text range, symbols).

Source-line information is not parsed here; build.py stores it next to each
ELF as <name>.lines.json (from llvm-dwarfdump) and load_elf() picks it up.
"""
import json
import os
import struct

from . import cpu


def _sections(data):
    (shoff,) = struct.unpack_from("<I", data, 0x20)
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", data, 0x2E)
    secs = []
    for i in range(shnum):
        f = struct.unpack_from("<IIIIIIIIII", data, shoff + i * shentsize)
        secs.append(dict(name_off=f[0], type=f[1], flags=f[2], addr=f[3], offset=f[4], size=f[5],
                         link=f[6], info=f[7], entsize=f[9]))
    strtab = secs[shstrndx]
    for s in secs:
        o = strtab["offset"] + s["name_off"]
        s["name"] = data[o:data.index(b"\0", o)].decode()
    return secs


def load_elf(path):
    data = open(path, "rb").read()
    assert data[:4] == b"\x7fELF" and data[4] == 1 and data[5] == 1, "need ELF32 little endian"
    (machine,) = struct.unpack_from("<H", data, 0x12)
    assert machine == 243, "not RISC-V"
    phoff, = struct.unpack_from("<I", data, 0x1C)
    phentsize, phnum = struct.unpack_from("<HH", data, 0x2A)
    rom = bytearray()
    ram = bytearray()
    for i in range(phnum):
        p_type, p_off, p_vaddr, p_paddr, p_filesz, p_memsz, p_flags, p_align = struct.unpack_from(
            "<IIIIIIII", data, phoff + i * phentsize)
        if p_type != 1 or p_memsz == 0:
            continue
        seg = data[p_off:p_off + p_filesz] + b"\0" * (p_memsz - p_filesz)
        if cpu.ROM_BASE <= p_vaddr < cpu.ROM_BASE + cpu.ROM_SIZE:
            o = p_vaddr - cpu.ROM_BASE
            if len(rom) < o + len(seg):
                rom.extend(b"\0" * (o + len(seg) - len(rom)))
            rom[o:o + len(seg)] = seg
        elif cpu.RAM_BASE <= p_vaddr < cpu.RAM_BASE + cpu.RAM_SIZE:
            o = p_vaddr - cpu.RAM_BASE
            if len(ram) < o + len(seg):
                ram.extend(b"\0" * (o + len(seg) - len(ram)))
            ram[o:o + len(seg)] = seg
        else:
            raise ValueError("segment at 0x%x outside the memory map" % p_vaddr)
    secs = _sections(data)
    text = [s for s in secs if s["name"] == ".text"][0]
    symbols = {}
    for s in secs:
        if s["type"] != 2:  # SHT_SYMTAB
            continue
        strs = secs[s["link"]]
        for j in range(s["size"] // 16):
            st_name, st_value, st_size, st_info, st_other, st_shndx = struct.unpack_from(
                "<IIIBBH", data, s["offset"] + j * 16)
            if st_name == 0:
                continue
            o = strs["offset"] + st_name
            nm = data[o:data.index(b"\0", o)].decode()
            if (st_info & 0xF) in (0, 1, 2) and st_shndx != 0:
                if nm not in symbols or st_size:
                    symbols[nm] = (st_value, st_size)
    lines = {}
    lp = os.path.splitext(path)[0] + ".lines.json"
    if os.path.exists(lp):
        lines = {int(k): tuple(v) for k, v in json.load(open(lp)).items()}
    return cpu.Program(rom, ram, symbols, (text["addr"], text["addr"] + text["size"]), lines)
