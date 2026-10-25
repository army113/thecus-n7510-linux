# Thecus firmware analysis

How the original Thecus OS on the N7510's internal DOM was opened, for anyone
who wants to dig further or port this to another model. All scripts are in
`firmware/` and work on copies under `$THECUS_DOM_DIR` (default
`/root/thecus-dom`); none of them write to the DOM.

## DOM layout

The DOM is a 1 GB "UDinfo MDS" SATA module on AHCI port 0, MBR-partitioned:

| Partition | Size | Contents |
|---|---|---|
| 1 | 98 MB, ext2 | GRUB legacy, `bzImage` (Linux 3.10.104, 2017), `ramdisk` (gzip'd 128 MB ext2 root) |
| 2 | 24 MB, ext2 | Thecus `/etc`, including `cfg/conf.db` (sqlite) |
| 3 | 815 MB | encrypted: `img.rom`, `opt.rom`, `usrlib64.rom`, `zoneinfo.rom` (squashfs) |
| 4 | 24 MB, ext2 | logs, SMART and superblock dumps |

Firmware version 2.06.02.10.cdv; the same build serves N2800, N4510U, N4800,
N5550 and N7510.

## Steps

1. **`capture-dom-key.sh /dev/sdX`** images the DOM and unpacks the ramdisk.
   The ramdisk's `rc.sysinit` opens partition 3 with
   `losetup -n -e AES128`, a Thecus-modified loop-AES `losetup` whose `-n`
   option uses a built-in password. The script runs that binary under `strace`
   in a chroot of the ramdisk: a modern kernel rejects the loop-AES request,
   but the 16-byte key is visible in the `LOOP_SET_STATUS64` ioctl.
2. **`open-p3.sh`** opens the partition 3 copy with dm-crypt
   (`--type plain -c aes-cbc-plain -s 128`, the loop-AES single-key layout),
   checks it with `e2fsck -n`, and mounts it and the `img.rom`/`opt.rom`
   squashfs images read-only.
3. **`extract-kernel.sh`** decompresses the kernel and lists the board-driver
   strings. The board support (`thecus_io`, `n2800_io`, `pca9532`,
   `pca9532_id`, PCH GPIO) is built into the kernel, not a module.
4. **`run-agent2.sh`** runs Thecus's LCD daemon `agent2` in the chroot under
   `strace` while it talks to the real MCU; **`decode-trace.py`** turns the
   trace into frames. The results are in [LCD protocol](lcd-protocol.md).

Useful files inside `img.rom`:

| Path | Contents |
|---|---|
| `bin/conf/sysconf.<model>.txt` | per-model hardware flags (`fan_chip=ITE8728`, `atmega168com=1`, `total_tray=7`, …) |
| `bin/setfan.sh` | fan chip set-up per model |
| `bin/pic.sh` | how scripts send messages to the LCD daemons |
| `bin/agent2` | the ATmega168 LCD daemon (this protocol) |
| `SDK/Agents.py` | a Python LCD agent for the newer `0xA0`-framed MCU (N2810/N4810), not this one |

Tools needed: `strace`, `cryptsetup`, `e2fsprogs`, `util-linux`, `python3`,
and `binutils` for `strings`/`objdump`.

## Legal

This was done on owned hardware for interoperability. The repository contains
no Thecus code, binaries, firmware or keys; the scripts only work with a DOM
you have.
