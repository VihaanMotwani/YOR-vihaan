using UnityEditor;
using UnityEditor.XR.Management;
using UnityEditor.XR.Management.Metadata;
using UnityEngine;
using Unity.XR.Oculus;
using UnityEngine.XR.Management;

public static class YorConfigureAndroidOculusXR
{
    private const BuildTargetGroup TargetGroup = BuildTargetGroup.Android;
    private const string LoaderTypeName = "Unity.XR.Oculus.OculusLoader";
    private const string OculusSettingsKey = "Unity.XR.Oculus.Settings";
    private const string OculusSettingsPath = "Assets/XR/Settings/OculusSettings.asset";

    [InitializeOnLoadMethod]
    private static void ConfigureOnEditorLoad()
    {
        ConfigureAndroidOculus();
    }

    [MenuItem("YOR/Configure Android Oculus XR")]
    public static void ConfigureAndroidOculus()
    {
        if (EditorApplication.isPlayingOrWillChangePlaymode)
        {
            return;
        }

        var settingsPerBuildTarget = GetOrCreateSettingsPerBuildTarget();
        if (!settingsPerBuildTarget.HasManagerSettingsForBuildTarget(TargetGroup))
        {
            settingsPerBuildTarget.CreateDefaultManagerSettingsForBuildTarget(TargetGroup);
        }

        var generalSettings = settingsPerBuildTarget.SettingsForBuildTarget(TargetGroup);
        generalSettings.InitManagerOnStart = true;

        var managerSettings = settingsPerBuildTarget.ManagerSettingsForBuildTarget(TargetGroup);
        managerSettings.automaticLoading = true;
        managerSettings.automaticRunning = true;

        var oculusSettings = GetOrCreateOculusSettings();
        oculusSettings.TargetQuest2 = true;
        oculusSettings.TargetQuest3 = true;
        EditorBuildSettings.AddConfigObject(OculusSettingsKey, oculusSettings, true);

        var assigned = XRPackageMetadataStore.AssignLoader(managerSettings, LoaderTypeName, TargetGroup);
        EditorUtility.SetDirty(oculusSettings);
        EditorUtility.SetDirty(generalSettings);
        EditorUtility.SetDirty(managerSettings);
        EditorUtility.SetDirty(settingsPerBuildTarget);
        AssetDatabase.SaveAssets();

        Debug.Log($"[YOR] Android Oculus XR configured. Loader assigned: {assigned}");
    }

    private static XRGeneralSettingsPerBuildTarget GetOrCreateSettingsPerBuildTarget()
    {
        var settingsKey = XRGeneralSettings.k_SettingsKey;
        if (EditorBuildSettings.TryGetConfigObject<XRGeneralSettingsPerBuildTarget>(
                settingsKey,
                out var settingsPerBuildTarget) &&
            settingsPerBuildTarget != null)
        {
            return settingsPerBuildTarget;
        }

        settingsPerBuildTarget = ScriptableObject.CreateInstance<XRGeneralSettingsPerBuildTarget>();
        if (!AssetDatabase.IsValidFolder("Assets/XR"))
        {
            AssetDatabase.CreateFolder("Assets", "XR");
        }

        const string assetPath = "Assets/XR/XRGeneralSettingsPerBuildTarget.asset";
        AssetDatabase.CreateAsset(settingsPerBuildTarget, assetPath);
        EditorBuildSettings.AddConfigObject(settingsKey, settingsPerBuildTarget, true);
        AssetDatabase.SaveAssets();

        return settingsPerBuildTarget;
    }

    private static OculusSettings GetOrCreateOculusSettings()
    {
        if (EditorBuildSettings.TryGetConfigObject<OculusSettings>(OculusSettingsKey, out var oculusSettings) &&
            oculusSettings != null)
        {
            return oculusSettings;
        }

        oculusSettings = AssetDatabase.LoadAssetAtPath<OculusSettings>(OculusSettingsPath);
        if (oculusSettings != null)
        {
            return oculusSettings;
        }

        if (!AssetDatabase.IsValidFolder("Assets/XR"))
        {
            AssetDatabase.CreateFolder("Assets", "XR");
        }

        if (!AssetDatabase.IsValidFolder("Assets/XR/Settings"))
        {
            AssetDatabase.CreateFolder("Assets/XR", "Settings");
        }

        oculusSettings = ScriptableObject.CreateInstance<OculusSettings>();
        oculusSettings.name = "OculusSettings";
        AssetDatabase.CreateAsset(oculusSettings, OculusSettingsPath);
        AssetDatabase.SaveAssets();

        return oculusSettings;
    }
}
