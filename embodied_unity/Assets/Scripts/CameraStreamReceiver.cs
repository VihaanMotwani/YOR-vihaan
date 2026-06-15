using System;
using System.IO;
using System.Net;
using System.Threading;
using UnityEngine;
using UnityEngine.UI;
using NetMQ;
using NetMQ.Sockets;

public class CameraStreamReceiver : MonoBehaviour
{
    public enum StreamType
    {
        MJPEG,
        ZeroMQ
    }

    [Header("Stream Configuration")]
    public StreamType streamType = StreamType.ZeroMQ;

    [Tooltip("HTTP URL for the MJPEG stream, e.g., http://127.0.0.1:8080/video")]
    public string mjpegUrl = "http://127.0.0.1:8080/video";

    [Tooltip("ZeroMQ publisher address to connect to, e.g., tcp://127.0.0.1:5556")]
    public string zmqAddress = "tcp://127.0.0.1:5556";

    [Tooltip("ZeroMQ topic to subscribe to. Leave empty to receive all messages.")]
    public string zmqTopic = "camera";

    [Header("Rendering Targets")]
    [Tooltip("Optional Renderer (e.g. Quad mesh renderer) to apply the camera texture to.")]
    public Renderer targetRenderer;

    [Tooltip("Optional RawImage component to apply the camera texture to.")]
    public RawImage targetRawImage;

    [Header("Performance & Status")]
    [ReadOnly] public bool isConnected = false;
    [ReadOnly] public float currentFps = 0f;
    [ReadOnly] public string streamStatus = "Disconnected";

    // Decoded texture
    private Texture2D texture;
    
    // Thread safety
    private Thread receiverThread;
    private volatile bool isRunning = false;
    private byte[] latestFrameBytes;
    private bool hasNewFrame = false;
    private readonly object frameLock = new object();

    // Stats
    private int frameCount = 0;
    private float fpsTimer = 0f;

    // Events for UI scripts to hook into
    public event Action<bool, string> OnStatusChanged;
    public event Action<float> OnFpsUpdated;

    void Awake()
    {
        ResolveNucIP();
    }

    private void ResolveNucIP()
    {
        string ip = NetworkConfig.GetNucIP();
        if (!string.IsNullOrEmpty(ip))
        {
            if (!string.IsNullOrEmpty(mjpegUrl))
            {
                string oldUrl = mjpegUrl;
                mjpegUrl = mjpegUrl.Replace("127.0.0.1", ip);
                Debug.Log($"[CameraStreamReceiver] Resolved MJPEG URL: {oldUrl} -> {mjpegUrl}");
            }
            if (!string.IsNullOrEmpty(zmqAddress))
            {
                string oldAddress = zmqAddress;
                zmqAddress = zmqAddress.Replace("127.0.0.1", ip);
                Debug.Log($"[CameraStreamReceiver] Resolved ZMQ Address: {oldAddress} -> {zmqAddress}");
            }
        }
    }

    void Start()
    {
        // Create the texture that we will reuse
        // Using a tiny starting resolution; LoadImage will automatically resize the texture
        texture = new Texture2D(2, 2, TextureFormat.RGB24, false);
        
        // Apply initial texture to rendering targets
        ApplyTextureToTargets(texture);

        StartStream();
    }

    public void StartStream()
    {
        if (isRunning) StopStream();

        isRunning = true;
        isConnected = false;
        streamStatus = "Connecting...";
        OnStatusChanged?.Invoke(isConnected, streamStatus);

        receiverThread = new Thread(BackgroundStreamLoop)
        {
            IsBackground = true,
            Name = "CameraStreamReceiverThread"
        };
        receiverThread.Start();
    }

    public void StopStream()
    {
        isRunning = false;
        
        if (receiverThread != null && receiverThread.IsAlive)
        {
            // Allow thread to exit gracefully
            receiverThread.Join(1000);
            if (receiverThread.IsAlive)
            {
                Debug.LogWarning("[CameraStreamReceiver] Receiver thread did not stop within 1s; it will exit after the active read timeout.");
            }
        }
        receiverThread = null;

        isConnected = false;
        streamStatus = "Disconnected";
        currentFps = 0f;
        OnStatusChanged?.Invoke(isConnected, streamStatus);
        OnFpsUpdated?.Invoke(currentFps);
    }

    void Update()
    {
        // Apply the latest decoded frame to our texture on the main thread
        byte[] bytesToLoad = null;

        lock (frameLock)
        {
            if (hasNewFrame)
            {
                bytesToLoad = latestFrameBytes;
                hasNewFrame = false;
            }
        }

        if (bytesToLoad != null)
        {
            if (!isConnected)
            {
                isConnected = true;
                streamStatus = "Connected";
                OnStatusChanged?.Invoke(isConnected, streamStatus);
            }

            // LoadImage auto-resizes the texture and uploads it to the GPU
            if (texture.LoadImage(bytesToLoad))
            {
                frameCount++;
            }
        }

        // FPS Calculations
        fpsTimer += Time.deltaTime;
        if (fpsTimer >= 1.0f)
        {
            currentFps = frameCount / fpsTimer;
            frameCount = 0;
            fpsTimer = 0f;
            OnFpsUpdated?.Invoke(currentFps);
        }
    }

    private void ApplyTextureToTargets(Texture2D tex)
    {
        if (targetRenderer != null)
        {
            targetRenderer.material.mainTexture = tex;
        }

        if (targetRawImage != null)
        {
            targetRawImage.texture = tex;
        }
    }

    private void OnFrameReceived(byte[] bytes)
    {
        lock (frameLock)
        {
            latestFrameBytes = bytes;
            hasNewFrame = true;
        }
    }

    private void BackgroundStreamLoop()
    {
        while (isRunning)
        {
            try
            {
                if (streamType == StreamType.MJPEG)
                {
                    RunMjpegClient();
                }
                else
                {
                    RunZmqClient();
                }
            }
            catch (Exception e)
            {
                Debug.LogWarning($"Stream connection error: {e.Message}");
                // Wait before retrying
                Thread.Sleep(2000);
            }
        }
    }

    private void RunMjpegClient()
    {
        HttpWebRequest request = (HttpWebRequest)WebRequest.Create(mjpegUrl);
        request.Timeout = 5000;
        request.ReadWriteTimeout = 5000;
        request.AllowReadStreamBuffering = false;

        using (HttpWebResponse response = (HttpWebResponse)request.GetResponse())
        using (Stream stream = response.GetResponseStream())
        {
            byte[] buffer = new byte[1024 * 1024]; // 1MB buffer for frames
            int bufferOffset = 0;

            while (isRunning)
            {
                int bytesRead = stream.Read(buffer, bufferOffset, buffer.Length - bufferOffset);
                if (bytesRead <= 0)
                {
                    throw new Exception("MJPEG stream returned 0 bytes.");
                }

                bufferOffset += bytesRead;

                // Look for JPEG Start of Image (SOI) and End of Image (EOI) markers
                int startIndex = -1;
                int endIndex = -1;

                for (int i = 0; i < bufferOffset - 1; i++)
                {
                    if (buffer[i] == 0xFF && buffer[i + 1] == 0xD8)
                    {
                        startIndex = i;
                        break;
                    }
                }

                if (startIndex != -1)
                {
                    for (int i = startIndex + 2; i < bufferOffset - 1; i++)
                    {
                        if (buffer[i] == 0xFF && buffer[i + 1] == 0xD9)
                        {
                            endIndex = i + 2; // Include EOI bytes
                            break;
                        }
                    }
                }

                if (startIndex != -1 && endIndex != -1)
                {
                    int imageLength = endIndex - startIndex;
                    byte[] imgBytes = new byte[imageLength];
                    Buffer.BlockCopy(buffer, startIndex, imgBytes, 0, imageLength);

                    // Send the frame data to the main thread buffer
                    OnFrameReceived(imgBytes);

                    // Shift remaining bytes in buffer
                    int remainingBytes = bufferOffset - endIndex;
                    if (remainingBytes > 0)
                    {
                        Buffer.BlockCopy(buffer, endIndex, buffer, 0, remainingBytes);
                        bufferOffset = remainingBytes;
                    }
                    else
                    {
                        bufferOffset = 0;
                    }
                }
                else if (bufferOffset >= buffer.Length)
                {
                    // Buffer is full but no complete frame is found, reset buffer offset to avoid overflow
                    bufferOffset = 0;
                }
            }
        }
    }

    private void RunZmqClient()
    {
        // NetMQ context must be initialized
        AsyncIO.ForceDotNet.Force();

        using (var subSocket = new SubscriberSocket())
        {
            subSocket.Connect(zmqAddress);
            subSocket.Subscribe(zmqTopic);
            subSocket.Options.ReceiveHighWatermark = 10; // Keep queue small for low latency

            Debug.Log($"Connected ZMQ Subscriber to {zmqAddress}, topic: {zmqTopic}");

            while (isRunning)
            {
                byte[] messageBytes = null;
                bool hasMore = false;

                // Try to read first frame (topic or raw image depending on publisher)
                if (subSocket.TryReceiveFrameBytes(TimeSpan.FromMilliseconds(200), out messageBytes, out hasMore))
                {
                    if (hasMore)
                    {
                        // Topic prefix pattern: read subsequent frame for actual image bytes
                        byte[] imageBytes = null;
                        if (subSocket.TryReceiveFrameBytes(TimeSpan.FromMilliseconds(200), out imageBytes, out hasMore))
                        {
                            OnFrameReceived(imageBytes);

                            // Drain any additional parts
                            while (hasMore)
                            {
                                subSocket.ReceiveFrameBytes(out hasMore);
                            }
                        }
                    }
                    else
                    {
                        // No topic prefix, raw image bytes only
                        OnFrameReceived(messageBytes);
                    }
                }
            }
        }
    }

    void OnDestroy()
    {
        StopStream();
    }

    void OnApplicationQuit()
    {
        StopStream();
    }
}

// Simple ReadOnly attribute for Inspector styling
public class ReadOnlyAttribute : PropertyAttribute { }

#if UNITY_EDITOR
[UnityEditor.CustomPropertyDrawer(typeof(ReadOnlyAttribute))]
public class ReadOnlyDrawer : UnityEditor.PropertyDrawer
{
    public override void OnGUI(Rect position, UnityEditor.SerializedProperty property, GUIContent label)
    {
        GUI.enabled = false;
        UnityEditor.EditorGUI.PropertyField(position, property, label, true);
        GUI.enabled = true;
    }
}
#endif
