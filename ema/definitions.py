"""How settings and measures are declared, once, for the windows, the files and the documentation.

A settings class (RoiSettings, SpatialSettings, DetectorSettings) is a
dataclass whose fields are made with `setting`: each carries its label, help
text, kind and unit, and the forms and the documentation tables are built from
them. A measure catalogue (ema.evoked.catalogue, ema.spontaneous.catalogue) is
a list of `Measure`.
"""

from dataclasses import asdict, dataclass, field, fields

KINDS = ("int", "float", "bool", "frames", "names", "choice")


def setting(default, group, label, help, kind, unit="", advanced=False, **options):
    """One setting: its default, the section it is shown in, its label and help, and its kind.

    `kind` picks its input: int or float (give `minimum`, `maximum` and, for
    float, `step`), bool, frames (a [first, last) window of frames), names
    (words separated by commas) or choice (one of `choices`). An `advanced`
    setting is shown under Advanced in the configurators.
    """
    if kind not in KINDS:
        raise ValueError(f"Unknown kind of setting: {kind}")
    if kind in ("int", "float") and not {"minimum", "maximum"} <= set(options):
        raise ValueError(f"The setting {label} needs a minimum and a maximum.")
    details = dict(group=group, label=label, help=help, kind=kind, unit=unit, advanced=advanced, **options)
    if isinstance(default, list):
        return field(default_factory=lambda: list(default), metadata=details)
    return field(default=default, metadata=details)


class Settings:
    """What every settings dataclass can do: be saved in a file and read back."""

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, values):
        """Settings from a saved file. Names this EMA does not know are ignored; missing ones take their default.

        Raises ValueError when a value is not of its setting's kind.
        """
        if not isinstance(values, dict):
            raise ValueError("The settings are damaged.")
        found = {}
        for f in fields(cls):
            if f.name in values:
                found[f.name] = _of_kind(values[f.name], f.metadata, f.name)
        return cls(**found)

    @classmethod
    def labels(cls):
        """{field name: label} of every setting."""
        return {f.name: f.metadata["label"] for f in fields(cls)}


def _of_kind(value, details, name):
    kind = details["kind"]
    try:
        if kind == "bool" and isinstance(value, bool):
            return value
        if kind == "int" and not isinstance(value, bool):
            return int(value)
        if kind == "float" and not isinstance(value, bool):
            return float(value)
        if kind == "frames":
            first, last = value
            return [int(first), int(last)]
        if kind == "names" and isinstance(value, list):
            return [str(word) for word in value]
        if kind == "choice" and value in details["choices"]:
            return value
    except (TypeError, ValueError):
        pass
    raise ValueError(f"The setting '{details['label']}' ({name}) has a value of the wrong kind: {value!r}.")


@dataclass(frozen=True)
class Measure:
    """One measure of a catalogue: its key (also its name in the tables), unit, group and one-line definition."""

    key: str
    unit: str
    group: str
    explanation: str
