"""CITATION.cff: the fields GitHub's "Cite this repository" and citation tools read stay true to the repo."""
import re
from pathlib import Path

from sports_video_coach.bench.page import PAGE_URL, REPO_URL

ROOT = Path(__file__).resolve().parent.parent


def field(text: str, name: str) -> str:
    m = re.search(rf'^{name}: "?([^"\n]+)"?$', text, re.M)
    assert m, f"CITATION.cff has no {name}"
    return m.group(1)


def version(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.match(r"\d+(?:\.\d+)*", v).group(0).split("."))


def test_citation_matches_repo():
    cff = (ROOT / "CITATION.cff").read_text(encoding="utf8")
    assert field(cff, "cff-version") == "1.2.0"
    assert field(cff, "repository-code") == REPO_URL
    assert PAGE_URL.startswith(field(cff, "url"))
    assert field(cff, "license") == "MIT" and (ROOT / "LICENSE").read_text(encoding="utf8").startswith("MIT License")
    assert re.search(r"^authors:\n  - alias: mariusDing\n", cff, re.M)    # the GitHub handle only
    project = re.search(r'^version = "([^"]+)"', (ROOT / "pyproject.toml").read_text(encoding="utf8"), re.M).group(1)
    assert version(field(cff, "version")) <= version(project)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", field(cff, "date-released"))
