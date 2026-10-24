using System.IO;
namespace FiveMCleaner;
public static class PathPolicy
{
    public static bool Within(string path, string root) =>
        System.IO.Path.GetFullPath(path).TrimEnd(System.IO.Path.DirectorySeparatorChar).StartsWith(
            System.IO.Path.GetFullPath(root).TrimEnd(System.IO.Path.DirectorySeparatorChar) + System.IO.Path.DirectorySeparatorChar,
            StringComparison.OrdinalIgnoreCase);
    public static bool HasLink(string path)
    {
        for (string? p = System.IO.Path.GetFullPath(path); p != null; p = System.IO.Path.GetDirectoryName(p))
            if ((File.Exists(p) || Directory.Exists(p)) && (File.GetAttributes(p) & FileAttributes.ReparsePoint) != 0) return true;
        return false;
    }
    public static bool Protected(string path)
    {
        var full = System.IO.Path.GetFullPath(path);
        if(full.Equals(Environment.ProcessPath,StringComparison.OrdinalIgnoreCase))return true;
        var windows = Environment.GetFolderPath(Environment.SpecialFolder.Windows);
        if (!string.IsNullOrEmpty(windows) && (full.Equals(windows, StringComparison.OrdinalIgnoreCase) || Within(full, windows))) return true;
        // Never remove game, anti-cheat or audit/history components, even if a supplied catalog claims ownership.
        if (new[] { ".evtx", ".etl", ".log", ".pf", ".blf", ".regtrans-ms", ".sys" }.Contains(System.IO.Path.GetExtension(full), StringComparer.OrdinalIgnoreCase)) return true;
        for (string? ancestor = System.IO.Path.GetDirectoryName(full); ancestor != null; ancestor = System.IO.Path.GetDirectoryName(ancestor))
            if (File.Exists(System.IO.Path.Combine(ancestor, "GTA5.exe")) || File.Exists(System.IO.Path.Combine(ancestor, "GTA5_Enhanced.exe"))) return true;
        var components = full.Split(new[] { '\\', '/' }, StringSplitOptions.RemoveEmptyEntries);
        return components.Any(c => new[] { "Grand Theft Auto V", "GTAV", "GTA V", "BattlEye", "EasyAntiCheat", "EasyAntiCheat_EOS", "Riot Vanguard", "FiveM", "FiveM.app", "FiveMDeepCleanManager", "WindowsApps", "Windows Defender", "Windows Defender Advanced Threat Protection", "Logs", "History", "EventLogs" }.Contains(c, StringComparer.OrdinalIgnoreCase))
            || new[] { "GTA5.exe", "GTA5_Enhanced.exe", "PlayGTAV.exe", "FiveM.exe", "EasyAntiCheat.exe", "EasyAntiCheat_EOS.exe", "BEService.exe", "BEService_x64.exe" }.Contains(System.IO.Path.GetFileName(full), StringComparer.OrdinalIgnoreCase);
    }
    public static bool SafeCache(string path)
    {
        if (HasLink(path)) return false;
        var windows = Environment.GetFolderPath(Environment.SpecialFolder.Windows);
        if (!string.IsNullOrEmpty(windows) && Within(path, windows)) return false;
        var data = System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "FiveM", "FiveM.app", "data");
        var cacheRoot = new[] { "cache", "server-cache", "server-cache-priv" }.Select(n => System.IO.Path.Combine(data, n)).FirstOrDefault(root => Within(path, root));
        if (cacheRoot == null) return false;
        var relative = System.IO.Path.GetRelativePath(cacheRoot, path);
        if (relative.Split(new[] { '\\', '/' }, StringSplitOptions.RemoveEmptyEntries).Any(c => new[] { "Logs", "History", "EventLogs", "BattlEye", "EasyAntiCheat", "EasyAntiCheat_EOS" }.Contains(c, StringComparer.OrdinalIgnoreCase))) return false;
        return !new[] { ".log", ".etl", ".evtx", ".sys", ".pf", ".blf", ".regtrans-ms" }.Contains(System.IO.Path.GetExtension(path), StringComparer.OrdinalIgnoreCase);
    }
    public static void DemandFile(string path)
    {
        if (!File.Exists(path) || HasLink(path) || Protected(path)) throw new InvalidOperationException("Caminho ausente, protegido ou com redirecionamento: " + path);
    }
    public static bool DedicatedRoot(string root)
    {
        if (!Directory.Exists(root) || HasLink(root) || Protected(root)) return false;
        var full = System.IO.Path.GetFullPath(root).TrimEnd(System.IO.Path.DirectorySeparatorChar);
        var forbidden = new[] { Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86), System.IO.Path.GetTempPath(), System.IO.Path.GetPathRoot(full) ?? "" };
        return !forbidden.Where(p => !string.IsNullOrEmpty(p)).Any(p => full.Equals(System.IO.Path.GetFullPath(p).TrimEnd(System.IO.Path.DirectorySeparatorChar), StringComparison.OrdinalIgnoreCase));
    }
}
