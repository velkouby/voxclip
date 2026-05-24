from __future__ import annotations

from collections import OrderedDict

from .base import TranscriptionEvent, TranscriptionEventType


class TranscriptBuffer:
    def __init__(self) -> None:
        self._partials: OrderedDict[str, str] = OrderedDict()
        self._finals: OrderedDict[str, str] = OrderedDict()

    def apply(self, event: TranscriptionEvent) -> str:
        item_id = event.item_id or "_default"

        if event.type is TranscriptionEventType.PARTIAL:
            self._partials[item_id] = self._partials.get(item_id, "") + event.text
        elif event.type is TranscriptionEventType.FINAL:
            self._partials.pop(item_id, None)
            self._finals[item_id] = event.text

        return self.text

    @property
    def text(self) -> str:
        parts = [*self._finals.values(), *self._partials.values()]
        return normalize_transcript(" ".join(part for part in parts if part))

    @property
    def final_text(self) -> str:
        return normalize_transcript(" ".join(part for part in self._finals.values() if part))


def normalize_transcript(text: str) -> str:
    return " ".join(text.split())
