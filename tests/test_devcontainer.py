"""The Codespaces / Dev Containers rerun environment (`.devcontainer/`): it parses, pins what it pulls, holds no
secret, installs the light core, and the docs link it."""
import json
import re
from pathlib import Path

from sports_video_coach.bench import page

ROOT = Path(__file__).resolve().parents[1]
DC = ROOT / ".devcontainer"


def strip_jsonc(text: str) -> str:
    """JSON with `//` and `/* */` comments, minus the comments (a `//` inside a string, as in a URL, stays)."""
    return re.sub(r'("(?:\\.|[^"\\])*")|//[^\n]*|/\*.*?\*/', lambda m: m.group(1) or "", text, flags=re.S)


def config() -> dict:
    return json.loads(strip_jsonc((DC / "devcontainer.json").read_text(encoding="utf8")))


def test_strip_jsonc_keeps_urls_in_strings():
    assert json.loads(strip_jsonc('// c\n{"u": "https://x.y/z", /* c */ "v": 1} // c')) == {"u": "https://x.y/z", "v": 1}


def test_devcontainer_parses_and_pins_image_uv_and_features():
    c = config()
    docker = (DC / c["build"]["dockerfile"]).read_text(encoding="utf8")
    image = re.search(r"^FROM (\S+)", docker, re.M).group(1)
    assert image.startswith("mcr.microsoft.com/devcontainers/python:")
    assert re.search(r":\d+\.\d+\.\d+-3\.11-", image), image             # pyproject: >=3.11,<3.12
    assert re.search(r"ghcr\.io/astral-sh/uv:\d+\.\d+\.\d+ ", docker)
    assert "ffmpeg" in docker
    assert c["features"] and all(re.search(r":\d+$", f) for f in c["features"])
    assert all(opts.get("version") for opts in c["features"].values())


def test_devcontainer_installs_the_light_core_and_pinned_agent_clis():
    c = config()
    cmd = c["postCreateCommand"]
    assert "uv sync --locked --no-group basketball" in cmd                  # no torch, no CUDA
    assert c["containerEnv"]["UV_NO_GROUP"] == "basketball"                # nor on a later `uv run`
    assert "sports-video-coach bench --help" in cmd
    for cli in ("@anthropic-ai/claude-code@", "@openai/codex@"):
        assert re.search(re.escape(cli) + r"\d+\.\d+\.\d+", cmd), cli


def test_devcontainer_holds_no_secret():
    c = config()
    assert all(set(v) <= {"description", "documentationUrl"} for v in c.get("secrets", {}).values())
    text = "".join(p.read_text(encoding="utf8") for p in DC.iterdir())
    assert not re.search(r"sk-[A-Za-z0-9_-]{10,}|(?:API_KEY|TOKEN)\s*[=:]\s*\S", text)
    assert not re.search(r"[A-Za-z]:[/\\]Users|/home/(?!vscode)", text)    # no local path


def test_devcontainer_workflow_pins_the_action():
    wf = (ROOT / ".github" / "workflows" / "devcontainer.yml").read_text(encoding="utf8")
    assert re.search(r"devcontainers/ci@[0-9a-f]{40}\b", wf)
    assert "bench --help" in wf and "bench baseline" in wf


def test_docs_link_codespaces_next_to_the_rerun_command():
    for name in ("README.md", "README.zh.md", "docs/benchmark.md"):
        text = (ROOT / name).read_text(encoding="utf8")
        assert f"({page.CODESPACES_URL})" in text, name
        assert "#rerun-it-in-the-browser" in text or "## Rerun it in the browser" in text, name
