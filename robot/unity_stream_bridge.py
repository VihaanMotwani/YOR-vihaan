#!/usr/bin/env python3
"""Bridge YOR ZED frames into the Unity VR app stream format.

The robot publishes ZED images through ``commlink`` on topic ``zed/image``.
The Unity app expects a plain ZeroMQ PUB socket with multipart messages:

    [b"camera", <jpeg bytes>]

This script keeps that translation at the process boundary so the Unity app
does not need to understand the robot's internal pub/sub payload format.
"""

from __future__ import annotations

import argparse
import io
import time
from typing import Any

import numpy as np
import zmq

try:
    from commlink import Subscriber
except ImportError:  # pragma: no cover - only needed when running the bridge.
    Subscriber = None

try:
    import cv2
except ImportError:  # pragma: no cover - exercised when OpenCV is unavailable.
    cv2 = None

try:
    from PIL import Image
except ImportError:  # pragma: no cover - Pillow is a project dependency.
    Image = None


ZED_PUB_PORT = 6000
IMAGE_TOPIC = "zed/image"

UNITY_CAMERA_PORT = 5556
UNITY_CAMERA_TOPIC = "camera"
UNITY_STATUS_PORT = 5558
UNITY_STATUS_TOPIC = "status"


def encode_jpeg(image: Any, quality: int) -> bytes:
    arr = np.asarray(image)
    if arr.ndim != 3 or arr.shape[2] < 3:
        raise ValueError(f"Expected HxWx3 image array, got shape {arr.shape}")

    arr = arr[:, :, :3]
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)

    quality = max(1, min(int(quality), 100))

    if cv2 is not None:
        # ZED publisher emits RGB; OpenCV's JPEG encoder expects BGR.
        bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        ok, encoded = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
        if not ok:
            raise RuntimeError("OpenCV failed to encode JPEG frame")
        return encoded.tobytes()

    if Image is None:
        raise RuntimeError("Install opencv-python or pillow to encode camera frames")

    buf = io.BytesIO()
    Image.fromarray(arr, mode="RGB").save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def publish_status(
    socket: zmq.Socket,
    *,
    topic: bytes,
    arm_locked: bool,
    base_moving: bool,
    camera_streaming: bool,
    last_frame_age_ms: int | None,
) -> None:
    fields = [
        f"arm_locked:{str(arm_locked).lower()}",
        f"base_moving:{str(base_moving).lower()}",
        f"camera_streaming:{str(camera_streaming).lower()}",
    ]
    if last_frame_age_ms is not None:
        fields.append(f"last_frame_age_ms:{last_frame_age_ms}")
    socket.send_multipart([topic, ";".join(fields).encode("utf-8")])


def run(args: argparse.Namespace) -> None:
    if Subscriber is None:
        raise RuntimeError("commlink is required to subscribe to the robot ZED stream")

    zed_sub = Subscriber(
        host=args.zed_host,
        port=args.zed_port,
        topics=[args.zed_image_topic],
        buffer=False,
    )

    ctx = zmq.Context.instance()
    camera_pub = ctx.socket(zmq.PUB)
    camera_pub.setsockopt(zmq.SNDHWM, 1)
    camera_pub.bind(f"tcp://{args.bind_host}:{args.camera_port}")

    status_pub = None
    if not args.no_status:
        status_pub = ctx.socket(zmq.PUB)
        status_pub.setsockopt(zmq.SNDHWM, 1)
        status_pub.bind(f"tcp://{args.bind_host}:{args.status_port}")

    camera_topic = args.camera_topic.encode("utf-8")
    status_topic = args.status_topic.encode("utf-8")
    frame_period = 1.0 / max(float(args.max_fps), 1.0)
    last_publish_time = 0.0
    last_status_time = 0.0
    last_frame_timestamp = None
    last_frame_wall_time = None

    print(
        "[unity_stream_bridge] "
        f"ZED {args.zed_host}:{args.zed_port}/{args.zed_image_topic} -> "
        f"Unity camera tcp://{args.bind_host}:{args.camera_port}/{args.camera_topic}"
    )
    if status_pub is not None:
        print(
            "[unity_stream_bridge] "
            f"Unity status tcp://{args.bind_host}:{args.status_port}/{args.status_topic}"
        )

    try:
        while True:
            now = time.monotonic()

            msg = zed_sub[args.zed_image_topic]
            if msg is not None and (now - last_publish_time) >= frame_period:
                timestamp = msg.get("timestamp")
                if timestamp != last_frame_timestamp:
                    jpeg = encode_jpeg(msg["image"], args.jpeg_quality)
                    camera_pub.send_multipart([camera_topic, jpeg])
                    last_publish_time = now
                    last_frame_timestamp = timestamp
                    last_frame_wall_time = now

            if status_pub is not None and (now - last_status_time) >= args.status_period_s:
                last_frame_age_ms = None
                if last_frame_wall_time is not None:
                    last_frame_age_ms = int((now - last_frame_wall_time) * 1000)

                publish_status(
                    status_pub,
                    topic=status_topic,
                    arm_locked=args.arm_locked,
                    base_moving=args.base_moving,
                    camera_streaming=last_frame_wall_time is not None,
                    last_frame_age_ms=last_frame_age_ms,
                )
                last_status_time = now

            time.sleep(0.001)
    except KeyboardInterrupt:
        print("\n[unity_stream_bridge] Shutting down...")
    finally:
        zed_sub.stop()
        camera_pub.close(linger=0)
        if status_pub is not None:
            status_pub.close(linger=0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zed-host", default="127.0.0.1")
    parser.add_argument("--zed-port", type=int, default=ZED_PUB_PORT)
    parser.add_argument("--zed-image-topic", default=IMAGE_TOPIC)
    parser.add_argument("--bind-host", default="*")
    parser.add_argument("--camera-port", type=int, default=UNITY_CAMERA_PORT)
    parser.add_argument("--camera-topic", default=UNITY_CAMERA_TOPIC)
    parser.add_argument("--status-port", type=int, default=UNITY_STATUS_PORT)
    parser.add_argument("--status-topic", default=UNITY_STATUS_TOPIC)
    parser.add_argument("--status-period-s", type=float, default=0.5)
    parser.add_argument("--jpeg-quality", type=int, default=80)
    parser.add_argument("--max-fps", type=float, default=30.0)
    parser.add_argument("--arm-locked", action="store_true")
    parser.add_argument("--base-moving", action="store_true")
    parser.add_argument("--no-status", action="store_true")
    return parser.parse_args()


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()
