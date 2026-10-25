"""Page hook: the measured skip count above the report."""
import json
from pathlib import Path


def skip_file(folder) -> Path:
    from .unit import Analysis
    return Analysis.load(folder).run / "skip" / "skip.json"


def skip_box(folder, band, langs) -> str:
    p = skip_file(folder)
    if not p.exists():
        return ""
    d = json.loads(p.read_text(encoding="utf8"))
    return f"<p><strong>Skips (measured):</strong> {d['skips']} in {d['duration_s']} s ({d['skips_per_min']}/min)</p>"
