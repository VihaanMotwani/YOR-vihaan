#!/bin/bash
# One-file startup for YOR physical robot + oculus whole-body teleop.
# Launches three tmux panes: CAN setup, robot driver, teleop client.

set -e

cd "$(dirname "$0")"

if ! command -v tmux &> /dev/null; then
    echo "ERROR: tmux is not installed. Install with: sudo apt install tmux"
    exit 1
fi

SESSION=robot

# If a previous session is still around, kill it so we start clean
tmux kill-session -t "$SESSION" 2>/dev/null || true

tmux new-session -d -s "$SESSION" -n window1
tmux set -g mouse on

# Split into three equal vertical panes: 0.0 (left), 0.2 (middle), 0.1 (right)
tmux split-window -h -t "$SESSION":0
tmux split-window -h -t "$SESSION":0.0
tmux select-layout -t "$SESSION":0 even-horizontal

# Pane 0.2 (rightmost): CAN setup — runs first
tmux send-keys -t "$SESSION":0.2 'conda activate yor' C-m
tmux send-keys -t "$SESSION":0.2 './extra/setup.sh' C-m

# Pane 0.1 (middle): robot driver — wait for CAN interfaces, then launch
tmux send-keys -t "$SESSION":0.1 'conda activate yor' C-m
tmux send-keys -t "$SESSION":0.1 'until ip link show can_left up &>/dev/null && ip link show can_right up &>/dev/null && ip link show can0 up &>/dev/null; do sleep 0.5; done; sleep 2; python robot/yor.py' C-m

# Pane 0.0 (left): teleop — wait for robot driver RPC port (5557), then launch
tmux send-keys -t "$SESSION":0.0 'conda activate yor' C-m
tmux send-keys -t "$SESSION":0.0 'until (echo > /dev/tcp/127.0.0.1/5557) &>/dev/null; do sleep 0.5; done; python robot/teleop/oculus_bimanual_wholebody_teleop.py' C-m

tmux attach-session -t "$SESSION"
