#!/usr/bin/env python3
"""Position-mode test for SparkFlex steer motors.

Commands SetPosition(0.0), holds, then SetPosition(0.25), holds, then back to 0.
Used to determine whether the absolute encoder is configured for the
controller's internal closed-loop (even if readback to Python is disabled).

Observed behavior tells us:
  * Wheel rotates ~90 deg between the two commanded positions and HOLDS there
      -> encoder works internally; no reflash needed.
  * Wheel spins continuously / drifts / doesn't hold
      -> encoder not connected to controller; reflash required.

Usage:
    python motor_pos_test.py <can_id> [hold_seconds]
Example:
    python motor_pos_test.py 5 1.5
"""
import sys
import time

from sparkcan_py import SparkFlex

CAN_IF = "can0"
HB_PERIOD = 0.005  # 200 Hz heartbeat


def hold_position(m: SparkFlex, frac: float, hold_s: float, label: str) -> None:
    print(f"[{label}] SetPosition({frac:.3f}); holding {hold_s:.1f} s")
    m.SetPosition(float(frac))
    t_end = time.monotonic() + hold_s
    last_print = 0.0
    while time.monotonic() < t_end:
        m.Heartbeat()
        m.SetPosition(float(frac))
        now = time.monotonic()
        if now - last_print > 0.25:
            try:
                p = float(m.GetAbsoluteEncoderPosition())
                print(f"  abs_pos = {p:+.4f}")
            except Exception as e:
                print(f"  (read failed: {e})")
            last_print = now
        time.sleep(HB_PERIOD)


def main(can_id: int, hold_s: float) -> None:
    m = SparkFlex(CAN_IF, can_id)

    # Warm-up heartbeats
    print(f"[ID {can_id}] warming up heartbeats")
    for _ in range(60):
        m.Heartbeat()
        time.sleep(HB_PERIOD)

    hold_position(m, 0.0, hold_s, f"ID {can_id} pos=0.00")
    hold_position(m, 0.25, hold_s, f"ID {can_id} pos=0.25 (+90 deg)")
    hold_position(m, 0.0, hold_s, f"ID {can_id} pos=0.00 (return)")

    print(f"[ID {can_id}] done.\n")
    print("Observation key:")
    print("  - Wheel snapped ~90 deg and HELD at each step -> encoder OK, no reflash")
    print("  - Wheel spun continuously / drifted -> encoder missing, reflash required")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: motor_pos_test.py <can_id> [hold_seconds]")
        sys.exit(1)
    cid = int(sys.argv[1])
    hs = float(sys.argv[2]) if len(sys.argv) > 2 else 1.5
    main(cid, hs)
