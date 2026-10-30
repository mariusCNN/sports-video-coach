"""Coaching knowledge base: every entry is complete and cites a source."""
import re
from pathlib import Path

KB = Path(__file__).resolve().parents[1] / "prompts" / "coach_kb.md"
LABELS = (
    "Symptom (observable)",
    "Why it happens",
    "What to check on film",
    "In-game rule",
    "Drill",
    "Next-game target",
    "Source",
)
PAGE_OR_URL = re.compile(r"(\bpp?\.\s*\d+|\bpages?\s+\d+|https?://)", re.IGNORECASE)


def parse_kb(text: str) -> dict[str, dict[str, str]]:
    """Return {slug: {label: text}} for every `### KB-<slug>` section."""
    entries: dict[str, dict[str, str]] = {}
    sections = re.split(r"^### KB-", text, flags=re.MULTILINE)[1:]
    label_re = re.compile(r"^\*\*(" + "|".join(map(re.escape, LABELS)) + r"):\*\*", re.MULTILINE)
    for sec in sections:
        slug, _, body = sec.partition("\n")
        slug = slug.strip()
        assert slug not in entries, f"duplicate slug KB-{slug}"
        body = re.split(r"^#{1,3} ", body, flags=re.MULTILINE)[0]
        marks = list(label_re.finditer(body))
        fields = {}
        for i, m in enumerate(marks):
            end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
            fields[m.group(1)] = body[m.end():end].strip()
        entries[slug] = fields
    return entries


def test_kb_entries_complete():
    entries = parse_kb(KB.read_text(encoding="utf-8"))
    assert len(entries) >= 10
    for slug, fields in entries.items():
        assert re.fullmatch(r"[a-z0-9-]+", slug), f"bad slug KB-{slug}"
        for label in LABELS:
            assert fields.get(label), f"KB-{slug}: missing or empty {label}"
        assert PAGE_OR_URL.search(fields["Source"]), f"KB-{slug}: Source needs a page ref or URL"


def test_kb_header_marks_own_numbers_and_rules():
    head = KB.read_text(encoding="utf-8").split("### KB-", 1)[0]
    assert "our own trial value" in head, "header must say targets and success measures are our trial values"
    assert '"(our rule)"' in head, "header must explain how our own rules are marked"


ROOT = KB.parents[1]
KB_FILES = {"coach_kb.md": "KB", "skill_kb.md": "KB", "movement_kb.md": "MV", "fuel_recovery_kb.md": "FR"}


def kb_counts() -> dict[str, int]:
    return {name: len(re.findall(rf"^### {prefix}-[a-z0-9-]+\s*$", (ROOT / "prompts" / name).read_text(encoding="utf-8"),
                                 re.MULTILINE)) for name, prefix in KB_FILES.items()}


def test_knowledge_base_doc_counts_match_the_files():
    """docs/knowledge-base.md and both READMEs state the entry counts; they follow the KB files."""
    counts = kb_counts()
    doc = (ROOT / "docs" / "knowledge-base.md").read_text(encoding="utf-8")
    for name, n in counts.items():
        row = next(ln for ln in doc.splitlines() if f"prompts/{name}" in ln and ln.startswith("|"))
        assert f"| {n}, `{KB_FILES[name]}-<slug>`" in row, name
    total = sum(counts.values())
    assert f"with {total} entries" in (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"共 {total} 条" in (ROOT / "README.zh.md").read_text(encoding="utf-8")


def test_every_kb_entry_cites_a_source():
    for name, prefix in KB_FILES.items():
        text = (ROOT / "prompts" / name).read_text(encoding="utf-8")
        for sec in re.split(rf"^### (?={prefix}-)", text, flags=re.MULTILINE)[1:]:
            assert "**Source:**" in sec.split("\n### ")[0], f"{name}: {sec.splitlines()[0]} has no Source"


def test_the_contribution_path_is_linked():
    form = ROOT / ".github" / "ISSUE_TEMPLATE" / "coaching_knowledge.yml"
    assert form.exists()
    for name in ("README.md", "README.zh.md", "CONTRIBUTING.md", "docs/knowledge-base.md"):
        assert "template=coaching_knowledge.yml" in (ROOT / name).read_text(encoding="utf-8"), name
    for link in re.findall(r"\]\(([^)#:]+)(?:#[^)]*)?\)", (ROOT / "docs" / "knowledge-base.md").read_text(encoding="utf-8")):
        assert (ROOT / "docs" / link).exists(), link
