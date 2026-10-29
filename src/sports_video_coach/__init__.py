"""sports-video-coach: an agent-first framework that turns sports and training videos into coaching deliverables.

The core (this package) owns the step-table driver (command steps run, agent steps stop with exit 3 and say what
to do), provenance, media helpers, clips, narration, the HTML page, the explained film and publishing. Sports live
in plugins (see `plugin.py`): basketball (`hoop_tape_miner`) and the built-in `generic` plugin ship with the repo.
"""

REPO_URL = "https://github.com/mariusDing/sports-video-coach"
# The revision every install command in the docs, the skill and the demo site pins (tests/test_install_pin.py
# checks they all name this one, and that it is a commit of this repo). Move it to a release tag when one is cut.
INSTALL_REF = "6845ffe9ddbfb79b8a52a5087ac26f566ef1fb4a"
INSTALL = f"uv tool install git+{REPO_URL}@{INSTALL_REF}"
CLONE = f"git clone {REPO_URL} && cd sports-video-coach && git checkout {INSTALL_REF}"


def installed_commit() -> str:
    """The commit this tool was installed from, as `uv tool install git+...@<sha>` records it in direct_url.json;
    '' without that record (a local-path or editable install)."""
    import json
    import re
    from importlib import metadata
    commit = ""
    try:
        raw = metadata.distribution("sports-video-coach").read_text("direct_url.json") or "{}"
        commit = json.loads(raw).get("vcs_info", {}).get("commit_id", "")
    except (metadata.PackageNotFoundError, ValueError, AttributeError):
        pass
    return commit if re.fullmatch(r"[0-9a-f]{40}", commit or "") else ""


def installed_ref() -> str:
    """The commit this tool was installed from (installed_commit), else INSTALL_REF. Text that tells an installed
    user what to check out names this: a pinned commit's own INSTALL_REF is the commit before it."""
    return installed_commit() or INSTALL_REF
