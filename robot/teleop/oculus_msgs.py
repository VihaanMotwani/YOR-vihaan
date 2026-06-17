import time
import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple

from mink.lie import SE3, SO3
from robot.teleop.head_tracking import yaw_from_unity_quaternion_xyzw

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
    head_world_position: Optional[np.ndarray] = None
    head_world_rotation: Optional[np.ndarray] = None
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

    @property
    def head_SE3(self) -> SE3:
        # convert left-handed to right-handed
        if self.head_local_position is None or self.head_local_rotation is None:
            return SE3.from_rotation_and_translation(
                rotation=SO3.from_matrix(np.eye(3)),
                translation=np.zeros(3),
            )
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
            fields[key.strip().lower().replace(" ", "")] = value.strip()

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

    def field_value(fields: dict[str, str], *keys: str) -> str:
        for key in keys:
            normalized = key.lower().replace(" ", "")
            if normalized in fields:
                return fields[normalized]
        raise KeyError(keys[0])

    def require_fields(section_name: str, keys: list[tuple[str, ...]]) -> list[str]:
        data = section_data.get(section_name)
        if data is None:
            raise ValueError(f"Missing '{section_name}' section in controller state")

        try:
            return [field_value(data, *key_options) for key_options in keys]
        except KeyError as exc:
            raise ValueError(f"Missing fields in '{section_name}' section: {exc.args[0]}") from exc

    def parse_section(section_name: str, prefix: str) -> Tuple:
        button0 = "x" if prefix == "left" else "a"
        button1 = "y" if prefix == "left" else "b"
        data = require_fields(section_name, [
            (f"{prefix} {button0}", button0),
            (f"{prefix} {button1}", button1),
            (f"{prefix} menu", "menu"),
            (f"{prefix} thumbstick", "thumbstick"),
            (f"{prefix} index trigger", "index trigger", "indextrigger"),
            (f"{prefix} hand trigger", "hand trigger", "handtrigger"),
            (f"{prefix} thumbstick axes", "thumbstick axes", "thumbstickaxes"),
            (f"{prefix} local position", "local position", "localposition"),
            (f"{prefix} local rotation", "local rotation", "localrotation"),
        ])
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

    def parse_head() -> Tuple[
        Optional[np.ndarray],
        Optional[np.ndarray],
        Optional[np.ndarray],
        Optional[np.ndarray],
        Optional[float],
        Optional[float],
    ]:
        data = section_data.get("head")
        if data is None:
            return (None, None, None, None, None, None)

        try:
            local_position = parse_list_float(field_value(data, "head local position", "pos"))
            local_rotation = parse_list_float(field_value(data, "head local rotation", "rot"))
            if local_position.shape != (3,) or local_rotation.shape != (4,):
                raise ValueError("head local pose has the wrong shape")

            world_position = None
            world_rotation = None
            if "headworldposition" in data:
                world_position = parse_list_float(data["headworldposition"])
            if "headworldrotation" in data:
                world_rotation = parse_list_float(data["headworldrotation"])

            return (
                local_position,
                local_rotation,
                world_position,
                world_rotation,
                time.time(),
                yaw_from_unity_quaternion_xyzw(local_rotation),
            )
        except (KeyError, ValueError, TypeError):
            return (None, None, None, None, None, None)

    left_parsed = parse_section("left", "left")
    right_parsed = parse_section("right", "right")
    head_parsed = parse_head()

    return ControllerState(time.time(), *left_parsed, *right_parsed, *head_parsed)
