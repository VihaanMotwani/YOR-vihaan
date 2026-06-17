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
    public bool logEveryFrame = false;

    // Publishes the latest controller/head snapshot for any external subscriber.
    private PublisherSocket publisher;
    private bool updateErrorLogged = false;

    void Start()
    {
        try
        {
            Logger.Log("Init libs");
            ForceDotNet.Force();

            TryAutoAssignHeadAnchor();

            controllerState = new ControllerState(leftController, rightController, centerEyeAnchor);

            Logger.Log("Create publisher");
            publisher = new PublisherSocket();
            publisher.Bind(tcpAddress);
            Logger.Log("Head tracking publisher listening on " + tcpAddress + " topic " + topic);
        }
        catch (System.Exception e)
        {
            Debug.LogError("[YOR] ControllerTracking startup failed: " + e);
            Logger.Log("ControllerTracking startup failed: " + e.Message);
            publisher?.Dispose();
            publisher = null;
        }
    }

    void Update()
    {
        if (controllerState == null || publisher == null)
        {
            return;
        }

        try
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
        catch (System.Exception e)
        {
            if (!updateErrorLogged)
            {
                updateErrorLogged = true;
                Debug.LogError("[YOR] ControllerTracking update failed: " + e);
                Logger.Log("ControllerTracking update failed: " + e.Message);
            }
        }
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
            return;
        }

        Camera mainCamera = Camera.main;
        if (mainCamera != null)
        {
            centerEyeAnchor = mainCamera.transform;
            Logger.Log("Assigned head anchor from Camera.main");
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
