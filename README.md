# FiveM Deep Clean Manager

Aplicativo de manutenção para **Windows 10/11 x64**, em **C# / .NET 8 / WPF**. Interface em português, tema preto e azul, revisão dos componentes e autorização explícita antes da remoção. O arquivo original `gpo.html` permanece independente e inalterado.

## Compilar e gerar o executável

No Windows, instale o **SDK .NET 8** ou Visual Studio 2022 com a carga de trabalho **Desenvolvimento para desktop com .NET**. Abra `FiveMDeepCleanManager.sln` ou execute, na raiz deste repositório:

```powershell
dotnet build FiveMDeepCleanManager.sln -c Release
dotnet run --project tests/SafetyChecks -c Release
dotnet run --project tests/WindowsChecks -c Release
dotnet publish src/FiveMCleaner/FiveMCleaner.csproj -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -o artifacts/win-x64
```

Execute `artifacts/win-x64/FiveM Deep Clean Manager.exe`. A publicação autocontida inclui o runtime; o usuário final não precisa instalar .NET. O manifesto solicita elevação via UAC. O executável gerado não possui assinatura de distribuição: para uma distribuição pública, assine-o com certificado de assinatura de código da sua organização. O aplicativo não instala serviço próprio.

Também é possível compilar e publicar para Windows a partir do Linux graças a `EnableWindowsTargeting`. **WPF, UAC, Registro, Authenticode, restauração e operações de remoção só podem ser executados e validados no Windows.** O workflow GitHub Actions compila nas duas plataformas e executa os testes de integração somente no Windows. O workflow foi adicionado; sua execução no GitHub depende de publicar o código no repositório.

## Usar

1. Feche GTA V e FiveM e abra o aplicativo. Os caminhos do perfil analisado pertencem à conta elevada que executa o aplicativo.
2. Clique em **Continuar**. A lista mostra programas registrados, sem classificá-los automaticamente como cheats.
3. Escolha explicitamente o software a remover. Opcionalmente, importe um catálogo local de hashes confiáveis e escolha uma pasta adicional. Para executar somente manutenção de cache, deixe o programa sem seleção e marque a opção de cache.
4. Clique em **Analisar componentes**. Nenhum componente vem marcado. Revise tipo, caminho e evidência na tabela; marque individualmente as operações autorizadas.
5. Clique em **Confirmar remoção selecionada** e revise o resumo. A tentativa de ponto de restauração ocorre antes da primeira remoção. Se ela falhar, outra confirmação permite cancelar ou continuar sem esse recurso.
6. Aguarde a desinstalação e a verificação final. Instaladores oficiais podem abrir sua própria interface; confirme suas opções e termine-os para o aplicativo prosseguir.
7. Consulte **Abrir relatórios**. O resultado distingue componentes residuais, falhas e limitações; pode recomendar reinicialização. Execute outra análise após reiniciar quando necessário.

**Cancelar** impede novas operações ao término da operação corrente; não desfaz o que já foi realizado. Um instalador oficial ou comando do Windows em andamento não é encerrado à força. O fechamento da janela é bloqueado durante operações para evitar abandonar transações. Cancele e aguarde; se houver instalador aberto, conclua ou cancele pela interface dele.

## Evidências e limites de remoção

- Instalações são lidas das chaves de desinstalação HKLM/HKCU, nas visões de 32 e 64 bits.
- Um arquivo é elegível se possuir **SHA-256 conhecido do catálogo explicitamente importado**, ou se estiver em `InstallLocation` dedicado, sem sobreposição registrada com outro produto, com **assinatura Authenticode verificada pelo Windows** e editor correspondente ao campo `Publisher`. Um nome suspeito nunca é suficiente.
- A verificação de confiança mantém a validação de cadeia e revogação. Indisponibilidade de certificados/revogação pode impedir essa evidência; o programa preserva o arquivo em vez de contornar a verificação.
- Não existe banco de cheats universal ou inventado embutido. Loaders portáteis, arquivos sem assinatura e configurações desconhecidas precisam de hashes confiáveis. Sem catálogo, apenas a instalação registrada fornece o escopo de arquivos. Software sem registro pode ser analisado com catálogo e sem programa selecionado.
- Com catálogo, a busca inclui Local/Roaming AppData, ProgramData, Program Files, Program Files (x86), temporários, inicialização e pasta adicional. Cada raiz tem limite de 150.000 arquivos; diretórios inacessíveis e limites atingidos são informados como análise parcial. O acesso é somente ao perfil elevado atual e áreas comuns, não a todos os perfis do PC.
- Desinstaladores EXE precisam de assinatura válida do editor e localização dentro da instalação dedicada. Interpretadores como `cmd`, PowerShell e `rundll32` são recusados. MSI exige ProductCode correspondente à chave de instalação; o aplicativo usa o `msiexec.exe` do Windows e solicita que ele não reinicie automaticamente. Instaladores de terceiros mantêm sua própria lógica e interface.
- Processos são relacionados pelo caminho do executável identificado, com confirmação por seleção e verificação antes de encerrá-los. Não se encerra a árvore de processos indiscriminadamente.
- Entradas Run/RunOnce, serviços Win32 de processo próprio e tarefas com uma única ação são relacionados pelo caminho exato do executável identificado. Cada um aparece como operação separada, desmarcada. Entradas alteradas desde a análise são recusadas. A verificação final também considera caminhos identificados anteriormente, para detectar referências pendentes mesmo após a exclusão do executável.
- Serviços compartilhados, tarefas com múltiplas ações, atalhos `.lnk` sem hash conhecido e componentes ambíguos não são removidos automaticamente. Não há limpeza genérica do Registro, de extensões de shell ou de componentes de kernel. Drivers `.sys` são preservados; use o desinstalador oficial para sua remoção suportada.
- Arquivos são revalidados por hash antes da exclusão. A exclusão abre e bloqueia o arquivo, recusa reparse points no objeto aberto e usa o mesmo handle para verificar o hash e solicitar a remoção, reduzindo trocas entre verificação e exclusão. Arquivos ocupados ou sem permissão ficam no relatório; não são agendados silenciosamente para apagar ao reiniciar.
- Pastas da instalação aparecem separadamente e só podem ser excluídas quando vazias. Não se utiliza exclusão recursiva de diretórios de software. Configurações desconhecidas e dados pessoais são preservados; configurações residuais com hash conhecido podem ser selecionadas explicitamente.
- O ponto de restauração é uma tentativa verificada e depende de Proteção do Sistema e políticas do Windows; não substitui backup nem garante restauração de arquivos pessoais. O aplicativo não habilita a Proteção do Sistema nem contorna suas políticas.

## FiveM, GTA V e auditoria

A manutenção identifica a instalação padrão `%LOCALAPPDATA%\FiveM\FiveM.app`. Somente arquivos de `data\cache`, `data\server-cache` e `data\server-cache-priv` são apresentados para autorização; configurações pessoais e o restante da instalação permanecem protegidos. Instalações portáteis/customizadas do FiveM precisam de manutenção pelo procedimento oficial; o aplicativo não tenta adivinhar um diretório equivalente.

A integridade do GTA V é delegada ao launcher oficial: o botão Steam abre `steam://validate/271590`, específico do **GTA V Legacy**. Para Enhanced, Epic ou Rockstar, utilize **Verificar arquivos** no launcher correspondente; o botão Rockstar abre o suporte oficial. O aplicativo não afirma que a validação terminou nem substitui essa validação.

Não há modificação de anticheat, descarregamento de drivers, alteração de Prefetch/Amcache/USN, limpeza de histórico de execução ou exclusão de logs de segurança. Há bloqueios para diretórios do Windows, instalações de jogos reconhecidas, diretórios de anticheat, logs, históricos, arquivos de auditoria e diretórios redirecionados. Arquivos em instalações personalizadas do GTA V também são protegidos quando um executável GTA5 está presente em um ancestral. Esses bloqueios são camadas de defesa; não constituem certificação contra um sistema já comprometido. Não use catálogos não confiáveis.

Relatórios incrementais **JSONL e TXT** são gravados em:

```text
%LOCALAPPDATA%\FiveMDeepCleanManager\Reports\clean-<data>-<id>.jsonl
%LOCALAPPDATA%\FiveMDeepCleanManager\Reports\clean-<data>-<id>.txt
```

Incluem componentes encontrados, evidências, autorização negada, operações tentadas e resultados, arquivos preservados sem evidência, erros e resíduos da nova busca. São gravados antes e depois das operações; falha na escrita interrompe a limpeza. Relatórios contêm caminhos locais e metadados de instalação: revise-os antes de compartilhar. A nova busca não comprova ausência de software desconhecido.

## Catálogo de hashes

Formato JSON (substitua o texto explicativo por um hash hexadecimal real de 64 caracteres):

```json
{
  "program": "Nome exato exibido na lista de programas",
  "files": {
    "loader.exe": "<SHA-256 de 64 caracteres obtido de uma fonte confiável>",
    "settings.json": "<SHA-256 de 64 caracteres obtido de uma fonte confiável>"
  }
}
```

O campo `program` precisa corresponder ao programa selecionado. Sem seleção de programa, é um identificador do catálogo. As chaves são nomes simples, sem caminhos; hashes são conferidos no conteúdo, não pelo nome. O formato suporta um hash por nome; para outras versões, importe outro catálogo. Pode-se obter o hash de uma amostra confiável com `Get-FileHash -Algorithm SHA256`. Não execute amostras de cheats para criar catálogos. A origem/autenticidade do catálogo precisa ser verificada por quem o importa; o aplicativo não faz download de listas externas.

## Organização e validação

```text
FiveMDeepCleanManager.sln
src/FiveMCleaner/
  App.xaml                  Recursos visuais e tratamento de exceções
  MainWindow.xaml           Interface WPF
  MainWindow.xaml.cs        Fluxo, seleção, confirmação e cancelamento
  CleanEngine.cs            Análise, evidências, remoção e auditoria
  PathPolicy.cs             Escopo e bloqueios de caminhos
  ProcessPolicy.cs          Identificação dos processos do jogo
  Models.cs                 Modelos de instalação, componentes e relatório
  app.manifest              Elevação UAC e compatibilidade Windows
 tests/SafetyChecks/         Testes executáveis de políticas de caminhos
 tests/WindowsChecks/        Testes de remoção em arquivos temporários próprios
.github/workflows/build.yml Compilação e testes no CI
```

Os testes Windows usam exclusivamente arquivos temporários criados pelo próprio teste. Não removem produtos instalados, serviços, tarefas ou entradas reais de inicialização. Antes de distribuir, valide em uma VM Windows descartável: UAC, interface, assinatura/revogação, ponto de restauração indisponível, cancelamento durante instalador, arquivos ocupados, serviço de teste, tarefa de teste e entradas de inicialização de teste. A compilação cruzada não verifica essas integrações.
