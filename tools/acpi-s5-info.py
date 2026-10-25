#!/usr/bin/env python3
"""Read-only: show the ACPI S5 (soft-off) sleep type from the DSDT and the
ICH10 PM1a control register, to diagnose boards that halt but do not power off."""
import os, re, struct

dsdt = open("/sys/firmware/acpi/tables/DSDT", "rb").read()
m = re.search(rb"_S5_\x12", dsdt)
if not m:
    raise SystemExit("no \\_S5_ package in the DSDT")
pkg = dsdt[m.end():m.end() + 16]
# Package: PkgLength, NumElements, then elements (0x0A = BytePrefix, or a bare Zero/One).
i = 2 if pkg[0] < 0x40 else 3
vals = []
while len(vals) < 2 and i < len(pkg):
    if pkg[i] == 0x0A:
        vals.append(pkg[i + 1]); i += 2
    elif pkg[i] in (0x00, 0x01):
        vals.append(pkg[i]); i += 1
    else:
        i += 1
print(f"_S5_ package bytes: {pkg.hex(' ')}")
print(f"SLP_TYPa={vals[0] if vals else '?'} SLP_TYPb={vals[1] if len(vals) > 1 else '?'}")

fadt = open("/sys/firmware/acpi/tables/FACP", "rb").read()
pm1a_cnt = struct.unpack_from("<I", fadt, 64)[0]
pm1a_evt = struct.unpack_from("<I", fadt, 56)[0]
print(f"FADT PM1a_EVT_BLK=0x{pm1a_evt:x} PM1a_CNT_BLK=0x{pm1a_cnt:x}")
fd = os.open("/dev/port", os.O_RDONLY)
os.lseek(fd, pm1a_cnt, 0)
cnt = struct.unpack("<H", os.read(fd, 2))[0]
os.lseek(fd, pm1a_evt, 0)
sts = struct.unpack("<H", os.read(fd, 2))[0]
print(f"PM1a_CNT=0x{cnt:04x} (SCI_EN={cnt & 1}, SLP_TYP={(cnt >> 10) & 7}) PM1a_STS=0x{sts:04x}")
