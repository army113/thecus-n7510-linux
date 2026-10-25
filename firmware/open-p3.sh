#!/bin/bash
# Decrypt the copied Thecus DOM partition 3 (loop-AES single key, aes-cbc-plain,
# 128-bit) read-only with dm-crypt, check it, and mount it and its squashfs
# images (img.rom, opt.rom) read-only. Needs the output of capture-dom-key.sh
# and cryptsetup. Never touches the DOM itself.
set -eu
cd "${THECUS_DOM_DIR:-/root/thecus-dom}"

# The key is the 16-byte lo_encrypt_key in the traced LOOP_SET_STATUS64 call.
python3 - <<'PY' > key.bin
import ast, re, sys
t = open("losetup.trace").read()
keys = [ast.literal_eval('b"' + s + '"') for s in re.findall(r'lo_encrypt_key="((?:[^"\\]|\\.)*)"', t)]
k = next(x for x in keys if x)
assert len(k) == 16, len(k)
sys.stdout.buffer.write(k)
PY
chmod 600 key.bin

[ -e /dev/mapper/thecus_p3 ] || \
  cryptsetup open --type plain --readonly -c aes-cbc-plain -s 128 --key-file key.bin p3.img thecus_p3
e2fsck -n -f /dev/mapper/thecus_p3 | tail -n 1

mkdir -p rom img opt
mountpoint -q rom || mount -o ro /dev/mapper/thecus_p3 rom
mountpoint -q img || mount -o ro,loop rom/img.rom img
mountpoint -q opt || mount -o ro,loop rom/opt.rom opt
cat img/version
ls img/bin/conf/ | grep -c sysconf
