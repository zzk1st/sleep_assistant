from __future__ import annotations

import logging
import signal
import sys
import threading
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

    def handle_signal(signum, frame):  # noqa: ANN001
        logger.info("Received signal %s; stopping...", signum)
        stop_event.set()
        wake_producer_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Prime the system by waking producer so initial content is generated
    wake_producer_event.set()

    producer.start()
    consumer.start()

    try:
        # Wait for threads to stop
        while producer.is_alive() or consumer.is_alive():
            producer.join(timeout=0.5)
            consumer.join(timeout=0.5)
    finally:
        stop_event.set()
        wake_producer_event.set()

    logger.info("Shutdown complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
