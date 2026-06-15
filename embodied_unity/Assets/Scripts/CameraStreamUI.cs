using UnityEngine;
using UnityEngine.UI;
using TMPro;

public class CameraStreamUI : MonoBehaviour
{
    public CameraStreamReceiver receiver;

    [Header("UI Text Controls")]
    public TMP_Text statusText;
    public TMP_Text fpsText;

    [Header("UI Input Controls")]
    public TMP_Dropdown streamTypeDropdown;
    public TMP_InputField addressInputField;
    public Button toggleConnectionButton;
    public TMP_Text buttonText;

    [Header("Network Configuration UI")]
    public TMP_InputField nucIpInputField;
    public RobotStatusSubscriber statusSubscriber;

    [Header("Visual Indicators")]
    public Image statusIndicatorLight;
    public Color connectedColor = Color.green;
    public Color connectingColor = new Color(1f, 0.75f, 0f); // Amber / Yellow
    public Color disconnectedColor = Color.red;

    void Awake()
    {
        if (receiver == null)
        {
            receiver = GetComponent<CameraStreamReceiver>();
        }
        if (statusSubscriber == null)
        {
            statusSubscriber = GetComponent<RobotStatusSubscriber>();
        }
    }

    void OnEnable()
    {
        if (receiver != null)
        {
            receiver.OnStatusChanged += HandleStatusChanged;
            receiver.OnFpsUpdated += HandleFpsUpdated;
        }

        if (toggleConnectionButton != null)
        {
            toggleConnectionButton.onClick.AddListener(OnToggleConnectionClicked);
        }

        if (streamTypeDropdown != null)
        {
            streamTypeDropdown.onValueChanged.AddListener(OnStreamTypeChanged);
        }

        if (nucIpInputField != null)
        {
            nucIpInputField.onEndEdit.AddListener(OnNucIpEndEdit);
        }

        // Initialize UI values
        InitializeUI();
    }

    void OnDisable()
    {
        if (receiver != null)
        {
            receiver.OnStatusChanged -= HandleStatusChanged;
            receiver.OnFpsUpdated -= HandleFpsUpdated;
        }

        if (toggleConnectionButton != null)
        {
            toggleConnectionButton.onClick.RemoveListener(OnToggleConnectionClicked);
        }

        if (streamTypeDropdown != null)
        {
            streamTypeDropdown.onValueChanged.RemoveListener(OnStreamTypeChanged);
        }

        if (nucIpInputField != null)
        {
            nucIpInputField.onEndEdit.RemoveListener(OnNucIpEndEdit);
        }
    }

    private void InitializeUI()
    {
        if (receiver == null) return;

        if (streamTypeDropdown != null)
        {
            streamTypeDropdown.value = (int)receiver.streamType;
        }

        if (nucIpInputField != null)
        {
            nucIpInputField.text = NetworkConfig.GetNucIP();
        }

        UpdateAddressInputText();
        HandleStatusChanged(receiver.isConnected, receiver.streamStatus);
        HandleFpsUpdated(receiver.currentFps);
    }

    private void OnStreamTypeChanged(int index)
    {
        if (receiver == null) return;

        bool wasRunning = receiver.isConnected || receiver.streamStatus == "Connecting...";
        receiver.StopStream();

        receiver.streamType = (CameraStreamReceiver.StreamType)index;
        UpdateAddressInputText();

        if (wasRunning)
        {
            receiver.StartStream();
        }
    }

    private void UpdateAddressInputText()
    {
        if (receiver == null || addressInputField == null) return;

        if (receiver.streamType == CameraStreamReceiver.StreamType.MJPEG)
        {
            addressInputField.text = receiver.mjpegUrl;
        }
        else
        {
            addressInputField.text = receiver.zmqAddress;
        }
    }

    private void OnNucIpEndEdit(string text)
    {
        string ip = text.Trim();
        if (System.Net.IPAddress.TryParse(ip, out _))
        {
            NetworkConfig.SaveNucIP(ip);
            
            if (receiver != null)
            {
                receiver.mjpegUrl = NetworkConfig.UpdateAddressIP(receiver.mjpegUrl, ip);
                receiver.zmqAddress = NetworkConfig.UpdateAddressIP(receiver.zmqAddress, ip);
                UpdateAddressInputText();
            }

            if (statusSubscriber != null)
            {
                bool wasRunning = statusSubscriber.isConnected;
                statusSubscriber.StopSubscriber();
                statusSubscriber.zmqAddress = NetworkConfig.UpdateAddressIP(statusSubscriber.zmqAddress, ip);
                if (wasRunning)
                {
                    statusSubscriber.StartSubscriber();
                }
            }
        }
    }

    private void OnToggleConnectionClicked()
    {
        if (receiver == null) return;

        bool isActive = receiver.isConnected || receiver.streamStatus == "Connecting...";
        if (isActive)
        {
            receiver.StopStream();
            if (statusSubscriber != null)
            {
                statusSubscriber.StopSubscriber();
            }
        }
        else
        {
            if (nucIpInputField != null)
            {
                string ip = nucIpInputField.text.Trim();
                if (System.Net.IPAddress.TryParse(ip, out _))
                {
                    NetworkConfig.SaveNucIP(ip);
                    
                    receiver.mjpegUrl = NetworkConfig.UpdateAddressIP(receiver.mjpegUrl, ip);
                    receiver.zmqAddress = NetworkConfig.UpdateAddressIP(receiver.zmqAddress, ip);

                    if (statusSubscriber != null)
                    {
                        statusSubscriber.StopSubscriber();
                        statusSubscriber.zmqAddress = NetworkConfig.UpdateAddressIP(statusSubscriber.zmqAddress, ip);
                    }
                }
            }

            if (addressInputField != null)
            {
                if (receiver.streamType == CameraStreamReceiver.StreamType.MJPEG)
                {
                    receiver.mjpegUrl = addressInputField.text;
                }
                else
                {
                    receiver.zmqAddress = addressInputField.text;
                }
            }

            receiver.StartStream();
            if (statusSubscriber != null)
            {
                statusSubscriber.StartSubscriber();
            }
        }
    }

    private void HandleStatusChanged(bool isConnected, string status)
    {
        if (statusText != null)
        {
            statusText.text = $"Status: {status}";
        }

        if (statusIndicatorLight != null)
        {
            if (isConnected)
            {
                statusIndicatorLight.color = connectedColor;
            }
            else if (status.Contains("Connecting"))
            {
                statusIndicatorLight.color = connectingColor;
            }
            else
            {
                statusIndicatorLight.color = disconnectedColor;
            }
        }

        if (buttonText != null)
        {
            bool isActive = isConnected || status.Contains("Connecting");
            buttonText.text = isActive ? "Disconnect" : "Connect";
        }
    }

    private void HandleFpsUpdated(float fps)
    {
        if (fpsText != null)
        {
            fpsText.text = $"FPS: {fps:F1}";
        }
    }
}
