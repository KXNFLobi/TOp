# Registro de validação — 24/10/2026

Ambiente de execução: Linux x64, SDK .NET 8.0.426. Compilação cruzada para Windows.

## Executado e aprovado

- `dotnet build FiveMDeepCleanManager.sln -c Release`: três projetos compilados; zero erros e zero avisos.
- `dotnet run --project tests/SafetyChecks -c Release --no-build`: **30 verificações aprovadas**, incluindo fronteiras de diretórios, traversal, reparse points, proteção de jogos/anticheat/auditoria/drivers, escopo do cache e identificação de processos sem confundir o gerenciador com FiveM.
- `dotnet publish src/FiveMCleaner/FiveMCleaner.csproj -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -o artifacts/win-x64`: executável autocontido gerado.
- Arquivo de saída reconhecido como PE32+ GUI x86-64 para Windows.
- `gpo.html` original preservado sem alterações.

## Compilado, mas não executado neste ambiente

`tests/WindowsChecks`: testes de exclusão por handle de fixture com hash conhecido, preservação de arquivo alterado, rejeição de hash desconhecido, cancelamento, preservação de auditoria e gravação do relatório. Esses testes só executam no Windows e não removem programas, serviços ou tarefas instalados.

## Integração que exige validação manual em Windows

- Renderização WPF, elevação UAC e interação com a interface.
- Assinatura Authenticode e acesso à revogação de certificados.
- Criação e falha de ponto de restauração.
- Desinstalador EXE/MSI de um produto de teste.
- Serviço de processo próprio, tarefa de ação única e entrada Run/RunOnce de teste.
- Cancelamento durante operação e comportamento de arquivos ocupados.
- Cache do FiveM e delegação de integridade ao launcher oficial.

A geração do executável não certifica essas integrações. A distribuição pública deve ocorrer após teste em VM Windows descartável e assinatura de código. Não foi executada limpeza em um computador Windows real nesta sessão. O executável é distribuído sem assinatura de código.

## Atualização visual 1.0.1

Templates escuros explícitos adicionados ao ComboBox, itens e barra de rolagem da lista de programas. Publicação cruzada Windows x64 autocontida concluída sem erros ou avisos. A alteração é visual; os 30 testes registrados acima correspondem à lógica de segurança, que não foi alterada. A aparência atualizada ainda requer conferência no Windows.

## Atualização de busca 1.1.0

- Busca somente de leitura por nome/pasta nas unidades locais fixas, com relatório de exclusões, acessos indisponíveis e candidatos omitidos.
- Janela de reconhecimento explícito e análise de cópias byte a byte idênticas por SHA-256; nenhum arquivo é autorizado apenas por nome.
- A suíte agora inclui 45 verificações, cobrindo descoberta em Downloads sem informar o caminho, busca em mais de uma raiz, exclusão de auditoria, candidato falso de mesmo tamanho, confirmação de amostra, cópia renomeada, modificação posterior, cancelamento e limite explícito de candidatos.
- Os testes Windows incluem a remoção separadamente autorizada de uma cópia da amostra reconhecida; sua execução ainda exige Windows.
- Renderização das novas telas, enumeração real das unidades Windows e integrações de remoção ainda exigem validação em VM Windows. Não foi feita varredura no computador do usuário nesta sessão.
