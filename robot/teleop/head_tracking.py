"""Head-tracking helpers for Meta Quest VR teleop.

The Quest/Unity client publishes the headset's local pose alongside the
controllers. We use the yaw of the headset (rotation around Unity's up axis)
to drive the base angular velocity so the robot's base yaw follows the
operator's head turn while wearing the HMD.

Position-tracking control: when the operator turns their head N degrees,
the base rotates N degrees and stops, with the top speed capped by
``max_omega`` purely as a safety. Internally the controller integrates its
own commanded yaw and runs a proportional loop against the head target.
"""

from __future__ import annotations

import math
import time
from typing import Optional, Sequence

import numpy as np


DEFAULT_DEADBAND_DEG = 8.0
DEFAULT_CLAMP_DEG = 45.0
DEFAULT_KP_POS = 2.0           # 1/s; W ≈ kp_pos × position_error
DEFAULT_MAX_OMEGA = 0.4        # rad/s safety cap
DEFAULT_STALE_TIMEOUT = 0.25   # seconds
DEFAULT_MANUAL_YAW_DEADBAND = 0.05
DEFAULT_SIGN = -1              # Quest head_yaw is negative on left turn; base CCW is +.
_DT_MAX = 0.1                  # cap integration step to avoid wind-up jumps


def wrap_pi(angle: float) -> float:
    """Wrap an angle in radians to (-pi, pi]."""
    return (float(angle) + math.pi) % (2.0 * math.pi) - math.pi


def yaw_from_unity_quaternion_xyzw(q: Sequence[float]) -> float:
    """Extract yaw (rotation around Unity's up / +Y axis) from a quaternion.

    Unity is left-handed Y-up; we return yaw directly in Unity's frame.
    Sign convention may need to be flipped via the controller's ``sign`` if
    the base ends up turning opposite to the operator's head.
    """
    x, y, z, w = float(q[0]), float(q[1]), float(q[2]), float(q[3])
    siny_cosp = 2.0 * (w * y + x * z)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    return math.atan2(siny_cosp, cosy_cosp)


class HeadYawController:
    """Position-tracking controller: base yaw follows head yaw 1:1, top speed capped.

    Usage:
        capture_neutral(head_yaw)  # at toggle-on; defines the zero
        ... each tick:
        w = compute(head_yaw, head_timestamp, manual_yaw_axis)

    Internal model:
        target          = sign × clamp(head_yaw − neutral)   in base frame
        commanded_delta = integral of w·dt                   in base frame
        w               = kp_pos × (target − commanded_delta), saturated to ±max_omega

    When target stops moving, commanded_delta converges to target and ``w`` → 0.
    """

    def __init__(
        self,
        deadband_deg: float = DEFAULT_DEADBAND_DEG,
        clamp_deg: float = DEFAULT_CLAMP_DEG,
        kp_pos: float = DEFAULT_KP_POS,
        max_omega: float = DEFAULT_MAX_OMEGA,
        stale_timeout: float = DEFAULT_STALE_TIMEOUT,
        manual_yaw_deadband: float = DEFAULT_MANUAL_YAW_DEADBAND,
        sign: int = DEFAULT_SIGN,
    ):
        self.deadband_rad = math.radians(deadband_deg)
        self.clamp_rad = math.radians(clamp_deg)
        self.kp_pos = kp_pos
        self.max_omega = max_omega
        self.stale_timeout = stale_timeout
        self.manual_yaw_deadband = manual_yaw_deadband
        self.sign = 1 if sign >= 0 else -1
        self.neutral_yaw: Optional[float] = None
        self.commanded_delta: float = 0.0
        self.last_compute_time: Optional[float] = None

    def capture_neutral(self, head_yaw: Optional[float]) -> None:
        self.commanded_delta = 0.0
        self.last_compute_time = None
        if head_yaw is None:
            self.neutral_yaw = None
            return
        self.neutral_yaw = float(head_yaw)

    def reset(self) -> None:
        self.neutral_yaw = None
        self.commanded_delta = 0.0
        self.last_compute_time = None

    def compute(
        self,
        head_yaw: Optional[float],
        head_timestamp: Optional[float],
        manual_yaw_axis: float,
        now: Optional[float] = None,
    ) -> Optional[float]:
        """Return the angular velocity command, or ``None`` for manual override."""
        if abs(float(manual_yaw_axis)) > self.manual_yaw_deadband:
            # Manual stick takes over — freeze integrator timing so we don't
            # blast a big dt on the next head-driven tick.
            self.last_compute_time = None
            return None

        if self.neutral_yaw is None:
            return 0.0
        if head_yaw is None or head_timestamp is None:
            return 0.0

        if now is None:
            now = time.time()
        if (now - float(head_timestamp)) > self.stale_timeout:
            self.last_compute_time = None
            return 0.0

        raw = wrap_pi(float(head_yaw) - self.neutral_yaw)
        if abs(raw) < self.deadband_rad:
            raw = 0.0
        raw = max(-self.clamp_rad, min(self.clamp_rad, raw))
        target = self.sign * raw

        error = target - self.commanded_delta
        w = self.kp_pos * error
        if w > self.max_omega:
            w = self.max_omega
        elif w < -self.max_omega:
            w = -self.max_omega

        if self.last_compute_time is not None:
            dt = max(0.0, min(_DT_MAX, now - self.last_compute_time))
            self.commanded_delta += w * dt
        self.last_compute_time = now

        return float(w)
