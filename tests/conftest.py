import pytest


@pytest.fixture(autouse=True)
def _empty_workspace(tmp_path_factory, monkeypatch):
    """Tests never read the real workspace (its profile, plugins, logs); a test may still point it elsewhere."""
    monkeypatch.delenv("SVC_WORKSPACE", raising=False)
    monkeypatch.delenv("SVC_PLUGIN_PATH", raising=False)
    monkeypatch.setenv("HOOP_WORKSPACE", str(tmp_path_factory.mktemp("ws")))
    from sports_video_coach import plugin
    monkeypatch.setattr(plugin, "_EXTRA", [])  # plugin folders found above an earlier test's unit
