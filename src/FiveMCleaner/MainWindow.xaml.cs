using System.IO;
using Microsoft.Win32;
using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Diagnostics;
using System.Security.Principal;
using System.Text.Json;
using System.Windows;
using System.Windows.Media.Animation;
namespace FiveMCleaner;
public partial class MainWindow : Window
{
    private readonly CleanEngine engine = new();
    private CancellationTokenSource? cancellation;
    private ObservableCollection<Finding> rows = [];
    private InstalledProgram? analyzedProgram;
    private HashCatalog? analyzedCatalog;
    private string analyzedExtra = "";
    private bool analyzedCache;
    private bool busy;
    public MainWindow() { InitializeComponent(); Closing += OnClosing; }
    private void OnClosing(object? sender, CancelEventArgs e) { if (busy) { e.Cancel = true; MessageBox.Show("Use Cancelar e aguarde a operação atual terminar. Desinstaladores oficiais precisam concluir sua transação."); } }
    private void SetProgress(int percent, string text) { Dispatcher.Invoke(() => { var previous = Progress.Value; Progress.BeginAnimation(System.Windows.Controls.Primitives.RangeBase.ValueProperty, null); Progress.Value = percent; Progress.BeginAnimation(System.Windows.Controls.Primitives.RangeBase.ValueProperty, new DoubleAnimation(previous, percent, TimeSpan.FromMilliseconds(250)) { FillBehavior = FillBehavior.Stop }); Percent.Text = percent + "%"; Status.Text = text; }); }
    private void Busy(bool value) { busy = value; Workspace.IsEnabled = true; Programs.IsEnabled = !value; AnalyzeButton.IsEnabled = !value; ExtraFolder.IsEnabled = !value; CacheOption.IsEnabled = !value; CancelButton.IsEnabled = value; CleanButton.IsEnabled = !value && rows.Count > 0; }
    private async void Continue_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            if (!new WindowsPrincipal(WindowsIdentity.GetCurrent()).IsInRole(WindowsBuiltInRole.Administrator)) throw new InvalidOperationException("Reabra como administrador.");
            Welcome.Visibility = Visibility.Collapsed; Workspace.Visibility = Visibility.Visible; Busy(true);
            SetProgress(5, "Lendo programas registrados no Windows…");
            Programs.ItemsSource = await Task.Run(CleanEngine.Programs);
            SetProgress(10, "Escolha o software. A lista não classifica programas como cheats.");
        }
        catch (Exception ex) { ShowError(ex); }
        finally { Busy(false); }
    }
    private void ClearProgram_Click(object sender,RoutedEventArgs e){if(busy)return;Programs.SelectedIndex=-1;InvalidateAnalysis();}
    private void Folder_Click(object sender, RoutedEventArgs e) { if (busy) return; var dialog = new OpenFolderDialog { Title = "Pasta adicional para procurar hashes do catálogo" }; if (dialog.ShowDialog() == true) ExtraFolder.Text = dialog.FolderName; InvalidateAnalysis(); }
    private void Catalog_Click(object sender, RoutedEventArgs e)
    {
        if (busy) return; var dialog = new OpenFileDialog { Filter = "Catálogo JSON|*.json" }; if (dialog.ShowDialog() != true) return;
        try
        {
            var catalog = JsonSerializer.Deserialize<HashCatalog>(File.ReadAllText(dialog.FileName), new JsonSerializerOptions { PropertyNameCaseInsensitive = true }) ?? throw new IOException("Catálogo vazio");
            if (string.IsNullOrWhiteSpace(catalog.Program) || catalog.Files == null || catalog.Files.Count == 0 || catalog.Files.Any(kv => string.IsNullOrWhiteSpace(kv.Key) || System.IO.Path.GetFileName(kv.Key) != kv.Key || !System.Text.RegularExpressions.Regex.IsMatch(kv.Value ?? "", "^[a-fA-F0-9]{64}$"))) throw new IOException("Informe Program e Files com nomes simples e hashes SHA-256 de 64 dígitos hexadecimais.");
            engine.Catalog = catalog with { Files = new Dictionary<string, string>(catalog.Files, StringComparer.OrdinalIgnoreCase) };
            CatalogInfo.Text = $"{catalog.Program}: {catalog.Files.Count} hashes. Use somente catálogos de origem confiável."; InvalidateAnalysis();
        }
        catch (Exception ex) { ShowError(ex); }
    }
    private void InvalidateAnalysis() { rows.Clear(); Findings.ItemsSource = rows; CleanButton.IsEnabled = false; SetProgress(0, "Configuração alterada: analise novamente."); }
    private async void Analyze_Click(object sender, RoutedEventArgs e)
    {
        if (busy) return;
        analyzedProgram = Programs.SelectedItem as InstalledProgram; analyzedCatalog = engine.Catalog; analyzedExtra = ExtraFolder.Text; analyzedCache = CacheOption.IsChecked == true;
        if (analyzedProgram == null && analyzedCatalog == null && !analyzedCache) { MessageBox.Show("Selecione um programa, carregue um catálogo conhecido ou habilite a manutenção de cache."); return; }
        if (analyzedProgram != null && analyzedCatalog != null && !analyzedProgram.Name.Equals(analyzedCatalog.Program, StringComparison.OrdinalIgnoreCase)) { MessageBox.Show("O campo Program do catálogo deve corresponder exatamente ao programa selecionado."); return; }
        Busy(true); cancellation = new(); rows = []; Findings.ItemsSource = rows;
        try
        {
            SetProgress(15, "Verificação inicial e busca de evidências…");
            var found = await Task.Run(() => engine.Analyze(analyzedProgram, analyzedExtra, analyzedCache, cancellation.Token));
            rows = new(found); Findings.ItemsSource = rows;
            SetProgress(45, $"Análise concluída: {rows.Count} componentes. Nenhum foi selecionado automaticamente.");
            if (engine.Warnings.Count > 0) MessageBox.Show("A análise tem limitações; não comprova ausência de componentes.\n\n" + string.Join("\n", engine.Warnings.Take(8)) + "\n\nDetalhes no relatório.", "Limitações da análise");
            if (rows.Count == 0) MessageBox.Show("Nenhum componente com evidência suficiente foi encontrado. Caminhos ausentes, arquivos sem assinatura ou sem hash conhecido não são autorizados para remoção. Use o desinstalador nas configurações do Windows quando necessário.");
        }
        catch (OperationCanceledException) { SetProgress(0, "Análise cancelada; nenhuma remoção realizada."); }
        catch (Exception ex) { ShowError(ex); }
        finally { cancellation?.Dispose(); cancellation = null; Busy(false); }
    }
    private async void Clean_Click(object sender, RoutedEventArgs e)
    {
        if (busy) return; Findings.CommitEdit(); Findings.CommitEdit(System.Windows.Controls.DataGridEditingUnit.Row, true);
        if (!Equals(Programs.SelectedItem, analyzedProgram) || engine.Catalog != analyzedCatalog || ExtraFolder.Text != analyzedExtra || (CacheOption.IsChecked == true) != analyzedCache) { InvalidateAnalysis(); return; }
        var selected = rows.Where(f => f.Selected).OrderBy(f => f.Kind switch { "Processo" => 0, "Desinstalador" => 1, "Serviço" => 2, "Tarefa" => 3, "Inicialização" => 4, "Pasta vazia" => 6, _ => 5 }).ToList();
        if (selected.Count == 0) { MessageBox.Show("Marque os componentes que autoriza remover."); return; }
        var groups = string.Join("\n", selected.GroupBy(f => f.Kind).Select(g => $"• {g.Key}: {g.Count()}"));
        if (MessageBox.Show($"Autoriza estas operações?\n\n{groups}\n\nArquivos serão excluídos permanentemente. O ponto de restauração não recupera todos os arquivos pessoais. Serviços, tarefas e entradas de inicialização marcados serão removidos. Processos marcados serão encerrados sem salvar dados.\n\nO desinstalador oficial pode ter sua própria interface e remover componentes adicionais do produto. Revise as opções que ele apresentar.", "Confirmar operações irreversíveis", MessageBoxButton.YesNo, MessageBoxImage.Warning, MessageBoxResult.No) != MessageBoxResult.Yes) return;
        Busy(true); cancellation = new();
        bool canceled = false; int failures = 0; bool complete = false;
        try
        {
            foreach (var f in rows.Where(f => !f.Selected)) engine.Log("Não autorizado", f.Path, "Preservado por escolha do usuário");
            CleanEngine.CheckGames(); SetProgress(50, "Tentando criar ponto de restauração…");
            await Task.Run(() => engine.RestorePoint(cancellation.Token));
            if (engine.Warnings.Any(w => w.StartsWith("Ponto de restauração")) && MessageBox.Show("Não foi possível confirmar um ponto de restauração. A remoção continua irreversível. Deseja prosseguir mesmo assim?", "Restauração indisponível", MessageBoxButton.YesNo, MessageBoxImage.Warning, MessageBoxResult.No) != MessageBoxResult.Yes) { canceled = true; return; }
            for (int i = 0; i < selected.Count; i++)
            {
                cancellation.Token.ThrowIfCancellationRequested(); var f = selected[i]; SetProgress(55 + (int)(30.0 * i / selected.Count), $"{f.Kind}: {f.Path}");
                try { await Task.Run(() => engine.Execute(f, analyzedProgram, cancellation.Token)); }
                catch (OperationCanceledException) { throw; }
                catch (Exception ex) { failures++; f.Outcome = "Não removido: " + ex.Message; engine.Log("Falha", f.Path, ex.Message); }
            }
            cancellation.Token.ThrowIfCancellationRequested(); SetProgress(90, "Verificação final: nova busca pelos componentes…");
            var remaining = await Task.Run(() => engine.Analyze(analyzedProgram, analyzedExtra, analyzedCache, cancellation.Token, true));
            var residuals = remaining.Where(f => f.Kind != "Desinstalador").ToList();
            foreach (var f in residuals) engine.Log("Residual", f.Path, f.Evidence);
            foreach (var f in remaining.Where(f => f.Kind == "Desinstalador")) engine.Log("Registro de instalação ainda presente", f.Path, f.Evidence);
            bool incomplete = failures > 0 || remaining.Count > 0 || engine.Warnings.Count > 0;
            complete = true; SetProgress(100, incomplete ? "Limpeza concluída com pendências — consulte o relatório." : "Limpeza concluída");
            using (var key = Registry.LocalMachine.OpenSubKey(@"SYSTEM\CurrentControlSet\Control\Session Manager")) if (key?.GetValue("PendingFileRenameOperations") != null) engine.Log("Reinicialização", "Windows", "Há operações pendentes no sistema; podem ser anteriores à sessão.");
            engine.Log("Resumo", "Sessão", $"Concluída; falhas {failures}; componentes ainda encontrados {remaining.Count}; limitações {engine.Warnings.Count}; reinicialização {engine.RebootRequired}");
            MessageBox.Show($"Limpeza concluída{(incomplete ? " com pendências" : "")}.\n\nFalhas: {failures}\nComponentes ainda encontrados: {remaining.Count}\nLimitações na verificação: {engine.Warnings.Count}\n{(engine.RebootRequired ? "Reinicie o Windows para concluir remoções de serviços ou instaladores." : "Consulte o relatório para eventuais operações de reinicialização já pendentes no Windows.")}\n\nRelatório: {engine.ReportPath}", "Resultado");
        }
        catch (OperationCanceledException) { canceled = true; engine.Log("Cancelamento", "Sessão", "Solicitado; operações concluídas não foram revertidas; verificação final pode estar incompleta."); }
        catch (Exception ex) { ShowError(ex); }
        finally
        {
            if (canceled) { foreach (var f in selected.Where(f => f.Outcome == "Aguardando")) f.Outcome = "Não executado"; SetProgress((int)Progress.Value, "Limpeza cancelada. Operações já concluídas foram preservadas no relatório."); }
            else if (!complete) SetProgress((int)Progress.Value, "Operação interrompida. Consulte o relatório e analise novamente.");
            cancellation?.Dispose(); cancellation = null; Busy(false); CleanButton.IsEnabled = false;
        }
    }
    private void Cancel_Click(object sender, RoutedEventArgs e) { cancellation?.Cancel(); Status.Text = "Cancelamento solicitado; aguardando operação atual. Instaladores não serão interrompidos."; }
    private void Reports_Click(object sender, RoutedEventArgs e) { try { Process.Start(new ProcessStartInfo(engine.ReportDirectory) { UseShellExecute = true }); } catch (Exception ex) { ShowError(ex); } }
    private void Steam_Click(object sender, RoutedEventArgs e) { if (MessageBox.Show("Abrir a validação oficial Steam do GTA V Legacy (app 271590)? Para Enhanced ou outra loja, use a opção Verificar arquivos do launcher correspondente. O jogo precisa permanecer fechado durante a limpeza.", "Integridade oficial", MessageBoxButton.YesNo) != MessageBoxResult.Yes) return; Open("steam://validate/271590"); }
    private void Rockstar_Click(object sender, RoutedEventArgs e) => Open("https://support.rockstargames.com/");
    private void Open(string target) { try { Process.Start(new ProcessStartInfo(target) { UseShellExecute = true }); } catch (Exception ex) { ShowError(ex); } }
    private void ShowError(Exception ex) { try { engine.Log("Erro", "Aplicativo", ex.Message); } catch {/* Do not continue destructive work if audit writing fails. */} SetProgress((int)Progress.Value, "Operação interrompida: " + ex.Message); MessageBox.Show(ex.Message, "Não foi possível concluir", MessageBoxButton.OK, MessageBoxImage.Error); }
}
