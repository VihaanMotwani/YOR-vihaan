using UnityEngine;

public class WorldAxes : MonoBehaviour
{
    public float axisLength = 5f;
    public float axisThickness = 0.03f;
    public Color xAxisColor = Color.red;
    public Color yAxisColor = Color.green;
    public Color zAxisColor = Color.blue;

    private GameObject xAxis;
    private GameObject yAxis;
    private GameObject zAxis;

    void Start()
    {
        // Build simple runtime line renderers so the scene origin is easy to inspect.
        xAxis = new GameObject("X Axis");
        xAxis.transform.SetParent(transform);
        xAxis.transform.localPosition = Vector3.zero;
        xAxis.AddComponent<LineRenderer>();
        LineRenderer xLineRenderer = xAxis.GetComponent<LineRenderer>();
        xLineRenderer.startColor = xAxisColor;
        xLineRenderer.endColor = xAxisColor;
        xLineRenderer.startWidth = axisThickness;
        xLineRenderer.endWidth = axisThickness;
        xLineRenderer.SetPositions(new Vector3[] {
            Vector3.zero,
            Vector3.right * axisLength
        });

        yAxis = new GameObject("Y Axis");
        yAxis.transform.SetParent(transform);
        yAxis.transform.localPosition = Vector3.zero;
        yAxis.AddComponent<LineRenderer>();
        LineRenderer yLineRenderer = yAxis.GetComponent<LineRenderer>();
        yLineRenderer.startColor = yAxisColor;
        yLineRenderer.endColor = yAxisColor;
        yLineRenderer.startWidth = axisThickness;
        yLineRenderer.endWidth = axisThickness;
        yLineRenderer.SetPositions(new Vector3[] {
            Vector3.zero,
            Vector3.up * axisLength
        });

        zAxis = new GameObject("Z Axis");
        zAxis.transform.SetParent(transform);
        zAxis.transform.localPosition = Vector3.zero;
        zAxis.AddComponent<LineRenderer>();
        LineRenderer zLineRenderer = zAxis.GetComponent<LineRenderer>();
        zLineRenderer.startColor = zAxisColor;
        zLineRenderer.endColor = zAxisColor;
        zLineRenderer.startWidth = axisThickness;
        zLineRenderer.endWidth = axisThickness;
        zLineRenderer.SetPositions(new Vector3[] {
            Vector3.zero,
            Vector3.forward * axisLength
        });
    }
}
