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
