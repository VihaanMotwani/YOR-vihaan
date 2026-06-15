using UnityEngine;
using NetMQ;
using AsyncIO;
using NetMQ.Sockets;

public class ControllerTracking : MonoBehaviour
{
    private OVRInput.Controller leftController = OVRInput.Controller.LTouch;
    private OVRInput.Controller rightController = OVRInput.Controller.RTouch;
    private ControllerState controllerState;

    [Header("OVR Rig References")]
    [Tooltip("Assign OVRCameraRig/TrackingSpace/CenterEyeAnchor here. If left empty, the script will try to find the OVRCameraRig automatically.")]
    public Transform centerEyeAnchor;

    [Header("Networking")]
    [Tooltip("Address used by the NetMQ publisher.")]
    public string tcpAddress = "tcp://*:5555";

    [Tooltip("Topic name used by downstream subscribers.")]
    public string topic = "oculus_controller";

    [Header("Debug")]
    [Tooltip("If true, prints the full state to the in-headset/debug logger every frame.")]
    public bool logEveryFrame = true;

    // Publishes the latest controller/head snapshot for any external subscriber.
    private PublisherSocket publisher;

    void Start()
    {
        Logger.Log("Init libs");
        ForceDotNet.Force();

        TryAutoAssignHeadAnchor();

        controllerState = new ControllerState(leftController, rightController, centerEyeAnchor);

        Logger.Log("Create publisher");
        publisher = new PublisherSocket();
        publisher.Bind(tcpAddress);
    }

    void Update()
    {
        controllerState.UpdateState();
        string state = controllerState.ToString();

        if (logEveryFrame)
        {
            Logger.Log(state);
        }

        // Publish on a named topic so downstream tools can filter messages.
        publisher.SendMoreFrame(topic).SendFrame(state);
    }

    private void TryAutoAssignHeadAnchor()
    {
        if (centerEyeAnchor != null)
        {
            return;
        }

        OVRCameraRig rig = FindObjectOfType<OVRCameraRig>();
        if (rig != null && rig.centerEyeAnchor != null)
        {
            centerEyeAnchor = rig.centerEyeAnchor;
            Logger.Log("Assigned CenterEyeAnchor from OVRCameraRig");
        }
        else
        {
            Logger.Log("Warning: CenterEyeAnchor not assigned. Head pose will be zero/identity.");
        }
    }

    void OnDestroy()
    {
        publisher?.Dispose();
        publisher = null;
    }

    void OnApplicationQuit()
    {
        publisher?.Dispose();
        publisher = null;
        NetMQConfig.Cleanup();
    }
}
