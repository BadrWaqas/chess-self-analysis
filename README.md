# ♟️ chess-self-analysis — an analysis of my own chess

I'm [chefbadr](https://www.chess.com/member/Chefbadr) on Chess.com. I've never opened an opening book in
my life — I play entirely on instinct — and after **1,488 games** over four years I got curious what that
instinct actually looks like from the outside. So I pulled my entire Chess.com history through their free
public API and pointed pandas at it.

Turns out the data knows me better than I know myself.

## The headlines

- **I play `1.e4` as White 98% of the time.** I did not know I was that predictable.
- **Chess.com's own opening classifier says my most-repeated line is the King's Pawn Opening** (65 games
  as White, 62 as Black) — I could not have told you its name before running this notebook.
- **786–630–72.** A 52.8% win rate across every rated and casual game since November 2022.
- **1,259** is my peak rapid rating; **1,148** is where it sits as of this writing.
- **I castle in 64% of games**, kingside nearly two-thirds of the time, on move **11** on average.
- **Checkmate ends 47% of my games** — more than resignations, timeouts, and draws combined. I don't let
  go of a losing position easily, for better or worse.
- **The single biggest predictor of whether I win: being rated at or above my opponent going in** — a
  +24-point swing in win rate, bigger than colour, castling side, or game length.
- **Saturday is my best day** (58% win rate) — make of that what you will.
- **1,465 of 1,488 games (98%) are rapid.** I am, almost exclusively, a rapid player.

*(Every number above is computed live in the notebook — see `data/processed/headline_stats.json` for the
machine-readable version, regenerated each time the notebook runs.)*

## What's actually in here

This is a small, honest data pipeline: **download → tidy → analyse**, with nothing hidden in a black box.

```
chess-self-analysis/
├── scripts/
│   └── download_games.py       # pulls every monthly archive from the Chess.com public API
├── notebooks/
│   └── chess_self_analysis.ipynb   # the full analysis, with charts and running commentary
├── data/
│   ├── raw/                    # one JSON file per month, exactly as Chess.com returns it
│   └── processed/              # combined PGN/JSON, the tidy per-game CSV, headline stats
├── requirements.txt
└── .gitignore
```

### 1. `scripts/download_games.py` — get the data

Chess.com publishes a free, unauthenticated API: `/pub/player/{username}/games/archives` lists one URL
per calendar month a player was active, and each of those URLs returns every game played that month
(PGN included). The script walks that list, caches each month's raw JSON under `data/raw/`, and stitches
everything into `data/processed/games.json` (structured) and `data/processed/all_games.pgn` (every game's
moves, back to back). Re-running it only fetches months you don't already have cached.

```bash
python scripts/download_games.py --username chefbadr
```

### 2. `notebooks/chess_self_analysis.ipynb` — turn it into answers

The notebook is written to be read, not just run — each section explains what it's computing and why
before showing the code, aimed at anyone comfortable with pandas but new to the Chess.com data shape.
It covers:

1. Loading the raw archive data
2. Turning nested JSON + embedded PGN into one tidy row-per-game DataFrame (this is where the interesting
   engineering lives: reverse-engineering *how* a game ended from Chess.com's two-sided result codes,
   recovering proper opening names from the `ECOUrl` field, and replaying every game move-by-move with
   `python-chess` to get first moves, castling timing, and game length)
3. Overview: total games, most common time controls
4. Rating progression over time, per time control
5. Win rate by colour
6. Win rate by opening
7. Performance by time of day and day of week
8. Win/loss/draw vs. opponent rating difference
9. Instinct-player habits: most common first moves and most-repeated opening sequences, as White and
   as Black, with their real names
10. Castling habits: how early, and which side
11. Average game length, and how games actually end (checkmate / resignation / timeout / draw)
12. Which recurring patterns in my play correlate with winning the most — and losing the most
13. Headline stats — the numbers quoted above, computed live so they can't drift out of sync with the data

## Running it yourself

```bash
python -m venv .venv
.venv\Scripts\activate          # source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt

python scripts/download_games.py --username <your_chess.com_username>
jupyter notebook notebooks/chess_self_analysis.ipynb
```

Swap the username to run this against your own history — nothing in the pipeline is chefbadr-specific
except the local-timezone offset applied in section 7 (I've defaulted it to UTC+3; adjust it to yours).

## Data source

All data comes from the [Chess.com Published-Data API](https://www.chess.com/news/view/published-data-api),
which is free and requires no authentication. This repo commits the downloaded data itself
(`data/raw/`, `data/processed/`) so the notebook reproduces identically without hitting the API again —
it's my own public game history, already visible on my Chess.com profile.

## Caveats I'd rather admit than hide

- Bullet and blitz samples are tiny (15 and 8 games respectively) — don't read too much into those rating
  lines.
- "Opening name" is Chess.com's own classifier via the `ECOUrl` field, not a hand-labelled ground truth.
- Local time-of-day assumes a fixed UTC+3 offset year-round; Chess.com doesn't record travel or DST.
- This is outcome-based analysis, not move-quality analysis — it tells you *what* correlates with winning,
  not whether any individual move was actually good. Running a chess engine over a game sample is the
  natural next step.
