using System;
using System.Threading;
using UnityEngine;
using NetMQ;
using NetMQ.Sockets;

public class RobotStatusSubscriber : MonoBehaviour
{
    [Header("ZMQ Status Configuration")]
    [Tooltip("Address of the robot status publisher, e.g., tcp://127.0.0.1:5558")]
    public string zmqAddress = "tcp://127.0.0.1:5558";

    [Tooltip("ZeroMQ topic to subscribe to. Leave empty to receive all messages.")]
    public string zmqTopic = "status";

    [Header("Status State")]
    [ReadOnly] public bool isConnected = false;
    [ReadOnly] public bool isArmLocked = false;
    [ReadOnly] public bool isBaseMoving = false;

    // Threading
    private Thread subThread;
    private volatile bool isRunning = false;
    private readonly object stateLock = new object();
    private bool hasChanges = false;

    // Backing states for thread-safety
    private bool tConnected = false;
    private bool tArmLocked = false;
    private bool tBaseMoving = false;

    // Tracked local states for event triggering
    private bool lastConnected = false;
    private bool lastArmLocked = false;
    private bool lastBaseMoving = false;

    // Events (fired on the main thread)
    public event Action<bool> OnConnectionStatusChanged;
    public event Action<bool> OnArmLockChanged;
    public event Action<bool> OnBaseMovingChanged;

    void Awake()
    {
        ResolveNucIP();
    }

    private void ResolveNucIP()
    {
        string ip = NetworkConfig.GetNucIP();
        if (!string.IsNullOrEmpty(ip) && !string.IsNullOrEmpty(zmqAddress))
        {
            string oldAddress = zmqAddress;
            zmqAddress = zmqAddress.Replace("127.0.0.1", ip);
            Debug.Log($"[RobotStatusSubscriber] Resolved address: {oldAddress} -> {zmqAddress}");
        }
    }

    void Start()
    {
        StartSubscriber();
    }

    public void StartSubscriber()
    {
        if (isRunning) StopSubscriber();

        isRunning = true;
        isConnected = false;
        
        subThread = new Thread(BackgroundSubscriberLoop)
        {
            IsBackground = true,
            Name = "RobotStatusSubscriberThread"
        };
        subThread.Start();
    }

    public void StopSubscriber()
    {
        isRunning = false;

        if (subThread != null && subThread.IsAlive)
        {
            subThread.Join(1000);
            if (subThread.IsAlive)
            {
                Debug.LogWarning("[RobotStatusSubscriber] Subscriber thread did not stop within 1s; it will exit after the active receive timeout.");
            }
        }
        subThread = null;

        lock (stateLock)
        {
            tConnected = false;
            tArmLocked = false;
            tBaseMoving = false;
            hasChanges = true;
        }
    }

    void Update()
    {
        bool currentConnected = false;
        bool currentArmLocked = false;
        bool currentBaseMoving = false;
        bool checkEvents = false;

        lock (stateLock)
        {
            if (hasChanges)
            {
                currentConnected = tConnected;
                currentArmLocked = tArmLocked;
                currentBaseMoving = tBaseMoving;
                checkEvents = true;
                hasChanges = false;

                // Sync public read-only properties in Inspector
                isConnected = tConnected;
                isArmLocked = tArmLocked;
                isBaseMoving = tBaseMoving;
            }
        }

        if (checkEvents)
        {
            if (currentConnected != lastConnected)
            {
                lastConnected = currentConnected;
                OnConnectionStatusChanged?.Invoke(currentConnected);
            }

            if (currentArmLocked != lastArmLocked)
            {
                lastArmLocked = currentArmLocked;
                OnArmLockChanged?.Invoke(currentArmLocked);
            }

            if (currentBaseMoving != lastBaseMoving)
            {
                lastBaseMoving = currentBaseMoving;
                OnBaseMovingChanged?.Invoke(currentBaseMoving);
            }
        }
    }

    private void BackgroundSubscriberLoop()
    {
        // Force NetMQ initialization
        AsyncIO.ForceDotNet.Force();

        while (isRunning)
        {
            try
            {
                using (var subSocket = new SubscriberSocket())
                {
                    subSocket.Connect(zmqAddress);
                    subSocket.Subscribe(zmqTopic);
                    subSocket.Options.ReceiveHighWatermark = 10;

                    Debug.Log($"Status Subscriber connected to {zmqAddress}, topic: {zmqTopic}");

                    // Connection check timestamp
                    long lastMessageTime = DateTime.UtcNow.Ticks;

                    while (isRunning)
                    {
                        string topicFrame = null;
                        string contentFrame = null;
                        bool hasMore = false;

                        // Try to receive a message (blocking with a timeout to allow exit)
                        if (subSocket.TryReceiveFrameString(TimeSpan.FromMilliseconds(500), out topicFrame, out hasMore))
                        {
                            lastMessageTime = DateTime.UtcNow.Ticks;

                            if (hasMore)
                            {
                                // Topic format: read payload frame
                                subSocket.TryReceiveFrameString(TimeSpan.FromMilliseconds(500), out contentFrame, out hasMore);
                                // Drain any extra frames
                                while (hasMore)
                                {
                                    subSocket.ReceiveFrameString(out hasMore);
                                }
                            }
                            else
                            {
                                // Single frame format: the content frame was the first one
                                contentFrame = topicFrame;
                            }

                            if (!string.IsNullOrEmpty(contentFrame))
                            {
                                ParseAndSetStatus(contentFrame);
                            }
                        }

                        // Timeout detection: if we haven't received a message in 3 seconds, mark as disconnected
                        long now = DateTime.UtcNow.Ticks;
                        if (now - lastMessageTime > TimeSpan.FromSeconds(3).Ticks)
                        {
                            lock (stateLock)
                            {
                                if (tConnected)
                                {
                                    tConnected = false;
                                    hasChanges = true;
                                }
                            }
                        }
                    }
                }
            }
            catch (Exception e)
            {
                Debug.LogWarning($"Status Subscriber connection error: {e.Message}");
                
                lock (stateLock)
                {
                    if (tConnected)
                    {
                        tConnected = false;
                        hasChanges = true;
                    }
                }

                // Wait before retrying
                Thread.Sleep(2000);
            }
        }
    }

    private void ParseAndSetStatus(string msg)
    {
        // Expecting format: "arm_locked:true;base_moving:false"
        bool newArmLocked = tArmLocked;
        bool newBaseMoving = tBaseMoving;
        bool updated = false;

        try
        {
            string[] pairs = msg.Split(';');
            foreach (string pair in pairs)
            {
                string[] kv = pair.Split(':');
                if (kv.Length == 2)
                {
                    string key = kv[0].Trim().ToLower();
                    string val = kv[1].Trim().ToLower();

                    if (key == "arm_locked")
                    {
                        newArmLocked = (val == "true" || val == "1");
                        updated = true;
                    }
                    else if (key == "base_moving")
                    {
                        newBaseMoving = (val == "true" || val == "1");
                        updated = true;
                    }
                }
            }

            if (updated)
            {
                lock (stateLock)
                {
                    tConnected = true;
                    tArmLocked = newArmLocked;
                    tBaseMoving = newBaseMoving;
                    hasChanges = true;
                }
            }
        }
        catch (Exception ex)
        {
            Debug.LogError($"Error parsing status payload '{msg}': {ex.Message}");
        }
    }

    void OnDestroy()
    {
        StopSubscriber();
    }

    void OnApplicationQuit()
    {
        StopSubscriber();
    }
}
