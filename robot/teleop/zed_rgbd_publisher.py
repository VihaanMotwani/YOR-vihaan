#!/usr/bin/env python3
"""ZED RGB+Depth -> ZMQ publisher for the Quest VR embodied-teleop client.

Path B vision pipeline. Runs on Thor (the CUDA host), opens a ZED in NEURAL
depth mode, and publishes left-eye RGB + per-pixel depth so a Quest client
can render the scene as a 3D point-cloud / depth mesh. Operator head motion
then creates real parallax (the whole point of Path B over Path A).

Wire format (multipart, NetMQ-compatible -- no pickle, plain bytes):
    frame 0: b"rgbd"
    frame 1: <rgb_jpg>          # JPEG, BGR uint8, e.g. 1280x720
    frame 2: <depth_raw>        # raw uint16 little-endian, one ushort per pixel
                                #   value = millimeters; 0 = invalid sentinel
                                #   payload size = W * H * 2 bytes (row-major)
    frame 3: <intrinsics_json>  # UTF-8 JSON metadata

Tuning for clean depth edges (Path B point-cloud rendering):
  * --confidence 30          (default; stricter than ZED's 90 default)
  * --texture-confidence 90  (drops untextured regions like skin)
  * --depth-stabilization 30 (temporal smoothing; max=100)
  * --remove-saturated       (default on; ignores over/underexposed pixels)

Run on Thor:
    python zed_rgbd_publisher.py
    python zed_rgbd_publisher.py --fake                  # no ZED needed
    python zed_rgbd_publisher.py --confidence 20         # even stricter

Verify from any machine on the LAN:
    python zed_rgbd_test_sub.py --host <thor_ip>
"""

import argparse
import json
import signal
import sys
import time

import cv2
import numpy as np
import zmq


TOPIC = b"rgbd"
DEFAULT_PORT = 5560


FAKE_RES = {
    "VGA":    (672,  376),
    "HD720":  (1280, 720),
    "HD1080": (1920, 1080),
    "HD2K":   (2208, 1242),
}


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="ZED RGB+Depth -> ZMQ publisher for Path B VR teleop")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT,
                    help="ZMQ PUB bind port (default: 5560)")
    ap.add_argument("--resolution", default="HD720",
                    choices=list(FAKE_RES.keys()),
                    help="ZED capture resolution (default: HD720)")
    ap.add_argument("--fps", type=int, default=30,
                    help="capture/publish rate Hz (default: 30)")
    ap.add_argument("--depth-mode", default="NEURAL",
                    choices=["NEURAL", "ULTRA", "QUALITY", "PERFORMANCE"],
                    help="ZED depth mode (default: NEURAL)")
    ap.add_argument("--min-depth-m", type=float, default=0.3,
                    help="clip depths below this to invalid (default: 0.3 m)")
    ap.add_argument("--max-depth-m", type=float, default=8.0,
                    help="clip depths above this to invalid (default: 8.0 m)")
    ap.add_argument("--confidence", type=int, default=30,
                    help="ZED depth confidence 0..100, LOWER=STRICTER (default: 30; "
                         "was 90 - drops uncertain edges that caused ghost halos)")
    ap.add_argument("--texture-confidence", type=int, default=90,
                    help="ZED texture confidence 0..100, LOWER=STRICTER "
                         "(default: 90 - drops untextured regions like skin)")
    ap.add_argument("--depth-stabilization", type=int, default=30,
                    help="ZED temporal depth smoothing 0..100 (default: 30; "
                         "was 1 - more smoothing => less per-frame flicker)")
    ap.add_argument("--remove-saturated", action="store_true", default=True,
                    help="exclude saturated (over/underexposed) pixels (default: on)")
    ap.add_argument("--jpeg-quality", type=int, default=70,
                    help="JPEG quality 0..100 for RGB (default: 70)")
    ap.add_argument("--fake", action="store_true",
                    help="skip the ZED, publish synthetic RGB+depth")
    return ap.parse_args()


def encode_depth_raw(depth_m: np.ndarray, min_m: float, max_m: float) -> bytes:
    """Convert float32 depth (meters) to raw uint16 little-endian bytes,
    one ushort per pixel storing millimeters. NaN/out-of-range pixels
    collapse to 0 (the agreed 'invalid' sentinel)."""
    valid = np.isfinite(depth_m) & (depth_m >= min_m) & (depth_m <= max_m)
    mm = np.where(valid, depth_m * 1000.0, 0.0)
    np.clip(mm, 0.0, 65535.0, out=mm)
    return mm.astype(np.uint16).tobytes()


def synthetic_rgb_depth(width: int, height: int, t: float):
    """Synthetic scene: a 'sphere' translating side-to-side over a tilted floor."""
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    floor_m = 0.7 + (1.0 - yy / (height - 1)) * 4.3
    cx = width  * (0.5 + 0.3 * np.sin(t * 0.7))
    cy = height * 0.55
    r  = min(width, height) * 0.18
    dx = xx - cx
    dy = yy - cy
    inside = dx * dx + dy * dy < r * r
    sphere_dist_m = 1.2 - 0.4 * np.sqrt(
        np.clip(r * r - dx * dx - dy * dy, 0.0, None)) / r
    depth_m = np.where(inside, sphere_dist_m, floor_m).astype(np.float32)

    rgb = np.zeros((height, width, 3), dtype=np.uint8)
    cell = 48
    grid = ((xx.astype(np.int32) // cell + yy.astype(np.int32) // cell) % 2).astype(np.uint8)
    rgb[..., 0] = 60 + 40 * grid
    rgb[..., 1] = 50 + 30 * grid
    rgb[..., 2] = 40 + 20 * grid
    rgb[inside] = (40, 140, 240)
    cv2.putText(rgb, f"FAKE t={t:6.2f}s {width}x{height}",
                (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                (255, 255, 255), 2, cv2.LINE_AA)
    return rgb, depth_m


def open_zed(args):
    """Open a real ZED. Returns (cam, fx, fy, cx, cy, W, H) or raises."""
    import pyzed.sl as sl
    res_map = {
        "VGA":    sl.RESOLUTION.VGA,
        "HD720":  sl.RESOLUTION.HD720,
        "HD1080": sl.RESOLUTION.HD1080,
        "HD2K":   sl.RESOLUTION.HD2K,
    }
    dm_map = {
        "NEURAL":      sl.DEPTH_MODE.NEURAL,
        "ULTRA":       sl.DEPTH_MODE.ULTRA,
        "QUALITY":     sl.DEPTH_MODE.QUALITY,
        "PERFORMANCE": sl.DEPTH_MODE.PERFORMANCE,
    }
    init = sl.InitParameters()
    init.camera_resolution = res_map[args.resolution]
    init.camera_fps = args.fps
    init.depth_mode = dm_map[args.depth_mode]
    init.coordinate_units = sl.UNIT.METER
    init.coordinate_system = sl.COORDINATE_SYSTEM.RIGHT_HANDED_Y_UP
    init.depth_maximum_distance = float(args.max_depth_m)
    init.depth_minimum_distance = float(args.min_depth_m)
    init.depth_stabilization = int(args.depth_stabilization)

    cam = sl.Camera()
    err = cam.open(init)
    if err != sl.ERROR_CODE.SUCCESS:
        raise RuntimeError(f"ZED open failed: {err!r}")

    ci = cam.get_camera_information()
    calib = ci.camera_configuration.calibration_parameters.left_cam
    fx, fy = float(calib.fx), float(calib.fy)
    cx, cy = float(calib.cx), float(calib.cy)
    W = int(ci.camera_configuration.resolution.width)
    H = int(ci.camera_configuration.resolution.height)
    return cam, fx, fy, cx, cy, W, H


def main() -> None:
    args = parse_args()

    use_fake = args.fake
    cam = None
    sl = None  # type: ignore
    fx = fy = cx = cy = 0.0
    W, H = FAKE_RES[args.resolution]

    if not use_fake:
        try:
            import pyzed.sl as sl  # noqa: F401
            cam, fx, fy, cx, cy, W, H = open_zed(args)
            print(f"[rgbd_pub] ZED open: {W}x{H}@{args.fps} "
                  f"depth={args.depth_mode}  fx={fx:.1f} fy={fy:.1f} "
                  f"cx={cx:.1f} cy={cy:.1f}")
            print(f"[rgbd_pub] runtime: confidence={args.confidence} "
                  f"texture_conf={args.texture_confidence} "
                  f"stabilization={args.depth_stabilization}")
        except Exception as e:
            print(f"[rgbd_pub] ZED unavailable ({e}); falling back to --fake.",
                  file=sys.stderr)
            use_fake = True

    if use_fake:
        fx = fy = 0.55 * W
        cx, cy = W * 0.5, H * 0.5
        print(f"[rgbd_pub] FAKE mode: {W}x{H}@{args.fps}  "
              f"fx={fx:.1f} cx={cx:.1f} cy={cy:.1f}")

    intrinsics = {
        "fx": fx, "fy": fy, "cx": cx, "cy": cy,
        "w": W, "h": H,
        "depth_scale_m": 0.001,
        "min_m": args.min_depth_m,
        "max_m": args.max_depth_m,
        "depth_encoding": "raw_u16_le",
    }

    ctx = zmq.Context.instance()
    sock = ctx.socket(zmq.PUB)
    sock.set_hwm(2)
    sock.bind(f"tcp://*:{args.port}")
    print(f"[rgbd_pub] bound tcp://*:{args.port}  topic={TOPIC!r}")

    stop = {"flag": False}

    def _handle(signum, _frame):
        stop["flag"] = True
        print(f"\n[rgbd_pub] signal {signum} -- shutting down")

    signal.signal(signal.SIGINT, _handle)
    signal.signal(signal.SIGTERM, _handle)

    jpeg_params = [int(cv2.IMWRITE_JPEG_QUALITY), int(args.jpeg_quality)]
    frame_interval = 1.0 / args.fps

    if not use_fake:
        import pyzed.sl as sl
        runtime = sl.RuntimeParameters()
        runtime.confidence_threshold = int(args.confidence)
        # texture_confidence_threshold may not exist on every SDK version;
        # guard with hasattr so the publisher still runs on older SDKs.
        if hasattr(runtime, "texture_confidence_threshold"):
            runtime.texture_confidence_threshold = int(args.texture_confidence)
        if hasattr(runtime, "remove_saturated_areas"):
            runtime.remove_saturated_areas = bool(args.remove_saturated)
        rgba_mat = sl.Mat(W, H, sl.MAT_TYPE.U8_C4, memory_type=sl.MEM.CPU)
        depth_mat = sl.Mat(W, H, sl.MAT_TYPE.F32_C1, memory_type=sl.MEM.CPU)

    t0 = time.monotonic()
    frames = 0
    win_start = time.monotonic()
    win_rgb_kb = 0
    win_depth_kb = 0

    try:
        while not stop["flag"]:
            loop_start = time.monotonic()

            if use_fake:
                rgb_bgr, depth_m = synthetic_rgb_depth(W, H, loop_start - t0)
            else:
                if cam.grab(runtime) != sl.ERROR_CODE.SUCCESS:
                    time.sleep(0.002)
                    continue
                cam.retrieve_image(rgba_mat, sl.VIEW.LEFT)
                cam.retrieve_measure(depth_mat, sl.MEASURE.DEPTH)
                rgba = rgba_mat.get_data()
                rgb_bgr = rgba[..., :3]
                depth_m = depth_mat.get_data().astype(np.float32, copy=False)

            ok_jpg, rgb_jpg = cv2.imencode(".jpg", rgb_bgr, jpeg_params)
            if not ok_jpg:
                print("[rgbd_pub] JPEG encode failed, skipping frame")
                continue

            depth_bytes = encode_depth_raw(depth_m, args.min_depth_m, args.max_depth_m)

            intrinsics["ts_ns"] = time.time_ns()
            meta = json.dumps(intrinsics, separators=(",", ":")).encode("utf-8")

            sock.send_multipart([TOPIC, rgb_jpg.tobytes(), depth_bytes, meta])

            frames += 1
            win_rgb_kb += len(rgb_jpg) / 1024.0
            win_depth_kb += len(depth_bytes) / 1024.0
            now = time.monotonic()
            if now - win_start >= 1.0:
                print(f"[rgbd_pub] {frames:3d} fps  "
                      f"rgb {win_rgb_kb/frames:5.1f} KB/f  "
                      f"depth {win_depth_kb/frames:5.1f} KB/f  "
                      f"total {(win_rgb_kb+win_depth_kb)*8/1024:.1f} Mbps   ",
                      end="\r")
                frames = 0
                win_rgb_kb = win_depth_kb = 0.0
                win_start = now

            if use_fake:
                slack = frame_interval - (time.monotonic() - loop_start)
                if slack > 0:
                    time.sleep(slack)
    finally:
        if cam is not None:
            cam.close()
        sock.close(linger=0)
        ctx.term()
        print("\n[rgbd_pub] closed")


if __name__ == "__main__":
    main()
