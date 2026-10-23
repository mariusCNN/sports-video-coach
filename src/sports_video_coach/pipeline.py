"""The step-table driver shared by `run` (games), `train` (training sessions) and `move` (movement sessions).

A driver is a list of Steps. A "cmd" step runs a stage (core or the unit's plugin); an "agent" step stops the run (exit 3)
and prints what the agent has to do. `drive` walks the list: done steps are skipped, the next command steps run
(long ones log to <workspace>/logs/), a failed command stops the run with exit 1 and its log tail, and exit 0
means everything is done. `--until` stops after a step (done or not), `--redo` runs a done step again, and
publish runs only with `--publish`.

Freshness (make-style, as in Snakemake / DVC / doit): a cmd step that declares `inputs` is done when its own
check passes AND its provenance record still matches: a signature of each input file (content hash for files
under 1 MB, else size + mtime), the step's `params`, and the run stamp of the steps named in `after` (for
inputs a later stage rewrites, such as tracks.pkl). Records live in <folder>/.hoop-steps.json. A change to any
of them makes the step stale, so `--redo X` (or a new input) re-runs the steps that depend on X. Folders from
before provenance have no records: their steps count as done by their own check, and `drive` writes the records
on its first walk (`--status` and `--dry` never write).

Agent steps keep their own checks; one that declares `derives` (each output with the files it is written from)
is also out of date when one of those inputs changed after the output was last seen and the agent has not
touched the output since: a corrected review or report waits for the narration and film scripts to follow it.
An agent step may also declare `checks` (e.g. a narration script whose stated length is off its read time): what
they find keeps the step waiting until the files are fixed. `--accept X [Y ...]` records agent steps as they are
(the scripts still hold, the findings are fine). A step marked `needs_all` (QA) counts as done only while every
step before it is done. A stop on agent steps lists every one that waits that way, so one pass fixes them all.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, ClassVar

from . import artifacts, clips, media, workspace
from . import langs as L

WAITING = 3
LANGS = ("zh", "en")  # the default report languages; langs.CODES lists every one the core knows
STORE = ".hoop-steps.json"
SMALL = 1 << 20      # files below this size are signed by content, larger ones by size + mtime


def profile_langs(allowed: tuple = L.CODES) -> tuple:
    """Report languages from team.json `languages` (default zh + en), each one of `allowed` (default: every
    language of langs.py; a plugin whose charts know fewer passes its own)."""
    langs = tuple(dict.fromkeys(workspace.profile().get("languages") or LANGS))
    bad = [l for l in langs if l not in allowed]
    if bad:
        sys.exit(f"team.json languages {list(langs)}: {bad} not supported (choose from {list(allowed)})")
    return langs


def unit_langs(data: dict, allowed: tuple = L.CODES) -> tuple:
    """Report languages of a unit: its json `languages` (what `run <folder> --lang` writes), else the profile's."""
    if not data.get("languages"):
        return profile_langs(allowed)
    langs = tuple(dict.fromkeys(data["languages"]))
    bad = [l for l in langs if l not in allowed]
    if bad:
        sys.exit(f"unit json languages {list(langs)}: {bad} not supported (choose from {list(allowed)})")
    return langs


def readme(lang: str) -> str:
    """README.md is the Chinese report, README.<lang>.md any other language (langs.readme)."""
    return L.readme(lang)


def localised(name: str, lang: str) -> str:
    """momentum.png for zh, momentum.<lang>.png otherwise."""
    stem, dot, ext = name.rpartition(".")
    return name if lang == "zh" else f"{stem}.{lang}{dot}{ext}"


# ---- what a driver walks over ------------------------------------------------------------------------------

@dataclass
class Unit:
    """One folder a driver works on (a game or a session): its json, run folder, video, review folder, pages."""
    folder: Path
    game: dict
    langs: tuple = LANGS

    JSON = "game.json"
    PLUGIN: ClassVar[str | None] = None   # the plugin whose stages the cmd steps run (None: core stages only)
    LANG_CHOICES: ClassVar[tuple] = L.CODES  # what `run <folder> --lang` may choose (a plugin's charts may know fewer)

    @property
    def gj(self) -> Path:
        return self.folder / self.JSON

    @property
    def run(self) -> Path:
        return self.folder / "run"

    @property
    def video(self) -> Path | None:
        return None

    @property
    def review(self) -> Path:
        return self.run / "review"

    def reports(self) -> list[Path]:
        """Report folders (each gets an index.html)."""
        return [self.folder]

    def fill_values(self) -> dict:
        """Placeholders for agent instructions ({folder}, {run}, {qa}, ...); {readmes} names only the READMEs not
        written yet when some are (a language added), else every one."""
        todo = [l for l in self.langs if not (self.folder / readme(l)).exists()] or self.langs
        return dict(folder=self.folder, run=self.run, review=self.review, video=self.video,
                    langs=", ".join(self.langs), readmes=" + ".join(readme(l) + (" (Chinese)" if l == "zh" else "") for l in todo), qa=qa_hash(self),
                    pages=" ".join(d.as_posix() for d in self.reports()))

    def fill(self, how: str) -> str:
        """Paths print with forward slashes, so `{run}/review/review.json` is one style on Windows too."""
        vals = {k: v.as_posix() if isinstance(v, Path) else v for k, v in self.fill_values().items()}
        return how.format(**vals)

    def note(self, step: str, errors: list[str]) -> str | None:
        """An extra line printed when an agent step waits (e.g. why an old game now fails a stricter check)."""
        return None

    def finished(self):
        print(f"[run] done: {slash(self.folder)}")

    @classmethod
    def load(cls, folder: Path) -> "Unit":
        raise NotImplementedError


class Session(Unit):
    """A personal session folder (training or movement): <JSON>, run/<REVIEW>, one page in the folder itself."""
    REVIEW = "review"
    VIDEO = "video.mp4"
    LABEL = "session"
    PLAN = "plan"         # what plan.json holds, for the closing line

    def path(self, key: str, default: str) -> Path:
        """A path value of the session json (absolute, or relative to the session folder), else folder/default."""
        v = self.game.get(key)
        p = Path(v).expanduser() if v else Path(default)
        return p if p.is_absolute() else Path(self.folder) / p

    @property
    def run(self) -> Path:
        return self.path("run", "run")

    @property
    def video(self) -> Path | None:
        return self.path("video", self.VIDEO)

    @property
    def review(self) -> Path:
        return self.run / self.REVIEW

    def fill_values(self) -> dict:
        return dict(super().fill_values(), player=self.game.get("player"))

    def finished(self):
        films = [self.folder / f"film.{l}.mp4" for l in self.langs]
        got, old = kept(self, html=[self.folder / "index.html"], film=films)
        print(f"[{self.LABEL}] done. Page: {slash(self.folder / 'index.html')}" if "html" in got
              else f"[{self.LABEL}] done.")
        if "film" in got:
            print(f"[{self.LABEL}] explained video (send it yourself, it is not published): "
                  + ", ".join(map(slash, films)))
        print(f"[{self.LABEL}] {self.PLAN}: {slash(self.folder / 'plan.json')}")
        if old:
            print(f"[{self.LABEL}] {old}")


@dataclass
class Step:
    name: str
    kind: str                                   # "cmd": run it; "agent": stop and say what to do
    done: Callable[[Unit], bool]                # the step's own check (outputs exist / pass)
    args: Callable[[Unit], list[list[str]]] = field(default=lambda g: [])   # cmd: one or more stage argv
    how: str = ""                               # agent: instructions ({run}, {folder}, ... filled in)
    long: bool = False                          # cmd: log to a file instead of the terminal
    expect_exit: bool = False                   # cmd: a non-zero exit is the expected stop (tracks pass 1)
    errors: Callable[[Unit], list[str]] | None = None   # agent: why its output does not pass yet (printed when waiting)
    inputs: Callable[[Unit], list[Path] | None] | None = None   # cmd: files it reads (None = nothing to track now)
    params: Callable[[Unit], dict] | None = None                # cmd: settings that shape its output
    after: tuple = ()                           # cmd: steps whose re-run makes this one stale
    again: tuple = ()                           # cmd: extra argv when it re-runs over existing outputs
    artifact: str | None = None                 # the deliverable it builds (artifacts.NAMES); None = always runs
    derives: Callable[[Unit], list[tuple[Path, list[Path]]]] | None = None  # agent: (output, files it follows)
    checks: Callable[[Unit], list[str]] | None = None   # agent: what to fix in its outputs first (--accept keeps it)
    needs_all: bool = False                     # done only while every step before it is done (QA checks them)
    passed: Callable[[Unit], str] | None = None  # agent: the line a run prints when its output passes the check


def newer(out: Path, *inputs: Path, slack: float = 2.0) -> bool:
    """out exists and no input changed after it (slack: files copied together differ by milliseconds)."""
    if not out.exists():
        return False
    t = out.stat().st_mtime + slack
    return all(not i.exists() or i.stat().st_mtime <= t for i in inputs)


# ---- provenance ----------------------------------------------------------------------------------------------

def signature(p: Path) -> str:
    """'sha1:<hash>' for a small file, '<size>:<mtime_ns>' for a large one, 'missing' when absent."""
    try:
        st = p.stat()
    except OSError:
        return "missing"
    if p.is_dir():
        return "dir"
    if st.st_size < SMALL:
        return "sha1:" + hashlib.sha1(p.read_bytes()).hexdigest()[:16]
    return f"{st.st_size}:{st.st_mtime_ns}"


def input_key(g: Unit, p: Path) -> str:
    """An input's name in the record: relative to the folder, else run/<rel>, else ext/<file name> (so moving the
    folder or the run does not make steps stale)."""
    for base, prefix in ((g.folder, ""), (g.run, "run/")):
        try:
            return prefix + Path(p).relative_to(base).as_posix()
        except ValueError:
            pass
    return "ext/" + Path(p).name


class Store:
    """<folder>/.hoop-steps.json: {"version": 1, "steps": {name: record}, "notes": {...}}; an unreadable file counts
    as empty. `notes` holds what the run remembers outside the steps (the READMEs' signatures: language_drift)."""

    def __init__(self, folder: Path):
        self.path = Path(folder) / STORE
        try:
            data = json.loads(self.path.read_text(encoding="utf8"))
            self.steps, self.notes = data.get("steps") or {}, data.get("notes") or {}
        except (OSError, ValueError, AttributeError):
            self.steps, self.notes = {}, {}

    def get(self, name: str) -> dict | None:
        return self.steps.get(name)

    def save(self):
        data = {"version": 1, "steps": self.steps, **({"notes": self.notes} if self.notes else {})}
        media.write_json_atomic(self.path, data, indent=1)


def language_drift(g: Unit, store: Store) -> list[str]:
    """One warning per README edited since the last run while another language's README stayed as it was: that
    language's README, listen and film scripts may no longer say the same (the guides: the same facts in every
    language). Records the READMEs' signatures in the store's notes (the caller saves), so each edit warns once.
    A README written for the first time (a language added) is not an edit, nor is an edit to one a warning named
    (bringing it in line must not warn back about the README that was edited first)."""
    if len(g.langs) < 2:
        return []
    old = store.notes.get("readmes") or {}
    was_owed = set(store.notes.get("readmes_owed") or ())  # READMEs a warning asked to bring in line
    owed = set(was_owed)
    now = {input_key(g, d / readme(l)): signature(d / readme(l))
           for d in g.reports() for l in g.langs if (d / readme(l)).exists()}
    out = []
    for d in g.reports():
        keys = {l: input_key(g, d / readme(l)) for l in g.langs}
        changed = [l for l, k in keys.items() if k in old and k in now and old[k] != now[k]]
        owed -= {keys[l] for l in changed}
        edited = [l for l in changed if keys[l] not in was_owed]
        kept = [l for l, k in keys.items() if k in old and old[k] == now.get(k)]
        if not edited or not kept:
            continue
        owed |= {keys[l] for l in kept}
        others = [p for o in kept for p in (d / readme(o), d / f"listen.{o}.md", g.folder / f"film.{o}.md")
                  if p.exists()]
        names = ", ".join(dict.fromkeys(slash(p.as_posix()) for p in others))
        out.append(f"{' and '.join(keys[l] for l in edited)} changed since the last run; the other languages' "
                   f"files may no longer match it: {names} (bring them in line if the facts changed; nothing "
                   f"waits on this)")
    if now != old:
        store.notes["readmes"] = now
    if owed != was_owed:
        store.notes["readmes_owed"] = sorted(owed)
    return out


def current(step: Step, g: Unit, store: Store) -> dict | None:
    """What the step's record would hold now (None: the step tracks nothing at the moment)."""
    files = step.inputs(g) if step.inputs else None
    if files is None:
        return None
    params = json.loads(json.dumps(step.params(g) if step.params else {}, default=str))
    return dict(inputs={input_key(g, p): signature(Path(p)) for p in files if p is not None}, params=params,
                after={d: (store.get(d) or {}).get("run") for d in step.after})


def changes(step: Step, g: Unit, store: Store) -> list[str]:
    """What changed since the step's record; [] when fresh, untracked, or never recorded (older folders)."""
    rec = store.get(step.name)
    cur = current(step, g, store) if rec is not None else None
    if cur is None:
        return []
    old, new = rec.get("inputs") or {}, cur["inputs"]
    out = [k for k in sorted(set(old) | set(new)) if old.get(k) != new.get(k)]
    if (rec.get("params") or {}) != cur["params"]:
        out.append("params")
    out += [f"{d} ran again" for d in step.after if (rec.get("after") or {}).get(d) != cur["after"][d]]
    return out


def record(step: Step, g: Unit, store: Store) -> bool:
    """Write the step's record as things are now (new run stamp); False when the step tracks nothing."""
    cur = current(step, g, store)
    if cur is None:
        return False
    store.steps[step.name] = dict(cur, run=uuid.uuid4().hex[:8], at=dt.datetime.now().isoformat(timespec="seconds"))
    return True


def derived(step: Step, g: Unit) -> dict:
    """An agent step's record of its outputs: per output, its signature and those of the files it is written from."""
    return {input_key(g, o): dict(sig=signature(o), inputs={input_key(g, p): signature(p) for p in ins})
            for o, ins in step.derives(g)}


def outdated(step: Step, g: Unit, store: Store) -> list[str]:
    """Outputs of an agent step whose inputs changed since the run last saw them, while the output itself did not
    (an output the agent edited since counts as following the change). [] without `derives` or a record."""
    rec = (store.get(step.name) or {}).get("outputs") if step.derives else None
    if rec is None:
        return []
    out = []
    for o, ins in step.derives(g):
        r = rec.get(input_key(g, o))
        if not r or r.get("sig") != signature(o):
            continue
        moved = [input_key(g, p) for p in ins if (r.get("inputs") or {}).get(input_key(g, p)) != signature(p)]
        if moved:
            out.append(f"{input_key(g, o)}: {', '.join(moved)} changed after it was written")
    return out


def note_outputs(step: Step, g: Unit, store: Store) -> bool:
    """Save what an agent step's outputs follow now; False when that is already the record (nothing to write)."""
    if not step.derives:
        return False
    now = derived(step, g)
    if (store.get(step.name) or {}).get("outputs") == now:
        return False
    store.steps[step.name] = dict(store.get(step.name) or {}, outputs=now,
                                  at=dt.datetime.now().isoformat(timespec="seconds"))
    return True


def flagged(step: Step, g: Unit, store: Store) -> list[str]:
    """What the step's `checks` find now, less what `--accept` recorded as fine."""
    if not step.checks:
        return []
    ok = (store.get(step.name) or {}).get("accepted") or []
    return [c for c in step.checks(g) if c not in ok]


def pending(step: Step, g: Unit, store: Store) -> list[str]:
    """Why an agent step whose files exist still waits: outputs out of date, then check findings."""
    return outdated(step, g, store) + flagged(step, g, store)


def accept_step(step: Step, g: Unit, store: Store) -> None:
    """`--accept`: the step's check findings as they are now count as fine (its outputs are noted after)."""
    if step.checks:
        store.steps[step.name] = dict(store.get(step.name) or {}, accepted=step.checks(g))


def adopt(steps: list[Step], g: Unit, store: Store) -> None:
    """Record every tracked step that passes its own check but has no record yet (a folder from before provenance),
    in order, so a later --redo makes its dependants stale. Saves the store when anything was added."""
    added = False
    for s in steps:
        if s.kind == "cmd" and s.inputs and store.get(s.name) is None and s.done(g):
            added = record(s, g, store) or added
    if added:
        store.save()


# ---- QA and publish (shared by every driver) ---------------------------------------------------------------

def qa_hash(g: Unit) -> str:
    """Stamp of what QA checks: the text of each report's pages and READMEs, plus the name and size of its audio
    and clips. Any edit after QA changes it. READMEs of languages beyond zh / en count only when they exist, so
    the stamps of zh / en units stay as they were."""
    h = hashlib.sha256()
    more = [L.readme(c) for c in L.CODES if c not in ("zh", "en")]
    for d in g.reports():
        names = ["index.html", "README.md", "README.en.md", *(n for n in more if (d / n).exists())]
        for p in [d / n for n in names]:
            h.update(f"{p.relative_to(g.folder).as_posix()}\0".encode())
            h.update(p.read_bytes() if p.exists() else b"-")
        for p in sorted([*d.glob("listen.*.mp3"), *d.glob("clips/*")]):
            h.update(f"{p.relative_to(g.folder).as_posix()}\0{p.stat().st_size}\0".encode())
    return h.hexdigest()[:16]


def qa_errors(g: Unit) -> list[str]:
    """Why qa.md does not count yet; [] when it starts with PASS and carries the stamp of the files as they are now."""
    qa = g.folder / "qa.md"
    if not qa.exists():
        return []           # not written yet: the step's instructions say what to do
    text = qa.read_text(encoding="utf8")
    errs = []
    if not text.lstrip().upper().startswith("PASS"):
        errs.append("qa.md does not start with PASS (fix what it lists, rebuild, check again)")
    stamp = re.search(r"checked:\s*([0-9a-f]{16})", text)
    now = qa_hash(g)
    if not stamp:
        errs.append(f"qa.md has no `checked: {now}` line")
    elif stamp.group(1) != now:
        errs.append(f"the pages, READMEs, audio or clips changed after QA (stamp {stamp.group(1)}, now {now}): "
                    f"check again, then write `checked: {now}`")
    return errs


def qa_done(g: Unit) -> bool:
    """qa.md starts with PASS and carries the stamp of the files as they are now (`checked: <qa_hash>`)."""
    return (g.folder / "qa.md").exists() and not qa_errors(g)


QA_STAMP = (" No browser? `sports-video-coach page-check --strict --write-qa {pages}` checks links, media and the "
            "text of the page and scripts (not layout or playback) and writes a qa.md draft that says what was not "
            "checked; read it, add what you checked yourself."
            " Then make sure qa.md has the line `checked: {qa}` (the stamp of the files you checked; an edit after "
            "QA changes it and the run asks for QA again). The run also waits on page-check's text warnings "
            "(leftover English, mojibake, French straight quotes) until they are fixed or `--accept qa` keeps "
            "them.")


def qa_checks(g: Unit) -> list[str]:
    """page-check's text warnings for each built report page (the page's report parts and the scripts next to
    it), so a PASS in qa.md does not hide them; no ffprobe or link checks here (those are in qa.md's job)."""
    from . import page_check
    return [f"{d.relative_to(g.folder).as_posix() if d != g.folder else '.'}: {w}" for d in g.reports()
            if (d / "index.html").exists() for w in page_check.warnings(d)]


def published(g: Unit) -> bool:
    """Every report page was uploaded by a successful `publish --deploy` after its index.html was last built
    (a failed deploy, or a publish without --deploy, does not count)."""
    from . import publish
    path = workspace.root() / "publish.json"
    if not path.exists():
        return False
    reg = publish.load_registry(path)
    root = workspace.root().resolve()
    for d in g.reports():
        try:
            key = d.resolve().relative_to(root).as_posix()
        except ValueError:
            return False
        if not publish.is_published(reg, key, d / "index.html"):
            return False
    return True


def reports_done(g: Unit) -> bool:
    return all((d / readme(l)).exists() for d in g.reports() for l in g.langs)


def clips_done(g: Unit) -> bool:
    """Every clip the reports mark is cut; not done while a report folder has no README yet."""
    return all(any((d / n).exists() for n in clips.READMES) for d in g.reports()) and \
        all(clips.clip_path(d, a, b).exists() for d in g.reports() for a, b in clips.find_clips(d))


def film_done(g: Unit) -> bool:
    return all(newer(g.folder / f"film.{l}.mp4", g.folder / f"film.{l}.md") for l in g.langs)


def listen_done(g: Unit) -> bool:
    return all(newer(d / f"listen.{l}.mp3", d / f"listen.{l}.md") for d in g.reports() for l in g.langs)


def html_inputs(g: Unit) -> list[Path]:
    return [x for d in g.reports() for x in (*(d / readme(l) for l in g.langs), g.gj, *sorted(d.glob("listen.*.mp3")),
                                             *sorted(d.glob("clips/*.mp4")))]


def html_done(g: Unit) -> bool:
    def inputs(d: Path) -> list[Path]:
        return [*(d / readme(l) for l in g.langs), g.gj, *d.glob("listen.*.mp3"), *d.glob("clips/*.mp4")]
    return all(newer(d / "index.html", *inputs(d)) for d in g.reports())


def missing(paths: list[Path], g: Unit) -> list[str]:
    """`missing: <path> (Chinese)` per file not written yet, so the agent sees each exact name (listen.zh.md); every
    language but English is named."""
    def note(p):
        code = "".join(p.name.split(".")[-2:-1])
        return f" ({L.name(code)})" if code in L.LANGS and code != "en" else ""
    return [f"missing: {slash(p.as_posix())}{note(p)}" for p in paths if not p.exists()]


def listen_checks(g: Unit) -> list[str]:
    """A narration script whose stated length ("about 2 minutes") is off its read time, per script written."""
    from . import narrate
    found = [narrate.length_problem(d / f"listen.{l}.md", l) for d in g.reports() for l in g.langs
             if (d / f"listen.{l}.md").exists()]
    return [p for p in found if p]


def tail_steps(video: Callable[[Unit], Path], listen_how: str, qa_how: str, film_script_how: str,
               film_run: bool = False) -> list[Step]:
    """The steps every driver ends with: clips -> narration -> page -> QA -> publish -> explained video.
    `video` is what clips and the film cut from; film_run passes --run (games: the film draws the tracks)."""
    def film_args(g):
        return [["film", str(g.folder), "--video", str(video(g)), *(["--run", str(g.run)] if film_run else [])]]
    return [
        Step("clips", "cmd", clips_done, lambda g: [["clips", str(d), "--video", str(video(g))] for d in g.reports()],
             inputs=lambda g: [video(g)], again=("--force",), artifact="clips"),  # a new video re-cuts every clip
        Step("listen-script", "agent",
             lambda g: all((d / f"listen.{l}.md").exists() for d in g.reports() for l in g.langs), how=listen_how,
             artifact="narration",
             errors=lambda g: missing([d / f"listen.{l}.md" for d in g.reports() for l in g.langs], g),
             derives=lambda g: [(d / f"listen.{l}.md", [d / readme(l)]) for d in g.reports() for l in g.langs],
             checks=listen_checks),  # a wrong "about N minutes" is fixed before the TTS render, not after
        Step("narrate", "cmd", listen_done, lambda g: [["narrate", str(d), "--lang", *g.langs] for d in g.reports()],
             inputs=lambda g: [d / f"listen.{l}.md" for d in g.reports() for l in g.langs], artifact="narration"),
        Step("html", "cmd", html_done, lambda g: [["html", str(d)] for d in g.reports()], inputs=html_inputs,
             artifact="html"),
        Step("qa", "agent", qa_done, how=qa_how + QA_STAMP, errors=qa_errors, artifact="qa", needs_all=True,
             checks=qa_checks),
        Step("publish", "cmd", published, lambda g: [["publish", *map(str, g.reports()), "--deploy"]],
             artifact="publish"),
        Step("film-script", "agent", lambda g: all((g.folder / f"film.{l}.md").exists() for l in g.langs),
             how=film_script_how, artifact="film",
             errors=lambda g: missing([g.folder / f"film.{l}.md" for l in g.langs], g),
             derives=lambda g: [(g.folder / f"film.{l}.md", [d / readme(l) for d in g.reports()]) for l in g.langs]),
        Step("film", "cmd", film_done, film_args, long=True,
             inputs=lambda g: [*(g.folder / f"film.{l}.md" for l in g.langs), video(g)], again=("--force",),
             artifact="film"),  # film keeps a language whose mp4 is newer than its script; a new video re-renders all
    ]


# ---- running -------------------------------------------------------------------------------------------------

def logs_dir(g: Unit | None = None) -> Path:
    """<workspace>/logs for a unit inside the workspace; else the unit's own run/logs, so a unit made with --out
    elsewhere never leaves a stray workspace/ folder in the current directory."""
    d = workspace.root() / "logs"
    if g is not None and not g.folder.resolve().is_relative_to(workspace.root().resolve()):
        d = g.run / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def stage_cmd(argv: list[str], plugin: str | None = None) -> list[str]:
    """The child process for one stage: `python -m sports_video_coach.cli <stage> ...`, a plugin stage qualified as
    `<plugin>:<stage>` so two plugins may share a stage name."""
    from . import cli
    head = argv[0] if not argv or plugin is None or ":" in argv[0] or argv[0] in cli.CORE else f"{plugin}:{argv[0]}"
    return [sys.executable, "-m", "sports_video_coach.cli", *([head] if argv else []), *argv[1:]]


def tail(path: Path, n: int = 15) -> str:
    lines = path.read_text(encoding="utf8", errors="replace").splitlines()
    return "\n".join(lines[-n:])


def slash(text) -> str:
    """Paths in run output with forward slashes on Windows too, so every line pastes into Git Bash as it is."""
    return str(text).replace("\\", "/") if os.sep == "\\" else str(text)


def child_env() -> dict:
    """The environment for stage subprocesses: UTF-8 stdio, so Chinese text in a log file or on a cp1252 / GBK
    Windows console never raises UnicodeEncodeError; unbuffered, so an agent reading the run through a pipe sees
    each progress line when it is printed, not all of them when the stage ends."""
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
    from . import plugin
    if found := plugin.search_path():  # e.g. a plugin found above the unit folder: its stages find it too
        env["SVC_PLUGIN_PATH"] = found
    return env


def shown(argv: list[str], plugin: str | None = None) -> str:
    """The stage command as a user can paste it: `sports-video-coach <plugin>:<stage> ...` (what stage_cmd runs)."""
    return slash("sports-video-coach " + " ".join(stage_cmd(argv, plugin)[3:]))


def run_cmd(step: Step, g: Unit, runner=subprocess.run, argvs: list[list[str]] | None = None) -> bool:
    """Run a command step; long ones log to a file and only the tail is printed on failure."""
    env = child_env()
    for i, argv in enumerate(step.args(g) if argvs is None else argvs):
        print(f"[run] {step.name}: {shown(argv, g.PLUGIN)}", flush=True)
        if step.long:
            log = logs_dir(g) / f"{g.folder.parent.name}-{g.folder.name}-{step.name}{i or ''}.log"
            print(f"[run]   log: {slash(log)}", flush=True)
            with open(log, "w", encoding="utf8") as fh:
                rc = runner(stage_cmd(argv, g.PLUGIN), stdout=fh, stderr=subprocess.STDOUT, env=env).returncode
        else:
            log, rc = None, runner(stage_cmd(argv, g.PLUGIN), env=env).returncode
        if rc != 0 and not step.expect_exit:
            print(f"[run] {step.name} failed (exit {rc})" + (f"; last lines of {slash(log)}:\n{tail(log)}" if log else
                  ": the error is in the lines above (this step prints to the console, it keeps no log)"))
            return False
    return True


def rows(g: Unit, steps: list[Step]) -> list[tuple[str, str, bool, list[str]]]:
    """(name, kind, done, what changed) per step, read-only: a step whose own check passes but whose inputs
    changed since its record is not done, and the changes say why."""
    store = Store(g.folder)
    out, waiting = [], []
    for s in artifacts.keep(steps, g):
        ok = s.done(g)
        why = (changes(s, g, store) + (pending(s, g, store) if s.kind == "agent" else [])) if ok else []
        if ok and not why and s.needs_all and waiting:
            why = [f"waits for {', '.join(waiting)}"]
        if not (ok and not why) and s.name != "publish":
            waiting.append(s.name)
        out.append((s.name, s.kind, ok and not why, why))
    return out


def status(g: Unit, steps: list[Step]) -> list[tuple[str, str, bool]]:
    return [(n, k, ok) for n, k, ok, _ in rows(g, steps)]


def print_status(g: Unit, steps: list[Step]) -> None:
    for name, kind, ok, why in rows(g, steps):
        stale = f"  (stale: {', '.join(why[:4])}{' ...' if len(why) > 4 else ''})" if why else ""
        if name == "publish" and not ok:  # optional: a finished run without --publish is not missing a step
            print(f"  skip  {name:13s} {kind}  (only with --publish)")
            continue
        print(f"  {'done' if ok else '----'}  {name:13s} {kind}{stale}")


def drive(g: Unit, steps: list[Step], until: str | None = None, redo: str | None = None, publish: bool = False,
          dry: bool = False, runner=subprocess.run, accept: str | list[str] | None = None) -> int:
    """Walk `steps` and return the exit code: 0 done (or stopped at --until), 3 waiting for the agent, 1 failed.
    `accept`: the agent steps (one name or several) to take as they are."""
    steps = artifacts.keep(steps, g)  # exits on a bad `artifacts` choice before any step runs
    accept = {accept} if isinstance(accept, str) else set(accept or ())
    store = Store(g.folder)
    if not dry:
        adopt(steps, g, store)
        before = json.dumps(store.notes, sort_keys=True)
        for w in language_drift(g, store):
            print(f"[run] warning: {w}")
        if json.dumps(store.notes, sort_keys=True) != before:
            store.save()
    for i, s in enumerate(steps):
        if s.name == "publish" and not publish:
            if not s.done(g):
                print("[run] publish skipped: re-run with --publish to deploy the pages as links")
            if s.name == until:
                print(f"[run] paused after {until} (--until): the steps after it run next time")
                return 0
            continue
        own = s.done(g)
        why = changes(s, g, store) if own else []
        stale = pending(s, g, store) if own and s.kind == "agent" else []
        if stale and s.name in accept and not dry:
            print(f"[run] {s.name}: accepted as it is ({len(stale)} finding(s) kept: inputs changed or a check)")
            accept_step(s, g, store)
            store.save()
            stale = []
        if own and not why and not stale and s.name != redo:
            if not dry and note_outputs(s, g, store):
                store.save()
            if s.passed and not dry:
                print(f"[run] {s.passed(g)}")
            if s.name == until:
                print(f"[run] paused after {until} (--until; it was already done)")
                return 0
            continue
        if s.kind == "agent":
            if not dry:
                g.review.mkdir(parents=True, exist_ok=True)   # where review.json and the helpers' parts go
            if stale:  # every agent step waiting this way, so one pass fixes them all
                later = [(t, pending(t, g, store)) for t in steps[i + 1:]
                         if t.kind == "agent" and t.name not in accept and t.done(g)]
                waits = [(s, stale), *((t, w) for t, w in later if w)]
                for k, (t, w) in enumerate(waits):
                    what = "is out of date" if outdated(t, g, store) else "has something to fix"
                    print(f"[run] waiting for the agent: {t.name} {what}" if k == 0 else f"[run] {t.name} {what} too")
                    for e in w[:12]:
                        print(f"[run]   {slash(e)}")
                names = [t.name for t, _ in waits]
                print(f"[run] Fix those files (bring them in line with what changed), then run again. They hold as "
                      f"they are? `{run_hint(g, '--accept', *names)}`.\n"
                      + slash(f"[run] The step, for reference: {g.fill(s.how)}"))
                return WAITING
            print(slash(f"[run] waiting for the agent: {s.name}\n{g.fill(s.how)}"))
            errs = s.errors(g) if s.errors else []
            for e in errs[:12]:
                print(f"[run]   {slash(e)}")
            if len(errs) > 12:
                print(f"[run]   ... {len(errs) - 12} more")
            note = g.note(s.name, errs)
            if note:
                print(f"[run] note: {note}")
            return WAITING
        argvs = [[*a, *s.again] for a in s.args(g)] if own else s.args(g)
        if why:
            print(f"[run] {s.name}: changed since its last run: {', '.join(why[:6])}{' ...' if len(why) > 6 else ''}")
        if dry:
            for argv in argvs:
                print(f"[dry] {s.name}: {shown(argv, g.PLUGIN)}")
            return 0
        if not run_cmd(s, g, runner, argvs):
            return 1
        g = type(g).load(g.folder)  # stages may have filled game.json
        if record(s, g, store):
            store.save()
        if s.expect_exit and not s.done(g):
            print(f"[run] {s.name} did not produce its output; see its log")
            return 1
        if s.name == until:
            print(f"[run] paused after {until} (--until): the steps after it run next time")
            return 0
    print(built_line(g, publish))
    g.finished()
    return 0


def built_line(g: Unit, publish: bool) -> str:
    """One line at exit 0: which deliverables were built, which the unit's `artifacts` choice left out and the
    command that builds those too (publish stays out: it is only for links the user asks for)."""
    chosen = artifacts.selected(g)
    line = "[run] built: " + ", ".join(n for n in chosen if n != "publish" or publish)
    if "publish" in chosen and not publish:
        line += "; publish: only with --publish"
    known = artifacts.known(g)
    off = [n for n in known if n not in chosen]
    if off:
        line += f"; left out by \"artifacts\" in {getattr(g, 'JSON', 'the unit json')}: {', '.join(off)}"
    if [n for n in off if n != "publish"]:
        more = [n for n in known if n in chosen or n != "publish"]
        line += f"\n[run] to build them too: {run_hint(g, '--artifacts', *more)}"
    return line


def kept(g: Unit, **files: list[Path]) -> tuple[dict[str, list[Path]], str]:
    """Deliverable files per artifact (html=[...], film=[...]) split by the unit's `artifacts` choice: the existing
    files of the chosen ones, and a closing line naming the others' files left from an earlier run ('' when none),
    so the closing list never claims what this run left out."""
    chosen = artifacts.selected(g)
    shown, old = {}, []
    for name, paths in files.items():
        there = [p for p in paths if p.exists()]
        if name in chosen:
            shown[name] = there
        else:
            old += there
    if not old:
        return shown, ""
    names = [p.relative_to(g.folder).as_posix() if p.is_relative_to(g.folder) else slash(p) for p in old]
    audio = " (the page still plays it)" if "html" in chosen and any(p.name.startswith("listen.") for p in old) else ""
    return shown, f"kept from an earlier run, not built this time: {', '.join(names)}{audio}"


def run_hint(g: Unit, *args: str) -> str:
    """The full later-run command for a hint: `sports-video-coach run <folder> <args>` (folder quoted if needed)."""
    folder = f'"{g.folder}"' if " " in str(g.folder) else g.folder
    return slash(f"sports-video-coach run {folder} {' '.join(args)}".rstrip())


def add_drive_args(ap, names: list[str], pages: str = "pages") -> None:
    """The flags every driver takes."""
    ap.add_argument("--status", action="store_true", help="list every step and whether it is done")
    ap.add_argument("--dry", action="store_true", help="print the next command instead of running it")
    ap.add_argument("--until", choices=names, help="stop after this step")
    ap.add_argument("--redo", choices=names, help="run this step again even if its output exists (steps that "
                                                  "depend on it run again too)")
    ap.add_argument("--publish", action="store_true", help=f"also deploy the {pages} (publish --deploy) at the end")
    ap.add_argument("--accept", nargs="+", choices=names, metavar="STEP",
                    help="agent steps reported out of date (their inputs changed, or a check flagged them) that still "
                         "hold as they are: record them and go on (one or several: --accept listen-script film-script)")
