# Baixar FiveM Deep Clean Manager — versão 1.1.0

Abra o arquivo **FiveM-Deep-Clean-Manager-win-x64.zip** acima e use **Download raw file** (ícone de download) no GitHub. Se o GitHub disser que o arquivo é grande demais para visualizar, use **View raw** para baixá-lo.

Depois de baixar no Windows, clique com o botão direito no ZIP, escolha **Extrair Tudo** e abra **FiveM Deep Clean Manager.exe**. O aplicativo solicita permissão de administrador.

O ZIP **FiveM-Deep-Clean-Manager-source.zip** contém o código-fonte. As instruções de compilação estão no README da raiz do repositório.

O executável não tem assinatura de código. A compilação cruzada e 45 testes de políticas de segurança e descoberta passaram no Linux. A interface e as integrações específicas do Windows ainda precisam ser validadas em uma VM Windows antes de uma distribuição pública; consulte `VALIDATION.md`.

`SHA256SUMS.txt` contém os hashes do executável dentro do ZIP e dos dois arquivos ZIP. O caminho `win-x64/` listado para o executável corresponde à pasta de publicação usada na geração.

Na versão 1.1.0, a caixa de seleção de programas, a lista aberta e sua barra de rolagem usam fundo escuro. Feche o executável antigo e extraia o ZIP atualizado em uma nova pasta antes de abrir.

Na versão 1.1.0, use **Buscar no PC inteiro**, com o nome **Loard**, para procurar candidatos sem informar a pasta. Depois reconheça um arquivo na janela de revisão para analisar cópias idênticas e componentes relacionados. Nenhuma exclusão é autorizada só pelo nome. A busca exclui áreas protegidas e inacessíveis e não apaga históricos de execução ou auditoria.


## Universal Game Booster Pro (Python / PySide6)

O novo aplicativo fica separado em `universal-game-booster-pro/`. Baixe **Universal-Game-Booster-Pro-source.zip**, extraia, instale Python 3.12 e execute `run.cmd` (a primeira execução instala as dependências). Consulte o README dentro do ZIP.

Para gerar o executável sem Python no PC de destino, abra **Actions → Universal Game Booster Pro - Windows**, selecione uma execução concluída da branch `fivem-deep-clean-manager` e baixe o artefato **UniversalGameBoosterPro-Windows-x64**. A geração ocorre no runner Windows, não neste ambiente Linux; confira o status da execução antes de procurar o artefato.

O modo de simulação vem ligado e os processos desconhecidos ficam protegidos. Não há promessa de ganho de FPS nem limpeza agressiva de RAM.


### Instalador para clientes — não exige Python

Use **UniversalGameBoosterPro-Setup.exe** após a conclusão do workflow Windows. O instalador contém os runtimes e instala o aplicativo para o usuário atual. O ZIP `Universal-Game-Booster-Pro-source.zip` é para desenvolvimento, não para entregar a clientes.

A publicação automática do Setup só ocorre depois de compilar, verificar os runtimes e testar instalação, abertura, fechamento normal e desinstalação em Windows. Confira o arquivo `UniversalGameBoosterPro-Setup-BUILD.txt` para o commit de origem e o SHA-256 no arquivo correspondente.


### FPS no painel — Game Booster Pro 1.1.0

O Setup atualizado inclui PresentMon. Abra o jogo, selecione seu processo em **Jogo para FPS** e clique em **Mostrar FPS**. A leitura ETW pode exigir reabrir como administrador mediante autorização do Windows. **Parar FPS** encerra somente o coletor particular; não fecha o jogo. O valor é FPS de apresentação, não uma estimativa de CPU/GPU. A captura e a preservação da aplicação gráfica durante a parada foram verificadas no runner Windows.
