#!/bin/bash
# Map IT8728 PWM outputs to fan tachometers. Starts and ends with every output at full speed.
H=$(dirname "$(grep -l it8728 /sys/class/hwmon/hwmon*/name)")
rpm() { echo "fan1=$(cat $H/fan1_input) fan3=$(cat $H/fan3_input)"; }
full() { for p in 1 2 3; do echo 1 > $H/pwm${p}_enable; echo 255 > $H/pwm$p; done; }

full
sleep 8
echo "all 255: $(rpm)"
for p in 1 2 3; do
  echo 110 > $H/pwm$p
  sleep 8
  echo "pwm$p=110: $(rpm)"
  echo 255 > $H/pwm$p
  sleep 6
done
full
sleep 5
echo "restored all 255: $(rpm)  temps: $(cat $H/temp1_input $H/temp2_input $H/temp3_input | tr '\n' ' ')"
