#!/bin/bash
# Run Thecus's agent2 (LCD daemon) inside the ramdisk chroot under strace, to
# record its serial exchange with the front-panel MCU. All Thecus images are
# mounted read-only; only the chroot copy's /var is writable. Needs the output
# of capture-dom-key.sh and open-p3.sh. agent2 owns /dev/ttyS0 while it runs,
# so n7510-lcd is stopped and restarted around it.
# Usage: run-agent2.sh [seconds]   then: decode-trace.py
# While it runs, feed it the boot commands Thecus would send, for example:
#   echo "agent2 0 STARTWD " > $THECUS_DOM_DIR/chroot/var/tmp/avrpipe
set -u
D=${THECUS_DOM_DIR:-/root/thecus-dom}
C=$D/chroot
SECS=${1:-120}

mnt() { mountpoint -q "$2" || mount "$@"; }
mkdir -p $C/img $C/usr/lib64 $C/opt $C/etc $C/var
[ -f $C/var/.unpacked ] || { tar -C $C -xzpf $C/var.tar.gz 2>/dev/null; touch $C/var/.unpacked; }
mkdir -p $C/var/tmp $C/var/run
mnt -o ro,loop $D/rom/img.rom $C/img
mnt -o ro,loop $D/rom/usrlib64.rom $C/usr/lib64
mnt -o ro,loop $D/rom/opt.rom $C/opt
mnt -o ro,bind $D/p2 $C/etc
mnt --bind /dev $C/dev
mnt -t proc proc $C/proc
echo N7510 > $C/var/run/model

lcd_was_active=$(systemctl is-active n7510-lcd 2>/dev/null)
[ "$lcd_was_active" = active ] && systemctl stop n7510-lcd
: > $D/agent2.trace
timeout $SECS strace -f -tt -s 2048 -x -e trace=open,openat,read,write,ioctl,execve \
  -o $D/agent2.trace chroot $C /img/bin/agent2 -p 0 > $D/agent2.out 2>&1
echo "agent2 exit $?" >> $D/agent2.out
[ "$lcd_was_active" = active ] && systemctl start n7510-lcd

umount $C/proc $C/dev $C/etc $C/opt $C/usr/lib64 $C/img
