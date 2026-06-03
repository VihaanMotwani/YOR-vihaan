"""Unit tests for head-tracking helpers and Quest packet parsing.

Run from the repo root:
    python -m unittest tests/test_oculus_head_tracking.py
"""

import math
import os
import sys
import time
import unittest

import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from robot.teleop.head_tracking import (  # noqa: E402
    HeadYawController,
    wrap_pi,
    yaw_from_unity_quaternion_xyzw,
)
from robot.teleop.oculus_msgs import parse_controller_state  # noqa: E402


def _section(prefix, *,
             x=False, y=False, menu=False, thumb=False,
             idx=0.0, hand=0.0,
             axes=(0.0, 0.0),
             pos=(0.0, 0.0, 0.0),
             rot=(0.0, 0.0, 0.0, 1.0),
             b0_name="X", b1_name="Y"):
    """Build one controller half of the Quest packet."""
    return (
        f"{prefix}:"
        f";{b0_name}:{'true' if x else 'false'}"
        f";{b1_name}:{'true' if y else 'false'}"
        f";Menu:{'true' if menu else 'false'}"
        f";Thumbstick:{'true' if thumb else 'false'}"
        f";IndexTrigger:{idx}"
        f";HandTrigger:{hand}"
        f";ThumbstickAxes:{axes[0]},{axes[1]}"
        f";LocalPosition:{pos[0]},{pos[1]},{pos[2]}"
        f";LocalRotation:{rot[0]},{rot[1]},{rot[2]},{rot[3]}"
        ";"
    )


def _two_section_packet():
    left = _section("Left Controller", b0_name="X", b1_name="Y")
    right = _section("Right Controller", b0_name="A", b1_name="B")
    return f"{left}|{right}"


def _three_section_packet(head_pos=(0.1, 1.5, 0.2),
                          head_rot=(0.0, math.sin(math.pi / 4), 0.0, math.cos(math.pi / 4))):
    left = _section("Left Controller", b0_name="X", b1_name="Y")
    right = _section("Right Controller", b0_name="A", b1_name="B")
    head = (
        "Head:"
        f";pos:{head_pos[0]},{head_pos[1]},{head_pos[2]}"
        f";rot:{head_rot[0]},{head_rot[1]},{head_rot[2]},{head_rot[3]}"
        ";"
    )
    return f"{left}|{right}|{head}"


class WrapPiTests(unittest.TestCase):
    def test_inside_range(self):
        self.assertAlmostEqual(wrap_pi(0.0), 0.0)
        self.assertAlmostEqual(wrap_pi(1.0), 1.0)
        self.assertAlmostEqual(wrap_pi(-1.0), -1.0)

    def test_wraps_across_pi(self):
        self.assertAlmostEqual(wrap_pi(math.pi + 0.1), -math.pi + 0.1, places=6)
        self.assertAlmostEqual(wrap_pi(-math.pi - 0.1), math.pi - 0.1, places=6)

    def test_wraps_multiple_revolutions(self):
        # 3*pi is co-terminal with pi (and -pi). Both representations are valid.
        wrapped = wrap_pi(3.0 * math.pi)
        self.assertAlmostEqual(abs(wrapped), math.pi, places=6)
        self.assertAlmostEqual(wrap_pi(2.0 * math.pi + 0.5), 0.5, places=6)


class YawFromQuaternionTests(unittest.TestCase):
    def test_identity_is_zero(self):
        self.assertAlmostEqual(yaw_from_unity_quaternion_xyzw([0, 0, 0, 1]), 0.0)

    def test_quarter_turn_around_y(self):
        q = [0.0, math.sin(math.pi / 4), 0.0, math.cos(math.pi / 4)]
        self.assertAlmostEqual(yaw_from_unity_quaternion_xyzw(q), math.pi / 2, places=6)


class OculusMsgsParsingTests(unittest.TestCase):
    def test_two_section_packet_has_no_head(self):
        state = parse_controller_state(_two_section_packet())
        self.assertIsNone(state.head_local_position)
        self.assertIsNone(state.head_local_rotation)
        self.assertIsNone(state.head_created_timestamp)
        self.assertIsNone(state.head_yaw)
        # Make sure the rest still parsed.
        np.testing.assert_array_equal(state.left_local_position, np.array([0.0, 0.0, 0.0]))
        self.assertFalse(state.left_x)
        self.assertFalse(state.right_a)

    def test_three_section_packet_parses_head_fields(self):
        head_pos = (0.1, 1.5, 0.2)
        head_rot = (0.0, math.sin(math.pi / 4), 0.0, math.cos(math.pi / 4))
        state = parse_controller_state(_three_section_packet(head_pos, head_rot))
        self.assertIsNotNone(state.head_local_position)
        np.testing.assert_allclose(state.head_local_position, head_pos)
        np.testing.assert_allclose(state.head_local_rotation, head_rot)
        self.assertIsNotNone(state.head_created_timestamp)
        self.assertAlmostEqual(state.head_yaw, math.pi / 2, places=6)

    def test_malformed_head_section_does_not_crash(self):
        left = _section("Left Controller", b0_name="X", b1_name="Y")
        right = _section("Right Controller", b0_name="A", b1_name="B")
        # rot has only 3 components, pos is missing
        bad_head = "Head:;rot:0.0,0.0,0.0;"
        state = parse_controller_state(f"{left}|{right}|{bad_head}")
        self.assertIsNone(state.head_local_position)
        self.assertIsNone(state.head_local_rotation)
        self.assertIsNone(state.head_yaw)


class HeadYawControllerTests(unittest.TestCase):
    def setUp(self):
        self.ctl = HeadYawController()
        self.ctl.capture_neutral(0.0)
        self.now = 1000.0

    def test_no_neutral_returns_zero(self):
        ctl = HeadYawController()
        # No neutral captured, no manual override: returns 0.
        self.assertEqual(
            ctl.compute(head_yaw=0.5, head_timestamp=self.now, manual_yaw_axis=0.0, now=self.now),
            0.0,
        )

    def test_inside_deadband_returns_zero(self):
        # 5 degrees < 8 degree deadband
        w = self.ctl.compute(
            head_yaw=math.radians(5.0),
            head_timestamp=self.now,
            manual_yaw_axis=0.0,
            now=self.now,
        )
        self.assertEqual(w, 0.0)

    def test_outside_deadband_produces_command(self):
        # 20 degrees, well outside the 8 degree deadband, inside the 45 degree clamp.
        head_yaw = math.radians(20.0)
        w = self.ctl.compute(
            head_yaw=head_yaw,
            head_timestamp=self.now,
            manual_yaw_axis=0.0,
            now=self.now,
        )
        self.assertAlmostEqual(w, 1.2 * head_yaw, places=6)

    def test_large_yaw_clamps(self):
        # 90 degree head turn -> clamped to 45 degrees * gain 1.2, then to max_omega 0.6.
        w = self.ctl.compute(
            head_yaw=math.radians(90.0),
            head_timestamp=self.now,
            manual_yaw_axis=0.0,
            now=self.now,
        )
        expected = min(0.6, 1.2 * math.radians(45.0))
        self.assertAlmostEqual(w, expected, places=6)
        self.assertLessEqual(abs(w), 0.6 + 1e-9)

    def test_yaw_wrap_across_pi(self):
        # Neutral close to +pi, current just past -pi: real error is small.
        ctl = HeadYawController()
        ctl.capture_neutral(math.pi - 0.05)
        w = ctl.compute(
            head_yaw=-math.pi + 0.05,
            head_timestamp=self.now,
            manual_yaw_axis=0.0,
            now=self.now,
        )
        # Wrapped error is +0.1 rad (~5.7 degrees), inside deadband, so command is 0.
        self.assertEqual(w, 0.0)
        # Push it outside the deadband and check the sign is right (no big wrap).
        ctl.capture_neutral(math.pi - 0.05)
        w = ctl.compute(
            head_yaw=-math.pi + 0.3,
            head_timestamp=self.now,
            manual_yaw_axis=0.0,
            now=self.now,
        )
        # Wrapped error = +0.35 rad (~20deg) — well below the clamp, so w = gain*error.
        self.assertGreater(w, 0.0)
        self.assertLess(w, 0.6 + 1e-9)
        self.assertAlmostEqual(w, 1.2 * 0.35, places=6)

    def test_stale_packet_returns_zero(self):
        old_ts = self.now - 1.0  # well beyond 0.25s timeout
        w = self.ctl.compute(
            head_yaw=math.radians(20.0),
            head_timestamp=old_ts,
            manual_yaw_axis=0.0,
            now=self.now,
        )
        self.assertEqual(w, 0.0)

    def test_missing_head_packet_returns_zero(self):
        w = self.ctl.compute(
            head_yaw=None,
            head_timestamp=None,
            manual_yaw_axis=0.0,
            now=self.now,
        )
        self.assertEqual(w, 0.0)

    def test_manual_yaw_overrides_head(self):
        # Large head yaw would normally produce a big command — manual stick wins.
        w = self.ctl.compute(
            head_yaw=math.radians(30.0),
            head_timestamp=self.now,
            manual_yaw_axis=0.8,
            now=self.now,
        )
        self.assertIsNone(w)


if __name__ == "__main__":
    unittest.main()
