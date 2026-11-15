"""Labels read from folder names, and near misses."""

import pytest

from ema.labels import Label, LabelSet, default_labels, find, words


def read(labels, path, root="C:/recordings"):
    return labels.read(labels.parts(path, root))


def test_folder_names_are_cut_into_words():
    assert words("IFNy_4hr") == ["ifny", "4", "hr"]
    assert words("Slice3 (rostral)") == ["slice", "3", "rostral"]
    assert words("LKI HET M5821") == ["lki", "het", "m", "5821"]
    assert words("IFNγ 2H") == ["ifnγ", "2", "h"]


@pytest.mark.parametrize("spelling, name, found", [
    ("4H", "IFN 4H", True),
    ("4H", "IFNy_4h", True),
    ("4H", "IFN 14H", False),
    ("4H", "IFN 4HR", False),
    ("Slice #", "slice3", True),
    ("Slice #", "extra slice (rostral)", False),
    ("input output", "Input_Output", True),
    ("F#", "GKI WT F5463 CG", True),
    ("F#", "Females", False),
])
def test_a_spelling_matches_whole_words_in_order(spelling, name, found):
    assert bool(find(spelling, words(name))) == found


def test_the_lab_folders_get_every_label():
    values = read(default_labels(), "Females/LKI HET F5819/IFNy_4hr/Slice 2/11p at 200uA").values
    assert values == {"Line": "LKI", "Genotype": "HET", "Treatment": "IFN", "Duration": "4H", "Sex": "F",
                      "Animal": "5819", "Slice": "2"}
    values = read(default_labels(), "Males/AK Recordings/GKI WT M5139/Control/Slice3/input_ouput").values
    assert values["Treatment"] == "CTRL" and values["Duration"] == "" and values["Slice"] == "3"


def test_the_innermost_folder_wins_and_a_disagreement_is_noted():
    labels = default_labels()
    found = read(labels, "Females/GKI HET F5383/GKI HET F5561/CTRL 4H/Slice 3/11p")
    assert found.values["Animal"] == "5561"
    assert found.notes == ["Animal: 5561 from 'GKI HET F5561', but 'GKI HET F5383' says 5383."]


def test_two_values_in_one_folder_name_leave_the_label_empty():
    found = read(default_labels(), "WT HET M1/CTRL/Slice 1")
    assert found.values["Genotype"] == ""
    assert "more than one value (WT, HET)" in found.notes[0]


def test_the_folders_above_the_recordings_folder_are_read_only_when_asked():
    labels = default_labels()
    assert read(labels, "CTRL/Slice 1", root="D:/LKI HET M5821").values["Genotype"] == ""
    labels.whole_path = True
    assert read(labels, "CTRL/Slice 1", root="D:/LKI HET M5821").values["Genotype"] == "HET"


def test_near_misses_are_found_with_a_suggestion():
    labels = LabelSet([
        Label("Genotype", {"WT": ["WT"], "HET": ["HET"]}),
        Label("Treatment", {"CTRL": ["CTRL"], "IFN": ["IFN"]}),
        Label("Slice", patterns=["Slice #"]),
    ])
    folders = {name: labels.parts(name, "C:/r") for name in
               ["HTE M1/Contrl/Slcie 1", "WT M2/CNTRL/Slice 2", "WT M3/IFNy 4H/Slice 1", "WT M3/IFN 4H/Slice 2"]}
    found = {(m.word, m.label, m.value, m.suggestion) for m in labels.near_misses(folders)}
    assert found == {
        ("HTE", "Genotype", "HET", "HTE"),
        ("Contrl", "Treatment", "CTRL", "Contrl"),
        ("CNTRL", "Treatment", "CTRL", "CNTRL"),
        ("IFNy", "Treatment", "IFN", "IFNy"),
        ("Slcie", "Slice", "", "Slcie #"),
    }


def test_a_near_miss_disappears_once_it_is_decided():
    labels = LabelSet([Label("Treatment", {"CTRL": ["CTRL"], "IFN": ["IFN"]})])
    folders = {"a": labels.parts("Contrl/x", "C:/r"), "b": labels.parts("IFNy/x", "C:/r")}
    labels.add_spelling("Treatment", "CTRL", "Contrl")
    labels.ignore("ifny")
    assert labels.near_misses(folders) == []
    assert read(labels, "Contrl/x").values["Treatment"] == "CTRL"


def test_common_folder_words_are_not_near_misses():
    names = ["Females/AK Recordings/GKI WT F4929/CTRL/Slice1/11pulses", "Males/GKI WT M5552 CG/IFN 2H/Slice 4/input output",
             "Females/GKI HET F5341/CNTRL 2HR/Slice 2 (electrode test)/input output exclude",
             "Males/GKI WT M5426/IFN 4H + 4AP/Slice 1/4ap wash on", "x/IFNy_4h/extra slice (rostral)/Input Output (black)"]
    labels = default_labels()
    assert labels.near_misses({name: labels.parts(name, "C:/r") for name in names}) == []


def test_labels_are_saved_and_read_back():
    labels = default_labels()
    labels.ignore("ouput")
    labels.whole_path = True
    again = LabelSet.from_dict(labels.to_dict())
    assert again == labels


def test_problems_with_labels_are_named():
    labels = LabelSet([Label("A", {"x": []}), Label("A", patterns=["Slice"])])
    problems = labels.problems()
    assert "Two labels have the same name." in problems
    assert "A: x needs at least one spelling." in problems
    assert "A: every spelling of a number label needs a # for the number." in problems
    assert default_labels().problems() == []


def test_values_sort_in_the_order_they_are_listed():
    genotype = default_labels().label("Genotype")
    assert sorted(["HET", "", "WT"], key=genotype.sort_key) == ["WT", "HET", ""]
    slice_ = default_labels().label("Slice")
    assert sorted(["10", "2", ""], key=slice_.sort_key) == ["2", "10", ""]
