#!/usr/bin/env python3
"""Single-motor velocity smoke test (HANDOVER.md §7).

Pulses SetVelocity() on one SparkFlex motor for a short window, commands 0,
then heartbeats while reading back velocity so you can confirm the motor
spun and stopped. Continuous heartbeats keep the controller from timing out.

Usage:
    python motor_vel_test.py <can_id> [velocity] [duration_ms]

Defaults: velocity=0.3, duration_ms=100
Example:  python motor_vel_test.py 5 0.3 100
"""
import sys
import time

from sparkcan_py import SparkFlex

CAN_IF = "can0"
HB_PERIOD = 0.005  # 200 Hz heartbeat


def smoke_test(can_id: int, vel: float, duration_ms: int) -> None:
    m = SparkFlex(CAN_IF, can_id)

    # Warm-up: heartbeat ~200ms so the controller knows we're alive
    for _ in range(40):
        m.Heartbeat()
        time.sleep(HB_PERIOD)
    m.SetVelocity(0.0)

    def read_pos():
        try:
            return float(m.GetAbsoluteEncoderPosition())
        except Exception:
            return None

    pos_before = read_pos()
    print(f"[ID {can_id}] pulsing SetVelocity({vel:+.3f}) for {duration_ms} ms "
          f"(abs_pos before = {pos_before})")
    vel_samples: list[float] = []
    pos_samples: list[float] = []
    t_end = time.monotonic() + duration_ms / 1000.0
    m.SetVelocity(vel)
    while time.monotonic() < t_end:
        m.Heartbeat()
        try:
            vel_samples.append(float(m.GetVelocity()))
        except Exception:
            pass
        p = read_pos()
        if p is not None:
            pos_samples.append(p)
        time.sleep(HB_PERIOD)
    m.SetVelocity(0.0)
    pos_after = read_pos()

    if vel_samples:
        peak_v = max(vel_samples, key=abs)
        print(f"  vel: n={len(vel_samples)} peak={peak_v:+.3f} "
              f"first={vel_samples[0]:+.3f} last={vel_samples[-1]:+.3f}")
    if pos_samples and pos_before is not None and pos_after is not None:
        dpos = pos_after - pos_before
        pmin, pmax = min(pos_samples), max(pos_samples)
        print(f"  pos: before={pos_before:.4f} after={pos_after:.4f} "
              f"delta={dpos:+.4f} range=[{pmin:.4f}, {pmax:.4f}]")
    print("  (encoder feedback not in flashed config; confirm movement visually)")

    # Settle window: confirm motor returns to zero
    print(f"[ID {can_id}] commanded 0; settling 500 ms")
    t_end = time.monotonic() + 0.5
    last_print = 0.0
    while time.monotonic() < t_end:
        m.Heartbeat()
        now = time.monotonic()
        if now - last_print > 0.1:
            try:
                v = m.GetVelocity()
                print(f"  settle vel = {v:+.3f}")
            except Exception as e:
                print(f"  (GetVelocity failed: {e})")
            last_print = now
        time.sleep(HB_PERIOD)
    m.SetVelocity(0.0)
    print(f"[ID {can_id}] done.\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: motor_vel_test.py <can_id> [velocity] [duration_ms]")
        sys.exit(1)
    cid = int(sys.argv[1])
    vel = float(sys.argv[2]) if len(sys.argv) > 2 else 0.3
    dms = int(sys.argv[3]) if len(sys.argv) > 3 else 100
    smoke_test(cid, vel, dms)
