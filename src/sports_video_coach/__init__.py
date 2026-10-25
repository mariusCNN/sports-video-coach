"""sports-video-coach: an agent-first framework that turns sports and training videos into coaching deliverables.

The core (this package) owns the step-table driver (command steps run, agent steps stop with exit 3 and say what
to do), provenance, media helpers, clips, narration, the HTML page, the explained film and publishing. Sports live
in plugins (see `plugin.py`): basketball (`hoop_tape_miner`) and the built-in `generic` plugin ship with the repo.
"""

REPO_URL = "https://github.com/mariusDing/sports-video-coach"
# The revision every install command in the docs, the skill and the demo site pins (tests/test_install_pin.py
# checks they all name this one, and that it is a commit of this repo). Move it to a release tag when one is cut.
INSTALL_REF = "ac27030efdd1c7008e3174650ff16f81f7c41187"
INSTALL = f"uv tool install git+{REPO_URL}@{INSTALL_REF}"
CLONE = f"git clone {REPO_URL} && cd sports-video-coach && git checkout {INSTALL_REF}"
