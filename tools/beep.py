#!/usr/bin/env python3
"""Sound the PC speaker through the kernel's pcspkr input device (EV_SND / SND_TONE).
Usage: beep.py [hz] [seconds]   (default 1000 Hz, 0.5 s)"""
import glob, os, struct, sys, time

hz = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
secs = float(sys.argv[2]) if len(sys.argv) > 2 else 0.5
EV_SND, SND_TONE = 0x12, 0x02
dev = next(iter(glob.glob("/dev/input/by-path/platform-pcspkr-event-spkr")), None)
if dev is None:
    sys.exit("no pcspkr input device (modprobe pcspkr)")
fd = os.open(dev, os.O_WRONLY)


def tone(freq):
    os.write(fd, struct.pack("llHHi", 0, 0, EV_SND, SND_TONE, freq))


tone(hz)
time.sleep(secs)
tone(0)
