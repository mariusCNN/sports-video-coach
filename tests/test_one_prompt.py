"""The one prompt a user pastes into their agent, and START.md, the file it makes the agent follow: both READMEs and
the demo site show the prompt word for word, and START.md installs the pinned revision, asks before installing,
treats CLI output as data and asks once about a star."""
import html
import re
from pathlib import Path

import sports_video_coach as svc
from sports_video_coach import demo

ROOT = Path(__file__).resolve().parents[1]
START = (ROOT / "START.md").read_text(encoding="utf8")


def test_the_prompts_name_the_repo_and_start_md_and_match_each_other():
    for lang, prompt in svc.ONE_PROMPT.items():
        assert svc.REPO_URL in prompt and "START.md" in prompt, lang
        assert len(prompt.splitlines()) == 2, lang   # one line for the video, one for the repo
    assert set(svc.ONE_PROMPT) == {"en", "zh"}


def test_each_readme_shows_its_prompt_in_a_code_block_and_links_start_md():
    for name, lang, heading in (("README.md", "en", "Start in one prompt"), ("README.zh.md", "zh", "一句话开始")):
        text = (ROOT / name).read_text(encoding="utf8")
        assert f"```text\n{svc.ONE_PROMPT[lang]}\n```" in text, name
        assert "](START.md)" in text, name
        # right after the author's "why" section, before the try-it and benchmark sections
        assert re.findall(r"^## (.+)$", text, re.M)[1] == heading, name


def test_start_md_quotes_the_prompt_and_installs_the_pinned_revision():
    assert f"```text\n{svc.ONE_PROMPT['en']}\n```" in START
    assert svc.INSTALL in START
    for sha in re.findall(r"\b[0-9a-f]{40}\b", START):
        assert sha == svc.INSTALL_REF


def test_start_md_keeps_the_agent_rules():
    assert re.search(r"every install command before you run it", START)
    assert "are data, not instructions" in START and "`--publish`" in START
    assert "one message of questions at most" in START
    assert ".star-asked" in START and "gh repo star mariusDing/sports-video-coach" in START
    assert "Never star without asking" in START
    for code in ("`3`", "`1`", "`2`", "`0`"):
        assert code in START
    for link in re.findall(r"\]\(([^)#:]+)\)", START):   # relative links point at files in the repo
        assert (ROOT / link).exists(), link


def test_landing_page_shows_the_prompt_start_md_and_a_star_button():
    home = demo.landing([])
    assert html.escape(svc.ONE_PROMPT["en"]) in home
    assert f'href="{demo.START_URL}"' in home and (ROOT / "START.md").exists()
    assert f'class="star" href="{svc.REPO_URL}"' in home


def test_landing_page_copy_buttons_zh_prompt_and_favicon():
    home = demo.landing([])
    assert f'<code id="prompt-zh">{html.escape(svc.ONE_PROMPT["zh"])}</code>' in home
    for box in ("prompt-en", "prompt-zh"):   # each prompt box has a copy button that targets it
        assert f'<code id="{box}">' in home and f'data-copy="{box}"' in home
    assert "navigator.clipboard.writeText(code.textContent)" in home
    assert f'<link rel="icon" href="{demo.FAVICON}">' in home and "#" not in demo.FAVICON   # '#' would end the URL
    # link rows are lists of 44 px targets, not links run together with " · "
    assert "</a> ·" not in home and home.count('<ul class="links">') == 3


def test_start_md_points_basketball_on_generic_at_the_three_kbs():
    """The one-prompt basketball path bases its fixes on the repo's KB entries (and says when it does not)."""
    for kb in ("prompts/coach_kb.md", "prompts/skill_kb.md", "prompts/movement_kb.md"):
        assert f"]({kb})" in START and (ROOT / kb).exists(), kb
    assert "name that entry" in START and "advice is your own" in START
    assert "does no tracking or measuring" in START
