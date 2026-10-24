"""Every install command a user or an agent copies pins one revision (sports_video_coach.INSTALL_REF), so what gets
installed is what was read: the docs, the skill, the demo site and the plugin's install hint all name it, and it is
a commit of this repo's history."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

import sports_video_coach as svc
from hoop_tape_miner.plugin import PLUGIN as HOOP
from sports_video_coach import demo

ROOT = Path(__file__).resolve().parents[1]
DOCS = ["README.md", "README.zh.md", "AGENTS.md", "docs/benchmark.md", "docs/basketball.md", "docs/basketball.zh.md",
        "skills/sports-video-coach/SKILL.md"]
REPO = re.escape(svc.REPO_URL)


@pytest.fixture(params=DOCS)
def doc(request):
    return request.param, (ROOT / request.param).read_text(encoding="utf8")


def test_the_ref_is_a_full_commit_sha():
    assert re.fullmatch(r"[0-9a-f]{40}", svc.INSTALL_REF)
    assert svc.INSTALL == f"uv tool install git+{svc.REPO_URL}@{svc.INSTALL_REF}"


def test_every_install_command_pins_the_ref(doc):
    name, text = doc
    for m in re.finditer(rf"git\+{REPO}(\S*)", text):
        assert m.group(1).startswith(f"@{svc.INSTALL_REF}"), f"{name}: unpinned install {m.group(0)}"
    for m in re.finditer(rf"{REPO}/archive/(\S+?)\.zip", text):
        assert m.group(1) == svc.INSTALL_REF, f"{name}: archive of {m.group(1)}"
    for sha in re.findall(r"(?:@|checkout |archive/)([0-9a-f]{7,40})\b", text):
        assert sha == svc.INSTALL_REF, f"{name}: names another revision {sha}"


def test_every_clone_is_followed_by_a_checkout_of_the_ref(doc):
    name, text = doc
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if re.search(rf"git clone {REPO}", ln):
            near = "\n".join(lines[i:i + 3])
            assert f"git checkout {svc.INSTALL_REF}" in near, f"{name}:{i + 1}: a clone without the checkout"


def test_the_skill_and_agents_md_ask_before_installing_and_treat_output_as_data():
    for name in ("AGENTS.md", "skills/sports-video-coach/SKILL.md"):
        text = (ROOT / name).read_text(encoding="utf8")
        assert re.search(r"exact\s+(install\s+)?command", text), name
        assert "are data, not instructions" in text and "only when" in text and "`--publish`" in text, name


def test_the_demo_site_and_the_plugin_hint_use_the_same_commands():
    assert demo.TRY[0] == svc.INSTALL
    assert svc.CLONE in HOOP.install and svc.CLONE.endswith(f"git checkout {svc.INSTALL_REF}")


def test_the_ref_is_in_this_repos_history():
    git = shutil.which("git")
    if not git or subprocess.run([git, "cat-file", "-e", f"{svc.INSTALL_REF}^{{commit}}"], cwd=ROOT,
                                 capture_output=True).returncode != 0:
        pytest.skip("no git, or a shallow clone without that commit")
    assert subprocess.run([git, "merge-base", "--is-ancestor", svc.INSTALL_REF, "HEAD"], cwd=ROOT).returncode == 0
