import time
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Tuple

from mink.lie import SE3, SO3

def from_quat(q: np.ndarray) -> np.ndarray:
    """Convert quaternion to rotation matrix.

    Args:
        q: Quaternion in scalar-last (x,y,z,w) format

    Returns:
        3x3 rotation matrix
    """
    x, y, z, w = q
    x2, y2, z2 = x*x, y*y, z*z

    R = np.array([
        [1 - 2*y2 - 2*z2,     2*x*y - 2*w*z,     2*x*z + 2*w*y],
        [    2*x*y + 2*w*z, 1 - 2*x2 - 2*z2,     2*y*z - 2*w*x],
        [    2*x*z - 2*w*y,     2*y*z + 2*w*x, 1 - 2*x2 - 2*y2]
    ])

    return R


@dataclass
class ControllerState:
    created_timestamp: float
    left_x: bool
    left_y: bool
    left_menu: bool
    left_thumbstick: bool
    left_index_trigger: float
    left_hand_trigger: float
    left_thumbstick_axes: np.ndarray
    left_local_position: np.ndarray
    left_local_rotation: np.ndarray

    right_a: bool
    right_b: bool
    right_menu: bool
    right_thumbstick: bool
    right_index_trigger: float
    right_hand_trigger: float
    right_thumbstick_axes: np.ndarray
    right_local_position: np.ndarray
    right_local_rotation: np.ndarray

    head_local_position: Optional[np.ndarray] = None
    head_local_rotation: Optional[np.ndarray] = None
    head_created_timestamp: Optional[float] = None
    head_yaw: Optional[float] = None

    @property
    def left_SE3(self) -> SE3:
        # convert left-handed to right-handed
        M = np.array([[1, 0, 0], [0, 1, 0], [0, 0, -1]])
        rotation_mat = M @ from_quat(self.left_local_rotation) @ M.T
        translation = self.left_local_position * np.array([1, 1, -1])
        return SE3.from_rotation_and_translation(rotation=SO3.from_matrix(rotation_mat), translation=translation)

    @property
    def right_SE3(self) -> SE3:
        # convert left-handed to right-handed
        M = np.array([[1, 0, 0], [0, 1, 0], [0, 0, -1]])
        rotation_mat = M @ from_quat(self.right_local_rotation) @ M.T
        translation = self.right_local_position * np.array([1, 1, -1])
        return SE3.from_rotation_and_translation(rotation=SO3.from_matrix(rotation_mat), translation=translation)


def parse_controller_state(controller_state_string: str) -> ControllerState:
    sections = controller_state_string.split("|")
    left_data = sections[0]
    right_data = sections[1]

    left_data_list = left_data.split(";")[1:-1]
    right_data_list = right_data.split(";")[1:-1]

    def parse_bool(val: str) -> bool:
        return val.split(":")[1].lower().strip() == "true"

    def parse_float(val: str) -> float:
        return float(val.split(":")[1])

    def parse_list_float(val: str) -> np.ndarray:
        return np.array(list(map(float, val.split(":")[1].split(","))))

    def parse_section(data: list[str]) -> Tuple:
        return (
            # Buttons
            parse_bool(data[0]),
            parse_bool(data[1]),
            parse_bool(data[2]),
            parse_bool(data[3]),
            # Triggers
            parse_float(data[4]),
            parse_float(data[5]),
            # Thumbstick
            parse_list_float(data[6]),
            # Pose
            parse_list_float(data[7]),
            parse_list_float(data[8]),
        )

    left_parsed = parse_section(left_data_list)
    right_parsed = parse_section(right_data_list)

    now = time.time()
    state = ControllerState(now, *left_parsed, *right_parsed)

    if len(sections) >= 3:
        head_section = sections[2]
        try:
            head_tokens = head_section.split(";")
            # Header at index 0 ("Head:"); we look for pos: / rot: anywhere after.
            head_fields = {}
            for tok in head_tokens[1:]:
                tok = tok.strip()
                if not tok or ":" not in tok:
                    continue
                key, _, val = tok.partition(":")
                head_fields[key.strip().lower()] = val
            pos = np.array(list(map(float, head_fields["pos"].split(","))))
            rot = np.array(list(map(float, head_fields["rot"].split(","))))
            if pos.shape != (3,) or rot.shape != (4,):
                raise ValueError("head pos/rot wrong shape")
            from robot.teleop.head_tracking import yaw_from_unity_quaternion_xyzw
            state.head_local_position = pos
            state.head_local_rotation = rot
            state.head_created_timestamp = now
            state.head_yaw = yaw_from_unity_quaternion_xyzw(rot)
        except (KeyError, ValueError, IndexError, TypeError):
            # Malformed head section — leave head fields as None.
            pass

    return state
