from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

from elevenlabs.client import ElevenLabs


logger = logging.getLogger(__name__)


@dataclass
class ElevenLabsConfig:
    api_key: str
    voice_id: str
    model_id: str = "eleven_turbo_v2"


class ElevenLabsTTS:
    def __init__(self, config: ElevenLabsConfig, timeout_seconds: float = 15.0):
        self._config = config
        self._timeout_seconds = timeout_seconds
        self._client = ElevenLabs(api_key=config.api_key)

    def synthesize(self, text: str, max_retries: int = 2, retry_backoff_seconds: float = 1.0) -> bytes:
        if not text:
            raise ValueError("text must be non-empty")

        last_exc: Optional[Exception] = None
        for attempt in range(1, max_retries + 1):
            try:
                audio = self._client.text_to_speech.convert(
                    text=text,
                    voice_id=self._config.voice_id,
                    model_id=self._config.model_id,
                    output_format="mp3_44100_128",
                )
                return b''.join(audio)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.exception("ElevenLabs TTS request failed on attempt %d", attempt)

            if attempt < max_retries:
                time.sleep(retry_backoff_seconds)

        if last_exc:
            raise last_exc
        raise RuntimeError("Failed to synthesize speech after retries")
