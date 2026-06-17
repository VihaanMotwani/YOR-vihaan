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


def test_unity_head_pose_uses_xr_head_device():
    controller_state = (ROOT / "embodied_unity/Assets/Scripts/ControllerState.cs").read_text()

    assert "XRNode.Head" in controller_state
    assert "CommonUsages.centerEyePosition" in controller_state
    assert "CommonUsages.centerEyeRotation" in controller_state


def test_unity_controller_state_uses_xr_controller_fallback():
    controller_state = (ROOT / "embodied_unity/Assets/Scripts/ControllerState.cs").read_text()

    assert "XRNode.LeftHand" in controller_state
    assert "XRNode.RightHand" in controller_state
    assert "CommonUsages.trigger" in controller_state
    assert "CommonUsages.grip" in controller_state
    assert "CommonUsages.primary2DAxis" in controller_state


def test_oculus_head_yaw_maps_to_base_omega():
    _install_mink_stub()
    oculus_msgs = _load_module(
        "oculus_msgs_head_yaw_test",
        "robot/teleop/oculus_msgs.py",
    )

    theta = np.deg2rad(30.0)
    reference = np.array([0.0, 0.0, 0.0, 1.0])
    turned = np.array([0.0, np.sin(theta / 2.0), 0.0, np.cos(theta / 2.0)])

    yaw = oculus_msgs.relative_head_yaw_rad(reference, turned)
    omega = oculus_msgs.yaw_to_angular_velocity(
        yaw,
        deadband_rad=np.deg2rad(5.0),
        max_yaw_rad=np.deg2rad(45.0),
        max_angular_vel=0.35,
        gain=1.0,
        sign=1.0,
    )

    assert np.isclose(yaw, theta)
    assert omega > 0.0
    assert omega <= 0.35


def test_oculus_head_yaw_ignores_neutral_pitch():
    _install_mink_stub()
    oculus_msgs = _load_module(
        "oculus_msgs_pitched_neutral_test",
        "robot/teleop/oculus_msgs.py",
    )

    pitch = np.deg2rad(-30.0)
    yaw = np.deg2rad(25.0)
    reference = np.array([np.sin(pitch / 2.0), 0.0, 0.0, np.cos(pitch / 2.0)])
    yaw_delta = np.array([0.0, np.sin(yaw / 2.0), 0.0, np.cos(yaw / 2.0)])
    current = oculus_msgs.quat_multiply_xyzw(yaw_delta, reference)

    measured_yaw = oculus_msgs.relative_head_yaw_rad(reference, current)

    assert np.isclose(measured_yaw, yaw)


def test_oculus_head_yaw_deadband_stops_small_yaw():
    _install_mink_stub()
    oculus_msgs = _load_module(
        "oculus_msgs_deadband_test",
        "robot/teleop/oculus_msgs.py",
    )

    omega = oculus_msgs.yaw_to_angular_velocity(
        np.deg2rad(3.0),
        deadband_rad=np.deg2rad(8.0),
        max_yaw_rad=np.deg2rad(45.0),
        max_angular_vel=0.35,
        gain=1.0,
        sign=1.0,
    )

    assert omega == 0.0


def test_wholebody_teleop_exposes_optional_head_base_control():
    teleop = (ROOT / "robot/teleop/oculus_bimanual_wholebody_teleop.py").read_text()

    assert "--head_base_control" in teleop
    assert "--head_base_start_enabled" in teleop
    assert "--quest_host" in teleop
    assert "head_base_omega" in teleop
    assert "relative_head_yaw_rad" in teleop
    assert "last_sent_base_motion" in teleop


def test_yor_server_supports_base_only_startup():
    yor_py = (ROOT / "robot/yor.py").read_text()

    assert "--no-arms" in yor_py
    assert "YOR(no_arms=args.no_arms)" in yor_py


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


def test_zed_image_publisher_cli_defaults_to_hd720_60():
    zed_image_publisher = _load_module(
        "zed_image_publisher_test",
        "robot/zed_image_publisher.py",
    )

    args = zed_image_publisher.parse_args([])

    assert args.topic == "zed/image"
    assert args.port == 6000
    assert args.resolution == "HD720"
    assert args.fps == 60


def test_zed_image_publisher_cli_accepts_vga_fallback():
    zed_image_publisher = _load_module(
        "zed_image_publisher_fallback_test",
        "robot/zed_image_publisher.py",
    )

    args = zed_image_publisher.parse_args(["--resolution", "VGA", "--fps", "60"])

    assert args.resolution == "VGA"
    assert args.fps == 60
