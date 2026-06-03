"""VR safety gate for the YOR auto-start flow.

Modes:
    wait-unlock — block before the driver launches, so the arms don't get
                  the home-pose command at boot.
    wait-kill   — block during teleop; on the same gesture, signal shutdown.

Gesture: click and hold both thumbsticks (left_thumbstick + right_thumbstick
both True) for >= 3s continuously. Thumbstick clicks are unused by the
teleop client, so this gesture has no side effects on the running robot.

State machine requires a clean release-then-press transition. This avoids
the kill gate firing immediately if the operator is still pressing the
sticks when wait-kill starts.

Run from /home/yor/YOR. Imports the existing oculus message parser used by
the teleop client; no other dependency on YOR internals.
"""
import json
import subprocess
import sys
import time
import zmq

from robot.teleop.oculus_msgs import parse_controller_state


def tailscale_ready() -> bool:
    try:
        out = subprocess.run(
            ["tailscale", "status", "--json"],
            capture_output=True, text=True, timeout=2,
        )
        return json.loads(out.stdout).get("BackendState") == "Running"
    except Exception:
        return False


VR_TCP_HOST = "100.122.50.128"   # tailscale; matches oculus_bimanual_wholebody_teleop.py
VR_TCP_PORT = 5555
VR_CONTROLLER_TOPIC = b"oculus_controller"

HOLD_SECONDS = 3.0
RCVTIMEO_MS = 1000


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ("wait-unlock", "wait-kill"):
        print("usage: vr_gate.py {wait-unlock|wait-kill}", file=sys.stderr)
        return 2

    label = "UNLOCK" if sys.argv[1] == "wait-unlock" else "KILL"

    ctx = zmq.Context()
    sock = ctx.socket(zmq.SUB)
    sock.setsockopt(zmq.RCVTIMEO, RCVTIMEO_MS)
    sock.setsockopt(zmq.LINGER, 0)
    sock.connect(f"tcp://{VR_TCP_HOST}:{VR_TCP_PORT}")
    sock.subscribe(VR_CONTROLLER_TOPIC)

    print(
        f"[vr_gate:{label}] release both thumbsticks, then click and hold "
        f"both (L3 + R3) for {HOLD_SECONDS:.1f}s...",
        flush=True,
    )

    # State: WAIT_RELEASE -> WAIT_PRESS -> HOLDING -> (confirmed) -> return
    state = "WAIT_RELEASE"
    hold_start = None
    last_silence_warn = 0.0
    announced_ready = False

    try:
        while True:
            try:
                _, msg = sock.recv_multipart()
            except zmq.Again:
                # Reset on VR silence so the gesture has to start fresh once
                # messages resume.
                state = "WAIT_RELEASE"
                hold_start = None
                announced_ready = False
                now = time.time()
                if now - last_silence_warn > 5.0:
                    if not tailscale_ready():
                        print(
                            f"[vr_gate:{label}] waiting for Tailscale to "
                            f"come up (BackendState != Running)...",
                            flush=True,
                        )
                    else:
                        print(
                            f"[vr_gate:{label}] no VR messages on "
                            f"{VR_TCP_HOST}:{VR_TCP_PORT} — is the headset on?",
                            flush=True,
                        )
                    last_silence_warn = now
                continue

            try:
                cs = parse_controller_state(msg.decode())
            except Exception as e:
                print(f"[vr_gate:{label}] parse error: {e}", flush=True)
                continue

            pressed = bool(cs.left_thumbstick) and bool(cs.right_thumbstick)

            if state == "WAIT_RELEASE":
                if not pressed:
                    state = "WAIT_PRESS"
                    if not announced_ready:
                        print(
                            f"[vr_gate:{label}] ready — click both "
                            f"thumbsticks (L3 + R3) now.",
                            flush=True,
                        )
                        announced_ready = True
            elif state == "WAIT_PRESS":
                if pressed:
                    state = "HOLDING"
                    hold_start = time.time()
                    print(
                        f"[vr_gate:{label}] gesture detected — keep holding "
                        f"for {HOLD_SECONDS:.1f}s...",
                        flush=True,
                    )
            elif state == "HOLDING":
                if pressed:
                    if time.time() - hold_start >= HOLD_SECONDS:
                        print(f"[vr_gate:{label}] confirmed.", flush=True)
                        return 0
                else:
                    print(
                        f"[vr_gate:{label}] released too early — restart "
                        f"the hold.",
                        flush=True,
                    )
                    state = "WAIT_PRESS"
                    hold_start = None
    finally:
        sock.close()
        ctx.destroy(linger=0)


if __name__ == "__main__":
    sys.exit(main())
