using System.IO;
using UnityEngine;

public static class NetworkConfig
{
    private const string FileName = "nuc_ip.txt";
    private const string DefaultNucIp = "10.21.15.143";

    public static string GetNucIP()
    {
        string defaultIp = Application.isEditor ? "127.0.0.1" : DefaultNucIp;
        string path = Path.Combine(Application.persistentDataPath, FileName);

        try
        {
            if (!File.Exists(path))
            {
                File.WriteAllText(path, defaultIp);
                Debug.Log($"Created default NUC IP configuration file at: {path} with IP: {defaultIp}");
                return defaultIp;
            }

            string ip = File.ReadAllText(path).Trim();
            if (System.Net.IPAddress.TryParse(ip, out _))
            {
                return ip;
            }
            else
            {
                Debug.LogWarning($"Invalid IP address '{ip}' found in {FileName}. Falling back to default: {defaultIp}");
            }
        }
        catch (System.Exception ex)
        {
            Debug.LogWarning($"Failed to read/write NUC IP config file: {ex.Message}");
        }

        return defaultIp;
    }

    public static void SaveNucIP(string ip)
    {
        if (string.IsNullOrEmpty(ip) || !System.Net.IPAddress.TryParse(ip.Trim(), out _))
        {
            Debug.LogWarning($"Attempted to save invalid IP address: '{ip}'");
            return;
        }

        string path = Path.Combine(Application.persistentDataPath, FileName);
        try
        {
            File.WriteAllText(path, ip.Trim());
            Debug.Log($"Saved NUC IP to: {path} with IP: {ip}");
        }
        catch (System.Exception ex)
        {
            Debug.LogWarning($"Failed to save NUC IP: {ex.Message}");
        }
    }

    public static string UpdateAddressIP(string address, string newIp)
    {
        if (string.IsNullOrEmpty(address) || string.IsNullOrEmpty(newIp)) return address;

        try
        {
            int protoEnd = address.IndexOf("://");
            if (protoEnd != -1)
            {
                string proto = address.Substring(0, protoEnd + 3);
                string rest = address.Substring(protoEnd + 3);
                int colonIndex = rest.IndexOf(':');
                if (colonIndex != -1)
                {
                    string portAndPath = rest.Substring(colonIndex);
                    return proto + newIp + portAndPath;
                }
            }
        }
        catch (System.Exception ex)
        {
            Debug.LogError($"Error updating address IP for '{address}': {ex.Message}");
        }
        return address;
    }
}
