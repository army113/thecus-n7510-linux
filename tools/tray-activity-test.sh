#!/bin/bash
# Map disks to trays: read each RAID member hard for 6 s, one after another,
# so its tray activity LED (or the drive sound) identifies it. Read-only.
# Usage: tray-activity-test.sh HH:MM:SS
start=$(date -d "$1" +%s)
log=/root/tray-activity-test.log
: > "$log"
i=0
for d in $(lsblk -dn -o NAME,FSTYPE | awk '$2 == "linux_raid_member" {print $1}' | sort); do
  t=$(( start + 10 * i ))
  while [ "$(date +%s)" -lt "$t" ]; do sleep 0.1; done
  serial=$(lsblk -dn -o SERIAL /dev/$d)
  model=$(lsblk -dn -o MODEL /dev/$d)
  echo "$(date +%T) step $((i + 1)) /dev/$d $model $serial $(readlink -f /sys/block/$d/device | grep -o 'ata[0-9]*')" >> "$log"
  timeout 6 dd if=/dev/$d of=/dev/null bs=1M iflag=direct skip=$(( (i + 1) * 100000 )) status=none
  i=$(( i + 1 ))
done
echo "$(date +%T) done" >> "$log"
sync
