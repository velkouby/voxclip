from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import pytest
import websockets

from vox_voice_paste.transcription import TranscriptionConfig
from vox_voice_paste.transcription.openai_realtime import (
    build_session_update,
    websocket_url,
)

ROOT = Path(__file__).resolve().parents[2]


def test_openai_realtime_transcription_session_handshake() -> None:
    if os.getenv("RUN_OPENAI_INTEGRATION") != "1":
        pytest.skip("Set RUN_OPENAI_INTEGRATION=1 to run live OpenAI integration tests.")

    api_key = _load_openai_api_key()
    if not api_key:
        pytest.skip("OPENAI_API_KEY is missing from environment or .env.")

    event = asyncio.run(_connect_and_update_session(api_key))

    assert event["type"] == "session.updated"


async def _connect_and_update_session(api_key: str) -> dict[str, Any]:
    config = TranscriptionConfig(api_key=api_key)

    async with websockets.connect(
        websocket_url(config),
        additional_headers={"Authorization": f"Bearer {api_key}"},
        open_timeout=config.connect_timeout_seconds,
    ) as websocket:
        await websocket.send(json.dumps(build_session_update(config)))

        for _ in range(5):
            raw_event = await asyncio.wait_for(
                websocket.recv(),
                timeout=config.final_timeout_seconds,
            )
            event = json.loads(raw_event)
            event_type = event.get("type")
            if event_type == "error":
                error = event.get("error") or {}
                message = error.get("message") if isinstance(error, dict) else None
                pytest.fail(str(message or "OpenAI realtime session returned an error."))
            if event_type == "session.updated":
                return event

    pytest.fail("OpenAI realtime session did not accept the session update.")


def _load_openai_api_key() -> str | None:
    env_value = os.getenv("OPENAI_API_KEY")
    if env_value:
        return env_value.strip()

    env_file = ROOT / ".env"
    if not env_file.exists():
        return None

    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key.strip() != "OPENAI_API_KEY":
            continue
        return value.strip().strip("\"'")

    return None
