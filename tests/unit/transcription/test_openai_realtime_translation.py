from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import AsyncIterator

from vox_voice_paste.config import REALTIME_TRANSLATION_MODEL
from vox_voice_paste.transcription import OPENAI_SAMPLE_RATE, TranscriptionConfig
from vox_voice_paste.transcription.openai_realtime_translation import (
    OpenAITranslationEventParser,
    build_translation_session_update,
    safe_translation_error_context,
    send_translation_audio,
    translation_websocket_url,
)


def test_translation_websocket_url_uses_translation_endpoint_model() -> None:
    config = TranscriptionConfig(
        api_key="sk-test",
        model=REALTIME_TRANSLATION_MODEL,
        websocket_base_url="wss://api.openai.com/v1/realtime/translations",
    )

    assert (
        translation_websocket_url(config)
        == "wss://api.openai.com/v1/realtime/translations?model=gpt-realtime-translate"
    )


def test_build_translation_session_update_sets_output_language() -> None:
    payload = build_translation_session_update(
        TranscriptionConfig(
            api_key="sk-test",
            translation_target_language="fr",
            sample_rate=OPENAI_SAMPLE_RATE,
        )
    )

    assert payload == {
        "type": "session.update",
        "session": {
            "audio": {
                "output": {
                    "language": "fr",
                },
            },
        },
    }


def test_openai_translation_safe_error_context_excludes_api_key() -> None:
    context = safe_translation_error_context(
        TranscriptionConfig(
            api_key="sk-test-secret",
            model=REALTIME_TRANSLATION_MODEL,
            translation_target_language="en",
            websocket_base_url="wss://api.openai.com/v1/realtime/translations",
        ),
        stage="websocket",
    )

    raw_context = json.dumps(context)
    assert context["provider"] == "openai"
    assert context["mode"] == "translation"
    assert context["translation_target_language"] == "en"
    assert "sk-test-secret" not in raw_context


def test_openai_translation_parser_emits_partial_and_final() -> None:
    parser = OpenAITranslationEventParser()

    partial = parser.parse(
        {
            "type": "session.output_transcript.delta",
            "delta": "Hello",
        }
    )
    final = parser.parse({"type": "session.closed"})

    assert partial is not None
    assert partial.text == "Hello"
    assert final is not None
    assert final.text == "Hello"


def test_send_translation_audio_appends_base64_and_closes() -> None:
    async def chunks() -> AsyncIterator[bytes]:
        yield b"abc"
        yield b""

    async def run() -> list[str]:
        websocket = FakeWebSocket()
        await send_translation_audio(websocket, chunks())
        return websocket.sent

    sent = asyncio.run(run())

    assert json.loads(sent[0]) == {
        "type": "session.input_audio_buffer.append",
        "audio": base64.b64encode(b"abc").decode("ascii"),
    }
    assert json.loads(sent[1]) == {"type": "session.close"}


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, payload: str) -> None:
        self.sent.append(payload)
