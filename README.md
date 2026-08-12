# chess-self-analysis

An analysis of my own Chess.com history. I play on instinct rather than from opening theory, so after 1,488 games over four years I wanted to see what that actually looks like measured from the outside. This pulls my full game history through the Chess.com public API, tidies it into one row per game, and analyses it with pandas, then goes a layer deeper with engine evaluation.

## Findings

**Outcome-based analysis (full history, 1,488 games)**

- I play 1.e4 as White in 98% of games. Chess.com's classifier identifies my most-repeated line as the King's Pawn Opening (65 games as White, 62 as Black), which I could not have named before running this.
- 786 wins, 630 losses, 72 draws: a 52.8% win rate since November 2022. Peak rapid rating 1,259, currently 1,148.
- I castle in 64% of games, kingside about two-thirds of the time, on move 11 on average.
- Checkmate ends 47% of my games, more than resignations, timeouts and draws combined.
- The strongest single predictor of a win is entering the game rated at or above my opponent, a 24-point swing in win rate, larger than colour, castling side or game length.
- 1,465 of 1,488 games are rapid, so the bullet and blitz numbers below carry little weight.

**Engine analysis (Stockfish, 300 most recent rapid games)**

Outcome data cannot distinguish a well-played win from a lucky one, so v2 adds move-level evaluation.

- Blunder rate of 7.0% of my moves, roughly one every 14 moves, plus 11.8% mistakes and 10.6% inaccuracies.
- The middlegame is the weak phase, not the opening or endgame: average centipawn loss per move is 43 in the opening, 78 in the middlegame, 52 in the endgame.
- Familiarity with an opening does not mean safety in it. Among openings reached at least six times, the Bishop's Opening (Berlin Defense) carries my highest blunder rate at 9.0%, and the Caro-Kann my lowest at 5.7%.
- 8pm local is my weakest hour, 11.1% blunder rate against a 7.0% baseline, over a 234-move sample. My apparent best hour has only a 15-move sample and should be treated as noise.
- Worst single move in the sample: Rxg6 in an endgame on 2026-04-08, turning a winning position into a lost one.

All figures are computed in the notebook and written to `data/processed/headline_stats.json` and `blunder_stats.json`, so this README cannot drift out of sync with the data.

## Structure

chess-self-analysis/
├── scripts/
│ ├── download_games.py # pulls every monthly archive from the Chess.com API
│ ├── setup_engine.py # downloads the Stockfish binary
│ └── analyze_blunders.py # runs Stockfish over a game sample, move by move
├── notebooks/
│ └── chess_self_analysis.ipynb
├── data/
│ ├── raw/ # one JSON file per month, as returned by the API
│ └── processed/ # tidy per-game CSV, engine output, headline stats
├── engines/ # Stockfish binary, gitignored (~110MB)
├── requirements.txt
└── .gitignore


**download_games.py** walks Chess.com's `/pub/player/{username}/games/archives` endpoint, which lists one URL per active month, caches each month's raw JSON, and combines everything into a structured JSON file and a single PGN. Re-running only fetches months not already cached.

**setup_engine.py** and **analyze_blunders.py** add move-quality measurement. The engine binary is downloaded rather than committed, so it stays out of version control. The analysis replays a configurable sample of games through python-chess, asks Stockfish to evaluate the position before and after each of my moves, and records the centipawn loss. Engine calls are slow, so sample size and search depth are both flags and results are cached per game.

**The notebook** is written to be read rather than only run. Each section explains what it computes before showing the code. The more involved engineering sits in the tidying stage: reconstructing how each game ended from Chess.com's two-sided result codes, recovering opening names from the ECOUrl field, and replaying every game move by move to extract first moves, castling timing and game length.

## Running it

```bash
python -m venv .venv
.venv\Scripts\activate          # source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt

python scripts/download_games.py --username <your_username>
python scripts/setup_engine.py                 # optional, fetches Stockfish
python scripts/analyze_blunders.py             # optional, move-quality analysis
jupyter notebook notebooks/chess_self_analysis.ipynb
```

Nothing is specific to my account except the local timezone offset in section 7, which defaults to UTC+3. The engine steps are optional: `data/processed/engine_analysis.csv` is committed, so the notebook runs end to end without them.

## Data source

All game data comes from the [Chess.com Published-Data API](https://www.chess.com/news/view/published-data-api), which is free and unauthenticated. The downloaded data is committed so the notebook reproduces without re-fetching. Move quality comes from running Stockfish locally against that same history.

## Limitations

- Bullet and blitz samples are too small to draw conclusions from (15 and 8 games).
- Opening names come from Chess.com's own classifier, not hand-labelled ground truth.
- Time-of-day analysis assumes a fixed UTC+3 offset year-round and does not account for travel or DST.
- Sections 1 to 13 measure outcomes, not move quality: they show what correlates with winning, not whether any individual move was sound.
- Engine analysis covers a 300-game recent sample at depth 14, a deliberate speed against precision tradeoff. The centipawn figures are directionally reliable rather than precise.
