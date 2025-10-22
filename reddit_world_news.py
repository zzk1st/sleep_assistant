#!/usr/bin/env python3
"""
Fetch top posts from r/worldnews with source link + top comments using PRAW (OAuth).

Requires REDDIT_* environment variables for authentication.

Outputs:
- Pretty text (default)
- Or JSON via --json
"""

import argparse
import os
import sys
import json
import re
from datetime import datetime, timezone


def praw_available():
    req = ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USERNAME", "REDDIT_PASSWORD"]
    return all(os.getenv(k) for k in req)

def run_with_praw(timeframe: str, limit: int|None, comment_limit: int, subreddit="worldnews"):
    """
    Generator that yields posts one at a time from the specified subreddit.
    
    Args:
        timeframe: Time filter for posts ('hour', 'day', 'week', 'month', 'year', 'all')
        limit: Maximum number of posts to fetch (None for unlimited)
        comment_limit: Number of top comments to fetch per post
        subreddit: Name of the subreddit to fetch from
        
    Yields:
        dict: Post data including title, score, comments, etc.
        
    Examples:
        # Fetch first 5 posts only (manual pagination)
        post_gen = run_with_praw("day", limit=None, comment_limit=3)
        first_5 = [next(post_gen) for _ in range(5)]
        
        # Fetch all posts up to a limit
        all_posts = list(run_with_praw("day", limit=20, comment_limit=3))
        
        # Stream posts one at a time (memory efficient)
        for post in run_with_praw("week", limit=100, comment_limit=5):
            process_post(post)
            # Can break early if needed
            if some_condition:
                break
    """
    import praw  # pip install praw

    reddit = praw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        username=os.getenv("REDDIT_USERNAME"),
        password=os.getenv("REDDIT_PASSWORD"),
        user_agent=os.getenv("REDDIT_USER_AGENT", "script:worldnews-top:v1.1 (by /u/your_username)"),
    )

    sub = reddit.subreddit(subreddit)

    for post in sub.top(time_filter=timeframe, limit=limit):
        # fetch comments sorted by 'top'
        post.comment_sort = "top"
        post.comment_limit = comment_limit
        post.comments.replace_more(limit=0)

        comments = []
        for c in post.comments[:comment_limit]:
            try:
                body = c.body if isinstance(c.body, str) else str(c.body)
                if c.stickied or c.author is None:
                    continue
                comments.append({
                    "author": str(c.author),
                    "score": getattr(c, "score", None),
                    "body": body,
                })
            except Exception:
                # be robust against deleted/odd objects
                continue

        source_url = post.url
        item = {
            "title": post.title,
            "score": post.score,
            "num_comments": post.num_comments,
            "source_url": source_url,
            "author": str(post.author) if post.author else "[deleted]",
            "id": post.id,
            "comments": comments,
        }
        yield item


def fetch_posts_paginated(timeframe: str, page_size: int, comment_limit: int, subreddit="worldnews", max_posts=None):
    """
    Helper function for explicit page-based pagination.
    
    Args:
        timeframe: Time filter for posts
        page_size: Number of posts per page
        comment_limit: Number of top comments per post
        subreddit: Name of the subreddit
        max_posts: Maximum total posts to fetch (None for unlimited)
        
    Yields:
        list: Pages of posts, each page contains up to page_size posts
        
    Example:
        # Fetch posts in pages of 10
        for page_num, page in enumerate(fetch_posts_paginated("day", page_size=10, comment_limit=3), start=1):
            print(f"Processing page {page_num} with {len(page)} posts")
            for post in page:
                print(post['title'])
            # Can stop after certain number of pages
            if page_num >= 5:
                break
    """
    post_gen = run_with_praw(timeframe, limit=max_posts, comment_limit=comment_limit, subreddit=subreddit)
    page = []
    
    for post in post_gen:
        page.append(post)
        if len(page) >= page_size:
            yield page
            page = []
    
    # Yield remaining posts if any
    if page:
        yield page


# ---------- Main ----------

def main():
    ap = argparse.ArgumentParser(description="Fetch r/worldnews top posts with source link + top comments using PRAW.")
    ap.add_argument("--timeframe", choices=["hour","day","week","month","year","all"], default="day")
    ap.add_argument("--limit", type=int, default=20, help="How many posts to fetch")
    ap.add_argument("--comment-limit", type=int, default=5, help="Top comments per post")
    ap.add_argument("--subreddit", default="worldnews")
    ap.add_argument("--json", action="store_true", help="Output JSON instead of pretty text")
    args = ap.parse_args()

    if not praw_available():
        print("Error: Required REDDIT_* environment variables not set.", file=sys.stderr)
        print("Please set: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD", file=sys.stderr)
        sys.exit(1)

    # Consume the generator - you can also iterate over it directly for true pagination
    items = list(run_with_praw(args.timeframe, args.limit, args.comment_limit, subreddit=args.subreddit))

    # Output
    print(json.dumps(items, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
