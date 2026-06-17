using UnityEngine;
using UnityEngine.XR;

public class ControllerState
{
    private OVRInput.Controller leftController;
    private OVRInput.Controller rightController;

    // Optional head transform, usually OVRCameraRig/TrackingSpace/CenterEyeAnchor.
    // Using the rig transform is safer than relying on a controller enum for head tracking.
    private Transform headTransform;
    private InputDevice headDevice;
    private InputDevice leftHandDevice;
    private InputDevice rightHandDevice;

    public bool leftX;
    public bool leftY;
    public bool leftMenu;
    public bool leftThumbstick;
    public float leftIndexTrigger;
    public float leftHandTrigger;
    public Vector2 leftThumbstickAxes;
    public Vector3 leftLocalPosition;
    public Quaternion leftLocalRotation;

    public bool rightA;
    public bool rightB;
    public bool rightMenu;
    public bool rightThumbstick;
    public float rightIndexTrigger;
    public float rightHandTrigger;
    public Vector2 rightThumbstickAxes;
    public Vector3 rightLocalPosition;
    public Quaternion rightLocalRotation;

    // Head pose from the CenterEyeAnchor.
    // Local pose is relative to the OVRCameraRig parent/tracking space.
    // World pose is useful if your robot-side consumer wants Unity scene coordinates.
    public Vector3 headLocalPosition;
    public Quaternion headLocalRotation;
    public Vector3 headWorldPosition;
    public Quaternion headWorldRotation;

    public ControllerState(
        OVRInput.Controller leftController,
        OVRInput.Controller rightController,
        Transform headTransform = null)
    {
        this.leftController = leftController;
        this.rightController = rightController;
        this.headTransform = headTransform;
    }

    public void SetHeadTransform(Transform headTransform)
    {
        this.headTransform = headTransform;
    }

    public void UpdateState()
    {
        // Left controller state
        this.leftX = OVRInput.Get(OVRInput.RawButton.X, this.leftController);
        this.leftY = OVRInput.Get(OVRInput.RawButton.Y, this.leftController);
        this.leftMenu = OVRInput.Get(OVRInput.RawButton.Start, this.leftController);
        this.leftThumbstick = OVRInput.Get(OVRInput.RawButton.LThumbstick, this.leftController);
        this.leftIndexTrigger = OVRInput.Get(OVRInput.RawAxis1D.LIndexTrigger, this.leftController);
        this.leftHandTrigger = OVRInput.Get(OVRInput.RawAxis1D.LHandTrigger, this.leftController);
        this.leftThumbstickAxes = OVRInput.Get(OVRInput.RawAxis2D.LThumbstick, this.leftController);
        this.leftLocalPosition = OVRInput.GetLocalControllerPosition(this.leftController);
        this.leftLocalRotation = OVRInput.GetLocalControllerRotation(this.leftController);
        UpdateControllerFromXr(
            XRNode.LeftHand,
            ref leftHandDevice,
            ref leftX,
            ref leftY,
            ref leftMenu,
            ref leftThumbstick,
            ref leftIndexTrigger,
            ref leftHandTrigger,
            ref leftThumbstickAxes,
            ref leftLocalPosition,
            ref leftLocalRotation);

        // Right controller state
        this.rightA = OVRInput.Get(OVRInput.RawButton.A, this.rightController);
        this.rightB = OVRInput.Get(OVRInput.RawButton.B, this.rightController);
        this.rightMenu = OVRInput.Get(OVRInput.RawButton.Start, this.rightController);
        this.rightThumbstick = OVRInput.Get(OVRInput.RawButton.RThumbstick, this.rightController);
        this.rightIndexTrigger = OVRInput.Get(OVRInput.RawAxis1D.RIndexTrigger, this.rightController);
        this.rightHandTrigger = OVRInput.Get(OVRInput.RawAxis1D.RHandTrigger, this.rightController);
        this.rightThumbstickAxes = OVRInput.Get(OVRInput.RawAxis2D.RThumbstick, this.rightController);
        this.rightLocalPosition = OVRInput.GetLocalControllerPosition(this.rightController);
        this.rightLocalRotation = OVRInput.GetLocalControllerRotation(this.rightController);
        UpdateControllerFromXr(
            XRNode.RightHand,
            ref rightHandDevice,
            ref rightA,
            ref rightB,
            ref rightMenu,
            ref rightThumbstick,
            ref rightIndexTrigger,
            ref rightHandTrigger,
            ref rightThumbstickAxes,
            ref rightLocalPosition,
            ref rightLocalRotation);

        // Head state. Prefer the XR runtime pose because a plain Main Camera
        // transform can stay static even while the headset is moving.
        if (TryGetXrHeadPose(out Vector3 xrHeadPosition, out Quaternion xrHeadRotation))
        {
            this.headLocalPosition = xrHeadPosition;
            this.headLocalRotation = xrHeadRotation;

            if (this.headTransform != null && this.headTransform.parent != null)
            {
                this.headWorldPosition = this.headTransform.parent.TransformPoint(xrHeadPosition);
                this.headWorldRotation = this.headTransform.parent.rotation * xrHeadRotation;
            }
            else
            {
                this.headWorldPosition = xrHeadPosition;
                this.headWorldRotation = xrHeadRotation;
            }
        }
        else if (this.headTransform != null)
        {
            this.headLocalPosition = this.headTransform.localPosition;
            this.headLocalRotation = this.headTransform.localRotation;
            this.headWorldPosition = this.headTransform.position;
            this.headWorldRotation = this.headTransform.rotation;
        }
        else
        {
            this.headLocalPosition = Vector3.zero;
            this.headLocalRotation = Quaternion.identity;
            this.headWorldPosition = Vector3.zero;
            this.headWorldRotation = Quaternion.identity;
        }
    }

    private void UpdateControllerFromXr(
        XRNode node,
        ref InputDevice device,
        ref bool primaryButton,
        ref bool secondaryButton,
        ref bool menuButton,
        ref bool thumbstickButton,
        ref float indexTrigger,
        ref float handTrigger,
        ref Vector2 thumbstickAxes,
        ref Vector3 localPosition,
        ref Quaternion localRotation)
    {
        if (!device.isValid)
        {
            device = InputDevices.GetDeviceAtXRNode(node);
        }

        if (!device.isValid)
        {
            return;
        }

        if (device.TryGetFeatureValue(CommonUsages.primaryButton, out bool xrPrimaryButton))
        {
            primaryButton = xrPrimaryButton;
        }

        if (device.TryGetFeatureValue(CommonUsages.secondaryButton, out bool xrSecondaryButton))
        {
            secondaryButton = xrSecondaryButton;
        }

        if (device.TryGetFeatureValue(CommonUsages.menuButton, out bool xrMenuButton))
        {
            menuButton = xrMenuButton;
        }

        if (device.TryGetFeatureValue(CommonUsages.primary2DAxisClick, out bool xrThumbstickButton))
        {
            thumbstickButton = xrThumbstickButton;
        }

        if (device.TryGetFeatureValue(CommonUsages.trigger, out float xrIndexTrigger))
        {
            indexTrigger = xrIndexTrigger;
        }
        else if (device.TryGetFeatureValue(CommonUsages.triggerButton, out bool xrIndexTriggerButton))
        {
            indexTrigger = xrIndexTriggerButton ? 1.0f : 0.0f;
        }

        if (device.TryGetFeatureValue(CommonUsages.grip, out float xrHandTrigger))
        {
            handTrigger = xrHandTrigger;
        }
        else if (device.TryGetFeatureValue(CommonUsages.gripButton, out bool xrHandTriggerButton))
        {
            handTrigger = xrHandTriggerButton ? 1.0f : 0.0f;
        }

        if (device.TryGetFeatureValue(CommonUsages.primary2DAxis, out Vector2 xrThumbstickAxes))
        {
            thumbstickAxes = xrThumbstickAxes;
        }

        if (device.TryGetFeatureValue(CommonUsages.devicePosition, out Vector3 xrLocalPosition))
        {
            localPosition = xrLocalPosition;
        }

        if (device.TryGetFeatureValue(CommonUsages.deviceRotation, out Quaternion xrLocalRotation))
        {
            localRotation = xrLocalRotation;
        }
    }

    private bool TryGetXrHeadPose(out Vector3 localPosition, out Quaternion localRotation)
    {
        if (!headDevice.isValid)
        {
            headDevice = InputDevices.GetDeviceAtXRNode(XRNode.Head);
        }

        localPosition = Vector3.zero;
        localRotation = Quaternion.identity;

        if (!headDevice.isValid)
        {
            return false;
        }

        bool hasPosition =
            headDevice.TryGetFeatureValue(CommonUsages.centerEyePosition, out localPosition) ||
            headDevice.TryGetFeatureValue(CommonUsages.devicePosition, out localPosition);

        bool hasRotation =
            headDevice.TryGetFeatureValue(CommonUsages.centerEyeRotation, out localRotation) ||
            headDevice.TryGetFeatureValue(CommonUsages.deviceRotation, out localRotation);

        if (!hasPosition)
        {
            localPosition = Vector3.zero;
        }

        if (!hasRotation)
        {
            localRotation = Quaternion.identity;
        }

        return hasPosition || hasRotation;
    }

    public override string ToString()
    {
        // The message uses semicolon-delimited fields for the current external consumer.
        return $"Head:;" +
               $"  Head Local Position: {Vector3ToString(headLocalPosition)};" +
               $"  Head Local Rotation: {QuaternionToString(headLocalRotation)};" +
               $"  Head World Position: {Vector3ToString(headWorldPosition)};" +
               $"  Head World Rotation: {QuaternionToString(headWorldRotation)};" +
               $"|Left Controller:;" +
               $"  Left X: {leftX};" +
               $"  Left Y: {leftY};" +
               $"  Left Menu: {leftMenu};" +
               $"  Left Thumbstick: {leftThumbstick};" +
               $"  Left Index Trigger: {leftIndexTrigger};" +
               $"  Left Hand Trigger: {leftHandTrigger};" +
               $"  Left Thumbstick Axes: {Vector2ToString(leftThumbstickAxes)};" +
               $"  Left Local Position: {Vector3ToString(leftLocalPosition)};" +
               $"  Left Local Rotation: {QuaternionToString(leftLocalRotation)};" +
               $"|Right Controller:;" +
               $"  Right A: {rightA};" +
               $"  Right B: {rightB};" +
               $"  Right Menu: {rightMenu};" +
               $"  Right Thumbstick: {rightThumbstick};" +
               $"  Right Index Trigger: {rightIndexTrigger};" +
               $"  Right Hand Trigger: {rightHandTrigger};" +
               $"  Right Thumbstick Axes: {Vector2ToString(rightThumbstickAxes)};" +
               $"  Right Local Position: {Vector3ToString(rightLocalPosition)};" +
               $"  Right Local Rotation: {QuaternionToString(rightLocalRotation)};";
    }

    public static string Vector2ToString(Vector2 vector)
    {
        return $"{vector.x},{vector.y}";
    }

    public static string Vector3ToString(Vector3 vector)
    {
        return $"{vector.x},{vector.y},{vector.z}";
    }

    public static string QuaternionToString(Quaternion quaternion)
    {
        return $"{quaternion.x},{quaternion.y},{quaternion.z},{quaternion.w}";
    }
}
