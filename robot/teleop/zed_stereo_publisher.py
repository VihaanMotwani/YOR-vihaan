#!/usr/bin/env python3
"""ZED (or any UVC stereo camera) -> ZMQ publisher for the Quest VR teleop client.

Reads a side-by-side stereo USB camera (e.g. ZED in UVC mode), JPEG-encodes
the packed frame, publishes it over ZMQ PUB on port 5558.

If no camera is present, falls back to a synthetic test pattern so the Unity
APK can be developed end-to-end before the camera is wired up.

Wire format (multipart):
    frame 0: b"img"
    frame 1: <jpeg bytes>     # BGR, (2*W) x H, e.g. 2560x720 for ZED HD720

The Unity-side NetMQ subscriber splits the texture down the middle and binds
the left half to the left eye, right half to the right eye.

No dependency on the ZED SDK or pyzed -- ZED cameras expose a normal UVC
device in /dev/videoX and OpenCV's V4L2 backend reads them just fine.
"""

import argparse
import signal
import time

import cv2
import numpy as np
import zmq


TOPIC = b"img"


def open_camera(device: int, width: int, height: int, fps: int):
    """Open the camera in V4L2 mode. Returns None if it can't deliver frames."""
    cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
    if not cap.isOpened():
        return None
    # Force MJPG so a USB2 link can carry 2560x720@30; YUYV would cap much lower.
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)
    ok, _ = cap.read()
    if not ok:
        cap.release()
        return None
    return cap


def synthetic_frame(half_w: int, h: int, t: float) -> np.ndarray:
    """Produce a (h, 2*half_w, 3) BGR test pattern with a clear L/R split and a
    ticking counter so the operator can confirm the stream is live and that
    the Unity stereo split is correctly assigning halves to eyes."""
    frame = np.zeros((h, 2 * half_w, 3), dtype=np.uint8)
    # Left half: dim blue
    frame[:, :half_w] = (60, 30, 0)
    cv2.putText(frame, "L",
                (half_w // 2 - 100, h // 2 + 80),
                cv2.FONT_HERSHEY_SIMPLEX, 8.0, (255, 255, 255), 12, cv2.LINE_AA)
    # Right half: dim red
    frame[:, half_w:] = (0, 30, 60)
    cv2.putText(frame, "R",
                (half_w + half_w // 2 - 100, h // 2 + 80),
                cv2.FONT_HERSHEY_SIMPLEX, 8.0, (255, 255, 255), 12, cv2.LINE_AA)
    # Ticking counter on both halves so frame updates are visible.
    msg = f"t={t:6.2f}s"
    cv2.putText(frame, msg, (40, h - 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3, cv2.LINE_AA)
    cv2.putText(frame, msg, (half_w + 40, h - 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3, cv2.LINE_AA)
    return frame


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="ZED/UVC stereo stream -> ZMQ for Quest VR client",
    )
    ap.add_argument("--device", type=int, default=0, help="V4L2 device index (/dev/videoN)")
    ap.add_argument("--width", type=int, default=2560, help="packed frame width (2x per-eye)")
    ap.add_argument("--height", type=int, default=720, help="frame height")
    ap.add_argument("--fps", type=int, default=30, help="capture/publish rate")
    ap.add_argument("--port", type=int, default=5558, help="ZMQ PUB bind port")
    ap.add_argument("--quality", type=int, default=70, help="JPEG quality 0..100")
    ap.add_argument("--fake", action="store_true",
                    help="skip camera; publish a synthetic test pattern")
    return ap.parse_args()


def main() -> None:
    args = parse_args()

    ctx = zmq.Context.instance()
    sock = ctx.socket(zmq.PUB)
    sock.set_hwm(2)
    sock.bind(f"tcp://*:{args.port}")
    print(f"[stereo_pub] bound tcp://*:{args.port}")

    cap = None
    use_fake = args.fake
    if not use_fake:
        cap = open_camera(args.device, args.width, args.height, args.fps)
        if cap is None:
            print(f"[stereo_pub] no camera at /dev/video{args.device} "
                  f"(or can't deliver {args.width}x{args.height}@{args.fps}); "
                  "falling back to synthetic pattern.")
            use_fake = True
    if use_fake:
        print(f"[stereo_pub] FAKE mode: {args.width}x{args.height} @ {args.fps} fps")
    else:
        print(f"[stereo_pub] camera /dev/video{args.device} "
              f"@ {args.width}x{args.height}@{args.fps}")

    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), args.quality]
    frame_interval = 1.0 / args.fps
    half_w = args.width // 2

    stop = {"flag": False}

    def _handle(signum, _frame):
        stop["flag"] = True
        print(f"\n[stereo_pub] signal {signum} -- shutting down")

    signal.signal(signal.SIGINT, _handle)
    signal.signal(signal.SIGTERM, _handle)

    t0 = time.monotonic()
    frames = 0
    t_window = time.monotonic()
    try:
        while not stop["flag"]:
            loop_start = time.monotonic()

            if use_fake:
                frame = synthetic_frame(half_w, args.height, loop_start - t0)
            else:
                ok, frame = cap.read()
                if not ok:
                    print("[stereo_pub] camera read failed; retrying")
                    time.sleep(0.05)
                    continue

            ok, jpg = cv2.imencode(".jpg", frame, encode_params)
            if not ok:
                continue
            sock.send_multipart([TOPIC, jpg.tobytes()])

            frames += 1
            now = time.monotonic()
            if now - t_window >= 1.0:
                print(f"[stereo_pub] {frames} fps, "
                      f"{len(jpg) / 1024:.0f} KB/frame   ",
                      end="\r")
                frames = 0
                t_window = now

            # Pace only in fake mode; real camera reads block at the device's rate.
            if use_fake:
                slack = frame_interval - (time.monotonic() - loop_start)
                if slack > 0:
                    time.sleep(slack)
    finally:
        if cap is not None:
            cap.release()
        sock.close(linger=0)
        ctx.term()
        print("\n[stereo_pub] closed")


if __name__ == "__main__":
    main()
