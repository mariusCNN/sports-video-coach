"""The basketball plugin: amateur games (CV tracking, league data, coach review) and personal training sessions.

Registered as the entry point `basketball` in the group `sports_video_coach.plugins`. The `hoop-tape-miner` script is
`sports-video-coach` with this plugin as the default, so every old command keeps working.
"""
from __future__ import annotations

from pathlib import Path

from sports_video_coach.plugin import Kind, Plugin

from . import film_hooks, page_hooks, site_hooks

STAGES = {
    "run": ("hoop_tape_miner.run", "one game end to end: run every stage in order, stop where the agent must judge"),
    "fetch": ("hoop_tape_miner.fetch", "league game url -> game folder, game.json, official.json and the game video"),
    "new-game": ("hoop_tape_miner.new_game", "scaffold workspace/teams/<opponent>/<date>/ with game.json + run/"),
    "scout": ("hoop_tape_miner.scout", "rematch dossier: past games vs one opponent -> scout.json + scout.md"),
    "extract": ("hoop_tape_miner.extract", "pass 1: detection + court homography + colour features"),
    "embed": ("hoop_tape_miner.embed", "pass 2a: SigLIP embeddings for team classification"),
    "recalib": ("hoop_tape_miner.recalib", "re-run court homography only, reuse detections"),
    "calibrate": ("hoop_tape_miner.calibrate", "court calibration keyframes for extract/recalib"),
    "tracks": ("hoop_tape_miner.build_tracks", "pass 2b: team clusters + court-space tracking"),
    "jersey": ("hoop_tape_miner.jersey", "pass 3: jersey numbers with Qwen3-VL"),
    "stitch": ("hoop_tape_miner.stitch", "pass 3b: split / join tracklets into player chains (stitch.json, used by analyze)"),
    "analyze": ("hoop_tape_miner.analyze", "pass 4: identities, possessions, tactical metrics"),
    "ball-track": ("hoop_tape_miner.ball", "smoothed ball track from the detections + ball-to-rim distances"),
    "rim-scan": ("hoop_tape_miner.rim_scan", "ball-sized movers in the air at each rim (video pass, CPU)"),
    "shot-proposals": ("hoop_tape_miner.shots", "shot attempts from rim arcs; made / likely miss from the official chart"),
    "track-eval": ("hoop_tape_miner.track_eval", "tracking quality: label-free proxies from a run; HOTA / IDF1 vs labelled MOT clips"),
    "review": ("hoop_tape_miner.review", "pass 5: annotated possession sheets for event review"),
    "coach-sheets": ("hoop_tape_miner.coach_review", "film-review sheets + lineup intervals for the coach review"),
    "shot-locate": ("hoop_tape_miner.shot_locate", "court-grid sheets per shot, merge the agent-read shot spots"),
    "merge-reviews": ("hoop_tape_miner.merge_reviews", "merge reviewed event parts after checking sheet coverage"),
    "coach-check": ("hoop_tape_miner.coach_schema", "validate coach review trips (schema v2); --migrate converts v1 parts"),
    "coach-summary": ("hoop_tape_miner.coach_summary", "aggregate coach review trips into per-segment numbers"),
    "coach-features": ("hoop_tape_miner.coach_features", "per-trip numbers from the court tracks (numbers back, spacing); ball quality"),
    "coach-insights": ("hoop_tape_miner.coach_insights", "check insights.json (evidence, KB, numbers, critic); blind A/B rating sheet"),
    "coach-eval": ("hoop_tape_miner.coach_eval", "score the coach review against official facts; lint insights"),
    "load": ("hoop_tape_miner.load", "running load per stint from the tracks: distance, sprints, top speed -> load.json"),
    "matchups": ("hoop_tape_miner.matchups", "defender distance at each reviewed shot + who guarded whom -> matchups.json"),
    "report": ("hoop_tape_miner.report", "pass 6: figures + stats.json"),
    "official": ("hoop_tape_miner.official", "league box score + score flow + video alignment"),
    "plusminus": ("hoop_tape_miner.plusminus", "on-court plus-minus per player from lineups + official score flow"),
    "momentum": ("hoop_tape_miner.momentum", "score-margin figure with scoring runs and on-court lanes"),
    "replay": ("hoop_tape_miner.replay", "2D tactics-board replay (mp4) of possessions from CV tracks"),
    "posters": ("hoop_tape_miner.posters", "telestrate clip posters: ring the players a clip is about, arrow fouler -> fouled"),
    "reels": ("hoop_tape_miner.reels", "9:16 phone reel of one player's clips, crop follows the player (never published)"),
    "program": ("hoop_tape_miner.program", "personal training-plan app: build the page, pull the progress synced from its link"),
    "season": ("hoop_tape_miner.season", "every game folder -> season page: results, Four Factors trends, targets checked, pooled on/off; --brief"),
    "train": ("hoop_tape_miner.train_run", "one personal training session end to end: phone videos -> page, film, next plan"),
    "train-new": ("hoop_tape_miner.train_new", "start a training session: session folder + joined session.mp4"),
    "train-scan": ("hoop_tape_miner.train_scan", "training: player pose, shot/finish candidates, dribble segments"),
    "train-sheets": ("hoop_tape_miner.train_sheets", "training: rim probe, rep and dribble review sheets, briefs"),
    "train-summary": ("hoop_tape_miner.train_summary", "training: reviewed reps -> summary.json, facts.md, figures"),
    "move": ("hoop_tape_miner.move_run", "one movement session end to end: clips -> gait metrics, review, page, film"),
    "move-new": ("hoop_tape_miner.move_new", "start a movement session: segments of any video -> movement.json + reel"),
    "move-scan": ("hoop_tape_miner.move_scan", "movement: pose per segment at native fps -> contacts, gait metrics"),
    "move-sheets": ("hoop_tape_miner.move_sheets", "movement: skeleton overlay reel, key-frame sheets, label strips, briefs"),
    "move-summary": ("hoop_tape_miner.move_summary", "movement: label check, review -> summary.json, facts.md, figures"),
}


def _is_game(d: dict) -> bool:
    return d.get("kind") in (None, "game")


def _clip_windows(folder: Path) -> list[tuple[str, str]]:
    from . import film_index  # lazy: listing plugins must stay cheap
    return film_index.windows(folder)


def _claims(target: str) -> bool:
    """A Glory League game url (fetched into a game folder by `run`)."""
    return target.startswith(("http://", "https://")) and "gloryleague" in target and "/game/" in target


PLUGIN = Plugin(
    name="basketball",
    summary="amateur basketball games (tracking, league box score, coach film review) and personal training sessions "
            "-> bilingual team / player pages with narration and clips, explained film",
    use_when="a league basketball game (stats site link), or tracking a fixed-camera full-court game from a clone (uv sync, GPU), "
             "or a player's own workout or movement clips; pickup game or phone clip without a league: generic",
    stages=STAGES,
    kinds=[
        Kind("game", "game.json", "hoop_tape_miner.run:Game", "hoop_tape_miner.run:STEPS", match=_is_game,
             driver="run", levels=1),
        Kind("training", "session.json", "hoop_tape_miner.train_run:Session", "hoop_tape_miner.train_run:TRAIN_STEPS",
             driver="train"),
        Kind("movement", "movement.json", "hoop_tape_miner.move_run:Session", "hoop_tape_miner.move_run:MOVE_STEPS",
             driver="move"),
        Kind("season", "season.json", driver="season"),
    ],
    prompts=Path(__file__).resolve().parents[2] / "prompts",
    clip_windows=_clip_windows,
    claims=_claims,
    page=page_hooks.PAGE,
    scenes=film_hooks.SCENES,
    film=film_hooks.FILM,
    site=site_hooks.SITE,
    requires=("pandas", "scipy", "sklearn", "matplotlib", "torch", "ultralytics", "supervision", "transformers"),
    install="a clone with the tracking extras: git clone https://github.com/mariusDing/sports-video-coach, `uv sync` "
            "in it, then `uv run ...` (docs/basketball.md)",
)
