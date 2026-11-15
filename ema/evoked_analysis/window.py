"""Evoked Analysis: measure the recordings of every folder in an ROI file with a protocol, and write the tables."""

import time
from pathlib import Path

from PyQt5.QtCore import Qt, QThread, QUrl, pyqtSignal
from PyQt5.QtGui import QColor, QDesktopServices
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
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


def _hint(text=""):
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet("color: gray")
    return label


def _folders(count):
    return f"{count} folder" if count == 1 else f"{count} folders"


def _short(path, parts=3):
    """The last folders of a long path, such as '…\\Slice 1\\input output'; the whole path when it is short."""
    path = Path(path)
    return str(path) if len(path.parts) <= parts + 1 else "…\\" + "\\".join(path.parts[-parts:])


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
        self.entries = []
        self._build_window()
        self._restore()

    # ------------------------------------------------------------------
    # Building the window
    # ------------------------------------------------------------------

    def _build_window(self):
        self.roi_input = FileInput("Choose the ROI file", "ROI files (roi_selections.json);;JSON files (*.json)")
        self.roi_input.changed.connect(self.load_roi_file)
        self.roi_info = _hint()
        self.filter = FolderFilter()
        self.filter.changed.connect(self.filter_changed)
        self.folder_count = QLabel()

        self.protocol_box = QComboBox()
        self.protocol_box.setMinimumWidth(240)
        self.protocol_box.activated.connect(self.choose_protocol)
        open_protocol = QPushButton("Open file…")
        open_protocol.setToolTip("Use a protocol file that is not in the library.")
        open_protocol.clicked.connect(self.open_protocol_file)
        protocol_row = QHBoxLayout()
        protocol_row.addWidget(self.protocol_box, 1)
        protocol_row.addWidget(open_protocol)
        self.protocol_info = _hint()
        self.protocol_problems = QLabel()
        self.protocol_problems.setWordWrap(True)

        self.output = FolderInput("Choose the output folder")
        self.output.changed.connect(self.output_changed)
        self.output_info = QLabel()
        self.output_info.setWordWrap(True)

        self.group_list = QListWidget()
        self.group_list.setMaximumHeight(120)
        self.group_list.itemChanged.connect(self.grouping_changed)
        self.rows_box = QComboBox()
        self.rows_box.activated.connect(self.grouping_changed)
        rows_row = QHBoxLayout()
        rows_row.addWidget(QLabel("Rows of the per-slice measure sheets:"))
        rows_row.addWidget(self.rows_box, 1)

        self.run_button = QPushButton("Run the analysis")
        self.run_button.setStyleSheet("font-weight: bold; padding: 6px 14px;")
        self.run_button.clicked.connect(self.start)
        self.cancel_button = QPushButton("Stop")
        self.cancel_button.setToolTip("Stop after the recording being measured. The folders measured so far are kept.")
        self.cancel_button.clicked.connect(self.cancel)
        self.cancel_button.hide()
        self.write_button = QPushButton("Write the tables")
        self.write_button.setToolTip("Write both Excel files again from the results kept in the output folder, with the "
                                     "labels and groups shown now. Nothing is measured.")
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

        steps = QWidget()
        layout = QVBoxLayout(steps)
        layout.addWidget(self._step("1.  ROI file", "The roi_selections.json made by ROI Selection. Its folders are "
                                    "measured, each with its ROI and electrode; flagged recordings are left out.",
                                    self.roi_input, self.roi_info, self.filter, self.folder_count))
        layout.addWidget(self._step("2.  Protocol", "What is measured, as set in the Evoked Analysis Configurator.",
                                    protocol_row, self.protocol_info, self.protocol_problems))
        layout.addWidget(self._step("3.  Output folder", f"The two Excel files ({PER_RECORDING}, {PER_SLICE}) and "
                                    f"{FILE_NAME}, which keeps the results so that a new run measures only what is "
                                    "new. Nothing is ever written into the recordings.", self.output, self.output_info))
        layout.addWidget(self._step("4.  Groups in the tables", "Slices are grouped by the values of the ticked labels, "
                                    "such as WT CTRL and HET CTRL: one group of columns each in the Prism sheets.",
                                    self.group_list, rows_row))
        layout.addStretch()
        self.settings_panel = steps
        scroll = QScrollArea()
        scroll.setWidget(steps)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left = QWidget()
        left.setMinimumWidth(480)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(scroll, 1)
        left_layout.addLayout(buttons)
        left_layout.addWidget(self.progress)
        left_layout.addWidget(self.status)

        self.folders_table = QTableWidget(0, 1)
        self.folders_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.folders_table.verticalHeader().setVisible(False)
        self.folders_table.setSortingEnabled(False)
        folders_page = QWidget()
        folders_layout = QVBoxLayout(folders_page)
        self.folders_hint = _hint()
        folders_layout.addWidget(self.folders_hint)
        folders_layout.addWidget(self.folders_table, 1)
        self.labels_editor = LabelsEditor()
        self.labels_editor.changed.connect(self.labels_changed)
        self.near_misses = NearMissList()
        self.near_misses.changed.connect(self.near_miss_applied)
        self.tabs = QTabWidget()
        self.tabs.addTab(folders_page, "Folders and their labels")
        self.tabs.addTab(self.labels_editor, "Labels")
        self.tabs.addTab(self.near_misses, "Near misses")

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([520, 880])
        self.setCentralWidget(splitter)
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1400, screen.width() - 40), min(860, screen.height() - 60))

    def _step(self, title, explanation, *parts):
        box = QGroupBox(title)
        layout = QVBoxLayout(box)
        layout.addWidget(_hint(explanation))
        for part in parts:
            if isinstance(part, QWidget):
                layout.addWidget(part)
            else:
                layout.addLayout(part)
        return box

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
        if path is None:
            self.roi_info.setText("")
        elif not path.is_file():
            self.roi_info.setText("⚠ There is no such file.")
        else:
            try:
                self.selections = Selections.load(path)
            except (OSError, ValueError, KeyError) as error:
                self.roi_info.setText(f"⚠ {error}")
            else:
                folders = self.selections.folders
                reviewed = sum(s.reviewed for s in folders.values())
                self.roi_info.setText(f"Recordings folder: {_short(self.selections.recordings_folder)}\n"
                                      f"{len(folders)} folders with an ROI, {reviewed} of them reviewed.")
                self.roi_info.setToolTip(str(self.selections.recordings_folder))
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
        total = len(self.selections.folders) if self.selections else 0
        self.folder_count.setText(f"{len(names)} of {total} folders will be measured." if self.selections else "")
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
        self.folders_hint.setText(
            "The labels read from each folder's names. Red: not found (the cell stays empty in the tables). "
            "Orange: two folder names disagree, or one holds two values; hover to see. Change the spellings on the "
            f"Labels tab. {missing} not found, {noted} to check." if names else
            "Choose an ROI file to see its folders and the labels read from their names.")
        parts = {name: labels.parts(name, recordings_folder) for name in names}
        misses = labels.near_misses(parts)
        self.near_misses.show_misses(labels, misses)
        self.tabs.setTabText(2, f"Near misses ({len(misses)})" if misses else "Near misses")
        self.tabs.setTabText(0, f"Folders and their labels ({len(names)})")

    # ------------------------------------------------------------------
    # Protocol
    # ------------------------------------------------------------------

    def fill_protocols(self, chosen=""):
        self.entries = library.entries(self.user_folder)
        self.protocol_box.clear()
        for entry in self.entries:
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
        if not path:
            self.protocol_info.setText("")
            return
        try:
            self.protocol = Protocol.load(path)
        except (OSError, ProtocolError, ValueError, KeyError) as error:
            self.protocol_info.setText("")
            self.protocol_problems.setText(f"<span style='color:#c1121f'>⚠ {error}</span>")
            self.protocol_problems.show()
            return
        self.protocol_path = path
        remember(evoked_analysis_protocol=path)
        per_slice = sum(m.per == "slice" for m in self.protocol.measures())
        per_recording = sum(m.per == "recording" for m in self.protocol.measures())
        self.protocol_info.setText(f"{self.protocol.description}\n{per_recording} measures per recording, {per_slice} per slice.")
        problems = self.protocol.problems()
        if not per_slice:
            problems.append("It has no per-slice measures, so the per-slice file will only list the slices. "
                            "Choose them in the configurator, under Comparisons and summary.")
        self.protocol_problems.setText("<br>".join(f"<span style='color:#c1121f'>⚠ {p}</span>" for p in problems))
        self.protocol_problems.setVisible(bool(problems))
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
                self.output_info.setText(f"⚠ The {FILE_NAME} there cannot be read: {error}")
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
            text = "A new analysis: every folder will be measured."
        elif self.protocol is not None and not analysis.is_current(self.protocol):
            old = analysis.protocol_object().name if analysis.protocol else "?"
            text = (f"<span style='color:#b35c00'>Holds the results of {_folders(measured)}, measured with "
                    f"<b>{old}</b> as it was then (or with another version of EMA). The protocol chosen differs, so "
                    "every folder will be measured again and both files replaced.</span>")
        else:
            text = (f"Holds the results of {_folders(measured)}, measured with this protocol. A run measures only "
                    "folders that are new or changed and adds them; the others keep their results.")
        self.output_info.setText(text)
        self.write_button.setEnabled(bool(analysis.folders))

    def show_labels(self):
        self.labels_editor.show_labels(self.analysis.labels)
        self.fill_groups()

    def fill_groups(self):
        names = self.analysis.labels.names()
        self.group_list.blockSignals(True)
        self.group_list.clear()
        for name in names:
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if name in self.analysis.group_by else Qt.Unchecked)
            self.group_list.addItem(item)
        self.group_list.blockSignals(False)
        self.rows_box.clear()
        self.rows_box.addItem("none: a column table, one column per group", "")
        for name in names:
            self.rows_box.addItem(f"{name}: a grouped table, one row per {name}", name)
        self.rows_box.setCurrentIndex(max(self.rows_box.findData(self.analysis.slice_rows_by), 0))

    def grouping_changed(self, *_):
        group_by = [self.group_list.item(i).text() for i in range(self.group_list.count())
                    if self.group_list.item(i).checkState() == Qt.Checked]
        self.analysis.group_by = group_by
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
            self.status.setText(f"<span style='color:#c1121f'>⚠ The analysis stopped: {worker.error}</span>")
            return
        the_plan = worker.args[3]
        self.analysis.save()
        stopped = worker.stop
        measured = [path.as_posix() for path, _, _ in the_plan.to_measure if path.as_posix() in self.analysis.folders]
        recordings = sum(len(self.analysis.folders[key].recordings) for key in measured)
        skipped = sum(len(self.analysis.folders[key].skipped) for key in measured)
        minutes, seconds = divmod(round(time.monotonic() - self.started), 60)
        lines = [f"{'Stopped' if stopped else 'Done'}: {_folders(len(measured))} measured ({recordings} recordings) in "
                 f"{minutes} min {seconds} s."]
        if the_plan.unchanged:
            lines.append(f"{_folders(len(the_plan.unchanged))} unchanged: their results were kept.")
        if the_plan.kept_others and worker.keep_others:
            lines.append(f"{_folders(len(the_plan.kept_others))} from earlier runs, not in this ROI file, kept.")
        if the_plan.missing:
            lines.append(f"⚠ {_folders(len(the_plan.missing))} of the ROI file not on this computer.")
        if skipped:
            lines.append(f"{skipped} recordings were not measured; the Notes sheets say why.")
        if stopped:
            lines.append("Run again to measure the rest; what was measured is kept.")
        self.status.setText("\n".join(lines))
        self.show_output_info()
        self.write_tables(quiet=True)

    def write_tables(self, quiet=False):
        if not self.analysis.folders or self.analysis.protocol is None:
            return
        try:
            self.analysis.save()
            paths = write_workbooks(self.analysis)
        except TablesLocked as error:
            QMessageBox.warning(self, "Close the file in Excel", str(error))
            return
        except OSError as error:
            QMessageBox.warning(self, "The tables could not be written", str(error))
            return
        written = " and ".join(path.name for path in paths)
        text = self.status.text() + f"\n{written} written." if quiet else f"{written} written."
        self.status.setText(text.strip())

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
