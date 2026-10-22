"""Publish reports as a private-link website, so the team opens one link instead of downloading files.

usage: sports-video-coach publish <report folder> [<report folder> ...]
       sports-video-coach publish ... --deploy --project <cloudflare-worker-name>
       sports-video-coach publish --deploy            (re-upload the site as it is)

Each report folder gets a random, stable path: re-publishing after an edit overwrites the same page, so the
link sent once keeps showing the latest version. Pages are the --share text (no local paths or repo links)
with audio and clips kept as files next to them, which in-app browsers play better than embedded data.
Reports are also listed on a hub page with its own random path. What the hub shows is up to the plugin that owns
each report folder (`Plugin.site`, a `SiteHooks`): which reports stay off it (personal pages, reachable only
through their own link), which groups are pinned on top (basketball: season pages) and the entry titles. With no
hooks every report is listed, titled by its README's first heading.

App pages (a plugin's `SiteHooks.app_page`, e.g. the basketball training-plan app of a program.json folder) are
published at /p/<token>/. Opened from that link, the app saves its progress to /api/sync/<token> (one Workers KV
namespace, <project>-sync, made on the first deploy that needs it), so it follows the user across devices.

Everything is built in <workspace>/site/ (paths -> tokens in <workspace>/publish.json, both gitignored) and
uploaded with `npx wrangler deploy` as Cloudflare Workers static assets (the successor of Pages; free plan,
run `npx wrangler login` once) behind publish_worker.js, which answers the Range requests Safari needs to play
clips. The site lands on https://<project>.<your-subdomain>.workers.dev.
The site is unlisted, not access-controlled: anyone holding a link can open it. See docs/privacy.md.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import re
import secrets
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import media, plugin
from . import workspace as ws


def _html():
    """The page renderer, imported on use: plugins import this module (SiteHooks) while they are listed."""
    from . import render_html
    return render_html

MAX_FILE = 25 * 1024 * 1024  # Cloudflare static assets per-file limit (25 MiB)
HEADERS = """/*
  X-Robots-Tag: noindex, nofollow
  Referrer-Policy: no-referrer
  X-Content-Type-Options: nosniff
"""  # publish_worker.js sets these (and a Content-Security-Policy) on every response, its own 206 answers too
ROBOTS = "User-agent: *\nDisallow: /\n"
BLANK = '<!doctype html><meta charset="utf-8"><meta name="robots" content="noindex"><title>.</title>\n'
LOCAL_SRC = re.compile(r'(src|poster)="((?!https?:|data:|#)[^"]+)"')
ASSET_EXT = {".mp3", ".mp4", ".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".vtt"}
SCRIPT = re.compile(r"<script>(.*?)</script>", re.S)


@dataclass
class SiteHooks:
    """What a plugin changes on the published site, for the report folders it owns. Every field is optional."""
    hidden: Callable[[Path], bool] | None = None           # never on the hub (still published at its own link)
    group: Callable[[Path], str | None] | None = None      # pinned group key of a hub entry (None: the plain list)
    groups: tuple[str, ...] = ()                           # pinned group keys, in hub order
    titles: Callable[[Path], dict[str, str]] | None = None  # {lang: title} of a hub entry (default: README headings)
    ui: dict[str, dict[str, str]] = field(default_factory=dict)  # hub wording per lang: "title", group key -> label
    is_app: Callable[[Path], bool] | None = None           # is this folder an app page (published at /p/<token>/)
    app_page: Callable[[Path], str] | None = None          # the app page html of such a folder


DEFAULT = SiteHooks()


def hooks_for(folder: Path) -> SiteHooks:
    """The site hooks of the plugin owning `folder`, else DEFAULT."""
    try:
        own = plugin.owner(folder)
    except (SystemExit, OSError, ValueError):  # a broken or foreign unit json: list the report plainly
        own = None
    return own[0].site if own and own[0].site else DEFAULT


def app_hooks(folder: Path) -> SiteHooks | None:
    """The hooks of the first plugin that publishes `folder` as an app page (app folders need no unit json)."""
    for p in plugin.plugins().values():
        h = p.site
        if h and h.is_app and h.app_page and h.is_app(folder):
            return h
    return None


def token() -> str:
    return secrets.token_hex(8)  # 64 bits: not guessable, short enough for a chat message


def load_registry(path: Path) -> dict:
    """publish.json, or its .bak when the file is broken. Exits rather than start over: a fresh registry would
    mint new tokens, and every link already sent would stop working."""
    reg = {}
    for p in (path, path.with_name(path.name + ".bak")):
        if not p.exists():
            continue
        try:
            reg = json.loads(p.read_text(encoding="utf8"))
            break
        except ValueError:
            print(f"warning: {p} is not valid JSON", file=sys.stderr)
    else:
        if path.exists():
            sys.exit(f"{path} is broken and has no readable .bak: restore it, or delete it to start new links")
    reg.setdefault("reports", {})
    reg.setdefault("programs", {})
    return reg


def save_registry(path: Path, reg: dict) -> None:
    """Write publish.json atomically (temp file + replace), keeping the previous good version as publish.json.bak."""
    if path.exists():
        try:
            json.loads(path.read_text(encoding="utf8"))
            shutil.copy2(path, path.with_name(path.name + ".bak"))
        except ValueError:
            pass  # never back up a broken file over a good .bak
    media.write_text_atomic(path, json.dumps(reg, indent=2) + "\n")


def is_published(reg: dict, key: str, page: Path) -> bool:
    """A successful deploy uploaded a build of this report made after `page` (its local index.html) was written."""
    built = (reg.get("deployed") or {}).get(key)
    return bool(built) and key in reg["reports"] and (not page.exists() or page.stat().st_mtime <= built + 2.0)


def report_key(folder: Path, root: Path) -> str:
    try:
        return folder.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        sys.exit(f"{folder} is not inside the workspace {root} (set HOOP_WORKSPACE)")


def pin_scripts(page: str) -> str:
    """Add a CSP meta tag that lets only the page's own inline script(s) run, by hash, so a script that slips
    into the page some other way does not."""
    hashes = " ".join("'sha256-" + base64.b64encode(hashlib.sha256(s.encode("utf8")).digest()).decode() + "'"
                      for s in SCRIPT.findall(page)) or "'none'"
    meta = (f'<meta http-equiv="Content-Security-Policy" content="script-src {hashes}; '
            "object-src 'none'; base-uri 'none'\">")
    return page.replace('<meta charset="utf-8">', '<meta charset="utf-8">\n' + meta, 1)


def build_report(folder: Path, dest: Path) -> list[str]:
    """Render the web page into dest (emptied first) and copy the audio/clip files it links to. Only media files
    inside the report folder are copied; any other reference is dropped from the page with a warning.
    Returns warnings (missing, outside or oversized files)."""
    page = _html().page(folder, share=True, embed=False)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    warnings, copy = [], {}
    root = folder.resolve()

    def keep(m):
        attr, rel = m.groups()
        src = _html().inside(folder, rel)
        if src is None or src.suffix.lower() not in ASSET_EXT:
            warnings.append(f"{folder.name}: {rel} is outside the report folder or not a media file; left out")
            return f'data-{attr}-removed=""'
        if src.is_file():
            copy[src.relative_to(root).as_posix()] = src
        else:
            warnings.append(f"{folder.name}: {rel} is linked but missing")
        return m.group(0)
    page = pin_scripts(LOCAL_SRC.sub(keep, page))
    (dest / "index.html").write_text(page, encoding="utf8")
    for rel, src in sorted(copy.items()):
        if src.stat().st_size > MAX_FILE:
            warnings.append(f"{folder.name}: {rel} is over 25 MiB, Cloudflare will reject it")
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest / rel)
    return sorted(set(warnings))


def build_program(folder: Path, dest: Path, hooks: SiteHooks | None = None) -> None:
    """The app page of an app folder (e.g. a training program) into dest (emptied first)."""
    hooks = hooks or app_hooks(folder)
    if hooks is None:
        sys.exit(f"{folder}: no plugin publishes it as an app page")
    page = pin_scripts(hooks.app_page(folder))
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    (dest / "index.html").write_text(page, encoding="utf8")


def is_program(folder: Path) -> bool:
    return app_hooks(folder) is not None


def has_report(folder: Path) -> bool:
    return any((folder / l[3]).exists() for l in _html().LANGS)


def title_of(folder: Path, readme: Path | None = None) -> str:
    m = re.match(r"# (.*)", (readme or _html().first_readme(folder)).read_text(encoding="utf8"))
    return m.group(1).strip() if m else folder.name


def titles_of(folder: Path) -> dict[str, str]:
    """Report title per language code, from each README the folder has (zh first)."""
    return {c: title_of(folder, folder / f) for c, _, _, f in _html().report_langs(folder)}


HUB_UI = {"zh": dict(title="报告", switch="切换语言"),
          "en": dict(title="Reports", switch="Switch language")}

HUB_JS = """<script>
(() => {
  const ui = %s, buttons = document.querySelectorAll("[data-set-lang]");
  function setLang(lang) {
    if (!ui[lang]) lang = Object.keys(ui)[0];
    document.querySelectorAll("main [data-lang]").forEach(el => { el.hidden = el.dataset.lang !== lang; });
    buttons.forEach(b => b.setAttribute("aria-pressed", String(b.dataset.setLang === lang)));
    document.querySelector(".lang").setAttribute("aria-label", ui[lang].switch);
    document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
    document.title = ui[lang].title;
    try { localStorage.setItem("report-lang", lang); } catch (e) {}  // same key as the report pages
    document.querySelectorAll("li a").forEach(a => {  // reports open in the language picked here
      const u = new URL(a.getAttribute("href"), location.href); u.searchParams.set("lang", lang); a.href = u.href; });
  }
  buttons.forEach(b => b.addEventListener("click", () => setLang(b.dataset.setLang)));
  let start = new URLSearchParams(location.search).get("lang");
  if (!start) { try { start = localStorage.getItem("report-lang"); } catch (e) {} }
  if (!start && !/^zh/i.test(navigator.language || "")) start = "en";
  setLang(start || Object.keys(ui)[0]);
})();
</script>
"""


def hub_page(entries: list[tuple[str, dict, str]], pinned: list[tuple[str, dict, str, str]] = (),
             wording: dict | None = None) -> str:
    """entries: (folder name, {lang: title}, token) of the listed reports, newest first; pinned: (folder name,
    {lang: title}, token, group key) of pinned reports, listed first (basketball: season pages), labelled
    "<wording[lang][group key]> <folder name>". wording: hub text per lang over HUB_UI. With more than one
    language the page gets the reports' 中文 / EN switch and shares their remembered choice."""
    have = {c for _, ts, *_ in [*pinned, *entries] for c in ts}
    langs = [l for l in _html().LANGS if l[0] in have] or _html().LANGS[:1]
    first = langs[0][0]
    ui = {}
    for c, *_ in langs:
        over = (wording or {}).get(c, {})
        ui[c] = {**over, **{k: v for k, v in HUB_UI.get(c, HUB_UI["en"]).items() if k not in over}}

    def spans(texts: dict) -> str:
        # one span per page language; a report missing that language shows its own first title
        fallback = next(iter(texts.values()), "")
        return "".join(f'<span data-lang="{c}" lang="{a}"{"" if c == first else " hidden"}>'
                       f'{html.escape(texts.get(c, fallback))}</span>' for c, a, _, _ in langs)

    def label(c: str, g: str, d: str) -> str:  # a group label missing in this language: any language's label
        lab = next((w[g] for w in (ui[c], *(wording or {}).values()) if g in w), "")
        return (lab + " " + d).strip()

    items = "".join(f'<li class="{html.escape(g)}"><a href="../{t}/"><small>{spans({c: label(c, g, d) for c in ui})}'
                    f'</small>{spans(ts)}</a></li>' for d, ts, t, g in pinned)
    items += "".join(f'<li><a href="../{t}/"><small>{html.escape(d)}</small>{spans(ts)}</a></li>'
                     for d, ts, t in entries)
    switch = script = ""
    if len(langs) > 1:
        switch = (f'<div class="lang" role="group" aria-label="{ui[first]["switch"]}">' + "".join(
            f'<button type="button" data-set-lang="{c}" lang="{a}" aria-pressed="{str(c == first).lower()}">{n}</button>'
            for c, a, n, _ in langs) + "</div>")
        script = HUB_JS % json.dumps(ui, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="{langs[0][1]}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>{html.escape(" · ".join(u["title"] for u in ui.values()))}</title>
<style>
body {{ margin: 0; font: 16px/1.5 system-ui, "PingFang SC", "Noto Sans SC", sans-serif; background: #f5f5f8; color: #221f45; }}
main {{ max-width: 640px; margin: 0 auto; padding: 28px 18px; }}
header {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; margin: 0 0 16px; }}
h1 {{ font-size: 22px; margin: 0; }}
ul {{ list-style: none; margin: 0; padding: 0; }}
li a {{ display: block; padding: 14px 16px; margin-bottom: 10px; background: #fff; border: 1px solid #dcdce6;
        border-radius: 10px; color: inherit; text-decoration: none; }}
li a:hover {{ border-color: #5b4bd1; }}
li.season a {{ border-color: #5b4bd1; border-width: 2px; }}
small {{ display: block; color: #6c6b84; }}
[hidden] {{ display: none !important; }}
.lang {{ display: inline-flex; border: 1px solid #b9b7d4; border-radius: 999px; padding: 2px; flex: none; }}
.lang button {{ font: 600 15px/1 system-ui, sans-serif; color: #5c5a86; background: none; border: 0;
  border-radius: 999px; padding: 7px 14px; cursor: pointer; }}
.lang button[aria-pressed="true"] {{ background: #221f45; color: #fff; }}
button:focus-visible, a:focus-visible {{ outline: 3px solid #f2c94c; outline-offset: 2px; }}
</style>
</head>
<body><main><header><h1>{spans({c: u["title"] for c, u in ui.items()})}</h1>{switch}</header><ul>{items}</ul></main>
{script}</body>
</html>
"""


def write_site(site: Path, reg: dict, root: Path) -> None:
    """The site skeleton and the hub page. Each report is listed by its own plugin's SiteHooks (DEFAULT: listed,
    README titles); hidden ones (e.g. basketball player-<N> pages and personal sessions) only have their own link."""
    site.mkdir(parents=True, exist_ok=True)
    (site / "_headers").write_text(HEADERS, encoding="utf8")
    (site / "robots.txt").write_text(ROBOTS, encoding="utf8")
    (site / "index.html").write_text(BLANK, encoding="utf8")
    plain, pinned, order, ui = [], [], {}, {}
    for key, t in reg["reports"].items():
        folder = root / key
        if not has_report(folder):
            continue
        h = hooks_for(folder)
        if h.hidden and h.hidden(folder):
            continue
        for c, words in h.ui.items():  # per word, the first listed plugin's wording wins
            for k, v in words.items():
                ui.setdefault(c, {}).setdefault(k, v)
        titles = (h.titles or titles_of)(folder)
        g = h.group(folder) if h.group else None
        if g is None:
            plain.append((folder.name, titles, t))
        else:
            order.setdefault(g, h.groups.index(g) if g in h.groups else len(h.groups) + len(order))
            pinned.append((folder.name, titles, t, g))
    if plain or pinned:
        reg.setdefault("hub", token())
        hub = site / reg["hub"]
        hub.mkdir(exist_ok=True)
        newest = sorted(pinned, key=lambda e: (e[0], e[2]), reverse=True)
        (hub / "index.html").write_text(hub_page(sorted(plain, key=lambda e: (e[0], e[2]), reverse=True),
                                                 sorted(newest, key=lambda e: order[e[3]]), ui), encoding="utf8")


def npx() -> str:
    exe = shutil.which("npx")
    if not exe:
        sys.exit("npx not found: install Node.js (https://nodejs.org) to deploy with wrangler")
    return exe


def worker_config(site: Path, project: str, out: Path, kv_id: str | None = None) -> Path:
    """wrangler.json + worker script in out/: the site as static assets, publish_worker.js in front of them,
    and the KV namespace that stores synced program progress when kv_id is given."""
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy(Path(__file__).with_name("publish_worker.js"), out / "worker.js")
    cfg = {"name": project, "main": "worker.js", "compatibility_date": "2026-10-01",
           "assets": {"directory": str(site.resolve()), "binding": "ASSETS", "run_worker_first": True}}
    if kv_id:
        cfg["kv_namespaces"] = [{"binding": "SYNC", "id": kv_id}]
    path = out / "wrangler.json"
    path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf8")
    return path


def wrangler(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([npx(), "--yes", "wrangler@4", *args], cwd=cwd, capture_output=True, text=True,
                          encoding="utf8", errors="replace")


def ensure_kv(project: str, workdir: Path) -> str:
    """Id of the KV namespace <project>-sync, created when the account does not have it yet."""
    name = f"{project}-sync"
    workdir.mkdir(parents=True, exist_ok=True)

    def find():
        r = wrangler("kv", "namespace", "list", cwd=workdir)
        if r.returncode:
            sys.exit(f"wrangler kv namespace list failed:\n{r.stderr[-1000:]}")
        try:
            spaces = json.loads(r.stdout[r.stdout.index("["):])
        except ValueError:
            sys.exit(f"could not read the KV namespace list from wrangler:\n{r.stdout[-1000:]}")
        # older wranglers prefix the title with the worker name
        return next((s["id"] for s in spaces if s.get("title") == name or s.get("title", "").endswith("-" + name)),
                    None)
    kv = find()
    if not kv:
        r = wrangler("kv", "namespace", "create", name, cwd=workdir)
        if r.returncode:
            sys.exit(f"wrangler kv namespace create {name} failed:\n{r.stderr[-1000:]}")
        kv = find()
        if not kv:
            sys.exit(f"created KV namespace {name} but cannot find it in `wrangler kv namespace list`")
    return kv


def deploy(site: Path, project: str, workdir: Path, kv_id: str | None = None) -> str | None:
    """Upload the site with its Worker; returns the workers.dev URL when wrangler prints one."""
    cfg = worker_config(site, project, workdir, kv_id)
    r = wrangler("deploy", "--config", str(cfg), cwd=workdir)
    enc = sys.stdout.encoding or "utf8"  # wrangler prints emoji; a cp1252 console or log file can't take them
    print((r.stdout[-2000:] + "\n" + r.stderr[-2000:]).encode(enc, "replace").decode(enc))
    if r.returncode:
        sys.exit("wrangler deploy failed (not logged in? run `npx wrangler login`)")
    m = re.search(r"https://[\w.-]+\.workers\.dev", r.stdout)
    return m.group(0) if m else None


def main(argv=None):
    ap = argparse.ArgumentParser(prog="publish", description=__doc__.split("\n\n")[0])
    ap.add_argument("folders", nargs="*", help="report folders (README.md + README.en.md) or app folders "
                    "(e.g. a training program.json) inside the workspace")
    ap.add_argument("--deploy", action="store_true", help="upload the site to Cloudflare (Workers static assets) with wrangler")
    ap.add_argument("--project", help="Cloudflare Worker name, part of the URL (remembered after the first use)")
    ap.add_argument("--base-url", help="site URL, e.g. a custom domain (remembered; else the workers.dev URL)")
    ap.add_argument("--new-link", action="store_true", help="give these folders a fresh path; old links stop working")
    a = ap.parse_args(argv)
    if not a.folders and not a.deploy:
        ap.error("give report folders and/or --deploy")

    root = ws.root()
    site, reg_path = root / "site", root / "publish.json"
    reg = load_registry(reg_path)
    for opt in ("project", "base_url"):
        if getattr(a, opt):
            reg[opt] = getattr(a, opt).rstrip("/")
    warnings = []
    for f in a.folders:
        folder = Path(f)
        app = app_hooks(folder)
        if app:
            key = report_key(folder, root)
            old = reg["programs"].get(key)
            if a.new_link or not old:  # a new link also starts a new, empty synced log
                if old and (site / "p" / old).exists():
                    shutil.rmtree(site / "p" / old)
                reg["programs"][key] = token()
            build_program(folder, site / "p" / reg["programs"][key], app)
            continue
        if not has_report(folder):
            sys.exit(f"{folder} has no README.md / README.en.md")
        key = report_key(folder, root)
        old = reg["reports"].get(key)
        if a.new_link or not old:
            if old and (site / old).exists():
                shutil.rmtree(site / old)
            reg["reports"][key] = token()
        warnings += build_report(folder, site / reg["reports"][key])
        reg.setdefault("built", {})[key] = time.time()
    write_site(site, reg, root)
    save_registry(reg_path, reg)  # tokens are kept even if the deploy below fails, so the links stay the same
    for w in warnings:
        print("warning:", w, file=sys.stderr)

    if a.deploy:
        if not reg.get("project"):
            sys.exit("first deploy needs --project <name> (lowercase letters, digits, dashes)")
        workdir = root / "publish-worker"
        if reg["programs"] and not reg.get("kv_id"):
            reg["kv_id"] = ensure_kv(reg["project"], workdir)
            save_registry(reg_path, reg)
        url = deploy(site, reg["project"], workdir, reg.get("kv_id"))  # exits on failure: nothing is marked live
        if url and not a.base_url:
            reg["base_url"] = url
        # the whole site went up, so every report is live as last built
        reg["deployed"] = {k: reg.get("built", {}).get(k, 0) for k in reg["reports"]}
        save_registry(reg_path, reg)
    base = reg.get("base_url") or "<site-url>"
    print(f"site folder: {site}")
    if reg.get("hub"):
        print(f"  team hub       {base}/{reg['hub']}/")
    for key in (a.folders and [report_key(Path(f), root) for f in a.folders]) or [*reg["reports"], *reg["programs"]]:
        if key in reg["programs"]:
            print(f"  {key:<40s} {base}/p/{reg['programs'][key]}/")
        else:
            print(f"  {key:<40s} {base}/{reg['reports'][key]}/")
    if not a.deploy:
        print("not uploaded yet: add --deploy")


if __name__ == "__main__":
    main()
