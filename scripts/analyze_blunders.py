"""
Run Stockfish over a sample of my games to measure actual move quality.

Section 6-12 of the notebook are all *outcome*-based: they tell you what
correlates with winning, never whether a specific move was any good. This
script closes that gap by replaying real games through a chess engine and
recording, move by move, how much worse my move was than the best one
Stockfish could find.

--- What "centipawn loss" means -------------------------------------------

A centipawn is 1/100th of a pawn -- the standard unit engines use to score a
position (a pawn-up position is roughly +100). For every position it looks
at, Stockfish reports the position's value *for the side to move*: positive
means that side is doing well, negative means they're worse off.

For each of my moves, this script asks Stockfish to evaluate the position
twice: once *before* the move (giving the best score Stockfish thinks I
could have achieved), and once immediately *after* the move I actually
played (giving the score my move actually reached, converted back to my own
point of view). The gap between those two -- clipped at 0, since a move
can't be better than the engine's own best line -- is the move's
**centipawn loss**:

    cp_loss = max(0, eval_before_my_move - eval_after_my_move)

A cp_loss of 0 means Stockfish considers my move (tied for) the best
available. A cp_loss of 300 means my move let a 3-pawn advantage evaporate,
or worse. Note this only evaluates *my* moves, not my opponents' -- each
position still has to be analysed once regardless (its score doubles as the
"after" reading for the move that reached it and the "before" reading for
whoever moves next), so skipping the classification step for opponent moves
doesn't skip the engine call, but it does keep the output focused on my own
play, which is the point of this script.

--- How moves are classified -----------------------------------------------

There's no official standard here; this follows the rough convention used
by chess.com/lichess post-game analysis, applied to the cp_loss above:

    cp_loss >= 300   -> "blunder"     (threw away 3+ pawns of advantage)
    cp_loss >= 100   -> "mistake"     (threw away 1-3 pawns)
    cp_loss >= 50    -> "inaccuracy"  (threw away 0.5-1 pawn)
    otherwise        -> "ok"

Positions where someone is already getting checkmated are scored as a large
constant (see MATE_SCORE_CP) rather than a real centipawn value, so forced
mates still register as huge blunders/brilliancies without special-casing
every comparison.

--- Why depth is configurable, and why it's modest by default -------------

Full engine analysis (the kind chess.com/lichess run, depth ~20+ with
multi-line search) takes seconds per position. Over a few hundred games
that's hours. This script defaults to depth 14, which a quick local
benchmark on this machine put at ~75ms/position (Stockfish 18, 4 threads) --
strong enough to reliably catch real blunders, fast enough that a
300-game sample finishes in well under an hour. Pass --depth for a deeper
(slower, more precise) or shallower (faster, noisier) search.

--- Output -------------------------------------------------------------

One row per move *I* played, appended to data/processed/engine_analysis.csv.
Deliberately kept as raw, joinable output (join key: uuid, same as
games_tidy.csv) rather than pre-aggregated -- aggregation, charts, and the
resulting headline stats belong in the notebook, exactly like
games_tidy.csv / headline_stats.json are notebook output, not
download_games.py output. This script's only job is "produce the expensive
data"; re-running it just tops up whatever games aren't analysed yet.
"""

from __future__ import annotations

import argparse
import io
import time
from pathlib import Path

import chess
import chess.engine
import chess.pgn
import pandas as pd

ME = "chefbadr"

DEFAULT_ENGINE_PATH = Path(__file__).resolve().parent.parent / "engines" / "stockfish.exe"
DEFAULT_SAMPLE_SIZE = 300  # how many of my most recent games (in --time-class) to analyse
DEFAULT_TIME_CLASS = "rapid"
DEFAULT_DEPTH = 14  # search depth per position -- see module docstring for the timing tradeoff
DEFAULT_THREADS = 4
DEFAULT_HASH_MB = 256

# Centipawn-loss thresholds for classifying a move -- see module docstring.
INACCURACY_CP = 50
MISTAKE_CP = 100
BLUNDER_CP = 300

# Forced mate isn't a centipawn value; treat it as this many "centipawns" so
# mates still sort/compare sanely against ordinary evaluations.
MATE_SCORE_CP = 100_000

OUTPUT_COLUMNS = [
    "uuid", "ply", "move_number", "mover_color", "phase",
    "move_san", "cp_before", "cp_after", "cp_loss", "classification",
]


def game_phase(board: chess.Board) -> str:
    """Classify the position *before* a move as opening / middlegame / endgame.

    There's no official definition, so this uses a simple two-part heuristic:
      - opening: still within the first 10 full moves (20 plies). This lines
        up with this dataset's own median castling move of 11 (see
        games_tidy.csv / the notebook's castling section) -- by move 10 most
        games have either castled or committed to not doing so.
      - endgame: queens are off the board, or total non-pawn material left
        (both sides combined, kings excluded) has dropped to a rook + minor
        piece or less (<=13 points on the standard 9/5/3/3 scale) -- a
        standard proxy for "few pieces left, kings can get active".
      - middlegame: everything else.
    """
    if board.ply() <= 20:
        return "opening"

    piece_values = {chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
    queens_on = len(board.pieces(chess.QUEEN, chess.WHITE)) + len(board.pieces(chess.QUEEN, chess.BLACK))
    non_pawn_material = sum(
        len(board.pieces(piece_type, color)) * value
        for piece_type, value in piece_values.items()
        for color in (chess.WHITE, chess.BLACK)
    )
    if queens_on == 0 or non_pawn_material <= 13:
        return "endgame"
    return "middlegame"


def evaluate_cp(board: chess.Board, engine: chess.engine.SimpleEngine, depth: int) -> int:
    """Score `board` in centipawns, from the point of view of the side to move."""
    if board.is_checkmate():
        return -MATE_SCORE_CP  # side to move has just been checkmated
    if board.is_game_over():
        return 0  # stalemate, insufficient material, repetition, etc.
    info = engine.analyse(board, chess.engine.Limit(depth=depth))
    return info["score"].relative.score(mate_score=MATE_SCORE_CP)


def classify(cp_loss: int) -> str:
    if cp_loss >= BLUNDER_CP:
        return "blunder"
    if cp_loss >= MISTAKE_CP:
        return "mistake"
    if cp_loss >= INACCURACY_CP:
        return "inaccuracy"
    return "ok"


def analyze_game(pgn_text: str, my_is_white: bool, engine: chess.engine.SimpleEngine, depth: int) -> list[dict]:
    """Replay one game and return one row per move *I* played.

    Walks every position in the game exactly once (rather than re-analysing
    around each of my moves), since each position's score doubles as the
    "after" reading for the move that reached it and the "before" reading
    for the move that follows -- halving the number of engine calls needed.
    """
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if game is None:
        return []

    board = game.board()
    rows = []
    prev_cp = evaluate_cp(board, engine, depth)  # eval before any move, POV of side to move (White)

    for move in game.mainline_moves():
        mover_is_white = board.turn
        mover_cp_before = prev_cp  # already in the mover's own POV
        san = board.san(move)
        ply_before = board.ply()
        phase = game_phase(board)

        board.push(move)
        cp_after_push = evaluate_cp(board, engine, depth)  # POV of the new side to move (opponent)
        mover_cp_after = -cp_after_push  # flip back to the mover's POV

        if mover_is_white == my_is_white:
            cp_loss = max(0, mover_cp_before - mover_cp_after)
            rows.append({
                "ply": ply_before + 1,
                "move_number": ply_before // 2 + 1,
                "mover_color": "white" if mover_is_white else "black",
                "phase": phase,
                "move_san": san,
                "cp_before": mover_cp_before,
                "cp_after": mover_cp_after,
                "cp_loss": cp_loss,
                "classification": classify(cp_loss),
            })

        prev_cp = cp_after_push

    return rows


def load_sample(project_root: Path, time_class: str, sample_size: int) -> pd.DataFrame:
    """Pick the N most recent games in `time_class`, with their PGN attached."""
    tidy_path = project_root / "data" / "processed" / "games_tidy.csv"
    games_path = project_root / "data" / "processed" / "games.json"
    if not tidy_path.exists() or not games_path.exists():
        raise SystemExit(
            "Missing data/processed/games_tidy.csv or games.json -- run "
            "scripts/download_games.py and the notebook's tidy-DataFrame cell first."
        )

    tidy = pd.read_csv(tidy_path, parse_dates=["datetime_utc"])
    tidy = tidy[tidy["time_class"] == time_class].sort_values("datetime_utc", ascending=False)
    sample = tidy.head(sample_size).copy()

    games = pd.read_json(games_path)[["uuid", "pgn", "rules"]]
    sample = sample.merge(games, on="uuid", how="left")
    sample = sample[(sample["rules"] == "chess") & sample["pgn"].notna()]
    return sample


def already_analyzed_uuids(output_path: Path) -> set[str]:
    if not output_path.exists():
        return set()
    return set(pd.read_csv(output_path, usecols=["uuid"])["uuid"].unique())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE,
                         help=f"how many recent games to analyse (default: {DEFAULT_SAMPLE_SIZE})")
    parser.add_argument("--time-class", default=DEFAULT_TIME_CLASS,
                         help=f"chess.com time class to sample from (default: {DEFAULT_TIME_CLASS})")
    parser.add_argument("--depth", type=int, default=DEFAULT_DEPTH,
                         help=f"Stockfish search depth per position (default: {DEFAULT_DEPTH})")
    parser.add_argument("--threads", type=int, default=DEFAULT_THREADS)
    parser.add_argument("--hash-mb", type=int, default=DEFAULT_HASH_MB)
    parser.add_argument("--engine-path", type=Path, default=DEFAULT_ENGINE_PATH,
                         help="path to the Stockfish executable (run scripts/setup_engine.py to fetch it)")
    parser.add_argument("--force", action="store_true",
                         help="re-analyse games already present in engine_analysis.csv")
    args = parser.parse_args()

    if not args.engine_path.exists():
        raise SystemExit(
            f"Stockfish not found at {args.engine_path}. Run scripts/setup_engine.py first."
        )

    project_root = Path(__file__).resolve().parent.parent
    output_path = project_root / "data" / "processed" / "engine_analysis.csv"

    sample = load_sample(project_root, args.time_class, args.sample_size)
    skip_uuids = set() if args.force else already_analyzed_uuids(output_path)
    todo = sample[~sample["uuid"].isin(skip_uuids)]

    print(f"{len(sample)} games in sample ({args.time_class}, most recent {args.sample_size}); "
          f"{len(sample) - len(todo)} already analysed, {len(todo)} to go.")
    if todo.empty:
        return

    engine = chess.engine.SimpleEngine.popen_uci(str(args.engine_path))
    engine.configure({"Threads": args.threads, "Hash": args.hash_mb})

    write_header = not output_path.exists() or args.force
    if args.force and output_path.exists():
        # Drop rows for games we're about to redo, keep the rest.
        existing = pd.read_csv(output_path)
        existing = existing[~existing["uuid"].isin(todo["uuid"])]
        existing.to_csv(output_path, index=False)
        write_header = False

    start = time.time()
    try:
        for i, (_, game_row) in enumerate(todo.iterrows(), start=1):
            my_is_white = game_row["my_color"] == "white"
            rows = analyze_game(game_row["pgn"], my_is_white, engine, args.depth)
            for r in rows:
                r["uuid"] = game_row["uuid"]

            out_df = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
            out_df.to_csv(output_path, mode="a", header=write_header, index=False)
            write_header = False

            n_blunders = sum(r["classification"] == "blunder" for r in rows)
            n_mistakes = sum(r["classification"] == "mistake" for r in rows)
            elapsed = time.time() - start
            avg = elapsed / i
            eta_min = avg * (len(todo) - i) / 60
            print(f"  [{i}/{len(todo)}] {game_row['datetime_utc'].date()} "
                  f"({len(rows)} my-moves, {n_blunders} blunders, {n_mistakes} mistakes) "
                  f"-- elapsed {elapsed:.0f}s, ETA {eta_min:.1f}min")
    except KeyboardInterrupt:
        print("\nInterrupted -- progress so far is already saved to "
              f"{output_path} (games are written as each one finishes). "
              "Re-run the same command to pick up where you left off.")
    finally:
        engine.quit()

    print(f"\nDone. -> {output_path}")


if __name__ == "__main__":
    main()
