"""sports-video-coach: an agent-first framework that turns sports and training videos into coaching deliverables.

The core (this package) owns the step-table driver (command steps run, agent steps stop with exit 3 and say what
to do), provenance, media helpers, clips, narration, the HTML page, the explained film and publishing. Sports live
in plugins (see `plugin.py`): basketball (`hoop_tape_miner`) and the built-in `generic` plugin ship with the repo.
"""
