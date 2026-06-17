#!/usr/bin/env python3
"""Publish ZED camera frames on the YOR internal commlink image topic.

This publisher is intentionally small and does not depend on SciPy. It is useful
for VR/Unity camera streaming on Jetson/NUC machines where the navigation stack
dependencies are not installed or have incompatible binary wheels.
"""

from __future__ import annotations

import argparse
import time
from typing import Any


RESOLUTIONS = ("HD2K", "HD1080", "HD720", "VGA")
VIEWS = ("LEFT", "RIGHT")
COLOR_ORDERS = ("rgb", "bgr")


def _enum_value(namespace: Any, name: str) -> Any:
    try:
        return getattr(namespace, name)
    except AttributeError as exc:
        valid = [key for key in dir(namespace) if key.isupper()]
        raise ValueError(f"Unknown ZED enum value {name!r}. Valid values include: {valid}") from exc


def _frame_rgb(frame: Any, *, color_order: str) -> Any:
    arr = frame.get_data()
    if arr.ndim != 3 or arr.shape[2] < 3:
        raise ValueError(f"Expected ZED frame with at least 3 channels, got shape {arr.shape}")

    if color_order == "bgr":
        return arr[:, :, 2::-1].copy()
    return arr[:, :, :3].copy()


def run(args: argparse.Namespace) -> None:
    import pyzed.sl as sl
    from commlink import Publisher

    pub = Publisher(args.host, port=args.port)

    init = sl.InitParameters()
    init.camera_resolution = _enum_value(sl.RESOLUTION, args.resolution)
    init.camera_fps = args.fps
    init.depth_mode = sl.DEPTH_MODE.NONE

    zed = sl.Camera()
    err = zed.open(init)
    if err != sl.ERROR_CODE.SUCCESS:
        raise RuntimeError(f"ZED open failed: {err}")

    runtime = sl.RuntimeParameters()
    image = sl.Mat()
    view = _enum_value(sl.VIEW, args.view)
    frames = 0
    last_log = time.monotonic()

    print(
        "[zed_image_publisher] "
        f"publishing {args.topic} on tcp://{args.host}:{args.port} "
        f"at {args.resolution}/{args.fps}",
        flush=True,
    )

    try:
        while True:
            if zed.grab(runtime) == sl.ERROR_CODE.SUCCESS:
                zed.retrieve_image(image, view)
                pub[args.topic] = {
                    "timestamp": time.time_ns(),
                    "image": _frame_rgb(image, color_order=args.color_order),
                }
                frames += 1

            now = time.monotonic()
            if now - last_log >= args.log_period_s:
                print(f"[zed_image_publisher] fps={frames / (now - last_log):.1f}", flush=True)
                frames = 0
                last_log = now
    except KeyboardInterrupt:
        print("\n[zed_image_publisher] Shutting down...")
    finally:
        zed.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="*", help="Commlink publisher bind host")
    parser.add_argument("--port", type=int, default=6000, help="Commlink publisher port")
    parser.add_argument("--topic", default="zed/image", help="Commlink image topic")
    parser.add_argument("--resolution", choices=RESOLUTIONS, default="HD720")
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--view", choices=VIEWS, default="LEFT")
    parser.add_argument(
        "--color-order",
        choices=COLOR_ORDERS,
        default="rgb",
        help="Use bgr if the displayed stream has red/blue channels swapped",
    )
    parser.add_argument("--log-period-s", type=float, default=2.0)
    return parser.parse_args(argv)


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()
