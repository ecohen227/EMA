"""Starts EMA: the Qt application, the error dialog and the launcher."""

import sys
import traceback
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import QApplication, QMessageBox, QSplashScreen

from . import APP_ID

ICON = str(Path(__file__).parent / "assets" / "ema.png")


def show_error(error_type, error, trace):
    """Show an unexpected error in a dialog. Without this, PyQt closes the whole program."""
    text = "".join(traceback.format_exception(error_type, error, trace))
    if sys.__stderr__ is not None:
        sys.__stderr__.write(text)
    box = QMessageBox(QMessageBox.Critical, "EMA error", f"{error_type.__name__}: {error}")
    box.setDetailedText(text)
    box.exec_()


def main():
    if sys.platform == "win32":
        # Lets Windows show the EMA icon on the taskbar instead of the Python one.
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)

    # Follow the Windows display scale exactly (for example 250 %) instead of rounding it.
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("EMA")
    app.setWindowIcon(QIcon(ICON))
    splash = QSplashScreen(QPixmap(ICON))
    splash.showMessage("Loading EMA…", Qt.AlignBottom | Qt.AlignHCenter, Qt.white)
    splash.show()
    app.processEvents()

    from .launcher import Launcher  # imported late: numpy, scipy and matplotlib take a few seconds

    sys.excepthook = show_error
    launcher = Launcher()
    launcher.show()
    splash.finish(launcher)
    sys.exit(app.exec_())
