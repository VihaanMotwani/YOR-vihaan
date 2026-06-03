// Path B Phase 2 -- Quest-side subscriber for the Thor RGBD stream.
//
// Connects to zed_rgbd_publisher.py over NetMQ, decodes the multipart
// [topic, rgb_jpg, depth_png, intrinsics_json] frames, and exposes the
// resulting Texture2Ds + intrinsics to the rest of the scene. The depth
// texture is loaded into an explicitly-linear RGBA32 so the byte values
// reach the shader unmodified by sRGB curves -- the shader-side
// reconstruction is `depth_mm = R*256 + G` (matches the publisher's
// rgb8_hl packing; B is unused; depth_mm == 0 means invalid).
//
// Wire side:  see robot/teleop/zed_rgbd_publisher.py
//
// Setup in Unity:
//   1. Drop this component on a GameObject in the scene.
//   2. Set Host to Thor's LAN IP (default 192.168.1.11) and Port to 5560.
//   3. (Optional Phase-2 sanity check) Drag a Quad's MeshRenderer into
//      DebugRgbQuad. Hit play -- the live RGB feed should show on the quad.
//      A second Quad assigned to DebugDepthQuad will show the raw packed
//      depth bytes as a strange color image; that's expected -- it
//      confirms data is flowing before Phase 3 turns those bytes into a
//      proper 3D mesh.

using System;
using System.Collections.Generic;
using System.Text;
using System.Threading;
using AsyncIO;
using NetMQ;
using NetMQ.Sockets;
using UnityEngine;

[Serializable]
public class RgbdIntrinsics
{
    public float fx;
    public float fy;
    public float cx;
    public float cy;
    public int w;
    public int h;
    public float depth_scale_m;
    public float min_m;
    public float max_m;
    public string depth_encoding;
    public long ts_ns;
}

public class RgbdStreamReceiver : MonoBehaviour
{
    [Header("Connection")]
    [Tooltip("Thor's LAN IP (the host running zed_rgbd_publisher.py)")]
    [SerializeField] private string host = "192.168.1.11";
    [SerializeField] private int port = 5560;
    [SerializeField] private string topic = "rgbd";

    [Header("Phase-2 sanity quads (optional)")]
    [Tooltip("Drag a Quad's MeshRenderer here; its material.mainTexture is " +
             "set to the live RGB feed once frames arrive.")]
    [SerializeField] private Renderer debugRgbQuad;
    [Tooltip("Same idea but shows the raw RGB-packed depth bytes -- looks " +
             "like a weird gradient and is mainly to confirm data flow.")]
    [SerializeField] private Renderer debugDepthQuad;
    [SerializeField] private bool logFirstFrame = true;

    public Texture2D RgbTex { get; private set; }
    public Texture2D DepthTex { get; private set; }
    public RgbdIntrinsics Intrinsics { get; private set; }
    public bool HasFrame { get; private set; }
    public int FramesReceived { get; private set; }

    // Worker -> main thread: the worker assigns _pending with Interlocked.
    // Exchange, the main thread pulls it with the same call. If the worker
    // produces a new frame before the main thread has consumed the previous
    // one, the old payload is GC'd -- correct behavior, we render the
    // freshest pixels rather than draining a backlog.
    private class FramePayload
    {
        public byte[] RgbJpg;
        public byte[] DepthPng;
        public string MetaJson;
    }

    private FramePayload _pending;
    private Thread _worker;
    private volatile bool _running;
    private bool _loggedFirst;

    private void Awake()
    {
        // Required before any NetMQ socket is created in a Unity process.
        ForceDotNet.Force();

        // 2x2 placeholder; real size comes from the first received frame.
        // RGB is sRGB (it's a real color image). Depth is linear so that
        // sampling in the shader returns raw byte values, not gamma-corrected
        // ones -- critical for the R*256+G reconstruction.
        RgbTex = new Texture2D(2, 2, TextureFormat.RGB24, mipChain: false);
        DepthTex = new Texture2D(2, 2, TextureFormat.RGBA32, mipChain: false, linear: true);
        DepthTex.filterMode = FilterMode.Point;
        DepthTex.wrapMode = TextureWrapMode.Clamp;
    }

    private void Start()
    {
        _running = true;
        _worker = new Thread(ReceiveLoop)
        {
            IsBackground = true,
            Name = "RgbdRx"
        };
        _worker.Start();
    }

    private void Update()
    {
        FramePayload payload = Interlocked.Exchange(ref _pending, null);
        if (payload == null) return;

        if (!RgbTex.LoadImage(payload.RgbJpg, markNonReadable: false))
        {
            Debug.LogWarning("[RgbdRx] RGB JPEG decode failed");
            return;
        }

        if (!DepthTex.LoadImage(payload.DepthPng, markNonReadable: false))
        {
            Debug.LogWarning("[RgbdRx] depth PNG decode failed");
            return;
        }
        // LoadImage can stomp filter/wrap modes when it resizes; reapply.
        DepthTex.filterMode = FilterMode.Point;
        DepthTex.wrapMode = TextureWrapMode.Clamp;

        try
        {
            Intrinsics = JsonUtility.FromJson<RgbdIntrinsics>(payload.MetaJson);
        }
        catch (Exception e)
        {
            Debug.LogWarning($"[RgbdRx] bad intrinsics JSON: {e.Message}");
        }

        HasFrame = true;
        FramesReceived++;

        if (debugRgbQuad != null && debugRgbQuad.material.mainTexture != RgbTex)
            debugRgbQuad.material.mainTexture = RgbTex;
        if (debugDepthQuad != null && debugDepthQuad.material.mainTexture != DepthTex)
            debugDepthQuad.material.mainTexture = DepthTex;

        if (logFirstFrame && !_loggedFirst)
        {
            _loggedFirst = true;
            var i = Intrinsics;
            Debug.Log($"[RgbdRx] first frame  rgb={RgbTex.width}x{RgbTex.height}  " +
                      $"depth={DepthTex.width}x{DepthTex.height}  " +
                      $"intr=(fx={i.fx:F1}, fy={i.fy:F1}, cx={i.cx:F1}, " +
                      $"cy={i.cy:F1}, enc={i.depth_encoding})");
        }
    }

    private void ReceiveLoop()
    {
        using (var sub = new SubscriberSocket())
        {
            sub.Options.ReceiveHighWatermark = 2;
            sub.Connect($"tcp://{host}:{port}");
            sub.Subscribe(topic);
            Debug.Log($"[RgbdRx] subscribed tcp://{host}:{port} topic='{topic}'");

            var timeout = TimeSpan.FromMilliseconds(50);
            var parts = new List<byte[]>(4);

            while (_running)
            {
                parts.Clear();
                if (!sub.TryReceiveMultipartBytes(timeout, ref parts, expectedFrameCount: 4))
                    continue;
                if (parts.Count < 4)
                    continue;

                var payload = new FramePayload
                {
                    RgbJpg = parts[1],
                    DepthPng = parts[2],
                    MetaJson = Encoding.UTF8.GetString(parts[3]),
                };
                Interlocked.Exchange(ref _pending, payload);
            }
        }
    }

    private void OnDisable()
    {
        _running = false;
    }

    private void OnDestroy()
    {
        _running = false;
        if (_worker != null && _worker.IsAlive)
            _worker.Join(500);
        NetMQConfig.Cleanup(false);
    }
}
