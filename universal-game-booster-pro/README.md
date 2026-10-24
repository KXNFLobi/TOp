# Universal Game Booster Pro

Aplicativo desktop em **Python 3.12 + PySide6** para Windows 10/11 x64. Monitoramento real, perfis por jogo, solicitação de fechamento normal de aplicativos autorizados e um único ajuste opcional de energia com recuperação persistente. Não promete FPS, não injeta código em jogos e não faz limpeza agressiva de memória.

## Distribuir para clientes: sem Python

O cliente recebe **UniversalGameBoosterPro-Setup.exe**, e não o ZIP do código. O instalador inclui o aplicativo, Python embutido, Qt/PySide6 e psutil; não requer `py`, `pip`, Python instalado ou acesso à Internet para instalar/executar. Instala somente para o usuário atual, cria atalho no menu Iniciar e oferece atalho na área de trabalho. Não ativa autostart nem muda planos de energia durante a instalação.

O workflow Windows compila o bundle e o instalador Inno Setup, verifica as DLLs dos runtimes, instala em uma pasta temporária, abre a interface empacotada, solicita fechamento normal e testa a desinstalação. Somente depois publica o Setup em `downloads/UniversalGameBoosterPro-Setup.exe` na branch `fivem-deep-clean-manager`, com SHA-256 e commit de origem. Se a política do repositório impedir o commit automático, o instalador continua disponível como artefato **UniversalGameBoosterPro-Setup** da execução bem-sucedida em Actions.

Para distribuição pública, assine o Setup e o executável com um certificado de assinatura de código de sua organização. Este projeto não inventa assinatura de editor. Um instalador não assinado pode receber alertas do Windows; não é necessário nem recomendado desativar proteções de segurança.

Para compilar localmente, use `build.cmd` em um PC de desenvolvimento com Python 3.12 e Inno Setup 6. **Só a máquina de compilação precisa dessas ferramentas; os clientes não.** O bundle portátil também funciona sem Python, desde que toda a pasta de saída seja distribuída junto.

## Baixar e executar

O código fica nesta pasta, separado do FiveM Deep Clean Manager. O ZIP do código está em `downloads/Universal-Game-Booster-Pro-source.zip` na raiz do repositório.

**Executável Windows pelo GitHub:** abra **Actions → Universal Game Booster Pro - Windows**, selecione uma execução concluída para a branch `fivem-deep-clean-manager` e baixe o artefato **UniversalGameBoosterPro-Windows-x64**. Extraia **todos os arquivos** juntos e abra `UniversalGameBoosterPro.exe`. O workflow gera o executável em um runner Windows; a existência do workflow não comprova que uma execução terminou com sucesso. O executável não é assinado para distribuição. Não precisa de Python quando gerado pelo PyInstaller.

**Executar pelo código:** instale Python **3.12** oficial, extraia o ZIP, execute `setup.cmd` e depois `run.cmd`. Não é necessário abrir como administrador. Para compilar seu próprio executável, execute `build.cmd` no Windows. O programa completo estará em `dist\UniversalGameBoosterPro`; mantenha a pasta `_internal` junto do `.exe`.

Comandos equivalentes:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python main.py
# Compilar no Windows:
.venv\Scripts\python -m pip install -r requirements-build.txt
.venv\Scripts\python -m unittest discover -s tests -v
.venv\Scripts\python -m PyInstaller --noconfirm --clean --onedir --windowed --name UniversalGameBoosterPro main.py
```

PyInstaller **não compila executáveis Windows a partir do Linux**. A interface e o modo de monitoramento podem ser testados no Linux; ações de fechamento, energia e inicialização automática ficam indisponíveis nessa plataforma.

## Como usar

1. Aguarde as primeiras medições. CPU, RAM, I/O agregado de disco e processos vêm do sistema, sem dados de demonstração.
2. Na aba **APLICATIVOS**, pesquise por nome, PID, caminho ou motivo de proteção. A primeira caixa significa **Fechar**; **Manter** sempre tem prioridade. A estrela marca favoritos. As escolhas são salvas automaticamente no perfil atual.
3. **Selecionar aplicativos seguros** marca apenas aplicações elegíveis já verificadas, sem incluir as que estão em Manter. **Desmarcar todos** desmarca a lista de fechamento; não remove proteções nem a lista Manter. **Manter selecionados abertos** move a seleção de fechamento para Manter.
4. **OTIMIZAR MEU PC AGORA** usa as escolhas de fechamento do perfil. Se não houver escolhas, propõe aplicações elegíveis com pelo menos 150 MiB de RSS ou 5% de CPU normalizada. **Fechar aplicativos selecionados** usa somente a seleção explícita. Ambos exibem prévia e exigem confirmação.
5. **Modo de simulação vem ligado.** Ele registra o que seria solicitado sem fechar aplicativos e sem alterar energia. As medições antes/depois continuam reais e podem variar naturalmente, sem representar ganhos provocados pela simulação.
6. Para uma operação real, salve seu trabalho, desmarque Simulação, confira a prévia e autorize. Cada aplicativo recebe somente `WM_CLOSE`, como ao fechar uma janela. Ele pode pedir para salvar, negar o fechamento ou continuar na bandeja. O gerenciador não passa por cima dessas decisões.
7. Confira **RESULTADOS E HISTÓRICO**: RAM, CPU, processos e memória disponível antes/depois; solicitação por aplicativo e se o processo original ainda foi visto. Variações não provam causalidade nem aumento de FPS.

## Proteções de processos

O inventário mostra processos acessíveis e também entradas inacessíveis como protegidas. Para ser elegível, o processo precisa simultaneamente:

- pertencer ao usuário atual e ter identidade executável conhecida;
- não ser serviço, processo crítico (`IsProcessCritical`), processo do gerenciador, jogo cadastrado, launcher, antivírus, anticheat, driver ou componente/periférico protegido;
- ter janela visível e pertencer à lista restrita de aplicações desktop reconhecidas;
- ter assinatura Authenticode válida e editor esperado verificados por ferramenta do Windows.

A lista inicial contempla Chrome, Edge, Firefox, Brave, Spotify, Discord, Telegram e WhatsApp **apenas quando a assinatura, a edição instalada e as demais condições forem reconhecidas**. Ausência de assinatura, editor diferente, aplicação UWP/sem janela ou acesso insuficiente mantêm proteção. Não se permite transformar arbitrariamente um processo desconhecido em processo seguro. Versões adicionais exigem revisão da política em `booster/safety.py`.

Processos são revalidados por PID, horário de criação, executável, usuário, serviço, criticidade, editor e HWND antes da solicitação. Não se usa `kill`, `terminate`, suspensão, manipulação de memória de outro processo ou fechamento de árvores. A lista Manter é respeitada pela seleção das ações. Jogos desconhecidos permanecem protegidos porque não pertencem à allowlist de aplicativos desktop assinados.

Essas verificações são barreiras conservadoras, não uma certificação de um sistema já comprometido. Não é um antivírus ou ferramenta de remoção de cheats.

## Meus jogos e Game Boost

**Detectar jogos instalados** lê bibliotecas/manifestos Steam e Epic e localizações padrão de FiveM/Roblox; não modifica arquivos nem tenta lançar executáveis encontrados. A descoberta Steam é limitada a quatro níveis e 5.000 entradas por instalação para evitar varreduras descontroladas. A lista pode conter mais de um executável do mesmo jogo: confirme o executável principal. Outros jogos, lojas, versões e bibliotecas podem ser adicionados manualmente pelo `.exe`.

Qualquer executável adicionado fica protegido. Selecione um jogo, use seu perfil e edite Fechar/Manter na aba Aplicativos. Perfis são associados ao caminho completo, evitando colisão entre jogos com o mesmo nome.

**GAME BOOST MODE** é opcional e vem desligado. Detecta executáveis cadastrados entre processos ativos e oferece abrir a prévia do perfil, sem aplicar fechamento automaticamente. Não acessa memória de jogos nem integra com anticheat. A detecção depende do caminho ser acessível ao usuário atual; um processo protegido pelo sistema pode não disponibilizá-lo.

## Energia e restauração

O único ajuste de desempenho do Windows é **Alto Desempenho temporário**, opcional, desligado por padrão e confirmado na prévia. O programa consulta o plano ativo, verifica se o plano padrão Alto Desempenho existe e usa `powercfg /setactive`. **Não cria planos**, não altera limites de CPU, Registro de desempenho ou configurações críticas. Alguns notebooks/Modern Standby não oferecem esse plano; a falha é informada sem contornar a política.

O GUID original é persistido **antes** da alteração. O plano é restaurado quando os jogos acompanhados terminam, ao clicar em **Restaurar ajustes temporários** ou ao fechar o aplicativo normalmente. Em caso de crash/reinicialização, o estado fica salvo e a próxima abertura avisa que há recuperação pendente. Não há serviço instalado que restaure o plano enquanto o gerenciador estiver fechado.

A restauração automática não substitui um plano escolhido posteriormente fora do programa; nesse caso, a recuperação permanece salva e o usuário pode restaurar explicitamente. Se a restauração falhar na saída, é possível sair mantendo a recuperação para a próxima sessão. Alto Desempenho pode aumentar consumo e temperatura e não garante melhora. Fechar aplicativos é uma ação que não pode recuperar trabalho perdido; o botão Restaurar não reabre suas sessões.

## Monitoramento e medições

- **CPU:** `psutil.cpu_percent`; por processo, utilização normalizada pelo número de CPUs lógicas. A primeira amostra precisa de aquecimento.
- **RAM:** uso do sistema estimado por total menos disponível e RSS de cada processo. RSS pode conter páginas compartilhadas; não é somado para prometer economia.
- **Disco:** taxa agregada de bytes lidos/escritos, em MiB/s, entre amostras; não representa tempo ativo do disco. Primeiro intervalo fica aguardando amostra.
- **GPU:** NVIDIA por `nvidia-smi`, quando disponível. Caso contrário, contadores oficiais WDDM via `Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine`, para drivers compatíveis AMD/Intel/NVIDIA. Soma processos do mesmo motor e exibe o motor mais ocupado; não soma percentuais de motores diferentes. Essa fonte não fornece temperatura.
- **Temperaturas:** NVIDIA quando fornecida pelo driver e CPU quando `psutil` disponibiliza sensor confiável. No Windows, CPU frequentemente fica indisponível. Não se inventam leituras de WMI/ACPI para preencher os campos.
- GPU é consultada em segundo plano a cada cinco segundos, sem travar o monitor de CPU/RAM; amostras vencidas são descartadas. Hardware, permissões ou drivers sem fonte resultam em **Indisponível**.
- CPU/RAM/GPU elevadas são observações, não diagnóstico comprovado de gargalo. **FPS não é exibido**: não há integração homologada com ferramenta de captura de frames.

## Preferências, relatórios e inicialização

Preferências, perfis, favoritos, recuperação de energia e até 200 registros de histórico ficam em `%LOCALAPPDATA%\UniversalGameBoosterPro\preferences.json`. Logs rotativos ficam na mesma pasta. A gravação é atômica. Preferências inválidas são preservadas em `preferences.invalid.json` antes de usar os padrões. Relatórios incluem caminhos de executáveis e PIDs; revise antes de compartilhar.

**Iniciar com Windows** é opcional e usa somente uma entrada do próprio aplicativo em `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`. Desmarcar remove somente essa entrada. Se mover a instalação, reconfigure a opção para atualizar o caminho. Não se desativam serviços, Defender, rede, áudio, TPM, Secure Boot ou anticheat.

## Estrutura e validação

- `main.py`: inicialização, tema e exceções.
- `booster/ui.py`: interface, gráficos, prévia, perfis, resultados e ações assíncronas.
- `booster/monitor.py` e `gpu.py`: medições e fontes de GPU em segundo plano.
- `booster/safety.py`: política de proteção e seleção.
- `booster/windows.py`: assinatura, criticidade, WM_CLOSE, energia e autostart.
- `booster/state.py`: preferências e recuperação persistente.
- `booster/games.py`: descoberta somente de leitura.
- `tests/`: testes da política, restauração, preferências, parser de GPU e interface/simulação.

Executar testes: `python -m unittest discover -s tests -v` (no Linux sem desktop: `QT_QPA_PLATFORM=offscreen`). Consulte `VALIDATION.md` para distinguir o que foi executado aqui das integrações que ainda precisam ser testadas no Windows.
