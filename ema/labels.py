"""Labels read from folder names, such as genotype, treatment, animal and slice.

A label (Genotype) has values (WT, HET), and each value has the spellings that
mean it in a folder name (HET, het). A number label (Slice) has spellings with
#, and its value is the number that # stands for.

Matching works on words. A name is cut into words at spaces and punctuation
and where letters meet digits, and case is ignored: 'IFNy_4hr' is the words
ifny, 4, hr. A spelling matches a name when its words appear one after the
other among the name's words, and # matches any number: 'Slice #' matches
'Slice 3', 'slice3' and 'Slice 3 (rostral)'; '4H' matches 'IFN 4H' and
'IFNy_4h', but not '14H' or '4HR'.

The folders of a recording folder's path are read from the innermost out; the
first folder in which a label is found gives its value.

A word that is not a spelling but looks like one ('Contrl' for 'Control',
'HTE' for 'HET') is a near miss: it is shown to the user, who decides what it
means.
"""

import re
from dataclasses import dataclass, field

NUMBER = "#"
_FOLDER_WORDS = re.compile(r"[^\W\d_]+|\d+")
_SPELLING_WORDS = re.compile(r"#|[^\W\d_]+|\d+")
MIN_NEAR_MISS_LETTERS = 3


def words(name):
    """The words of a folder name, in lower case: 'IFNy_4hr' gives ['ifny', '4', 'hr']."""
    return _FOLDER_WORDS.findall(name.lower())


def spelling_words(spelling):
    """The words of a spelling, # kept as a word of its own: 'Slice #' gives ['slice', '#']."""
    return _SPELLING_WORDS.findall(spelling.lower())


def find(spelling, name_words):
    """Every place where a spelling appears in a name: (first word, number that # stands for or None)."""
    wanted = spelling_words(spelling)
    if not wanted:
        return []
    found = []
    for start in range(len(name_words) - len(wanted) + 1):
        part = name_words[start : start + len(wanted)]
        if all(w == p or (w == NUMBER and p.isdigit()) for w, p in zip(wanted, part)):
            numbers = [p for w, p in zip(wanted, part) if w == NUMBER]
            found.append((start, str(int(numbers[0])) if numbers else None))
    return found


@dataclass
class Label:
    """A label and how to recognise its values; a label without values is a number label."""

    name: str
    values: dict = field(default_factory=dict)  # value -> its spellings
    patterns: list = field(default_factory=list)  # number label: spellings with #, whose number is the value

    @property
    def is_number(self):
        return not self.values

    def spellings(self):
        """(value, spelling) pairs; the value is None for the patterns of a number label."""
        if self.is_number:
            return [(None, pattern) for pattern in self.patterns]
        return [(value, spelling) for value, spellings in self.values.items() for spelling in spellings]

    def found_in(self, name):
        """The values of this label found in one folder name, in the order they appear."""
        name_words = words(name)
        hits = []
        for value, spelling in self.spellings():
            for start, number in find(spelling, name_words):
                hits.append((start, number if value is None else value))
        return list(dict.fromkeys(value for _, value in sorted(hits) if value is not None))

    def sort_key(self, value):
        """Values in the order they are listed (number labels by number); an unknown value last."""
        if not value:
            return (2, 0, "")
        if self.is_number:
            return (0, int(value), "") if value.isdigit() else (1, 0, value)
        order = list(self.values)
        return (0, order.index(value), "") if value in order else (1, 0, value)

    def to_dict(self):
        if self.is_number:
            return {"name": self.name, "number": self.patterns}
        return {"name": self.name, "values": self.values}

    @classmethod
    def from_dict(cls, data):
        if "number" in data:
            return cls(data["name"], patterns=list(data["number"]))
        return cls(data["name"], {value: list(spellings) for value, spellings in data["values"].items()})


@dataclass
class FolderLabels:
    """The labels of one recording folder, and what to tell the user about them."""

    values: dict  # label name -> value, '' when not found
    notes: list = field(default_factory=list)


@dataclass
class NearMiss:
    """A word in folder names that looks like a spelling of a label but is not one."""

    word: str  # as written in the first folder it was seen in
    label: str
    value: str  # the value of the spelling it looks like; '' for a number label
    spelling: str  # the spelling it looks like
    suggestion: str  # the spelling to add if the word means the same: the spelling with the word in it
    folders: list = field(default_factory=list)  # the recording folders it appears in


@dataclass
class LabelSet:
    """Every label, the words the user said are not labels, and how much of each path to read."""

    labels: list = field(default_factory=list)
    ignored: list = field(default_factory=list)  # words that are never near misses
    whole_path: bool = False  # also read the folders above the recordings folder

    def names(self):
        return [label.name for label in self.labels]

    def label(self, name):
        return next((label for label in self.labels if label.name == name), None)

    def parts(self, folder_name, recordings_folder):
        """The folder names to read for a recording folder, innermost first.

        `folder_name` is its path inside the recordings folder. The recordings
        folder and the folders above it are read too with `whole_path`.
        """
        inside = [part for part in re.split(r"[\\/]+", folder_name) if part]
        above = [part for part in re.split(r"[\\/]+", str(recordings_folder)) if part] if self.whole_path else []
        return (above + inside)[::-1]

    def read(self, parts):
        """The labels of a recording folder from its folder names, innermost first."""
        values, notes = {}, []
        for label in self.labels:
            found = [(part, label.found_in(part)) for part in parts]
            found = [(part, hits) for part, hits in found if hits]
            if not found:
                values[label.name] = ""
                continue
            part, hits = found[0]
            if len(hits) > 1:
                values[label.name] = ""
                notes.append(f"{label.name}: '{part}' holds more than one value ({', '.join(hits)}), so it is left empty.")
                continue
            values[label.name] = hits[0]
            others = {hit for _, more in found[1:] for hit in more} - {hits[0]}
            if others:
                elsewhere = next(p for p, more in found[1:] if set(more) & others)
                notes.append(f"{label.name}: {hits[0]} from '{part}', but '{elsewhere}' says {', '.join(sorted(others))}.")
        return FolderLabels(values, notes)

    def near_misses(self, folders):
        """The near misses among the names of `folders`, given as {recording folder name: its parts}."""
        ignored = {word.lower() for word in self.ignored}
        known = {w for label in self.labels for _, s in label.spellings() for w in spelling_words(s)}
        found = {}
        for folder, parts in folders.items():
            for part in parts:
                covered = self._covered(part)
                for position, word in enumerate(words(part)):
                    if position in covered or word in known or word in ignored or not word.isalpha():
                        continue
                    if len(word) < MIN_NEAR_MISS_LETTERS:
                        continue
                    for miss in self._looks_like(word, part):
                        key = (word, miss.label, miss.value, miss.spelling)
                        found.setdefault(key, miss)
                        if folder not in found[key].folders:
                            found[key].folders.append(folder)
        return sorted(found.values(), key=lambda m: (self.names().index(m.label), m.word.lower()))

    def _covered(self, part):
        """Positions of the words of a folder name that are part of a matching spelling."""
        name_words = words(part)
        covered = set()
        for label in self.labels:
            for _, spelling in label.spellings():
                length = len(spelling_words(spelling))
                for start, _ in find(spelling, name_words):
                    covered.update(range(start, start + length))
        return covered

    def _looks_like(self, word, part):
        """One near miss per value the word looks like, with the spelling it is closest to."""
        written = _as_written(word, part)
        best = {}
        for label in self.labels:
            for value, spelling in label.spellings():
                for target in spelling_words(spelling):
                    if target == NUMBER or not target.isalpha() or not _close(word, target):
                        continue
                    key, distance = (label.name, value or ""), _distance(word, target)
                    if key not in best or distance < best[key][0]:
                        best[key] = (distance, NearMiss(written, label.name, value or "", spelling, _replace_word(spelling, target, written)))
        return [miss for _, miss in best.values()]

    def add_spelling(self, label_name, value, spelling):
        """Count a spelling as meaning `value` of a label (a pattern of a number label when value is '')."""
        label = self.label(label_name)
        target = label.patterns if label.is_number else label.values.setdefault(value, [])
        if spelling.lower() not in {s.lower() for s in target}:
            target.append(spelling)

    def ignore(self, word):
        if word.lower() not in {w.lower() for w in self.ignored}:
            self.ignored.append(word)

    def problems(self):
        """What is wrong with the labels, as sentences. Empty when they can be used."""
        found = []
        names = [label.name.strip() for label in self.labels]
        if any(not name for name in names):
            found.append("Every label needs a name.")
        if len({name.lower() for name in names}) < len(names):
            found.append("Two labels have the same name.")
        for label in self.labels:
            if label.is_number and not label.patterns:
                found.append(f"{label.name}: give at least one value or one spelling with #.")
            if label.is_number and any(NUMBER not in pattern for pattern in label.patterns):
                found.append(f"{label.name}: every spelling of a number label needs a # for the number.")
            for value, spellings in label.values.items():
                if not value.strip():
                    found.append(f"{label.name}: every value needs a name.")
                if not any(spelling_words(s) for s in spellings):
                    found.append(f"{label.name}: {value} needs at least one spelling.")
        return found

    def to_dict(self):
        return {"labels": [label.to_dict() for label in self.labels], "not_labels": self.ignored, "whole_path": self.whole_path}

    @classmethod
    def from_dict(cls, data):
        return cls([Label.from_dict(item) for item in data["labels"]], list(data.get("not_labels", [])), bool(data.get("whole_path", False)))


def default_labels():
    """The labels of the lab's folder names, such as 'LKI HET M5821/IFN 4HR/Slice 2'."""
    return LabelSet([
        Label("Line", {"GKI": ["GKI"], "LKI": ["LKI"]}),
        Label("Genotype", {"WT": ["WT", "wild type", "wildtype"], "HET": ["HET"]}),
        Label("Treatment", {"CTRL": ["CTRL", "CNTRL", "control"], "IFN": ["IFN", "IFNy", "IFNg", "IFNγ"]}),
        Label("Duration", {"2H": ["2H", "2HR", "2HRS", "2 hours"], "4H": ["4H", "4HR", "4HRS", "4 hours"]}),
        Label("Sex", {"F": ["F#", "female", "females"], "M": ["M#", "male", "males"]}),
        Label("Animal", patterns=["F#", "M#"]),
        Label("Slice", patterns=["Slice #"]),
    ])


def _close(word, target):
    """True if a word looks like a misspelling of a target word.

    It does when one or two letters are off ('HTE', 'Slcie'), when one starts
    the other ('IFNy' and 'IFN'), or when one is a short form of the other: it
    starts with the same letter and has the rest of its letters in the same
    order ('CNTRL' and 'control'), and is at least half as long.
    """
    if word == target or len(target) < MIN_NEAR_MISS_LETTERS:
        return False
    if word.startswith(target) or target.startswith(word):
        return True
    short, long = sorted((word, target), key=len)
    if short[0] == long[0] and len(long) <= 2 * len(short) + 1 and _in_order(short, long):
        return True
    return _distance(word, target) <= (1 if len(target) <= 5 else 2)


def _in_order(short, long):
    """True if the letters of `short` appear in `long` in the same order."""
    rest = iter(long)
    return all(letter in rest for letter in short)


def _distance(a, b):
    """Edits (insert, delete, replace, swap two neighbours) that turn one word into the other."""
    rows = [list(range(len(b) + 1))]
    for i in range(1, len(a) + 1):
        row = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            row[j] = min(rows[-1][j] + 1, row[j - 1] + 1, rows[-1][j - 1] + (a[i - 1] != b[j - 1]))
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                row[j] = min(row[j], rows[-2][j - 2] + 1)
        rows.append(row)
    return rows[-1][-1]


def _as_written(word, part):
    match = re.search(re.escape(word), part, re.IGNORECASE)
    return match.group() if match else word


def _replace_word(spelling, target, word):
    """The spelling with one of its words replaced: ('Slice #', 'slice', 'Slcie') gives 'Slcie #'."""
    if spelling_words(spelling) == [target]:
        return word
    return re.sub(re.escape(target), word.replace("\\", r"\\"), spelling, count=1, flags=re.IGNORECASE)
