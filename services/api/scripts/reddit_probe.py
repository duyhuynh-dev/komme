# ruff: noqa: E402

import argparse
import asyncio
from pathlib import Path
import sys

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.core.config import get_settings
from app.taste.errors import TasteProviderError
from app.taste.providers.public_username import PublicUsernameProvider


async def main(username: str) -> int:
    provider = PublicUsernameProvider()
    try:
        activity = await provider.fetch(username)
    except TasteProviderError as error:
        print(f"[{error.code}] {error.message}")
        return 1

    cache_dir = Path(get_settings().reddit_public_cache_dir) / "probes"
    cache_dir.mkdir(parents=True, exist_ok=True)
    output_path = cache_dir / f"{username.lower()}.json"
    output_path.write_text(activity.model_dump_json(indent=2))

    print(f"Fetched public Reddit activity for u/{activity.username}")
    print(f"Comments: {activity.total_comments}")
    print(f"Submissions: {activity.total_submissions}")
    print("Top subreddit activity:")
    for summary in activity.subreddit_activity[:10]:
        total = summary.comment_count + summary.submission_count
        print(
            f"  - r/{summary.subreddit}: {total} items "
            f"({summary.comment_count} comments / {summary.submission_count} submissions), karma {summary.total_karma}"
        )
    print(f"Saved normalized output to {output_path}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Probe Reddit public profile activity.")
    parser.add_argument("username", help="Reddit username to inspect")
    parsed = parser.parse_args()
    raise SystemExit(asyncio.run(main(parsed.username)))
