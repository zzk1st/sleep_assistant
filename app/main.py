from __future__ import annotations

import logging
import signal
import sys
import threading
import time
from queue import Queue

from .config import load_config
from .producer import ProducerThread, ProducerConfig
from .consumer import ConsumerThread, ConsumerConfig
from .tts_elevenlabs import ElevenLabsTTS, ElevenLabsConfig


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(threadName)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> int:
    cfg = load_config()

    text_queue: Queue[str] = Queue(maxsize=cfg.queue_maxsize)

    stop_event = threading.Event()
    wake_producer_event = threading.Event()

    tts = ElevenLabsTTS(
        ElevenLabsConfig(
            api_key=cfg.elevenlabs_api_key,
            voice_id=cfg.elevenlabs_voice_id,
            model_id=cfg.elevenlabs_model_id,
        )
    )

    producer = ProducerThread(
        queue=text_queue,
        wake_event=wake_producer_event,
        stop_event=stop_event,
        config=ProducerConfig(batch_produce_count=cfg.batch_produce_count),
        name="Producer",
    )

    consumer = ConsumerThread(
        queue=text_queue,
        wake_producer_event=wake_producer_event,
        stop_event=stop_event,
        tts=tts,
        config=ConsumerConfig(low_watermark=cfg.low_watermark),
        name="Consumer",
    )

    force_exit_event = threading.Event()
    first_signal_received = False

    def handle_signal(signum, frame):  # noqa: ANN001
        nonlocal first_signal_received
        logger.info("Received signal %s; stopping...", signum)
        if not first_signal_received:
            first_signal_received = True
            stop_event.set()
            wake_producer_event.set()
        else:
            logger.warning("Second signal received; forcing exit now")
            force_exit_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Prime the system by waking producer so initial content is generated
    wake_producer_event.set()

    producer.start()
    consumer.start()

    graceful_shutdown_started_at: float | None = None

    try:
        # Wait for threads to stop, but honor force-exit and a grace timeout
        while (producer.is_alive() or consumer.is_alive()) and not force_exit_event.is_set():
            producer.join(timeout=0.25)
            consumer.join(timeout=0.25)

            if stop_event.is_set() and graceful_shutdown_started_at is None:
                graceful_shutdown_started_at = time.time()

            if graceful_shutdown_started_at is not None:
                elapsed = time.time() - graceful_shutdown_started_at
                if elapsed > 5.0:
                    logger.warning("Graceful shutdown timed out; forcing exit")
                    break
    finally:
        stop_event.set()
        wake_producer_event.set()

    if force_exit_event.is_set():
        logger.info("Forced exit requested; exiting immediately")
        return 130  # 128 + SIGINT

    logger.info("Shutdown complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
