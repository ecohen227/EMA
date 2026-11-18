"""The first window of EMA: pick one of its packages, in the order they are used."""

import sys

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QLabel, QMessageBox, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from . import __version__
from .evoked_analysis.window import EvokedAnalysisWindow
from .evoked_configurator.window import ConfiguratorWindow
from .paths import DOCUMENTATION
from .roi_selection.setup_dialog import SetupDialog
from .roi_selection.window import RoiSelectionWindow
from .spontaneous_analysis.window import SpontaneousAnalysisWindow
from .spontaneous_configurator.window import SpontaneousConfiguratorWindow


def open_roi_selection(launcher):
    """Run the setup dialog, then open the ROI Selection window. Returns the window, or None if cancelled."""
    dialog = SetupDialog(launcher)
    if not dialog.exec_():
        return None
    return RoiSelectionWindow(dialog.selections, dialog.output_folder)


# heading, what it is for, then (name, what it does, the function that opens its window) in the order of use
WORKFLOWS = [
    ("Evoked responses", "Responses to electrical stimulation, measured in a region of interest (ROI).", [
        ("ROI Selection", "Find the ROI and the electrode in every recording folder, and flag bad recordings. "
                          "Makes the ROI file.", open_roi_selection),
        ("Evoked Analysis Configurator", "Set the pulses, windows and measures: makes a protocol.",
         lambda launcher: ConfiguratorWindow()),
        ("Evoked Analysis", "Measure every folder of the ROI file with a protocol, and write the tables for Prism.",
         lambda launcher: EvokedAnalysisWindow()),
    ]),
    ("Spontaneous events", "Events in the unstimulated recordings. Uses the ROI file when there is one.", [
        ("Spontaneous Event Configurator", "Set how events are found and what is measured on them: makes a detector.",
         lambda launcher: SpontaneousConfiguratorWindow()),
        ("Spontaneous Event Analysis", "Find and measure the events of every folder of recordings, and write the tables "
                                       "for Prism.", lambda launcher: SpontaneousAnalysisWindow()),
    ]),
]
PACKAGES = [package for _, _, packages in WORKFLOWS for package in packages]


class Launcher(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EMA")
        self.package_window = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(10)
        title = QLabel(f"<h1>EMA</h1>Version {__version__}. Choose what you want to do.")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        for heading, about, packages in WORKFLOWS:
            label = QLabel(f"<h3>{heading}</h3>{about}")
            label.setWordWrap(True)
            layout.addWidget(label)
            for step, (name, description, open_package) in enumerate(packages, start=1):
                layout.addWidget(self._package_button(f"{step}  {name}", description, open_package))
        documentation = QPushButton("Documentation: how each package works")
        documentation.clicked.connect(self.open_documentation)
        layout.addSpacing(6)
        layout.addWidget(documentation, alignment=Qt.AlignCenter)
        self.setMinimumWidth(620)

    def _package_button(self, name, description, open_package):
        button = QPushButton()
        text = QLabel(f"<b>{name}</b><br>{description}")
        text.setWordWrap(True)
        text.setAttribute(Qt.WA_TransparentForMouseEvents)
        inside = QVBoxLayout(button)
        inside.setContentsMargins(12, 6, 12, 6)
        inside.addWidget(text)
        button.setMinimumHeight(text.heightForWidth(560) + 14)
        button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        button.setAccessibleName(name)
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
                "The documentation has not been built yet.\n\nOpen a terminal in the EMA folder and type:\n"
                + ("py install.py" if sys.platform == "win32" else "python3 install.py"),
            )
