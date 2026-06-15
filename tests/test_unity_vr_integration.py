from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]


class _SO3:
    @classmethod
    def from_matrix(cls, matrix):
        return cls()


class _SE3:
    @classmethod
    def from_rotation_and_translation(cls, rotation, translation):
        return cls()


def _install_mink_stub() -> None:
    mink = types.ModuleType("mink")
    lie = types.ModuleType("mink.lie")
    lie.SE3 = _SE3
    lie.SO3 = _SO3
    mink.lie = lie
    sys.modules["mink"] = mink
    sys.modules["mink.lie"] = lie


def _load_module(name: str, relpath: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relpath)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _controller_section(name: str, *, left: bool) -> str:
    if left:
        return (
            f"{name}:;"
            " Left X: true;"
            " Left Y: false;"
            " Left Menu: false;"
            " Left Thumbstick: true;"
            " Left Index Trigger: 0.1;"
            " Left Hand Trigger: 0.2;"
            " Left Thumbstick Axes: 0.3,0.4;"
            " Left Local Position: 1,2,3;"
            " Left Local Rotation: 0,0,0,1;"
        )

    return (
        f"{name}:;"
        " Right A: false;"
        " Right B: true;"
        " Right Menu: false;"
        " Right Thumbstick: false;"
        " Right Index Trigger: 0.5;"
        " Right Hand Trigger: 0.6;"
        " Right Thumbstick Axes: 0.7,0.8;"
        " Right Local Position: 4,5,6;"
        " Right Local Rotation: 0,0,0,1;"
    )


def _left_right_message() -> str:
    return "|".join(
        [
            _controller_section("Left Controller", left=True),
            _controller_section("Right Controller", left=False),
        ]
    )


def _head_left_right_message() -> str:
    return (
        "Head:;"
        " Head Local Position: 0.1,0.2,0.3;"
        " Head Local Rotation: 0,0,0,1;"
        " Head World Position: 1.1,1.2,1.3;"
        " Head World Rotation: 0,0,0,1;"
        "|"
        + _left_right_message()
    )


def test_controller_parser_accepts_legacy_controller_only_packet():
    _install_mink_stub()
    oculus_msgs = _load_module("oculus_msgs_legacy_test", "robot/teleop/oculus_msgs.py")

    state = oculus_msgs.parse_controller_state(_left_right_message())

    assert state.left_x is True
    assert state.right_b is True
    np.testing.assert_allclose(state.left_local_position, np.array([1, 2, 3]))
    np.testing.assert_allclose(state.head_local_position, np.zeros(3))


def test_controller_parser_accepts_unity_head_pose_packet():
    _install_mink_stub()
    oculus_msgs = _load_module("oculus_msgs_head_test", "robot/teleop/oculus_msgs.py")

    state = oculus_msgs.parse_controller_state(_head_left_right_message())

    assert state.left_x is True
    assert state.right_b is True
    np.testing.assert_allclose(state.head_local_position, np.array([0.1, 0.2, 0.3]))
    np.testing.assert_allclose(state.head_world_position, np.array([1.1, 1.2, 1.3]))


def test_unity_stream_bridge_encodes_jpeg_frame():
    unity_stream_bridge = _load_module(
        "unity_stream_bridge_test",
        "robot/unity_stream_bridge.py",
    )
    img = np.zeros((8, 8, 3), dtype=np.uint8)
    img[:, :, 0] = 255

    data = unity_stream_bridge.encode_jpeg(img, quality=80)

    assert data.startswith(b"\xff\xd8")
    assert data.endswith(b"\xff\xd9")
