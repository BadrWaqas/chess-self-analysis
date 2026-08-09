"""
Download the Stockfish chess engine for Windows.

Move-quality analysis (scripts/analyze_blunders.py) needs an actual chess
engine binary to call out to -- `python-chess` only speaks the UCI protocol
to *some* engine, it doesn't ship one. Stockfish publishes prebuilt,
license-free (GPLv3) binaries as GitHub release assets, so rather than
committing a ~110MB executable to this repo, this script fetches the latest
one on demand.

    GET /repos/official-stockfish/Stockfish/releases/latest
        -> {"tag_name": "sf_18", "assets": [{"name": ..., "browser_download_url": ...}, ...]}

We grab the Windows x86-64 AVX2 build (the standard choice for any Intel/AMD
CPU from roughly the last decade -- see https://www.chess.com/computer-chess-championship/about
for background on why engines ship multiple CPU-feature variants), unzip it,
and keep just the .exe under engines/stockfish.exe. That folder is
.gitignore'd: every developer runs this script once instead of the binary
living in version control.
"""

from __future__ import annotations

import argparse
import io
import shutil
import zipfile
from pathlib import Path

import requests

GITHUB_API_LATEST_RELEASE = "https://api.github.com/repos/official-stockfish/Stockfish/releases/latest"
ASSET_NAME = "stockfish-windows-x86-64-avx2.zip"
HEADERS = {
    "User-Agent": (
        "chess-self-analysis/2.0 "
        "(personal project analysing my own Chess.com history; "
        "contact: laithbadrwed@gmail.com)"
    )
}


def find_download_url() -> tuple[str, str]:
    """Ask GitHub for the latest Stockfish release and return (version, zip URL)."""
    resp = requests.get(GITHUB_API_LATEST_RELEASE, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    release = resp.json()
    for asset in release["assets"]:
        if asset["name"] == ASSET_NAME:
            return release["tag_name"], asset["browser_download_url"]
    raise RuntimeError(f"No asset named {ASSET_NAME!r} in latest Stockfish release")


def install(engines_dir: Path, force: bool = False) -> Path:
    """Download, unzip, and install stockfish.exe under engines_dir. Returns its path."""
    exe_path = engines_dir / "stockfish.exe"
    if exe_path.exists() and not force:
        print(f"Already installed: {exe_path} (pass --force to re-download)")
        return exe_path

    version, url = find_download_url()
    print(f"Downloading Stockfish {version} ({ASSET_NAME}) ...")
    resp = requests.get(url, headers=HEADERS, timeout=120)
    resp.raise_for_status()

    engines_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        # The zip contains full source + docs; we only want the .exe, wherever
        # the release happens to nest it.
        exe_member = next(n for n in zf.namelist() if n.endswith(".exe"))
        with zf.open(exe_member) as src, exe_path.open("wb") as dst:
            shutil.copyfileobj(src, dst)

    print(f"Installed -> {exe_path}")
    return exe_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force", action="store_true", help="Re-download even if engines/stockfish.exe already exists"
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    engines_dir = project_root / "engines"
    install(engines_dir, force=args.force)


if __name__ == "__main__":
    main()
