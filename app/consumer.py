from __future__ import annotations

import io
import logging
import threading
import time
from dataclasses import dataclass
from queue import Queue, Empty
import shutil
import subprocess
import signal
import os

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
        """
        Play WAV bytes using available system audio players.

        Preference order (first found in PATH):
        - ffplay (ffmpeg) - uses -nodisp -autoexit -loglevel error
        - aplay (ALSA)
        - paplay (PulseAudio)
        - play (SoX)
        - mpv
        """
        try:
            # Write to a temporary file and invoke a CLI player.
            import tempfile
            import os

            with tempfile.NamedTemporaryFile(prefix="sleeping_assistant_", suffix=".wav", delete=False) as tmp:
                tmp.write(wav_bytes)
                tmp_path = tmp.name

            try:
                candidates: list[tuple[str, list[str]]] = []

                ffplay = shutil.which("ffplay")
                if ffplay:
                    candidates.append(("ffplay", [ffplay, "-nodisp", "-autoexit", "-loglevel", "error", tmp_path]))

                aplay = shutil.which("aplay")
                if aplay:
                    candidates.append(("aplay", [aplay, tmp_path]))

                paplay = shutil.which("paplay")
                if paplay:
                    candidates.append(("paplay", [paplay, tmp_path]))

                play = shutil.which("play")
                if play:
                    candidates.append(("play", [play, tmp_path]))

                mpv = shutil.which("mpv")
                if mpv:
                    candidates.append(("mpv", [mpv, "--no-video", "--really-quiet", tmp_path]))

                if not candidates:
                    raise RuntimeError("No audio playback utility found (ffplay/aplay/paplay/play/mpv)")

                last_exc: Exception | None = None
                for name, cmd in candidates:
                    try:
                        # Start player in its own process group so we can terminate reliably
                        proc = subprocess.Popen(cmd, start_new_session=True)
                        # Poll for completion while honoring stop_event cancellation
                        while True:
                            if self._stop_event.is_set():
                                try:
                                    os.killpg(proc.pid, signal.SIGTERM)
                                except Exception:  # noqa: BLE001
                                    pass
                                # Give it a brief moment to exit gracefully
                                try:
                                    proc.wait(timeout=1.0)
                                except Exception:  # noqa: BLE001
                                    try:
                                        os.killpg(proc.pid, signal.SIGKILL)
                                    except Exception:  # noqa: BLE001
                                        pass
                                break

                            ret = proc.poll()
                            if ret is not None:
                                if ret != 0:
                                    raise subprocess.CalledProcessError(ret, cmd)
                                last_exc = None
                                break
                            time.sleep(0.05)

                        if self._stop_event.is_set():
                            # If we cancelled, stop trying further players
                            last_exc = None
                            break
                        # Playback succeeded
                        break
                    except Exception as exc:  # noqa: BLE001
                        last_exc = exc
                        logger.warning("Audio player '%s' failed, trying next...", name)

                if last_exc:
                    raise last_exc
            finally:
                try:
                    os.remove(tmp_path)
                except Exception:  # noqa: BLE001
                    logger.warning("Failed to remove temporary audio file: %s", tmp_path)
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
                if self._stop_event.is_set():
                    break
                wav_bytes = self._tts.synthesize(text)
                if self._stop_event.is_set():
                    break
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
