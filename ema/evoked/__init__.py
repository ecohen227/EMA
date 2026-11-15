"""Evoked responses: protocols (what to measure) and the measuring itself.

The Evoked Analysis Configurator writes protocols; the Evoked Analysis will
read them. To read one in a script::

    from ema.evoked import Protocol, measure

    protocol = Protocol.load("protocols/My protocol.json")
    for item in protocol.measures():
        print(item.name, item.unit, item.explanation)
"""

from .measures import Measurement, measure, summarise
from .protocol import Protocol, ProtocolError

__all__ = ["Measurement", "Protocol", "ProtocolError", "measure", "summarise"]
