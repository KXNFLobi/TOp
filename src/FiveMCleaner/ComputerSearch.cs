using System.Diagnostics;
using System.IO;
using System.Security.Cryptography;
namespace FiveMCleaner;

public record SearchCandidate(string Path, long Size, DateTime ModifiedUtc)
{
    public string SizeDisplay => $"{Size:N0} bytes";
    public string ModifiedDisplay => ModifiedUtc.ToLocalTime().ToString("g");
}
public record ScanUpdate(long Files, string CurrentPath);
public record ComputerSearchResult(IReadOnlyList<SearchCandidate> Candidates, IReadOnlyList<string> Roots,
    long Files, long Excluded, long Inaccessible, long OmittedCandidates);

// A name match is discovery evidence only. This class never authorizes removal.
public sealed class ComputerSearch
{
    public const int CandidateLimit = 2000;
    public static IReadOnlyList<string> LocalRoots(Action<string, string, string> log)
    {
        var roots = new List<string>();
        foreach (var drive in DriveInfo.GetDrives())
        {
            try
            {
                if (drive.DriveType != DriveType.Fixed) { log("Unidade não pesquisada", drive.Name, "Não é unidade local fixa"); continue; }
                if (!drive.IsReady) { log("Unidade indisponível", drive.Name, "Não pronta ou bloqueada"); continue; }
                roots.Add(drive.RootDirectory.FullName);
            }
            catch (Exception e) when (e is IOException or UnauthorizedAccessException)
            { log("Unidade inacessível", drive.Name, e.Message); }
        }
        return roots;
    }

    public ComputerSearchResult Scan(IEnumerable<string> roots, string query, CancellationToken token,
        IProgress<ScanUpdate>? progress = null, Action<string, string, string>? log = null)
    {
        query = query.Trim();
        if (query.Length < 3 || query.Length > 80 || query.IndexOfAny(new[] { '\\', '/', '*', '?' }) >= 0)
            throw new ArgumentException("Use um nome de pelo menos 3 caracteres, sem caminhos ou curingas.");
        var normalizedRoots = roots.Select(Path.GetFullPath).Distinct(StringComparer.OrdinalIgnoreCase).ToArray();
        var candidates = new List<SearchCandidate>();
        var seenDirectories = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        long files = 0, excluded = 0, inaccessible = 0, omitted = 0;
        var clock = Stopwatch.StartNew();
        void Report(string path)
        {
            if (clock.ElapsedMilliseconds < 250) return;
            clock.Restart(); progress?.Report(new(files, path));
        }
        void Inaccessible(string path, Exception e)
        { inaccessible++; log?.Invoke("Busca: inacessível", path, e.Message); }
        try
        {
            foreach (var root in normalizedRoots)
            {
                log?.Invoke("Raiz da busca", root, "Somente leitura; áreas protegidas, offline e redirecionadas são excluídas");
                var stack = new Stack<(string Path, bool MatchingFolder)>();
                stack.Push((root, false));
                while (stack.Count > 0)
                {
                    token.ThrowIfCancellationRequested();
                    var (directory, inheritedMatch) = stack.Pop();
                    if (!seenDirectories.Add(directory)) continue;
                    try
                    {
                        if (!Directory.Exists(directory)) { inaccessible++; log?.Invoke("Busca: raiz ausente", directory, "Não disponível"); continue; }
                        if (PathPolicy.HasLink(directory) || PathPolicy.Protected(directory))
                        { excluded++; log?.Invoke("Busca: área excluída", directory, "Área protegida ou redirecionada; não pesquisada"); continue; }
                        var matchingFolder = inheritedMatch || Path.GetFileName(directory).Contains(query, StringComparison.OrdinalIgnoreCase);
                        foreach (var entry in Directory.EnumerateFileSystemEntries(directory))
                        {
                            token.ThrowIfCancellationRequested(); Report(directory);
                            try
                            {
                                var attributes = File.GetAttributes(entry);
                                if ((attributes & (FileAttributes.ReparsePoint | FileAttributes.Offline)) != 0) { excluded++; log?.Invoke("Busca: redirecionamento excluído", entry, "Não seguido; arquivo offline ou redirecionado"); continue; }
                                if ((attributes & FileAttributes.Directory) != 0) { stack.Push((entry, matchingFolder)); continue; }
                                files++;
                                if (PathPolicy.Protected(entry)) { excluded++; continue; }
                                if (!matchingFolder && !Path.GetFileName(entry).Contains(query, StringComparison.OrdinalIgnoreCase)) continue;
                                if (candidates.Count >= CandidateLimit) { omitted++; continue; }
                                var info = new FileInfo(entry);
                                var candidate = new SearchCandidate(info.FullName, info.Length, info.LastWriteTimeUtc);
                                candidates.Add(candidate);
                                log?.Invoke("Candidato por nome/pasta", entry, $"{candidate.Size} bytes; somente revisão; não comprova que é cheat");
                            }
                            catch (Exception e) when (e is IOException or UnauthorizedAccessException)
                            { Inaccessible(entry, e); }
                        }
                    }
                    catch (Exception e) when (e is IOException or UnauthorizedAccessException)
                    { Inaccessible(directory, e); }
                }
            }
            progress?.Report(new(files, "Busca concluída"));
            return new(candidates, normalizedRoots, files, excluded, inaccessible, omitted);
        }
        finally
        {
            log?.Invoke("Resumo de busca", query,
                $"Arquivos vistos: {files}; candidatos: {candidates.Count}; excluídos: {excluded}; inacessíveis: {inaccessible}; candidatos omitidos: {omitted}; cancelada: {token.IsCancellationRequested}");
        }
    }
}

// Created only after explicit user recognition of an exact candidate, never from its name alone.
public sealed record ConfirmedTarget(string Path, long Length, string Sha256)
{
    public static ConfirmedTarget FromRecognition(SearchCandidate candidate, CancellationToken token = default)
    {
        PathPolicy.DemandFile(candidate.Path);
        var info = new FileInfo(candidate.Path);
        if (info.Length == 0) throw new IOException("Arquivo vazio não pode servir como amostra.");
        if (info.Length != candidate.Size || info.LastWriteTimeUtc != candidate.ModifiedUtc)
            throw new IOException("O arquivo mudou desde a busca. Pesquise novamente antes de confirmar.");
        using var stream = new FileStream(candidate.Path, FileMode.Open, FileAccess.Read, FileShare.Read);
        return new(candidate.Path, stream.Length, Digest(stream, token));
    }
    public bool Matches(string path, CancellationToken token = default)
    {
        if (!File.Exists(path) || PathPolicy.Protected(path) || PathPolicy.HasLink(path)) return false;
        if ((File.GetAttributes(path) & FileAttributes.Offline) != 0 || new FileInfo(path).Length != Length) return false;
        using var stream = File.OpenRead(path);
        return Digest(stream, token).Equals(Sha256, StringComparison.OrdinalIgnoreCase);
    }
    private static string Digest(Stream stream, CancellationToken token)
    {
        using var hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
        var buffer = new byte[1024 * 1024];
        int count;
        while ((count = stream.Read(buffer)) > 0)
        { token.ThrowIfCancellationRequested(); hash.AppendData(buffer, 0, count); }
        token.ThrowIfCancellationRequested();
        return Convert.ToHexString(hash.GetHashAndReset());
    }

}
