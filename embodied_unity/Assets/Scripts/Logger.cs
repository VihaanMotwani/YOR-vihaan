using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

class Logger
{
    private static Text Text;
    private static List<string> Logs = new List<string>();
    private static bool overlayInitialized = false;
    public static int LogLimit = 5;

    private static void EnsureOverlay()
    {
        if (overlayInitialized)
        {
            return;
        }

        overlayInitialized = true;

        try
        {
            // Attach the debug canvas to the VR rig when present, otherwise to
            // the active XR camera. Some test scenes only have Main Camera.
            Transform parent = null;
            OVRCameraRig ovrCamera = GameObject.FindObjectOfType<OVRCameraRig>();
            if (ovrCamera != null)
            {
                parent = ovrCamera.transform;
            }
            else if (Camera.main != null)
            {
                parent = Camera.main.transform;
            }

            if (parent == null)
            {
                Debug.LogWarning("[YOR] Logger overlay disabled: no OVRCameraRig or Main Camera found.");
                return;
            }

            GameObject goCanvas = new GameObject("Canvas");
            goCanvas.transform.SetParent(parent, false);
            goCanvas.transform.localPosition = new Vector3(0, -0.35f, 1.5f);
            Canvas canvas = goCanvas.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.WorldSpace;

            GameObject goText = new GameObject("Text");
            goText.transform.SetParent(goCanvas.transform, false);
            goText.transform.localPosition = Vector3.zero;
            goText.transform.localRotation = Quaternion.identity;

            Text = goText.AddComponent<Text>();
            Text.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
            Text.fontSize = 30;
            Text.color = Color.red;

            RectTransform tr = goText.GetComponent<RectTransform>();
            tr.localScale = new Vector3(0.01f, 0.01f, 0.01f);
            tr.sizeDelta = new Vector2(1000, 1000);
        }
        catch (System.Exception e)
        {
            Debug.LogWarning("[YOR] Logger overlay disabled: " + e.Message);
        }
    }

    private static void PrintLogs()
    {
        if (Text == null)
        {
            return;
        }

        // Rebuild the visible log text from the rolling buffer.
        string StringToLog = "";
        foreach (string item in Logs)
            StringToLog += item + "\n";

        Text.text = StringToLog;
    }

    public static void Log(string log)
    {
        string StringToLog = log.ToString();
        Debug.Log("[YOR] " + StringToLog);

        EnsureOverlay();

        Logs.Add(StringToLog);

        // Keep the overlay readable by capping the number of displayed entries.
        if (Logs.Count > LogLimit)
            Logs.RemoveAt(0);

        PrintLogs();
    }
}
