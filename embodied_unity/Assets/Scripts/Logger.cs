using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

class Logger
{
    private static Text Text;
    private static List<string> Logs = new List<string>();
    public static int LogLimit = 5;

    static Logger()
    {
        // Attach the debug canvas to the VR camera rig so logs stay in view in-headset.
        OVRCameraRig OVRCamera = GameObject.FindObjectOfType<OVRCameraRig>();

        GameObject goCanvas = new GameObject("Canvas");
        goCanvas.transform.parent = OVRCamera.gameObject.transform;
        goCanvas.transform.position = new Vector3(0, -6, 0);
        Canvas canvas = goCanvas.AddComponent<Canvas>();
        canvas.renderMode = RenderMode.WorldSpace;

        GameObject goText = new GameObject("Text");
        goText.transform.parent = goCanvas.transform;
        goText.transform.position = new Vector3(0, 0, 10);
        goText.transform.rotation = new Quaternion(0, 0, 0, 0);

        Text = goText.AddComponent<Text>();
        Text.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
        Text.fontSize = 30;
        Text.color = Color.red;

        RectTransform tr = goText.GetComponent<RectTransform>();
        tr.localScale = new Vector3(0.01f, 0.01f, 0.01f);
        tr.sizeDelta = new Vector2(1000, 1000);
    }

    private static void PrintLogs()
    {
        // Rebuild the visible log text from the rolling buffer.
        string StringToLog = "";
        foreach (string item in Logs)
            StringToLog += item + "\n";

        Text.text = StringToLog;
    }

    public static void Log(string log)
    {
        string StringToLog = log.ToString();
        Logs.Add(StringToLog);

        // Keep the overlay readable by capping the number of displayed entries.
        if (Logs.Count > LogLimit)
            Logs.RemoveAt(0);

        PrintLogs();
    }
}

