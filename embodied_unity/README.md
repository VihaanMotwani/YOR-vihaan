# xarm-vr

## Unity Environment Setup

### Recommended Unity Version

- Unity 2022.3 LTS
- Android Build Support installed through Unity Hub
  - Android SDK & NDK Tools
  - OpenJDK

### Required Unity Packages

The project uses the following Unity XR packages:

- `com.unity.xr.management`
- `com.unity.xr.oculus`

The project also requires the Meta XR SDK / Oculus Integration layer in order to provide:

- `OVRInput`
- `OVRCameraRig`
- `OVRManager`

These are required by:

- `ControllerTracking.cs`
- `ControllerState.cs`

### Recommended Meta XR Setup
https://developers.meta.com/horizon/downloads/package/meta-xr-core-sdk/

After importing the Meta XR SDK:

1. Open:

   ```text
   Meta → Tools → Project Setup Tool
   ```

2. Run:
   - `Fix All` for required items
   - `Apply All` for recommended Android settings

### Recommended Build Settings

#### Platform

```text
Android
```

#### Player Settings

```text
Scripting Backend: IL2CPP
Target Architecture: ARM64
Color Space: Linear
Graphics API: Vulkan
```

#### XR Plug-in Management

Enable for Android:

- Oculus / Meta XR

### Recommended Scene Setup

The scene should minimally contain:

```text
Scene
 ├── OVRCameraRig
 ├── ControllerTrackingManager
 ├── Directional Light (optional)
 ├── Plane (optional)
 └── WorldAxes (optional)
```

### Required Tracking References

`ControllerTracking.cs` should reference the following transforms from the `OVRCameraRig`:

```text
OVRCameraRig
 └── TrackingSpace
      ├── CenterEyeAnchor
      ├── LeftHandAnchor
      └── RightHandAnchor
```

These are used for:

- Head tracking
- Left controller tracking
- Right controller tracking

### Networking Dependencies

The project currently uses ZeroMQ networking through plugin DLLs located in:

```text
Assets/Plugins/
```

Required DLLs:

- `NetMQ.dll`
- `AsyncIO.dll`
- `NaCl.dll`

If networking compile errors occur, verify these DLLs exist inside `Assets/Plugins`.

### Git Recommendations

Unity-generated folders should NOT be committed to Git.

Recommended `.gitignore` exclusions include:

```gitignore
[Ll]ibrary/
[Tt]emp/
[Ll]ogs/
[Uu]ser[Ss]ettings/
[Bb]uild/
[Bb]uilds/
```

## Project Overview

This Unity project streams Oculus controller and head pose from a VR scene over ZeroMQ, receives a robot camera stream, and displays basic robot status. The core custom logic lives in `Assets/Scripts`, while most of the remaining project content is imported Unity, Oculus, TextMesh Pro, and plugin/package content.

## Main Custom Scripts

- `Assets/Scripts/ControllerTracking.cs`
  Reads Oculus controller and `CenterEyeAnchor` head pose input each frame, formats the state, and publishes it over a ZeroMQ publisher socket.

- `Assets/Scripts/ControllerState.cs`
  Stores the current head, left controller, and right controller state and converts that state into a serialized string.

- `Assets/Scripts/CameraStreamReceiver.cs`
  Receives MJPEG or ZeroMQ JPEG camera frames and applies them to a `Renderer` or `RawImage`.

- `Assets/Scripts/CameraStreamUI.cs`
  Connects stream settings, NUC IP configuration, status text, FPS text, and connect/disconnect controls to the camera receiver.

- `Assets/Scripts/RobotStatusSubscriber.cs`
  Subscribes to a simple ZeroMQ status stream from the robot.

- `Assets/Scripts/RobotStatusUI.cs`
  Displays robot arm-lock and base-motion status indicators.

- `Assets/Scripts/WorldAxes.cs`
  Draws runtime X/Y/Z axes in the scene for orientation and debugging.

- `Assets/Scripts/Logger.cs`
  Builds a world-space UI text logger at runtime and is currently used by `ControllerTracking`.

## Scene Setup

The main scene in this shared project is `Assets/Scenes/SampleScene.unity`.

This scene currently includes:

- An imported `OVRCameraRig` prefab
- Imported Oculus controller prefabs
- The custom `ControllerTracking` component
- The custom `WorldAxes` component

## Dependencies

The project uses Unity packages defined in `Packages/manifest.json`, including:

- `com.unity.xr.management`
- `com.unity.xr.oculus`
- `com.unity.textmeshpro`
- `com.unity.ugui`

The project also includes plugin DLLs in `Assets/Plugins` for:

- `NetMQ`
- `AsyncIO`
- `NaCl`
- `websocket-sharp`

## Robot Integration

Expected network flow:

```text
Quest/Unity app --tcp://*:5555, topic oculus_controller--> robot teleop script
robot zed_pub_node.py --tcp://*:6000, topic zed/image--> robot/unity_stream_bridge.py
robot/unity_stream_bridge.py --tcp://*:5556, topic camera--> Quest/Unity app
robot/unity_stream_bridge.py --tcp://*:5558, topic status--> Quest/Unity app
```

On the robot/NUC or Jetson camera host:

```bash
python robot/zed_image_publisher.py --resolution HD720 --fps 60
python robot/unity_stream_bridge.py --zed-host 127.0.0.1 --bind-host 0.0.0.0 --max-fps 60 --jpeg-quality 75
```

In the Unity app, set the NUC IP field to the robot/NUC IP. The default stream settings are:

```text
Camera ZeroMQ address: tcp://<nuc-ip>:5556
Camera topic: camera
Status ZeroMQ address: tcp://<nuc-ip>:5558
Status topic: status
```

For the YOR Jetson/Thor test setup, the working path is:

```text
ZED 2i -> robot/zed_image_publisher.py, tcp://*:6000, topic zed/image
robot/unity_stream_bridge.py -> tcp://*:5556 camera + tcp://*:5558 status
Unity/Quest -> tcp://<jetson-ip>:5556 and tcp://<jetson-ip>:5558
```

The same Unity publisher sends both controller state and head pose on `tcp://*:5555`, topic `oculus_controller`. On the robot, use the existing Oculus teleop scripts; head yaw can be added to base yaw in whole-body teleop with:

```bash
python robot/teleop/oculus_bimanual_wholebody_teleop.py --quest_host <quest-ip> --head_base_control
```

If the stream is laggy, restart only the bridge with lower JPEG quality:

```bash
python robot/unity_stream_bridge.py --zed-host 127.0.0.1 --bind-host 0.0.0.0 --max-fps 60 --jpeg-quality 60
```

If the ZED rejects `HD720/60` or the network drops too many frames, restart the publisher with:

```bash
python robot/zed_image_publisher.py --resolution VGA --fps 60
```
