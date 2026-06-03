#!/bin/bash
# YOR CAN setup — serial-based identification (sid edit 2026-05-13)
# Replaces upstream extra/setup.sh blind enumeration-order rename with stable
# serial-based naming. Idempotent: safe to re-run from any state.
set -e

# Serial-number prefixes (from /sys/class/net/canX/device/.../serial)
BASE_SERIAL=005000544C45
LEFT_SERIAL=0038003E
RIGHT_SERIAL=003A0048

find_can_by_serial() {
    local prefix=$1
    for c in /sys/class/net/can* ; do
        [ -d "$c" ] || continue
        name=$(basename "$c")
        parent=$(readlink -f "$c/device") 2>/dev/null
        [ -n "$parent" ] || continue
        serial=$(cat "$(dirname "$parent")/serial" 2>/dev/null)
        if [[ "$serial" == "$prefix"* ]]; then
            echo "$name"
            return 0
        fi
    done
    return 1
}

BASE=$(find_can_by_serial $BASE_SERIAL)  || { echo "ERROR: no CAN device with serial prefix $BASE_SERIAL"; exit 1; }
LEFT=$(find_can_by_serial $LEFT_SERIAL)  || { echo "ERROR: no CAN device with serial prefix $LEFT_SERIAL"; exit 1; }
RIGHT=$(find_can_by_serial $RIGHT_SERIAL) || { echo "ERROR: no CAN device with serial prefix $RIGHT_SERIAL"; exit 1; }

echo "Identified: BASE=$BASE  LEFT=$LEFT  RIGHT=$RIGHT"

# Bring down all three before renaming
sudo ip link set "$BASE"  down 2>/dev/null || true
sudo ip link set "$LEFT"  down 2>/dev/null || true
sudo ip link set "$RIGHT" down 2>/dev/null || true

# Two-step rename (via tmp) to avoid name collisions with current state
sudo ip link set "$BASE"  name __canbase_tmp
sudo ip link set "$LEFT"  name __canleft_tmp
sudo ip link set "$RIGHT" name __canright_tmp

sudo ip link set __canbase_tmp  name can0
sudo ip link set __canleft_tmp  name can_left
sudo ip link set __canright_tmp name can_right

# Configure each at 1 Mbps
for c in can0 can_left can_right ; do
    sudo ip link set "$c" type can bitrate 1000000
    sudo ip link set "$c" up
    sudo ip link set "$c" txqueuelen 1000
    echo "$c -> 1Mbps UP txqueuelen=1000"
done

echo ""
echo "Final state:"
ip -br link show type can
