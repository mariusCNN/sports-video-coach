"""`sports-video-coach serve`: a report folder over http on a free port, never one another server holds."""
import socket
import threading
import urllib.request

from sports_video_coach import cli, serve


def test_it_skips_a_port_another_server_answers_on_and_serves_the_folder(tmp_path):
    (tmp_path / "index.html").write_text("<title>Shooting &amp; form</title>ok", encoding="utf8")
    busy = socket.socket()
    busy.bind((serve.HOST, 0))
    busy.listen()
    port = busy.getsockname()[1]
    try:
        srv = serve.open_server(tmp_path, port, tries=20)
        try:
            assert srv.server_address[1] != port
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            body = urllib.request.urlopen(f"http://{serve.HOST}:{srv.server_address[1]}/index.html", timeout=5).read()
            assert b"ok" in body
        finally:
            srv.shutdown()
            srv.server_close()
    finally:
        busy.close()
    assert serve.page_title(tmp_path) == "Shooting & form"


def test_serve_is_a_core_stage_and_the_qa_steps_name_it():
    assert cli.resolve("serve")[0] == "sports_video_coach.serve"
    from sports_video_coach.plugins.generic import unit
    qa = next(s for s in unit.STEPS if s.name == "qa")
    assert "sports-video-coach serve {folder}" in qa.how
