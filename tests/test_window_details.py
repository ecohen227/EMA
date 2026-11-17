"""Small behaviours of the windows that protect the user's work."""

import pytest
from PyQt5.QtWidgets import QApplication, QInputDialog, QMessageBox

from ema import user_settings
from ema.labels import default_labels
from ema.labels_editor import LabelsEditor
from ema.widgets import FolderInput, with_unit


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def own_user_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(user_settings, "FILE", tmp_path / "user" / "settings.json")


def test_units_are_shown_unless_they_repeat_the_name():
    assert with_unit("onset", "s") == "onset (s)"
    assert with_unit("tail fraction", "fraction") == "tail fraction"
    assert with_unit("events", "") == "events"


def test_leaving_a_path_unchanged_is_not_a_change(app):
    field = FolderInput("Choose", "C:/data")
    changes = []
    field.changed.connect(lambda: changes.append(field.folder()))
    field.path.editingFinished.emit()
    assert not changes
    field.path.setText("C:/other")
    field.path.editingFinished.emit()
    field.path.editingFinished.emit()
    assert len(changes) == 1


def test_removing_a_label_asks_first(app, monkeypatch):
    editor = LabelsEditor()
    labels = default_labels()
    editor.show_labels(labels)
    editor.tree.setCurrentItem(editor.tree.topLevelItem(0))
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.No)
    editor.remove()
    assert labels.names()[0] == "Line"
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.Yes)
    editor.remove()
    assert "Line" not in labels.names()


def test_a_new_protocol_needs_a_name(app, monkeypatch):
    from ema.evoked_configurator.template_dialog import TemplateDialog

    said = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args: said.append(args[2]))
    dialog = TemplateDialog(None, "")
    dialog.accept()
    assert said == ["Give the protocol a name."] and not dialog.result()


def test_the_spontaneous_configurator_saves_and_deletes_with_the_shared_bar(app, tmp_path, monkeypatch):
    from ema.spontaneous_configurator.window import SpontaneousConfiguratorWindow

    window = SpontaneousConfiguratorWindow(user_folder=tmp_path / "detectors")
    bar = window.bar
    assert bar.entry.built_in and not bar.unsaved and not bar.buttons["Delete"].isEnabled()
    window.form.inputs["event_z"].setValue(6.0)
    assert bar.unsaved and "not saved" in bar.state.text()
    monkeypatch.setattr(QInputDialog, "getText", lambda *args, **kwargs: ("Low threshold", True))
    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
    assert bar.save()  # a built-in detector is saved under a new name
    assert bar.entry.name == "Low threshold" and not bar.entry.built_in and not bar.unsaved
    assert (tmp_path / "detectors" / "Low threshold.json").is_file()
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)
    bar.delete()
    assert bar.entry.built_in and not (tmp_path / "detectors" / "Low threshold.json").exists()
    window.close()


def test_a_detector_with_problems_is_not_saved(app, tmp_path, monkeypatch):
    from ema.spontaneous_configurator.window import SpontaneousConfiguratorWindow

    window = SpontaneousConfiguratorWindow(user_folder=tmp_path / "detectors")
    window.form.inputs["region_z"].setValue(20.0)  # above the event threshold
    warned = []
    monkeypatch.setattr(QInputDialog, "getText", lambda *args, **kwargs: ("Broken", True))
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warned.append(args[2]))
    assert not window.bar.save()
    assert "event threshold must be at least the region threshold" in warned[0]
    assert not (tmp_path / "detectors").exists()
    window.bar.saved = window.detector.to_dict()
    window.close()
