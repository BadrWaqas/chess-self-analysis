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

## The v2 headlines: what Stockfish found

Sections 1-13 above are outcome-based — they can't tell a clean win from a lucky one. Running
[Stockfish](https://stockfishchess.org/) over my **300 most recent rapid games** (see section 14) closes
that gap:

- **I blunder (throw away 3+ pawns of advantage in one move) about once every 14 of my own moves** — a
  7.0% blunder rate, plus another 11.8% mistakes and 10.6% inaccuracies. Most of my moves are fine; the
  bad ones are common enough to matter.
- **The middlegame is where I fall apart, not the opening.** Average centipawn loss per move: **43 in the
  opening, 78 in the middlegame, 52 in the endgame** — I lose nearly twice as much per move once the
  book runs out and the position opens up as I do anywhere else.
- **My favourite openings are *not* uniformly safer.** Among openings I reach at least 6 times in the
  sample, the **Bishops Opening: Berlin Defense** is my riskiest (9.0% blunder rate over 10 games) and
  the **Caro-Kann Defense** my safest (5.7% over 7 games) — playing an opening a lot doesn't mean I play
  it well.
- **8pm (UTC+3) is my worst hour to play** — an 11.1% blunder rate, well above my 7.0% baseline, over a
  solid 234-move sample. (My best-looking hour, 8am, had zero blunders — but on only 15 moves, so treat
  that one as a hint, not a rule.)
- **My single worst blunder in the sample:** `Rxg6` in the endgame on 2026-04-08, swinging the position
  from completely winning to completely lost in one move —
  [see the actual game](https://www.chess.com/game/live/167003692906).

*(Also computed live — see `data/processed/blunder_stats.json`. Full method, chart-by-chart, in section
14 of the notebook.)*

## What's actually in here

This is a small, honest data pipeline: **download → tidy → analyse**, with nothing hidden in a black box.

```
chess-self-analysis/
├── scripts/
│   ├── download_games.py       # pulls every monthly archive from the Chess.com public API
│   ├── setup_engine.py         # downloads Stockfish for Windows (v2)
│   └── analyze_blunders.py     # runs Stockfish over a game sample, move by move (v2)
├── notebooks/
│   └── chess_self_analysis.ipynb   # the full analysis, with charts and running commentary
├── data/
│   ├── raw/                    # one JSON file per month, exactly as Chess.com returns it
│   └── processed/              # combined PGN/JSON, tidy per-game CSV, engine analysis, headline stats
├── engines/                     # Stockfish binary lives here, gitignored (~110MB, not committed)
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

### 2. `scripts/setup_engine.py` + `scripts/analyze_blunders.py` — measure move quality (v2)

Everything from `download_games.py` is outcome-based: wins, losses, openings, timing. It never asks
whether a specific move was actually *good*. These two scripts close that gap by running the
[Stockfish](https://stockfishchess.org/) chess engine over a sample of real games:

- `setup_engine.py` downloads the official prebuilt Stockfish binary for Windows straight from its
  GitHub releases (~110MB) into `engines/`, which is gitignored — every developer runs this once instead
  of a binary living in version control.
- `analyze_blunders.py` replays a configurable sample of recent games (by default my **300 most recent
  rapid games**) through `python-chess`'s UCI interface, asks Stockfish to evaluate the position before
  and after each of my own moves, and records the **centipawn loss** for each one — see the notebook's
  section 14 for exactly what that means and how moves get classified into inaccuracy / mistake /
  blunder. It's slow by nature (an engine call per position), so both the sample size and the search
  depth are flags, results are cached per game so a re-run only tops up new games, and progress
  prints as it goes.

```bash
python scripts/setup_engine.py
python scripts/analyze_blunders.py --sample-size 300 --time-class rapid --depth 14
```

### 3. `notebooks/chess_self_analysis.ipynb` — turn it into answers

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
14. **Engine analysis (v2):** Stockfish-measured centipawn loss on a 300-game recent sample — blunder
    rate by opening and by hour of day, average centipawn loss by game phase, and the worst individual
    moves in the sample, each linked back to the actual game

## Running it yourself

```bash
python -m venv .venv
.venv\Scripts\activate          # source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt

python scripts/download_games.py --username <your_chess.com_username>
python scripts/setup_engine.py                # optional (v2): fetches Stockfish for Windows
python scripts/analyze_blunders.py             # optional (v2): move-quality analysis, see above
jupyter notebook notebooks/chess_self_analysis.ipynb
```

Swap the username to run this against your own history — nothing in the pipeline is chefbadr-specific
except the local-timezone offset applied in section 7 (I've defaulted it to UTC+3; adjust it to yours).
The two v2 steps are optional: `data/processed/engine_analysis.csv` is already committed, so section 14
of the notebook runs as-is against my own sample even if you skip them — you only need to run them
yourself to widen the sample, change the search depth, or analyse your own games instead of mine.

## Data source

All data comes from the [Chess.com Published-Data API](https://www.chess.com/news/view/published-data-api),
which is free and requires no authentication. This repo commits the downloaded data itself
(`data/raw/`, `data/processed/`) so the notebook reproduces identically without hitting the API again —
it's my own public game history, already visible on my Chess.com profile. Move-quality data (v2) comes
from running [Stockfish](https://stockfishchess.org/), a free and open-source engine, locally against
that same game history — no third-party analysis service involved.

## Caveats I'd rather admit than hide

- Bullet and blitz samples are tiny (15 and 8 games respectively) — don't read too much into those rating
  lines.
- "Opening name" is Chess.com's own classifier via the `ECOUrl` field, not a hand-labelled ground truth.
- Local time-of-day assumes a fixed UTC+3 offset year-round; Chess.com doesn't record travel or DST.
- Sections 1-13 are outcome-based analysis, not move-quality analysis — they tell you *what* correlates
  with winning, not whether any individual move was actually good.
- Section 14's engine analysis only covers a 300-game recent sample (not my full history) at a modest
  search depth (14 ply), a deliberate speed/precision tradeoff — see the notebook for the timing math.
  Treat the centipawn-loss numbers as directionally right, not lab-grade precise.
