"""Page hook: the measured stroke rate above the report."""
import json
from pathlib import Path


def stroke_file(folder) -> Path:
    from .unit import Analysis
    return Analysis.load(folder).run / "stroke" / "stroke.json"


def stroke_box(folder, band, langs) -> str:
    p = stroke_file(folder)
    if not p.exists():
        return ""
    d = json.loads(p.read_text(encoding="utf8"))
    return (f"<p><strong>Stroke rate (measured):</strong> {d['stroke_rate_spm']} cycles/min "
            f"(one cycle every {d['cycle_s']} s)</p>")
