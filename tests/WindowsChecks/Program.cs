using FiveMCleaner;
using System.Security.Cryptography;
if (!OperatingSystem.IsWindows()) { Console.WriteLine("Windows integration checks require Windows."); return 2; }
var root = Path.Combine(Path.GetTempPath(), "FiveMCleaner-fixture-" + Guid.NewGuid().ToString("N")); Directory.CreateDirectory(root);
var engine = new CleanEngine(); var passed = 0;
void Check(bool b, string name) { if (!b) throw new Exception("FAIL: " + name); passed++; Console.WriteLine("PASS: " + name); }
string Digest(string p) => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(p)));
Finding Plan(string p) => new() { Kind = "Arquivo", Path = p, Identity = Digest(p), Evidence = "Test fixture hash" };
try
{
    var file = Path.Combine(root, "owned.bin"); File.WriteAllText(file, "owned fixture");
    engine.Catalog = new("Test fixture", new(StringComparer.OrdinalIgnoreCase) { [Path.GetFileName(file)] = Digest(file) });
    var plan = Plan(file); await engine.Execute(plan, null, CancellationToken.None);
    Check(!File.Exists(file) && plan.Outcome == "Removido", "known hash file removed");
    File.WriteAllText(file, "owned fixture"); plan = Plan(file); File.AppendAllText(file, " changed");
    try { await engine.Execute(plan, null, CancellationToken.None); throw new Exception("Changed file was deleted"); } catch (IOException) { }
    Check(File.Exists(file), "changed file preserved");
    plan = Plan(file); try { await engine.Execute(plan, null, CancellationToken.None); throw new Exception("Unknown hash was deleted"); } catch (IOException) { }
    Check(File.Exists(file), "unrecognized hash preserved");
    using var cts = new CancellationTokenSource(); cts.Cancel(); try { await engine.Execute(plan, null, cts.Token); throw new Exception("Cancellation ignored"); } catch (OperationCanceledException) { }
    Check(File.Exists(file), "cancellation prevents deletion");
    var log = Path.Combine(root, "audit.log"); File.WriteAllText(log, "audit fixture"); engine.Catalog.Files["audit.log"] = Digest(log);
    try { await engine.Execute(Plan(log), null, CancellationToken.None); throw new Exception("Audit removed"); } catch (InvalidOperationException) { }
    Check(File.Exists(log), "audit preserved even with known hash");
    Check(File.ReadLines(engine.ReportPath).Count() >= 5, "operations recorded on disk");
    Console.WriteLine($"{passed} Windows checks passed; report: {engine.ReportPath}"); return 0;
}
finally { Directory.Delete(root, true); }
