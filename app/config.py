from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv


@dataclass(frozen=True)
class AppConfig:
    elevenlabs_api_key: str
    elevenlabs_voice_id: str
    elevenlabs_model_id: str = "eleven_turbo_v2"

    queue_maxsize: int = 50
    low_watermark: int = 1
    batch_produce_count: int = 1

    # Background music settings
    bgm_path: Optional[str] = "background_music.mp3"
    bgm_initial_volume: float = 2.0
    bgm_ducked_volume: float = 0.1
    bgm_fade_seconds: float = 1.0


def load_config(env_file: Optional[str] = None) -> AppConfig:
    if env_file:
        load_dotenv(env_file)
    else:
        load_dotenv()

    api_key = os.getenv("ELEVENLABS_API_KEY")
    voice_id = "qWdiyiWdNPlPyVCOLW0h"
    model_id = os.getenv("ELEVENLABS_MODEL_ID", "eleven_v3")

    if not api_key:
        raise RuntimeError(
            "ELEVENLABS_API_KEY is required. Set it in your environment or .env file."
        )
    if not voice_id:
        raise RuntimeError(
            "ELEVENLABS_VOICE_ID is required. Set it in your environment or .env file."
        )

    queue_maxsize_str = os.getenv("QUEUE_MAXSIZE", "50")
    low_watermark_str = os.getenv("LOW_WATERMARK", "1")
    batch_count_str = os.getenv("BATCH_PRODUCE_COUNT", "1")

    try:
        queue_maxsize = int(queue_maxsize_str)
        low_watermark = int(low_watermark_str)
        batch_produce_count = int(batch_count_str)
    except ValueError as exc:
        raise RuntimeError(
            "QUEUE_MAXSIZE, LOW_WATERMARK, and BATCH_PRODUCE_COUNT must be integers"
        ) from exc

    # Background music envs (optional)
    bgm_path = os.getenv("BGM_PATH", "background_music.wav")  # can be None; user will provide later
    def _parse_float(name: str, default: float) -> float:
        v = os.getenv(name)
        if v is None:
            return default
        try:
            f = float(v)
        except ValueError as exc:
            raise RuntimeError(f"{name} must be a float") from exc
        return max(0.0, min(1.0, f)) if name != "BGM_FADE_SECONDS" else max(0.0, f)

    bgm_initial_volume = _parse_float("BGM_INITIAL_VOLUME", 2.0)
    bgm_ducked_volume = _parse_float("BGM_DUCKED_VOLUME", 0.1)
    bgm_fade_seconds = _parse_float("BGM_FADE_SECONDS", 1.0)

    return AppConfig(
        elevenlabs_api_key=api_key,
        elevenlabs_voice_id=voice_id,
        elevenlabs_model_id=model_id,
        queue_maxsize=queue_maxsize,
        low_watermark=low_watermark,
        batch_produce_count=batch_produce_count,
        bgm_path=bgm_path,
        bgm_initial_volume=bgm_initial_volume,
        bgm_ducked_volume=bgm_ducked_volume,
        bgm_fade_seconds=bgm_fade_seconds,
    )
