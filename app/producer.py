from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from queue import Queue
from typing import Optional

import google.generativeai as genai


logger = logging.getLogger(__name__)


@dataclass
class ProducerConfig:
    batch_produce_count: int = 1


class ProducerThread(threading.Thread):
    def __init__(
        self,
        queue: Queue[str],
        wake_event: threading.Event,
        stop_event: threading.Event,
        config: ProducerConfig,
        *,
        name: str = "ProducerThread",
        daemon: bool = True,
    ) -> None:
        super().__init__(name=name, daemon=daemon)
        self._queue = queue
        self._wake_event = wake_event
        self._stop_event = stop_event
        self._config = config

        self._gemini_model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self._gemini_api_key = os.getenv("GEMINI_API_KEY")
        self._model: Optional[genai.GenerativeModel] = None
        if self._gemini_api_key:
            try:
                genai.configure(api_key=self._gemini_api_key)
                self._model = genai.GenerativeModel(self._gemini_model_name)
            except Exception:  # noqa: BLE001
                logger.exception("Failed to initialize Gemini model; will use fallback text")
                self._model = None
        else:
            logger.warning("GEMINI_API_KEY is not set; using fallback text generator")

    def _generate_sleep_paragraphs_text(self) -> list[str]:
        if not self._model:
            paragraphs = [
                (
                    "Close your eyes and let your breath slow down. Feel the weight of the day "
                    "melting away from your shoulders. With each gentle inhale, invite calm; "
                    "with each soft exhale, release any lingering tension. Imagine a quiet, safe "
                    "place where the air is warm and the light is soft. Your thoughts can drift "
                    "like clouds, unhurried and light, passing without needing attention. You are "
                    "safe, you are cared for, and you can rest."
                ),
                (
                    "Let your breathing become soft and steady. With every exhale, imagine "
                    "tension dissolving like mist. You are supported and at ease; the night "
                    "is gentle around you. Thoughts can pass like distant waves, fading as they "
                    "reach the shore."
                ),
                (
                    "Feel the surface beneath you holding your body with quiet kindness. "
                    "There is nothing you need to do now. Allow comfort to spread through "
                    "your chest, your shoulders, your jaw. You are safe, you are warm, and it "
                    "is time to rest."
                ),
            ]
            return paragraphs

        prompt = (
            "You are crafting exactly three short, soothing paragraphs to help someone fall asleep. "
            "Write in a calm, gentle tone, focusing on breath, comfort, and safety. "
            "Avoid instructions that require movement; keep it simple, reassuring, and warm. "
            "Each paragraph must be 50 words or fewer. Output exactly three paragraphs, separated by a blank line, with no titles or numbering."
        )

        try:
            resp = self._model.generate_content(prompt)
            text = (resp.text or "").strip()
        except Exception:  # noqa: BLE001
            logger.exception("Gemini generation failed; using fallback text")
            text = (
                "Let your breathing become soft and steady. With every exhale, imagine "
                "tension dissolving like mist. You are safe and supported; the night holds you "
                "gently. Allow your thoughts to float by without chasing them. It is okay to rest now.\n\n"
                "Close your eyes and picture a quiet, warm light around you. Each breath brings "
                "ease; each exhale carries away the day. Your body can settle, your mind can drift, "
                "comfortably and unhurried.\n\n"
                "Feel the calm spreading from your chest to your shoulders and down your arms. "
                "There is nothing to fix, nothing to solve. You are safe, and you can rest."
            )

        if not text:
            text = (
                "Breathe slowly and let your body settle. You are safe and cared for. "
                "Allow your thoughts to drift away as you sink into rest.\n\n"
                "In this gentle quiet, comfort surrounds you like a soft blanket. "
                "Your breath moves in a calm rhythm.\n\n"
                "Let the night hold you with ease; it is time to rest."
            )

        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

        # Ensure exactly three paragraphs; truncate or pad with simple fallbacks
        if len(paragraphs) < 3:
            fallback = [
                "Let your breathing be soft and easy. You are safe and can rest.",
                "Comfort gathers around you; the night is gentle and calm.",
                "Thoughts can drift by; it is okay to let go and sleep.",
            ]
            paragraphs.extend(fallback[: 3 - len(paragraphs)])
        elif len(paragraphs) > 3:
            paragraphs = paragraphs[:3]

        # Enforce <= 200 words per paragraph
        trimmed: list[str] = []
        for p in paragraphs:
            words = p.split()
            if len(words) > 200:
                p = " ".join(words[:200]).rstrip()
                if not p.endswith((".", "!", "?")):
                    p += "."
            trimmed.append(p)

        return trimmed

    def run(self) -> None:  # noqa: D401
        while not self._stop_event.is_set():
            signaled = self._wake_event.wait(timeout=1)
            if self._stop_event.is_set():
                break
            if not signaled:
                continue

            self._wake_event.clear()

            for _ in range(self._config.batch_produce_count):
                if self._stop_event.is_set():
                    break
                try:
                    logger.info("Generating sleep paragraphs")
                    paragraphs = self._generate_sleep_paragraphs_text()
                    logger.info(f"Produced {len(paragraphs)} paragraphs")
                    for paragraph in paragraphs:
                        logger.info(f"Enqueuing paragraph: {paragraph}")
                        self._queue.put(paragraph, timeout=0.5)
                except Exception:  # noqa: BLE001
                    logger.exception("Producer failed to enqueue paragraph")

            time.sleep(0.05)

        logger.info("Producer stopping.")
