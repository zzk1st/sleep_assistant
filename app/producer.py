from __future__ import annotations

import logging
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from queue import Queue
from typing import Optional
import random

import google.generativeai as genai

from app.transcript_agent.transcript_agent import TranscriptAgent
from app.reddit_world_news import run_with_praw
from app.config import load_config
from app.utils import fetch_news_summary


logger = logging.getLogger(__name__)


@dataclass
class ProducerConfig:
    batch_produce_count: int = 1
    news_timeframe: str = "day"  # 'hour', 'day', 'week', 'month', 'year', 'all'
    news_limit: int = 10  # Number of news items to fetch
    comment_limit: int = 5  # Number of top comments per post
    subreddit: str = "worldnews"
    max_workers: int = 5  # Maximum concurrent threads for fetching summaries


def _fetch_and_process_news_item(news_item: dict) -> Optional[dict]:
    """
    Fetch summary for a single news item and return processed item.
    Returns None if fetching fails.
    """
    try:
        logger.info(f"Fetching summary for: {news_item['source_url']}")
        summary = fetch_news_summary(news_item["source_url"])
        
        # Transform to format expected by transcript agent
        processed_item = {
            "url": news_item["source_url"],
            "summary": summary,
            "comments": [
                {"author": c["author"], "body": c["body"]} 
                for c in news_item["comments"]
            ]
        }
        logger.info(f"Successfully processed news item: {news_item['source_url']}")
        return processed_item
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Failed to fetch summary for {news_item['source_url']}: {e}. Skipping this news item.")
        return None


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

        # Initialize transcript agent
        self._transcript_agent = TranscriptAgent()
        
        # Fetch news items from Reddit
        self._news_items = []
        self._current_news_index = 0
        
        try:
            logger.info(f"Fetching {config.news_limit} news items from r/{config.subreddit}")
            # Convert generator to list
            news_generator = run_with_praw(
                config=load_config(),
                timeframe=config.news_timeframe,
                limit=config.news_limit,
                comment_limit=config.comment_limit,
                subreddit=config.subreddit
            )
            
            # Collect all news items first
            news_items_list = list(news_generator)
            logger.info(f"Fetched {len(news_items_list)} news items from Reddit")
            
            # Fetch summaries concurrently using ThreadPoolExecutor
            logger.info(f"Fetching summaries concurrently with {config.max_workers} workers")
            with ThreadPoolExecutor(max_workers=config.max_workers) as executor:
                # Submit all tasks
                future_to_news = {
                    executor.submit(_fetch_and_process_news_item, news_item): news_item
                    for news_item in news_items_list
                }
                
                # Collect results as they complete
                for future in as_completed(future_to_news):
                    processed_item = future.result()
                    if processed_item is not None:
                        self._news_items.append(processed_item)
            
            logger.info(f"Successfully fetched {len(self._news_items)} news items with summaries")
        except Exception as e:  # noqa: BLE001
            logger.exception(f"Failed to fetch news from Reddit: {e}")
            # Provide fallback behavior with empty news list
            self._news_items = []

    def _process_next_news(self) -> Optional[list[str]]:
        """
        Process the next news item using the transcript agent.
        Returns list of paragraphs or None if no more news.
        """
        if self._current_news_index >= len(self._news_items):
            return None
        
        news_item = self._news_items[self._current_news_index]
        
        try:
            logger.info(f"Processing news {self._current_news_index + 1}/{len(self._news_items)}: {news_item['url']}")
            
            # Prepare input with prefetched summary and comments
            news_input = {
                "summary": news_item["summary"],
                "comments": news_item["comments"]
            }
            
            # Use transcript agent to generate paragraphs
            # Add sleep guidance only for the last news item
            result = self._transcript_agent.process_news(
                news_input=news_input,
                add_sleep_guidance=True
            )
            
            paragraphs = result.get("paragraphs", [])
            self._current_news_index += 1
            
            return paragraphs
        except Exception as e:  # noqa: BLE001
            logger.exception(f"Failed to process news item: {e}")
            self._current_news_index += 1
            # Return a fallback paragraph
            return [
                "Let us move on to the next story. May your mind stay calm and peaceful as you rest."
            ]

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
                    # Process the next news item
                    paragraphs = self._process_next_news()
                    
                    if paragraphs is None:
                        # All news consumed, send goodbye message
                        logger.info("All news items processed, sending goodbye message")
                        goodbye_message = (
                            "That's all for tonight's news. Thank you for listening. "
                            "May you have a peaceful and restful sleep. Goodnight."
                        )
                        self._queue.put(goodbye_message, timeout=0.5)
                        # Stop processing after goodbye
                        break
                    
                    logger.info(f"Produced {len(paragraphs)} paragraphs")
                    for paragraph in paragraphs:
                        logger.info(f"Enqueuing paragraph: {paragraph[:50]}...")
                        self._queue.put(paragraph, timeout=0.5)
                except Exception:  # noqa: BLE001
                    logger.exception("Producer failed to enqueue paragraph")

            time.sleep(0.05)

        logger.info("Producer stopping.")
