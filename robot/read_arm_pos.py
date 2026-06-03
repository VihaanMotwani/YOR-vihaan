"""Read current joint positions from left and right Piper arms.

Prereq: CAN interfaces up (run `./extra/setup.sh` once per boot).

Starts the C++ MIT control loop just long enough to read state.
The first command holds arms at their CURRENT pose (no reset_to_home),
so arms will not lurch. Calls piper.stop() at the end (damping mode).
"""
import time
from pathlib import Path

import numpy as np

from piperlib import ControllerConfig, PiperController

_HERE = Path(__file__).parent
URDF_LEFT = (_HERE / "../piperlib/urdf/piper_cone-e_left.urdf").resolve().as_posix()
URDF_RIGHT = (_HERE / "../piperlib/urdf/piper_cone-e_right.urdf").resolve().as_posix()


def _make_controller(can_port: str, urdf_path: str) -> PiperController:
    cfg = ControllerConfig()
    cfg.interface_name = can_port
    cfg.urdf_path = urdf_path
    cfg.gravity_compensation = False
    cfg.default_kp = np.array([15.0, 15.0, 15.0, 15.0, 15.0, 15.0])
    cfg.controller_freq_hz = 200
    cfg.gripper_on = False
    return PiperController(cfg)


def _read(can_port: str, urdf_path: str, label: str):
    piper = _make_controller(can_port, urdf_path)
    if not piper.start():
        print(f"[{label}] FAILED to start on {can_port}")
        return
    # Let the control loop settle and publish a fresh state.
    time.sleep(0.3)
    state = piper.get_current_state()
    q = np.asarray(state.pos)
    gripper = getattr(state, "gripper_pos", None)
    print(f"[{label}] joint pos (rad): {np.round(q, 4).tolist()}")
    print(f"[{label}] joint pos (deg): {np.round(np.degrees(q), 2).tolist()}")
    if gripper is not None:
        print(f"[{label}] gripper_pos:    {gripper}")
    piper.stop()


if __name__ == "__main__":
    _read("can_left", URDF_LEFT, "LEFT")
    _read("can_right", URDF_RIGHT, "RIGHT")
