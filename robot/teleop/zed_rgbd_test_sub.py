#!/usr/bin/env python3
"""Diagnostic subscriber for the Path B RGBD stream.

Connects to `zed_rgbd_publisher.py` on Thor (default 192.168.1.105:5560),
decodes the multipart [topic, rgb_jpg, depth_blob, intrinsics_json] frames,
and displays:
  * an RGB window
  * a colormap'd depth window (jet, near=red far=blue, black=invalid)

Depth blob interpretation is driven by meta["depth_encoding"]:
  * "raw_u16_le" (current) -- raw little-endian uint16 mm bytes
  * "rgb8_hl"    (legacy)  -- PNG-8 BGR with R=high, G=low byte
Other encodings get logged and skipped.

Use this from a Linux box with a display (the Pi over `ssh -X`, or your
laptop) to confirm the stream is reachable and that depth looks reasonable
before moving on to the Unity-side RGBD receiver.

    python zed_rgbd_test_sub.py --host 192.168.1.105
    python zed_rgbd_test_sub.py --host 127.0.0.1         # if running on Thor
"""

import argparse
import json

import cv2
import numpy as np
import zmq


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="192.168.1.11",
                    help="publisher host (Thor LAN IP)")
    ap.add_argument("--port", type=int, default=5560)
    ap.add_argument("--topic", default="rgbd")
    ap.add_argument("--max-depth-m", type=float, default=8.0,
                    help="upper bound for the depth colormap")
    args = ap.parse_args()

    ctx = zmq.Context.instance()
    sub = ctx.socket(zmq.SUB)
    sub.set_hwm(2)
    sub.connect(f"tcp://{args.host}:{args.port}")
    sub.subscribe(args.topic.encode())
    print(f"[rgbd_test_sub] subscribed tcp://{args.host}:{args.port} "
          f"topic={args.topic!r}")
    print("[rgbd_test_sub] press ESC in either window to quit")

    printed_intr = False
    frames = 0
    try:
        while True:
            parts = sub.recv_multipart()
            if len(parts) < 4:
                print(f"[rgbd_test_sub] short message: {len(parts)} parts; skipping")
                continue
            _topic, rgb_jpg, depth_blob, meta_json = parts[:4]

            try:
                meta = json.loads(meta_json.decode("utf-8"))
            except Exception as e:
                print(f"[rgbd_test_sub] bad intrinsics JSON: {e}")
                continue

            rgb = cv2.imdecode(np.frombuffer(rgb_jpg, np.uint8), cv2.IMREAD_COLOR)
            if rgb is None:
                print("[rgbd_test_sub] JPEG decode failed; skipping frame")
                continue

            enc = meta.get("depth_encoding", "raw_u16_le")
            if enc == "raw_u16_le":
                W, H = int(meta["w"]), int(meta["h"])
                expected = W * H * 2
                if len(depth_blob) != expected:
                    print(f"[rgbd_test_sub] depth size {len(depth_blob)} != "
                          f"expected {expected}; skipping")
                    continue
                depth_u16 = np.frombuffer(depth_blob, dtype=np.uint16).reshape(H, W)
            elif enc == "rgb8_hl":
                # Legacy PNG-8 BGR packing: R=high byte, G=low byte, B=0.
                bgr = cv2.imdecode(np.frombuffer(depth_blob, np.uint8),
                                   cv2.IMREAD_COLOR)
                if bgr is None:
                    print("[rgbd_test_sub] PNG depth decode failed; skipping")
                    continue
                depth_u16 = ((bgr[..., 2].astype(np.uint16) << 8)
                             | bgr[..., 1].astype(np.uint16))
            else:
                print(f"[rgbd_test_sub] unknown depth_encoding {enc!r}; skipping")
                continue

            if not printed_intr:
                print(f"[rgbd_test_sub] first frame: rgb {rgb.shape}, "
                      f"depth {depth_u16.shape} dtype={depth_u16.dtype}")
                print(f"[rgbd_test_sub] intrinsics: {meta}")
                printed_intr = True

            # Colormap depth: scale mm -> [0,255] over [0, max_depth_m].
            depth_m = depth_u16.astype(np.float32) * 0.001
            valid = depth_u16 != 0
            scaled = np.clip(depth_m / max(args.max_depth_m, 1e-3), 0.0, 1.0)
            depth_vis = cv2.applyColorMap(
                (scaled * 255).astype(np.uint8), cv2.COLORMAP_JET)
            depth_vis[~valid] = (0, 0, 0)

            # Overlay center-pixel depth so the operator can sanity-check distance.
            h, w = depth_u16.shape
            cu, cv_ = w // 2, h // 2
            d_center = depth_m[cv_, cu] if valid[cv_, cu] else float("nan")
            cv2.drawMarker(depth_vis, (cu, cv_), (255, 255, 255),
                           cv2.MARKER_CROSS, 24, 2)
            cv2.putText(depth_vis, f"center {d_center:.2f} m",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                        (255, 255, 255), 2, cv2.LINE_AA)

            cv2.imshow("rgbd_test: RGB", rgb)
            cv2.imshow("rgbd_test: DEPTH (jet, black=invalid)", depth_vis)
            if cv2.waitKey(1) & 0xFF == 27:     # ESC
                break

            frames += 1
            if frames % 30 == 0:
                rgb_kb = len(rgb_jpg) // 1024
                depth_kb = len(depth_blob) // 1024
                print(f"[rgbd_test_sub] {frames} frames  "
                      f"rgb {rgb_kb} KB  depth {depth_kb} KB    ", end="\r")
    finally:
        sub.close()
        ctx.term()
        cv2.destroyAllWindows()
        print(f"\n[rgbd_test_sub] received {frames} frames total")


if __name__ == "__main__":
    main()
