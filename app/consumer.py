from __future__ import annotations

import asyncio
import io
import logging
import threading
import time
from dataclasses import dataclass
from typing import Optional
from queue import Queue, Empty
import shutil
import subprocess
import signal
import os

from .tts_elevenlabs import ElevenLabsTTS, ElevenLabsConfig
from .bgm import BackgroundMusicManager
from elevenlabs.play import play


logger = logging.getLogger(__name__)


@dataclass
class ConsumerConfig:
    low_watermark: int = 1


class ConsumerThread(threading.Thread):
    def __init__(
        self,
        queue: Queue[str],
        wake_producer_event: threading.Event,
        stop_event: threading.Event,
        tts: ElevenLabsTTS,
        config: ConsumerConfig,
        bgm: Optional[BackgroundMusicManager] = None,
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
        self._bgm = bgm

    def run(self) -> None:  # noqa: D401
        while not self._stop_event.is_set():
            try:
                text = self._queue.get(timeout=0.2)
            except Empty:
                # If queue is empty, signal producer and keep waiting until queue is filled
                if self._queue.qsize() <= self._config.low_watermark:
                    self._wake_producer_event.set()
                    # Keep waiting until queue has items or stop event is set
                    while not self._stop_event.is_set() and self._queue.qsize() <= self._config.low_watermark:
                        logger.info(f"Queue is below low-watermark; waiting for items... {self._queue.qsize()}")
                        time.sleep(1)
                continue

            try:
                if self._stop_event.is_set():
                    break
                logger.info(f"Synthesizing audio for text: {text}")
                audio = self._tts.synthesize(text)
                logger.info(f"Synthesized audio for text: {audio}")
                if self._stop_event.is_set():
                    break
                logger.info(f"Playing audio for text: {text}")
                try:
                    if self._bgm:
                        self._bgm.duck()
                    play(audio)
                finally:
                    if self._bgm:
                        self._bgm.unduck()
                logger.info(f"Played audio for text: {text}")
            except Exception:  # noqa: BLE001
                logger.exception("Failed to synthesize or play audio; item will be dropped")
            finally:
                # Mark item as done regardless of success to prevent deadlocks
                self._queue.task_done()

            # Small sleep to be gentle on CPU
            time.sleep(0.01)

        logger.info("Consumer stopping.")
