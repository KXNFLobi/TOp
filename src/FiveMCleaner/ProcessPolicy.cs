using System.Text.RegularExpressions;
namespace FiveMCleaner;
public static class ProcessPolicy
{
    public static bool IsGame(string name) => Regex.IsMatch(name,
        @"^(GTA5(_Enhanced)?(_BE)?|PlayGTAV|FiveM(_.*)?)$", RegexOptions.IgnoreCase);
}
