using FiveMCleaner;
var root = Path.Combine(Path.GetTempPath(), "fivem-policy-" + Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(root);
var count = 0;
void Check(bool condition, string name) { if (!condition) throw new Exception("FAIL: " + name); count++; Console.WriteLine("PASS: " + name); }
try
{
    var file = Path.Combine(root, "product", "app.exe"); Directory.CreateDirectory(Path.GetDirectoryName(file)!); File.WriteAllText(file, "fixture");
    Check(PathPolicy.Within(file, Path.Combine(root, "product")), "child belongs to installation");
    Check(!PathPolicy.Within(Path.Combine(root, "product-other", "app.exe"), Path.Combine(root, "product")), "prefix collision rejected");
    Check(!PathPolicy.Within(Path.Combine(root, "product", "..", "other.exe"), Path.Combine(root, "product")), "traversal normalized");
    Check(!PathPolicy.Within(root, root), "root itself is not a child");
    Check(PathPolicy.Protected(Path.Combine(root, "BattlEye", "tool.dll")), "anti-cheat protected");
    Check(PathPolicy.Protected(Path.Combine(root, "Grand Theft Auto V", "dinput8.dll")), "game directory protected");
    Check(PathPolicy.Protected(Path.Combine(root, "Logs", "events.log")), "audit logs protected");
    Check(PathPolicy.Protected(Path.Combine(root, "History", "entry.db")), "history protected");
    Check(PathPolicy.Protected(Path.Combine(root, "FiveM.exe")), "FiveM executable protected");
    Check(!PathPolicy.DedicatedRoot(Path.GetTempPath()), "shared temp root rejected");
    Check(PathPolicy.DedicatedRoot(Path.GetDirectoryName(file)!), "dedicated directory accepted");
    var linked = Path.Combine(root, "redirect"); if(OperatingSystem.IsWindows()){
        var start=new System.Diagnostics.ProcessStartInfo("cmd.exe"){UseShellExecute=false,CreateNoWindow=true};
        foreach(var arg in new[]{"/c","mklink","/J",linked,Path.GetDirectoryName(file)!})start.ArgumentList.Add(arg);
        using var process=System.Diagnostics.Process.Start(start)!;process.WaitForExit();
        if(process.ExitCode!=0)throw new IOException("Could not create junction fixture");
    }else Directory.CreateSymbolicLink(linked, Path.GetDirectoryName(file)!);
    Check(PathPolicy.HasLink(Path.Combine(linked, "app.exe")), "linked ancestor rejected");
    bool rejected = false; try { PathPolicy.DemandFile(Path.Combine(linked, "app.exe")); } catch (InvalidOperationException) { rejected = true; }
    Check(rejected, "destructive guard rejects links");
    Check(!PathPolicy.HasLink(file), "ordinary file accepted");
    Check(PathPolicy.Protected(Path.Combine(root, "other", "audit.evtx")), "event files protected outside log folders");
    Check(PathPolicy.Protected(Path.Combine(root, "driver.sys")), "kernel drivers never directly deleted");
    Check(PathPolicy.Protected(Path.Combine(root, "FiveM", "FiveM.app", "data", "settings.xml")), "FiveM settings protected");
    var cache = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "FiveM", "FiveM.app", "data", "cache");
    Check(PathPolicy.SafeCache(Path.Combine(cache, "resource.bin")), "temporary cache allowed");
    Check(!PathPolicy.SafeCache(Path.Combine(cache, "..", "settings.xml")), "cache traversal rejected");
    Check(!PathPolicy.SafeCache(Path.Combine(cache, "audit.log")), "cache audit logs preserved");
    Check(!PathPolicy.SafeCache(Path.Combine(cache, "History", "entry.db")), "history inside cache preserved");
    Check(!PathPolicy.SafeCache(Path.Combine(cache, "driver.sys")), "drivers inside cache preserved");
    Check(!PathPolicy.SafeCache(Path.Combine(cache + "-other", "resource.bin")), "cache prefix collision rejected");
    var game = Path.Combine(root, "custom-install"); Directory.CreateDirectory(game); File.WriteAllText(Path.Combine(game, "GTA5.exe"), "fixture");
    Check(PathPolicy.Protected(Path.Combine(game, "plugin.dll")), "custom game installation detected by executable");
    Check(ProcessPolicy.IsGame("GTA5"), "GTA V process detected");
    Check(ProcessPolicy.IsGame("GTA5_Enhanced_BE"), "Enhanced process detected");
    Check(ProcessPolicy.IsGame("FiveM_b3258_GTAProcess"), "FiveM subprocess detected");
    Check(ProcessPolicy.IsGame("FiveM"), "FiveM main process detected");
    Check(!ProcessPolicy.IsGame("FiveM Deep Clean Manager"), "manager never mistaken for game");
    Check(!ProcessPolicy.IsGame("NotFiveM"), "unrelated process ignored");
    var diskA = Path.Combine(root, "diskA"); var diskB = Path.Combine(root, "diskB");
    Directory.CreateDirectory(Path.Combine(diskA, "Downloads")); Directory.CreateDirectory(diskB);
    var sample = Path.Combine(diskA, "Downloads", "Loard.exe"); File.WriteAllText(sample, "sample1");
    var renamed = Path.Combine(diskB, "renamed.bin"); File.Copy(sample, renamed);
    var impostor = Path.Combine(diskB, "LoardOther.exe"); File.WriteAllText(impostor, "sample2");
    Directory.CreateDirectory(Path.Combine(diskA, "Loard-folder"));
    var config = Path.Combine(diskA, "Loard-folder", "settings.json"); File.WriteAllText(config, "config");
    Directory.CreateDirectory(Path.Combine(diskA, "Logs")); File.WriteAllText(Path.Combine(diskA, "Logs", "loard.exe"), "audit");
    File.WriteAllText(Path.Combine(diskA, "loard.log"), "audit");
    var scanner = new ComputerSearch();
    var search = scanner.Scan(new[] { diskA, diskB, diskA }, "LoArD", CancellationToken.None);
    Check(search.Roots.Count == 2, "whole search deduplicates roots");
    Check(search.Candidates.Any(c => c.Path == sample), "Downloads candidate found without providing its path");
    Check(search.Candidates.Any(c => c.Path == impostor), "name-only impostor is a candidate, not automatically removed");
    Check(search.Candidates.Any(c => c.Path == config), "matching parent folder discovers nested files");
    Check(!search.Candidates.Any(c => c.Path.Contains("Logs") || c.Path.EndsWith(".log")), "discovery excludes protected audit areas");
    Check(File.Exists(sample) && File.ReadAllText(impostor) == "sample2", "discovery never deletes or changes candidates");
    Check(!search.Candidates.Any(c => c.Path == renamed), "renamed file not falsely discovered by name alone");
    var recognized = ConfirmedTarget.FromRecognition(search.Candidates.Single(c => c.Path == sample));
    Check(recognized.Matches(renamed), "recognized sample identifies a renamed byte-identical copy");
    Check(!recognized.Matches(impostor), "same size and suspicious name never establish content identity");
    File.WriteAllText(renamed, "changed");
    Check(!recognized.Matches(renamed), "changed content loses recognized identity");
    var oldCandidate = search.Candidates.Single(c => c.Path == sample);
    File.AppendAllText(sample, "modified");
    bool changedRejected = false;
    try { ConfirmedTarget.FromRecognition(oldCandidate); } catch(IOException) { changedRejected = true; }
    Check(changedRejected, "recognition refuses files modified after discovery");
    bool canceledSearch = false;
    using (var cancel = new CancellationTokenSource())
    { cancel.Cancel(); try { scanner.Scan(new[] { diskA }, "loard", cancel.Token); } catch(OperationCanceledException) { canceledSearch = true; } }
    Check(canceledSearch, "whole computer discovery honors cancellation");
    bool queryRejected = false;
    try { scanner.Scan(new[] { diskA }, "*", CancellationToken.None); } catch(ArgumentException) { queryRejected = true; }
    Check(queryRejected, "empty/broad wildcard search rejected");
    Check(scanner.Scan(new[] { Path.Combine(root, "missing") }, "loard", CancellationToken.None).Inaccessible == 1, "missing scan root reported as incomplete coverage");
    var many = Path.Combine(root, "many"); Directory.CreateDirectory(many);
    for(int i = 0; i < ComputerSearch.CandidateLimit + 1; i++) File.WriteAllText(Path.Combine(many, $"loard-{i}.bin"), "x");
    var limited = scanner.Scan(new[]{many}, "loard", CancellationToken.None);
    Check(limited.Candidates.Count == ComputerSearch.CandidateLimit && limited.OmittedCandidates == 1, "candidate limit is explicit while traversal continues");
    Console.WriteLine($"{count} safety checks passed");
}
finally { Directory.Delete(root, true); }
