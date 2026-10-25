"""The report guides cap the small-print `note` block, so a page's data note stays scannable on a phone."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CAP = re.compile(r"note`? to at most two short sentences \(<= 220 characters; Chinese <= 110\).{0,200}?"
                 r"`::: more [^`]+` fold", re.S)


@pytest.mark.parametrize("guide", [
    "prompts/coach_report.md",
    "prompts/player_deep_dive.md",
    "src/sports_video_coach/plugins/generic/prompts/report.md",
    "examples/plugins/swim-stroke-rate/prompts/report.md",
])
def test_guide_caps_the_note_and_folds_the_rest(guide):
    text = " ".join((ROOT / guide).read_text(encoding="utf8").split())  # the guides wrap lines anywhere
    assert CAP.search(text), f"{guide}: the note block has no length cap"
