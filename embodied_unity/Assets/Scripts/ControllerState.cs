using UnityEngine;

public class ControllerState
{
    private OVRInput.Controller leftController;
    private OVRInput.Controller rightController;

    // Optional head transform, usually OVRCameraRig/TrackingSpace/CenterEyeAnchor.
    // Using the rig transform is safer than relying on a controller enum for head tracking.
    private Transform headTransform;

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

        // Head state
        if (this.headTransform != null)
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
