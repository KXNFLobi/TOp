using System.Windows;
namespace FiveMCleaner;
public partial class App : Application
{
    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);
        DispatcherUnhandledException += (_, args) =>
        {
            MessageBox.Show("Operação interrompida: " + args.Exception.Message, "Falha", MessageBoxButton.OK, MessageBoxImage.Error);
            args.Handled = true;
        };
    }
}
