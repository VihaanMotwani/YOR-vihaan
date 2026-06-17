using UnityEngine;
using UnityEngine.UI;
using TMPro;

public class RobotStatusUI : MonoBehaviour
{
    public RobotStatusSubscriber subscriber;

    [Header("Arm Lock UI")]
    public Image armLockLight;
    public TMP_Text armLockText;
    public Color armLockedColor = Color.green;      // Safe to rest / locked
    public Color armUnlockedColor = Color.red;      // Active / unlocked
    public Color unknownColor = Color.gray;

    [Header("Base Movement UI")]
    public Image baseMovingLight;
    public TMP_Text baseMovingText;
    public Color baseMovingColor = new Color(1f, 0.5f, 0f); // Orange warning light
    public Color baseIdleColor = Color.gray;

    void Awake()
    {
        if (subscriber == null)
        {
            subscriber = GetComponent<RobotStatusSubscriber>();
        }
    }

    void OnEnable()
    {
        if (subscriber != null)
        {
            subscriber.OnConnectionStatusChanged += HandleConnectionStatusChanged;
            subscriber.OnArmLockChanged += HandleArmLockChanged;
            subscriber.OnBaseMovingChanged += HandleBaseMovingChanged;

            // Trigger initial UI setup
            UpdateUI(subscriber.isConnected, subscriber.isArmLocked, subscriber.isBaseMoving);
        }
    }

    void OnDisable()
    {
        if (subscriber != null)
        {
            subscriber.OnConnectionStatusChanged -= HandleConnectionStatusChanged;
            subscriber.OnArmLockChanged -= HandleArmLockChanged;
            subscriber.OnBaseMovingChanged -= HandleBaseMovingChanged;
        }
    }

    private void HandleConnectionStatusChanged(bool isConnected)
    {
        if (isConnected)
        {
            UpdateUI(true, subscriber.isArmLocked, subscriber.isBaseMoving);
        }
        else
        {
            // Set lights to gray if ZMQ connection to robot is lost
            UpdateUI(false, false, false);
        }
    }

    private void HandleArmLockChanged(bool isLocked)
    {
        if (subscriber.isConnected)
        {
            UpdateArmLockUI(true, isLocked);
        }
    }

    private void HandleBaseMovingChanged(bool isMoving)
    {
        if (subscriber.isConnected)
        {
            UpdateBaseMovingUI(true, isMoving);
        }
    }

    private void UpdateUI(bool isConnected, bool isLocked, bool isMoving)
    {
        UpdateArmLockUI(isConnected, isLocked);
        UpdateBaseMovingUI(isConnected, isMoving);
    }

    private void UpdateArmLockUI(bool isConnected, bool isLocked)
    {
        if (armLockLight != null)
        {
            armLockLight.color = isConnected ? (isLocked ? armLockedColor : armUnlockedColor) : unknownColor;
        }

        if (armLockText != null)
        {
            armLockText.text = isConnected ? (isLocked ? "Arm: LOCKED" : "Arm: UNLOCKED") : "Arm: OFF/UNKNOWN";
        }
    }

    private void UpdateBaseMovingUI(bool isConnected, bool isMoving)
    {
        if (baseMovingLight != null)
        {
            baseMovingLight.color = isConnected ? (isMoving ? baseMovingColor : baseIdleColor) : unknownColor;
        }

        if (baseMovingText != null)
        {
            baseMovingText.text = isConnected ? (isMoving ? "Base: MOVING" : "Base: IDLE") : "Base: OFF/UNKNOWN";
        }
    }
}
