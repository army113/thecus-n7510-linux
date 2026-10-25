#!/usr/bin/env python3
"""Timed test of ICH10 GPIO pins as tray activity LEDs (Thecus N7510).

For each pin: switch to GPIO output, drive low 3 s, high 3 s, then restore the
pin's original USE_SEL / IO_SEL / LVL bits. Uses /dev/port at GPIOBASE 0x500.
Usage: gpio-led-test.py HH:MM:SS [pins...]   (default pins 0 2 3 4 5)
"""
import os, struct, sys, time

BASE = 0x500
USE_SEL, IO_SEL, LVL = 0x00, 0x04, 0x0C   # bank 0, GPIO 0-31
LOG = "/root/gpio-led-test.log"

start = time.mktime(time.strptime(time.strftime("%Y-%m-%d ") + sys.argv[1], "%Y-%m-%d %H:%M:%S"))
pins = [int(p) for p in sys.argv[2:]] or [0, 2, 3, 4, 5]
fd = os.open("/dev/port", os.O_RDWR)
log = open(LOG, "w", buffering=1)


def rd(off):
    os.lseek(fd, BASE + off, 0)
    return struct.unpack("<I", os.read(fd, 4))[0]


def wr(off, val):
    os.lseek(fd, BASE + off, 0)
    os.write(fd, struct.pack("<I", val))


def setbit(off, bit, on):
    v = rd(off)
    wr(off, v | (1 << bit) if on else v & ~(1 << bit))


def note(msg):
    log.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    log.flush()
    os.fsync(log.fileno())


for i, pin in enumerate(pins):
    t0 = start + 8 * i
    while time.time() < t0:
        time.sleep(0.05)
    orig = {off: (rd(off) >> pin) & 1 for off in (USE_SEL, IO_SEL, LVL)}
    note(f"GPIO{pin} original use={orig[USE_SEL]} in={orig[IO_SEL]} lvl={orig[LVL]}; low")
    setbit(LVL, pin, False)
    setbit(IO_SEL, pin, False)      # 0 = output
    setbit(USE_SEL, pin, True)      # 1 = GPIO function
    time.sleep(3)
    note(f"GPIO{pin} high")
    setbit(LVL, pin, True)
    time.sleep(3)
    setbit(USE_SEL, pin, bool(orig[USE_SEL]))
    setbit(IO_SEL, pin, bool(orig[IO_SEL]))
    setbit(LVL, pin, bool(orig[LVL]))
    note(f"GPIO{pin} restored")
note("done")
