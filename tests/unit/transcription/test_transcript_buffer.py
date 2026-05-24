from __future__ import annotations

from vox_voice_paste.transcription import TranscriptBuffer, TranscriptionEvent


def test_transcript_buffer_accumulates_partial_and_final_text() -> None:
    buffer = TranscriptBuffer()

    assert buffer.apply(TranscriptionEvent.partial("Bonjour ", item_id="a")) == "Bonjour"
    assert buffer.apply(TranscriptionEvent.partial("Vincent", item_id="a")) == "Bonjour Vincent"
    assert buffer.apply(TranscriptionEvent.final("Bonjour Vincent.", item_id="a")) == (
        "Bonjour Vincent."
    )

    assert buffer.final_text == "Bonjour Vincent."


def test_transcript_buffer_normalizes_spacing() -> None:
    buffer = TranscriptBuffer()

    buffer.apply(TranscriptionEvent.final("  Bonjour   le monde  "))

    assert buffer.final_text == "Bonjour le monde"
