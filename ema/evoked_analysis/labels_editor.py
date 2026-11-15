"""Editing the labels read from folder names, and deciding what near misses mean."""

import json
from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..labels import Label, LabelSet, default_labels

NOT_A_LABEL = "Not a label"


def _hint(text):
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet("color: gray")
    return label


def _split(text):
    return [part.strip() for part in text.split(",") if part.strip()]


class LabelsEditor(QWidget):
    """The labels as a tree: each label, and under it its values with their spellings.

    A label without values is a number label: its spellings hold a # for the
    number, which is its value. Double-click a name or the spellings to change
    them. The label set shown is changed in place; `changed` follows each edit.
    """

    changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.labels = LabelSet()
        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Label and its values", "Spellings in folder names (separated by commas)"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tree.setEditTriggers(QTreeWidget.NoEditTriggers)
        self.tree.itemDoubleClicked.connect(self._edit)
        self.tree.itemChanged.connect(self._read_tree)

        buttons = QHBoxLayout()
        for text, tip, action in (
            ("Add label", "A label with values, such as Genotype with WT and HET.", self.add_label),
            ("Add number label", "A label whose value is a number in the folder name, such as Slice in 'Slice 3'.", self.add_number_label),
            ("Add value", "Another value of the selected label.", self.add_value),
            ("Remove", "Remove the selected label or value.", self.remove),
            ("▲", "Move the selected label or value up.", lambda: self.move(-1)),
            ("▼", "Move the selected label or value down.", lambda: self.move(1)),
        ):
            button = QPushButton(text)
            button.setToolTip(tip)
            button.clicked.connect(action)
            buttons.addWidget(button)
        buttons.addStretch()
        files = QHBoxLayout()
        for text, tip, action in (
            ("Restore defaults", "The labels of the lab's folder names: line, genotype, treatment, duration, sex, animal, slice.", self.restore_defaults),
            ("Import…", "Use the labels saved in a labels file or in another analysis.", self.import_labels),
            ("Export…", "Save these labels in a file, for example to share them.", self.export_labels),
        ):
            button = QPushButton(text)
            button.setToolTip(tip)
            button.clicked.connect(action)
            files.addWidget(button)
        files.addStretch()
        self.whole_path = QCheckBox("Also read the recordings folder and the folders above it")
        self.whole_path.setToolTip(
            "Off: only the folders inside the recordings folder of the ROI file are read.\n"
            "On: the recordings folder and every folder above it are read too (the nearest folder still wins)."
        )
        self.whole_path.toggled.connect(self._whole_path_toggled)

        layout = QVBoxLayout(self)
        layout.addWidget(_hint(
            "Each folder name is cut into words at spaces, punctuation and where letters meet digits, ignoring case: "
            "'IFNy_4hr' is ifny, 4, hr. A spelling matches when its words appear in that order: '4HR' matches "
            "'IFNy_4hr' but not '14HR'. In a spelling, # stands for any number: 'Slice #' matches 'Slice 3' and "
            "'slice3', and 'F#' matches 'F5819'. The folders are read from the innermost out; the first one that "
            "holds a label gives its value. Double-click a name or a list of spellings to change it."
        ))
        layout.addLayout(buttons)
        layout.addWidget(self.tree, 1)
        layout.addWidget(self.whole_path)
        layout.addLayout(files)

    def show_labels(self, labels):
        self.labels = labels
        self.whole_path.blockSignals(True)
        self.whole_path.setChecked(labels.whole_path)
        self.whole_path.blockSignals(False)
        self._fill()

    def _fill(self, select=None):
        self.tree.blockSignals(True)
        self.tree.clear()
        for label in self.labels.labels:
            top = QTreeWidgetItem([label.name, ", ".join(label.patterns) if label.is_number else ""])
            top.setToolTip(0, "A number label: its value is the number that # stands for." if label.is_number else "A label")
            font = top.font(0)
            font.setBold(True)
            top.setFont(0, font)
            self.tree.addTopLevelItem(top)
            for value, spellings in label.values.items():
                top.addChild(QTreeWidgetItem([value, ", ".join(spellings)]))
            top.setExpanded(True)
            if select == (label.name, None):
                self.tree.setCurrentItem(top)
            for i in range(top.childCount()):
                if select == (label.name, top.child(i).text(0)):
                    self.tree.setCurrentItem(top.child(i))
        self.tree.blockSignals(False)

    def _edit(self, item, column):
        if column == 0 or item.parent() is not None or item.childCount() == 0:
            self.tree.blockSignals(True)
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            self.tree.blockSignals(False)
            self.tree.editItem(item, column)

    def _read_tree(self):
        """Take the labels from the tree, as edited."""
        labels = []
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            name = top.text(0).strip()
            if top.childCount():
                values = {}
                for j in range(top.childCount()):
                    child = top.child(j)
                    values[child.text(0).strip()] = _split(child.text(1))
                labels.append(Label(name, values))
            else:
                labels.append(Label(name, patterns=_split(top.text(1))))
        self.labels.labels = labels
        self.changed.emit()

    def _selected(self):
        """(label index, value index or None) of the selected row, or None."""
        item = self.tree.currentItem()
        if item is None:
            return None
        if item.parent() is None:
            return self.tree.indexOfTopLevelItem(item), None
        return self.tree.indexOfTopLevelItem(item.parent()), item.parent().indexOfChild(item)

    def _new_name(self, base, taken):
        name, n = base, 2
        while name.lower() in {t.lower() for t in taken}:
            name, n = f"{base} {n}", n + 1
        return name

    def add_label(self):
        name = self._new_name("New label", self.labels.names())
        self.labels.labels.append(Label(name, {"Value 1": ["value1"]}))
        self._after_change((name, None))

    def add_number_label(self):
        name = self._new_name("New number", self.labels.names())
        self.labels.labels.append(Label(name, patterns=["Name #"]))
        self._after_change((name, None))

    def add_value(self):
        selected = self._selected()
        if selected is None:
            QMessageBox.information(self, "Add value", "Select the label to add a value to.")
            return
        label = self.labels.labels[selected[0]]
        value = self._new_name("New value", list(label.values))
        label.values[value] = [value.replace(" ", "").lower()]
        label.patterns = []
        self._after_change((label.name, value))

    def remove(self):
        selected = self._selected()
        if selected is None:
            return
        label_index, value_index = selected
        label = self.labels.labels[label_index]
        if value_index is None:
            del self.labels.labels[label_index]
        else:
            del label.values[list(label.values)[value_index]]
            if not label.values:
                label.patterns = ["Name #"]
        self._after_change()

    def move(self, step):
        selected = self._selected()
        if selected is None:
            return
        label_index, value_index = selected
        if value_index is None:
            items = self.labels.labels
            target = label_index + step
            if 0 <= target < len(items):
                items[label_index], items[target] = items[target], items[label_index]
            self._after_change((items[target if 0 <= target < len(items) else label_index].name, None))
            return
        label = self.labels.labels[label_index]
        values = list(label.values.items())
        target = value_index + step
        if 0 <= target < len(values):
            values[value_index], values[target] = values[target], values[value_index]
            label.values = dict(values)
        self._after_change((label.name, values[min(max(target, 0), len(values) - 1)][0]))

    def restore_defaults(self):
        defaults = default_labels()
        self.labels.labels, self.labels.ignored = defaults.labels, []
        self._after_change()

    def import_labels(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import labels", "", "Labels or analysis files (*.json)")
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            labels = LabelSet.from_dict(data.get("labels") if isinstance(data.get("labels"), dict) else data)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            QMessageBox.warning(self, "Import labels", f"{Path(path).name} holds no labels EMA can read.\n\n{error}")
            return
        self.labels.labels, self.labels.ignored, self.labels.whole_path = labels.labels, labels.ignored, labels.whole_path
        self.show_labels(self.labels)
        self.changed.emit()

    def export_labels(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export labels", "labels.json", "Labels files (*.json)")
        if path:
            Path(path).write_text(json.dumps(self.labels.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    def _whole_path_toggled(self, on):
        self.labels.whole_path = on
        self.changed.emit()

    def _after_change(self, select=None):
        self._fill(select)
        self.changed.emit()


class NearMissList(QWidget):
    """The near misses: words in folder names that look like a spelling but are not one. The user says what each means."""

    changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.labels = None
        self.misses = []
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Word", "Looks like", "In folders", "It means", ""])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        header = self.table.horizontalHeader()
        for column in range(5):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        self.empty = QLabel("No near misses: every word that looks like a spelling is one.")
        layout = QVBoxLayout(self)
        layout.addWidget(_hint(
            "Words in the folder names that look like a spelling of a label but are not one, such as 'Contrl' for "
            "CTRL or 'HTE' for HET. Say what each means: it is then added to the spellings of that value, or never "
            "shown again if it is not a label. Hover over the folder count to see the folders."
        ))
        layout.addWidget(self.empty)
        layout.addWidget(self.table, 1)

    def show_misses(self, labels, misses):
        self.labels, self.misses = labels, misses
        self.empty.setVisible(not misses)
        self.table.setVisible(bool(misses))
        self.table.setRowCount(0)
        for miss in misses:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(miss.word))
            looks = f"{miss.value} ({miss.label})" if miss.value else f"{miss.label} number"
            self.table.setItem(row, 1, QTableWidgetItem(f"{looks}: {miss.spelling}"))
            count = QTableWidgetItem(f"{len(miss.folders)}: {miss.folders[0]}" + (" …" if len(miss.folders) > 1 else ""))
            count.setToolTip("\n".join(miss.folders[:40]) + ("\n…" if len(miss.folders) > 40 else ""))
            self.table.setItem(row, 2, count)
            choice = QComboBox()
            label = labels.label(miss.label)
            if label.is_number:
                choice.addItem(f"{miss.label} number: add '{miss.suggestion}'", (miss.label, ""))
            else:
                for value in [miss.value] + [v for v in label.values if v != miss.value]:
                    choice.addItem(f"{value} ({miss.label})", (miss.label, value))
            choice.addItem(NOT_A_LABEL, None)
            self.table.setCellWidget(row, 3, choice)
            apply = QPushButton("Apply")
            apply.clicked.connect(lambda _, m=miss, box=choice: self.apply(m, box.currentData()))
            self.table.setCellWidget(row, 4, apply)

    def apply(self, miss, meaning):
        if meaning is None:
            self.labels.ignore(miss.word)
        else:
            self.labels.add_spelling(meaning[0], meaning[1], miss.suggestion)
        self.changed.emit()
