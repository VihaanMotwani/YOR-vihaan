using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

public static class YorConfigureHeadTracking
{
    private const string ScenePath = "Assets/Scenes/SampleScene.unity";
    private const string TrackingPublisherName = "TrackingPublisher";

    [InitializeOnLoadMethod]
    private static void ConfigureOnEditorLoad()
    {
        EditorApplication.delayCall -= EnsureTrackingPublisher;
        EditorApplication.delayCall += EnsureTrackingPublisher;
    }

    [MenuItem("YOR/Configure Head Tracking Publisher")]
    public static void EnsureTrackingPublisher()
    {
        if (EditorApplication.isPlayingOrWillChangePlaymode)
        {
            return;
        }

        Scene scene = SceneManager.GetActiveScene();
        if (scene.path != ScenePath)
        {
            scene = EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
        }

        GameObject publisherObject = GameObject.Find(TrackingPublisherName);
        if (publisherObject == null)
        {
            publisherObject = new GameObject(TrackingPublisherName);
        }

        ControllerTracking tracking = publisherObject.GetComponent<ControllerTracking>();
        if (tracking == null)
        {
            tracking = publisherObject.AddComponent<ControllerTracking>();
        }

        tracking.tcpAddress = "tcp://*:5555";
        tracking.topic = "oculus_controller";
        tracking.logEveryFrame = false;

        Camera mainCamera = Camera.main;
        if (mainCamera != null)
        {
            tracking.centerEyeAnchor = mainCamera.transform;
        }

        EditorUtility.SetDirty(tracking);
        EditorUtility.SetDirty(publisherObject);
        EditorSceneManager.MarkSceneDirty(scene);
        EditorSceneManager.SaveScene(scene);
        Debug.Log("[YOR] Head tracking publisher configured in SampleScene.");
    }
}
