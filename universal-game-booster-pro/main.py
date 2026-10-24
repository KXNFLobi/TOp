import sys
from PySide6.QtWidgets import QApplication, QMessageBox
from booster.ui import MainWindow, STYLE

def main():
    app=QApplication(sys.argv)
    app.setApplicationName("Universal Game Booster Pro")
    app.setOrganizationName("UniversalGameBoosterPro")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window=MainWindow()
    def unexpected(kind,value,trace):
        window.store.log.error("Exceção não tratada",exc_info=(kind,value,trace))
        QMessageBox.critical(window,"Operação interrompida",str(value))
    sys.excepthook=unexpected
    window.show()
    return app.exec()

if __name__=="__main__":
    raise SystemExit(main())
