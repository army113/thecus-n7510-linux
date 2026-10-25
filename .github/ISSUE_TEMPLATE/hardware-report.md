---
name: Hardware report or problem
about: Something does not work, or you tried this on another Thecus model
labels: ''
---

**Model** (e.g. N7510, N5550, N4800):

**What happened / what you expected:**

**System details** (run as root and paste the output):

```sh
cat /sys/class/dmi/id/board_name /sys/class/dmi/id/product_name /sys/class/dmi/id/bios_version
uname -r
cat /etc/os-release | head -n 2
i2cget -y "$(i2cdetect -l | awk '/SMBus I801/{sub("i2c-","",$1); print $1}')" 0x62 0 b   # board ID in bits 0-3
grep "MCU version" /var/log/n7510-lcd.log | tail -n 1
systemctl status n7510-fan n7510-lcd n7510-leds --no-pager | grep -E "Active|Main PID"
journalctl -u n7510-leds -u n7510-fan -n 20 --no-pager
```

**If you mapped pins on another model**, please list what each one did and
whether any pin reset the board. Test one pin at a time with your RAID stopped.
