#!/bin/bash
# Systemd-friendly variant of start.sh with a VR safety gate.
#
# Layout (4 tmux panes, left -> right):
#   0.0 teleop    — waits for driver port (5557), then runs the teleop client
#   0.1 kill-gate — once driver is up, watches for VR kill gesture
#   0.2 driver    — waits for CAN, then waits for VR UNLOCK, then runs yor.py
#                   (yor.py is what homes the arms via ArmNode.init, so this
#                    is the pane that has to wait — gating teleop is too late)
#   0.3 CAN setup — passwordless sudo via /etc/sudoers.d/yor-can
#
# Unlock / kill gesture (same in both modes):
#   click and hold both thumbsticks (L3 + R3 — push the sticks straight
#   down so they click) for >= 3 seconds. Thumbstick clicks are unused by
#   the teleop client, so the gesture has no side effects on a running
#   robot (in particular, doesn't move the lift like the grip triggers do).
#
# Run directly (./auto_start.sh) for an interactive tmux session, or via
# systemd (yor.service) for headless boot. $INVOCATION_ID is set by systemd
# and absent in normal shells, so the same script handles both.

set -e

cd "$(dirname "$0")"

if ! command -v tmux &> /dev/null; then
    echo "ERROR: tmux is not installed. Install with: sudo apt install tmux"
    exit 1
fi

SESSION=robot

# Graceful shutdown: SIGINT teleop, lower lift to 0 (while driver is still
# alive), SIGINT driver, auto-feed Enter twice for piper.stop()'s "support
# the arms" prompts, kill tmux session. Used both by the kill-gate pane and
# by the SIGTERM handler below.
tear_down() {
    echo "[auto_start] shutdown initiated"
    tmux send-keys -t "$SESSION":0.0 C-c 2>/dev/null || true
    sleep 2
    # Lower the lift to 0 while the driver is still up. ss check skips the
    # python spawn if the driver is already gone. Subshell isolates conda.
    if ss -ltn 2>/dev/null | grep -q ':5557 '; then
        echo "[auto_start] lowering lift to 0..."
        (
            source /home/yor/miniforge3/etc/profile.d/conda.sh
            conda activate yor
            cd /home/yor/YOR
            python -c 'from commlink import RPCClient; c = RPCClient(host="localhost", port=5557); c.lift_to_height(0.0, timeout_s=20.0)'
        ) 2>&1 | sed 's/^/[lift] /' || true
    fi
    tmux send-keys -t "$SESSION":0.2 C-c 2>/dev/null || true
    sleep 6
    tmux send-keys -t "$SESSION":0.2 Enter 2>/dev/null || true
    sleep 3
    tmux send-keys -t "$SESSION":0.2 Enter 2>/dev/null || true
    sleep 3
    tmux kill-session -t "$SESSION" 2>/dev/null || true
}

# Systemd `stop` sends SIGTERM; we have to propagate that into the panes,
# otherwise the detached tmux server (and the running driver) survive.
trap 'tear_down; exit 0' TERM INT

# Kill any stale session so we start clean.
tmux kill-session -t "$SESSION" 2>/dev/null || true

tmux new-session -d -s "$SESSION" -n window1
tmux set -g mouse on

# Build the 4-pane layout by always splitting the rightmost pane, so the
# index order matches the visual order: 0.0 | 0.1 | 0.2 | 0.3
tmux split-window -h -t "$SESSION":0.0
tmux split-window -h -t "$SESSION":0.1
tmux split-window -h -t "$SESSION":0.2
tmux select-layout -t "$SESSION":0 even-horizontal

# Pane 0.3 — CAN setup. Passwordless sudo via /etc/sudoers.d/yor-can.
tmux send-keys -t "$SESSION":0.3 'sudo /home/yor/YOR/extra/setup.sh' C-m

# Pane 0.2 — driver. Waits for CAN, THEN for the VR unlock gesture, THEN
# launches yor.py. ArmNode.init() inside yor.py is what homes the arms, so
# the gate has to be in front of yor.py itself.
tmux send-keys -t "$SESSION":0.2 'conda activate yor' C-m
tmux send-keys -t "$SESSION":0.2 'until ip link show can_left up &>/dev/null && ip link show can_right up &>/dev/null && ip link show can0 up &>/dev/null; do sleep 0.5; done; sleep 2; python vr_gate.py wait-unlock && python robot/yor.py' C-m

# Pane 0.0 — teleop. Waits for driver RPC port (which only opens after
# unlock + yor.py init), then launches the teleop client. No gate needed
# here — the driver is already unlocked by the time this fires.
tmux send-keys -t "$SESSION":0.0 'conda activate yor' C-m
tmux send-keys -t "$SESSION":0.0 'until (echo > /dev/tcp/127.0.0.1/5557) &>/dev/null; do sleep 0.5; done; python robot/teleop/oculus_bimanual_wholebody_teleop.py' C-m

# Pane 0.1 — kill gate. Waits for driver port (so we know there is
# something to tear down), then blocks on the kill gesture. On confirmation
# runs the same tear_down sequence the SIGTERM trap uses.
tmux send-keys -t "$SESSION":0.1 'conda activate yor' C-m
tmux send-keys -t "$SESSION":0.1 "until (echo > /dev/tcp/127.0.0.1/5557) &>/dev/null; do sleep 0.5; done; python vr_gate.py wait-kill && { echo '[auto_start] kill gesture confirmed'; tmux send-keys -t ${SESSION}:0.0 C-c; sleep 2; python -c 'from commlink import RPCClient; c = RPCClient(host=\"localhost\", port=5557); print(\"[lift] lowering to 0...\"); c.lift_to_height(0.0, timeout_s=20.0); print(\"[lift] done\")'; tmux send-keys -t ${SESSION}:0.2 C-c; sleep 6; tmux send-keys -t ${SESSION}:0.2 Enter; sleep 3; tmux send-keys -t ${SESSION}:0.2 Enter; sleep 3; tmux kill-session -t ${SESSION}; }" C-m

# Foreground behavior:
#   - Interactive (no $INVOCATION_ID): attach so the operator sees the panes.
#   - Systemd ($INVOCATION_ID set): poll until the tmux session is gone,
#     then exit. `sleep` is signal-interruptible, so SIGTERM unblocks us
#     and the trap above handles teardown.
if [ -z "$INVOCATION_ID" ]; then
    tmux attach-session -t "$SESSION"
else
    while tmux has-session -t "$SESSION" 2>/dev/null; do
        sleep 2
    done
fi
