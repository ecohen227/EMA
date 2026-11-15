"""Evoked Analysis: measure the recordings of every folder in an ROI file with a protocol, and write the tables."""

import time
from pathlib import Path

from PyQt5.QtCore import Qt, QThread, QUrl, pyqtSignal
from PyQt5.QtGui import QColor, QDesktopServices
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..evoked import library
from ..evoked.analysis import FILE_NAME, Analysis, plan, run
from ..evoked.protocol import Protocol, ProtocolError
from ..evoked.workbook import PER_RECORDING, PER_SLICE, TablesLocked, write_workbooks
from ..labels import LabelSet, default_labels
from ..roi_selection import Selections
from ..roi_selection.setup_dialog import FolderFilter, FolderInput
from ..user_settings import remember, remembered
from .labels_editor import LabelsEditor, NearMissList

MISSING = QColor("#fde2e1")
NOTED = QColor("#fff1d6")
WARNING = "color:#b35c00"
ERROR = "color:#c1121f"


def _grey(text=""):
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet("color: gray")
    return label


def _folders(count):
    return f"{count} folder" if count == 1 else f"{count} folders"


def _is_inside(folder, parent):
    folder, parent = Path(folder).resolve(), Path(parent).resolve()
    return folder == parent or parent in folder.parents


class FileInput(QWidget):
    """A file path with a Browse button."""

    changed = pyqtSignal()

    def __init__(self, title, file_filter, path=""):
        super().__init__()
        self.title, self.file_filter = title, file_filter
        self.path = QLineEdit(path)
        self.path.editingFinished.connect(self.changed)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self.browse)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.path, 1)
        layout.addWidget(browse)

    def browse(self):
        path, _ = QFileDialog.getOpenFileName(self, self.title, self.path.text(), self.file_filter)
        if path:
            self.path.setText(path)
            self.changed.emit()

    def file(self):
        text = self.path.text().strip()
        return Path(text) if text else None


class Worker(QThread):
    """Runs the measuring, so the window stays responsive. Results go into the analysis it was given."""

    progressed = pyqtSignal(int, int, str)

    def __init__(self, analysis, protocol, selections, the_plan, keep_others):
        super().__init__()
        self.args = (analysis, protocol, selections, the_plan)
        self.keep_others = keep_others
        self.stop = False
        self.error = None

    def run(self):
        try:
            run(*self.args, progress=self.progressed.emit, cancelled=lambda: self.stop, keep_others=self.keep_others)
        except Exception as error:  # noqa: BLE001  shown to the user, instead of being lost in the thread
            self.error = error


class AnalysisWindow(QMainWindow):
    closed = pyqtSignal()

    def __init__(self, user_folder=None):
        super().__init__()
        self.setWindowTitle("EMA – Evoked Analysis")
        self.user_folder = user_folder  # the protocol library's folder; None means its own
        self.selections = None
        self.protocol = None
        self.protocol_path = None
        self.analysis = Analysis(labels=_remembered_labels())
        self.worker = None
        self.started = 0.0
        self.group_boxes = {}
        self._build_window()
        self._restore()

    # ------------------------------------------------------------------
    # Building the window
    # ------------------------------------------------------------------

    def _build_window(self):
        self.roi_input = FileInput("Choose the ROI file", "ROI files (roi_selections.json);;JSON files (*.json)")
        self.roi_input.changed.connect(self.load_roi_file)
        self.roi_info = _grey()
        self.filter = FolderFilter()
        self.filter.changed.connect(self.filter_changed)

        self.protocol_box = QComboBox()
        self.protocol_box.activated.connect(self.choose_protocol)
        open_protocol = QPushButton("Open…")
        open_protocol.setToolTip("Use a protocol file that is not in the library.")
        open_protocol.clicked.connect(self.open_protocol_file)
        protocol_row = QHBoxLayout()
        protocol_row.addWidget(self.protocol_box, 1)
        protocol_row.addWidget(open_protocol)
        self.protocol_info = _grey()

        self.output = FolderInput("Choose the output folder")
        self.output.changed.connect(self.output_changed)
        self.output_info = _grey()

        self.groups = QWidget()
        self.groups_grid = QGridLayout(self.groups)
        self.groups_grid.setContentsMargins(0, 0, 0, 0)
        self.rows_box = QComboBox()
        self.rows_box.activated.connect(self.grouping_changed)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        rows = [
            ("ROI file", "The roi_selections.json made by ROI Selection. Each folder is measured with its ROI and "
                         "electrode; recordings flagged there are left out.", [self.roi_input, self.roi_info]),
            ("Folders", "Measure only the folders with one of these words in their path (for example 'input output' "
                        "for the 2P protocol), and none of the words to skip.", [self.filter]),
            ("Protocol", "What is measured, as made in the Evoked Analysis Configurator.", [protocol_row, self.protocol_info]),
            ("Output folder", f"Where {PER_RECORDING}, {PER_SLICE} and {FILE_NAME} (the kept results) are written. "
                              "It must be outside the recordings.", [self.output, self.output_info]),
            ("Group by", "The labels whose values make the groups of the Prism sheets: with Genotype and Treatment, "
                         "the groups are WT CTRL, WT IFN, HET CTRL and HET IFN.", [self.groups]),
            ("Slice sheets", "How the per-slice Prism sheets are laid out: one column per group (a column table), or "
                             "one row per value of a label, such as CTRL and IFN (a grouped table).", [self.rows_box]),
        ]
        for title, tip, parts in rows:
            field = QVBoxLayout()
            field.setSpacing(2)
            for part in parts:
                field.addWidget(part) if isinstance(part, QWidget) else field.addLayout(part)
            label = QLabel(title + ":")
            label.setToolTip(tip)
            form.addRow(label, field)
            for part in parts:
                if isinstance(part, QWidget):
                    part.setToolTip(part.toolTip() or tip)

        self.run_button = QPushButton("Run the analysis")
        self.run_button.setStyleSheet("font-weight: bold; padding: 6px 14px;")
        self.run_button.setToolTip("Measure the folders that are new or changed, then write both Excel files.")
        self.run_button.clicked.connect(self.start)
        self.cancel_button = QPushButton("Stop")
        self.cancel_button.setToolTip("Stop after the recording being measured. The folders measured so far are kept.")
        self.cancel_button.clicked.connect(self.cancel)
        self.cancel_button.hide()
        self.write_button = QPushButton("Rewrite the tables")
        self.write_button.setToolTip("Write both Excel files again with the labels and groups shown now. Nothing is measured.")
        self.write_button.clicked.connect(lambda: self.write_tables())
        self.open_button = QPushButton("Open the output folder")
        self.open_button.clicked.connect(self.open_output)
        buttons = QHBoxLayout()
        for button in (self.run_button, self.cancel_button, self.write_button, self.open_button):
            buttons.addWidget(button)
        buttons.addStretch()
        self.progress = QProgressBar()
        self.progress.hide()
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.settings_panel = QWidget()
        self.settings_panel.setLayout(form)
        left = QWidget()
        left.setMinimumWidth(460)
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(self.settings_panel)
        left_layout.addSpacing(8)
        left_layout.addLayout(buttons)
        left_layout.addWidget(self.progress)
        left_layout.addWidget(self.status)
        left_layout.addStretch()

        self.folders_table = QTableWidget(0, 1)
        self.folders_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.folders_table.verticalHeader().setVisible(False)
        folders_page = QWidget()
        folders_layout = QVBoxLayout(folders_page)
        self.folders_hint = _grey()
        folders_layout.addWidget(self.folders_hint)
        folders_layout.addWidget(self.folders_table, 1)
        self.labels_editor = LabelsEditor()
        self.labels_editor.changed.connect(self.labels_changed)
        self.near_misses = NearMissList()
        self.near_misses.changed.connect(self.near_miss_applied)
        self.tabs = QTabWidget()
        self.tabs.addTab(folders_page, "Folders")
        self.tabs.addTab(self.labels_editor, "Labels")
        self.tabs.addTab(self.near_misses, "Near misses")

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([500, 900])
        self.setCentralWidget(splitter)
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1400, screen.width() - 40), min(760, screen.height() - 60))

    def _restore(self):
        """Start where the user left off: the last ROI file, protocol and output folder."""
        self.fill_protocols(remembered("evoked_analysis_protocol"))
        output = remembered("evoked_analysis_output")
        if output:
            self.output.path.setText(output)
            self.output_changed()
        roi_file = remembered("evoked_analysis_roi_file")
        if roi_file and Path(roi_file).is_file():
            self.roi_input.path.setText(roi_file)
            self.load_roi_file()
        self.show_labels()

    # ------------------------------------------------------------------
    # ROI file and folders
    # ------------------------------------------------------------------

    def load_roi_file(self):
        path = self.roi_input.file()
        self.selections = None
        self.roi_info.setToolTip("")
        if path is not None and not path.is_file():
            self.roi_info.setText("⚠ There is no such file.")
        elif path is not None:
            try:
                self.selections = Selections.load(path)
            except (OSError, ValueError, KeyError) as error:
                self.roi_info.setText(f"⚠ {error}")
            else:
                self.roi_info.setToolTip(f"Recordings folder: {self.selections.recordings_folder}")
                remember(evoked_analysis_roi_file=str(path))
        self.refresh_folders()

    def filter_changed(self):
        self.analysis.only_folders_with, self.analysis.skip_folders_with = self.filter.words()
        self.refresh_folders()

    def folder_names(self):
        """The folders of the ROI file that pass the folder filter."""
        if self.selections is None:
            return []
        return [name for name in sorted(self.selections.folders) if self.analysis.matches(name)]

    def refresh_folders(self):
        """Show the folders to measure with their labels, and the near misses in their names."""
        names = self.folder_names()
        labels = self.analysis.labels
        if self.selections is not None:
            folders = self.selections.folders
            reviewed = sum(folders[name].reviewed for name in names)
            self.roi_info.setText(f"{len(names)} of {len(folders)} folders will be measured; {reviewed} of them reviewed.")
        columns = ["Folder", *labels.names()]
        table = self.folders_table
        table.setRowCount(0)
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(columns)
        missing = noted = 0
        recordings_folder = self.selections.recordings_folder if self.selections else ""
        for name in names:
            read = labels.read(labels.parts(name, recordings_folder))
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(name))
            for column, label in enumerate(labels.names(), start=1):
                item = QTableWidgetItem(read.values.get(label, ""))
                notes = [note for note in read.notes if note.startswith(label + ":")]
                if notes:
                    item.setBackground(NOTED)
                    item.setToolTip("\n".join(notes))
                    noted += 1
                elif not item.text():
                    item.setBackground(MISSING)
                    item.setToolTip(f"No {label} in the folder names.")
                    missing += 1
                table.setItem(row, column, item)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        if not names:
            hint = "Choose an ROI file to see its folders and their labels."
        elif missing or noted:
            hint = "Red: not found in the folder names. Orange: to check (hover over it)."
        else:
            hint = "Every label was found."
        self.folders_hint.setText(hint)
        parts = {name: labels.parts(name, recordings_folder) for name in names}
        misses = labels.near_misses(parts)
        self.near_misses.show_misses(labels, misses)
        self.tabs.setTabText(0, f"Folders ({len(names)})" if names else "Folders")
        self.tabs.setTabText(2, f"Near misses ({len(misses)})" if misses else "Near misses")

    # ------------------------------------------------------------------
    # Protocol
    # ------------------------------------------------------------------

    def fill_protocols(self, chosen=""):
        self.protocol_box.clear()
        for entry in library.entries(self.user_folder):
            self.protocol_box.addItem(entry.label, str(entry.path))
        if chosen and self.protocol_box.findData(chosen) < 0 and Path(chosen).is_file():
            self.protocol_box.addItem(f"{Path(chosen).stem}  (file)", chosen)
        index = self.protocol_box.findData(chosen) if chosen else -1
        self.protocol_box.setCurrentIndex(max(index, 0))
        self.choose_protocol()

    def open_protocol_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open a protocol", remembered("evoked_analysis_protocol"), "Protocol files (*.json)")
        if path:
            if self.protocol_box.findData(path) < 0:
                self.protocol_box.addItem(f"{Path(path).stem}  (file)", path)
            self.protocol_box.setCurrentIndex(self.protocol_box.findData(path))
            self.choose_protocol()

    def choose_protocol(self, *_):
        path = self.protocol_box.currentData()
        self.protocol, self.protocol_path = None, None
        self.protocol_info.setToolTip("")
        if not path:
            self.protocol_info.setText("")
            return
        try:
            self.protocol = Protocol.load(path)
        except (OSError, ProtocolError, ValueError, KeyError) as error:
            self.protocol_info.setText(f"<span style='{ERROR}'>⚠ {error}</span>")
            return
        self.protocol_path = path
        remember(evoked_analysis_protocol=path)
        measures = self.protocol.measures()
        per_slice = sum(m.per == "slice" for m in measures)
        text = f"{len(measures) - per_slice} measures per recording, {per_slice} per slice."
        problems = self.protocol.problems()
        if not per_slice:
            problems.append("No per-slice measures: the per-slice file will only list the slices.")
        text += "".join(f"<br><span style='{ERROR}'>⚠ {problem}</span>" for problem in problems)
        self.protocol_info.setText(text)
        self.protocol_info.setToolTip(self.protocol.description)
        self.show_output_info()

    # ------------------------------------------------------------------
    # Output folder, labels and groups
    # ------------------------------------------------------------------

    def output_changed(self):
        """Take over the settings of the analysis kept in the output folder, if it holds one."""
        folder = self.output.folder()
        if folder is None:
            self.show_output_info()
            return
        if (folder / FILE_NAME).is_file():
            try:
                self.analysis = Analysis.load(folder / FILE_NAME)
            except (OSError, ValueError, KeyError) as error:
                self.analysis = Analysis(folder, labels=self.analysis.labels)
                self.output_info.setText(f"<span style='{ERROR}'>⚠ Its {FILE_NAME} cannot be read: {error}</span>")
                return
        else:
            self.analysis = Analysis(folder, labels=self.analysis.labels, only_folders_with=self.analysis.only_folders_with,
                                     skip_folders_with=self.analysis.skip_folders_with, group_by=self.analysis.group_by,
                                     slice_rows_by=self.analysis.slice_rows_by)
        remember(evoked_analysis_output=str(folder))
        self.filter.blockSignals(True)
        self.filter.show_words(self.analysis.only_folders_with, self.analysis.skip_folders_with)
        self.filter.blockSignals(False)
        self.show_labels()
        self.refresh_folders()
        self.show_output_info()

    def show_output_info(self):
        analysis = self.analysis
        measured = sum(bool(result.recordings) for result in analysis.folders.values())
        if analysis.folder is None:
            text = ""
        elif not analysis.folders:
            text = "New: every folder will be measured."
        elif self.protocol is not None and not analysis.is_current(self.protocol):
            text = (f"<span style='{WARNING}'>{_folders(measured)} measured with another protocol: everything will be "
                    "measured again.</span>")
        else:
            text = f"{_folders(measured)} measured before: only new or changed folders will be measured."
        self.output_info.setText(text)
        self.write_button.setEnabled(bool(analysis.folders))

    def show_labels(self):
        self.labels_editor.show_labels(self.analysis.labels)
        self.fill_groups()

    def fill_groups(self):
        """A tick box per label for the groups, and the choices of rows for the per-slice sheets."""
        while self.groups_grid.count():
            self.groups_grid.takeAt(0).widget().deleteLater()
        self.group_boxes = {}
        for n, name in enumerate(self.analysis.labels.names()):
            box = QCheckBox(name)
            box.setChecked(name in self.analysis.group_by)
            box.toggled.connect(self.grouping_changed)
            self.groups_grid.addWidget(box, n // 4, n % 4)
            self.group_boxes[name] = box
        self.rows_box.clear()
        self.rows_box.addItem("One column per group", "")
        for name in self.analysis.labels.names():
            self.rows_box.addItem(f"One row per {name}", name)
        self.rows_box.setCurrentIndex(max(self.rows_box.findData(self.analysis.slice_rows_by), 0))

    def grouping_changed(self, *_):
        self.analysis.group_by = [name for name, box in self.group_boxes.items() if box.isChecked()]
        self.analysis.slice_rows_by = self.rows_box.currentData() or ""

    def labels_changed(self):
        names = self.analysis.labels.names()
        self.analysis.group_by = [name for name in self.analysis.group_by if name in names]
        if self.analysis.slice_rows_by not in names:
            self.analysis.slice_rows_by = ""
        remember(evoked_labels=self.analysis.labels.to_dict())
        self.fill_groups()
        self.refresh_folders()

    def near_miss_applied(self):
        self.labels_editor.show_labels(self.analysis.labels)
        self.labels_changed()

    # ------------------------------------------------------------------
    # Running
    # ------------------------------------------------------------------

    def problems(self):
        found = []
        if self.selections is None:
            found.append("Choose an ROI file.")
        if self.protocol is None:
            found.append("Choose a protocol.")
        elif self.protocol.problems():
            found.append("The protocol is not complete: " + " ".join(self.protocol.problems()))
        folder = self.output.folder()
        if folder is None:
            found.append("Choose an output folder.")
        elif self.selections is not None and _is_inside(folder, self.selections.recordings_folder):
            found.append("The output folder must be outside the recordings folder, so the recordings stay untouched.")
        found += self.analysis.labels.problems()
        if self.selections is not None and not self.folder_names():
            found.append("No folder of the ROI file passes the folder filter.")
        return found

    def start(self):
        problems = self.problems()
        if problems:
            QMessageBox.warning(self, "Please check", "\n\n".join(problems))
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            the_plan = plan(self.analysis, self.protocol, self.selections)
        finally:
            QApplication.restoreOverrideCursor()
        if not self.confirm(the_plan):
            return
        keep_others = self.keep_others(the_plan)
        if keep_others is None:
            return
        self.analysis.roi_file = str(self.roi_input.file())
        self.worker = Worker(self.analysis, self.protocol, self.selections, the_plan, keep_others)
        self.worker.progressed.connect(self.show_progress)
        self.worker.finished.connect(self.finished)
        self.set_running(True)
        self.started = time.monotonic()
        self.worker.start()

    def confirm(self, the_plan):
        """Ask before the kept results are replaced. True to run."""
        if not the_plan.replace_all:
            return True
        dropped = (f" The results of folders that are not in this ROI file ({_folders(len(the_plan.kept_others))}) "
                   "are dropped." if the_plan.kept_others else "")
        answer = QMessageBox.question(
            self, "Measure everything again?",
            "The results kept in the output folder were measured with another protocol (or another version of "
            f"EMA). All folders will be measured again with {self.protocol.name}, and both Excel files replaced."
            f"{dropped}\n\nContinue?",
        )
        return answer == QMessageBox.Yes

    def keep_others(self, the_plan):
        """Ask whether to keep the folders of earlier runs that are not in this ROI file. None: do not run."""
        if the_plan.replace_all or not the_plan.kept_others:
            return True
        names = [self.analysis.folders[key].name for key in the_plan.kept_others]
        examples = "\n".join(names[:3]) + ("\n…" if len(names) > 3 else "")
        answer = QMessageBox.question(
            self, "Keep the other folders?",
            "The output folder holds the results of folders that are not in this ROI file (or do not pass the "
            f"folder filter): {_folders(len(names))}, for example\n\n{examples}\n\nKeep them in the tables? Choose "
            "No if they are these same recordings in another place, so they are not in the tables twice.",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
        )
        return None if answer == QMessageBox.Cancel else answer == QMessageBox.Yes

    def set_running(self, running):
        self.settings_panel.setEnabled(not running)
        self.labels_editor.setEnabled(not running)
        self.near_misses.setEnabled(not running)
        self.cancel_button.setVisible(running)
        self.cancel_button.setEnabled(running)
        self.run_button.setEnabled(not running)
        self.write_button.setEnabled(not running and bool(self.analysis.folders))
        self.progress.setVisible(running)
        if running:
            self.progress.setValue(0)
            self.status.setText("Checking what is new…")

    def show_progress(self, done, total, text):
        self.progress.setMaximum(max(total, 1))
        self.progress.setValue(done)
        self.status.setText(f"Measuring {min(done + 1, total)} of {total}: {text}" if done < total else "Writing the tables…")

    def cancel(self):
        if self.worker is not None:
            self.worker.stop = True
            self.cancel_button.setEnabled(False)
            self.status.setText("Stopping after this recording…")

    def finished(self):
        worker, self.worker = self.worker, None
        self.set_running(False)
        if worker.error is not None:
            self.status.setText(f"<span style='{ERROR}'>⚠ The analysis stopped: {worker.error}</span>")
            return
        the_plan = worker.args[3]
        self.analysis.save()
        measured = [path.as_posix() for path, _, _ in the_plan.to_measure if path.as_posix() in self.analysis.folders]
        recordings = sum(len(self.analysis.folders[key].recordings) for key in measured)
        skipped = sum(len(self.analysis.folders[key].skipped) for key in measured)
        minutes, seconds = divmod(round(time.monotonic() - self.started), 60)
        lines = [f"{'Stopped' if worker.stop else 'Done'} in {minutes} min {seconds} s: {_folders(len(measured))} "
                 f"measured ({recordings} recordings), {len(the_plan.unchanged)} unchanged."]
        if skipped:
            lines.append(f"{skipped} recordings not measured: see the Notes sheet.")
        if the_plan.missing:
            lines.append(f"⚠ {_folders(len(the_plan.missing))} of the ROI file not found on this computer.")
        if worker.stop:
            lines.append("Run again to measure the rest.")
        self.status.setText("\n".join(lines))
        self.show_output_info()
        self.write_tables(quiet=True)

    def write_tables(self, quiet=False):
        if not self.analysis.folders or self.analysis.protocol is None:
            return
        try:
            self.analysis.save()
            write_workbooks(self.analysis)
        except TablesLocked as error:
            QMessageBox.warning(self, "Close the file in Excel", str(error))
            return
        except OSError as error:
            QMessageBox.warning(self, "The tables could not be written", str(error))
            return
        self.status.setText((self.status.text() + "\n" if quiet else "") + "Tables written.")

    def open_output(self):
        folder = self.output.folder()
        if folder is not None and folder.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def closeEvent(self, event):
        if self.worker is not None:
            answer = QMessageBox.question(self, "Stop the analysis?", "The analysis is running. Stop it and close? "
                                          "The folders measured so far are kept.")
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            self.worker.finished.disconnect()
            self.worker.stop = True
            self.worker.wait()
            self.analysis.save()
        self.closed.emit()
        super().closeEvent(event)


def _remembered_labels():
    saved = remembered("evoked_labels", None)
    if saved:
        try:
            return LabelSet.from_dict(saved)
        except (KeyError, TypeError, AttributeError):
            pass
    return default_labels()
