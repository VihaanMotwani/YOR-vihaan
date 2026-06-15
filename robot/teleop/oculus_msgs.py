import time
import numpy as np
from dataclasses import dataclass, field
from typing import Tuple

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

    head_local_position: np.ndarray = field(default_factory=lambda: np.zeros(3))
    head_local_rotation: np.ndarray = field(default_factory=lambda: np.array([0.0, 0.0, 0.0, 1.0]))
    head_world_position: np.ndarray = field(default_factory=lambda: np.zeros(3))
    head_world_rotation: np.ndarray = field(default_factory=lambda: np.array([0.0, 0.0, 0.0, 1.0]))

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

    @property
    def head_SE3(self) -> SE3:
        # convert left-handed to right-handed
        M = np.array([[1, 0, 0], [0, 1, 0], [0, 0, -1]])
        rotation_mat = M @ from_quat(self.head_local_rotation) @ M.T
        translation = self.head_local_position * np.array([1, 1, -1])
        return SE3.from_rotation_and_translation(rotation=SO3.from_matrix(rotation_mat), translation=translation)


def parse_controller_state(controller_state_string: str) -> ControllerState:
    section_data = {}
    for raw_section in controller_state_string.split("|"):
        parts = [part.strip() for part in raw_section.split(";") if part.strip()]
        if not parts:
            continue

        section_name = parts[0].rstrip(":").lower()
        fields = {}
        for item in parts[1:]:
            if ":" not in item:
                continue
            key, value = item.split(":", 1)
            fields[key.strip().lower()] = value.strip()

        if "left" in section_name:
            section_data["left"] = fields
        elif "right" in section_name:
            section_data["right"] = fields
        elif "head" in section_name:
            section_data["head"] = fields

    def parse_bool(val: str) -> bool:
        return val.lower().strip() == "true"

    def parse_float(val: str) -> float:
        return float(val)

    def parse_list_float(val: str) -> np.ndarray:
        return np.array(list(map(float, val.split(","))))

    def require_fields(section_name: str, keys: list[str]) -> list[str]:
        data = section_data.get(section_name)
        if data is None:
            raise ValueError(f"Missing '{section_name}' section in controller state")

        missing = [key for key in keys if key not in data]
        if missing:
            raise ValueError(f"Missing fields in '{section_name}' section: {missing}")

        return [data[key] for key in keys]

    def parse_section(section_name: str, prefix: str) -> Tuple:
        data = require_fields(
            section_name,
            [
                f"{prefix} x" if prefix == "left" else f"{prefix} a",
                f"{prefix} y" if prefix == "left" else f"{prefix} b",
                f"{prefix} menu",
                f"{prefix} thumbstick",
                f"{prefix} index trigger",
                f"{prefix} hand trigger",
                f"{prefix} thumbstick axes",
                f"{prefix} local position",
                f"{prefix} local rotation",
            ],
        )
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

    def parse_head() -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        data = section_data.get("head")
        if data is None:
            return (
                np.zeros(3),
                np.array([0.0, 0.0, 0.0, 1.0]),
                np.zeros(3),
                np.array([0.0, 0.0, 0.0, 1.0]),
            )

        return (
            parse_list_float(data.get("head local position", "0,0,0")),
            parse_list_float(data.get("head local rotation", "0,0,0,1")),
            parse_list_float(data.get("head world position", "0,0,0")),
            parse_list_float(data.get("head world rotation", "0,0,0,1")),
        )

    left_parsed = parse_section("left", "left")
    right_parsed = parse_section("right", "right")
    head_parsed = parse_head()

    return ControllerState(time.time(), *left_parsed, *right_parsed, *head_parsed)
