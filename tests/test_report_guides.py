"""The report guides cap the small-print `note` block, so a page's data note stays scannable on a phone."""
import re
from pathlib import Path

import pytest

PROMPTS = Path(__file__).resolve().parents[1] / "prompts"
CAP = re.compile(r"note`? to at most two short sentences \(<= 220 characters; Chinese <= 110\).{0,200}?"
                 r"`::: more [^`]+` fold", re.S)


@pytest.mark.parametrize("guide", ["coach_report.md", "player_deep_dive.md"])
def test_guide_caps_the_note_and_folds_the_rest(guide):
    text = " ".join((PROMPTS / guide).read_text(encoding="utf8").split())  # the guides wrap lines anywhere
    assert CAP.search(text), f"{guide}: the note block has no length cap"
