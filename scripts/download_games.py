"""
Download the complete Chess.com game history for a given player.

Chess.com exposes a free, unauthenticated public API. The relevant shape is:

    GET /pub/player/{username}/games/archives
        -> {"archives": ["https://api.chess.com/pub/player/{username}/games/2022/11", ...]}

    GET <one of those archive URLs>
        -> {"games": [ {..one game record, including a "pgn" field..}, ... ]}

There is one archive per calendar month the player was active, and each
archive contains every game (any time control, rated or not) played that
month. To get "complete history" we simply have to walk every archive URL.

This script does three things:
  1. Fetch the list of monthly archives for the player.
  2. Download each archive's raw JSON and cache it under data/raw/ (one
     file per month) so re-runs don't re-hit the API for months we already
     have.
  3. Stitch everything together into two convenience files under
     data/processed/: one combined JSON array of every game, and one
     combined PGN file with every game's moves back to back. The notebook
     reads from data/processed/, not from the API directly -- that keeps
     "get the data" and "analyse the data" cleanly separated.

Chess.com asks API consumers to identify themselves with a descriptive
User-Agent so they can contact you if something's wrong on your end
instead of just blocking the IP -- see https://www.chess.com/news/view/published-data-api
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import requests

API_ROOT = "https://api.chess.com/pub"
HEADERS = {
    "User-Agent": (
        "chess-self-analysis/1.0 "
        "(personal project analysing my own Chess.com history; "
        "contact: laithbadrwed@gmail.com)"
    )
}
REQUEST_DELAY_SECONDS = 0.5  # be polite to a free public API


def get_archive_urls(username: str) -> list[str]:
    """Ask Chess.com for the list of monthly archive URLs for a player."""
    url = f"{API_ROOT}/player/{username}/games/archives"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()["archives"]


def download_archives(username: str, raw_dir: Path, force: bool = False) -> list[Path]:
    """Download each monthly archive to data/raw/, skipping ones we already have.

    Returns the list of raw JSON file paths (old + newly downloaded).
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    archive_urls = get_archive_urls(username)
    print(f"Found {len(archive_urls)} monthly archives for '{username}'.")

    saved_paths = []
    for url in archive_urls:
        # Archive URLs look like .../games/2022/11 -> use YYYY-MM as the filename
        year, month = url.rstrip("/").split("/")[-2:]
        out_path = raw_dir / f"{year}-{month}.json"
        saved_paths.append(out_path)

        if out_path.exists() and not force:
            continue

        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        out_path.write_text(json.dumps(resp.json(), indent=2), encoding="utf-8")
        print(f"  downloaded {year}-{month}: {len(resp.json().get('games', []))} games")
        time.sleep(REQUEST_DELAY_SECONDS)

    return saved_paths


def combine(raw_paths: list[Path], processed_dir: Path) -> None:
    """Merge every monthly archive into one JSON array and one PGN file."""
    processed_dir.mkdir(parents=True, exist_ok=True)

    all_games = []
    for path in sorted(raw_paths):
        data = json.loads(path.read_text(encoding="utf-8"))
        all_games.extend(data.get("games", []))

    # Games in each monthly archive are already chronological; months are
    # processed in sorted (chronological) filename order above.
    combined_json_path = processed_dir / "games.json"
    combined_json_path.write_text(json.dumps(all_games, indent=2), encoding="utf-8")

    combined_pgn_path = processed_dir / "all_games.pgn"
    with combined_pgn_path.open("w", encoding="utf-8") as f:
        for game in all_games:
            pgn = game.get("pgn")
            if pgn:
                f.write(pgn.strip() + "\n\n")

    print(f"\nCombined {len(all_games)} games total.")
    print(f"  -> {combined_json_path}")
    print(f"  -> {combined_pgn_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", default="chefbadr", help="Chess.com username")
    parser.add_argument(
        "--force", action="store_true", help="Re-download months already cached locally"
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    raw_dir = project_root / "data" / "raw"
    processed_dir = project_root / "data" / "processed"

    raw_paths = download_archives(args.username, raw_dir, force=args.force)
    combine(raw_paths, processed_dir)


if __name__ == "__main__":
    main()
