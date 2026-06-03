#!/usr/bin/env python3
"""Command SetPosition(0.0) to a list of SparkFlex motors.

Used to neutralize / quick-test rotation motors. Note: if a motor's absolute
encoder isn't configured (case a), SetPosition(0) won't snap to a defined
physical position -- the wheel may rotate uncontrollably.
"""
import sys
import time

from sparkcan_py import SparkFlex

CAN_IF = "can0"
HB_PERIOD = 0.005
DEFAULT_HOLD_S = 2.0


def main(ids: list[int], hold_s: float) -> None:
    motors = []
    for cid in ids:
        m = SparkFlex(CAN_IF, cid)
        motors.append((cid, m))

    # Warm-up heartbeats so all controllers see us alive
    print("warming up heartbeats")
    for _ in range(60):
        for _, m in motors:
            m.Heartbeat()
        time.sleep(HB_PERIOD)

    print(f"commanding SetPosition(0.0) on IDs {ids}, holding {hold_s:.1f} s")
    t_end = time.monotonic() + hold_s
    last_print = 0.0
    while time.monotonic() < t_end:
        for _, m in motors:
            m.Heartbeat()
            m.SetPosition(0.0)
        now = time.monotonic()
        if now - last_print > 0.5:
            for cid, m in motors:
                try:
                    p = float(m.GetAbsoluteEncoderPosition())
                except Exception:
                    p = float("nan")
                print(f"  ID {cid}  abs_pos = {p:+.4f}")
            print("---")
            last_print = now
        time.sleep(HB_PERIOD)
    print("done.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("usage: motor_pos_zero.py [id1 id2 ...] [--hold SECONDS]")
        print("default: IDs 5 6 7, hold 2.0 s")
        sys.exit(0)

    args = sys.argv[1:]
    hold = DEFAULT_HOLD_S
    if "--hold" in args:
        i = args.index("--hold")
        hold = float(args[i + 1])
        del args[i:i + 2]
    ids = [int(x) for x in args] if args else [5, 6, 7]
    main(ids, hold)
