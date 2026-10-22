"""The core must not know any sport: no `hoop_tape_miner` import or module reference in sports_video_coach."""
import re
from pathlib import Path

import sports_video_coach

CORE = Path(sports_video_coach.__file__).parent
REF = re.compile(r"(from|import)\s+hoop_tape_miner|['\"]hoop_tape_miner[.:]")  # imports and module strings


def test_core_never_references_the_basketball_package():
    bad = [f"{p.relative_to(CORE)}:{i}: {line.strip()}"
           for p in CORE.rglob("*.py")
           for i, line in enumerate(p.read_text(encoding="utf8").splitlines(), 1)
           if REF.search(line)]
    assert bad == []
