using System.ComponentModel;
using System.Runtime.CompilerServices;
namespace FiveMCleaner;
public record InstalledProgram(string Name, string Publisher, string Location, string Uninstall, string Key, string View)
{
    public string Display => $"{Name} — {Publisher}";
}
public class Finding : INotifyPropertyChanged
{
    public bool Selected { get; set; }
    public string Kind { get; init; } = "";
    public string Path { get; init; } = "";
    public string Evidence { get; init; } = "";
    public string Description => $"{Path} — {Evidence}";
    public string Identity { get; init; } = "";
    private string outcome = "Aguardando";
    public string Outcome { get => outcome; set { outcome = value; Changed(); } }
    public event PropertyChangedEventHandler? PropertyChanged;
    private void Changed([CallerMemberName] string? name = null) => PropertyChanged?.Invoke(this, new(name));
}
public record HashCatalog(string Program, Dictionary<string, string> Files);
public record AuditEntry(DateTimeOffset Time, string Operation, string Target, string Result);
