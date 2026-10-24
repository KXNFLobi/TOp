# Validação — 24/10/2026

Ambiente: Linux x64, Python 3.12, PySide6 6.12.0 e psutil 7.2.2.

Executado:

- Instalação real das dependências pelos pacotes oficiais do PyPI, preservando TLS e verificação dos pacotes.
- **34 testes aprovados** (incluindo interface e simulação) de segurança, prioridade de Manter, preferências, recuperação durável de energia, recusa de sobrescrever mudança externa, descoberta por manifesto, agregação de contadores GPU e interface/simulação.
- Interface Qt iniciada com renderização offscreen, monitoramento real de processos, CPU, RAM e disco, múltiplas amostras e encerramento normal do monitor. Nenhuma ação sobre aplicativos de terceiros foi feita no Linux.
- Captura real da interface no ambiente Linux, sem dados artificiais de CPU, GPU ou RAM.

A confirmar no Windows 10/11:

- Assinatura Authenticode, IsProcessCritical, enumeração de serviços/HWNDs e WM_CLOSE com aplicativos de teste; verificar prompts de salvar, minimização à bandeja, processos encerrados externamente e PID reutilizado.
- Plano de energia real, permissões, notebook Modern Standby, recuperação após crash e restauração ao terminar um jogo.
- Detecção em bibliotecas reais Steam/Epic, processos de jogos, fontes WDDM/NVIDIA e sensores.
- Entrada opt-in de inicialização automática e empacotamento PyInstaller no runner Windows.

O workflow foi preparado para executar os testes e empacotar no Windows. A execução ou publicação de um artefato no GitHub Actions não é confirmada por este arquivo. Um executável Windows não foi produzido na máquina Linux. Não há promessa de aumento de FPS.


## Distribuição sem Python instalado

A execução Windows anterior foi confirmada como concluída com sucesso na página do GitHub Actions: https://github.com/KXNFLobi/TOp/actions/runs/40127049949 . Isso confirma os testes e o empacotamento portátil daquela versão; não comprova o novo instalador.

O instalador Inno Setup e o workflow atualizado adicionam verificação dos runtimes, instalação silenciosa de teste, abertura da janela empacotada, fechamento normal e desinstalação. A publicação automática do Setup depende de esses passos passarem e do token do workflow poder escrever na branch. Consulte o arquivo BUILD gerado junto do instalador para identificar a compilação publicada.


## FPS 1.1.0

A suíte acrescenta validações de PID, separação de swapchains, média ponderada dos intervalos de apresentação, expiração de leitura, rejeição de métricas inválidas, integridade do binário oficial e encerramento restrito ao handle do coletor particular. A interface é testada para não manter um FPS antigo quando a fonte deixa de fornecer quadros.

O workflow Windows agora compila uma aplicação gráfica Direct3D11 WARP de teste, com duração limitada a 15 segundos, captura eventos ETW reais com PresentMon e exige FPS positivo com pelo menos dez intervalos. Depois de parar a captura, exige que a aplicação gráfica continue aberta e aguarda sua saída natural. O instalador só é publicado se esse teste e os testes de instalação/interface/desinstalação passarem. A execução deste novo teste ainda deve ser confirmada no GitHub; compatibilidade de cada jogo/anticheat real continua dependente do ambiente.


### Resultado confirmado do FPS no Windows

Execução concluída com sucesso: https://github.com/KXNFLobi/TOp/actions/runs/40137161333 . Os 46 testes passaram no Windows, o binário PresentMon teve integridade conferida, a aplicação Direct3D11 de teste produziu FPS real e pelo menos dez intervalos, e continuou aberta depois da parada do coletor. O bundle e o instalador passaram pela verificação de dependências, instalação, abertura da interface, fechamento normal e desinstalação. O instalador correspondente foi publicado com arquivo BUILD apontando para o commit de origem `c89d08e`.

Esses resultados não comprovam compatibilidade com todo jogo ou anticheat; ausência de eventos/permissões continua resultando em leitura indisponível, sem estimativa por CPU/GPU.
