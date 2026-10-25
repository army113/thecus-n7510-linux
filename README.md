# Thecus N7510 on modern Linux

Front-panel LCD, buttons, fans, LEDs and beeper for the **Thecus N7510**
(7-bay, Intel Atom D2701, "Granite Well" board) running any current Linux
distribution instead of the end-of-life Thecus OS.

Thecus stopped updating these boxes years ago. The hardware is a plain x86 PC,
so it runs Debian, openmediavault, Ubuntu, Fedora and others fine, but out of
the box the LCD sits on its boot animation, the buttons do nothing, the fans
run at fixed BIOS speeds and none of the tray or status LEDs work. This
repository fixes that with three small daemons that use only the Python 3
standard library and mainline kernel drivers.

<p align="center">
  <img src="docs/images/n7510-front.jpg" alt="Thecus N7510 front panel with trays 1 to 7 numbered and the LCD showing RAID md0 clean" width="320"><br>
  <sub>Status LEDs down the left edge (power, System "!", LAN1, LAN2, USB, eSATA),
  trays 1–7 from the top, LCD and buttons at the bottom.</sub>
</p>

| Feature | Without this | With this |
|---|---|---|
| Front LCD | stuck on the boot animation | pages: hostname, WAN/LAN IP, RAID state |
| Buttons and menu | dead | password-protected menu: fan mode, reboot, power off, change password |
| Fans | fixed BIOS speeds, PWM disabled | follow the hottest disk; full speed on overheating or any fault |
| Tray LEDs (red) | off | lit while that tray's disk is missing or out of sync |
| Tray LEDs (green) | only trays 6–7 | all seven blink on disk activity |
| System "!" LED | off | red on a fault or overheating (plus three beeps), orange during RAID resync |
| USB LED | off | on while a USB storage device is attached |

Tested on openmediavault 6 (Debian 11, kernel 6.0). The code avoids
distribution-specific pieces so it should move to newer releases unchanged.

> **Not affiliated with Thecus.** Use at your own risk. This drives hardware
> directly; read [Safety](#safety) first.

## Install

```sh
git clone https://github.com/army113/thecus-n7510-linux.git
cd thecus-n7510-linux
sudo ./install.sh
```

The installer copies the daemons to `/opt/n7510/`, sets the `it87` option
`fix_pwm_polarity=1`, autoloads `it87`, `drivetemp`, `i2c-i801`, `i2c-dev`
and `pcspkr`, enables `n7510-fan`, `n7510-lcd` and `n7510-leds`, and adds
the `n7510-poweroff` shutdown hook so power off really switches the box off. On
openmediavault it also installs a small fix that keeps the systemd journal
working under folder2ram. `sudo ./uninstall.sh` removes everything.

Requirements: Python 3.7+, systemd, a kernel with the drivers above
(any mainstream distribution kernel). Optional: `gpio_ich` with
`acpi_enforce_resources=lax` on the kernel command line; without it, the green
tray LEDs are driven through `/dev/port`, which Secure Boot lockdown blocks.

LCD menu actions start in **dry-run** mode (choices are only logged). Enable
them with `sudo touch /etc/n7510/lcd-actions-enabled && sudo systemctl restart n7510-lcd`.
The default LCD password is `0000`.

## Status and limitations

Version 0.1.3. Built and tested on **one** N7510 (board ID 6, LCD MCU
firmware `01.04.00`), first on openmediavault 6 / Debian 11 (kernel 6.0),
then on a fresh openmediavault 8 / Debian 13 (kernel 7.2 from backports, 6.12
also booted), where `install.sh` ran unchanged.

| Area | Status |
|---|---|
| Fans, LCD pages, password entry, fan-mode menu, change password, reboot and power off from the panel | tested |
| Power off actually cutting power (`n7510-poweroff` hook, see below) | tested |
| Power button (short press: clean shutdown and power off) | tested; on openmediavault set *System → Power Management → Power button* to **Shutdown** (its default, Standby, suspends) |
| Wake-on-LAN from power-off | tested (magic packet; enable with `ethtool -s <nic> wol g`, OMV's interface setting, or systemd `WakeOnLan=magic`) |
| Scheduled power-on (RTC wake alarm, `rtcwake`) | tested (`rtcwake -m no -s 120`, then power off; works with the BIOS's own "Resume by Alarm" left Disabled) |
| Overheat alarm (board sensors ≥ 60 °C, CPU ≥ 70 °C, disk ≥ 50 °C: full fans, red "!", beeps) | logic tested, not triggered by real heat |
| Tray LEDs (red/green), System "!" red + beeps, USB LED | tested, including a real disk dropping out of a tray |
| System "!" orange during RAID resync/check | tested (RAID check) |
| eSATA LED | not controllable from software as far as we can tell; probably lit by the eSATA controller itself (unconfirmed, no eSATA device to test) |
| USB Copy on the panel | answered with "USB Copy N/A"; copying is not implemented |
| Other Thecus models | untested; the pin map may differ |

Known limitations:

- **Power off needs a fix on this board.** Without it, `poweroff` ends at
  `reboot: Power down` and the box stays on: the BIOS traps the ACPI S5 write
  into SMM (`SLP_SMI_EN`), and its handler fails on a missing TPM method
  (`\_SB.PCI0.LPCB.TPM.PTS`, `AE_NOT_FOUND`). The installer adds a systemd
  `system-shutdown` hook, `n7510-poweroff`, that clears `SLP_SMI_EN` as the
  last step of a power-off, so the kernel's normal S5 write reaches the
  hardware. It does nothing on reboot or halt, or on other boards.
- The green LEDs of trays 1–5 need either the kernel's `gpio_ich` driver
  (with `acpi_enforce_resources=lax`) or `/dev/port`, and the power-off hook
  needs `/dev/port`. Kernel lockdown, as enabled by Secure Boot on many
  distributions, blocks `/dev/port`: then, without `gpio_ich`, those five LEDs
  stay dark, and power off halts without cutting power (hold the power button).
  Everything else is unaffected.
- The default LCD password is `0000`. Change it from the panel menu.
- Disks are matched to trays by serial number on first start
  (`/etc/n7510/tray-map.json`). After moving disks between trays, delete that
  file and restart `n7510-leds`.
- The LED daemon samples disk activity 20 times a second, about 3 % of one
  Atom thread.

## Safety

- **PCA9532 `0x62` pin 7 hard-resets the whole board.** The daemons only ever
  write pins 9, 10 and 12 of that chip (enforced in code). If you probe pins
  yourself, stop your RAID arrays first and switch one pin at a time.
- Pins 0–3 of `0x62` are board-ID inputs; never drive them.
- The original Thecus firmware lives on an internal 1 GB DOM. Nothing here
  writes to it, and the firmware tools work on an image copy.
- Stopping `n7510-fan` sets both fans to full speed.

## How it was done

The protocols were recovered from the Thecus firmware still sitting on the
internal DOM:

1. Image the DOM and unpack its ramdisk. Partition 3 is encrypted (loop-AES,
   AES-128) with a key built into Thecus's modified `losetup -n`. Running that
   binary under `strace` in a chroot shows the key in the `LOOP_SET_STATUS64`
   ioctl, even though a modern kernel rejects the call. The key is **not**
   published here; `firmware/capture-dom-key.sh` recovers it from your own DOM.
2. The decrypted partition holds Thecus's per-model configs, scripts and the
   LCD daemon `agent2`. Running `agent2` under `strace` recorded its serial
   exchange with the panel's ATmega168, and disassembling it decoded the menus
   and settings: [LCD protocol](docs/lcd-protocol.md).
3. Every LED, fan and pin was then mapped on a live unit, one pin at a time:
   [hardware reference](docs/hardware.md).

Details of the firmware layout and tools: [firmware analysis](docs/firmware.md).

## Repository layout

| Path | Contents |
|---|---|
| `src/` | the three daemons |
| `systemd/` | service units and the openmediavault journald fix |
| `tools/` | probing and test helpers, see [tools](tools/README.md) |
| `firmware/` | DOM imaging, decryption and `agent2` tracing scripts |
| `docs/` | hardware reference, LCD protocol, firmware analysis |

## Related models

The N7510 shares its firmware build (`2.06.x.cdv`) with the N2800, N4510U,
N4800 and N5550, and its board design with the N5550. Much of this probably
applies there too, but pin maps differ between boards (the N5550 reports
board ID 2, the N7510 6), so verify one pin at a time before trusting this
map on another model. Reports and pull requests are welcome.

## Credits

- [ipilcher/n5550](https://github.com/ipilcher/n5550): the N5550 board
  module, LCD notes and the Debian/openmediavault recipe that made this
  possible.
- [Nicholas Starke](https://starkeblog.com/cryptography/firmware/2024/06/11/thecus-nas-firmware-decrypt.html):
  Thecus firmware-update decryption.
- [jncronin/pymonitor](https://github.com/jncronin/pymonitor),
  [system1357/Thecus_tools](https://github.com/system1357/Thecus_tools) and
  [mStirner/thecus-nas](https://github.com/mStirner/thecus-nas): earlier
  Thecus LCD and GPIO work.
- The openmediavault forum threads on Thecus hardware.

## License

[MIT](LICENSE). Thecus is a trademark of its owner; this project contains no
Thecus code or firmware.
