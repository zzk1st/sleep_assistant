from __future__ import annotations

import io
import logging
import threading
import time
from dataclasses import dataclass
from queue import Queue, Empty

import simpleaudio as sa

from .tts_elevenlabs import ElevenLabsTTS, ElevenLabsConfig


logger = logging.getLogger(__name__)


@dataclass
class ConsumerConfig:
    low_watermark: int = 3


class ConsumerThread(threading.Thread):
    def __init__(
        self,
        queue: Queue[str],
        wake_producer_event: threading.Event,
        stop_event: threading.Event,
        tts: ElevenLabsTTS,
        config: ConsumerConfig,
        *,
        name: str = "ConsumerThread",
        daemon: bool = True,
    ) -> None:
        super().__init__(name=name, daemon=daemon)
        self._queue = queue
        self._wake_producer_event = wake_producer_event
        self._stop_event = stop_event
        self._tts = tts
        self._config = config

    def _play_wav_bytes(self, wav_bytes: bytes) -> None:
        try:
            # simpleaudio expects raw PCM or WAV file data; it can handle WAV directly.
            # Use sa.WaveObject.from_wave_file requires a file path, so we load from bytes via BytesIO -> wave module
            # Instead, simpleaudio has from_wave_file only; we will use wave + from_wave_read
            import wave

            with wave.open(io.BytesIO(wav_bytes), "rb") as wave_read:
                wave_obj = sa.WaveObject.from_wave_read(wave_read)
                play_obj = wave_obj.play()
                play_obj.wait_done()  # Block until playback is finished
        except Exception:  # noqa: BLE001
            logger.exception("Audio playback failed")
            raise

    def run(self) -> None:  # noqa: D401
        while not self._stop_event.is_set():
            try:
                text = self._queue.get(timeout=0.2)
            except Empty:
                # If queue is empty, consider signaling producer to avoid starvation
                if self._queue.qsize() <= self._config.low_watermark:
                    self._wake_producer_event.set()
                continue

            try:
                wav_bytes = self._tts.synthesize(text)
                self._play_wav_bytes(wav_bytes)
            except Exception:  # noqa: BLE001
                logger.exception("Failed to synthesize or play audio; item will be dropped")
            finally:
                # Mark item as done regardless of success to prevent deadlocks
                self._queue.task_done()

            # After consumption, if the queue is at/below low-watermark, wake producer
            if self._queue.qsize() <= self._config.low_watermark:
                self._wake_producer_event.set()

            # Small sleep to be gentle on CPU
            time.sleep(0.01)

        logger.info("Consumer stopping.")
