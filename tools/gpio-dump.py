#!/usr/bin/env python3
"""Read-only dump of ICH10 GPIO configuration (GPIOBASE 0x500) for given pins.
Usage: gpio-dump.py [pins...]   (default: every pin 0-75 in GPIO mode)"""
import os, struct, sys

BASE = 0x500
BANKS = [(0x00, 0x04, 0x0C), (0x30, 0x34, 0x38), (0x40, 0x44, 0x48)]
fd = os.open("/dev/port", os.O_RDONLY)


def rd(off):
    os.lseek(fd, BASE + off, 0)
    return struct.unpack("<I", os.read(fd, 4))[0]


regs = [tuple(rd(o) for o in bank) for bank in BANKS]
pins = [int(p) for p in sys.argv[1:]] or [p for p in range(76) if regs[p // 32][0] >> (p % 32) & 1]
for p in pins:
    use, io, lvl = (r >> (p % 32) & 1 for r in regs[p // 32])
    print(f"GPIO{p:<3} {'gpio  ' if use else 'native'} {'in ' if io else 'out'} level={lvl}")
