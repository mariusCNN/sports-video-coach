import json
import subprocess
from types import SimpleNamespace

from sports_video_coach import cli, doctor


def ready(monkeypatch, tmp_path):
    monkeypatch.setattr(doctor.sys, "version_info", (3, 11, 18))
    monkeypatch.setattr(doctor.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(doctor.importlib.metadata, "version", lambda name: "test")
    monkeypatch.setattr(doctor.shutil, "which", lambda name: str(tmp_path / name))
    monkeypatch.setattr(doctor.subprocess, "run", lambda *a, **k: SimpleNamespace(
        returncode=0, stdout="media tool version test\n", stderr=""))
    monkeypatch.setenv("SVC_WORKSPACE", str(tmp_path / "not-created"))


def test_doctor_reports_ready_without_creating_workspace(monkeypatch, tmp_path, capsys):
    ready(monkeypatch, tmp_path)
    assert cli.resolve("doctor")[0] == "sports_video_coach.doctor"
    assert doctor.main(["--json", "--agent", "codex"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] and all(row["status"] == "ok" for row in result["checks"])
    assert not (tmp_path / "not-created").exists()


def test_missing_agent_is_optional_until_selected(monkeypatch, tmp_path, capsys):
    ready(monkeypatch, tmp_path)
    monkeypatch.setattr(doctor.shutil, "which", lambda name: None if name in doctor.AGENTS else name)
    assert doctor.main(["--json"]) == 0
    assert json.loads(capsys.readouterr().out)["checks"][-1]["status"] == "warn"
    assert doctor.main(["--agent", "codex"]) == 1


def test_media_timeout_and_missing_binary_are_actionable(monkeypatch, tmp_path):
    ready(monkeypatch, tmp_path)
    monkeypatch.setattr(doctor.shutil, "which", lambda name: None)
    assert doctor.binary_check("ffprobe", "ffprobe")["status"] == "fail"
    monkeypatch.setattr(doctor.shutil, "which", lambda name: name)

    def timeout(*args, **kwargs):
        assert kwargs["timeout"] == 5 and kwargs["stdin"] == subprocess.DEVNULL
        raise subprocess.TimeoutExpired(args[0], 5)

    monkeypatch.setattr(doctor.subprocess, "run", timeout)
    assert doctor.binary_check("ffmpeg", "ffmpeg")["status"] == "fail"


def test_workspace_file_fails_without_overwriting_it(monkeypatch, tmp_path, capsys):
    ready(monkeypatch, tmp_path)
    target = tmp_path / "occupied"
    target.write_text("keep")
    monkeypatch.setenv("SVC_WORKSPACE", str(target))
    assert doctor.main(["--json"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert next(row for row in result["checks"] if row["name"] == "workspace")["status"] == "fail"
    assert target.read_text() == "keep"
