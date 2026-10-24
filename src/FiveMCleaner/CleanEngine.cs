using System.IO;
using Microsoft.Win32;
using Microsoft.Win32.SafeHandles;
using System.Diagnostics;
using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
namespace FiveMCleaner;
public sealed class CleanEngine
{
    public string ReportDirectory { get; } = System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "FiveMDeepCleanManager", "Reports");
    public string ReportPath { get; }
    public List<AuditEntry> Journal { get; } = [];
    public List<string> Warnings { get; } = [];
    public bool RebootRequired { get; private set; }
    public HashCatalog? Catalog { get; set; }
    private readonly object logLock = new();
    private readonly HashSet<string> previousOwned = new(StringComparer.OrdinalIgnoreCase);
    private string? signatureRoot;
    public CleanEngine() { Directory.CreateDirectory(ReportDirectory); ReportPath = System.IO.Path.Combine(ReportDirectory, $"clean-{DateTime.Now:yyyyMMdd-HHmmss}-{Guid.NewGuid():N}.jsonl"); Log("Sessão", Environment.MachineName, "Iniciada"); }
    public void Log(string operation, string target, string result)
    {
        lock (logLock) { var entry = new AuditEntry(DateTimeOffset.Now, operation, target, result); File.AppendAllText(ReportPath, JsonSerializer.Serialize(entry) + Environment.NewLine); File.AppendAllText(System.IO.Path.ChangeExtension(ReportPath, "txt"), $"{entry.Time:O} | {operation} | {target} | {result}" + Environment.NewLine); Journal.Add(entry); }
    }
    public static List<InstalledProgram> Programs()
    {
        var result = new List<InstalledProgram>();
        foreach (var hive in new[] { RegistryHive.LocalMachine, RegistryHive.CurrentUser })
            foreach (var view in new[] { RegistryView.Registry64, RegistryView.Registry32 })
            {
                using var root = RegistryKey.OpenBaseKey(hive, view);
                using var uninstall = root.OpenSubKey(@"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall");
                if (uninstall == null) continue;
                foreach (var name in uninstall.GetSubKeyNames())
                {
                    using var key = uninstall.OpenSubKey(name); if (key == null) continue;
                    var title = key.GetValue("DisplayName") as string;
                    if (string.IsNullOrWhiteSpace(title) || Convert.ToInt32(key.GetValue("SystemComponent", 0)) == 1) continue;
                    result.Add(new(title, key.GetValue("Publisher") as string ?? "", key.GetValue("InstallLocation") as string ?? "", key.GetValue("UninstallString") as string ?? "", $"{hive}\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{name}", view.ToString()));
                }
            }
        return result.DistinctBy(p => (p.Key, p.View)).OrderBy(p => p.Name).ToList();
    }
    public static void CheckGames()
    {
        foreach (var process in Process.GetProcesses()) using (process)
                if (process.Id != Environment.ProcessId && ProcessPolicy.IsGame(process.ProcessName)) throw new InvalidOperationException("Feche GTA V e FiveM antes de continuar.");
    }
    private static string Hash(string file) { using var stream = File.OpenRead(file); return Convert.ToHexString(SHA256.HashData(stream)); }
    [DllImport("wintrust.dll", ExactSpelling = true, CharSet = CharSet.Unicode)] private static extern int WinVerifyTrust(IntPtr hwnd, IntPtr action, IntPtr data);
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)] private struct TrustFile { public uint Size; [MarshalAs(UnmanagedType.LPWStr)] public string Path; public IntPtr Handle; public IntPtr Subject; }
    [StructLayout(LayoutKind.Sequential)] private struct TrustData { public uint Size; public IntPtr Policy; public IntPtr Sip; public uint UI; public uint Revocation; public uint Choice; public IntPtr File; public uint StateAction; public IntPtr State; public IntPtr Url; public uint Flags; public uint Context; public IntPtr SignatureSettings; }
    private static bool TrustedPublisher(string path, string publisher)
    {
        if (string.IsNullOrWhiteSpace(publisher)) return false;
        var file = new TrustFile { Size = (uint)Marshal.SizeOf<TrustFile>(), Path = path };
        var fp = Marshal.AllocHGlobal(Marshal.SizeOf<TrustFile>()); var dp = Marshal.AllocHGlobal(Marshal.SizeOf<TrustData>()); var ap = Marshal.AllocHGlobal(16);
        try
        {
            Marshal.StructureToPtr(file, fp, false); Marshal.StructureToPtr(new TrustData { Size = (uint)Marshal.SizeOf<TrustData>(), UI = 2, Revocation = 1, Choice = 1, File = fp, Flags = 0x80 }, dp, false);
            Marshal.StructureToPtr(new Guid("00AAC56B-CD44-11d0-8CC2-00C04FC295EE"), ap, false);
            if (WinVerifyTrust(new IntPtr(-1), ap, dp) != 0) return false;
#pragma warning disable SYSLIB0057
            using var signedCertificate = X509Certificate.CreateFromSignedFile(path);
            using var cert = new X509Certificate2(signedCertificate);
#pragma warning restore SYSLIB0057
            return cert.GetNameInfo(X509NameType.SimpleName, false).Equals(publisher, StringComparison.OrdinalIgnoreCase);
        }
        catch (CryptographicException) { return false; }
        finally { Marshal.DestroyStructure<TrustFile>(fp); Marshal.FreeHGlobal(fp); Marshal.FreeHGlobal(dp); Marshal.FreeHGlobal(ap); }
    }
    private string? Ownership(string path, InstalledProgram? program)
    {
        if (!File.Exists(path) || PathPolicy.HasLink(path) || PathPolicy.Protected(path)) return null;
        if (Catalog != null && (program == null || Catalog.Program.Equals(program.Name, StringComparison.OrdinalIgnoreCase)) && Catalog.Files.TryGetValue(System.IO.Path.GetFileName(path), out var expected) && Hash(path).Equals(expected, StringComparison.OrdinalIgnoreCase)) return "SHA-256: " + expected;
        if (program != null && signatureRoot == program.Location && PathPolicy.DedicatedRoot(program.Location) && PathPolicy.Within(path, program.Location) && new[] { ".exe", ".dll" }.Contains(System.IO.Path.GetExtension(path), StringComparer.OrdinalIgnoreCase) && TrustedPublisher(path, program.Publisher)) return "InstallLocation + assinatura Authenticode válida: " + program.Publisher;
        return null;
    }
    private void Warn(string target, Exception ex) { var message = target + ": " + ex.Message; Warnings.Add(message); Log("Limitação", target, ex.Message); }
    private IEnumerable<string> Walk(string root, CancellationToken token, bool cache = false)
    {
        var stack = new Stack<string>(); stack.Push(root); int visited = 0;
        while (stack.Count > 0)
        {
            token.ThrowIfCancellationRequested(); var dir = stack.Pop(); if (PathPolicy.HasLink(dir) || (!cache && PathPolicy.Protected(dir))) continue;
            string[] files, dirs; try { files = Directory.GetFiles(dir); dirs = Directory.GetDirectories(dir); } catch (Exception e) when (e is IOException or UnauthorizedAccessException) { Warn(dir, e); continue; }
            foreach (var file in files) { if (++visited > 150000) { Warnings.Add("Limite de 150.000 arquivos alcançado em " + root); Log("Limitação", root, "Varredura parcial: limite de arquivos"); yield break; } yield return file; }
            foreach (var child in dirs) stack.Push(child);
        }
    }
    public async Task<List<Finding>> Analyze(InstalledProgram? program, string extra, bool cache, CancellationToken token, bool finalVerification = false)
    {
        CheckGames(); Warnings.Clear();
        if (!finalVerification)
        {
            previousOwned.Clear(); signatureRoot = null;
            if (program != null && PathPolicy.DedicatedRoot(program.Location))
            {
                var otherRoots = Programs().Where(p => p.Name != program.Name && !string.IsNullOrWhiteSpace(p.Location) && Directory.Exists(p.Location));
                if (!otherRoots.Any(p => System.IO.Path.GetFullPath(p.Location).TrimEnd('\\').Equals(System.IO.Path.GetFullPath(program.Location).TrimEnd('\\'), StringComparison.OrdinalIgnoreCase) || PathPolicy.Within(p.Location, program.Location) || PathPolicy.Within(program.Location, p.Location))) signatureRoot = program.Location;
                else { Warnings.Add("InstallLocation compartilhado com outro produto: somente hashes conhecidos autorizam arquivos."); Log("Limitação", program.Location, Warnings[^1]); }
            }
            else if (program != null) { Warnings.Add("InstallLocation ausente ou inseguro: a análise de resíduos requer catálogo de hashes conhecidos."); Log("Limitação", program.Name, Warnings[^1]); }
        }
        if (program != null && Regex.IsMatch(program.Name, @"(?i)(Grand Theft Auto|GTA\s*V|FiveM|BattlEye|Easy\s*Anti\s*Cheat|Vanguard|Windows)")) throw new InvalidOperationException("Produto protegido: a remoção deste componente não é permitida.");
        var findings = new List<Finding>(); int unverified = 0;var examined=new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        Log("Análise", program?.Name ?? "Catálogo/cache", "Iniciada");
        var roots = new List<string>();
        if (program != null && PathPolicy.DedicatedRoot(program.Location)) roots.Add(program.Location);
        if (Catalog != null)
        {
            roots.AddRange(new[] { Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86), System.IO.Path.GetTempPath(), Environment.GetFolderPath(Environment.SpecialFolder.Startup), Environment.GetFolderPath(Environment.SpecialFolder.CommonStartup) });
            if (Directory.Exists(extra)) roots.Add(extra);
        }
        foreach (var root in roots.Where(Directory.Exists).Distinct(StringComparer.OrdinalIgnoreCase))
            foreach (var path in Walk(root, token))
            {
                token.ThrowIfCancellationRequested();
                if (!examined.Add(path)) continue;
                try
                {
                    var evidence = Ownership(path, program); if (evidence != null) findings.Add(new() { Kind = "Arquivo", Path = path, Evidence = evidence, Identity = Hash(path) });
                    else if (program != null && !string.IsNullOrWhiteSpace(program.Location) && Directory.Exists(program.Location) && PathPolicy.Within(path, program.Location)) { unverified++; Log("Preservado sem evidência", path, "Não há hash conhecido ou assinatura correspondente suficiente"); }
                }
                catch (Exception e) when (e is IOException or UnauthorizedAccessException or CryptographicException) { Warn(path, e); }
            }
        if (program != null && PathPolicy.DedicatedRoot(program.Location))
        {
            var dirs = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            foreach (var file in findings.Where(f => f.Kind == "Arquivo").ToArray())
            {
                for (var parent = System.IO.Path.GetDirectoryName(file.Path); parent != null && (PathPolicy.Within(parent, program.Location) || parent.Equals(System.IO.Path.GetFullPath(program.Location).TrimEnd(System.IO.Path.DirectorySeparatorChar), StringComparison.OrdinalIgnoreCase)); parent = System.IO.Path.GetDirectoryName(parent)) dirs.Add(parent);
            }
            foreach (var dir in dirs.OrderByDescending(p => p.Length)) findings.Add(new() { Kind = "Pasta vazia", Path = dir, Identity = program.Location, Evidence = "Pasta de instalação; remover somente se estiver vazia na execução" });
        }
        if (unverified > 0) { Warnings.Add($"{unverified} arquivos na instalação foram preservados por falta de evidência. Consulte o relatório."); }
        var owned = findings.Where(f => f.Kind == "Arquivo").Select(f => f.Path).ToHashSet(StringComparer.OrdinalIgnoreCase);
        if (finalVerification) owned.UnionWith(previousOwned); else previousOwned.UnionWith(owned);
        if (program != null && !string.IsNullOrWhiteSpace(program.Uninstall) && Programs().Any(p => p.Key == program.Key && p.View == program.View))
        {
            try { var cmd = Uninstaller(program); findings.Insert(0, new() { Kind = "Desinstalador", Path = cmd.FileName, Evidence = "Comando oficial registrado; interface interativa. " + program.Uninstall, Identity = program.Uninstall }); }
            catch (Exception e) { Warn("Desinstalador", e); }
        }
        foreach (var proc in Process.GetProcesses()) using (proc) { try { var path = proc.MainModule?.FileName; if (path != null && owned.Contains(path)) findings.Add(new() { Kind = "Processo", Path = path, Evidence = $"PID {proc.Id}; executável identificado", Identity = proc.Id.ToString() }); } catch (Exception e) when (e is System.ComponentModel.Win32Exception or InvalidOperationException or NotSupportedException) {/* Other processes are inaccessible by design. */} }
        foreach (var hive in new[] { RegistryHive.LocalMachine, RegistryHive.CurrentUser }) foreach (var view in new[] { RegistryView.Registry64, RegistryView.Registry32 })
            {
                using var root = RegistryKey.OpenBaseKey(hive, view);
                foreach (var keyPath in new[] { @"SOFTWARE\Microsoft\Windows\CurrentVersion\Run", @"SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce" })
                {
                    using var key = root.OpenSubKey(keyPath); if (key == null) continue;
                    foreach (var name in key.GetValueNames()) if (key.GetValue(name) is string value) { var exe = Executable(value); if (exe != null && owned.Contains(exe)) findings.Add(new() { Kind = "Inicialização", Path = $"{hive}\\{keyPath}\\{name}", Evidence = value, Identity = JsonSerializer.Serialize(new[] { hive.ToString(), view.ToString(), keyPath, name, value, exe }) }); }
                }
            }
        using (var services = Registry.LocalMachine.OpenSubKey(@"SYSTEM\CurrentControlSet\Services")) if (services != null) foreach (var name in services.GetSubKeyNames())
                {
                    using var key = services.OpenSubKey(name); var image = key?.GetValue("ImagePath") as string; if (image == null) continue;
                    var exe = Executable(image); var type = Convert.ToInt32(key?.GetValue("Type", 0));
                    if (exe != null && owned.Contains(exe) && type == 16) findings.Add(new() { Kind = "Serviço", Path = name, Evidence = image, Identity = exe });
                }
        try
        {
            var json = await PowerShell("@(Get-ScheduledTask -ErrorAction Stop | ForEach-Object { $t=$_; foreach($a in $t.Actions){ if(@($t.Actions).Count -eq 1 -and $a.Execute){ [pscustomobject]@{ Name=$t.TaskName; Path=$t.TaskPath; Execute=$a.Execute } } } }) | ConvertTo-Json -Compress", token);
            if (!string.IsNullOrWhiteSpace(json))
            {
                using var doc = JsonDocument.Parse(json); var entries = doc.RootElement.ValueKind == JsonValueKind.Array ? doc.RootElement.EnumerateArray().ToArray() : new[] { doc.RootElement };
                foreach (var t in entries) { var exe = Environment.ExpandEnvironmentVariables(t.GetProperty("Execute").GetString() ?? "").Trim('"'); if (owned.Contains(exe)) findings.Add(new() { Kind = "Tarefa", Path = t.GetProperty("Path").GetString() + t.GetProperty("Name").GetString(), Evidence = exe, Identity = exe }); }
            }
        }
        catch (Exception e) when (e is not OperationCanceledException) { Warn("Tarefas agendadas", e); }
        if (cache) { var data = System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "FiveM", "FiveM.app", "data"); foreach (var name in new[] { "cache", "server-cache", "server-cache-priv" }) { var dir = System.IO.Path.Combine(data, name); if (Directory.Exists(dir) && !PathPolicy.HasLink(dir)) foreach (var file in Walk(dir, token, true)) if (PathPolicy.SafeCache(file)) findings.Add(new() { Kind = "Cache FiveM", Path = file, Evidence = "Cache temporário permitido: " + name, Identity = Hash(file) }); } }
        foreach (var finding in findings) Log("Encontrado: " + finding.Kind, finding.Path, finding.Evidence);
        Log("Análise", program?.Name ?? "Cache", $"{findings.Count} componentes; {Warnings.Count} limitações"); return findings;
    }
    [DllImport("shell32.dll", SetLastError = true, CharSet = CharSet.Unicode)] private static extern IntPtr CommandLineToArgvW(string command, out int count);
    [DllImport("kernel32.dll")] private static extern IntPtr LocalFree(IntPtr p);
    private static string[] SplitCommand(string command) { var ptr = CommandLineToArgvW(command, out var n); if (ptr == IntPtr.Zero) throw new InvalidOperationException("Comando inválido"); try { return Enumerable.Range(0, n).Select(i => Marshal.PtrToStringUni(Marshal.ReadIntPtr(ptr, i * IntPtr.Size)) ?? "").ToArray(); } finally { LocalFree(ptr); } }
    private static string? Executable(string cmd) { try { var args = SplitCommand(Environment.ExpandEnvironmentVariables(cmd)); if (args.Length == 0) return null; var path = args[0]; if (path.StartsWith(@"\??\")) path = path[4..]; return System.IO.Path.IsPathFullyQualified(path) ? System.IO.Path.GetFullPath(path) : null; } catch { return null; } }
    private static ProcessStartInfo Uninstaller(InstalledProgram p)
    {
        if (!Programs().Any(current => current == p)) throw new InvalidOperationException("Registro de instalação alterado ou ausente; analise novamente");
        var args = SplitCommand(Environment.ExpandEnvironmentVariables(p.Uninstall)); if (args.Length == 0) throw new InvalidOperationException("Sem comando");
        if (System.IO.Path.GetFileName(args[0]).Equals("msiexec.exe", StringComparison.OrdinalIgnoreCase) || args[0].Equals("msiexec", StringComparison.OrdinalIgnoreCase))
        {
            var match = Regex.Match(p.Uninstall, @"(?i)(?:/I|/X)\s*(\{[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\})");
            if (!match.Success || !p.Key.EndsWith(match.Groups[1].Value, StringComparison.OrdinalIgnoreCase)) throw new InvalidOperationException("MSI sem ProductCode correspondente ao registro");
            return Command(System.IO.Path.Combine(Environment.SystemDirectory, "msiexec.exe"), "/x", match.Groups[1].Value, "/norestart");
        }
        var exe = args[0]; PathPolicy.DemandFile(exe);
        if (new[] { "powershell.exe", "pwsh.exe", "cmd.exe", "rundll32.exe", "regsvr32.exe", "wscript.exe", "cscript.exe", "mshta.exe" }.Contains(System.IO.Path.GetFileName(exe), StringComparer.OrdinalIgnoreCase)) throw new InvalidOperationException("Desinstalação por interpretador não é executada automaticamente");
        if (!System.IO.Path.IsPathFullyQualified(exe) || !PathPolicy.DedicatedRoot(p.Location) || !PathPolicy.Within(exe, p.Location) || !TrustedPublisher(exe, p.Publisher)) throw new InvalidOperationException("Desinstalador não possui caminho e assinatura de editor verificados; use Aplicativos do Windows.");
        return Command(exe, args.Skip(1).ToArray());
    }
    private static ProcessStartInfo Command(string exe, params string[] args) { var info = new ProcessStartInfo(exe) { UseShellExecute = false, CreateNoWindow = true }; foreach (var arg in args) info.ArgumentList.Add(arg); return info; }
    private static async Task<int> Run(ProcessStartInfo info, CancellationToken token) { token.ThrowIfCancellationRequested(); using var p = Process.Start(info) ?? throw new IOException("Processo não iniciado"); await p.WaitForExitAsync(CancellationToken.None); return p.ExitCode; }
    private static async Task<string> PowerShell(string script, CancellationToken token) { token.ThrowIfCancellationRequested(); var info = Command(System.IO.Path.Combine(Environment.SystemDirectory, @"WindowsPowerShell\v1.0\powershell.exe"), "-NoProfile", "-NonInteractive", "-EncodedCommand", Convert.ToBase64String(Encoding.Unicode.GetBytes("$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; " + script))); info.RedirectStandardOutput = true; info.RedirectStandardError = true; using var p = Process.Start(info) ?? throw new IOException("PowerShell indisponível"); var output = p.StandardOutput.ReadToEndAsync(CancellationToken.None); var error = p.StandardError.ReadToEndAsync(CancellationToken.None); await p.WaitForExitAsync(CancellationToken.None); if (p.ExitCode != 0) throw new IOException(await error); return await output; }
    public async Task RestorePoint(CancellationToken token) { try { await PowerShell("$before=(Get-ComputerRestorePoint | Sort-Object SequenceNumber -Descending | Select-Object -First 1).SequenceNumber; Checkpoint-Computer -Description 'FiveM Deep Clean Manager' -RestorePointType MODIFY_SETTINGS -ErrorAction Stop; $r=Get-ComputerRestorePoint | Sort-Object SequenceNumber -Descending | Select-Object -First 1; if(!$r -or $r.SequenceNumber -le $before -or $r.Description -ne 'FiveM Deep Clean Manager' -or ([Management.ManagementDateTimeConverter]::ToDateTime($r.CreationTime) -lt (Get-Date).AddMinutes(-5))){throw 'Ponto de restauração recente não confirmado'}", token); Log("Restauração", "Windows", "Ponto criado e confirmado"); } catch (Exception e) when (e is not OperationCanceledException) { Warn("Ponto de restauração não confirmado", e); } }
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern SafeFileHandle CreateFileW(string name, uint access, uint sharing, IntPtr security, uint creation, uint flags, IntPtr template);
    [StructLayout(LayoutKind.Sequential)] private struct AttributeTag { public uint Attributes; public uint Tag; }
    [StructLayout(LayoutKind.Sequential)] private struct Disposition { [MarshalAs(UnmanagedType.Bool)] public bool Delete; }
    [DllImport("kernel32.dll", SetLastError = true)] private static extern bool GetFileInformationByHandleEx(SafeFileHandle handle, int kind, out AttributeTag info, uint size);
    [DllImport("kernel32.dll", SetLastError = true)] private static extern bool SetFileInformationByHandle(SafeFileHandle handle, int kind, ref Disposition info, uint size);
    private static void DeleteVerified(string path, string expectedHash)
    {
        // Lock the exact file against writers/deleters and delete through that same handle.
        // OPEN_REPARSE_POINT prevents following a substituted final symlink.
        using var handle = CreateFileW(path, 0x80010000, 1, IntPtr.Zero, 3, 0x00200000, IntPtr.Zero);
        if (handle.IsInvalid) throw new IOException("Não foi possível bloquear o arquivo", new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error()));
        if (!GetFileInformationByHandleEx(handle, 9, out var tag, (uint)Marshal.SizeOf<AttributeTag>()) || (tag.Attributes & 0x410) != 0) throw new IOException("Arquivo é diretório, redirecionamento ou não pôde ser inspecionado");
        using var stream = new FileStream(handle, FileAccess.Read);
        if (!Convert.ToHexString(SHA256.HashData(stream)).Equals(expectedHash, StringComparison.OrdinalIgnoreCase)) throw new IOException("Arquivo alterado antes da exclusão");
        var disposition = new Disposition { Delete = true };
        if (!SetFileInformationByHandle(handle, 4, ref disposition, (uint)Marshal.SizeOf<Disposition>())) throw new IOException("Exclusão não autorizada pelo Windows", new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error()));
    }
    public async Task Execute(Finding f, InstalledProgram? program, CancellationToken token)
    {
        token.ThrowIfCancellationRequested(); CheckGames(); Log("Antes de " + f.Kind, f.Path, f.Evidence);
        switch (f.Kind)
        {
            case "Arquivo":
            case "Cache FiveM":
                if (!File.Exists(f.Path)) { f.Outcome = "Já ausente"; break; }
                if (f.Kind == "Cache FiveM") { if (!PathPolicy.SafeCache(f.Path)) throw new IOException("Cache fora do escopo ou com redirecionamento"); }
                else PathPolicy.DemandFile(f.Path);
                if (Hash(f.Path) != f.Identity) throw new IOException("Arquivo alterado desde a análise; nova análise necessária");
                if (f.Kind == "Arquivo" && Ownership(f.Path, program) == null) throw new IOException("Evidência não é mais válida");
                if (f.Kind == "Cache FiveM")
                {
                    var data = System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "FiveM", "FiveM.app", "data");
                    if (!new[] { "cache", "server-cache", "server-cache-priv" }.Any(n => PathPolicy.Within(f.Path, System.IO.Path.Combine(data, n)))) throw new IOException("Cache fora do escopo");
                }
                DeleteVerified(f.Path, f.Identity); f.Outcome = File.Exists(f.Path) ? "Ainda presente" : "Removido"; break;
            case "Pasta vazia":
                if (!Directory.Exists(f.Path)) { f.Outcome = "Já ausente"; break; }
                if (PathPolicy.HasLink(f.Path) || PathPolicy.Protected(f.Path) || !PathPolicy.DedicatedRoot(f.Identity) || !(PathPolicy.Within(f.Path, f.Identity) || System.IO.Path.GetFullPath(f.Path).TrimEnd('\\').Equals(System.IO.Path.GetFullPath(f.Identity).TrimEnd('\\'), StringComparison.OrdinalIgnoreCase))) throw new IOException("Pasta fora do escopo");
                Directory.Delete(f.Path, false); f.Outcome = "Removido"; break;
            case "Processo":
                using (var proc = Process.GetProcessById(int.Parse(f.Identity))) { if (!string.Equals(proc.MainModule?.FileName, f.Path, StringComparison.OrdinalIgnoreCase) || Ownership(f.Path, program) == null) throw new IOException("Processo mudou de identidade"); proc.Kill(false); await proc.WaitForExitAsync(CancellationToken.None); }
                f.Outcome = "Encerrado"; break;
            case "Desinstalador":
                if (program == null) throw new InvalidOperationException("Programa não selecionado");
                var exit = await Run(Uninstaller(program), CancellationToken.None); // Never abandon an installer mid-transaction.
                if (exit == 3010 || exit == 1641) RebootRequired = true;
                if (exit != 0 && exit != 3010 && exit != 1641) throw new IOException("Desinstalador retornou " + exit);
                f.Outcome = "Executado; verificar"; break;
            case "Inicialização":
                var fields = JsonSerializer.Deserialize<string[]>(f.Identity)!;
                using (var root = RegistryKey.OpenBaseKey(Enum.Parse<RegistryHive>(fields[0]), Enum.Parse<RegistryView>(fields[1]))) using (var key = root.OpenSubKey(fields[2], true))
                {
                    if (key?.GetValue(fields[3]) as string != fields[4]) throw new IOException("Entrada alterada ou ausente");
                    if (File.Exists(fields[5]) && Ownership(fields[5], program) == null) throw new IOException("Executável perdeu evidência");
                    key.DeleteValue(fields[3], true);
                }
                f.Outcome = "Removido"; break;
            case "Serviço":
                using (var key = Registry.LocalMachine.OpenSubKey(@"SYSTEM\CurrentControlSet\Services\" + f.Path))
                {
                    if (key == null) { f.Outcome = "Já ausente"; break; }
                    if (Convert.ToInt32(key.GetValue("Type", 0)) != 16 || !string.Equals(Executable(key.GetValue("ImagePath") as string ?? ""), f.Identity, StringComparison.OrdinalIgnoreCase)) throw new IOException("Serviço alterado");
                    if (File.Exists(f.Identity) && Ownership(f.Identity, program) == null) throw new IOException("Evidência inválida");
                }
                var sc = System.IO.Path.Combine(Environment.SystemDirectory, "sc.exe");
                await Run(Command(sc, "stop", f.Path), token);
                var code = await Run(Command(sc, "delete", f.Path), token); if (code != 0) throw new IOException("sc delete retornou " + code);
                RebootRequired = true; f.Outcome = "Remoção solicitada"; break;
            case "Tarefa":
                var full = Convert.ToBase64String(Encoding.UTF8.GetBytes(f.Path)); var exe64 = Convert.ToBase64String(Encoding.UTF8.GetBytes(f.Identity));
                if (File.Exists(f.Identity) && Ownership(f.Identity, program) == null) throw new IOException("Evidência inválida");
                await PowerShell("$n=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('" + full + "')); $e=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('" + exe64 + "')); $t=@(Get-ScheduledTask | Where-Object { ($_.TaskPath+$_.TaskName) -eq $n }); if($t.Count -ne 1){throw 'Tarefa ausente ou ambígua'}; if(@($t[0].Actions).Count -ne 1){throw 'Tarefa passou a ter múltiplas ações'}; if(@($t[0].Actions | Where-Object { [Environment]::ExpandEnvironmentVariables($_.Execute).Trim('\"') -eq $e }).Count -eq 0){throw 'Ação alterada'}; $t[0] | Unregister-ScheduledTask -Confirm:$false", token);
                f.Outcome = "Removido"; break;
        }
        Log(f.Kind, f.Path, f.Outcome);
    }
}
