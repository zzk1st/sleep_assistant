from __future__ import annotations

import logging
import threading
import time
from typing import Optional

try:
    import pygame
    from pygame import mixer
except Exception:  # noqa: BLE001
    pygame = None  # type: ignore[assignment]
    mixer = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)


class BackgroundMusicManager:
    def __init__(
        self,
        music_path: Optional[str],
        *,
        initial_volume: float = 0.4,
        ducked_volume: float = 0.1,
        fade_seconds: float = 1.0,
    ) -> None:
        logger.info(f"Initializing background music manager with path: {music_path}")
        self._music_path = music_path
        self._initial_volume = max(0.0, min(1.0, initial_volume))
        self._ducked_volume = max(0.0, min(1.0, ducked_volume))
        self._fade_seconds = max(0.0, fade_seconds)

        self._lock = threading.RLock()
        self._running = False
        self._ready = False

    def _ensure_init(self) -> None:
        if self._ready:
            return
        if not self._music_path:
            logger.warning("No background music path provided; background music disabled")
            return
        if pygame is None or mixer is None:
            logger.warning("pygame not available; background music disabled")
            return
        try:
            if not mixer.get_init():
                mixer.init()
            # Try normal load first
            try:
                mixer.music.load(self._music_path)
            except Exception:
                # Retry with name hint for MP3 in case decoder needs a hint
                try:
                    mixer.music.load(self._music_path, namehint="mp3")
                except Exception:
                    # If mp3 fails, try same basename with .wav or .ogg if available
                    import os
                    base, _ = os.path.splitext(self._music_path)
                    fallback_paths = [f"{base}.wav", f"{base}.ogg"]
                    loaded = False
                    for p in fallback_paths:
                        if os.path.exists(p):
                            try:
                                mixer.music.load(p)
                                self._music_path = p
                                loaded = True
                                logger.info("Background music fell back to: %s", p)
                                break
                            except Exception:
                                continue
                    if not loaded:
                        raise
            mixer.music.set_volume(self._initial_volume)
            self._ready = True
            logger.info("Background music initialized: %s", self._music_path)
        except Exception:  # noqa: BLE001
            logger.exception(
                "Failed to initialize background music; disabled. "
                "If you're using MP3, try converting it to 44.1kHz 16-bit stereo WAV or OGG."
            )
            self._ready = False

    def start(self) -> None:
        with self._lock:
            self._ensure_init()
            if not self._ready or self._running:
                return
            try:
                mixer.music.play(-1)  # loop forever
                self._running = True
                logger.info("Background music started")
            except Exception:  # noqa: BLE001
                logger.exception("Failed to start background music")

    def stop(self) -> None:
        with self._lock:
            if not self._ready:
                return
            try:
                mixer.music.fadeout(int(self._fade_seconds * 1000))
            except Exception:  # noqa: BLE001
                logger.exception("Failed to fadeout background music")
            finally:
                try:
                    mixer.music.stop()
                except Exception:  # noqa: BLE001
                    pass
                self._running = False

    def _tween_volume(self, start: float, end: float, duration: float) -> None:
        if not self._ready:
            return
        steps = max(1, int(duration * 30))  # ~30 FPS
        dv = (end - start) / steps
        v = start
        for _ in range(steps):
            v = max(0.0, min(1.0, v + dv))
            try:
                mixer.music.set_volume(v)
            except Exception:  # noqa: BLE001
                break
            time.sleep(duration / steps if steps > 0 else 0)
        try:
            mixer.music.set_volume(end)
        except Exception:  # noqa: BLE001
            pass

    def duck(self) -> None:
        with self._lock:
            if not self._ready or not self._running:
                return
            try:
                current = mixer.music.get_volume()
            except Exception:  # noqa: BLE001
                current = self._initial_volume
            self._tween_volume(current, self._ducked_volume, self._fade_seconds)

    def unduck(self) -> None:
        with self._lock:
            if not self._ready or not self._running:
                return
            try:
                current = mixer.music.get_volume()
            except Exception:  # noqa: BLE001
                current = self._ducked_volume
            self._tween_volume(current, self._initial_volume, self._fade_seconds)


