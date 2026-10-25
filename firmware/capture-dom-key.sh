#!/bin/bash
# Image the Thecus DOM (read-only), unpack its ramdisk, and capture the fixed
# loop-AES key of partition 3 by running Thecus's own `losetup -n` under strace
# in a chroot. Writes everything under $THECUS_DOM_DIR (default
# /root/thecus-dom); never writes the DOM. Needs: strace, util-linux, gzip.
# Usage: capture-dom-key.sh /dev/sdX   (the 1 GB "UDinfo MDS" DOM)
# Next: open-p3.sh (decrypt the copy), extract-kernel.sh, run-agent2.sh.
set -eu
DOM=${1:?DOM device, e.g. /dev/sdb}
D=${THECUS_DOM_DIR:-/root/thecus-dom}
mkdir -p $D && cd $D

[ -f dom.img ] || dd if="$DOM" of=dom.img bs=4M status=none
sha256sum "$DOM" dom.img

# Partition 1 holds GRUB, the kernel (bzImage) and the gzip'd ext2 ramdisk.
L=$(losetup -r -P -f --show dom.img)
mkdir -p p1 p2 p4 rd/root
for p in 1 2 4; do mountpoint -q p$p || mount -o ro ${L}p$p p$p; done
[ -f rd/rootfs.img ] || gzip -dc p1/boot/ramdisk > rd/rootfs.img
mountpoint -q rd/root || mount -o ro,loop rd/rootfs.img rd/root

# Writable chroot copy of the ramdisk, with a copy of partition 3.
start=$(sfdisk -d dom.img | awk '/img3 /{gsub(",","",$4); print $4}')
size=$(sfdisk -d dom.img | awk '/img3 /{gsub(",","",$6); print $6}')
[ -f p3.img ] || dd if=dom.img of=p3.img bs=512 skip="$start" count="$size" status=none
mkdir -p chroot && [ -f chroot/init ] || cp -a rd/root/. chroot/
mkdir -p chroot/work && cp p3.img chroot/work/p3.img
mount --bind /dev chroot/dev
mount -t proc proc chroot/proc
LD=$(losetup -f)
# A current kernel rejects the loop-AES request (EINVAL), but the key is in the ioctl.
strace -f -v -s 256 -e trace=ioctl -o losetup.trace chroot chroot /sbin/losetup -n -e AES128 "$LD" /work/p3.img || true
losetup -d "$LD" 2>/dev/null || true
umount chroot/proc chroot/dev
grep -c 'lo_encrypt_key_size=16' losetup.trace && echo "key captured in $D/losetup.trace; run open-p3.sh"
