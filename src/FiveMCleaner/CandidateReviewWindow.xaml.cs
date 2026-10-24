using System.Windows;
using System.Windows.Controls;
namespace FiveMCleaner;
public partial class CandidateReviewWindow : Window
{
    public SearchCandidate? RecognizedFile { get; private set; }
    public CandidateReviewWindow(ComputerSearchResult result)
    {
        InitializeComponent();
        Candidates.ItemsSource = result.Candidates.OrderBy(c => System.IO.Path.GetExtension(c.Path).Equals(".exe", StringComparison.OrdinalIgnoreCase) ? 0 : 1).ThenBy(c => c.Path);
        Summary.Text = $"{result.Files:N0} arquivos vistos • {result.Candidates.Count} candidatos • {result.Inaccessible} acessos indisponíveis • {result.Excluded} exclusões de proteção. {(result.OmittedCandidates > 0 ? $"Mais {result.OmittedCandidates} candidatos omitidos pelo limite de 2.000; refine o nome para outra busca." : "")}\nA busca não comprova ausência de software renomeado ou versões diferentes.";
    }
    private void Candidate_Changed(object sender, SelectionChangedEventArgs e)
    {
        if (CandidatePath == null || Recognized == null) return;
        CandidatePath.Text = (Candidates.SelectedItem as SearchCandidate)?.Path ?? "";
        Recognized.IsChecked = false;
    }
    private void Confirm_Click(object sender, RoutedEventArgs e)
    {
        if (Candidates.SelectedItem is not SearchCandidate candidate || Recognized.IsChecked != true)
        { MessageBox.Show("Selecione o arquivo e confirme que o reconhece. Se não tiver certeza, volte sem autorizar."); return; }
        RecognizedFile = candidate; DialogResult = true;
    }
}
