from __future__ import annotations
from collections import deque
from dataclasses import asdict, replace
from datetime import datetime
import json
import os
from pathlib import Path
import time
import psutil
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QPropertyAnimation, QEasingCurve, QUrl
from PySide6.QtGui import QColor, QPainter, QPen, QPainterPath, QDesktopServices, QAction
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QCheckBox, QComboBox, QMessageBox,
    QFileDialog, QDialog, QDialogButtonBox, QTextEdit, QGraphicsOpacityEffect, QSystemTrayIcon, QStyle)
from .state import Store, canonical
from .safety import assess, choose, ProcessRow
from .monitor import Monitor, Metrics, metrics
from .windows import IS_WINDOWS, PowerPlan, Signatures, request_close, configure_startup
from .games import discover
from .fps import FpsCapture, GAME_NAME, trace_allowed, reopen_elevated

STYLE = """
QWidget { background:#0a0e1a; color:#e7edff; font-family:'Segoe UI'; font-size:12px; }
QMainWindow { background:#0a0e1a; }
QLabel#title { font-size:26px; font-weight:700; }
QLabel#muted { color:#98a8ca; }
QLabel#card { background:#131d34; border:1px solid #273957; border-radius:12px; padding:15px; font-size:16px; }
QPushButton { background:#20365c; border:1px solid #36558b; border-radius:8px; padding:10px 14px; }
QPushButton:hover { background:#2e4c7e; border-color:#64a5ff; }
QPushButton:disabled { color:#71809b; background:#172137; border-color:#25314a; }
QPushButton#boost { background:#5936c8; border:1px solid #9b7bff; font-size:20px; font-weight:700; padding:21px; }
QPushButton#boost:hover { background:#7150e8; }
QLineEdit, QComboBox, QTextEdit { background:#151f36; border:1px solid #354a70; border-radius:6px; padding:8px; selection-background-color:#415fba; }
QComboBox QAbstractItemView { background:#151f36; color:#e7edff; selection-background-color:#31558a; }
QTabWidget::pane { border:1px solid #273957; border-radius:8px; }
QTabBar::tab { background:#151f36; padding:12px 22px; margin:0 3px 4px 0; border-radius:6px; }
QTabBar::tab:selected { background:#283c72; color:#b8d9ff; }
QTableWidget { background:#10192c; alternate-background-color:#17243c; gridline-color:#263650; border:none; }
QHeaderView::section { background:#233452; color:#dce9ff; border:none; padding:9px; }
QTableWidget::item:selected { background:#2c4f82; }
QCheckBox { spacing:8px; padding:6px; }
QCheckBox::indicator { width:16px; height:16px; border:1px solid #6d83a5; background:#111b2f; border-radius:3px; }
QCheckBox::indicator:checked { background:#7864ef; border:2px solid #b6adff; }
QScrollBar:vertical { background:#10192c; width:12px; }
QScrollBar::handle:vertical { background:#415b87; min-height:26px; border-radius:5px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0px; }
QScrollBar:horizontal { background:#10192c; height:12px; }
QScrollBar::handle:horizontal { background:#415b87; min-width:26px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width:0px; }
"""

def button(text, callback, layout):
    widget = QPushButton(text); widget.clicked.connect(callback); layout.addWidget(widget); return widget

def table(headers):
    widget = QTableWidget(0, len(headers)); widget.setHorizontalHeaderLabels(headers)
    widget.setAlternatingRowColors(True); widget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    widget.verticalHeader().setVisible(False); widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    return widget

class Chart(QWidget):
    def __init__(self):
        super().__init__(); self.values = deque(maxlen=120); self.setMinimumHeight(130)
    def append(self, metric):
        self.values.append((metric.cpu, metric.ram_percent, metric.gpu)); self.update()
    def paintEvent(self, event):
        painter = QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(12, 10, -12, -26)
        painter.fillRect(self.rect(), QColor("#10192c"))
        painter.setPen(QColor("#283953"))
        for i in range(5):
            y = rect.top()+rect.height()*i/4; painter.drawLine(rect.left(), int(y), rect.right(), int(y))
        for channel, color, name in [(0,"#4ea1ff","CPU"),(1,"#a47bff","RAM"),(2,"#32dcc5","GPU")]:
            painter.setPen(QPen(QColor(color), 2)); path = QPainterPath(); started = False
            for i, values in enumerate(self.values):
                value = values[channel]
                if value is None:
                    started = False; continue
                x = rect.left()+i*rect.width()/119; y = rect.bottom()-min(100,max(0,value))*rect.height()/100
                if started: path.lineTo(x,y)
                else: path.moveTo(x,y); started=True
            painter.drawPath(path); painter.drawText(15+channel*160, self.height()-7, name)

class Job(QThread):
    done = Signal(object)
    failed = Signal(str)
    def __init__(self, function):
        super().__init__(); self.function = function
    def run(self):
        try: self.done.emit(self.function())
        except Exception as exc: self.failed.emit(str(exc))

class Preview(QDialog):
    def __init__(self, rows, simulation, power, parent=None):
        super().__init__(parent); self.setWindowTitle("Prévia — nenhuma ação executada"); self.resize(850,500)
        layout=QVBoxLayout(self)
        message = ("SIMULAÇÃO: nenhum aplicativo ou plano será alterado." if simulation else
                   "Será solicitado o fechamento normal das janelas abaixo. Salve seu trabalho. Não haverá encerramento forçado.")
        label=QLabel(message); label.setWordWrap(True); layout.addWidget(label)
        listing=table(["Aplicativo","PID","RAM (MiB)","Executável"]); layout.addWidget(listing)
        for row in rows:
            i=listing.rowCount(); listing.insertRow(i)
            for j,value in enumerate([row.name,str(row.pid),f"{row.rss/1024**2:.1f}",row.exe]): listing.setItem(i,j,QTableWidgetItem(value))
        note=QLabel(("Ajuste solicitado: Alto Desempenho temporário; pode aumentar consumo e temperatura. " if power else "Sem ajuste de energia. ")+
                    "Restaurar reverte o plano de energia; não recupera trabalho perdido nem reabre sessões dos aplicativos. A decisão de salvar/cancelar em cada aplicativo será respeitada.")
        note.setWordWrap(True); layout.addWidget(note)
        self.consent=QCheckBox("Li a prévia e autorizo estas ações" if not simulation else "Executar somente a simulação")
        layout.addWidget(self.consent)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Confirmar" if not simulation else "Simular")
        buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.consent.toggled.connect(buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)

class MainWindow(QMainWindow):
    def __init__(self, store=None, start_monitor=True):
        super().__init__(); self.store=store or Store(); self.power=PowerPlan(self.store)
        self.setWindowTitle("Universal Game Booster Pro"); self.resize(1280,900); self.setMinimumSize(960,700)
        self.rows=[]; self.decisions={}; self.latest=None; self.jobs=[]; self.busy=False; self._refreshing=False
        self.current_user=psutil.Process().username(); self.active_games=set(); self.offered=set(); self.restore_games=set(); self._allow_pending_exit=False
        self.profile_name=self.store.data.get("profile","Global")
        self.store.profile(self.profile_name)
        self.monitor=None; self.fps_capture=None; self.fps_error=""; self._closing_after_fps=False
        root=QWidget(); self.setCentralWidget(root); layout=QVBoxLayout(root); layout.setContentsMargins(24,20,24,20)
        title=QLabel("UNIVERSAL GAME BOOSTER PRO"); title.setObjectName("title"); layout.addWidget(title)
        subtitle=QLabel("Recursos reais. Escolhas suas. Segurança preservada."); subtitle.setObjectName("muted"); layout.addWidget(subtitle)
        cards=QHBoxLayout(); self.cards={}
        for key in ("CPU","GPU","RAM","DISCO","PROCESSOS","FPS"):
            label=QLabel(key+"\nAguardando leitura"); label.setObjectName("card"); cards.addWidget(label); self.cards[key]=label
        self.cards["FPS"].setText("FPS\nDesativado")
        layout.addLayout(cards); self.chart=Chart(); layout.addWidget(self.chart)
        self.diagnosis=QLabel("FPS via PresentMon/ETW • Temperaturas somente quando o hardware disponibiliza sensores.")
        self.diagnosis.setWordWrap(True); layout.addWidget(self.diagnosis)
        fpsbar=QHBoxLayout();fpsbar.addWidget(QLabel("Jogo para FPS:"));self.fps_targets=QComboBox();self.fps_targets.setMinimumWidth(240);fpsbar.addWidget(self.fps_targets,1)
        self.fps_start=button("Mostrar FPS",self.start_fps,fpsbar);self.fps_start.setEnabled(IS_WINDOWS)
        self.fps_stop=button("Parar FPS",self.stop_fps,fpsbar);self.fps_stop.setEnabled(False);layout.addLayout(fpsbar)
        self.fps_detail=QLabel("Escolha o processo gráfico de um jogo aberto. Fonte: PresentMon • não injeta código no jogo.")
        self.fps_detail.setWordWrap(True);layout.addWidget(self.fps_detail)
        controls=QHBoxLayout(); self.simulation=QCheckBox("Modo de simulação"); self.simulation.setChecked(self.store.data["simulation"])
        self.simulation.toggled.connect(self.save_flags); controls.addWidget(self.simulation)
        self.power_option=QCheckBox("Alto Desempenho temporário (opcional)"); self.power_option.setEnabled(IS_WINDOWS); controls.addWidget(self.power_option)
        self.game_boost=QCheckBox("GAME BOOST MODE"); self.game_boost.setChecked(self.store.data["game_boost"])
        self.game_boost.toggled.connect(self.save_flags); controls.addWidget(self.game_boost)
        self.profile=QComboBox(); self.profile.setMinimumWidth(180); self.profile.setMaximumWidth(320); self.profile.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon); self.profile.addItems(self.store.data["profiles"]); self.profile.setCurrentText(self.profile_name)
        self.profile.currentTextChanged.connect(self.profile_changed); controls.addWidget(QLabel("Perfil:")); controls.addWidget(self.profile)
        layout.addLayout(controls)
        self.boost=button("OTIMIZAR MEU PC AGORA",self.optimize,layout); self.boost.setObjectName("boost")
        self.tabs=QTabWidget(); layout.addWidget(self.tabs,1)
        self.make_apps(); self.make_games(); self.make_history(); self.make_settings()
        self.status=QLabel("Simulação é o padrão. Processos desconhecidos permanecem protegidos."); self.status.setWordWrap(True); layout.addWidget(self.status)
        self.tray=QSystemTrayIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon), self)
        if QSystemTrayIcon.isSystemTrayAvailable(): self.tray.show()
        effect=QGraphicsOpacityEffect(root); root.setGraphicsEffect(effect); self.fade=QPropertyAnimation(effect,b"opacity",self)
        self.fade.setDuration(350); self.fade.setStartValue(0); self.fade.setEndValue(1); self.fade.setEasingCurve(QEasingCurve.Type.OutCubic); self.fade.start()
        self.render_games(); self.render_history()
        if start_monitor:
            self.monitor=Monitor(self.store.log); self.monitor.sample.connect(self.on_sample); self.monitor.failed.connect(self.error); self.monitor.start()
        if self.store.load_warning: self.notify(self.store.load_warning)
        if self.store.data.get("power_restore"): self.notify("Há um plano de energia salvo de uma sessão anterior. Use Restaurar ajustes para recuperá-lo.")

    def refresh_fps_targets(self):
        if self.fps_capture:return
        previous=self.fps_targets.currentData()
        old_pid=previous.pid if previous else None
        self.fps_targets.blockSignals(True);self.fps_targets.clear()
        for row in self.rows:
            if row.created and row.exe and (canonical(row.exe) in self.game_paths() or GAME_NAME.fullmatch(row.name)):
                self.fps_targets.addItem(f"{row.name} • PID {row.pid}",row)
                if row.pid==old_pid:self.fps_targets.setCurrentIndex(self.fps_targets.count()-1)
        if self.fps_targets.count() and self.fps_targets.currentIndex()<0:self.fps_targets.setCurrentIndex(0)
        self.fps_targets.blockSignals(False)
        if not self.fps_targets.count():self.fps_targets.setPlaceholderText("Abra um jogo; cadastre outros executáveis em MEUS JOGOS")

    def start_fps(self):
        if self.busy or self.fps_capture:return
        row=self.fps_targets.currentData()
        if not row:self.notify("Abra um jogo e selecione seu processo gráfico. Para outros jogos, adicione o executável em MEUS JOGOS.");return
        if not trace_allowed():
            if self.store.data.get("power_restore"):
                self.notify("Restaure primeiro os ajustes temporários antes de reabrir o aplicativo com permissão de FPS.");return
            response=QMessageBox.question(self,"Permissão para medir FPS","O PresentMon precisa de permissão ETW. Reabrir este aplicativo como administrador? O Windows solicitará sua autorização. Depois de reabrir, escolha o jogo e clique em Mostrar FPS novamente. Nenhuma configuração de segurança será alterada.",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)
            if response==QMessageBox.StandardButton.Yes:
                try:self.store.save();reopen_elevated();self.close()
                except Exception as exc:self.error(str(exc))
            return
        self.fps_error="";capture=FpsCapture(row,self.store.log);self.fps_capture=capture
        self.fps_targets.setEnabled(False);self.fps_start.setEnabled(False);self.fps_stop.setEnabled(True)
        self.cards["FPS"].setText("FPS\nColetando…");self.fps_detail.setText(f"PresentMon • {row.name} • PID {row.pid} • aguardando quadros reais")
        capture.updated.connect(self.fps_updated);capture.failed.connect(self.fps_failed)
        capture.finished.connect(self.fps_finished);capture.start()

    def fps_updated(self,sample):
        if sample.fps is None:
            self.cards["FPS"].setText("FPS\nIndisponível")
            self.fps_detail.setText(self.fps_error or sample.message)
        else:
            self.cards["FPS"].setText(f"FPS\n{sample.fps:.1f}")
            self.fps_detail.setText(f"{sample.message} • {sample.frame_ms:.2f} ms/quadro • {sample.frames} intervalos • PID {self.fps_capture.target.pid if self.fps_capture else '—'}")
    def fps_failed(self,message):
        self.fps_error=message;self.fps_detail.setText(message);self.error("FPS indisponível: "+message)
    def fps_finished(self):
        capture=self.fps_capture;self.fps_capture=None
        self.fps_stop.setEnabled(False);self.fps_targets.setEnabled(True);self.fps_start.setEnabled(IS_WINDOWS and not self.busy)
        if not self.fps_error:self.cards["FPS"].setText("FPS\nDesativado")
        if capture:capture.deleteLater()
        self.refresh_fps_targets()
        if self._closing_after_fps:QTimer.singleShot(0,self.close)
    def stop_fps(self):
        if self.fps_capture:
            self.fps_capture.requestInterruption();self.fps_stop.setEnabled(False);self.fps_detail.setText("Parando somente o coletor de FPS; o jogo continuará aberto…")

    def make_apps(self):
        page=QWidget(); layout=QVBoxLayout(page); bar=QHBoxLayout()
        self.search=QLineEdit(); self.search.setPlaceholderText("Pesquisar nome, PID, caminho ou proteção…"); self.search.textChanged.connect(self.render_apps); bar.addWidget(self.search)
        button("Salvar escolhas neste perfil",self.save_profile,bar); layout.addLayout(bar)
        self.apps=table(["Fechar","Manter","★","Aplicativo / PID","CPU %","RAM MiB","Estado / proteção","Executável"])
        self.apps.horizontalHeader().setSectionResizeMode(6,QHeaderView.ResizeMode.Stretch)
        self.apps.itemChanged.connect(self.app_item_changed); layout.addWidget(self.apps)
        actions=QHBoxLayout()
        self.safe_button=button("SELECIONAR APLICATIVOS SEGUROS",self.select_safe,actions)
        button("DESMARCAR TODOS",self.unselect,actions)
        button("MANTER SELECIONADOS ABERTOS",self.keep_selected,actions)
        self.close_button=button("FECHAR APLICATIVOS SELECIONADOS",lambda:self.optimize(selected_only=True),actions)
        layout.addLayout(actions); self.tabs.addTab(page,"APLICATIVOS")

    def make_games(self):
        page=QWidget(); layout=QVBoxLayout(page)
        note=QLabel("Detecta manifestos Steam/Epic e instalações padrão FiveM/Roblox. Qualquer jogo pode ser adicionado pelo executável; ele será protegido.")
        note.setWordWrap(True); layout.addWidget(note)
        actions=QHBoxLayout(); button("Detectar jogos instalados",self.detect_games,actions); button("Adicionar executável…",self.add_game,actions)
        button("Usar perfil do jogo selecionado",self.use_game,actions); button("Favorito ★",self.favorite_game,actions); layout.addLayout(actions)
        self.games=table(["★","Jogo / perfil","Executável protegido","Ativo"]); self.games.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch)
        self.games.cellDoubleClicked.connect(lambda *_:self.use_game()); layout.addWidget(self.games)
        layout.addWidget(QLabel("Para editar um perfil: ative-o, escolha Fechar/Manter em APLICATIVOS e salve. Launchers e processos necessários permanecem protegidos."))
        self.tabs.addTab(page,"MEUS JOGOS")

    def make_history(self):
        page=QWidget(); layout=QVBoxLayout(page)
        self.comparison=table(["Métrica","Antes","Depois","Variação observada"]); self.comparison.setMaximumHeight(190); layout.addWidget(self.comparison)
        self.history_note=QLabel("Nenhuma otimização registrada."); self.history_note.setWordWrap(True); layout.addWidget(self.history_note)
        self.history=QTextEdit(); self.history.setReadOnly(True); layout.addWidget(self.history)
        button("Abrir pasta de relatórios",lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.store.directory))),layout)
        self.tabs.addTab(page,"RESULTADOS E HISTÓRICO")

    def make_settings(self):
        page=QWidget(); layout=QVBoxLayout(page)
        label=QLabel("PROTEGIDOS POR PADRÃO\n\nWindows e serviços; antivírus e Defender; áudio e rede; drivers e periféricos; anticheats; jogos cadastrados; launchers; processos desconhecidos ou sem assinatura verificada.\n\nSomente aplicativos de desktop reconhecidos, assinados pelo editor esperado, do usuário atual e com janela visível podem receber WM_CLOSE. Não há kill, limpeza agressiva de RAM, alteração de arquivos de jogos, prioridade de tempo real ou tweaks de Registro.\n\nGPU: NVIDIA via nvidia-smi ou contadores WDDM do Windows (AMD/Intel/NVIDIA), quando disponíveis. Sem fonte confiável, mostra indisponível. CPU e temperaturas sem sensor ficam indisponíveis; isso não indica falha do hardware.")
        label.setWordWrap(True); layout.addWidget(label)
        self.startup=QCheckBox("Iniciar com o Windows (somente este usuário)"); self.startup.setChecked(self.store.data["startup"]); self.startup.setEnabled(IS_WINDOWS)
        self.startup.toggled.connect(self.startup_changed); layout.addWidget(self.startup)
        button("Restaurar ajustes temporários",self.restore_clicked,layout)
        layout.addWidget(QLabel("Restaurar atua no plano de energia salvo. Aplicativos fechados e seu trabalho não podem ser recuperados por esse botão."))
        layout.addStretch(); self.tabs.addTab(page,"PROTEÇÃO E AJUSTES")

    def save_flags(self,*_):
        self.store.data["simulation"]=self.simulation.isChecked()
        # game_boost may not exist during construction.
        if hasattr(self,"game_boost"): self.store.data["game_boost"]=self.game_boost.isChecked()
        self.persist()

    def persist(self):
        try: self.store.save()
        except OSError as exc: self.error(f"Não foi possível salvar preferências: {exc}")

    def profile_changed(self,name):
        if not name:return
        self.profile_name=name; self.profile.setToolTip(name); self.store.profile(name); self.store.data["profile"]=name; self.persist(); self.render_apps()

    def game_paths(self): return {canonical(game["exe"]) for game in self.store.data["games"]}

    def on_sample(self,snapshot,rows):
        self.latest=snapshot; self.rows=rows
        self.decisions={r.pid:assess(r,self.current_user,self.game_paths(),os.environ.get("SystemRoot",""),IS_WINDOWS) for r in rows}
        self.cards["CPU"].setText(f"CPU\n{snapshot.cpu:.1f}%")
        self.cards["GPU"].setToolTip(snapshot.gpu_source)
        self.cards["GPU"].setText("GPU\n"+(f"{snapshot.gpu:.1f}%" if snapshot.gpu is not None else "Indisponível"))
        self.cards["RAM"].setText(f"RAM\n{snapshot.ram_percent:.1f}% · {snapshot.ram_used/1024**3:.1f} GiB")
        self.cards["DISCO"].setText("DISCO · I/O agregado\n"+(f"{snapshot.disk_mbps:.1f} MiB/s" if snapshot.disk_mbps is not None else "Aguardando amostra"))
        self.cards["PROCESSOS"].setText(f"PROCESSOS\n{snapshot.processes}")
        self.chart.append(snapshot)
        notes=[]
        if snapshot.ram_percent>=85:notes.append("Pressão de memória observada")
        if snapshot.cpu>=85:notes.append("CPU muito ocupada")
        if snapshot.gpu is not None and snapshot.gpu>=95:notes.append("GPU muito ocupada")
        notes.append("Essas leituras isoladas não comprovam gargalo nem ganho de FPS")
        notes.append("CPU °C: "+(f"{snapshot.cpu_temp:.0f}" if snapshot.cpu_temp is not None else "indisponível"))
        notes.append("GPU °C: "+(f"{snapshot.gpu_temp:.0f}" if snapshot.gpu_temp is not None else "indisponível"))
        self.diagnosis.setText(" • ".join(notes))
        self.refresh_fps_targets()
        # Do not replace rows while the user is clicking/choosing cells.
        if QApplication.mouseButtons()==Qt.MouseButton.NoButton and not self.busy:self.render_apps()
        previous=self.active_games; self.active_games={canonical(r.exe) for r in rows if canonical(r.exe) in self.game_paths()}
        self.render_games()
        self.offered.intersection_update(self.active_games)
        if self.store.data.get("power_restore") and not self.restore_games and self.active_games:
            self.restore_games=set(self.active_games)
        if self.restore_games and not (self.restore_games & self.active_games) and not self.busy:
            self.restore_games.clear(); self.restore(auto=True)
        if self.game_boost.isChecked() and not self.busy:
            for path in self.active_games-previous:
                if path not in self.offered:
                    self.offered.add(path)
                    QTimer.singleShot(0,lambda path=path:self.offer_game(path))

    def render_apps(self,*_):
        if not hasattr(self,"apps"):return
        vertical=self.apps.verticalScrollBar().value(); horizontal=self.apps.horizontalScrollBar().value()
        old=self.apps.item(self.apps.currentRow(),0); old_pid=old.data(Qt.ItemDataRole.UserRole)[1] if old else None
        self._refreshing=True; self.apps.setUpdatesEnabled(False); self.apps.setRowCount(0)
        profile=self.store.profile(self.profile_name); keep=set(profile["keep"]); selected=set(profile["close"])
        favorites=set(self.store.data["favorites"]); query=self.search.text().casefold()
        for row in sorted(self.rows,key=lambda r:(canonical(r.exe) not in favorites,-r.rss,r.pid)):
            decision=self.decisions.get(row.pid)
            reason=decision.reason if decision else "Aguardando verificação"
            if query and query not in f"{row.name} {row.pid} {row.exe} {reason}".casefold():continue
            i=self.apps.rowCount(); self.apps.insertRow(i); path=canonical(row.exe)
            for column,checked in [(0,path in selected and path not in keep),(1,path in keep),(2,path in favorites)]:
                item=QTableWidgetItem(); item.setFlags(Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsUserCheckable)
                if not path or (column==0 and (not decision or not decision.allowed or path in keep)):
                    item.setFlags(Qt.ItemFlag.NoItemFlags)
                item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
                item.setData(Qt.ItemDataRole.UserRole,(path,row.pid)); self.apps.setItem(i,column,item)
            for j,text in enumerate([f"{row.name} / {row.pid}",f"{row.cpu:.1f}" if row.created else "N/D",f"{row.rss/1024**2:.1f}" if row.created else "N/D","Manter aberto" if path in keep else reason,row.exe],3):
                item=QTableWidgetItem(text); item.setToolTip(text); self.apps.setItem(i,j,item)
        if old_pid is not None:
            for i in range(self.apps.rowCount()):
                if self.apps.item(i,0).data(Qt.ItemDataRole.UserRole)[1]==old_pid:self.apps.setCurrentCell(i,3);break
        self.apps.verticalScrollBar().setValue(vertical); self.apps.horizontalScrollBar().setValue(horizontal)
        self.apps.setUpdatesEnabled(True); self._refreshing=False

    def app_item_changed(self,item):
        if self._refreshing or item.column()>2:return
        path,pid=item.data(Qt.ItemDataRole.UserRole)
        if not path:return
        checked=item.checkState()==Qt.CheckState.Checked; profile=self.store.profile(self.profile_name)
        key="close" if item.column()==0 else "keep" if item.column()==1 else "favorites"
        target=self.store.data if key=="favorites" else profile
        values=set(target[key]); values.add(path) if checked else values.discard(path); target[key]=sorted(values)
        if key=="keep" and checked:profile["close"]=[p for p in profile["close"] if p!=path]
        self.persist()
        QTimer.singleShot(0,self.render_apps)

    def select_safe(self):
        profile=self.store.profile(self.profile_name)
        profile["close"]=sorted({canonical(r.exe) for r in self.rows if self.decisions[r.pid].allowed and canonical(r.exe) not in profile["keep"]})
        self.persist(); self.render_apps()
    def unselect(self):
        self.store.profile(self.profile_name)["close"]=[]; self.persist(); self.render_apps()
    def keep_selected(self):
        profile=self.store.profile(self.profile_name); profile["keep"]=sorted(set(profile["keep"])|set(profile["close"])); profile["close"]=[]
        self.persist(); self.render_apps()
    def save_profile(self): self.persist(); self.notify("Escolhas salvas no perfil "+self.profile_name)

    def run_job(self,function,done,on_error=None):
        if self.busy:return
        self.busy=True; self.fps_start.setEnabled(False); self.tabs.setEnabled(False); self.profile.setEnabled(False); self.simulation.setEnabled(False); self.game_boost.setEnabled(False); self.power_option.setEnabled(False); self.boost.setEnabled(False); self.close_button.setEnabled(False); self.safe_button.setEnabled(False)
        job=Job(function); self.jobs.append(job)
        def finish(result=None,error=None):
            self.busy=False; self.fps_start.setEnabled(IS_WINDOWS and self.fps_capture is None); self.tabs.setEnabled(True); self.profile.setEnabled(True); self.simulation.setEnabled(True); self.game_boost.setEnabled(True); self.power_option.setEnabled(IS_WINDOWS); self.boost.setEnabled(True); self.close_button.setEnabled(True); self.safe_button.setEnabled(True)
            if error:
                self.error(error)
                if on_error:on_error(error)
            else:
                try:done(result)
                except Exception as exc:self.error(str(exc))
        job.done.connect(lambda result:finish(result=result)); job.failed.connect(lambda error:finish(error=error))
        job.finished.connect(lambda:self.jobs.remove(job) if job in self.jobs else None); job.start()

    def optimize(self, selected_only=False, game_path=None):
        if self.busy:return
        if self.latest is None:self.notify("Aguarde uma leitura real do monitoramento.");return
        profile=self.store.profile(self.profile_name); selected=set(profile["close"]); keep=set(profile["keep"])
        if not selected and not selected_only:
            selected={canonical(r.exe) for r in self.rows if r.rss>=150*1024**2 or r.cpu>=5}
        rows=choose(self.rows,self.decisions,selected,keep)
        simulation=self.simulation.isChecked(); power=self.power_option.isChecked()
        if not rows and not power:self.notify("Nenhum aplicativo elegível selecionado. Desconhecidos, jogos e serviços continuam protegidos.");return
        if Preview(rows,simulation,power,self).exec()!=QDialog.DialogCode.Accepted:return
        game_paths=self.game_paths(); profile_name=self.profile_name; active_at_start=set(self.active_games)
        def perform():
            before,_,_=metrics(); before=replace(before,cpu=psutil.cpu_percent(interval=0.8))
            outcomes=[]; plan="Sem alteração"; signatures=Signatures()
            for row in rows:
                if simulation:outcomes.append({"pid":row.pid,"app":row.name,"result":"Simulação: seria solicitado fechamento normal"});continue
                try:
                    self.store.log.info("Autorizado fechamento normal PID=%s executável=%s",row.pid,row.exe)
                    result=request_close(row,signatures,self.current_user,game_paths)
                except Exception as exc:result="Preservado: "+str(exc)
                outcomes.append({"pid":row.pid,"app":row.name,"result":result})
                self.store.log.info("Solicitação de fechamento PID=%s app=%s: %s",row.pid,row.exe,result)
            if power:
                if simulation:plan="Simulação: plano não alterado"
                else:
                    try:plan=self.power.apply()
                    except Exception as exc:plan="Não aplicado: "+str(exc)
            time.sleep(1.5)
            after,_,_=metrics(); after=replace(after,cpu=psutil.cpu_percent(interval=0.8))
            if not simulation:
                for outcome,row in zip(outcomes,rows):
                    try:alive=psutil.Process(row.pid).create_time()==row.created
                    except psutil.NoSuchProcess:alive=False
                    except psutil.Error:alive=True
                    outcome["verification"]="Ainda ativo / bandeja ou aguardando o usuário" if alive else "Processo original não está mais ativo"
            return {"time":datetime.now().astimezone().isoformat(),"simulation":simulation,"profile":profile_name,
                    "before":asdict(before),"after":asdict(after),"actions":outcomes,"power":plan}
        def done(entry):
            self.store.record(entry); self.render_history(); self.tabs.setCurrentIndex(2)
            if not simulation and self.store.data.get("power_restore"):self.restore_games=active_at_start|({game_path} if game_path else set())
            self.notify("Simulação concluída; nenhuma ação aplicada." if simulation else "Solicitações concluídas. Confira o resultado de cada aplicativo e as medições observadas.")
        self.status.setText("Analisando, revalidando identidades e medindo antes/depois…"); self.run_job(perform,done)

    def render_history(self):
        history=self.store.data["history"]
        self.history.setPlainText("\n\n".join(json.dumps(e,ensure_ascii=False,indent=2) for e in reversed(history[-30:])))
        self.comparison.setRowCount(0)
        if not history:return
        entry=history[-1]; before=entry["before"]; after=entry["after"]
        self.history_note.setText(("SIMULAÇÃO — nenhuma ação aplicada. " if entry.get("simulation") else "Medições observadas, sem garantia de ganho. ")+"A variação pode ter outras causas; não comprova aumento de FPS.")
        for label,key,scale,suffix in [("RAM em uso","ram_used",1024**3,"GiB"),("CPU","cpu",1,"%"),("Processos ativos","processes",1,""),("Memória disponível","available",1024**3,"GiB")]:
            i=self.comparison.rowCount(); self.comparison.insertRow(i); a=before[key]/scale; b=after[key]/scale
            for j,text in enumerate([label,f"{a:.2f} {suffix}",f"{b:.2f} {suffix}",f"{b-a:+.2f} {suffix}"]):self.comparison.setItem(i,j,QTableWidgetItem(text))
        self.history.setToolTip("Variações do sistema podem ter outras causas. Simulação não libera recursos. Nenhum ganho de FPS é inferido.")

    def render_games(self):
        current=self.selected_game() if self.games.rowCount() else None
        self.games.setRowCount(0)
        for game in sorted(self.store.data["games"],key=lambda g:(not g.get("favorite",False),g["name"])):
            i=self.games.rowCount(); self.games.insertRow(i)
            for j,text in enumerate(["★" if game.get("favorite") else "",game["name"],game["exe"],"Sim" if canonical(game["exe"]) in self.active_games else "Não"]):
                item=QTableWidgetItem(text);item.setData(Qt.ItemDataRole.UserRole,game["exe"]);self.games.setItem(i,j,item)
            if current and game["exe"]==current["exe"]:self.games.setCurrentCell(i,1)

    def detect_games(self):
        def done(found):
            existing={canonical(g["exe"]) for g in self.store.data["games"]}
            self.store.data["games"].extend(g for g in found if canonical(g["exe"]) not in existing)
            self.persist();self.render_games();self.notify(f"Detecção concluída: {len(found)} executáveis candidatos de jogos. Revise e adicione os que faltam manualmente.")
        self.run_job(discover,done)
    def add_game(self):
        filename,_=QFileDialog.getOpenFileName(self,"Adicionar executável de qualquer jogo","","Executável Windows (*.exe)")
        if not filename:return
        if canonical(filename) not in self.game_paths():self.store.data["games"].append({"name":Path(filename).stem,"exe":filename,"favorite":False})
        self.persist();self.render_games()
    def selected_game(self):
        row=self.games.currentRow()
        if row<0:return None
        path=self.games.item(row,1).data(Qt.ItemDataRole.UserRole)
        return next((g for g in self.store.data["games"] if g["exe"]==path),None)
    def use_game(self):
        game=self.selected_game()
        if not game:self.notify("Selecione um jogo.");return
        self.activate_profile(game);self.tabs.setCurrentIndex(0)
    def activate_profile(self,game):
        # Full path prevents two games with the same display name sharing choices accidentally.
        name=game["name"]+" | "+canonical(game["exe"])
        self.store.profile(name)
        if self.profile.findText(name)<0:self.profile.addItem(name)
        self.profile.setCurrentText(name);return name
    def favorite_game(self):
        game=self.selected_game()
        if game:game["favorite"]=not game.get("favorite",False);self.persist();self.render_games()
    def offer_game(self,path):
        if self.busy or not self.game_boost.isChecked() or path not in self.active_games:return
        game=next((g for g in self.store.data["games"] if canonical(g["exe"])==path),None)
        if not game:return
        if QMessageBox.question(self,"Game Boost",f"{game['name']} está ativo. Abrir a prévia do perfil salvo? Nenhum aplicativo será fechado sem confirmação.",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes:
            self.activate_profile(game);self.optimize(selected_only=True,game_path=path)

    def restore(self,auto=False,force=False):
        if self.busy or not self.store.data.get("power_restore"):return
        self.run_job(lambda:self.power.restore(force),lambda result:self.notify(result))
    def restore_clicked(self):
        if not self.store.data.get("power_restore"):self.notify("Nenhum plano temporário pendente.");return
        if QMessageBox.question(self,"Restaurar energia","Restaurar o plano original salvo, substituindo o plano atualmente ativo? Aplicativos fechados não serão reabertos.",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes:self.restore(force=True)
    def startup_changed(self,enabled):
        try:configure_startup(enabled);self.store.data["startup"]=enabled;self.persist()
        except Exception as exc:
            self.startup.blockSignals(True);self.startup.setChecked(not enabled);self.startup.blockSignals(False);self.error(str(exc))
    def error(self,message):
        self.store.log.error(message)
        if hasattr(self,"status"):self.status.setText("Operação não concluída: "+message)
    def notify(self,message):
        if hasattr(self,"status"):self.status.setText(message)
        if hasattr(self,"tray") and self.tray.isVisible():self.tray.showMessage("Universal Game Booster Pro",message,QSystemTrayIcon.MessageIcon.Information,5000)
    def closeEvent(self,event):
        if self.busy or any(job.isRunning() for job in self.jobs):self.notify("Aguarde a operação atual terminar antes de fechar.");event.ignore();return
        if self.fps_capture:
            self._closing_after_fps=True;self.stop_fps();event.ignore();return
        if self.store.data.get("power_restore") and not self._allow_pending_exit:
            event.ignore()
            def finish(result):self.notify(result);QTimer.singleShot(100,self.close)
            def restore_failed(message):
                if QMessageBox.question(self,"Restauração pendente",message+"\n\nSair mantendo o plano original salvo para recuperação na próxima abertura?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes:
                    self._allow_pending_exit=True; QTimer.singleShot(0,self.close)
            self.run_job(lambda:self.power.restore(),finish,restore_failed)
            return
        if self.monitor:
            self.monitor.requestInterruption()
            if not self.monitor.wait(5000):self.notify("Aguardando a leitura de hardware terminar…");event.ignore();return
        self.persist();self.tray.hide();self.store.close();event.accept()
