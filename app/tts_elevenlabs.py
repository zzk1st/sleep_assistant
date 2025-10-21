from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Dict, Optional

import requests


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
        self._base_url = "https://api.elevenlabs.io/v1"

    def synthesize(self, text: str, max_retries: int = 2, retry_backoff_seconds: float = 1.0) -> bytes:
        if not text:
            raise ValueError("text must be non-empty")

        endpoint = f"{self._base_url}/text-to-speech/{self._config.voice_id}"
        headers: Dict[str, str] = {
            "xi-api-key": self._config.api_key,
            "accept": "audio/wav",
            "content-type": "application/json",
        }
        payload: Dict[str, object] = {
            "text": text,
            "model_id": self._config.model_id,
            # voice_settings and other options can be added later
        }

        last_exc: Optional[Exception] = None
        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                    timeout=self._timeout_seconds,
                )
                if resp.status_code == 200 and resp.content:
                    return resp.content
                logger.warning(
                    "ElevenLabs TTS non-200 response: %s %s", resp.status_code, resp.text[:200]
                )
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.exception("ElevenLabs TTS request failed on attempt %d", attempt)

            if attempt < max_retries:
                time.sleep(retry_backoff_seconds)

        if last_exc:
            raise last_exc
        raise RuntimeError("Failed to synthesize speech after retries")
