"""The first window of EMA: pick one of its packages."""

from pathlib import Path

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from . import __version__
from .evoked_analysis.window import AnalysisWindow
from .evoked_configurator.window import ConfiguratorWindow
from .roi_selection.setup_dialog import SetupDialog
from .roi_selection.window import RoiSelectionWindow

DOCUMENTATION = Path(__file__).parent.parent / "docs" / "_build" / "html" / "index.html"


def open_roi_selection(launcher):
    """Run the setup dialog, then open the ROI Selection window. Returns the window, or None if cancelled."""
    dialog = SetupDialog(launcher)
    if not dialog.exec_():
        return None
    return RoiSelectionWindow(dialog.selections, dialog.output_folder)


def open_configurator(launcher):
    return ConfiguratorWindow()


def open_analysis(launcher):
    return AnalysisWindow()


# name, what it does, the function that opens it (None while it is not built yet)
PACKAGES = [
    ("ROI Selection", "Find the ROI and the electrode of every recording, and flag bad recordings.", open_roi_selection),
    ("Evoked Analysis", "Measure the evoked responses inside the selected ROIs, and write the tables for Prism.", open_analysis),
    ("Evoked Analysis Configurator", "Set the pulses, windows and measures of the evoked analysis.", open_configurator),
    ("Spontaneous Event Analysis", "Find and measure spontaneous events in unstimulated recordings.", None),
]


class Launcher(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EMA")
        self.package_window = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(12)
        title = QLabel(f"<h1>EMA</h1>Version {__version__}. Choose what you want to do.")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        for name, description, open_package in PACKAGES:
            layout.addWidget(self._package_button(name, description, open_package))
        documentation = QPushButton("Documentation")
        documentation.setFlat(True)
        documentation.clicked.connect(self.open_documentation)
        layout.addWidget(documentation, alignment=Qt.AlignCenter)
        self.setFixedWidth(600)

    def _package_button(self, name, description, open_package):
        available = open_package is not None
        button = QPushButton(f"{name}\n{description}" if available else f"{name}  (coming soon)\n{description}")
        button.setStyleSheet("text-align: left; padding: 12px; font-size: 10pt;")
        button.setEnabled(available)
        if available:
            button.clicked.connect(lambda: self.open(open_package))
        return button

    def open(self, open_package):
        """Open a package and hide this window until the package is closed."""
        window = open_package(self)
        if window is None:
            return
        self.package_window = window
        window.closed.connect(self.show)
        window.show()
        self.hide()

    def open_documentation(self):
        if DOCUMENTATION.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(DOCUMENTATION)))
        else:
            QMessageBox.information(
                self,
                "Documentation",
                "The documentation has not been built yet.\n\nIn the EMA folder, run:\n"
                "python -m sphinx docs docs/_build/html",
            )
