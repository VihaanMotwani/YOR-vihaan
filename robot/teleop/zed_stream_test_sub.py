#!/usr/bin/env python3
"""Quick test subscriber for the ZED stereo stream.

Connects to the publisher at <host>:5558, decodes JPEGs, displays them in a
window. Use this to verify the stream is reachable from a remote machine
(e.g. your PC, on the same LAN as the Pi) before debugging the Unity client.

Requires a display (cv2.imshow). If running on the Pi over SSH, use 'ssh -X'.

Install on the consumer machine:
    pip install pyzmq opencv-python numpy

Run from your PC:
    python zed_stream_test_sub.py                  # default host 192.168.1.163
    python zed_stream_test_sub.py --host 127.0.0.1  # if running on the Pi
"""

import argparse

import cv2
import numpy as np
import zmq


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="192.168.1.163",
                    help="publisher host (Pi LAN IP)")
    ap.add_argument("--port", type=int, default=5558)
    ap.add_argument("--topic", default="img")
    args = ap.parse_args()

    ctx = zmq.Context.instance()
    sub = ctx.socket(zmq.SUB)
    sub.set_hwm(2)
    sub.connect(f"tcp://{args.host}:{args.port}")
    sub.subscribe(args.topic.encode())
    print(f"[test_sub] subscribed tcp://{args.host}:{args.port} topic='{args.topic}'")
    print("[test_sub] press ESC in the image window to quit")

    frames = 0
    last_size_kb = 0
    try:
        while True:
            parts = sub.recv_multipart()
            if len(parts) < 2:
                continue
            payload = parts[1]
            arr = np.frombuffer(payload, dtype=np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is None:
                print("[test_sub] JPEG decode failed")
                continue
            frames += 1
            last_size_kb = len(payload) // 1024
            cv2.imshow("zed_stereo_test", frame)
            if cv2.waitKey(1) & 0xFF == 27:     # ESC
                break
            if frames % 30 == 0:
                print(f"[test_sub] {frames} frames, last {last_size_kb} KB, "
                      f"shape {frame.shape}    ", end="\r")
    finally:
        sub.close()
        ctx.term()
        cv2.destroyAllWindows()
        print(f"\n[test_sub] received {frames} frames total")


if __name__ == "__main__":
    main()
