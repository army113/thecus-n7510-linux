#!/bin/bash
# Timed single-output test of PCA9532 0x64 (tray error LEDs on the Thecus N7510).
# Output n is on for 4 s starting at START + 6*n seconds; everything else stays off.
# Usage: tray-led-test.sh HH:MM:SS
start=$(date -d "$1" +%s)
log=/root/tray-led-test.log
: > "$log"
off() { for r in 6 7 8 9; do i2cset -y 0 0x64 $r 0x00; done; }
off
for n in $(seq 0 15); do
  t=$(( start + 6 * n ))
  while [ "$(date +%s)" -lt "$t" ]; do sleep 0.1; done
  reg=$(( 6 + n / 4 ))
  val=$(( 1 << (2 * (n % 4)) ))
  i2cset -y 0 0x64 $reg $val
  echo "$(date +%T) output $n on" >> "$log"
  sleep 4
  i2cset -y 0 0x64 $reg 0x00
done
off
echo "$(date +%T) done" >> "$log"
sync
