#!/usr/bin/env python3
"""Set or restore one ICH10 GPIO pin (Thecus N7510 LED probing) via /dev/port.

  gpio-pin.py <pin> low|high   switch the pin to GPIO output at that level
                               (original bits saved on first change)
  gpio-pin.py <pin> restore    put back the saved USE_SEL / IO_SEL / LVL bits
  gpio-pin.py <pin> show       print the current bits
Pins 0-31 use bank 1, 32-63 bank 2 (GPIOBASE 0x500).
"""
import json, os, struct, sys

BASE = 0x500
BANKS = [(0x00, 0x04, 0x0C), (0x30, 0x34, 0x38)]   # USE_SEL, IO_SEL, LVL
SAVE = "/root/gpio-pin-saved.json"

pin, action = int(sys.argv[1]), sys.argv[2]
use_off, io_off, lvl_off = BANKS[pin // 32]
bit = pin % 32
fd = os.open("/dev/port", os.O_RDWR)


def rd(off):
    os.lseek(fd, BASE + off, 0)
    return struct.unpack("<I", os.read(fd, 4))[0]


def wr(off, val):
    os.lseek(fd, BASE + off, 0)
    os.write(fd, struct.pack("<I", val))


def setbit(off, on):
    v = rd(off)
    wr(off, v | (1 << bit) if on else v & ~(1 << bit))


def bits():
    return {k: (rd(o) >> bit) & 1 for k, o in (("use", use_off), ("in", io_off), ("lvl", lvl_off))}


saved = json.load(open(SAVE)) if os.path.exists(SAVE) else {}
if action in ("low", "high"):
    if str(pin) not in saved:
        saved[str(pin)] = bits()
        json.dump(saved, open(SAVE, "w"))
    setbit(lvl_off, action == "high")
    setbit(io_off, False)
    setbit(use_off, True)
elif action == "restore":
    orig = saved.pop(str(pin), None)
    if orig is None:
        sys.exit(f"GPIO{pin}: nothing saved")
    setbit(use_off, bool(orig["use"]))
    setbit(io_off, bool(orig["in"]))
    setbit(lvl_off, bool(orig["lvl"]))
    json.dump(saved, open(SAVE, "w"))
print(f"GPIO{pin} {action}: {bits()}")
