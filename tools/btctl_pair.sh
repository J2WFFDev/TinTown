#!/bin/bash
# Non-interactive bluetoothctl helper to pair/trust/connect a device
BTADDR="F8:FE:92:31:12:E3"
set -x
bluetoothctl <<EOF
power on
agent on
default-agent
scan on
# wait a bit for device to be seen
sleep 5
pair $BTADDR
trust $BTADDR
connect $BTADDR
scan off
quit
EOF
