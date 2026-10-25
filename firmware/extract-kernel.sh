#!/bin/bash
# Decompress the Thecus bzImage payload and list board-driver strings.
set -u
cd "${THECUS_DOM_DIR:-/root/thecus-dom}"
python3 - <<'PY'
import gzip, lzma, zlib
data = open("p1/boot/bzImage", "rb").read()
out = None
for magic, kind in ((b"\x1f\x8b\x08", "gzip"), (b"\xfd7zXZ\x00", "xz"), (b"\x5d\x00\x00", "lzma")):
    start = 0
    while out is None:
        i = data.find(magic, start)
        if i < 0:
            break
        try:
            if kind == "gzip":
                d = zlib.decompressobj(16 + zlib.MAX_WBITS)
                out = d.decompress(data[i:])
            elif kind == "xz":
                out = lzma.decompress(data[i:], format=lzma.FORMAT_XZ)
            else:
                out = lzma.decompress(data[i:], format=lzma.FORMAT_ALONE)
            if not out.startswith(b"\x7fELF"):
                out = None
        except Exception:
            out = None
        start = i + 1
    if out:
        print("payload", kind, "at", i, "size", len(out))
        break
open("vmlinux", "wb").write(out)
PY
file vmlinux
strings -n 5 vmlinux | grep -iE "nxxxx|thecus_io|board_id|pca953|PCA9532|MODELNAME|HDD_ERR|U_LED|SLED|BUZZER|LCM_|gpio_ich|N7510|N5550|N4510|N2800|N4800" | sort -u | head -n 120
